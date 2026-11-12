#!/usr/bin/env python
"""Benchmark XAI · MESE (T1.c): integración y análisis descriptivo del LSTM entrenado en el LNS.

Criterios en results/xai_benchmark/proof_ledger.md, "Enmienda MESE", M1. Descriptivo: el LSTM no
entra en H1–H3, en el ensamble de alertas ni en la mediana de 6 pares de H2-a.

1. Verificación de lo bajado del LNS (como xai_03c): las 72 corridas de la partición principal y
   las 60 del walk-forward, con pesos; mismas muestras que los modelos en CPU; sin NaN. Horas-core
   de SLURM (sacct_lns.txt) y versiones (env_lns.txt).
2. Selección por horizonte (xai_15.select) y su coincidencia con la que usó el walk-forward.
3. Habilidad en la partición principal (como xai_05): NSE, KGE, RMSE y SS contra persistencia por
   estación evaluable, con la media de las 3 semillas; resumen por cuenca y agregado.
4. ΔNSE (LSTM − XGBoost): mediana con IC por bootstrap de estaciones y de los 23 grupos de RR-3.
5. Explicaciones: IG (64 pasos, línea base cero) en la muestra fija de xai_06, por semilla, con el
   error de completitud. Mapas de importancia como rq2_importance.csv.
6. Acuerdo y techo de ruido (RR-2): con el caché de RR-2 (mismas ventanas y mitades), las cinco
   medidas entre semillas y entre mitades del LSTM, y entre el LSTM y cada modelo aprendido, en las
   cuencas con ≥ 8 estaciones; un par queda bajo el techo si su medida es menor que la mínima de
   las medianas entre semillas de los dos modelos.
7. Walk-forward 2021–2025 (como xai_10): NSE, KGE y SS por estación evaluable de cada año, y ΔNSE
   contra XGBoost.

Entrada: --runs, la carpeta runs/ del LNS descomprimida (split/, wf/, env_lns.txt, sacct_lns.txt).
Salidas en results/xai_benchmark/mese/: lstm_import.json, lstm_manifest.csv,
lstm_station_metrics.csv, lstm_skill.csv, lstm_vs_xgboost.csv, lstm_importance.csv,
lstm_ig_delta.csv, lstm_concordance.csv, lstm_walkforward.csv, e_mese_lstm.json y
numbers.json → mese_lstm (correr después de xai_08, xai_12 y xai_14).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from datetime import date
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_18")
OUT = ROOT / "results" / "xai_benchmark"
MESE = OUT / "mese"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
TAG = "descriptivo (post hoc, MESE M1)"
SEEDS, SIZES, WF_SEED = (20261010, 20261011, 20261012), (32, 64), 20261010
YEARS = (2021, 2022, 2023, 2024, 2025)
SAMPLE_SEED, N_SAMPLE, IG_STEPS, MIN_N, MIN_STATIONS = 20261010, 2000, 64, 180, 8
LEARNED = ("xgboost", "tcn", "convnext", "patchtst")
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _r(x, n: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def _same_samples(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Como xai_03c: mismas claves, fechas (al día) y gasto observado."""
    if len(a) != len(b) or not (a["clave"].to_numpy() == b["clave"].to_numpy()).all():
        return False
    for c in ("issue", "target_date"):
        if not (a[c].to_numpy("datetime64[D]") == b[c].to_numpy("datetime64[D]")).all():
            return False
    return bool(np.allclose(a["y_flow"], b["y_flow"], equal_nan=True))


def _index(root: Path) -> tuple[dict, dict, dict]:
    preds = {p.stem: p for p in root.rglob("preds/lstm-*.npz")}
    weights = {p.stem: p for p in root.rglob("weights/lstm-*.pt")}
    metas = {}
    for p in root.rglob("meta/*.parquet"):
        metas.setdefault(p.stem, p)
    return preds, weights, metas


def _slurm_seconds(s: str) -> float:
    """[D-]HH:MM:SS[.mmm] o MM:SS[.mmm] → segundos."""
    if not isinstance(s, str) or not s:
        return 0.0
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    parts = [float(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return days * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


# ----------------------------------------------------------------------------- 1–2. verificación
def verify(runs: Path, X15) -> tuple[dict, dict, dict]:
    split, wf = runs / "split", runs / "wf"
    sp, sw, sm = _index(split)
    wp, ww, wm = _index(wf)
    exp_split = {f"lstm-{z}_{SLUG[b]}_h{h}_s{s}" for z in SIZES for b in D.BASINS for h in D.HORIZONS for s in SEEDS}
    bad_meta, nan_runs, len_bad = [], [], []
    for b in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            cpu = {p: pd.read_parquet(INTERIM / "cpu" / "meta" / f"{tag}_{p}.parquet") for p in ("val", "test")}
            for p in ("val", "test"):
                if f"{tag}_{p}" not in sm or not _same_samples(pd.read_parquet(sm[f"{tag}_{p}"]), cpu[p]):
                    bad_meta.append(f"split {tag}_{p}")
            for rid in sorted(r for r in exp_split & set(sp) if f"_{tag}_s" in r):
                d = np.load(sp[rid])
                if any(np.isnan(d[k]).any() for k in d.files):
                    nan_runs.append(rid)
                if any(len(d[f"{q}_{p}"]) != len(cpu[p]) for q in ("z", "flow") for p in ("val", "test")):
                    len_bad.append(rid)
    sel = X15.select(split)
    chosen = {int(r.h): int(r.config) for r in sel.itertuples() if r.elegida}
    exp_wf = {f"lstm-{chosen[h]}_{SLUG[b]}_h{h}_y{y}" for y in YEARS for b in D.BASINS for h in D.HORIZONS}
    for y in YEARS:
        for b in D.BASINS:
            for h in D.HORIZONS:
                tag = f"{SLUG[b]}_h{h}_y{y}"
                cpu = pd.read_parquet(INTERIM / "walk_forward" / "meta" / f"{tag}_test.parquet")
                if f"{tag}_test" not in wm or not _same_samples(pd.read_parquet(wm[f"{tag}_test"]), cpu):
                    bad_meta.append(f"wf {tag}")
                rid = f"lstm-{chosen[h]}_{tag}"
                if rid in wp:
                    d = np.load(wp[rid])
                    if any(np.isnan(d[k]).any() for k in d.files):
                        nan_runs.append(rid)
                    if len(d["flow_test"]) != len(cpu):
                        len_bad.append(rid)
    wf_sel = sorted(wf.rglob("lstm_selection.csv"))
    wf_chosen = {}
    if wf_sel:
        s = pd.read_csv(wf_sel[0])
        wf_chosen = {int(r.h): int(r.config) for r in s.itertuples() if r.elegida}
    man = []
    for part, root in (("split", split), ("wf", wf)):
        for p in sorted(root.rglob("compute_manifest.csv")):
            man.append(pd.read_csv(p).assign(origen=part, carpeta=p.parent.name))
    man = pd.concat(man, ignore_index=True) if man else pd.DataFrame()
    man.to_csv(MESE / "lstm_manifest.csv", index=False)
    sel.to_csv(MESE / "lstm_selection.csv", index=False)
    sacct_p, env_p = runs / "sacct_lns.txt", runs / "env_lns.txt"
    core = {}
    if sacct_p.exists():
        sa = pd.read_csv(sacct_p, sep="|")
        sa = sa[sa["JobName"].astype(str).str.startswith("lstm")]
        core = {"horas_core_asignadas": _r(sa["CPUTimeRAW"].sum() / 3600, 2),
                "horas_cpu_usadas": _r(sum(_slurm_seconds(x) for x in sa["TotalCPU"]) / 3600, 2),
                "trabajos": sa[["JobID", "JobName", "AllocCPUS", "Elapsed", "State"]].astype(str).to_dict("records")}
    env = [ln.strip("# \n") for ln in env_p.read_text(encoding="utf-8").splitlines() if ln.startswith("#")] \
        if env_p.exists() else []
    res = {"fecha": date.today().isoformat(), "fuente": "scripts/xai_18_mese_lstm.py",
           "corridas_principal": {"esperadas": len(exp_split), "predicciones": len(exp_split & set(sp)),
                                  "pesos": len(exp_split & set(sw)), "faltantes": sorted(exp_split - set(sp))},
           "corridas_walk_forward": {"esperadas": len(exp_wf), "predicciones": len(exp_wf & set(wp)),
                                     "pesos": len(exp_wf & set(ww)), "faltantes": sorted(exp_wf - set(wp))},
           "muestras_distintas": bad_meta, "corridas_con_nan": nan_runs, "longitudes_distintas": len_bad,
           "seleccion": {f"h{h}": f"lstm-{z}" for h, z in chosen.items()},
           "seleccion_coincide_con_walk_forward": wf_chosen == chosen if wf_chosen else None,
           "entorno_lns": env, "computo_slurm": core,
           "entrenamiento_segundos": _r(man["segundos"].sum(), 1) if len(man) else None}
    res["ok"] = (not (res["corridas_principal"]["faltantes"] or res["corridas_walk_forward"]["faltantes"]
                      or bad_meta or nan_runs or len_bad)
                 and res["corridas_principal"]["pesos"] == len(exp_split)
                 and res["corridas_walk_forward"]["pesos"] == len(exp_wf) and res["seleccion_coincide_con_walk_forward"])
    (MESE / "lstm_import.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    if not res["ok"]:
        raise SystemExit(f"La verificación del LSTM falló; ver {MESE / 'lstm_import.json'}")
    return res, chosen, {"split": (sp, sw), "wf": (wp, ww)}


# ----------------------------------------------------------------------------- 3–4. habilidad y ΔNSE
def skill(chosen: dict, files: dict, st: pd.DataFrame, groups: pd.Series, X14) -> tuple[dict, pd.DataFrame]:
    sp = files["split"][0]
    evaluable = {h: set(st.loc[(st["h"] == h) & (st["modelo"] == "persistencia"), "clave"]) for h in D.HORIZONS}
    rows = []
    for b in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            meta = pd.read_parquet(INTERIM / "cpu" / "meta" / f"{tag}_test.parquet")
            pers = np.load(INTERIM / "cpu" / "preds" / f"baselines_{tag}.npz")["persistence_test"]
            seeds = np.stack([np.load(sp[f"lstm-{chosen[h]}_{tag}_s{s}"])["flow_test"] for s in SEEDS])
            sim, obs = seeds.mean(0), meta["y_flow"].to_numpy()
            for k, idx in meta.groupby("clave").indices.items():
                if k not in evaluable[h]:
                    continue
                o, s = obs[idx], sim[idx]
                r_, alpha, beta = M.kge_components(o, s)
                rows.append({"cuenca": b, "h": h, "clave": k, "modelo": "lstm", "n": len(idx), "nse": M.nse(o, s),
                             "kge": M.kge(o, s), "rmse": M.rmse(o, s), "ss": M.skill_mse(o, s, pers[idx]),
                             "kge_r": r_, "kge_alpha": alpha, "kge_beta": beta,
                             "nse_semillas_sd": float(np.std([M.nse(o, x) for x in seeds[:, idx]]))})
    ls = pd.DataFrame(rows)
    ls.to_csv(MESE / "lstm_station_metrics.csv", index=False)
    summ = []
    for g, sub in [(b, ls[ls["cuenca"] == b]) for b in D.BASINS] + [("agregado", ls)]:
        for h, x in sub.groupby("h"):
            r = {"grupo": g, "h": h, "modelo": "lstm", "estaciones": int(x["clave"].nunique())}
            for met in ("nse", "kge", "rmse", "ss"):
                q = x[met].quantile([0.25, 0.5, 0.75])
                r.update({f"{met}_mediana": round(q[0.5], 4), f"{met}_q25": round(q[0.25], 4),
                          f"{met}_q75": round(q[0.75], 4)})
            if g == "agregado" or r["estaciones"] >= MIN_STATIONS:
                _, lo, hi = M.bootstrap_median_ci(x["ss"])
                r.update({"ss_ic_lo": round(lo, 4), "ss_ic_hi": round(hi, 4)})
            summ.append(r)
    pd.DataFrame(summ).to_csv(MESE / "lstm_skill.csv", index=False)
    xg = st[st["modelo"] == "xgboost"].set_index(["h", "clave"])["nse"]
    drows, dres = [], {}
    for h in D.HORIZONS:
        lh = ls[ls["h"] == h].set_index("clave")["nse"]
        d = (lh - xg.loc[h].reindex(lh.index)).dropna()
        cs = M.bootstrap_median_ci(d)
        cg = X14.group_median_ci(d, groups)
        for name, ci, n in (("estaciones", cs, len(d)), ("grupos_conectados", cg, int(groups.reindex(d.index).nunique()))):
            drows.append({"h": h, "remuestreo": name, "unidades": n, "mediana": _r(ci[0]), "ic_lo": _r(ci[1]),
                          "ic_hi": _r(ci[2])})
            dres[f"h{h}_{name}"] = [_r(v) for v in ci]
    pd.DataFrame(drows).to_csv(MESE / "lstm_vs_xgboost.csv", index=False)
    agg = pd.DataFrame(summ)
    agg = agg[agg["grupo"] == "agregado"].set_index("h")
    res = {"estaciones": int(ls["clave"].nunique()),
           "agregado": {f"h{h}": {k: _r(agg.loc[h, k]) for k in ("nse_mediana", "nse_q25", "nse_q75", "kge_mediana",
                                                               "ss_mediana", "ss_ic_lo", "ss_ic_hi")}
                        for h in D.HORIZONS},
           "delta_nse_vs_xgboost": dres}
    return res, ls


# ----------------------------------------------------------------------------- 5–6. explicaciones y acuerdo
def explain(chosen: dict, files: dict, big: list[str], threads: int, X14) -> dict:
    import torch

    from hidroxai_mx.models import nets
    from hidroxai_mx.xai import attributions as A
    torch.set_num_threads(threads)
    sw = files["split"][1]
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft
    rr2 = pd.read_csv(OUT / "rev_rr2_medidas.csv")
    imp_rows, delta_rows, conc_rows = [], [], []
    for b in D.BASINS:
        bp = {k: panels[k] for k in claves if basin_of[k] == b}
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            g = D.group_arrays(bp, h)
            meta = pd.read_parquet(INTERIM / "cpu" / "meta" / f"{tag}_test.parquet")
            assert meta[["clave", "issue"]].equals(g["test"]["meta"][["clave", "issue"]])
            idx = A.stratified_sample(meta, N_SAMPLE, SAMPLE_SEED)
            X = g["test"]["X"][idx]
            del g
            per_window = []
            for s in SEEDS:
                net = nets.build("lstm", chosen[h])
                net.load_state_dict(torch.load(sw[f"lstm-{chosen[h]}_{tag}_s{s}"], weights_only=True))
                attr, delta = A.integrated_gradients(net, X, n_steps=IG_STEPS)
                per_window.append(X14._per_window(attr))
                delta_rows.append({"cuenca": b, "h": h, "modelo": "lstm", "semilla": s,
                                   "delta_abs_mediana": float(np.median(np.abs(delta))),
                                   "delta_abs_p95": float(np.quantile(np.abs(delta), 0.95))})
            seedmaps = [p.mean(0) for p in per_window]
            full = np.mean(seedmaps, axis=0)
            for j in range(full.shape[0]):
                for c, ch in enumerate(D.CHANNELS):
                    imp_rows.append({"cuenca": b, "h": h, "modelo": "lstm", "canal": ch, "rezago_ventana": 29 - j,
                                     "rezago_objetivo": 29 - j + h, "importancia": float(full[j, c])})
            if b not in big:
                continue
            z = np.load(INTERIM / "review" / f"rr2_{tag}.npz")
            cl = z["claves"]
            assert (cl == meta["clave"].to_numpy()[idx].astype(str)).all(), f"muestra distinta de RR-2 en {tag}"
            rng = np.random.default_rng(SAMPLE_SEED)             # mismas mitades que RR-2
            half = np.zeros(len(cl), dtype=bool)
            for k in sorted(set(cl)):
                ix = np.flatnonzero(cl == k)
                half[rng.permutation(ix)[: len(ix) // 2]] = True
            halves = (np.mean([p[half].mean(0) for p in per_window], axis=0),
                      np.mean([p[~half].mean(0) for p in per_window], axis=0))
            others = {m: np.mean([z[f"{m}_s{s}"].mean(0) for s in SEEDS], axis=0) for m in LEARNED}
            for meas in X14.MEASURES:
                ws_l = [X14._measure(meas, seedmaps[i], seedmaps[j]) for i, j in combinations(range(len(SEEDS)), 2)]
                conc_rows += [{"cuenca": b, "h": h, "medida": meas, "tipo": "entre_semillas", "modelo_a": "lstm",
                               "modelo_b": "lstm", "valor": v} for v in ws_l]
                conc_rows.append({"cuenca": b, "h": h, "medida": meas, "tipo": "entre_mitades", "modelo_a": "lstm",
                                  "modelo_b": "lstm", "valor": X14._measure(meas, *halves)})
                ref = rr2[(rr2["cuenca"] == b) & (rr2["h"] == h) & (rr2["medida"] == meas)]
                ws_o = ref[ref["tipo"] == "entre_semillas"].groupby("modelo_a")["valor"].median()
                for m in LEARNED:
                    v = X14._measure(meas, others[m], full)
                    conc_rows.append({"cuenca": b, "h": h, "medida": meas, "tipo": "entre_modelos", "modelo_a": m,
                                      "modelo_b": "lstm", "valor": v,
                                      "bajo_techo_semillas": bool(v < min(float(np.median(ws_l)), float(ws_o[m])))})
            log.info("%s h=%d: IG del LSTM listo", b, h)
    pd.DataFrame(imp_rows).to_csv(MESE / "lstm_importance.csv", index=False)
    dl = pd.DataFrame(delta_rows)
    dl.to_csv(MESE / "lstm_ig_delta.csv", index=False)
    conc = pd.DataFrame(conc_rows)
    conc.to_csv(MESE / "lstm_concordance.csv", index=False)
    s180 = conc[conc["medida"] == "spearman_180"]
    bm = s180[s180["tipo"] == "entre_modelos"]
    res = {"ig_error_completitud": {"delta_abs_mediana_max": _r(dl["delta_abs_mediana"].max(), 6),
                                    "delta_abs_p95_max": _r(dl["delta_abs_p95"].max(), 6)},
           "spearman_180_lstm_vs": {m: _r(bm[bm["modelo_a"] == m]["valor"].median(), 3) for m in LEARNED},
           "spearman_180_lstm_entre_semillas_mediana": _r(s180[s180["tipo"] == "entre_semillas"]["valor"].median(), 3),
           "spearman_180_lstm_entre_mitades_mediana": _r(s180[s180["tipo"] == "entre_mitades"]["valor"].median(), 3),
           "pares_con_lstm_bajo_techo": {meas: f"{int(x['bajo_techo_semillas'].sum())} de {len(x)}"
                                         for meas, x in conc[conc["tipo"] == "entre_modelos"].groupby("medida")},
           "nota": "Pares adicionales; la mediana de 6 pares de H2-a no cambia."}
    return res


# ----------------------------------------------------------------------------- 7. walk-forward
def walk_forward(chosen: dict, files: dict) -> dict:
    wp = files["wf"][0]
    wst = pd.read_csv(OUT / "wf_station_metrics.csv", dtype={"clave": str})
    rows = []
    for y in YEARS:
        for b in D.BASINS:
            for h in D.HORIZONS:
                tag = f"{SLUG[b]}_h{h}_y{y}"
                meta = pd.read_parquet(INTERIM / "walk_forward" / "meta" / f"{tag}_test.parquet")
                pers = np.load(INTERIM / "walk_forward" / "preds" / f"baselines_{tag}.npz")["persistence_test"]
                sim = np.load(wp[f"lstm-{chosen[h]}_{tag}"])["flow_test"]
                gq = meta.groupby("clave")["y_flow"]
                ok = (gq.size() >= MIN_N) & (gq.var() > 0)
                ev = set(ok[ok].index)
                ref = set(wst[(wst["año"] == y) & (wst["cuenca"] == b) & (wst["h"] == h)
                              & (wst["modelo"] == "persistencia")]["clave"])
                assert ev == ref, f"estaciones evaluables distintas de xai_10 en {tag}"
                obs = meta["y_flow"].to_numpy()
                for k, idx in meta.groupby("clave").indices.items():
                    if k in ev:
                        o, s = obs[idx], sim[idx]
                        rows.append({"año": y, "cuenca": b, "h": h, "clave": k, "modelo": "lstm", "n": len(idx),
                                     "nse": M.nse(o, s), "kge": M.kge(o, s), "rmse": M.rmse(o, s),
                                     "ss": M.skill_mse(o, s, pers[idx])})
    lw = pd.DataFrame(rows)
    xg = wst[wst["modelo"] == "xgboost"].set_index(["año", "h", "clave"])["nse"]
    summ = []
    for g, sub in [(b, lw[lw["cuenca"] == b]) for b in D.BASINS] + [("agregado", lw)]:
        for (y, h), x in sub.groupby(["año", "h"]):
            r = {"grupo": g, "año": y, "h": h, "modelo": "lstm", "estaciones": int(x["clave"].nunique()),
                 "nse_mediana": round(x["nse"].median(), 4), "kge_mediana": round(x["kge"].median(), 4),
                 "ss_mediana": round(x["ss"].median(), 4)}
            if g == "agregado" or r["estaciones"] >= MIN_STATIONS:
                _, lo, hi = M.bootstrap_median_ci(x["ss"])
                d = (x.set_index("clave")["nse"] - xg.loc[(y, h)].reindex(x["clave"]).to_numpy()).dropna()
                dm, dlo, dhi = M.bootstrap_median_ci(d)
                r.update({"ss_ic_lo": round(lo, 4), "ss_ic_hi": round(hi, 4), "delta_nse_xgb_mediana": round(dm, 4),
                          "delta_nse_xgb_ic_lo": round(dlo, 4), "delta_nse_xgb_ic_hi": round(dhi, 4)})
            summ.append(r)
    sm = pd.DataFrame(summ)
    sm.to_csv(MESE / "lstm_walkforward.csv", index=False)
    agg = sm[sm["grupo"] == "agregado"]
    return {f"{int(r.año)}_h{int(r.h)}": {"nse_mediana": r.nse_mediana,
                                         "delta_nse_xgboost": [r.delta_nse_xgb_mediana, r.delta_nse_xgb_ic_lo,
                                                               r.delta_nse_xgb_ic_hi]}
            for r in agg.itertuples()}


def main() -> None:
    global MESE
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=INTERIM / "mese" / "lstm_lns" / "runs")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--out", type=Path, default=MESE, help="Solo pruebas: otra carpeta de salida.")
    ap.add_argument("--sin-numbers", action="store_true", help="Solo pruebas: no escribe numbers.json.")
    a = ap.parse_args()
    t0 = time.perf_counter()
    MESE = a.out
    MESE.mkdir(parents=True, exist_ok=True)
    X15, X14 = _load_script("xai_15_lstm_walk_forward"), _load_script("xai_14_review_analyses")
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    groups = pd.read_csv(OUT / "rev_rr3_grupos.csv", dtype={"clave": str}).set_index("clave")["grupo"]
    big = json.loads((OUT / "e_rq2.json").read_text(encoding="utf-8"))["cuencas_con_inferencia"]

    imp_res, chosen, files = verify(a.runs, X15)
    log.info("verificación superada; selección %s", imp_res["seleccion"])
    res = {"fuente": "scripts/xai_18_mese_lstm.py", "tipo": TAG, "verificacion": imp_res}
    res["habilidad"], _ = skill(chosen, files, st, groups, X14)
    res["explicaciones"] = explain(chosen, files, big, a.threads, X14)
    res["walk_forward"] = walk_forward(chosen, files)
    res["computo_local"] = {"fecha": date.today().isoformat(), "segundos": round(time.perf_counter() - t0, 1),
                            "cpu": platform.processor() or "cpu"}
    (MESE / "e_mese_lstm.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    if a.sin_numbers:
        log.info("listo en %.0f s (sin numbers.json)", time.perf_counter() - t0)
        return
    nums = json.loads((OUT / "numbers.json").read_text(encoding="utf-8"))
    nums["mese_lstm"] = {**res, "tablas": [f"mese/{f}" for f in ("lstm_skill.csv", "lstm_vs_xgboost.csv",
                                                                  "lstm_concordance.csv", "lstm_walkforward.csv")]}
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("listo en %.0f s", time.perf_counter() - t0)


if __name__ == "__main__":
    main()

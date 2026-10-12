#!/usr/bin/env python
"""Benchmark XAI · paso 10: evaluación del walk-forward anual (protocolo §3; especificación de
ejecución del 2026-10-11 en proof_ledger.md). No cambia los veredictos de §7.

Antes de evaluar comprueba que las funciones de `hidroxai_mx.models.criteria` reproducen los
veredictos oficiales y que `hidroxai_mx.alert.evaluation`, con 12 miembros, reproduce el ΔCSI
de `e_rq3.json`. Después, por año de prueba (2021–2025):
1. métricas por estación evaluable en el año (≥ 180 muestras y varianza > 0): NSE, KGE, RMSE, SS;
2. H1 y H1-b con la regla congelada (bootstrap de estaciones, 10,000);
3. ranking de los 7 modelos por NSE mediana; W de Kendall entre años y τ media entre pares
   (descriptivo);
4. H2-a y H2-b: TreeSHAP e IG con el modelo del pliegue sobre ≤ 2,000 ventanas del año;
5. H3 con el ensamble de 4 miembros (descriptivo) y, como referencia, el mismo ensamble de
   4 miembros en la partición principal.
Robustez por hipótesis: veredicto anual contra el principal (estable / estable con
excepciones / inestable). Sin las redes de Kaggle corre lo que no las necesita.

Entradas: --wf (xai_09 en CPU) y --wf-nets (salida de Kaggle descomprimida).
Salidas: results/xai_benchmark/wf_station_metrics.csv, wf_summary.csv, wf_rankings.csv,
         wf_concordance.csv, wf_top_precip_lag.csv, wf_rq3_summary.csv, e_walkforward.json
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import date
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, rankdata

from hidroxai_mx.alert import evaluation as AE
from hidroxai_mx.alert import fuzzy as F
from hidroxai_mx.models import criteria as C
from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_10")
OUT = ROOT / "results" / "xai_benchmark"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
YEARS = (2021, 2022, 2023, 2024, 2025)
SEED, SEEDS_MAIN = 20261010, (20261010, 20261011, 20261012)
LEARNED, DEEP = ("xgboost", "tcn", "convnext", "patchtst"), ("tcn", "convnext", "patchtst")
ORDER = ("persistencia", "climatologia", "arima", *LEARNED)
MIN_STATIONS, MIN_SAMPLES, N_SAMPLE, IG_STEPS = 8, 180, 2000, 64


def _ci(v) -> list[float]:
    return [round(float(x), 4) for x in v]


def train_obs(panels: dict, part: tuple[str, str]) -> dict[str, np.ndarray]:
    out = {}
    for k, p in panels.items():
        m = (p.index >= part[0]) & (p.index <= part[1]) & (p["calidad"] == 0)
        v = p.loc[m, D.TARGET].to_numpy(dtype=float)
        out[k] = v[np.isfinite(v)]
    return out


def same_samples(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    return (len(a) == len(b) and (a["clave"].to_numpy() == b["clave"].to_numpy()).all()
            and (a["issue"].to_numpy("datetime64[D]") == b["issue"].to_numpy("datetime64[D]")).all())


def load_fold(wf: Path, wf_nets: Path, chosen: dict, tag: str, h: int):
    meta = pd.read_parquet(wf / "meta" / f"{tag}_test.parquet")
    nm = wf_nets / "meta" / f"{tag}_test.parquet"
    if nm.exists():
        assert same_samples(pd.read_parquet(nm), meta), f"muestras distintas en {tag}"
    base = np.load(wf / "preds" / f"baselines_{tag}.npz")
    pred = {"persistencia": base["persistence_test"], "climatologia": base["climatology_test"],
            "arima": base["arima_test"]}
    for m in LEARNED:
        f = (wf if m == "xgboost" else wf_nets) / "preds" / f"{chosen[f'{m}_h{h}']}_{tag}.npz"
        if f.exists():
            pred[m] = np.load(f)["flow_test"]
            assert len(pred[m]) == len(meta), f"longitud distinta en {f.name}"
    return meta, pred


def verify_nets(wf_nets: Path, chosen: dict) -> dict:
    """Corridas de redes esperadas, presentes, con pesos y sin NaN; horas de GPU del manifiesto de Kaggle."""
    expected = {f"{chosen[f'{m}_h{h}']}_{SLUG[b]}_h{h}_y{y}" for y in YEARS for b in D.BASINS
                for h in D.HORIZONS for m in DEEP}
    preds = {p.stem for p in (wf_nets / "preds").glob("*.npz")}
    weights = {p.stem for p in (wf_nets / "weights").glob("*.pt")}
    nan = sorted(r for r in expected & preds if np.isnan(np.load(wf_nets / "preds" / f"{r}.npz")["flow_test"]).any())
    man = pd.read_csv(wf_nets / "compute_manifest.csv") if (wf_nets / "compute_manifest.csv").exists() else pd.DataFrame()
    man = man[man["run"].isin(expected)] if len(man) else man
    return {"corridas_esperadas": len(expected), "predicciones": len(expected & preds), "pesos": len(expected & weights),
            "faltantes": sorted(expected - preds), "con_nan": nan,
            "dispositivo": sorted(man["dispositivo"].dropna().unique().tolist()) if len(man) else [],
            "gpu_h": round(float(man["segundos"].sum()) / 3600, 3) if len(man) else 0.0,
            "ok": not (expected - preds) and not nan and expected <= weights}


def evaluable_stations(meta: pd.DataFrame) -> set[str]:
    g = meta.groupby("clave")["y_flow"]
    ok = (g.size() >= MIN_SAMPLES) & (g.var() > 0)
    return set(ok[ok].index)


def h3_block(fis, members_by_tag: dict, metas: dict, evaluable: dict, obs_train: dict) -> tuple[dict, pd.DataFrame]:
    """ΔCSI agregado por evento y horizonte a partir de miembros por (cuenca, h)."""
    rows = []
    for (b, h), members in members_by_tag.items():
        lv = AE.ensemble_levels(fis, np.stack(members), metas[(b, h)], obs_train)
        rows += [{"cuenca": b, "h": h, **r} for r in AE.contingency(lv, metas[(b, h)], evaluable[h])]
    ct = pd.DataFrame(rows)
    deltas, summ = {}, []
    for (h, e), x in ct.groupby(["h", "evento"]):
        deltas[f"{e}_h{h}"] = AE.boot_delta_csi(x)
        row = {"h": h, "evento": e}
        for metodo, y in x.groupby("metodo"):
            row.update({f"{metodo}_{k}": v for k, v in AE.scores(y[["aciertos", "fallos", "falsas"]].sum()).items()})
        summ.append(row)
    return deltas, pd.DataFrame(summ)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wf", type=Path, default=INTERIM / "walk_forward")
    ap.add_argument("--wf-nets", type=Path, default=INTERIM / "walk_forward_nets")
    ap.add_argument("--cpu", type=Path, default=INTERIM / "cpu")
    ap.add_argument("--nets", type=Path, default=INTERIM / "nets")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--skip-xai", action="store_true", help="Omite H2 (para pruebas rápidas).")
    a = ap.parse_args()
    t0 = time.perf_counter()
    e1, e2, e3 = (json.loads((OUT / f"e_rq{i}.json").read_text(encoding="utf-8")) for i in (1, 2, 3))
    chosen = e1["configuracion_elegida"]

    # 0. las funciones de criterios reproducen los veredictos oficiales
    assert C.h1({k: tuple(v) for k, v in e1["H1"]["ic_mediana_ss"].items()}) == e1["H1"]["veredicto"]
    for h in D.HORIZONS:
        assert C.h1b([tuple(e1["H1b"]["ic_mediana_delta_nse"][f"{m}_h{h}"]) for m in DEEP]) == \
            e1["H1b"]["veredicto"][f"h{h}"]
    assert C.h2a(e2["H2a"]["spearman_mediano"].values()) == e2["H2a"]["veredicto"]
    assert C.h2b(e2["H2b"]["proporcion_1_3_dias"]) == e2["H2b"]["veredicto"]
    d3 = e3["H3"]["delta_csi_ic"]
    assert C.h3(tuple(d3["P90_h1"]), tuple(d3["P90_h7"])) == e3["H3"]["veredicto"]

    # manifiestos del walk-forward → manifiesto del benchmark
    for src in (a.wf, a.wf_nets):
        if (src / "compute_manifest.csv").exists():
            for row in pd.read_csv(src / "compute_manifest.csv").to_dict("records"):
                manifest.replace(OUT / "compute_manifest.csv", **{k: v for k, v in row.items() if pd.notna(v)})

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft
    fis = F.build_protocol_fis()

    # 0b. evaluación de alertas: 12 miembros reproducen e_rq3; 4 miembros = referencia
    st_main = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    ev_main = {h: set(st_main.loc[(st_main["h"] == h) & (st_main["modelo"] == "persistencia"), "clave"])
               for h in D.HORIZONS}
    obs_main = train_obs(panels, D.PARTITIONS["train"])
    metas_main, m12, m4 = {}, {}, {}
    for b in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            metas_main[(b, h)] = pd.read_parquet(a.cpu / "meta" / f"{tag}_test.parquet")
            files = {(m, s): (a.cpu if m == "xgboost" else a.nets) / "preds" / f"{chosen[f'{m}_h{h}']}_{tag}_s{s}.npz"
                     for m in LEARNED for s in SEEDS_MAIN}
            m12[(b, h)] = [np.load(f)["flow_test"] for f in files.values()]
            m4[(b, h)] = [np.load(files[(m, SEED)])["flow_test"] for m in LEARNED]
    d12, _ = h3_block(fis, m12, metas_main, ev_main, obs_main)
    assert {k: _ci(v) for k, v in d12.items()} == {k: _ci(v) for k, v in d3.items()}, "no reproduce e_rq3"
    d4_main, _ = h3_block(fis, m4, metas_main, ev_main, obs_main)
    log.info("criterios y alertas reproducen los resultados oficiales")

    # 1. métricas por año
    rows, metas, preds, evals = [], {}, {}, {}
    for y in YEARS:
        for b in D.BASINS:
            for h in D.HORIZONS:
                tag = f"{SLUG[b]}_h{h}_y{y}"
                meta, pred = load_fold(a.wf, a.wf_nets, chosen, tag, h)
                metas[(y, b, h)], preds[(y, b, h)] = meta, pred
                ev = evaluable_stations(meta)
                evals[(y, b, h)] = ev
                obs = meta["y_flow"].to_numpy()
                for k, idx in meta.groupby("clave").indices.items():
                    if k not in ev:
                        continue
                    for name in ORDER:
                        if name in pred:
                            o, s = obs[idx], pred[name][idx]
                            rows.append({"año": y, "cuenca": b, "h": h, "clave": k, "modelo": name, "n": len(idx),
                                         "nse": M.nse(o, s), "kge": M.kge(o, s), "rmse": M.rmse(o, s),
                                         "ss": M.skill_mse(o, s, pred["persistencia"][idx])})
    st = pd.DataFrame(rows)
    st.to_csv(OUT / "wf_station_metrics.csv", index=False)
    have_nets = all(m in preds[k] for k in preds for m in DEEP)
    nets_check = verify_nets(a.wf_nets, chosen) if a.wf_nets.exists() else None
    if have_nets:
        assert nets_check and nets_check["ok"], f"redes del walk-forward incompletas: {nets_check}"
    summ = []
    for g, sub in [(b, st[st["cuenca"] == b]) for b in D.BASINS] + [("agregado", st)]:
        for (y, h, m), x in sub.groupby(["año", "h", "modelo"]):
            r = {"grupo": g, "año": y, "h": h, "modelo": m, "estaciones": int(x["clave"].nunique()),
                 "nse_mediana": round(x["nse"].median(), 4), "kge_mediana": round(x["kge"].median(), 4),
                 "ss_mediana": round(x["ss"].median(), 4)}
            if m != "persistencia" and (g == "agregado" or r["estaciones"] >= MIN_STATIONS):
                _, lo, hi = M.bootstrap_median_ci(x["ss"])
                r.update({"ss_ic_lo": round(lo, 4), "ss_ic_hi": round(hi, 4)})
            summ.append(r)
    sm = pd.DataFrame(summ)
    sm.to_csv(OUT / "wf_summary.csv", index=False)

    res = {"fecha": date.today().isoformat(),
           "fuente": "scripts/xai_10_walk_forward_eval.py; results/xai_benchmark/wf_*.csv",
           "especificacion": "proof_ledger.md, especificación de ejecución del walk-forward (2026-10-11)",
           "años": list(YEARS), "semilla": SEED,
           "consistencia": {"criterios_reproducen_veredictos_oficiales": True,
                            "alertas_12_miembros_reproducen_e_rq3": True},
           "estaciones_evaluables": {str(y): {f"h{h}": int(st[(st["año"] == y) & (st["h"] == h)]["clave"].nunique())
                                              for h in D.HORIZONS} for y in YEARS},
           "redes_disponibles": have_nets, "verificacion_redes": nets_check}

    # 2. ranking (descriptivo)
    agg = sm[sm["grupo"] == "agregado"]
    rank_rows, rk = [], {}
    for h in D.HORIZONS:
        models = [m for m in ORDER if all(((agg["año"] == y) & (agg["h"] == h) & (agg["modelo"] == m)).any()
                                          for y in YEARS)]
        mat = np.array([[-agg[(agg["año"] == y) & (agg["h"] == h) & (agg["modelo"] == m)]["nse_mediana"].item()
                         for m in models] for y in YEARS])
        ranks = np.vstack([rankdata(r) for r in mat])                    # 1 = mejor NSE mediana
        for y, r in zip(YEARS, ranks, strict=True):
            rank_rows += [{"año": y, "h": h, "modelo": m, "rango": float(v)} for m, v in zip(models, r, strict=True)]
        n, k = len(models), len(YEARS)
        s = ((ranks.sum(0) - ranks.sum(0).mean()) ** 2).sum()
        rk[f"h{h}"] = {"modelos": models, "kendall_w": round(float(12 * s / (k ** 2 * (n ** 3 - n))), 3),
                       "tau_media_entre_años": round(float(np.mean([kendalltau(ranks[i], ranks[j])[0]
                                                                   for i, j in combinations(range(k), 2)])), 3),
                       "mejor_por_año": {str(y): models[int(np.argmin(r))] for y, r in zip(YEARS, ranks, strict=True)}}
    pd.DataFrame(rank_rows).to_csv(OUT / "wf_rankings.csv", index=False)
    res["ranking"] = {"tipo": "descriptivo (no preregistrado)", "criterio": "NSE mediana agregada", **rk}

    if not have_nets:
        res["pendiente"] = "faltan las redes del walk-forward (Kaggle): H1, H1-b, H2 y H3 no se evalúan"
        (OUT / "e_walkforward.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        log.warning(res["pendiente"])
        return

    # 3. H1 y H1-b por año
    h1y, h1by, h1_out, h1b_out = {}, {h: {} for h in D.HORIZONS}, {}, {}
    for y in YEARS:
        sy = st[st["año"] == y]
        ci = {f"{m}_h{h}": M.bootstrap_median_ci(sy[(sy["modelo"] == m) & (sy["h"] == h)]["ss"])
              for m in LEARNED for h in (7, 14)}
        h1y[y] = C.h1(ci)
        h1_out[str(y)] = {"ic_mediana_ss": {k: _ci(v) for k, v in ci.items()}, "veredicto": h1y[y]}
        h1b_out[str(y)] = {}
        for h in D.HORIZONS:
            x = sy[sy["h"] == h].pivot_table(index="clave", columns="modelo", values="nse")
            cis = {m: M.bootstrap_median_ci((x[m] - x["xgboost"]).dropna()) for m in DEEP}
            h1by[h][y] = C.h1b(list(cis.values()))
            h1b_out[str(y)][f"h{h}"] = {"ic_mediana_delta_nse": {m: _ci(v) for m, v in cis.items()},
                                        "veredicto": h1by[h][y]}
    res["H1"] = {"por_año": h1_out, "robustez": C.stability(h1y, e1["H1"]["veredicto"])}
    res["H1b"] = {"por_año": h1b_out,
                  "robustez": {f"h{h}": C.stability(h1by[h], e1["H1b"]["veredicto"][f"h{h}"]) for h in D.HORIZONS}}

    # 4. H2 por año
    if not a.skip_xai:
        import torch
        import xgboost as xgb

        from hidroxai_mx.models import nets
        from hidroxai_mx.models import xgb as XG
        from hidroxai_mx.xai import attributions as A
        torch.set_num_threads(a.threads)
        conc_rows, lag_rows, h2a_y, h2b_y, h2_out = [], [], {}, {}, {}
        for y in YEARS:
            parts = D.walk_forward_partitions(y)
            big = [b for b in D.BASINS if all(len(evals[(y, b, h)]) >= MIN_STATIONS for h in D.HORIZONS)]
            for b in big:
                bp = {k: panels[k] for k in claves if basin_of[k] == b}
                for h in D.HORIZONS:
                    tag = f"{SLUG[b]}_h{h}_y{y}"
                    g = D.group_arrays(bp, h, {"train": parts["train"], "test": parts["test"]})
                    meta = metas[(y, b, h)]
                    assert same_samples(g["test"]["meta"], meta)
                    X = g["test"]["X"][A.stratified_sample(meta, N_SAMPLE, SEED)]
                    del g
                    imps = {}
                    for m in LEARNED:
                        rid = f"{chosen[f'{m}_h{h}']}_{tag}"
                        if m == "xgboost":
                            booster = xgb.Booster()
                            booster.load_model(a.wf / "models" / f"{rid}.json")
                            imps[m] = A.importance(XG.tree_shap(booster, X))
                        else:
                            net = nets.build(m, int(chosen[f"{m}_h{h}"].split("-")[1]))
                            net.load_state_dict(torch.load(a.wf_nets / "weights" / f"{rid}.pt", weights_only=True))
                            imps[m] = A.importance(A.integrated_gradients(net, X, n_steps=IG_STEPS)[0])
                        lag_rows.append({"año": y, "cuenca": b, "h": h, "modelo": m,
                                         "rezago_precip_mas_importante": A.top_precip_lag(imps[m], h)})
                    conc_rows.append(A.concordance(imps).assign(año=y, cuenca=b, h=h))
                    log.info("%d %s h=%d: Spearman mediano %.2f", y, b, h, conc_rows[-1]["spearman"].median())
            conc_y = pd.concat([c for c in conc_rows if c["año"].iloc[0] == y])
            med = conc_y.groupby(["cuenca", "h"])["spearman"].median()
            lags_y = pd.DataFrame([r for r in lag_rows if r["año"] == y])
            prop = float(lags_y[lags_y["h"] == 1]["rezago_precip_mas_importante"].between(1, 3).mean())
            h2a_y[y], h2b_y[y] = C.h2a(med.values), C.h2b(prop)
            h2_out[str(y)] = {"cuencas": big, "spearman_mediano": {f"{b}_h{h}": round(v, 3) for (b, h), v in med.items()},
                              "fraccion_ge_0.5": round(float((med >= 0.5).mean()), 3),
                              "fraccion_lt_0.3": round(float((med < 0.3).mean()), 3), "veredicto_h2a": h2a_y[y],
                              "proporcion_1_3_dias_h1": round(prop, 3), "veredicto_h2b": h2b_y[y]}
        pd.concat(conc_rows).to_csv(OUT / "wf_concordance.csv", index=False)
        pd.DataFrame(lag_rows).to_csv(OUT / "wf_top_precip_lag.csv", index=False)
        res["H2a"] = {"por_año": h2_out, "robustez": C.stability(h2a_y, e2["H2a"]["veredicto"])}
        res["H2b"] = {"tipo": "descriptivo", "robustez": C.stability(h2b_y, e2["H2b"]["veredicto"])}

    # 5. H3 con 4 miembros (descriptivo)
    h3y, h3_out, summ3 = {}, {}, []
    for y in YEARS:
        obs_y = train_obs(panels, D.walk_forward_partitions(y)["train"])
        mem = {(b, h): [preds[(y, b, h)][m] for m in LEARNED] for b in D.BASINS for h in D.HORIZONS}
        ev_y = {h: set().union(*(evals[(y, b, h)] for b in D.BASINS)) for h in D.HORIZONS}
        deltas, s3 = h3_block(fis, mem, {(b, h): metas[(y, b, h)] for b in D.BASINS for h in D.HORIZONS}, ev_y, obs_y)
        h3y[y] = C.h3(deltas["P90_h1"], deltas["P90_h7"])
        h3_out[str(y)] = {"delta_csi_ic": {k: _ci(v) for k, v in deltas.items()}, "veredicto": h3y[y]}
        summ3.append(s3.assign(año=y))
    pd.concat(summ3).round(4).to_csv(OUT / "wf_rq3_summary.csv", index=False)
    res["H3"] = {"tipo": "descriptivo (no preregistrado): ensamble de 4 miembros (1 semilla), no de 12",
                 "por_año": h3_out,
                 "referencia_principal_4_miembros": {"delta_csi_ic": {k: _ci(v) for k, v in d4_main.items()},
                                                     "veredicto": C.h3(d4_main["P90_h1"], d4_main["P90_h7"])},
                 "robustez": C.stability(h3y, e3["H3"]["veredicto"])}
    (OUT / "e_walkforward.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    sec = round(time.perf_counter() - t0, 1)
    manifest.replace(OUT / "compute_manifest.csv", fecha=date.today().isoformat(), tipo="evaluacion",
                     run="xai_10_walk_forward_eval", modelo="walk_forward", dispositivo=platform.processor() or "cpu",
                     hilos=a.threads, segundos=sec, pared_s=sec)
    log.info("robustez: H1 %s | H3 %s", res["H1"]["robustez"]["robustez"], res["H3"]["robustez"]["robustez"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Benchmark XAI · paso 5: evaluación de la RQ1 (protocolo, secciones 4 y 7).

1. Selección de configuración por modelo y horizonte: la de mayor mediana de NSE de
   validación de la predicción promedio de las 3 semillas, sobre las 4 cuencas; en empate,
   la más pequeña.
2. Métricas por estación en prueba (estaciones evaluables, `sample_profile.csv`): NSE, KGE,
   RMSE y SS contra persistencia, para referencias, ARIMA y modelos aprendidos.
3. Mediana e IQR por cuenca, horizonte y agregado; bootstrap de estaciones (10,000).
4. Veredictos H1 y H1-b con los umbrales congelados.

Entradas: --cpu (xai_04) y --nets (salida de Kaggle de xai_03, descomprimida).
Salidas: results/xai_benchmark/rq1_station_metrics.csv, rq1_summary.csv, rq1_selection.csv,
         e_rq1.json
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import ROOT, get_logger

log = get_logger("xai_05")
OUT = ROOT / "results" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
SEEDS = (20261010, 20261011, 20261012)
LEARNED = {"xgboost": (4, 6), "tcn": (32, 64), "convnext": (32, 64), "patchtst": (32, 64)}
DEEP = ("tcn", "convnext", "patchtst")
MIN_STATIONS_INFERENCE = 8


def _load(cpu: Path, nets: Path, basin: str, h: int) -> dict:
    tag = f"{SLUG[basin]}_h{h}"
    meta = {p: pd.read_parquet(cpu / "meta" / f"{tag}_{p}.parquet") for p in ("val", "test")}
    for p in ("val", "test"):                      # las redes deben usar exactamente las mismas muestras
        nm = nets / "meta" / f"{tag}_{p}.parquet"
        if nm.exists():
            other = pd.read_parquet(nm)
            same = ((other["clave"].to_numpy() == meta[p]["clave"].to_numpy()).all()
                    and (other["issue"].to_numpy("datetime64[D]") == meta[p]["issue"].to_numpy("datetime64[D]")).all())
            assert len(other) == len(meta[p]) and same, f"meta distinta {tag} {p}"
    base = np.load(cpu / "preds" / f"baselines_{tag}.npz")
    pred = {p: {"persistencia": base[f"persistence_{p}"], "climatologia": base[f"climatology_{p}"],
                "arima": base[f"arima_{p}"]} for p in ("val", "test")}
    for model, sizes in LEARNED.items():
        src = cpu if model == "xgboost" else nets
        for size in sizes:
            files = [src / "preds" / f"{model}-{size}_{tag}_s{s}.npz" for s in SEEDS]
            if not all(f.exists() for f in files):
                continue
            arr = [np.load(f) for f in files]
            for p in ("val", "test"):
                stack = np.stack([x[f"flow_{p}"] for x in arr])
                pred[p][f"{model}-{size}"] = stack.mean(0)
                pred[p][f"{model}-{size}__seeds"] = stack
    return {"meta": meta, "pred": pred}


def _station_metric(meta: pd.DataFrame, obs, sim, fn) -> pd.Series:
    return pd.Series({k: fn(obs[i], sim[i]) for k, i in meta.groupby("clave").indices.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "cpu")
    ap.add_argument("--nets", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "nets")
    a = ap.parse_args()
    t0 = time.perf_counter()
    prof = pd.read_csv(OUT / "sample_profile.csv", dtype={"clave": str})
    test = prof[prof["particion"] == "test"]
    evaluable = {h: set(test.loc[(test["h"] == h) & (test["n"] >= 180) & (test["var_objetivo"] > 0), "clave"])
                 for h in D.HORIZONS}
    data = {(b, h): _load(a.cpu, a.nets, b, h) for b in D.BASINS for h in D.HORIZONS}

    # 1. selección de configuración (validación, 4 cuencas juntas)
    sel_rows, chosen = [], {}
    for model, sizes in LEARNED.items():
        for h in D.HORIZONS:
            scores = {}
            for size in sizes:
                key = f"{model}-{size}"
                vals = []
                for b in D.BASINS:
                    d = data[(b, h)]
                    if key not in d["pred"]["val"]:
                        break
                    vals.append(_station_metric(d["meta"]["val"], d["meta"]["val"]["y_flow"].to_numpy(),
                                                d["pred"]["val"][key], M.nse))
                else:
                    scores[size] = float(pd.concat(vals).median())
            if len(scores) == len(sizes):
                best = max(sorted(scores), key=lambda s: (scores[s], -s))
                chosen[(model, h)] = f"{model}-{best}"
            for size, s in scores.items():
                sel_rows.append({"modelo": model, "h": h, "config": size, "nse_val_mediana": round(s, 4),
                                 "elegida": chosen.get((model, h)) == f"{model}-{size}"})
    pd.DataFrame(sel_rows).to_csv(OUT / "rq1_selection.csv", index=False)

    # 2. métricas por estación en prueba
    rows = []
    for (b, h), d in data.items():
        meta = d["meta"]["test"]
        obs = meta["y_flow"].to_numpy()
        pers = d["pred"]["test"]["persistencia"]
        models = {"persistencia": pers, "climatologia": d["pred"]["test"]["climatologia"],
                  "arima": d["pred"]["test"]["arima"]}
        models.update({m: d["pred"]["test"][chosen[(m, h)]] for m in LEARNED if (m, h) in chosen})
        for k, idx in meta.groupby("clave").indices.items():
            if k not in evaluable[h]:
                continue
            o = obs[idx]
            for name, sim in models.items():
                s = sim[idx]
                r_, alpha, beta = M.kge_components(o, s)       # descriptivo (no preregistrado)
                rows.append({"cuenca": b, "h": h, "clave": k, "modelo": name, "n": len(idx),
                             "nse": M.nse(o, s), "kge": M.kge(o, s), "rmse": M.rmse(o, s),
                             "ss": M.skill_mse(o, s, pers[idx]),
                             "kge_r": r_, "kge_alpha": alpha, "kge_beta": beta})
                if name in LEARNED:
                    seeds = d["pred"]["test"][f"{chosen[(name, h)]}__seeds"][:, idx]
                    rows[-1]["nse_semillas_sd"] = float(np.std([M.nse(o, x) for x in seeds]))
    st = pd.DataFrame(rows)
    st.to_csv(OUT / "rq1_station_metrics.csv", index=False)

    # 3. resumen
    summ = []
    groups = [(b, st[st["cuenca"] == b]) for b in D.BASINS] + [("agregado", st)]
    for g, sub in groups:
        for (h, mname), x in sub.groupby(["h", "modelo"]):
            r = {"grupo": g, "h": h, "modelo": mname, "estaciones": int(x["clave"].nunique())}
            for met in ("nse", "kge", "rmse", "ss"):
                q = x[met].quantile([0.25, 0.5, 0.75])
                r.update({f"{met}_mediana": round(q[0.5], 4), f"{met}_q25": round(q[0.25], 4),
                          f"{met}_q75": round(q[0.75], 4)})
            if g == "agregado" or r["estaciones"] >= MIN_STATIONS_INFERENCE:
                med, lo, hi = M.bootstrap_median_ci(x["ss"])
                r.update({"ss_ic_lo": round(lo, 4), "ss_ic_hi": round(hi, 4)})
            summ.append(r)
    sm = pd.DataFrame(summ)
    sm.to_csv(OUT / "rq1_summary.csv", index=False)

    # 4. veredictos
    agg = st
    def ci_ss(m, h):
        return M.bootstrap_median_ci(agg[(agg["modelo"] == m) & (agg["h"] == h)]["ss"])
    h1 = {f"{m}_h{h}": ci_ss(m, h) for m in LEARNED for h in (7, 14) if (m, h) in chosen}
    n_pos = {h: sum(h1[f"{m}_h{h}"][1] > 0 for m in LEARNED if f"{m}_h{h}" in h1) for h in (7, 14)}
    any_pos = any(v[1] > 0 for v in h1.values())
    v1 = ("SUPPORTED" if all(n_pos[h] >= 3 for h in (7, 14)) else "REJECTED" if not any_pos else "OPEN")
    h1b = {}
    for h in D.HORIZONS:
        x = agg[agg["h"] == h].pivot_table(index="clave", columns="modelo", values="nse")
        for m in DEEP:
            if m in x and "xgboost" in x:
                h1b[f"{m}_h{h}"] = M.bootstrap_median_ci((x[m] - x["xgboost"]).dropna())
    v1b = {}
    for h in D.HORIZONS:
        cis = [h1b[f"{m}_h{h}"] for m in DEEP if f"{m}_h{h}" in h1b]
        v1b[f"h{h}"] = ("SUPPORTED" if any(c[1] > 0 for c in cis) else
                        "REJECTED" if cis and all(c[2] < 0 for c in cis) else "OPEN")
    res = {"fecha": date.today().isoformat(),
           "fuente": "scripts/xai_05_evaluate.py; results/xai_benchmark/rq1_station_metrics.csv",
           "configuracion_elegida": {f"{m}_h{h}": c for (m, h), c in chosen.items()},
           "estaciones_evaluables": {f"h{h}": int(n) for h, n in st.groupby("h")["clave"].nunique().items()},
           "H1": {"ic_mediana_ss": {k: [round(x, 4) for x in v] for k, v in h1.items()},
                  "modelos_con_ic_positivo": {f"h{h}": n for h, n in n_pos.items()}, "veredicto": v1},
           "H1b": {"ic_mediana_delta_nse": {k: [round(x, 4) for x in v] for k, v in h1b.items()},
                   "veredicto": v1b}}
    (OUT / "e_rq1.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    sec = round(time.perf_counter() - t0, 1)
    manifest.replace(OUT / "compute_manifest.csv", fecha=date.today().isoformat(), tipo="evaluacion",
                     run="xai_05_evaluate", modelo="evaluacion_rq1", dispositivo=platform.processor() or "cpu",
                     hilos=1, segundos=sec, pared_s=sec)
    log.info("H1 %s | H1-b %s", v1, v1b)


if __name__ == "__main__":
    main()

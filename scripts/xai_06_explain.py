#!/usr/bin/env python
"""Benchmark XAI · paso 6: explicabilidad y RQ2 (protocolo, secciones 5 y 7).

Para cada cuenca y horizonte, sobre la muestra fija de hasta 2,000 ventanas de prueba
(semilla 20261010) y con la configuración elegida en `e_rq1.json` (3 semillas):
TreeSHAP para XGBoost, Integrated Gradients para las redes y atención por parche para
PatchTST. Calcula la concordancia entre modelos y el rezago de precipitación más
importante respecto al objetivo, y emite los veredictos H2-a y H2-b.

Salidas: results/xai_benchmark/rq2_importance.csv (formato largo), rq2_concordance.csv,
         rq2_top_precip_lag.csv, rq2_ig_delta.csv, rq2_attention.csv, e_rq2.json
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import xgboost as xgb

from hidroxai_mx.models import data as D
from hidroxai_mx.models import nets
from hidroxai_mx.models import xgb as XG
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger
from hidroxai_mx.xai import attributions as A

log = get_logger("xai_06")
OUT = ROOT / "results" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
SEEDS = (20261010, 20261011, 20261012)
MODELS = ("xgboost", "tcn", "convnext", "patchtst")
SAMPLE_SEED, N_SAMPLE, IG_STEPS = 20261010, 2000, 64
MIN_STATIONS_INFERENCE = 8


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "cpu")
    ap.add_argument("--nets", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "nets")
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    chosen = json.loads((OUT / "e_rq1.json").read_text(encoding="utf-8"))["configuracion_elegida"]
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    n_eval = st[st["modelo"] == "persistencia"].groupby(["cuenca", "h"])["clave"].nunique()

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft

    imp_rows, conc_rows, lag_rows, delta_rows, att_rows = [], [], [], [], []
    for basin in D.BASINS:
        bp = {k: panels[k] for k in claves if basin_of[k] == basin}
        for h in D.HORIZONS:
            tag = f"{SLUG[basin]}_h{h}"
            g = D.group_arrays(bp, h)
            meta = pd.read_parquet(a.cpu / "meta" / f"{tag}_test.parquet")
            assert meta[["clave", "issue"]].equals(g["test"]["meta"][["clave", "issue"]])
            idx = A.stratified_sample(meta, N_SAMPLE, SAMPLE_SEED)
            X = g["test"]["X"][idx]
            imps = {}
            for model in MODELS:
                cfg = chosen[f"{model}_h{h}"]
                per_seed = []
                for seed in SEEDS:
                    rid = f"{cfg}_{tag}_s{seed}"
                    if model == "xgboost":
                        booster = xgb.Booster()
                        booster.load_model(a.cpu / "models" / f"{rid}.json")   # conserva best_iteration
                        per_seed.append(A.importance(XG.tree_shap(booster, X)))
                    else:
                        net = nets.build(model, int(cfg.split("-")[1]))
                        net.load_state_dict(torch.load(a.nets / "weights" / f"{rid}.pt", weights_only=True))
                        attr, delta = A.integrated_gradients(net, X, n_steps=IG_STEPS)
                        per_seed.append(A.importance(attr))
                        delta_rows.append({"cuenca": basin, "h": h, "modelo": model, "semilla": seed,
                                           "delta_abs_mediana": float(np.median(np.abs(delta))),
                                           "delta_abs_p95": float(np.quantile(np.abs(delta), 0.95))})
                        if model == "patchtst":
                            att = A.attention_by_patch(net, X)
                            att_rows += [{"cuenca": basin, "h": h, "semilla": seed, "parche": p,
                                          "dias_ventana": f"t-{29 - 5 * p}…t-{25 - 5 * p}",
                                          "atencion_recibida": float(v)} for p, v in enumerate(att)]
                imp = np.mean(per_seed, axis=0)
                imps[model] = imp
                for j in range(imp.shape[0]):
                    for c, ch in enumerate(D.CHANNELS):
                        imp_rows.append({"cuenca": basin, "h": h, "modelo": model, "canal": ch,
                                         "rezago_ventana": 29 - j, "rezago_objetivo": 29 - j + h,
                                         "importancia": float(imp[j, c])})
                lag_rows.append({"cuenca": basin, "h": h, "modelo": model,
                                 "rezago_precip_mas_importante": A.top_precip_lag(imp, h)})
            cc = A.concordance(imps).assign(cuenca=basin, h=h)
            conc_rows.append(cc)
            log.info("%s h=%d: Spearman mediano %.2f", basin, h, cc["spearman"].median())

    pd.DataFrame(imp_rows).to_csv(OUT / "rq2_importance.csv", index=False)
    conc = pd.concat(conc_rows, ignore_index=True)
    conc.to_csv(OUT / "rq2_concordance.csv", index=False)
    lags = pd.DataFrame(lag_rows)
    lags.to_csv(OUT / "rq2_top_precip_lag.csv", index=False)
    pd.DataFrame(delta_rows).to_csv(OUT / "rq2_ig_delta.csv", index=False)
    pd.DataFrame(att_rows).to_csv(OUT / "rq2_attention.csv", index=False)

    big = [b for b in D.BASINS if all(n_eval.get((b, h), 0) >= MIN_STATIONS_INFERENCE for h in D.HORIZONS)]
    med = conc[conc["cuenca"].isin(big)].groupby(["cuenca", "h"])["spearman"].median()
    frac_hi, frac_lo = float((med >= 0.5).mean()), float((med < 0.3).mean())
    v2a = "SUPPORTED" if frac_hi >= 2 / 3 else ("REJECTED" if frac_lo > 0.5 else "OPEN")
    l1 = lags[(lags["h"] == 1) & lags["cuenca"].isin(big)]
    prop = float(l1["rezago_precip_mas_importante"].between(1, 3).mean())
    v2b = "SUPPORTED" if prop >= 0.75 else ("REJECTED" if prop < 0.5 else "OPEN")
    res = {"fecha": date.today().isoformat(),
           "fuente": "scripts/xai_06_explain.py; results/xai_benchmark/rq2_*.csv",
           "muestra": {"max_ventanas": N_SAMPLE, "semilla": SAMPLE_SEED, "ig_pasos": IG_STEPS,
                       "linea_base_ig": "cero en el espacio estandarizado"},
           "cuencas_con_inferencia": big,
           "H2a": {"spearman_mediano": {f"{b}_h{h}": round(v, 3) for (b, h), v in med.items()},
                   "fraccion_ge_0.5": round(frac_hi, 3), "fraccion_lt_0.3": round(frac_lo, 3), "veredicto": v2a},
           "H2b": {"pares": l1[["cuenca", "modelo", "rezago_precip_mas_importante"]].to_dict("records"),
                   "proporcion_1_3_dias": round(prop, 3), "veredicto": v2b}}
    (OUT / "e_rq2.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("H2-a %s | H2-b %s", v2a, v2b)


if __name__ == "__main__":
    main()

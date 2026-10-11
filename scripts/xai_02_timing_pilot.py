#!/usr/bin/env python
"""Benchmark XAI · paso 2: piloto de tiempos (protocolo, sección 8). No toca la prueba.

En la cuenca más grande (Lerma–Santiago, h = 1) mide:
- segundos por época de cada red y tamaño de malla (3 épocas, entrenamiento + validación);
- un ajuste completo de XGBoost por profundidad (early stopping en validación);
- la selección de orden ARIMA de una estación.

Con esos tiempos estima las horas de CPU del diseño principal, escalando por número de
muestras de entrenamiento de cada cuenca. Supuestos explícitos: 40 épocas por red
(escenario central) y 100 (cota superior del protocolo).

Salidas: results/xai_benchmark/timing_pilot.json y filas "piloto" en compute_manifest.csv
Uso:  python scripts/xai_02_timing_pilot.py
"""
from __future__ import annotations

import json
import os
import platform
import time
from datetime import date

import pandas as pd
import torch

from hidroxai_mx.models import arima, nets, train
from hidroxai_mx.models import data as D
from hidroxai_mx.models import xgb as XG
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_02")
OUT = ROOT / "results" / "xai_benchmark"
SEED, PILOT_EPOCHS = 20261010, 3
SIZES = {"tcn": (32, 64), "convnext": (32, 64), "patchtst": (32, 64)}
DEPTHS = (4, 6)


def manifest_row(**kw) -> dict:
    return {"fecha": date.today().isoformat(), "tipo": "piloto", "dispositivo": "cpu",
            "hilos": torch.get_num_threads(), **kw}


def main() -> None:
    torch.set_num_threads(min(16, os.cpu_count() or 1))
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin = D.station_basins(link)
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]])
    panels = {k: D.daily_panel(ft, k) for k in link["clave"] if pd.notna(basin.get(k))}
    by_basin = {b: {k: p for k, p in panels.items() if basin[k] == b} for b in D.BASINS}
    n_train = {b: {h: len(D.group_arrays(ps, h)["train"]["y"]) for h in D.HORIZONS}
               for b, ps in by_basin.items()}
    g = D.group_arrays(by_basin["Lerma–Santiago"], 1)
    tr, va = g["train"], g["val"]
    ref_n = len(tr["y"])
    rows, res = [], {"deep_s_per_epoch": {}, "xgb_s": {}, "fuente": "scripts/xai_02_timing_pilot.py",
                     "cpu": platform.processor(), "hilos": torch.get_num_threads(),
                     "grupo_piloto": "Lerma–Santiago, h = 1", "muestras_entrenamiento_piloto": ref_n,
                     "muestras_entrenamiento": n_train}

    for name, sizes in SIZES.items():
        for size in sizes:
            model = nets.build(name, size)
            r = train.fit(model, tr["X"], tr["y"], va["X"], va["y"], seed=SEED,
                          max_epochs=PILOT_EPOCHS, patience=PILOT_EPOCHS + 1)
            spe = r["seconds"] / r["epochs"]
            res["deep_s_per_epoch"][f"{name}-{size}"] = round(spe, 2)
            rows.append(manifest_row(modelo=name, config=size, cuenca="Lerma–Santiago", h=1, semilla=SEED,
                                     epocas=r["epochs"], segundos=round(r["seconds"], 1),
                                     parametros=sum(p.numel() for p in model.parameters())))
            log.info("%s-%d: %.1f s/época", name, size, spe)

    for depth in DEPTHS:
        t0 = time.perf_counter()
        booster = XG.fit(tr["X"], tr["y"], va["X"], va["y"], max_depth=depth, seed=SEED, n_jobs=16)
        sec = time.perf_counter() - t0
        res["xgb_s"][f"depth{depth}"] = {"segundos": round(sec, 1), "arboles": booster.best_iteration + 1}
        rows.append(manifest_row(modelo="xgboost", config=depth, cuenca="Lerma–Santiago", h=1, semilla=SEED,
                                 epocas=booster.best_iteration + 1, segundos=round(sec, 1), parametros=None))
        log.info("xgboost depth %d: %.1f s", depth, sec)

    clave = max(by_basin["Lerma–Santiago"], key=lambda k: len(by_basin["Lerma–Santiago"][k]))
    t0 = time.perf_counter()
    order, _ = arima.station_forecasts(by_basin["Lerma–Santiago"][clave], D.PARTITIONS["train"],
                                       D.HORIZONS, D.TARGET)
    res["arima_s_estacion"] = round(time.perf_counter() - t0, 1)
    res["arima_orden_piloto"] = {"clave": clave, "orden": list(order)}
    rows.append(manifest_row(modelo="arima", config=str(order), cuenca="Lerma–Santiago", h="1,7,14",
                             semilla=None, epocas=None, segundos=res["arima_s_estacion"], parametros=None))

    # ---- estimación del diseño principal (horas de CPU) ----
    scale = {b: {h: n_train[b][h] / ref_n for h in D.HORIZONS} for b in D.BASINS}
    seeds, n_st = 3, sum(len(v) for v in by_basin.values())
    deep_epoch_units = sum(scale[b][h] for b in D.BASINS for h in D.HORIZONS) * seeds
    spe_sum = sum(res["deep_s_per_epoch"].values())
    xgb_units = sum(scale[b][h] for b in D.BASINS for h in D.HORIZONS) * seeds
    xgb_sum = sum(v["segundos"] for v in res["xgb_s"].values())
    est = {}
    for label, epochs in (("central_40_epocas", 40), ("cota_100_epocas", 100)):
        deep_h = spe_sum * epochs * deep_epoch_units / 3600
        est[label] = {"redes_h": round(deep_h, 1), "xgboost_h": round(xgb_sum * xgb_units / 3600, 2),
                      "arima_h": round(res["arima_s_estacion"] * n_st / 3600, 2)}
        est[label]["total_h"] = round(sum(est[label].values()), 1)
    res["estimacion_diseno_principal"] = est
    res["presupuesto_h"] = 40
    (OUT / "timing_pilot.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    man = OUT / "compute_manifest.csv"
    pd.DataFrame(rows).to_csv(man, mode="a", header=not man.exists(), index=False)
    log.info("estimación: %s", est)


if __name__ == "__main__":
    main()

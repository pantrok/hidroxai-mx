#!/usr/bin/env python
"""Benchmark XAI · paso 4: modelos en CPU (protocolo, sección 4).

- XGBoost global por cuenca y horizonte: max_depth ∈ {4, 6} × 3 semillas.
- ARIMA por estación (orden por AIC en entrenamiento; pronóstico desde el estado filtrado).
- Referencias: persistencia y climatología (31 días, periodo de entrenamiento).

Las predicciones se guardan con el mismo formato y orden de muestras que las redes
(`xai_03`): preds/<run>.npz con z_<particion> (estandarizado, si aplica) y flow_<particion>
(m³/s), y meta/<cuenca>_h<h>_<particion>.parquet. Reanudable: salta lo ya guardado.

Uso:  python scripts/xai_04_train_cpu_models.py [--out data/interim/xai_benchmark/cpu] [--workers 6]
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import arima, baselines, manifest
from hidroxai_mx.models import data as D
from hidroxai_mx.models import xgb as XG
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_04")
SEEDS = (20261010, 20261011, 20261012)
DEPTHS = (4, 6)
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
MANIFEST = ROOT / "results" / "xai_benchmark" / "compute_manifest.csv"
CPU = platform.processor() or "cpu"


def _manifest(**kw) -> None:
    manifest.append(MANIFEST, fecha=date.today().isoformat(), tipo="principal", dispositivo=CPU, **kw)


def _to_flow(g: dict, part: str, z: np.ndarray) -> np.ndarray:
    flow = np.empty(len(z))
    for clave, idx in g[part]["meta"].groupby("clave").indices.items():
        flow[idx] = g["scalers"][clave].target_to_flow(z[idx])
    return flow


def _arima_station(args):
    clave, panel = args
    t0 = time.perf_counter()
    try:
        order, fc = arima.station_forecasts(panel, D.PARTITIONS["train"], D.HORIZONS, D.TARGET)
    except RuntimeError as exc:
        return clave, None, None, time.perf_counter() - t0, str(exc)
    return clave, order, fc, time.perf_counter() - t0, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "cpu")
    ap.add_argument("--workers", type=int, default=6, help="Procesos para ARIMA.")
    ap.add_argument("--xgb-threads", type=int, default=16)
    a = ap.parse_args()
    for sub in ("meta", "preds", "models"):
        (a.out / sub).mkdir(parents=True, exist_ok=True)

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft

    # ---- ARIMA por estación (una sola vez; sirve para los tres horizontes) ----
    arima_file = a.out / "models" / "arima_forecasts.parquet"
    if not arima_file.exists():
        t0 = time.perf_counter()
        with mp.get_context("spawn").Pool(a.workers) as pool:
            res = pool.map(_arima_station, [(k, panels[k]) for k in claves])
        frames, orders = [], []
        for clave, order, fc, sec, err in res:
            orders.append({"clave": clave, "orden": None if order is None else list(order),
                           "segundos": round(sec, 1), "error": err})
            if fc is not None:
                frames.append(pd.DataFrame({"clave": clave, "issue": fc[1].index,
                                            **{f"h{h}": fc[h].to_numpy() for h in D.HORIZONS}}))
        pd.concat(frames, ignore_index=True).to_parquet(arima_file, index=False)
        pd.DataFrame(orders).to_csv(a.out / "models" / "arima_orders.csv", index=False)
        _manifest(run="arima_todas", modelo="arima", config="AIC p,q<=3 d<=1", cuenca="todas", h="1,7,14",
                  semilla=None, hilos=a.workers, epocas=None,
                  segundos=round(sum(o["segundos"] for o in orders), 1),
                  pared_s=round(time.perf_counter() - t0, 1))
        log.info("ARIMA: %d estaciones, %d sin orden", len(orders), sum(o["error"] is not None for o in orders))
    afc = pd.read_parquet(arima_file).set_index(["clave", "issue"])

    for basin in D.BASINS:
        bp = {k: panels[k] for k in claves if basin_of[k] == basin}
        for h in D.HORIZONS:
            g = D.group_arrays(bp, h)
            for part in ("val", "test"):
                mp_ = a.out / "meta" / f"{SLUG[basin]}_h{h}_{part}.parquet"
                if not mp_.exists():
                    g[part]["meta"].to_parquet(mp_, index=False)
            tag = f"{SLUG[basin]}_h{h}"
            # referencias y ARIMA alineados a las muestras
            ref = a.out / "preds" / f"baselines_{tag}.npz"
            if not ref.exists():
                out = {}
                for part in ("val", "test"):
                    meta = g[part]["meta"]
                    out[f"persistence_{part}"] = baselines.persistence(meta["q_issue"]).astype(np.float32)
                    clim = np.empty(len(meta))
                    for clave, idx in meta.groupby("clave").indices.items():
                        c = baselines.Climatology().fit(bp[clave], D.PARTITIONS["train"])
                        clim[idx] = c.predict(meta["target_date"].iloc[idx])
                    out[f"climatology_{part}"] = clim.astype(np.float32)
                    key = pd.MultiIndex.from_arrays([meta["clave"], meta["issue"]])
                    out[f"arima_{part}"] = afc[f"h{h}"].reindex(key).to_numpy(dtype=np.float32)
                np.savez_compressed(ref, **out)
            # XGBoost
            for seed in SEEDS:
                for depth in DEPTHS:
                    rid = f"xgboost-{depth}_{tag}_s{seed}"
                    if (a.out / "preds" / f"{rid}.npz").exists():
                        continue
                    t0 = time.perf_counter()
                    booster = XG.fit(g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"],
                                     max_depth=depth, seed=seed, n_jobs=a.xgb_threads)
                    sec = time.perf_counter() - t0
                    out = {}
                    for part in ("val", "test"):
                        z = XG.predict(booster, g[part]["X"]).astype(np.float32)
                        out[f"z_{part}"], out[f"flow_{part}"] = z, _to_flow(g, part, z).astype(np.float32)
                    np.savez_compressed(a.out / "preds" / f"{rid}.npz", **out)
                    booster.save_model(a.out / "models" / f"{rid}.json")
                    _manifest(run=rid, modelo="xgboost", config=depth, cuenca=basin, h=h, semilla=seed,
                              hilos=a.xgb_threads, epocas=booster.best_iteration + 1, segundos=round(sec, 1),
                              pared_s=round(sec, 1),
                              mejor_val_mse=round(float(np.mean((out["z_val"] - g["val"]["y"]) ** 2)), 6))
                    log.info("%s: %d árboles, %.0f s", rid, booster.best_iteration + 1, sec)


if __name__ == "__main__":
    main()

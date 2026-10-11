#!/usr/bin/env python
"""Benchmark XAI · paso 9: walk-forward anual (protocolo §3; especificación en proof_ledger.md).

Para cada año de prueba Y = 2021…2025 (entrenamiento 2010 – Y−2, validación Y−1, prueba Y):
- referencias: persistencia y climatología del entrenamiento del pliegue;
- ARIMA con el orden de la partición principal (`arima_orders.csv`) y coeficientes reestimados;
- XGBoost y redes con la configuración de `e_rq1.json` y una semilla (20261010).

Referencias, ARIMA y XGBoost corren en CPU local; las redes, en GPU de Kaggle
(`notebooks/kaggle_xai_walk_forward.ipynb`). Es reanudable: salta lo ya guardado y retoma
las redes desde su checkpoint por época.

Salidas en --out (data/interim/xai_benchmark/walk_forward):
  meta/<cuenca>_h<h>_y<Y>_test.parquet     muestras de prueba del pliegue
  preds/baselines_<cuenca>_h<h>_y<Y>.npz    persistencia, climatología y ARIMA (m³/s)
  preds/<config>_<cuenca>_h<h>_y<Y>.npz     XGBoost y redes: z_test y flow_test
  weights/<run>.pt, models/<run>.json       pesos de redes y modelos XGBoost (explicabilidad)
  models/arima_y<Y>.parquet                 pronósticos ARIMA por estación y emisión
  compute_manifest.csv                      una fila por corrida (tipo walk_forward)

Uso:
  python scripts/xai_09_walk_forward.py --models baselines xgboost             # CPU local
  python scripts/xai_09_walk_forward.py --models tcn convnext patchtst --device cuda   # Kaggle
"""
from __future__ import annotations

import argparse
import ast
import json
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

log = get_logger("xai_09")
YEARS = (2021, 2022, 2023, 2024, 2025)
SEED = 20261010
NETS = ("tcn", "convnext", "patchtst")
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
CHOSEN = ROOT / "results" / "xai_benchmark" / "e_rq1.json"
ARIMA_ORDERS = ROOT / "data" / "interim" / "xai_benchmark" / "cpu" / "models" / "arima_orders.csv"


def _to_flow(g: dict, z: np.ndarray) -> np.ndarray:
    flow = np.empty(len(z))
    for clave, idx in g["test"]["meta"].groupby("clave").indices.items():
        flow[idx] = g["scalers"][clave].target_to_flow(z[idx])
    return flow


def _arima_station(args):
    clave, panel, order, train = args
    t0 = time.perf_counter()
    try:
        _, fc = arima.station_forecasts(panel, train, D.HORIZONS, D.TARGET, order=order)
    except RuntimeError as exc:
        return clave, None, time.perf_counter() - t0, str(exc)
    return clave, fc, time.perf_counter() - t0, None


def _device(name: str):
    import torch
    dev = torch.device("cuda" if name == "auto" and torch.cuda.is_available() else
                       ("cpu" if name == "auto" else name))
    label = torch.cuda.get_device_name(dev) if dev.type == "cuda" else (platform.processor() or "cpu")
    return dev, label


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "walk_forward")
    ap.add_argument("--models", nargs="*", default=["baselines", "xgboost"],
                    help="baselines (persistencia, climatología, ARIMA), xgboost, tcn, convnext, patchtst")
    ap.add_argument("--years", nargs="*", type=int, default=list(YEARS))
    ap.add_argument("--basins", nargs="*", default=list(D.BASINS))
    ap.add_argument("--max-epochs", type=int, default=100, help="Solo para pruebas rápidas; el protocolo usa 100.")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=6, help="Procesos para ARIMA.")
    ap.add_argument("--xgb-threads", type=int, default=16)
    ap.add_argument("--stop-after-hours", type=float, default=0.0)
    a = ap.parse_args()
    t_start = time.perf_counter()
    for sub in ("meta", "preds", "weights", "models", "ckpt"):
        (a.out / sub).mkdir(parents=True, exist_ok=True)
    chosen = json.loads(CHOSEN.read_text(encoding="utf-8"))["configuracion_elegida"]
    man = a.out / "compute_manifest.csv"
    nets_wanted = [m for m in a.models if m in NETS]
    if nets_wanted:
        import torch

        from hidroxai_mx.models import nets, train
        dev, dev_label = _device(a.device)
    cpu_label = platform.processor() or "cpu"

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft

    for year in a.years:
        parts = D.walk_forward_partitions(year)
        # ARIMA: un ajuste por estación y año, sirve para los tres horizontes
        afc = None
        if "baselines" in a.models:
            afile = a.out / "models" / f"arima_y{year}.parquet"
            if not afile.exists():
                orders = pd.read_csv(ARIMA_ORDERS, dtype={"clave": str}).dropna(subset=["orden"])
                orders = {r.clave: ast.literal_eval(r.orden) for r in orders.itertuples()}
                t0 = time.perf_counter()
                with mp.get_context("spawn").Pool(a.workers) as pool:
                    res = pool.map(_arima_station, [(k, panels[k], orders[k], parts["train"])
                                                    for k in claves if k in orders])
                frames = [pd.DataFrame({"clave": k, "issue": fc[1].index, **{f"h{h}": fc[h].to_numpy()
                                                                           for h in D.HORIZONS}})
                          for k, fc, _, err in res if fc is not None]
                pd.concat(frames, ignore_index=True).to_parquet(afile, index=False)
                fails = [k for k, fc, _, _ in res if fc is None]
                manifest.append(man, fecha=date.today().isoformat(), tipo="walk_forward", run=f"arima_y{year}",
                                modelo="arima", config="orden principal", cuenca="todas", h="1,7,14",
                                dispositivo=cpu_label, hilos=a.workers, epocas=None,
                                segundos=round(sum(r[2] for r in res), 1),
                                pared_s=round(time.perf_counter() - t0, 1),
                                parada_temprana=None, parametros=None)
                log.info("ARIMA %d: %d estaciones, sin convergencia: %s", year, len(res), fails or "ninguna")
            afc = pd.read_parquet(afile).set_index(["clave", "issue"])

        for basin in a.basins:
            bp = {k: panels[k] for k in claves if basin_of[k] == basin}
            for h in D.HORIZONS:
                tag = f"{SLUG[basin]}_h{h}_y{year}"
                runs = []
                if "baselines" in a.models and not (a.out / "preds" / f"baselines_{tag}.npz").exists():
                    runs.append("baselines")
                runs += [m for m in a.models if (m == "xgboost" or m in NETS)
                         and not (a.out / "preds" / f"{chosen[f'{m}_h{h}']}_{tag}.npz").exists()]
                if not runs:
                    continue
                if a.stop_after_hours and (time.perf_counter() - t_start) / 3600 > a.stop_after_hours:
                    log.info("Límite de %.1f h alcanzado; se retoma en otra sesión.", a.stop_after_hours)
                    return
                g = D.group_arrays(bp, h, parts)
                meta = g["test"]["meta"]
                mpath = a.out / "meta" / f"{tag}_test.parquet"
                if not mpath.exists():
                    meta.to_parquet(mpath, index=False)
                for m in runs:
                    if m == "baselines":
                        clim = np.empty(len(meta))
                        for clave, idx in meta.groupby("clave").indices.items():
                            c = baselines.Climatology().fit(bp[clave], parts["train"])
                            clim[idx] = c.predict(meta["target_date"].iloc[idx])
                        key = pd.MultiIndex.from_arrays([meta["clave"], meta["issue"]])
                        np.savez_compressed(a.out / "preds" / f"baselines_{tag}.npz",
                                            persistence_test=baselines.persistence(meta["q_issue"]).astype(np.float32),
                                            climatology_test=clim.astype(np.float32),
                                            arima_test=afc[f"h{h}"].reindex(key).to_numpy(dtype=np.float32))
                        continue
                    cfg = chosen[f"{m}_h{h}"]
                    rid = f"{cfg}_{tag}"
                    size = int(cfg.split("-")[1])
                    t0 = time.perf_counter()
                    if m == "xgboost":
                        booster = XG.fit(g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"],
                                         max_depth=size, seed=SEED, n_jobs=a.xgb_threads)
                        z = XG.predict(booster, g["test"]["X"])
                        booster.save_model(a.out / "models" / f"{rid}.json")
                        row = {"dispositivo": cpu_label, "hilos": a.xgb_threads, "epocas": booster.best_iteration + 1,
                               "parada_temprana": None, "parametros": None,
                               "mejor_val_mse": round(float(np.mean((XG.predict(booster, g["val"]["X"])
                                                                     - g["val"]["y"]) ** 2)), 6)}
                        sec = time.perf_counter() - t0
                    else:
                        model = nets.build(m, size)
                        r = train.fit(model, g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"],
                                      seed=SEED, ckpt=a.out / "ckpt" / f"{rid}.pt", max_epochs=a.max_epochs,
                                      device=dev)
                        z = train.predict(model, g["test"]["X"])
                        torch.save({k: v.cpu() for k, v in model.state_dict().items()},
                                   a.out / "weights" / f"{rid}.pt")
                        (a.out / "ckpt" / f"{rid}.pt").unlink(missing_ok=True)
                        sec = r["seconds"]
                        row = {"dispositivo": dev_label, "hilos": None, "epocas": r["epochs"],
                               "parada_temprana": r["stopped_early"], "mejor_val_mse": round(r["best_val_mse"], 6),
                               "parametros": sum(p.numel() for p in model.parameters())}
                    np.savez_compressed(a.out / "preds" / f"{rid}.npz", z_test=z.astype(np.float32),
                                        flow_test=_to_flow(g, z).astype(np.float32))
                    manifest.append(man, fecha=date.today().isoformat(), tipo="walk_forward", run=rid, modelo=m,
                                    config=size, cuenca=basin, h=h, semilla=SEED, segundos=round(sec, 1),
                                    pared_s=round(time.perf_counter() - t0, 1), **row)
                    log.info("%s: %s, %.0f s", rid, row["epocas"], sec)


if __name__ == "__main__":
    main()

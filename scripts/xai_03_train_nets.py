#!/usr/bin/env python
"""Benchmark XAI · paso 3: entrenamiento de las redes (protocolo, sección 4).

Malla completa: cuencas × horizontes × {TCN, ConvNeXt-1D, PatchTST} × 2 tamaños × 3 semillas.
Orden: semilla → horizonte → cuenca → modelo → tamaño, para que un corte deje completa la
semilla 1. Es reanudable: salta las corridas con predicciones guardadas y retoma las
parciales desde su checkpoint por época. Corre en CPU o GPU (Kaggle).

Salidas en --out:
  meta/<cuenca>_h<h>_<particion>.parquet  claves y fechas de las muestras (una vez)
  preds/<run>.npz                          predicciones de validación y prueba (estandarizadas y m³/s)
  weights/<run>.pt                         pesos de la mejor época (para la Fase 3)
  compute_manifest.csv                     una fila por corrida (dispositivo, épocas, segundos)

Uso:
  python scripts/xai_03_train_nets.py --out data/interim/xai_benchmark/nets --device auto
  python scripts/xai_03_train_nets.py --dry-run           # lista las corridas pendientes
"""
from __future__ import annotations

import argparse
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from hidroxai_mx.models import data as D
from hidroxai_mx.models import nets, train
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_03")
SEEDS = (20261010, 20261011, 20261012)
SIZES = (32, 64)
MODELS = ("tcn", "convnext", "patchtst")
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}


def run_id(model: str, size: int, basin: str, h: int, seed: int) -> str:
    return f"{model}-{size}_{SLUG[basin]}_h{h}_s{seed}"


def device_name(dev: torch.device) -> str:
    return torch.cuda.get_device_name(dev) if dev.type == "cuda" else (platform.processor() or "cpu")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "nets")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--threads", type=int, default=0, help="Hilos de PyTorch en CPU (0 = por defecto).")
    ap.add_argument("--basins", nargs="*", default=D.BASINS)
    ap.add_argument("--horizons", nargs="*", type=int, default=list(D.HORIZONS))
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--sizes", nargs="*", type=int, default=list(SIZES))
    ap.add_argument("--seeds", nargs="*", type=int, default=list(SEEDS))
    ap.add_argument("--max-epochs", type=int, default=train.MAX_EPOCHS)
    ap.add_argument("--stop-after-hours", type=float, default=0.0,
                    help="No inicia corridas nuevas pasado este tiempo (sesiones de Kaggle: 12 h).")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    t_start = time.perf_counter()

    dev = torch.device("cuda" if a.device == "auto" and torch.cuda.is_available()
                       else ("cpu" if a.device == "auto" else a.device))
    if a.threads:
        torch.set_num_threads(a.threads)
    for sub in ("meta", "preds", "weights", "ckpt"):
        (a.out / sub).mkdir(parents=True, exist_ok=True)
    runs = [(s, h, b, m, z) for s in a.seeds for h in a.horizons for b in a.basins
            for m in a.models for z in a.sizes]
    todo = [r for r in runs if not (a.out / "preds" / f"{run_id(r[3], r[4], r[2], r[1], r[0])}.npz").exists()]
    log.info("%d corridas, %d pendientes; dispositivo %s (%s)", len(runs), len(todo), dev, device_name(dev))
    if a.dry_run or not todo:
        return

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if basin_of.get(k) in a.basins]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {b: {k: D.daily_panel(ft, k) for k in claves if basin_of[k] == b} for b in a.basins}
    cache: dict = {}
    manifest = a.out / "compute_manifest.csv"

    for seed, h, basin, model_name, size in todo:
        if a.stop_after_hours and (time.perf_counter() - t_start) / 3600 > a.stop_after_hours:
            log.info("Límite de %.1f h alcanzado; las corridas pendientes se retoman en otra sesión.",
                     a.stop_after_hours)
            break
        rid = run_id(model_name, size, basin, h, seed)
        if (basin, h) not in cache:
            cache.clear()                                    # una cuenca × horizonte en memoria
            cache[(basin, h)] = D.group_arrays(panels[basin], h)
            for part in ("val", "test"):
                mp = a.out / "meta" / f"{SLUG[basin]}_h{h}_{part}.parquet"
                if not mp.exists():
                    cache[(basin, h)][part]["meta"].to_parquet(mp, index=False)
        g = cache[(basin, h)]
        model = nets.build(model_name, size)
        t0 = time.perf_counter()
        r = train.fit(model, g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"], seed=seed,
                      ckpt=a.out / "ckpt" / f"{rid}.pt", max_epochs=a.max_epochs, device=dev)
        wall = time.perf_counter() - t0
        out = {}
        for part in ("val", "test"):
            z = train.predict(model, g[part]["X"])
            meta = g[part]["meta"]
            flow = np.empty(len(z))
            for clave, idx in meta.groupby("clave").indices.items():
                flow[idx] = g["scalers"][clave].target_to_flow(z[idx])
            out[f"z_{part}"], out[f"flow_{part}"] = z.astype(np.float32), flow.astype(np.float32)
        np.savez_compressed(a.out / "preds" / f"{rid}.npz", **out)
        torch.save({k: v.cpu() for k, v in model.state_dict().items()}, a.out / "weights" / f"{rid}.pt")
        (a.out / "ckpt" / f"{rid}.pt").unlink(missing_ok=True)
        row = {"fecha": date.today().isoformat(), "tipo": "principal", "run": rid, "modelo": model_name,
               "config": size, "cuenca": basin, "h": h, "semilla": seed, "dispositivo": device_name(dev),
               "hilos": torch.get_num_threads() if dev.type == "cpu" else None, "epocas": r["epochs"],
               "segundos": round(r["seconds"], 1), "pared_s": round(wall, 1),
               "mejor_val_mse": round(r["best_val_mse"], 6), "parada_temprana": r["stopped_early"],
               "parametros": sum(p.numel() for p in model.parameters())}
        pd.DataFrame([row]).to_csv(manifest, mode="a", header=not manifest.exists(), index=False)
        log.info("%s: %d épocas, %.0f s, val MSE %.4f", rid, r["epochs"], r["seconds"], r["best_val_mse"])


if __name__ == "__main__":
    main()

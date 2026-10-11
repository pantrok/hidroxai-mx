#!/usr/bin/env python
"""Benchmark XAI · paso 2b: rendimiento con procesos en paralelo (no cambia el protocolo).

Entrena 2 épocas de TCN-32 y de PatchTST-32 (Lerma–Santiago, h = 1) en P procesos
simultáneos con H hilos cada uno y mide épocas por hora del equipo con el proceso más lento.
Con 15 GB de RAM y otras aplicaciones abiertas solo se prueban 1 × 16 y 2 × 8; cada proceso
lee solo su cuenca. Solo usa entrenamiento y validación.

Salida: results/xai_benchmark/timing_pilot_parallel.json
Uso:  python scripts/xai_02b_parallel_pilot.py
"""
from __future__ import annotations

import json
import multiprocessing as mp

import pandas as pd

from hidroxai_mx.utils import ROOT

OUT = ROOT / "results" / "xai_benchmark"
LAYOUTS = [(1, 16), (2, 8)]
ARCHS = ["tcn", "patchtst"]
EPOCHS = 2


def _worker(args):
    name, threads = args
    import torch

    from hidroxai_mx.models import data as D
    from hidroxai_mx.models import nets, train
    from hidroxai_mx.utils import FEATURES, PROCESSED
    torch.set_num_threads(threads)
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin = D.station_basins(link)
    claves = [k for k in link["clave"] if basin.get(k) == "Lerma–Santiago"]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    g = D.group_arrays({k: D.daily_panel(ft, k) for k in claves}, 1)
    r = train.fit(nets.build(name, 32), g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"],
                  seed=20261010, max_epochs=EPOCHS, patience=EPOCHS + 1)
    return r["seconds"] / r["epochs"]


def main() -> None:
    res = {"fuente": "scripts/xai_02b_parallel_pilot.py", "epocas_por_proceso": EPOCHS, "configuraciones": []}
    ctx = mp.get_context("spawn")
    for name in ARCHS:
        for procs, threads in LAYOUTS:
            with ctx.Pool(procs) as pool:
                spe = pool.map(_worker, [(name, threads)] * procs)
            row = {"modelo": f"{name}-32", "procesos": procs, "hilos": threads,
                   "s_por_epoca_por_proceso": [round(s, 1) for s in spe],
                   "epocas_por_hora_equipo": round(procs * 3600 / max(spe), 1)}
            res["configuraciones"].append(row)
            print(row, flush=True)
            (OUT / "timing_pilot_parallel.json").write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                                            encoding="utf-8")


if __name__ == "__main__":
    main()

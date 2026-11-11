#!/usr/bin/env python
"""Benchmark XAI · MESE: selección de configuración y walk-forward anual del LSTM descriptivo.

Enmienda MESE en results/xai_benchmark/proof_ledger.md. El LSTM no entra en H1–H3 ni en el
ensamble de alertas. La partición principal se entrena con `scripts/xai_03_train_nets.py
--models lstm`, sin cambios. Este script hace lo que `xai_09_walk_forward.py` hace con las
otras redes, que toma su configuración de `e_rq1.json` y no conoce al LSTM:

1. **Selección** (protocolo §4): por horizonte, el tamaño (32 o 64) con la mayor mediana de
   NSE de validación, con la predicción media de las 3 semillas y las estaciones de las cuatro
   cuencas juntas; en empate, el menor. Misma regla y mismo cálculo que `xai_05_evaluate.py`.
2. **Walk-forward:** para cada año Y = 2021…2025, cuenca y horizonte, entrena el LSTM con el
   tamaño elegido y una semilla (20261010) en el pliegue de `D.walk_forward_partitions`, igual
   que la rama de redes de `xai_09`. Es reanudable: salta lo guardado y retoma desde el
   checkpoint por época.

Entrada (--split-runs): la salida de `xai_03` para el LSTM; puede estar repartida en
subcarpetas (una por elemento del arreglo de SLURM). Se buscan `preds/lstm-*.npz` y
`meta/<cuenca>_h<h>_val.parquet` en todo el árbol.

Salidas en --out (mismo esquema que xai_09):
  lstm_selection.csv                      NSE de validación por horizonte y tamaño, y el elegido
  meta/<cuenca>_h<h>_y<Y>_test.parquet    muestras de prueba del pliegue
  preds/lstm-<tamaño>_<cuenca>_h<h>_y<Y>.npz   z_test y flow_test
  weights/<run>.pt                        pesos (explicabilidad)
  compute_manifest.csv                    una fila por corrida (tipo walk_forward)

Uso:
  python scripts/xai_15_lstm_walk_forward.py --split-runs RUNS/split --select-only --out RUNS
  python scripts/xai_15_lstm_walk_forward.py --split-runs RUNS/split --out RUNS/wf/<tag> \\
         --years 2023 --basins Pánuco --horizons 1 --threads 24
  Prueba local corta, sin selección: --size 32 --max-epochs 2
"""
from __future__ import annotations

import argparse
import os
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_15")
YEARS = (2021, 2022, 2023, 2024, 2025)
SEED = 20261010
SEEDS = (20261010, 20261011, 20261012)
SIZES = (32, 64)
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
BASIN_OF_SLUG = {v: k for k, v in SLUG.items()}


def _index(split: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """Predicciones del LSTM (run → archivo) y metadatos de validación (cuenca_h → archivo)."""
    preds = {p.stem: p for p in split.rglob("preds/lstm-*.npz")}
    metas = {}
    for p in split.rglob("meta/*_val.parquet"):
        metas.setdefault(p.stem.removesuffix("_val"), p)
    return preds, metas


def select(split: Path) -> pd.DataFrame:
    """Tamaño por horizonte con la regla del protocolo §4 (como xai_05)."""
    preds, metas = _index(split)
    rows = []
    for h in D.HORIZONS:
        scores = {}
        for size in SIZES:
            vals = []
            for b in D.BASINS:
                tag = f"{SLUG[b]}_h{h}"
                runs = [f"lstm-{size}_{tag}_s{s}" for s in SEEDS]
                missing = [r for r in runs if r not in preds] + ([f"meta {tag}_val"] if tag not in metas else [])
                if missing:
                    raise SystemExit(f"Faltan corridas de la partición principal: {missing}")
                meta = pd.read_parquet(metas[tag])
                sim = np.stack([np.load(preds[r])["flow_val"] for r in runs]).mean(0)
                obs = meta["y_flow"].to_numpy()
                vals.append(pd.Series({k: M.nse(obs[i], sim[i]) for k, i in meta.groupby("clave").indices.items()}))
            scores[size] = float(pd.concat(vals).median())
        best = max(sorted(scores), key=lambda s: (scores[s], -s))
        rows += [{"modelo": "lstm", "h": h, "config": s, "nse_val_mediana": round(v, 4), "elegida": s == best}
                 for s, v in scores.items()]
    return pd.DataFrame(rows)


def _atomic_csv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-runs", type=Path, help="Salida de xai_03 para el LSTM (partición principal).")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "mese" / "lstm_wf")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--size", type=int, default=0, help="Solo pruebas: fija el tamaño sin selección.")
    ap.add_argument("--years", nargs="*", type=int, default=list(YEARS))
    ap.add_argument("--basins", nargs="*", default=list(D.BASINS),
                    help="Nombres de cuenca o sus slugs (lerma_santiago, panuco, alta_balsas, cutzamala).")
    ap.add_argument("--horizons", nargs="*", type=int, default=list(D.HORIZONS))
    ap.add_argument("--max-epochs", type=int, default=100, help="Solo para pruebas rápidas; el protocolo usa 100.")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    a.basins = [BASIN_OF_SLUG.get(b, b) for b in a.basins]
    for sub in ("meta", "preds", "weights", "ckpt"):
        (a.out / sub).mkdir(parents=True, exist_ok=True)

    if a.size:
        chosen = {h: a.size for h in a.horizons}
        log.warning("Tamaño fijado a mano (%d): solo para pruebas, no es la selección del protocolo.", a.size)
    else:
        if a.split_runs is None:
            raise SystemExit("--split-runs es obligatorio salvo con --size.")
        sel = select(a.split_runs)
        _atomic_csv(sel, a.out / "lstm_selection.csv")
        chosen = {int(r.h): int(r.config) for r in sel.itertuples() if r.elegida}
        log.info("Selección: %s", {f"h{h}": f"lstm-{s}" for h, s in chosen.items()})
    if a.select_only:
        return

    import torch

    from hidroxai_mx.models import nets, train
    dev = torch.device(a.device)
    if a.threads:
        torch.set_num_threads(a.threads)
    dev_label = torch.cuda.get_device_name(dev) if dev.type == "cuda" else (platform.processor() or platform.machine())
    man = a.out / "compute_manifest.csv"

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if basin_of.get(k) in a.basins]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft

    for year in a.years:
        parts = D.walk_forward_partitions(year)
        for basin in a.basins:
            bp = {k: panels[k] for k in claves if basin_of[k] == basin}
            for h in a.horizons:
                tag = f"{SLUG[basin]}_h{h}_y{year}"
                cfg = f"lstm-{chosen[h]}"
                rid = f"{cfg}_{tag}"
                if (a.out / "preds" / f"{rid}.npz").exists():
                    continue
                g = D.group_arrays(bp, h, parts)
                mpath = a.out / "meta" / f"{tag}_test.parquet"
                if not mpath.exists():
                    g["test"]["meta"].to_parquet(mpath, index=False)
                t0 = time.perf_counter()
                model = nets.build("lstm", chosen[h])
                r = train.fit(model, g["train"]["X"], g["train"]["y"], g["val"]["X"], g["val"]["y"],
                              seed=SEED, ckpt=a.out / "ckpt" / f"{rid}.pt", max_epochs=a.max_epochs, device=dev)
                z = train.predict(model, g["test"]["X"])
                flow = np.empty(len(z))
                for clave, idx in g["test"]["meta"].groupby("clave").indices.items():
                    flow[idx] = g["scalers"][clave].target_to_flow(z[idx])
                torch.save({k: v.cpu() for k, v in model.state_dict().items()}, a.out / "weights" / f"{rid}.pt")
                np.savez_compressed(a.out / "preds" / f"{rid}.npz", z_test=z.astype(np.float32),
                                    flow_test=flow.astype(np.float32))
                (a.out / "ckpt" / f"{rid}.pt").unlink(missing_ok=True)
                manifest.append(man, fecha=date.today().isoformat(), tipo="walk_forward", run=rid, modelo="lstm",
                                config=chosen[h], cuenca=basin, h=h, semilla=SEED, dispositivo=dev_label,
                                hilos=torch.get_num_threads() if dev.type == "cpu" else None, epocas=r["epochs"],
                                segundos=round(r["seconds"], 1), pared_s=round(time.perf_counter() - t0, 1),
                                mejor_val_mse=round(r["best_val_mse"], 6), parada_temprana=r["stopped_early"],
                                parametros=sum(p.numel() for p in model.parameters()))
                log.info("%s: %d épocas, %.0f s", rid, r["epochs"], r["seconds"])


if __name__ == "__main__":
    main()

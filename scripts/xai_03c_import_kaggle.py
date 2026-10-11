#!/usr/bin/env python
"""Benchmark XAI · paso 3c: verifica e integra las corridas de redes hechas en Kaggle.

Comprueba, sobre la salida de `notebooks/kaggle_xai_train_nets.ipynb` ya descomprimida en
--nets, que:
- están las 216 corridas del diseño principal (3 redes × 2 tamaños × 4 cuencas × 3 horizontes
  × 3 semillas), con predicciones y pesos;
- las muestras (clave, emisión, objetivo, gasto observado) coinciden una por una con las de
  los modelos en CPU (`xai_04`);
- ninguna predicción tiene NaN y sus longitudes coinciden con las muestras.
Después agrega las filas del manifiesto de Kaggle a results/xai_benchmark/compute_manifest.csv
(reemplaza las que ya estuvieran, así que puede re-ejecutarse).

Salida: results/xai_benchmark/kaggle_import.json
Uso:  python scripts/xai_03c_import_kaggle.py [--zip ruta/xai_runs.zip]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.utils import ROOT, get_logger

log = get_logger("xai_03c")
OUT = ROOT / "results" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
SEEDS = (20261010, 20261011, 20261012)
NETS = {"tcn": (32, 64), "convnext": (32, 64), "patchtst": (32, 64)}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _same_samples(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if len(a) != len(b) or not (a["clave"].to_numpy() == b["clave"].to_numpy()).all():
        return False
    for c in ("issue", "target_date"):                # Kaggle y local pueden diferir en precisión (ns/µs)
        if not (a[c].to_numpy("datetime64[D]") == b[c].to_numpy("datetime64[D]")).all():
            return False
    return bool(np.allclose(a["y_flow"], b["y_flow"], equal_nan=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "cpu")
    ap.add_argument("--nets", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "nets")
    ap.add_argument("--zip", type=Path, default=None, help="ZIP descargado de Kaggle (solo para su MD5).")
    a = ap.parse_args()

    expected = {f"{m}-{s}_{SLUG[b]}_h{h}_s{seed}" for m, sizes in NETS.items() for s in sizes
                for b in D.BASINS for h in D.HORIZONS for seed in SEEDS}
    preds = {p.stem for p in (a.nets / "preds").glob("*.npz")}
    weights = {p.stem for p in (a.nets / "weights").glob("*.pt")}
    meta_bad, nan_runs, len_bad = [], [], []
    for b in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            cpu_meta = {p: pd.read_parquet(a.cpu / "meta" / f"{tag}_{p}.parquet") for p in ("val", "test")}
            for p in ("val", "test"):
                if not _same_samples(pd.read_parquet(a.nets / "meta" / f"{tag}_{p}.parquet"), cpu_meta[p]):
                    meta_bad.append(f"{tag}_{p}")
            for rid in sorted(r for r in expected & preds if f"_{tag}_s" in r):
                d = np.load(a.nets / "preds" / f"{rid}.npz")
                if any(np.isnan(d[k]).any() for k in d.files):
                    nan_runs.append(rid)
                if any(len(d[f"{q}_{p}"]) != len(cpu_meta[p]) for q in ("z", "flow") for p in ("val", "test")):
                    len_bad.append(rid)

    km = pd.read_csv(a.nets / "compute_manifest.csv")
    km = km[km["run"].isin(expected)]
    path = OUT / "compute_manifest.csv"
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    old[~old["run"].isin(set(km["run"]))].to_csv(path, index=False)
    for row in km.to_dict("records"):
        manifest.append(path, **{k: v for k, v in row.items() if pd.notna(v)})

    res = {"fecha": date.today().isoformat(), "fuente": "scripts/xai_03c_import_kaggle.py",
           "zip_md5": _md5(a.zip) if a.zip else None,
           "corridas_esperadas": len(expected), "predicciones": len(expected & preds), "pesos": len(expected & weights),
           "faltantes": sorted(expected - preds), "muestras_distintas": meta_bad, "corridas_con_nan": nan_runs,
           "longitudes_distintas": len_bad, "filas_manifiesto_kaggle": len(km),
           "dispositivo": sorted(km["dispositivo"].dropna().unique().tolist()),
           "gpu_h": round(km["segundos"].sum() / 3600, 3), "gpu_pared_h": round(km["pared_s"].sum() / 3600, 3)}
    res["ok"] = not (res["faltantes"] or meta_bad or nan_runs or len_bad) and res["pesos"] == len(expected)
    (OUT / "kaggle_import.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Kaggle: %d/%d corridas, ok=%s, %.2f h de GPU", res["predicciones"], len(expected), res["ok"], res["gpu_h"])


if __name__ == "__main__":
    main()

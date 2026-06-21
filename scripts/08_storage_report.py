#!/usr/bin/env python
"""Etapa 08 — Reporte y guardarraíl de almacenamiento (presupuesto R2 = 10 GB).

Mide el tamaño de cada zona de datos y de lo que DVC versionaría (raw + processed +
features, EXCLUYENDO *.npz). Falla (exit 1) si se supera el tope (env R2_CAP_GB, def 9.5)
para evitar cargos por pasar de 10 GB en Cloudflare R2.

Uso:  python scripts/08_storage_report.py   (correr antes de 'dvc push')
"""
from __future__ import annotations

import os
import sys

from hidroxai_mx.utils import DATA, get_logger

log = get_logger("08_storage")
CAP_GB = float(os.environ.get("R2_CAP_GB", "9.5"))


def _size(path, exclude_ext=(".npz",)) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(exclude_ext):
                continue
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def main() -> None:
    zonas = ["raw", "interim", "processed", "features"]
    versionado = 0
    print(f"{'zona':12} {'tamaño':>12} {'(.npz excl.)':>14}")
    for z in zonas:
        p = DATA / z
        full = _size(p, exclude_ext=())
        novpz = _size(p)
        if z in ("raw", "processed", "features"):
            versionado += novpz
        print(f"{z:12} {full/1e6:10.1f} MB {novpz/1e6:12.1f} MB")
    npz = _size(DATA / "features", exclude_ext=()) - _size(DATA / "features")
    print("-" * 42)
    print(f"A versionar en R2 (raw+processed+features, sin .npz): {versionado/1e9:.2f} GB / tope {CAP_GB} GB")
    if npz > 0:
        print(f"AVISO: hay {npz/1e9:.2f} GB en .npz (tensores) que NO deben subirse a R2.")
    if versionado / 1e9 > CAP_GB:
        log.error("SUPERA el tope de %.1f GB. Reduce estaciones o no versiones features pesadas.", CAP_GB)
        sys.exit(1)
    log.info("Dentro del presupuesto. OK para 'dvc add' + 'dvc push'.")


if __name__ == "__main__":
    main()

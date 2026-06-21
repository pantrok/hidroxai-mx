#!/usr/bin/env python
"""Etapa 02 — Descarga de catálogos espaciales del SMN (KMZ climatológicas/EMAS + EMAS.xlsx).

Uso:
    python scripts/02_download_smn_kmz.py [--overwrite]
"""
from __future__ import annotations

import click

from hidroxai_mx.io import smn
from hidroxai_mx.utils import get_logger

log = get_logger("02_smn")


@click.command()
@click.option("--overwrite", is_flag=True)
def main(overwrite: bool) -> None:
    paths = smn.download_smn_catalogs(overwrite=overwrite)
    for name, p in paths.items():
        log.info("%-30s -> %s", name, p)
    # Parseo de prueba de los KMZ a puntos
    for key in ("estaciones_climatologicas_kmz", "emas_kmz"):
        if key in paths:
            try:
                gdf = smn.read_kmz_points(paths[key])
                log.info("%s: %d estaciones parseadas", key, len(gdf))
            except Exception as exc:  # noqa: BLE001
                log.warning("No se pudo parsear %s: %s", key, exc)
    log.info("Listo. Catálogos SMN en data/raw/smn/")


if __name__ == "__main__":
    main()

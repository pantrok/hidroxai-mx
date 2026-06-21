#!/usr/bin/env python
"""Etapa 01 — Catálogos maestros del SIH (hidrométricas y climatológicas), CSV directo.

Uso:  python scripts/01_download_sih_catalogs.py [--overwrite]
"""
from __future__ import annotations

import click

from hidroxai_mx.io import conagua
from hidroxai_mx.utils import get_logger

log = get_logger("01_catalogs")


@click.command()
@click.option("--overwrite", is_flag=True, help="Re-descargar aunque exista en caché.")
def main(overwrite: bool) -> None:
    for tipo in ("hidrometricas", "climatologicas"):
        path = conagua.download_catalog(tipo, overwrite=overwrite)
        try:
            df = conagua.read_catalog(path)
            rh = sorted(df["region_hidrologica"].dropna().unique())[:8] if "region_hidrologica" in df else []
            log.info("%-15s %5d estaciones -> %s | RH ej.: %s", tipo, len(df), path.name, rh)
        except Exception as exc:  # noqa: BLE001
            log.warning("%-15s descargado, no parseable aún (%s)", tipo, exc)


if __name__ == "__main__":
    main()

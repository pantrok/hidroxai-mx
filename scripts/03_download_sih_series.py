#!/usr/bin/env python
"""Etapa 03 — Series diarias del SIH (CSV directo por estación).

Por defecto descarga las claves de data/processed/estaciones_candidatas_<tipo>.csv
(generadas por 05). Con --all usa todo el catálogo. Fuente primaria 2010–2025.

Uso:
    python scripts/03_download_sih_series.py --tipo hidrometricas
    python scripts/03_download_sih_series.py --tipo climatologicas --all --limit 50
"""
from __future__ import annotations

import click
import pandas as pd

from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, get_logger

log = get_logger("03_series")


@click.command()
@click.option("--tipo", type=click.Choice(["hidrometricas", "climatologicas"]), default="hidrometricas")
@click.option("--all", "use_all", is_flag=True, help="Descargar todo el catálogo (ignora candidatas).")
@click.option("--limit", type=int, default=None, help="Limitar nº de estaciones (prueba).")
def main(tipo: str, use_all: bool, limit: int | None) -> None:
    claves = None
    cand = PROCESSED / f"estaciones_candidatas_{tipo}.csv"
    if not use_all and cand.exists():
        claves = pd.read_csv(cand, dtype=str)["clave"].dropna().tolist()
        log.info("Usando %d estaciones candidatas de %s", len(claves), cand.name)
    else:
        log.info("Sin candidatas (o --all): se usará el catálogo completo.")
    paths = conagua.download_series(tipo, claves=claves, limit=limit)
    log.info("Listo: %d series en data/raw/sih_series/%s/", len(paths), tipo)


if __name__ == "__main__":
    main()

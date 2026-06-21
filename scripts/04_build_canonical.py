#!/usr/bin/env python
"""Etapa 04 — Esquema canónico + Parquet particionado por año.

Lee data/raw/sih_series/<tipo>/*.csv con el parser robusto, aplica QC e imputación
corta, valida con pandera y persiste en data/processed/.

Uso:  python scripts/04_build_canonical.py --tipo hidrometricas
"""
from __future__ import annotations

import click
import pandas as pd

from hidroxai_mx.data import clean, persist, schema
from hidroxai_mx.io import conagua
from hidroxai_mx.utils import RAW, get_logger

log = get_logger("04_canonical")


@click.command()
@click.option("--tipo", type=click.Choice(["hidrometricas", "climatologicas"]), default="hidrometricas")
def main(tipo: str) -> None:
    folder = RAW / "sih_series" / tipo
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise SystemExit(f"No hay CSVs en {folder}. Corre 03 primero.")
    frames = []
    for f in files:
        try:
            frames.append(conagua.read_series_csv(f))
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo leer %s: %s", f.name, exc)
    df = pd.concat(frames, ignore_index=True)
    df["fuente"] = "SIH"
    value_col = "gasto_medio_m3s" if tipo == "hidrometricas" else "precip_mm"
    if value_col not in df.columns:
        value_col = "nivel_m" if "nivel_m" in df.columns else df.columns[1]

    df = clean.to_daily(df)
    df = clean.flag_outliers(df, value_col)
    df = clean.impute_short_gaps(df, value_col)
    df["calidad"] = df["calidad"].fillna(0).astype(int)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["anio"] = df["fecha"].dt.year

    try:
        schema.validate_series(df)
        log.info("Validación pandera: OK")
    except Exception as exc:  # noqa: BLE001
        log.warning("Validación pandera con avisos: %s", str(exc)[:400])

    out = persist.write_parquet(df, f"series_{tipo}.parquet", partition_cols=["anio"])
    log.info("Dataset canónico (%s): %d filas, %d estaciones -> %s",
             tipo, len(df), df["clave_estacion"].nunique(), out)


if __name__ == "__main__":
    main()

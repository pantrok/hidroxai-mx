#!/usr/bin/env python
"""Etapa 04 — Esquema canónico + Parquet particionado por año.

Lee data/raw/sih_series/<tipo>/*.csv con el parser robusto, aplica QC e imputación
corta, valida con pandera y persiste en data/processed/.

Uso:  python scripts/04_build_canonical.py --tipo hidrometricas
"""
from __future__ import annotations

import json

import click
import pandas as pd

from hidroxai_mx.data import clean, persist, schema
from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, RAW, get_logger

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
    value_col = "gasto_medio_m3s" if tipo == "hidrometricas" else "precip_mm"
    if value_col not in df.columns:
        value_col = "nivel_m" if "nivel_m" in df.columns else df.columns[1]

    df = clean.to_daily(df)
    # Después de reconstruir el calendario: las filas de días faltantes también son SIH.
    df["fuente"] = "SIH"
    df = clean.flag_outliers(df, value_col)
    df = clean.flag_physical_limits(df, schema.PHYSICAL_LIMITS)
    if tipo == "hidrometricas":
        df = clean.impute_short_gaps(df, value_col)
    else:
        # La interpolación temporal fabrica lluvia en días sin dato; los huecos de
        # precipitación se dejan como NaN (el relleno espacial está en precip_idw_mm).
        log.info("Precipitación: sin imputación temporal.")
    df["calidad"] = df["calidad"].fillna(0).astype(int)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["anio"] = df["fecha"].dt.year

    rep = schema.validation_report(df)
    out_rep = PROCESSED / "reportes" / f"validacion_{tipo}.json"
    out_rep.parent.mkdir(parents=True, exist_ok=True)
    out_rep.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    if rep["valido"]:
        log.info("Validación pandera: OK")
    else:
        log.warning("Validación pandera: %d reglas con fallas (ver %s)", len(rep["fallas"]), out_rep)

    out = persist.write_parquet(df, f"series_{tipo}.parquet", partition_cols=["anio"])
    log.info("Dataset canónico (%s): %d filas, %d estaciones -> %s",
             tipo, len(df), df["clave_estacion"].nunique(), out)


if __name__ == "__main__":
    main()

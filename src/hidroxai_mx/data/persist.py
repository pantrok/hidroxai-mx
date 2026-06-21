"""Persistencia en Parquet particionado (Capa 2).

Particionado por region_hidrologica (catálogos/series) o por año (series diarias):
acceso 10–50x más rápido en el pipeline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils import PROCESSED, get_logger

log = get_logger("data.persist")


def write_parquet(
    df: pd.DataFrame,
    name: str,
    partition_cols: list[str] | None = None,
    base: Path = PROCESSED,
) -> Path:
    out = base / name
    df.to_parquet(out, partition_cols=partition_cols, index=False)
    log.info("Parquet -> %s (%d filas, partición=%s)", out, len(df), partition_cols)
    return out


def read_parquet(name: str, base: Path = PROCESSED, **kwargs) -> pd.DataFrame:
    return pd.read_parquet(base / name, **kwargs)

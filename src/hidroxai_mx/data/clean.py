"""Limpieza y control de calidad de series (Capa 3).

Reglas (del inventario de datasets):
- NaN codificados como -9999.0 o 0.0 espurios -> np.nan.
- Outliers físicos: gastos negativos y valores > Q99.9 * 3 por estación -> marcar (calidad=2).
- Imputación corta (<7 días): interpolación cúbica restringida.
- Imputación larga: modelo auxiliar con k=3 vecinos espaciales (corr >= 0.6) [ver features].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import get_logger

log = get_logger("data.clean")
SENTINELS = (-9999.0, -9999, 99999.0)


def replace_sentinels(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df:
            df[c] = df[c].replace(list(SENTINELS), np.nan)
    return df


def flag_outliers(df: pd.DataFrame, value_col: str, group: str = "clave_estacion") -> pd.DataFrame:
    """Marca outliers físicos en `calidad` (2) sin eliminarlos (sirven al módulo XAI)."""
    df = df.copy()
    if "calidad" not in df:
        df["calidad"] = 0

    pieces = []
    for key, g in df.groupby(group, sort=False):
        g = g.copy()
        v = g[value_col]
        thr = v.quantile(0.999) * 3 if v.notna().any() else np.inf
        mask = (v < 0) | (v > thr)
        g.loc[mask, "calidad"] = 2
        g[group] = key
        pieces.append(g)
    return pd.concat(pieces) if pieces else df


def impute_short_gaps(
    df: pd.DataFrame, value_col: str, group: str = "clave_estacion", max_gap: int = 7
) -> pd.DataFrame:
    """Interpolación cúbica para huecos < max_gap días; marca calidad=1 lo imputado."""
    df = df.sort_values([group, "fecha"]).copy()
    if "calidad" not in df:
        df["calidad"] = 0

    pieces = []
    for key, g in df.groupby(group, sort=False):
        g = g.copy()
        before = g[value_col].isna()
        try:
            g[value_col] = g[value_col].interpolate(
                method="cubic", limit=max_gap, limit_area="inside"
            )
        except (ValueError, TypeError) as exc:
            # scipy cubic spline needs >=4 valid points; fall back to linear for sparse series.
            log.debug("%s: cubic interpolation failed (%s); using linear", key, exc)
            g[value_col] = g[value_col].interpolate(
                method="linear", limit=max_gap, limit_area="inside"
            )
        newly = before & g[value_col].notna()
        g.loc[newly, "calidad"] = g.loc[newly, "calidad"].clip(lower=1)
        g[group] = key
        pieces.append(g)
    return pd.concat(pieces) if pieces else df


def to_daily(df: pd.DataFrame, group: str = "clave_estacion", tz: str = "America/Mexico_City"):
    """Reindexa cada estación a frecuencia diaria completa (introduce NaN en huecos)."""
    out = []
    for key, g in df.groupby(group):
        g = g.set_index("fecha").sort_index()
        idx = pd.date_range(g.index.min(), g.index.max(), freq="D")
        g = g.reindex(idx)
        g[group] = key
        g.index.name = "fecha"
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True)

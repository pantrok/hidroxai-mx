"""Limpieza y control de calidad de series (Capa 3).

Reglas:
- NaN codificados como -9999.0 -> np.nan.
- Outliers físicos: gastos negativos y valores > Q99.9 * 3 por estación -> marcar (calidad=2),
  sin eliminarlos.
- Imputación corta del gasto: interpolación lineal de huecos internos de 1 a 6 días
  (calidad=1). El método se eligió con el experimento de enmascaramiento de
  scripts/dib_03_imputation_masking.py (lineal ≈ PCHIP; el spline cúbico sobreoscila y
  produce negativos). La precipitación no se imputa en el tiempo.
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


def _short_gap_mask(isna: np.ndarray, max_gap: int) -> np.ndarray:
    """True en los días de huecos internos completos de menos de `max_gap` días."""
    d = np.diff(np.r_[0, isna.astype(np.int8), 0])
    starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
    fill = np.zeros(len(isna), dtype=bool)
    for s, e in zip(starts, ends, strict=True):
        if e - s < max_gap and s > 0 and e < len(isna):
            fill[s:e] = True
    return fill


def impute_short_gaps(
    df: pd.DataFrame, value_col: str, group: str = "clave_estacion", max_gap: int = 7
) -> pd.DataFrame:
    """Interpolación lineal de huecos internos de menos de `max_gap` días; calidad=1.

    - Solo se imputan huecos completos (1 … max_gap−1 días con dato a ambos lados); un
      hueco de `max_gap` días o más queda íntegro, sin relleno parcial.
    - Los nodos son solo observaciones originales (calidad 0): un outlier marcado no se
      usa para interpolar. Como todo valor negativo está marcado, lo imputado es ≥ 0.
    - Espera una serie diaria continua por estación (ver `to_daily`).
    """
    df = df.sort_values([group, "fecha"]).copy()
    if "calidad" not in df:
        df["calidad"] = 0

    pieces = []
    for key, g in df.groupby(group, sort=False):
        g = g.copy()
        v = g[value_col]
        cal = g["calidad"].fillna(0)
        fill = _short_gap_mask(v.isna().to_numpy(), max_gap)
        if fill.any():
            knots = v.where(cal == 0).reset_index(drop=True)
            interp = knots.interpolate(method="linear", limit_area="inside").to_numpy()
            ok = fill & ~np.isnan(interp)
            vals = v.to_numpy(dtype=float, copy=True)
            vals[ok] = interp[ok]
            g[value_col] = vals
            g.loc[g.index[ok], "calidad"] = 1
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

"""Ingeniería de características (L3): lags, agregados, SPI/SPEI, STL, IDW, ventanas.

Opera sobre el esquema canónico ya limpio (data/processed) y produce la zona
data/features lista para tensores de PyTorch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import get_logger

log = get_logger("features")
LAGS = (1, 3, 7, 14, 30)
ROLLING = (7, 30)


# --------------------------------------------------------------------------- #
# Lags y agregados
# --------------------------------------------------------------------------- #
def add_lags(df: pd.DataFrame, col: str, group: str = "clave_estacion", lags=LAGS) -> pd.DataFrame:
    df = df.sort_values([group, "fecha"]).copy()
    for k in lags:
        df[f"{col}_lag{k}"] = df.groupby(group)[col].shift(k)
    return df


def add_rolling(df: pd.DataFrame, col: str, group: str = "clave_estacion", windows=ROLLING):
    df = df.sort_values([group, "fecha"]).copy()
    for w in windows:
        df[f"{col}_ma{w}"] = df.groupby(group)[col].transform(
            lambda s: s.rolling(w, min_periods=max(2, w // 2)).mean())
    return df


# --------------------------------------------------------------------------- #
# Índices de sequía
# --------------------------------------------------------------------------- #
def spi(precip_monthly: pd.Series, scale: int = 3) -> pd.Series:
    """SPI a `scale` meses (climate_indices si está; si no, z-score acumulado)."""
    try:
        from climate_indices import compute, indices  # type: ignore

        vals = indices.spi(
            precip_monthly.to_numpy(dtype=float), scale=scale,
            distribution=indices.Distribution.gamma,
            data_start_year=int(precip_monthly.index[0].year),
            calibration_year_initial=int(precip_monthly.index[0].year),
            calibration_year_final=int(precip_monthly.index[-1].year),
            periodicity=compute.Periodicity.monthly)
        return pd.Series(vals, index=precip_monthly.index, name=f"spi{scale}")
    except Exception as exc:  # noqa: BLE001
        log.warning("climate_indices no disponible (%s); z-score aproximado.", exc)
        roll = precip_monthly.rolling(scale).sum()
        return ((roll - roll.mean()) / roll.std()).rename(f"spi{scale}")


def spei(precip_monthly: pd.Series, pet_monthly: pd.Series, scale: int = 3) -> pd.Series:
    """SPEI a `scale` meses sobre el balance P - PET (aprox. con evaporación)."""
    bal = (precip_monthly - pet_monthly)
    roll = bal.rolling(scale).sum()
    return ((roll - roll.mean()) / roll.std()).rename(f"spei{scale}")


def stl_components(series: pd.Series, period: int = 365) -> pd.DataFrame:
    """Descomposición estacional STL (tendencia/estacional/residuo)."""
    from statsmodels.tsa.seasonal import STL

    res = STL(series.interpolate(), period=period, robust=True).fit()
    return pd.DataFrame({"trend": res.trend, "seasonal": res.seasonal, "resid": res.resid})


# --------------------------------------------------------------------------- #
# IDW: clima vecino -> estación hidrométrica
# --------------------------------------------------------------------------- #
def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def idw_to_station(target_lat: float, target_lon: float,
                   neighbors: list[tuple[float, float, pd.Series]], power: int = 2) -> pd.Series:
    """Interpola por IDW (potencia 2) las series de los vecinos a la estación objetivo.

    neighbors: lista de (lat, lon, serie indexada por fecha). Renormaliza los pesos por
    fecha según los vecinos con dato disponible. Devuelve una Serie combinada.
    """
    if not neighbors:
        return pd.Series(dtype=float, name="idw")
    dists = np.array([_haversine(target_lat, target_lon, la, lo) for la, lo, _ in neighbors])
    w = np.where(dists > 0, 1.0 / np.power(dists, power), 1e12)
    mat = pd.concat([s.rename(i) for i, (_, _, s) in enumerate(neighbors)], axis=1).sort_index()
    vals = mat.to_numpy(dtype=float)
    mask = ~np.isnan(vals)
    num = np.nansum(np.where(mask, vals, 0.0) * w, axis=1)
    den = (mask * w).sum(axis=1)
    out = np.where(den > 0, num / den, np.nan)
    return pd.Series(out, index=mat.index, name="idw")


# --------------------------------------------------------------------------- #
# Normalización y ventanas
# --------------------------------------------------------------------------- #
def normalize_per_station(df: pd.DataFrame, cols: list[str], group: str = "clave_estacion"):
    """Estandariza por estación (z-score). Devuelve (df_norm, stats)."""
    df = df.copy()
    stats = {}
    for c in cols:
        g = df.groupby(group)[c]
        mu, sd = g.transform("mean"), g.transform("std").replace(0, 1.0)
        df[c] = (df[c] - mu) / sd
        stats[c] = {"mean": g.mean(), "std": g.std()}
    return df, stats


def make_windows(arr: np.ndarray, t_in: int = 256, horizon: int = 7):
    """Ventanas deslizantes (X, y) para pronóstico a `horizon` días.

    arr:(T, F). Devuelve X:(N, t_in, F), y:(N,) usando la 1ª columna como objetivo.
    """
    xs, ys = [], []
    for i in range(len(arr) - t_in - horizon + 1):
        xs.append(arr[i:i + t_in])
        ys.append(arr[i + t_in + horizon - 1, 0])
    if not xs:
        return np.empty((0, t_in, arr.shape[1])), np.empty((0,))
    return np.stack(xs), np.asarray(ys)


def build_windows_multi(df: pd.DataFrame, feature_cols: list[str], target_col: str,
                        group: str = "clave_estacion", t_in: int = 256, horizon: int = 7):
    """Genera ventanas (X,y) concatenando todas las estaciones. target = 1ª columna."""
    cols = [target_col] + [c for c in feature_cols if c != target_col]
    Xs, ys, meta = [], [], []
    for key, g in df.sort_values([group, "fecha"]).groupby(group):
        arr = g[cols].to_numpy(dtype=float)
        if len(arr) < t_in + horizon:
            continue
        X, y = make_windows(arr, t_in=t_in, horizon=horizon)
        Xs.append(X); ys.append(y); meta += [(key, horizon)] * len(y)
    if not Xs:
        return np.empty((0, t_in, len(cols))), np.empty((0,)), []
    return np.concatenate(Xs), np.concatenate(ys), meta

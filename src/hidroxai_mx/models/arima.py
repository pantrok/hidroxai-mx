"""ARIMA por estación (protocolo, sección 4).

Ajuste sobre log1p(Q) del periodo de entrenamiento; orden (p, d, q) por AIC con
p, q ∈ {0…3} y d ∈ {0, 1}. Los parámetros se fijan y el filtro de Kalman se corre sobre
toda la serie (los huecos son faltantes): el pronóstico a h pasos desde t propaga el estado
filtrado en t, sin reestimar.
"""
from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

ORDERS = [(p, d, q) for p, d, q in itertools.product(range(4), (0, 1), range(4))]


def _fit(y: np.ndarray, order) -> object | None:
    trend = "c" if order[1] == 0 else "n"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return SARIMAX(y, order=order, trend=trend, enforce_stationarity=True,
                           enforce_invertibility=True).fit(disp=False, maxiter=200)
        except Exception:  # noqa: BLE001 — un orden que no converge se descarta
            return None


def select_and_fit(y_train: np.ndarray) -> tuple[tuple[int, int, int], object]:
    """Mejor orden por AIC sobre la serie diaria de entrenamiento (con NaN en los huecos)."""
    best = None
    for order in ORDERS:
        res = _fit(y_train, order)
        if res is not None and np.isfinite(res.aic) and (best is None or res.aic < best[1].aic):
            best = (order, res)
    if best is None:
        raise RuntimeError("Ningún orden ARIMA convergió")
    return best


def forecast_from_filtered(res, y_full: np.ndarray, h: int) -> np.ndarray:
    """Pronóstico a h pasos emitido en cada t (con la observación de t incluida).

    Devuelve un arreglo de longitud len(y_full): posición t = pronóstico de y[t+h].
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = res.apply(y_full, refit=False)
    ssm = full.model.ssm

    def _fixed(name, ndim):  # matrices invariantes en el tiempo: se quita el eje temporal
        m = np.asarray(ssm[name], dtype=float)
        return m[..., 0] if m.ndim > ndim else m

    T, Z = _fixed("transition", 2), _fixed("design", 2)
    c, d = _fixed("state_intercept", 1), _fixed("obs_intercept", 1)
    a = full.filtered_state                     # [k, n] = a_{t|t}
    Th = np.linalg.matrix_power(T, h)
    acc = sum(np.linalg.matrix_power(T, i) for i in range(h)) @ c
    a_h = Th @ a + acc[:, None]
    return (Z @ a_h + d[:, None]).ravel()


def station_forecasts(panel: pd.DataFrame, train: tuple[str, str], horizons, target: str):
    """Ajusta en entrenamiento y devuelve {h: Serie de pronósticos de Q(t+h) en m³/s, índice t}."""
    q = panel[target].where(panel["calidad"] != 2)
    y = np.log1p(q.clip(lower=0)).to_numpy(dtype=float)
    tr = (panel.index >= train[0]) & (panel.index <= train[1])
    order, res = select_and_fit(y[tr])
    # el filtro corre desde el inicio del entrenamiento para que los estados estén asentados
    start = np.argmax(tr)
    out = {h: pd.Series(np.expm1(forecast_from_filtered(res, y[start:], h)), index=panel.index[start:])
           for h in horizons}
    return order, out

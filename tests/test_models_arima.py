"""Pruebas del ARIMA por estación: propagación del estado filtrado = pronóstico de statsmodels."""
import numpy as np
import pandas as pd
import pytest

from hidroxai_mx.models import arima as A


def _ar1(n=400, phi=0.8, seed=0):
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = 0.5 + phi * y[i - 1] + rng.normal(0, 0.3)
    return y


@pytest.mark.parametrize("h", [1, 7])
def test_filtered_propagation_matches_statsmodels_forecast(h):
    y = _ar1()
    res = A._fit(y[:300], (1, 0, 0))
    fc = A.forecast_from_filtered(res, y, h)
    full = res.apply(y, refit=False)
    t = 320
    ref = full.apply(y[: t + 1], refit=False).forecast(h)[-1]
    assert fc[t] == pytest.approx(ref, rel=1e-6)


def test_station_forecasts_shapes(monkeypatch):
    idx = pd.date_range("2010-01-01", periods=500, freq="D")
    panel = pd.DataFrame({"gasto_medio_m3s": np.expm1(_ar1(500)).clip(0), "calidad": 0}, index=idx)
    monkeypatch.setattr(A, "ORDERS", [(1, 0, 0), (0, 1, 1)])  # malla reducida para la prueba
    order, out = A.station_forecasts(panel, ("2010-01-01", "2010-12-31"), (1, 7), "gasto_medio_m3s")
    assert order in A.ORDERS and set(out) == {1, 7}
    assert len(out[1]) == 500 and np.isfinite(out[7].iloc[-1])

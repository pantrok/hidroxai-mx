"""Pruebas de helpers puros de features (sin dependencias pesadas)."""
import numpy as np
import pandas as pd

from hidroxai_mx import features as F
from hidroxai_mx.geo import spatial


def test_bbox():
    minlon, minlat, maxlon, maxlat = spatial.bbox_from_latlon([10, 20], [-100, -90], margin_deg=0.1)
    assert round(minlon, 1) == -100.1 and round(maxlat, 1) == 20.1


def test_make_windows_shapes():
    arr = np.arange(20, dtype=float).reshape(10, 2)
    X, y = F.make_windows(arr, t_in=3, horizon=2)
    assert X.shape == (6, 3, 2)
    assert y[0] == arr[4, 0]  # i=0 -> t_in+horizon-1 = 4


def test_add_lags():
    df = pd.DataFrame({"clave_estacion": ["A"] * 5,
                       "fecha": pd.date_range("2020-01-01", periods=5),
                       "v": [1.0, 2, 3, 4, 5]})
    out = F.add_lags(df, "v", lags=(1,))
    assert out["v_lag1"].tolist()[1:] == [1.0, 2.0, 3.0, 4.0]


def test_idw_renormalizes_on_nan():
    idx = pd.date_range("2020-01-01", periods=2)
    n1 = (10.0, -100.0, pd.Series([1.0, np.nan], index=idx))
    n2 = (10.0, -100.2, pd.Series([3.0, 4.0], index=idx))
    out = F.idw_to_station(10.0, -100.1, [n1, n2])
    assert not np.isnan(out.iloc[0])         # ambos disponibles -> promedio ponderado
    assert abs(out.iloc[1] - 4.0) < 1e-9     # solo n2 disponible -> toma n2


def test_build_windows_multi():
    rows = []
    for st in ("A", "B"):
        for i in range(8):
            rows.append({"clave_estacion": st, "fecha": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                         "gasto_medio_m3s": float(i), "gasto_medio_m3s_lag1": float(i)})
    df = pd.DataFrame(rows)
    X, y, meta = F.build_windows_multi(df, ["gasto_medio_m3s_lag1"], "gasto_medio_m3s", t_in=3, horizon=2)
    assert X.shape[1:] == (3, 2) and len(y) == len(meta) and len(y) == 2 * (8 - 3 - 2 + 1)

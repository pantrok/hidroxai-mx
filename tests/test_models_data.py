"""Pruebas de muestras, particiones y escalado del benchmark."""
import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D


def _ft(n=80, start="2010-01-01", gaps=(), cal2=(), cal1=()):
    fechas = pd.date_range(start, periods=n, freq="D")
    q = np.arange(1.0, n + 1)
    df = pd.DataFrame({"clave_estacion": "K", "fecha": fechas, "gasto_medio_m3s": q,
                       "gasto_medio_m3s_ma7": q, "gasto_medio_m3s_ma30": q,
                       "precip_idw_mm": np.ones(n), "calidad": 0})
    df.loc[list(cal2), "calidad"] = 2
    df.loc[list(cal1), "calidad"] = 1
    return df.drop(index=list(gaps))


def test_panel_reindexes_daily_and_adds_doy():
    p = D.daily_panel(_ft(gaps=[40]), "K")
    assert len(p) == 80 and p["gasto_medio_m3s"].isna().sum() == 1
    assert {"doy_sin", "doy_cos"} <= set(p.columns)


def test_valid_mask_rules():
    p = D.daily_panel(_ft(gaps=[40], cal2=[60], cal1=[35]), "K")
    m = D.valid_issue_mask(p, h=1)
    assert not m[: D.WINDOW - 1].any()   # ventana incompleta al inicio
    assert not m[34]                      # objetivo (día 35) imputado: calidad 1
    assert m[36]                          # imputado dentro de la ventana: se admite
    assert m[38] and not m[39]            # objetivo (día 40) faltante
    assert not m[45]                      # la ventana contiene el hueco (día 40)
    assert not m[75]                      # la ventana contiene calidad 2 (día 60)


def test_partition_requires_window_and_target_inside():
    dates = pd.date_range("2020-12-01", "2021-02-28", freq="D")
    m = D.partition_mask(dates, h=7, part=("2021-01-01", "2021-12-31"))
    first_ok = dates[m][0]
    assert first_ok == pd.Timestamp("2021-01-30")  # 2021-01-01 + 29 días


def test_samples_shapes_and_inverse_scaling():
    p = D.daily_panel(_ft(n=120), "K")
    sc = D.Scaler.fit(p, ("2010-01-01", "2010-12-31"))
    s = D.station_samples(p, sc, h=7, part=("2010-01-01", "2010-12-31"))
    assert s["X"].shape[1:] == (D.WINDOW, len(D.CHANNELS)) and len(s["y"]) == len(s["X"])
    np.testing.assert_allclose(sc.target_to_flow(s["y"]), s["y_flow"], rtol=1e-5)
    # la última columna de gasto de la ventana es Q(t) estandarizado
    np.testing.assert_allclose(sc.target_to_flow(s["X"][:, -1, 0]), s["q_issue"], rtol=1e-5)


def test_walk_forward_and_basins():
    wf = D.walk_forward_partitions(2025)
    assert wf["train"][1] == "2023-12-31" and wf["test"] == ("2025-01-01", "2025-09-03")
    link = pd.DataFrame({"clave": ["A", "B", "C"], "unidad_piloto": ["Bajio", "Panuco", np.nan]})
    b = D.station_basins(link)
    assert b["A"] == "Lerma–Santiago" and b["B"] == "Pánuco" and pd.isna(b["C"])

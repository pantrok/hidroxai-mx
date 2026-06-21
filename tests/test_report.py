"""Pruebas de las funciones de validación del dataset (report.py)."""
import numpy as np
import pandas as pd

from hidroxai_mx import report


def _toy():
    f = pd.date_range("2010-01-01", "2010-12-31")
    rows = []
    for st, rh in (("A", "12"), ("B", "12"), ("C", "26")):
        for d in f:
            rows.append({"clave_estacion": st, "region_hidrologica": rh, "fecha": d,
                         "gasto_medio_m3s": float(d.month), "calidad": 0})
    df = pd.DataFrame(rows)
    df.loc[df.sample(50, random_state=1).index, "gasto_medio_m3s"] = np.nan
    df.loc[df.sample(10, random_state=2).index, "calidad"] = 1
    return df


def test_inventory():
    inv = report.station_inventory(_toy())
    assert inv["n_estaciones"].sum() == 3
    assert set(inv["region_hidrologica"]) == {"12", "26"}


def test_coverage_range():
    cov = report.coverage_table(_toy(), "gasto_medio_m3s", inicio="2010-01-01", fin="2010-12-31")
    assert cov["cobertura"].between(0, 1).all()
    assert (cov["dias_periodo"] == 365).all()


def test_quality_sums_100():
    q = report.quality_summary(_toy())
    assert abs(q["pct"].sum() - 100.0) < 1e-6
    assert q.loc[q["calidad"] == 1, "n"].iloc[0] >= 1


def test_monthly_climatology():
    mc = report.monthly_climatology(_toy(), "gasto_medio_m3s")
    assert len(mc) == 12 and abs(mc.loc[mc["mes"] == 6, "mean"].iloc[0] - 6.0) < 1e-6


def test_lagged_corr():
    s = report.lagged_corr(_toy(), "gasto_medio_m3s", "gasto_medio_m3s", max_lag=3)
    assert abs(s[0] - 1.0) < 1e-9   # autocorrelación a lag 0 = 1

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


def test_quality_summary_counts_only_days_with_value():
    df = _toy()
    q_all = report.quality_summary(df)
    q_val = report.quality_summary(df, "gasto_medio_m3s")
    assert q_val["n"].sum() == df["gasto_medio_m3s"].notna().sum() < q_all["n"].sum()


def test_deseasonalized_anomalies_remove_seasonal_cycle():
    """Una serie que es solo ciclo estacional + ruido deja anomalías sin ciclo."""
    f = pd.date_range("2010-01-01", "2015-12-31")
    rng = np.random.default_rng(0)
    seasonal = 10 + 5 * np.sin(2 * np.pi * f.dayofyear / 365.25)
    df = pd.DataFrame({"clave_estacion": "A", "fecha": f,
                       "v": seasonal + rng.normal(0, 0.5, len(f))})
    an = report.deseasonalized_anomalies(df, "v", inicio="2010-01-01", fin="2015-12-31")
    by_month = an.assign(m=an["fecha"].dt.month).groupby("m")["anomalia"].mean()
    assert by_month.abs().max() < 0.3          # sin ciclo residual apreciable
    assert abs(an["anomalia"].std() - 1) < 0.05


def test_regional_lag_correlation_recovers_known_lag():
    f = pd.date_range("2010-01-01", periods=2000)
    rng = np.random.default_rng(1)
    x = pd.Series(rng.normal(size=len(f)), index=f)
    y = x.shift(3, freq="D").reindex(f) + rng.normal(0, 0.1, len(f))
    r = report.regional_lag_correlation(x, y, max_lag=10)
    assert int(r.loc[r["pearson"].idxmax(), "lag"]) == 3
    assert int(r.loc[r["spearman"].idxmax(), "lag"]) == 3

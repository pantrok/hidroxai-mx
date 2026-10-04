"""Pruebas del esquema canónico y de la limpieza."""
import numpy as np
import pandas as pd
import pytest

from hidroxai_mx.data import clean, schema


def _toy_series() -> pd.DataFrame:
    fechas = pd.date_range("2010-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "clave_estacion": ["12345"] * 10,
            "fecha": fechas,
            "gasto_medio_m3s": [1.0, 2.0, -9999.0, 3.0, np.nan, 5.0, 6.0, 7.0, 8.0, 9.0],
            "fuente": ["SIH"] * 10,
            "calidad": [0] * 10,
        }
    )


def test_replace_sentinels():
    df = clean.replace_sentinels(_toy_series(), ["gasto_medio_m3s"])
    assert df["gasto_medio_m3s"].isna().sum() >= 1
    assert -9999.0 not in df["gasto_medio_m3s"].values


def test_impute_short_gaps_marks_quality():
    df = clean.replace_sentinels(_toy_series(), ["gasto_medio_m3s"])
    out = clean.impute_short_gaps(df, "gasto_medio_m3s", max_gap=7)
    assert (out["calidad"] == 1).any()


def _series(values, calidad=None) -> pd.DataFrame:
    n = len(values)
    return pd.DataFrame({
        "clave_estacion": ["K"] * n,
        "fecha": pd.date_range("2010-01-01", periods=n, freq="D"),
        "gasto_medio_m3s": values,
        "calidad": calidad if calidad is not None else [0] * n,
    })


def test_impute_fills_short_gap_linearly():
    out = clean.impute_short_gaps(_series([1.0, np.nan, np.nan, 4.0]), "gasto_medio_m3s")
    assert out["gasto_medio_m3s"].tolist() == pytest.approx([1.0, 2.0, 3.0, 4.0])
    assert out["calidad"].tolist() == [0, 1, 1, 0]


@pytest.mark.parametrize("gap", [7, 10])
def test_impute_leaves_long_gap_untouched(gap):
    """Un hueco de 7 días o más no se rellena, ni siquiera sus primeros días."""
    out = clean.impute_short_gaps(_series([1.0] + [np.nan] * gap + [2.0]), "gasto_medio_m3s")
    assert out["gasto_medio_m3s"].isna().sum() == gap
    assert (out["calidad"] == 0).all()


def test_impute_fills_six_day_gap():
    out = clean.impute_short_gaps(_series([0.0] + [np.nan] * 6 + [7.0]), "gasto_medio_m3s")
    assert out["gasto_medio_m3s"].notna().all()
    assert (out["calidad"] == 1).sum() == 6


def test_impute_does_not_use_outliers_as_knots():
    df = _series([1.0, -50.0, np.nan, 4.0], calidad=[0, 2, 0, 0])
    out = clean.impute_short_gaps(df, "gasto_medio_m3s")
    assert out["gasto_medio_m3s"].iloc[1] == -50.0          # el outlier se conserva
    assert out["gasto_medio_m3s"].iloc[2] == pytest.approx(3.0)  # entre 1 (t=0) y 4 (t=3)
    assert out["gasto_medio_m3s"].min() >= -50.0 and out["gasto_medio_m3s"].iloc[2] >= 0


def test_impute_does_not_extrapolate_edges():
    out = clean.impute_short_gaps(_series([np.nan, 1.0, 2.0, np.nan]), "gasto_medio_m3s")
    assert out["gasto_medio_m3s"].isna().tolist() == [True, False, False, True]


def test_series_schema_valid():
    df = clean.replace_sentinels(_toy_series(), ["gasto_medio_m3s"])
    df = clean.impute_short_gaps(df, "gasto_medio_m3s")
    df["calidad"] = df["calidad"].astype(int)
    validated = schema.validate_series(df)
    assert len(validated) == len(df)


def test_series_schema_rejects_bad_fuente():
    df = _toy_series()
    df["fuente"] = "DESCONOCIDA"
    with pytest.raises(Exception):
        schema.validate_series(df)


def _clima(tmed, evap) -> pd.DataFrame:
    n = len(tmed)
    return pd.DataFrame({
        "clave_estacion": ["C"] * n,
        "fecha": pd.date_range("2010-01-01", periods=n, freq="D"),
        "precip_mm": [0.0] * n,
        "tmed_c": tmed,
        "evap_mm": evap,
        "fuente": ["SIH"] * n,
        "calidad": [0] * n,
    })


def test_flag_physical_limits_marks_and_keeps_values():
    df = _clima([20.0, 99.0, np.nan, 18.0], [3.0, 2.0, 1.0, -1.0])
    out = clean.flag_physical_limits(df, schema.PHYSICAL_LIMITS)
    assert out["calidad"].tolist() == [0, 2, 0, 2]
    assert out["tmed_c"].iloc[1] == 99.0 and out["evap_mm"].iloc[3] == -1.0


def test_schema_accepts_out_of_limits_only_when_flagged():
    df = _clima([20.0, 99.0], [3.0, 2.0])
    assert not schema.validation_report(df)["valido"]
    flagged = clean.flag_physical_limits(df, schema.PHYSICAL_LIMITS)
    assert schema.validation_report(flagged)["valido"]

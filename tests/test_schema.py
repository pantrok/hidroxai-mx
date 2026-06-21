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

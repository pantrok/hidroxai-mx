"""El manifiesto de cómputo mantiene un esquema fijo aunque las filas traigan campos distintos."""
import pandas as pd
import pytest

from hidroxai_mx.models import manifest


def test_append_keeps_fixed_columns(tmp_path):
    p = tmp_path / "m.csv"
    manifest.append(p, tipo="piloto", modelo="tcn", segundos=1.0)
    manifest.append(p, tipo="principal", modelo="xgboost", mejor_val_mse=0.1, run="x")
    df = pd.read_csv(p)
    assert list(df.columns) == manifest.COLUMNS and len(df) == 2


def test_replace_drops_previous_run(tmp_path):
    p = tmp_path / "m.csv"
    manifest.append(p, run="a", segundos=1.0)
    manifest.append(p, run="b", segundos=2.0)
    manifest.replace(p, run="a", segundos=3.0)
    df = pd.read_csv(p)
    assert sorted(df["run"]) == ["a", "b"] and df.loc[df["run"] == "a", "segundos"].item() == 3.0


def test_append_rejects_unknown_columns(tmp_path):
    with pytest.raises(ValueError):
        manifest.append(tmp_path / "m.csv", foo=1)

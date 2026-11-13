"""El manifiesto de xai_03 distingue la partición de la corrida (principal o walk_forward)."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("torch")

from hidroxai_mx.models import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _xai_03():
    spec = importlib.util.spec_from_file_location("xai_03", ROOT / "scripts" / "xai_03_train_nets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = {"epochs": 3, "seconds": 12.34, "best_val_mse": 0.1234567, "stopped_early": False}


@pytest.mark.parametrize("tipo", ["principal", "walk_forward"])
def test_manifest_row_keeps_run_type(tipo):
    row = _xai_03().manifest_row(tipo, "lstm-32_cutzamala_h1_s1", "lstm", 32, "Cutzamala", 1, 1, "cpu", 8, R, 13.0, 100)
    assert row["tipo"] == tipo
    assert list(row) == manifest.COLUMNS            # mismo esquema que el manifiesto publicado


def test_manifest_row_rejects_unknown_type():
    with pytest.raises(ValueError):
        _xai_03().manifest_row("otro", "r", "lstm", 32, "Cutzamala", 1, 1, "cpu", 8, R, 13.0, 100)


def test_default_run_type_is_principal():
    # el valor por defecto no cambia: los manifiestos ya publicados siguen siendo válidos
    src = (ROOT / "scripts" / "xai_03_train_nets.py").read_text(encoding="utf-8")
    assert 'default="principal"' in src

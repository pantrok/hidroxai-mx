"""Pruebas del sistema Mamdani del protocolo."""
import numpy as np

from hidroxai_mx.alert import fuzzy as F


def test_vectorized_matches_pointwise():
    fis = F.build_protocol_fis()
    rng = np.random.default_rng(0)
    p, d = rng.uniform(0, 1, 300), rng.uniform(0, 0.4, 300)
    vec = fis.infer_array({"percentil": p, "dispersion": d}, chunk=64)
    ref = np.array([fis.infer({"percentil": a, "dispersion": b}) for a, b in zip(p, d, strict=True)])
    np.testing.assert_allclose(vec, ref, atol=1e-9)


def test_rule_outcomes():
    fis = F.build_protocol_fis()
    lv = lambda p, d: int(F.level_index(fis.infer({"percentil": p, "dispersion": d})))  # noqa: E731
    assert lv(0.30, 0.02) == 0            # bajo → normal
    assert lv(0.85, 0.02) == 1            # alto → vigilancia
    assert lv(0.94, 0.02) == 2            # muy alto, baja dispersión → alerta
    assert lv(0.94, 0.50) == 1            # muy alto, alta dispersión → vigilancia
    assert lv(0.995, 0.02) == 3           # extremo, baja → emergencia
    assert lv(0.995, 0.50) == 2           # extremo, alta → alerta


def test_vertical_shoulders_are_full_membership():
    np.testing.assert_allclose(F.TrapezoidalMF(0.0, 0.0, 0.05, 0.15)([0.0, 0.05, 0.10, 0.15]), [1, 1, 0.5, 0])
    np.testing.assert_allclose(F.TrapezoidalMF(0.97, 0.99, 1.0, 1.0)([0.97, 0.98, 1.0]), [0, 0.5, 1])
    fis = F.build_protocol_fis()
    lv = lambda p, d: int(F.level_index(fis.infer({"percentil": p, "dispersion": d})))  # noqa: E731
    assert lv(0.94, 0.0) == 2             # miembros idénticos: muy alto + baja → alerta
    assert lv(1.0, 0.0) == 3              # por encima del máximo de entrenamiento → emergencia
    assert lv(0.0, 0.0) == 0


def test_rules_table_and_percentile():
    t = F.build_protocol_fis().rules_table()
    assert len(t) == 8 and set(t["nivel"]) == set(F.LEVELS)
    pct = F.station_percentile([1.0, 5.0, 11.0], np.arange(1, 11, dtype=float))
    np.testing.assert_allclose(pct, [0.1, 0.5, 1.0])

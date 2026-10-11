"""Criterios congelados (protocolo §7), estabilidad del walk-forward y contingencia de alertas."""
import numpy as np
import pandas as pd

from hidroxai_mx.alert import evaluation as E
from hidroxai_mx.models import criteria as C

POS, NEG, ZERO = (0.2, 0.1, 0.3), (-0.2, -0.3, -0.1), (0.0, -0.1, 0.1)


def test_h1_rules():
    models = ("xgboost", "tcn", "convnext", "patchtst")
    assert C.h1({f"{m}_h{h}": POS for m in models for h in (7, 14)}) == "SUPPORTED"
    assert C.h1({f"{m}_h{h}": ZERO for m in models for h in (7, 14)}) == "REJECTED"
    mixed = {f"{m}_h{h}": POS for m in models for h in (7, 14)} | {"tcn_h14": ZERO, "convnext_h14": ZERO}
    assert C.h1(mixed) == "OPEN"


def test_h1b_h2_h3_rules():
    assert C.h1b([ZERO, POS]) == "SUPPORTED" and C.h1b([NEG, NEG]) == "REJECTED" and C.h1b([NEG, ZERO]) == "OPEN"
    assert C.h2a([0.6, 0.55, 0.2]) == "SUPPORTED" and C.h2a([0.2, 0.25, 0.4]) == "REJECTED"
    assert C.h2a([0.6, 0.4, 0.2]) == "OPEN"
    assert C.h2b(0.75) == "SUPPORTED" and C.h2b(0.49) == "REJECTED" and C.h2b(0.6) == "OPEN"
    assert C.h3(POS, POS) == "SUPPORTED" and C.h3(POS, NEG) == "REJECTED" and C.h3(ZERO, ZERO) == "REJECTED"
    assert C.h3(POS, ZERO) == "OPEN"


def test_stability_labels():
    assert C.stability({y: "SUPPORTED" for y in range(2021, 2026)}, "SUPPORTED")["robustez"] == "estable"
    s = C.stability({2021: "OPEN", 2022: "SUPPORTED", 2023: "SUPPORTED", 2024: "SUPPORTED", 2025: "SUPPORTED"},
                    "SUPPORTED")
    assert s["robustez"] == "estable con excepciones" and s["excepciones"] == {"2021": "OPEN"}
    assert C.stability({y: "OPEN" for y in range(2021, 2026)}, "SUPPORTED")["robustez"] == "inestable"


def test_contingency_and_bootstrap():
    obs, pred = np.array([1, 1, 0, 0], bool), np.array([1, 0, 1, 0], bool)
    assert E.counts(obs, pred) == {"aciertos": 1, "fallos": 1, "falsas": 1, "negativos": 1}
    assert E.scores(E.counts(obs, pred))["csi"] == 1 / 3
    tab = pd.DataFrame([{"clave": k, "metodo": m, "aciertos": a, "fallos": 1, "falsas": 1}
                        for k in "abcd" for m, a in (("difuso", 3), ("umbral", 1))])
    point, lo, hi = E.boot_delta_csi(tab, n_boot=200)
    assert point == 3 / 5 - 1 / 3 and lo <= point <= hi

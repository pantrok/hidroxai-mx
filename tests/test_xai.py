"""Pruebas de la explicabilidad del benchmark."""
import numpy as np
import pandas as pd
import pytest

from hidroxai_mx.xai import attributions as A


def test_stratified_sample_is_balanced_and_reproducible():
    meta = pd.DataFrame({"clave": ["a"] * 50 + ["b"] * 500 + ["c"] * 5})
    i1 = A.stratified_sample(meta, n_max=60)
    assert (i1 == A.stratified_sample(meta, n_max=60)).all() and len(i1) <= 60
    counts = meta.iloc[i1]["clave"].value_counts()
    assert counts["c"] == 5 and abs(counts["a"] - counts["b"]) <= 5


def test_importance_normalization_and_top_lag():
    attr = np.zeros((4, 30, 6))
    attr[:, 28, A.PRECIP_CHANNEL] = 2.0     # precipitación en t−1
    attr[:, 29, 0] = 1.0                     # gasto en t
    imp = A.importance(attr)
    assert imp.sum() == pytest.approx(1.0)
    assert A.top_precip_lag(imp, h=1) == 2   # t−1 respecto a t+1: 2 días


def test_concordance_identical_is_one():
    rng = np.random.default_rng(0)
    m = rng.random((30, 6))
    c = A.concordance({"x": m, "y": m, "z": -m})
    assert c.set_index(["modelo_a", "modelo_b"]).loc[("x", "y"), "spearman"] == pytest.approx(1.0)


def test_integrated_gradients_completeness_on_linear_model():
    torch = pytest.importorskip("torch")
    pytest.importorskip("captum")
    lin = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(180, 1), torch.nn.Flatten(0))
    X = np.random.default_rng(1).normal(size=(8, 30, 6)).astype(np.float32)
    attr, delta = A.integrated_gradients(lin, X, n_steps=16)
    w = lin[1].weight.detach().numpy().reshape(30, 6)
    np.testing.assert_allclose(attr, X * w, rtol=1e-4, atol=1e-5)   # IG exacto en un modelo lineal
    assert np.abs(delta).max() < 1e-4


def test_patchtst_attention_by_patch():
    pytest.importorskip("torch")
    from hidroxai_mx.models import nets
    m = nets.build("patchtst", 32)
    att = A.attention_by_patch(m, np.zeros((5, 30, 6), dtype=np.float32))
    assert att.shape == (6,) and att.sum() == pytest.approx(1.0, rel=1e-4)

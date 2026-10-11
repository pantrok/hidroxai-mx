"""Pruebas de métricas, bootstrap y referencias del benchmark."""
import numpy as np
import pandas as pd
import pytest

from hidroxai_mx.models import baselines as B
from hidroxai_mx.models import metrics as M


def test_perfect_and_mean_predictions():
    o = np.array([1.0, 2.0, 3.0, 4.0])
    assert M.nse(o, o) == 1.0 and M.kge(o, o) == pytest.approx(1.0)
    assert M.nse(o, np.full(4, o.mean())) == pytest.approx(0.0)
    assert M.rmse(o, o + 1) == pytest.approx(1.0)


def test_skill_against_reference():
    o = np.array([1.0, 2.0, 3.0])
    assert M.skill_mse(o, o, o + 1) == 1.0
    assert M.skill_mse(o, o + 1, o + 1) == pytest.approx(0.0)


def test_bootstrap_ci_contains_median_and_is_reproducible():
    v = np.random.default_rng(0).normal(1.0, 0.2, 50)
    a = M.bootstrap_median_ci(v, n_boot=2000)
    assert a == M.bootstrap_median_ci(v, n_boot=2000)
    assert a[1] <= a[0] <= a[2]


def test_climatology_and_persistence():
    idx = pd.date_range("2010-01-01", "2011-12-31", freq="D")
    panel = pd.DataFrame({"gasto_medio_m3s": np.where(idx.dayofyear < 180, 1.0, 3.0), "calidad": 0},
                         index=idx)
    c = B.Climatology().fit(panel, ("2010-01-01", "2011-12-31"))
    pred = c.predict(pd.to_datetime(["2023-03-01", "2023-10-01"]))
    assert pred[0] == pytest.approx(1.0) and pred[1] == pytest.approx(3.0)
    assert (B.persistence([2.0, 5.0]) == np.array([2.0, 5.0])).all()


def test_kge_components_recompose_kge():
    rng = np.random.default_rng(1)
    o = rng.gamma(2.0, 3.0, 200)
    s = 0.6 * o + rng.normal(0, 1.0, 200) + 0.5
    r, alpha, beta = M.kge_components(o, s)
    assert alpha == pytest.approx(s.std() / o.std()) and beta == pytest.approx(s.mean() / o.mean())
    assert M.kge(o, s) == pytest.approx(1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))

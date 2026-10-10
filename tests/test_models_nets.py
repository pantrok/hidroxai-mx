"""Pruebas de las redes, del entrenamiento reanudable y de XGBoost (datos sintéticos)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
xgboost = pytest.importorskip("xgboost")

from hidroxai_mx.models import nets, train  # noqa: E402
from hidroxai_mx.models import xgb as X  # noqa: E402


def _toy(n=512, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 30, 6)).astype(np.float32)
    y = (0.8 * x[:, -1, 0] + 0.5 * x[:, -3, 3]).astype(np.float32)   # gasto en t y precip en t−2
    return x, y


@pytest.mark.parametrize("name", ["tcn", "convnext", "patchtst"])
def test_shapes_and_one_training_step(name):
    x, y = _toy(64)
    torch.manual_seed(0)
    m = nets.build(name, 32)
    out = m(torch.from_numpy(x))
    assert out.shape == (64,)
    opt = torch.optim.AdamW(m.parameters(), lr=1e-2)
    loss0 = torch.nn.functional.mse_loss(m(torch.from_numpy(x)), torch.from_numpy(y))
    for _ in range(20):
        opt.zero_grad()
        loss = torch.nn.functional.mse_loss(m(torch.from_numpy(x)), torch.from_numpy(y))
        loss.backward()
        opt.step()
    assert loss.item() < loss0.item()


def test_tcn_is_causal():
    m = nets.build("tcn", 32).eval()
    x = torch.from_numpy(_toy(2)[0])
    x2 = x.clone()
    x2[:, -1, :] += 10.0                       # cambia solo el último día
    a, b = m.net(x.transpose(1, 2)), m.net(x2.transpose(1, 2))
    assert torch.allclose(a[:, :, :-1], b[:, :, :-1])


def test_patchtst_attention_maps():
    m = nets.build("patchtst", 32).eval()
    m(torch.from_numpy(_toy(3)[0]))
    maps = m.attention_maps()
    assert len(maps) == 2 and maps[0].shape == (3 * 6, 4, 6, 6)


def test_fit_resumes_from_checkpoint(tmp_path):
    x, y = _toy(256)
    ck = tmp_path / "ck.pt"
    m1 = nets.build("tcn", 32)
    r1 = train.fit(m1, x, y, x[:64], y[:64], seed=1, ckpt=ck, max_epochs=2)
    m2 = nets.build("tcn", 32)
    r2 = train.fit(m2, x, y, x[:64], y[:64], seed=1, ckpt=ck, max_epochs=4)   # reanuda en la época 2
    assert r1["epochs"] == 2 and r2["epochs"] == 4 and r2["history"][:2] == r1["history"]


def test_xgboost_fit_predict_and_treeshap():
    x, y = _toy(600)
    model = X.fit(x[:500], y[:500], x[500:], y[500:], max_depth=4, seed=0, n_jobs=2)
    pred = X.predict(model, x[500:])
    contrib = X.tree_shap(model, x[500:])
    assert pred.shape == (100,) and contrib.shape == (100, 30, 6)
    # aditividad de TreeSHAP: sesgo + contribuciones = predicción
    bias = pred - contrib.reshape(100, -1).sum(1)
    assert np.allclose(bias, bias[0], atol=1e-3)
    imp = np.abs(contrib).mean(0)
    assert imp.argmax() in (29 * 6 + 0, 27 * 6 + 3)   # gasto en t o precipitación en t−2

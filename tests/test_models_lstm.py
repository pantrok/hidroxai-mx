"""Pruebas del LSTM descriptivo (enmienda MESE): interfaz, entrenamiento y explicaciones."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from hidroxai_mx.models import nets, train  # noqa: E402


def _toy(n=512, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 30, 6)).astype(np.float32)
    y = (0.8 * x[:, -1, 0] + 0.5 * x[:, -3, 3]).astype(np.float32)
    return x, y


@pytest.mark.parametrize("size", [32, 64])
def test_lstm_interface_and_training_step(size):
    x, y = _toy(64)
    torch.manual_seed(0)
    m = nets.build("lstm", size)
    assert m.lstm.num_layers == 1 and m.lstm.batch_first and m.lstm.hidden_size == size
    assert m.drop.p == 0.1
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


def test_lstm_fit_with_common_training():
    x, y = _toy(256)
    r = train.fit(nets.build("lstm", 32), x, y, x[:64], y[:64], seed=1, max_epochs=2)
    assert r["epochs"] == 2 and len(r["history"]) == 2


def test_lstm_integrated_gradients():
    pytest.importorskip("captum")
    from hidroxai_mx.xai import attributions as A

    x, _ = _toy(8)
    m = nets.build("lstm", 32)
    attr, delta = A.integrated_gradients(m, x, n_steps=16)
    assert attr.shape == (8, 30, 6) and delta.shape == (8,)
    assert np.isfinite(attr).all()

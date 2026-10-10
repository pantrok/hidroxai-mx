"""Entrenamiento común de las redes (protocolo, sección 4), reanudable por checkpoint.

AdamW (lr 1e-3, weight decay 1e-4), lote 256, pérdida MSE sobre el objetivo estandarizado,
hasta 100 épocas, early stopping con paciencia 10 sobre la pérdida de validación. Al final
del entrenamiento se restauran los pesos de la mejor época.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

LR, WEIGHT_DECAY, BATCH, MAX_EPOCHS, PATIENCE = 1e-3, 1e-4, 256, 100, 10


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


@torch.no_grad()
def predict(model: nn.Module, X: np.ndarray, batch: int = 4096) -> np.ndarray:
    model.eval()
    out = [model(torch.from_numpy(X[i:i + batch])).numpy() for i in range(0, len(X), batch)]
    return np.concatenate(out) if out else np.empty(0, dtype=np.float32)


def _val_loss(model, X, y) -> float:
    return float(np.mean((predict(model, X) - y) ** 2))


def fit(model: nn.Module, Xtr: np.ndarray, ytr: np.ndarray, Xva: np.ndarray, yva: np.ndarray,
        seed: int, ckpt: Path | None = None, max_epochs: int = MAX_EPOCHS,
        patience: int = PATIENCE) -> dict:
    """Entrena con early stopping; si `ckpt` existe, reanuda desde ahí."""
    set_seed(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    gen = torch.Generator().manual_seed(seed)
    state = {"epoch": 0, "best": np.inf, "best_state": None, "wait": 0, "history": [], "seconds": 0.0}
    if ckpt is not None and Path(ckpt).exists():
        saved = torch.load(ckpt, weights_only=False)
        model.load_state_dict(saved["model"])
        opt.load_state_dict(saved["opt"])
        gen.set_state(saved["gen"])
        torch.set_rng_state(saved["torch_rng"])
        state = saved["state"]
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    loss_fn = nn.MSELoss()
    while state["epoch"] < max_epochs and state["wait"] < patience:
        t0 = time.perf_counter()
        model.train()
        perm = torch.randperm(len(Xt), generator=gen)
        for i in range(0, len(perm), BATCH):
            idx = perm[i:i + BATCH]
            opt.zero_grad()
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
        vl = _val_loss(model, Xva, yva)
        state["epoch"] += 1
        state["history"].append(vl)
        if vl < state["best"] - 1e-6:
            state["best"], state["wait"] = vl, 0
            state["best_state"] = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            state["wait"] += 1
        state["seconds"] += time.perf_counter() - t0
        if ckpt is not None:
            Path(ckpt).parent.mkdir(parents=True, exist_ok=True)
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "gen": gen.get_state(),
                        "torch_rng": torch.get_rng_state(), "state": state}, ckpt)
    if state["best_state"] is not None:
        model.load_state_dict(state["best_state"])
    return {"epochs": state["epoch"], "best_val_mse": state["best"], "seconds": state["seconds"],
            "history": state["history"], "stopped_early": state["wait"] >= patience}

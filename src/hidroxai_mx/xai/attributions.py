"""Explicabilidad del benchmark (protocolo, sección 5).

- Muestra fija de ventanas de prueba, estratificada por estación (semilla registrada).
- Integrated Gradients (Captum) para las redes: línea base cero en el espacio estandarizado
  (= media de entrenamiento de la estación por canal; 0 para seno y coseno), 64 pasos.
- TreeSHAP para XGBoost (`hidroxai_mx.models.xgb.tree_shap`).
- Importancia: |atribución| normalizada a suma 1 por ventana y promediada → matriz
  rezago × canal (30 × 6).
- Concordancia entre modelos: Spearman entre los vectores de 180 importancias.
- El rezago se mide respecto al día objetivo: posición j de la ventana (0 = t−29) →
  rezago de ventana 29 − j → rezago respecto al objetivo 29 − j + h.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PRECIP_CHANNEL = 3   # posición de precip_idw_mm en hidroxai_mx.models.data.CHANNELS


def stratified_sample(meta: pd.DataFrame, n_max: int = 2000, seed: int = 20261010) -> np.ndarray:
    """Índices de hasta `n_max` ventanas, el mismo número por estación (o todas si hay menos)."""
    rng = np.random.default_rng(seed)
    groups = meta.groupby("clave").indices
    per = int(np.ceil(n_max / max(len(groups), 1)))
    idx = np.concatenate([rng.choice(ix, size=min(per, len(ix)), replace=False)
                          for _, ix in sorted(groups.items())])
    if len(idx) > n_max:
        idx = rng.choice(idx, size=n_max, replace=False)
    return np.sort(idx)


def integrated_gradients(model, X: np.ndarray, n_steps: int = 64, batch: int = 256):
    """Atribuciones IG [n, 30, canales] y error de completitud por ventana."""
    import torch
    from captum.attr import IntegratedGradients

    model.eval()
    dev = next(model.parameters()).device
    ig = IntegratedGradients(model)
    attrs, deltas = [], []
    for i in range(0, len(X), batch):
        x = torch.from_numpy(X[i:i + batch]).to(dev)
        a, d = ig.attribute(x, baselines=torch.zeros_like(x), n_steps=n_steps,
                            return_convergence_delta=True)
        attrs.append(a.detach().cpu().numpy())
        deltas.append(d.detach().cpu().numpy())
    return np.concatenate(attrs), np.concatenate(deltas)


def importance(attr: np.ndarray) -> np.ndarray:
    """|atribución| normalizada a suma 1 por ventana, promediada → [30, canales]."""
    a = np.abs(attr)
    tot = a.sum(axis=(1, 2), keepdims=True)
    a = np.divide(a, tot, out=np.zeros_like(a), where=tot > 0)
    return a.mean(0)


def attention_by_patch(model, X: np.ndarray, batch: int = 512) -> np.ndarray:
    """PatchTST: atención promedio (capas, cabezas, canales, ventanas) recibida por cada parche."""
    import torch

    model.eval()
    dev = next(model.parameters()).device
    acc, n = None, 0
    with torch.no_grad():
        for i in range(0, len(X), batch):
            model(torch.from_numpy(X[i:i + batch]).to(dev))
            maps = torch.stack(model.attention_maps())          # [capas, B·C, cabezas, P, P]
            recv = maps.mean(dim=(0, 2)).mean(dim=1)            # atención recibida por parche [B·C, P]
            s = recv.sum(0).cpu().numpy()
            acc = s if acc is None else acc + s
            n += recv.shape[0]
    return acc / n


def concordance(imps: dict[str, np.ndarray]) -> pd.DataFrame:
    """Spearman entre cada par de modelos sobre los vectores de importancias."""
    rows = []
    for (a, ia), (b, ib) in itertools.combinations(sorted(imps.items()), 2):
        rows.append({"modelo_a": a, "modelo_b": b, "spearman": float(spearmanr(ia.ravel(), ib.ravel())[0])})
    return pd.DataFrame(rows)


def top_precip_lag(imp: np.ndarray, h: int) -> int:
    """Rezago (días respecto al objetivo) de la precipitación más importante."""
    j = int(np.argmax(imp[:, PRECIP_CHANNEL]))
    return (imp.shape[0] - 1 - j) + h

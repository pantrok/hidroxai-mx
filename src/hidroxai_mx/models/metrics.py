"""Métricas del benchmark (protocolo, sección 4) y bootstrap de estaciones."""
from __future__ import annotations

import numpy as np


def _clean(obs, sim):
    obs, sim = np.asarray(obs, dtype=float), np.asarray(sim, dtype=float)
    ok = np.isfinite(obs) & np.isfinite(sim)
    return obs[ok], sim[ok]


def nse(obs, sim) -> float:
    o, s = _clean(obs, sim)
    den = np.sum((o - o.mean()) ** 2)
    return float(1 - np.sum((s - o) ** 2) / den) if o.size and den > 0 else np.nan


def kge(obs, sim) -> float:
    """Kling–Gupta efficiency (Gupta et al., 2009)."""
    o, s = _clean(obs, sim)
    if o.size < 2 or o.std() == 0 or o.mean() == 0:
        return np.nan
    r = np.corrcoef(o, s)[0, 1] if s.std() > 0 else 0.0
    return float(1 - np.sqrt((r - 1) ** 2 + (s.std() / o.std() - 1) ** 2 + (s.mean() / o.mean() - 1) ** 2))


def rmse(obs, sim) -> float:
    o, s = _clean(obs, sim)
    return float(np.sqrt(np.mean((s - o) ** 2))) if o.size else np.nan


def skill_mse(obs, sim, ref) -> float:
    """SS = 1 − MSE(modelo) / MSE(referencia), sobre las mismas muestras."""
    obs, sim, ref = (np.asarray(a, dtype=float) for a in (obs, sim, ref))
    ok = np.isfinite(obs) & np.isfinite(sim) & np.isfinite(ref)
    mse_ref = np.mean((ref[ok] - obs[ok]) ** 2)
    return float(1 - np.mean((sim[ok] - obs[ok]) ** 2) / mse_ref) if ok.any() and mse_ref > 0 else np.nan


def bootstrap_median_ci(values, n_boot: int = 10_000, seed: int = 20261010,
                        level: float = 0.95) -> tuple[float, float, float]:
    """Mediana e IC por bootstrap de estaciones (remuestreo con reemplazo)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    meds = np.median(v[rng.integers(0, v.size, size=(n_boot, v.size))], axis=1)
    a = (1 - level) / 2
    return float(np.median(v)), float(np.quantile(meds, a)), float(np.quantile(meds, 1 - a))

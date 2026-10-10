"""XGBoost global por cuenca y horizonte (protocolo, sección 4) y su TreeSHAP nativo.

Usa la API nativa (`xgb.train`), sin scikit-learn.
"""
from __future__ import annotations

import numpy as np
import xgboost as xgb

PARAMS = {"eta": 0.05, "subsample": 0.8, "colsample_bytree": 0.8, "tree_method": "hist",
          "objective": "reg:squarederror"}
N_ROUNDS, EARLY_STOP = 2000, 100


def flatten(X: np.ndarray) -> np.ndarray:
    """[n, 30, canales] → [n, 30·canales], columna = rezago × canal (orden de la ventana)."""
    return X.reshape(len(X), -1)


def fit(Xtr, ytr, Xva, yva, max_depth: int, seed: int, n_jobs: int = -1) -> xgb.Booster:
    params = {**PARAMS, "max_depth": max_depth, "seed": seed, "nthread": n_jobs}
    dtr, dva = xgb.DMatrix(flatten(Xtr), label=ytr), xgb.DMatrix(flatten(Xva), label=yva)
    return xgb.train(params, dtr, num_boost_round=N_ROUNDS, evals=[(dva, "val")],
                     early_stopping_rounds=EARLY_STOP, verbose_eval=False)


def _rng(booster: xgb.Booster) -> tuple[int, int]:
    return (0, booster.best_iteration + 1)


def predict(booster: xgb.Booster, X: np.ndarray) -> np.ndarray:
    return booster.predict(xgb.DMatrix(flatten(X)), iteration_range=_rng(booster))


def tree_shap(booster: xgb.Booster, X: np.ndarray) -> np.ndarray:
    """Contribuciones TreeSHAP [n, 30, canales] (sin el término de sesgo)."""
    contrib = booster.predict(xgb.DMatrix(flatten(X)), pred_contribs=True, iteration_range=_rng(booster))
    return contrib[:, :-1].reshape(X.shape)

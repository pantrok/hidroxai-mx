"""Referencias del benchmark: persistencia y climatología (protocolo, sección 4)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TARGET


def persistence(q_issue) -> np.ndarray:
    """Q̂(t+h) = Q(t)."""
    return np.asarray(q_issue, dtype=float)


class Climatology:
    """Media por día del año del periodo de entrenamiento, con suavizado circular de 31 días."""

    def __init__(self, window: int = 31):
        self.window = window
        self.table: np.ndarray | None = None   # índice 1..366

    def fit(self, panel: pd.DataFrame, train: tuple[str, str]) -> Climatology:
        p = panel.loc[train[0]:train[1]]
        p = p[(p["calidad"] != 2) & p[TARGET].notna()]
        doy = p.index.dayofyear.to_numpy()
        sums = np.bincount(doy, weights=p[TARGET].to_numpy(), minlength=367)[1:]
        cnts = np.bincount(doy, minlength=367)[1:].astype(float)
        half = self.window // 2
        k = np.ones(self.window)
        s = np.convolve(np.r_[sums[-half:], sums, sums[:half]], k, mode="valid")
        c = np.convolve(np.r_[cnts[-half:], cnts, cnts[:half]], k, mode="valid")
        with np.errstate(invalid="ignore", divide="ignore"):
            self.table = np.r_[np.nan, s / c]
        return self

    def predict(self, target_dates) -> np.ndarray:
        if self.table is None:
            raise RuntimeError("Climatology sin ajustar")
        return self.table[pd.DatetimeIndex(target_dates).dayofyear.to_numpy()]

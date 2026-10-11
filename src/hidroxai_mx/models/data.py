"""Muestras, particiones y escalado del benchmark de modelos (protocolo congelado).

Implementa las secciones 2 y 3 de ``results/xai_benchmark/protocol.md``:

- grupos de entrenamiento = cuencas piloto (Lerma–Santiago = Lerma Alto + Bajío + Santiago);
- ventana de 30 días con 6 canales y objetivo Q(t+h), h ∈ {1, 7, 14};
- muestra válida: canales completos en la ventana, sin ``calidad = 2`` en la ventana, y
  objetivo con valor y ``calidad = 0``;
- particiones cronológicas: la ventana completa y el día objetivo dentro del periodo;
- log1p y estandarización por estación con estadísticos del periodo de entrenamiento.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TARGET = "gasto_medio_m3s"
CHANNELS = [TARGET, f"{TARGET}_ma7", f"{TARGET}_ma30", "precip_idw_mm", "doy_sin", "doy_cos"]
LOG_CHANNELS = CHANNELS[:4]          # log1p + estandarización por estación
WINDOW = 30
HORIZONS = (1, 7, 14)
PARTITIONS = {
    "train": ("2010-01-01", "2020-12-31"),
    "val": ("2021-01-01", "2022-12-31"),
    "test": ("2023-01-01", "2025-09-03"),
}
UNIT_TO_BASIN = {
    "Lerma Alto": "Lerma–Santiago", "Bajio": "Lerma–Santiago", "Santiago": "Lerma–Santiago",
    "Panuco": "Pánuco", "Alta del Balsas": "Alta del Balsas", "Cutzamala": "Cutzamala",
}
BASINS = ["Lerma–Santiago", "Pánuco", "Alta del Balsas", "Cutzamala"]


def walk_forward_partitions(year: int) -> dict[str, tuple[str, str]]:
    """Pliegue anual: entrenamiento 2010 – Y−2, validación Y−1, prueba Y."""
    end_test = PARTITIONS["test"][1] if year == 2025 else f"{year}-12-31"
    return {"train": ("2010-01-01", f"{year - 2}-12-31"),
            "val": (f"{year - 1}-01-01", f"{year - 1}-12-31"),
            "test": (f"{year}-01-01", end_test)}


def station_basins(link: pd.DataFrame) -> pd.Series:
    """clave → cuenca piloto; NaN para las estaciones fuera de toda unidad."""
    return link.set_index("clave")["unidad_piloto"].map(UNIT_TO_BASIN)


def daily_panel(ft: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Serie diaria continua de una estación con los 6 canales y la bandera de calidad."""
    g = ft.loc[ft["clave_estacion"] == clave, ["fecha", "calidad", *CHANNELS[:4]]].copy()
    g["fecha"] = pd.to_datetime(g["fecha"])
    g = g.set_index("fecha").sort_index()
    g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
    doy = g.index.dayofyear.to_numpy()
    g["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    g["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    g.index.name = "fecha"
    return g


def valid_issue_mask(panel: pd.DataFrame, h: int, window: int = WINDOW) -> np.ndarray:
    """True en cada fecha de emisión t con una muestra válida (protocolo, sección 3)."""
    n = len(panel)
    ok_day = panel[CHANNELS].notna().all(axis=1).to_numpy() & (panel["calidad"].to_numpy() != 2)
    # ventana completa válida: suma móvil de días válidos == window
    c = np.concatenate([[0], np.cumsum(ok_day.astype(int))])
    full = np.zeros(n, dtype=bool)
    idx = np.arange(window - 1, n)
    full[idx] = (c[idx + 1] - c[idx + 1 - window]) == window
    tgt = np.zeros(n, dtype=bool)
    q = panel[TARGET].to_numpy()
    cal = panel["calidad"].to_numpy()
    tgt[: n - h] = ~np.isnan(q[h:]) & (cal[h:] == 0)
    return full & tgt


def partition_mask(dates: pd.DatetimeIndex, h: int, part: tuple[str, str],
                   window: int = WINDOW) -> np.ndarray:
    """La ventana completa (t−window+1) y el día objetivo (t+h) caen dentro del periodo."""
    start, end = pd.Timestamp(part[0]), pd.Timestamp(part[1])
    first = dates - pd.Timedelta(days=window - 1)
    target = dates + pd.Timedelta(days=h)
    return np.asarray((first >= start) & (target <= end))


@dataclass
class Scaler:
    """log1p + z-score por estación con estadísticos del periodo de entrenamiento."""
    mean: dict[str, float]
    std: dict[str, float]

    @classmethod
    def fit(cls, panel: pd.DataFrame, train: tuple[str, str]) -> Scaler:
        p = panel.loc[train[0]:train[1]]
        p = p[p["calidad"] != 2]
        mean, std = {}, {}
        for c in LOG_CHANNELS:
            v = np.log1p(p[c].clip(lower=0).to_numpy(dtype=float))
            v = v[~np.isnan(v)]
            mean[c] = float(v.mean()) if v.size else 0.0
            sd = float(v.std()) if v.size else 1.0
            std[c] = sd if sd > 1e-8 else 1.0
        return cls(mean, std)

    def transform(self, panel: pd.DataFrame) -> np.ndarray:
        out = np.empty((len(panel), len(CHANNELS)), dtype=np.float32)
        for j, c in enumerate(CHANNELS):
            v = panel[c].to_numpy(dtype=float)
            if c in LOG_CHANNELS:
                v = (np.log1p(np.clip(v, 0, None)) - self.mean[c]) / self.std[c]
            out[:, j] = v
        return out

    def target_to_flow(self, z: np.ndarray) -> np.ndarray:
        """Objetivo estandarizado → gasto en m³/s."""
        return np.expm1(np.asarray(z) * self.std[TARGET] + self.mean[TARGET])


def group_arrays(panels: dict[str, pd.DataFrame], h: int,
                 partitions: dict[str, tuple[str, str]] = PARTITIONS) -> dict:
    """Arreglos de un grupo (cuenca) por partición, con escaladores por estación.

    Devuelve {"scalers": {clave: Scaler}, particion: {"X", "y", "meta"}}; `meta` es un
    DataFrame con clave, fecha de emisión, fecha objetivo, gasto observado y Q(t).
    """
    out: dict = {"scalers": {}}
    acc = {k: {"X": [], "y": [], "meta": []} for k in partitions}
    for clave, panel in panels.items():
        sc = Scaler.fit(panel, partitions["train"])
        out["scalers"][clave] = sc
        for name, part in partitions.items():
            s = station_samples(panel, sc, h, part)
            acc[name]["X"].append(s["X"])
            acc[name]["y"].append(s["y"])
            acc[name]["meta"].append(pd.DataFrame({"clave": clave, "issue": s["issue"],
                                                   "target_date": s["target_date"],
                                                   "y_flow": s["y_flow"], "q_issue": s["q_issue"]}))
    for name, a in acc.items():
        out[name] = {"X": np.concatenate(a["X"]) if a["X"] else np.empty((0, WINDOW, len(CHANNELS)), np.float32),
                     "y": np.concatenate(a["y"]) if a["y"] else np.empty(0, np.float32),
                     "meta": pd.concat(a["meta"], ignore_index=True) if a["meta"] else pd.DataFrame()}
    return out


def station_samples(panel: pd.DataFrame, scaler: Scaler, h: int, part: tuple[str, str],
                    window: int = WINDOW) -> dict:
    """Ventanas X [n, window, 6], objetivo estandarizado y, y metadatos de la estación."""
    dates = panel.index
    keep = valid_issue_mask(panel, h, window) & partition_mask(dates, h, part, window)
    t_idx = np.nonzero(keep)[0]
    z = scaler.transform(panel)
    if t_idx.size:
        win = np.lib.stride_tricks.sliding_window_view(z, window, axis=0)  # [n-w+1, 6, w]
        X = win[t_idx - window + 1].transpose(0, 2, 1).astype(np.float32)
    else:
        X = np.empty((0, window, len(CHANNELS)), dtype=np.float32)
    q = panel[TARGET].to_numpy(dtype=float)
    y_flow = q[t_idx + h]
    y = ((np.log1p(np.clip(y_flow, 0, None)) - scaler.mean[TARGET]) / scaler.std[TARGET]).astype(np.float32)
    return {"X": X, "y": y, "issue": dates[t_idx], "target_date": dates[t_idx] + pd.Timedelta(days=h),
            "y_flow": y_flow, "q_issue": q[t_idx]}

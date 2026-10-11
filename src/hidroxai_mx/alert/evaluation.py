"""Evaluación de alertas (protocolo §6): niveles del ensamble, contingencia y ΔCSI.

Misma lógica que `scripts/xai_07_alerts.py`, empaquetada para reutilizarla en el
walk-forward. `scripts/xai_10_walk_forward_eval.py` comprueba que reproduce `e_rq3.json`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import fuzzy as F

EVENTS = {"P90": (0.90, 2), "P99": (0.99, 3)}   # percentil del evento; nivel difuso mínimo


def ensemble_levels(fis, members: np.ndarray, meta: pd.DataFrame, train_obs: dict[str, np.ndarray]) -> dict:
    """members [m, n] en m³/s → media, percentil, dispersión, umbrales de evento y nivel difuso."""
    ens = members.mean(0)
    n = len(meta)
    pct, disp = np.empty(n), np.empty(n)
    thr = {e: np.empty(n) for e in EVENTS}
    for k, idx in meta.groupby("clave").indices.items():
        ref = train_obs[k]
        pct[idx] = F.station_percentile(ens[idx], ref)
        mp = np.stack([F.station_percentile(m[idx], ref) for m in members])
        disp[idx] = np.quantile(mp, 0.75, axis=0) - np.quantile(mp, 0.25, axis=0)
        for e, (q, _) in EVENTS.items():
            thr[e][idx] = np.quantile(ref, q)
    level = F.level_index(fis.infer_array({"percentil": pct, "dispersion": disp}))
    return {"ensamble": ens, "percentil": pct, "dispersion": disp, "umbral": thr, "nivel": level}


def counts(obs: np.ndarray, pred: np.ndarray) -> dict:
    return {"aciertos": int((obs & pred).sum()), "fallos": int((obs & ~pred).sum()),
            "falsas": int((~obs & pred).sum()), "negativos": int((~obs & ~pred).sum())}


def scores(c) -> dict:
    a, f, fa = c["aciertos"], c["fallos"], c["falsas"]
    return {"pod": a / (a + f) if a + f else np.nan, "far": fa / (a + fa) if a + fa else np.nan,
            "csi": a / (a + f + fa) if a + f + fa else np.nan}


def contingency(lv: dict, meta: pd.DataFrame, evaluable: set[str]) -> list[dict]:
    """Tablas por estación evaluable, evento y método (difuso / umbral)."""
    rows, obs_flow = [], meta["y_flow"].to_numpy()
    for k, idx in meta.groupby("clave").indices.items():
        if k not in evaluable:
            continue
        for e, (q, min_level) in EVENTS.items():
            obs = obs_flow[idx] > lv["umbral"][e][idx]
            for metodo, pred in (("difuso", lv["nivel"][idx] >= min_level), ("umbral", lv["percentil"][idx] >= q)):
                rows.append({"clave": k, "evento": e, "metodo": metodo, **counts(obs, pred)})
    return rows


def boot_delta_csi(tab: pd.DataFrame, n_boot: int = 10_000, seed: int = 20261010) -> tuple[float, float, float]:
    """IC del ΔCSI (difuso − umbral) remuestreando estaciones y sumando sus tablas."""
    piv = tab.pivot_table(index="clave", columns="metodo", values=["aciertos", "fallos", "falsas"], aggfunc="sum")
    arr = {m: piv.xs(m, axis=1, level=1)[["aciertos", "fallos", "falsas"]].to_numpy() for m in ("difuso", "umbral")}

    def csi(x):
        s = x.sum(0)
        return s[0] / s.sum() if s.sum() else np.nan

    point = csi(arr["difuso"]) - csi(arr["umbral"])
    rng = np.random.default_rng(seed)
    n = len(piv)
    bs = [csi(arr["difuso"][i]) - csi(arr["umbral"][i]) for i in (rng.integers(0, n, n) for _ in range(n_boot))]
    return float(point), float(np.nanquantile(bs, 0.025)), float(np.nanquantile(bs, 0.975))

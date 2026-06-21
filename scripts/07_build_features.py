#!/usr/bin/env python
"""Etapa 07 — Features y (opcional) tensores.

SIEMPRE escribe la tabla compacta data/features/feature_table.parquet (por-día).
Los tensores de ventana deslizante (.npz) NO se generan por defecto: con stride 1
ocupan ~9 GB para 200 estaciones (reventaría el límite de 10 GB de R2). Se generan
al vuelo en el DataLoader de entrenamiento, o aquí con --save-tensors (cuидado).

Uso:
    python scripts/07_build_features.py --t-in 256 --horizon 7
    python scripts/07_build_features.py --save-tensors   # solo para el set piloto
"""
from __future__ import annotations

import click
import numpy as np
import pandas as pd

from hidroxai_mx import features as F
from hidroxai_mx.data import persist
from hidroxai_mx.utils import FEATURES, PROCESSED, get_logger

log = get_logger("07_features")


def _load(name):
    return persist.read_parquet(name) if (PROCESSED / name).exists() else None


@click.command()
@click.option("--t-in", type=int, default=256)
@click.option("--horizon", type=click.Choice(["1", "7", "14"]), default="7")
@click.option("--save-tensors/--no-save-tensors", default=False,
              help="Materializar .npz (¡pesado! solo para el set piloto).")
def main(t_in: int, horizon: str, save_tensors: bool) -> None:
    horizon = int(horizon)
    hid = _load("series_hidrometricas.parquet")
    cli = _load("series_climatologicas.parquet")
    if hid is None:
        raise SystemExit("Falta data/processed/series_hidrometricas.parquet (corre 04).")

    sel = PROCESSED / "estaciones_seleccionadas_hidrometricas.csv"
    est = pd.read_csv(sel, dtype={"clave": str}) if sel.exists() else pd.DataFrame()
    clamap = {}
    if cli is not None:
        cat = PROCESSED / "estaciones_seleccionadas_climatologicas.csv"
        if cat.exists():
            cc = pd.read_csv(cat, dtype={"clave": str})
            clamap = {r["clave"]: (r["latitud"], r["longitud"]) for _, r in cc.iterrows()}

    target = "gasto_medio_m3s" if "gasto_medio_m3s" in hid.columns else "nivel_m"
    frames = []
    for clave, g in hid.groupby("clave_estacion"):
        g = g.sort_values("fecha").copy()
        row = est[est["clave"] == clave] if not est.empty else pd.DataFrame()
        if cli is not None and not row.empty and isinstance(row.iloc[0].get("vecinos_clima"), str):
            tlat, tlon = row.iloc[0]["latitud"], row.iloc[0]["longitud"]
            neigh = []
            for vk in str(row.iloc[0]["vecinos_clima"]).split(","):
                if vk in clamap and "precip_mm" in cli.columns:
                    s = cli[cli["clave_estacion"] == vk].set_index("fecha")["precip_mm"]
                    neigh.append((clamap[vk][0], clamap[vk][1], s))
            if neigh:
                g["precip_idw_mm"] = F.idw_to_station(tlat, tlon, neigh).reindex(g["fecha"].values).values
        g = F.add_lags(g, target)
        g = F.add_rolling(g, target)
        frames.append(g)

    df = pd.concat(frames, ignore_index=True)
    feat_cols = [c for c in df.columns if c.startswith(target + "_") or c == "precip_idw_mm"]
    df, _ = F.normalize_per_station(df, [target] + feat_cols)
    df = df.dropna(subset=[target])
    persist.write_parquet(df, "feature_table.parquet", partition_cols=None, base=FEATURES)
    log.info("feature_table.parquet: %d filas, %d estaciones, %d features",
             len(df), df["clave_estacion"].nunique(), len(feat_cols))

    if save_tensors:
        X, y, meta = F.build_windows_multi(df.fillna(0.0), feat_cols, target, t_in=t_in, horizon=horizon)
        out = FEATURES / f"tensors_h{horizon}.npz"
        np.savez_compressed(out, X=X.astype("float32"), y=y.astype("float32"),
                            claves=np.array([m[0] for m in meta]))
        log.warning("Tensores materializados X=%s -> %s (NO versionar en DVC/R2).", X.shape, out)
    else:
        log.info("Tensores NO materializados (se generan al entrenar). Usa --save-tensors solo en piloto.")


if __name__ == "__main__":
    main()

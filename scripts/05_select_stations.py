#!/usr/bin/env python
"""Etapa 05 — Selección de estaciones piloto.

Paso 1 (por defecto): filtra el catálogo por regiones hidrológicas piloto y escribe
data/processed/estaciones_candidatas_<tipo>.csv (insumo de 03).

Paso 2 (--refine, tras descargar series): filtra por cobertura >= umbral en el periodo
objetivo y calcula k vecinos climatológicos por estación hidrométrica (haversine).

Uso:
    python scripts/05_select_stations.py            # candidatas por región
    python scripts/05_select_stations.py --refine   # refina por cobertura + vecinos
"""
from __future__ import annotations

import click
import numpy as np
import pandas as pd

from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, RAW, get_logger, load_cuencas

log = get_logger("05_select")


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _coverage(tipo: str, clave: str, value_col: str, inicio: str, fin: str) -> float:
    f = RAW / "sih_series" / tipo / f"{clave}.csv"
    if not f.exists():
        return 0.0
    try:
        df = conagua.read_series_csv(f)
    except Exception:  # noqa: BLE001
        return 0.0
    if value_col not in df.columns:
        return 0.0
    df = df[(df["fecha"] >= inicio) & (df["fecha"] <= fin)]
    expected = (pd.Timestamp(fin) - pd.Timestamp(inicio)).days + 1
    valid = df["value" if False else value_col].notna().sum()
    return float(valid) / expected if expected > 0 else 0.0


@click.command()
@click.option("--refine", is_flag=True, help="Refinar por cobertura y vecinos (tras 03).")
@click.option("--k", type=int, default=3, help="Vecinos climatológicos por estación hidro.")
def main(refine: bool, k: int) -> None:
    cfg = load_cuencas()
    regiones = {str(r) for r in cfg.get("regiones_hidrologicas", [12, 18, 26])}
    crit = cfg.get("criterios_seleccion_estaciones", {})
    cov_min = float(crit.get("cobertura_minima", 0.80))
    per = crit.get("periodo", {"inicio": "2010-01-01", "fin": "2025-12-31"})

    cats = {}
    for tipo in ("hidrometricas", "climatologicas"):
        cat = conagua.download_catalog(tipo)
        df = conagua.read_catalog(cat)
        sel = df[df["region_hidrologica"].isin(regiones)].copy()
        cats[tipo] = sel
        (PROCESSED / f"estaciones_candidatas_{tipo}.csv").write_text(
            sel.to_csv(index=False), encoding="utf-8")
        log.info("%-15s candidatas en RH %s: %d", tipo, sorted(regiones), len(sel))

    if not refine:
        log.info("Candidatas escritas. Corre 03 y luego 05 --refine.")
        return

    out = {}
    for tipo, value_col in (("hidrometricas", "gasto_medio_m3s"), ("climatologicas", "precip_mm")):
        df = cats[tipo].copy()
        df["cobertura"] = [
            _coverage(tipo, c, value_col, per["inicio"], per["fin"]) for c in df["clave"]
        ]
        keep = df[df["cobertura"] >= cov_min].copy()
        out[tipo] = keep
        log.info("%-15s con cobertura>=%.0f%%: %d/%d", tipo, cov_min * 100, len(keep), len(df))

    hid, cli = out["hidrometricas"], out["climatologicas"]
    if not cli.empty:
        neigh = []
        for _, r in hid.iterrows():
            d = _haversine(r["latitud"], r["longitud"], cli["latitud"].values, cli["longitud"].values)
            idx = np.argsort(d)[:k]
            neigh.append(",".join(cli.iloc[idx]["clave"].tolist()))
        hid = hid.assign(vecinos_clima=neigh)
    (PROCESSED / "estaciones_seleccionadas_hidrometricas.csv").write_text(hid.to_csv(index=False), encoding="utf-8")
    (PROCESSED / "estaciones_seleccionadas_climatologicas.csv").write_text(cli.to_csv(index=False), encoding="utf-8")
    log.info("Seleccionadas: %d hidro (+%d vecinos clima). Meta OE1 >=200.", len(hid), k)


if __name__ == "__main__":
    main()

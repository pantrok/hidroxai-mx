#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E6 — sensibilidad del DEM a la resolución (15 m vs 30 m).

Reformulado a nivel de DEM al retirarse los polígonos de subcuencas (enmienda del
2026-09-26 en results/dib_revision/proof_ledger.md). Compara el CEM de Alta del Balsas tal
como se distribuye (0.5″ ≈ 15 m) con el mismo raster agregado a 1″ (≈ 30 m) con
Resampling.average, que es como se produjeron las otras cinco unidades:

- elevación: diferencia 30 m − 15 m (15 m promediado a la celda de 30 m) → sesgo y RMSD;
- pendiente |∇z| en m/m con tamaño de celda en metros por fila (el CEM es geográfico):
  media, mediana, P90 y fracción de celdas con pendiente > 0.3 a cada resolución.

Salidas: results/dib_revision/dem_resolution_sensitivity.csv, e6_dem.json
Uso:  python scripts/dib_06_dem_resolution.py [--unit alta_del_balsas]
"""
from __future__ import annotations

import json

import click
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

from hidroxai_mx.geo.spatial import meters_per_degree
from hidroxai_mx.utils import RAW, ROOT, get_logger

log = get_logger("dib_06")
OUT = ROOT / "results" / "dib_revision"


def _slope(z: np.ndarray, transform) -> np.ndarray:
    """|∇z| (m/m) de un DEM geográfico, con dx, dy en metros por fila."""
    rows = np.arange(z.shape[0])
    lat = transform.f + (rows + 0.5) * transform.e
    m_lat, m_lon = meters_per_degree(lat)
    dx = (abs(transform.a) * m_lon)[:, None]
    dy = (abs(transform.e) * m_lat)[:, None]
    gy, gx = np.gradient(z)
    return np.hypot(gx / dx, gy / dy).astype("float32")


def _stats(s: np.ndarray) -> dict:
    v = s[np.isfinite(s)]
    return {"media": float(v.mean()), "mediana": float(np.median(v)), "p90": float(np.percentile(v, 90)),
            "frac_gt_0.3": float((v > 0.3).mean()), "n_celdas": int(v.size)}


@click.command()
@click.option("--unit", default="alta_del_balsas", show_default=True)
def main(unit: str) -> None:
    with rasterio.open(RAW / "inegi" / f"cem_{unit}.tif") as src:
        z15 = src.read(1).astype("float32")
        z15[z15 == src.nodata] = np.nan
        t15 = src.transform
        h30, w30 = src.height // 2, src.width // 2
        z30m = src.read(1, out_shape=(h30, w30), resampling=Resampling.average, masked=True)
        z30 = z30m.astype("float32").filled(np.nan)
        t30 = src.transform * src.transform.scale(src.width / w30, src.height / h30)
        res15 = abs(src.res[0])

    z15c = z15[: h30 * 2, : w30 * 2].reshape(h30, 2, w30, 2)
    z15_on_30 = np.nanmean(z15c, axis=(1, 3))
    diff = z30 - z15_on_30
    ok = np.isfinite(diff)
    s15 = _slope(z15, t15)
    s30 = _slope(z30, t30)
    st15, st30 = _stats(s15), _stats(s30)
    rows = [{"resolucion": "15 m (0.5″)", **st15}, {"resolucion": "30 m (1″)", **st30}]
    pd.DataFrame(rows).to_csv(OUT / "dem_resolution_sensitivity.csv", index=False)
    lat_mid = t15.f + (z15.shape[0] / 2) * t15.e
    m_lat, m_lon = meters_per_degree(lat_mid)
    res = {
        "unidad": unit,
        "celda_15m_aprox_m": [round(res15 * float(m_lon), 2), round(res15 * float(m_lat), 2)],
        "elevacion_sesgo_m": round(float(np.nanmean(diff[ok])), 3),
        "elevacion_rmsd_m": round(float(np.sqrt(np.nanmean(diff[ok] ** 2))), 3),
        "elevacion_media_15m": round(float(np.nanmean(z15)), 1),
        "elevacion_media_30m": round(float(np.nanmean(z30)), 1),
        "pendiente_15m": {k: round(v, 4) if isinstance(v, float) else v for k, v in st15.items()},
        "pendiente_30m": {k: round(v, 4) if isinstance(v, float) else v for k, v in st30.items()},
        "atenuacion_pendiente_media_pct": round((1 - st30["media"] / st15["media"]) * 100, 1),
        "atenuacion_pendiente_p90_pct": round((1 - st30["p90"] / st15["p90"]) * 100, 1),
    }
    (OUT / "e6_dem.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("E6: %s", res)


if __name__ == "__main__":
    main()

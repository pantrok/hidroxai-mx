#!/usr/bin/env python
"""RevisiÃ³n DIB-D-26-01662 Â· E5b â€” diagnÃ³stico del error de Ã¡rea de las subcuencas.

Contrasta dos mecanismos con evidencia de los rasters de la delineaciÃ³n:

1. Ajuste al cauce mÃ¡s cercano: acumulaciÃ³n (kmÂ²) en la celda a la que
   `jenson_snap_pour_points` moviÃ³ la estaciÃ³n vs acumulaciÃ³n mÃ¡xima dentro del mismo
   radio de ajuste alrededor de la posiciÃ³n original de la estaciÃ³n.
2. Truncamiento del DEM: fracciÃ³n de celdas sin dato del CEM de cada unidad (estados no
   descargados o fuera del mosaico) y si la cuenca de mÃ¡xima acumulaciÃ³n toca el borde.

Salidas: results/dib_revision/snap_diagnosis.csv y e5b_snap_diagnosis.json
Uso:  python scripts/dib_05b_snap_diagnosis.py --work-dir data/interim/dib_revision/work_30m
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from hidroxai_mx.geo.spatial import meters_per_degree
from hidroxai_mx.utils import PROCESSED, RAW, ROOT, get_logger, load_cuencas

log = get_logger("dib_05b")
OUT = ROOT / "results" / "dib_revision"


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


@click.command()
@click.option("--work-dir", type=click.Path(path_type=Path, exists=True), required=True)
def main(work_dir: Path) -> None:
    cfg = load_cuencas()
    snap = float(cfg["delineacion"]["snap_dist_grados"])
    val = pd.read_csv(OUT / "subbasin_validation.csv", dtype={"clave_estacion": str})
    rows, units = [], {}
    for c in cfg["cuencas_piloto"]:
        unit, slug = c["nombre"], _slug(c["nombre"])
        pts = gpd.read_file(ROOT / "data/interim/dib_revision/cuencas_redelin_dedup" / f"{slug}.gpkg", layer="pour_points")
        pts = pts[pts["poligono_en_unidad"] == unit]
        est = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
        est = est.set_index("clave")
        with rasterio.open(work_dir / slug / "d8_accum.tif") as acc, \
                rasterio.open(RAW / "inegi" / f"cem_{slug}.tif") as dem:
            rx, ry = abs(acc.res[0]), abs(acc.res[1])
            nod = 0
            for _, w in dem.block_windows(1):
                nod += int((dem.read(1, window=w) == dem.nodata).sum())
            units[unit] = {"frac_sin_dato_cem": round(nod / (dem.width * dem.height), 4)}
            for _, p in pts.iterrows():
                k = p["clave_estacion"]
                lon0, lat0 = float(est.loc[k, "longitud"]), float(est.loc[k, "latitud"])
                m_lat, m_lon = meters_per_degree(lat0)
                cell_km2 = rx * m_lon * ry * m_lat / 1e6
                r_s, c_s = acc.index(p["lon_ajustada"], p["lat_ajustada"])
                a_snap = float(acc.read(1, window=Window(c_s, r_s, 1, 1))[0, 0])
                r0, c0 = acc.index(lon0, lat0)
                half = int(np.ceil(snap / rx))
                win = Window(max(0, c0 - half), max(0, r0 - half), 2 * half + 1, 2 * half + 1)
                block = acc.read(1, window=win).astype(float)
                yy, xx = np.mgrid[0:block.shape[0], 0:block.shape[1]]
                cy, cx = r0 - win.row_off, c0 - win.col_off
                inside = np.hypot((yy - cy) * ry, (xx - cx) * rx) <= snap
                block[~inside] = np.nan
                a_max = float(np.nanmax(block))
                iy, ix = np.unravel_index(np.nanargmax(block), block.shape)
                rows.append({"clave_estacion": k, "unidad": unit,
                             "area_snap_km2": a_snap * cell_km2,
                             "area_max_radio_km2": a_max * cell_km2,
                             "razon_max_vs_snap": a_max / a_snap if a_snap > 0 else np.nan,
                             "max_toca_borde": bool(win.row_off + iy in (0, acc.height - 1)
                                                    or win.col_off + ix in (0, acc.width - 1))})
    d = pd.DataFrame(rows).merge(val[["clave_estacion", "area_ref_km2", "toca_bbox"]],
                                 on="clave_estacion", how="left")
    d["err_snap"] = d["area_snap_km2"] / d["area_ref_km2"] - 1
    d["err_max_radio"] = d["area_max_radio_km2"] / d["area_ref_km2"] - 1
    d.to_csv(OUT / "snap_diagnosis.csv", index=False)
    m = d[d["area_ref_km2"].notna()]
    res = {
        "estaciones": int(len(d)),
        "con_referencia": int(len(m)),
        "snap_a_celda_de_menor_acumulacion_x10": int((m["razon_max_vs_snap"] > 10).sum()),
        "mediana_abs_err_pct_snap_jenson": round(float(m["err_snap"].abs().median() * 100), 1),
        "mediana_abs_err_pct_max_acum_en_radio": round(float(m["err_max_radio"].abs().median() * 100), 1),
        "frac_dentro_20pct_max_acum_en_radio": round(float((m["err_max_radio"].abs() <= 0.2).mean()), 3),
        "frac_subestima_mas_50pct_max_acum": round(float((m["err_max_radio"] < -0.5).mean()), 3),
        "unidades": units,
    }
    (OUT / "e5b_snap_diagnosis.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("E5b: %s", res)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Código de auditoría (no forma parte del pipeline de v2026.10).

Re-delinea las 6 unidades con los parámetros de v2026.06 (1000 celdas; ajuste Jenson de
0.01°) usando ``delineate_v2026_06_audit`` y escribe un GeoPackage por unidad con capas
``cuenca`` (con clave_estacion y atributos) y ``pour_points``, más
delineation_params.json. Es la entrada de scripts/dib_02_dedup_subbasins.py y de
scripts/dib_05*_*.py.

Uso (desde la raíz del repo):
    PYTHONPATH=src python results/dib_revision/audit_code/redelineate_v2026_06.py \
        --out-dir data/interim/dib_revision/cuencas_redelin \
        --work-dir data/interim/dib_revision/work_30m
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import delineate_v2026_06_audit as D  # noqa: E402

from hidroxai_mx.utils import PROCESSED, RAW, get_logger, load_cuencas  # noqa: E402

log = get_logger("audit_redelin")


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


@click.command()
@click.option("--out-dir", type=click.Path(path_type=Path), required=True)
@click.option("--work-dir", type=click.Path(path_type=Path), required=True)
@click.option("--threshold", type=int, default=1000, show_default=True)
@click.option("--snap-dist", type=float, default=0.01, show_default=True)
def main(out_dir: Path, work_dir: Path, threshold: int, snap_dist: float) -> None:
    import rasterio

    cfg = load_cuencas()
    est = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv",
                      dtype={"clave": str, "region_hidrologica": str})
    out_dir.mkdir(parents=True, exist_ok=True)
    params = {"stream_threshold_celdas": threshold, "snap_dist": snap_dist, "unidades": {}}
    for c in cfg["cuencas_piloto"]:
        nombre, slug = c["nombre"], _slug(c["nombre"])
        x0, y0, x1, y1 = c["bbox"]
        sub = est[est["longitud"].between(x0, x1) & est["latitud"].between(y0, y1)].reset_index(drop=True)
        cem = RAW / "inegi" / f"cem_{slug}.tif"
        with rasterio.open(cem) as src:
            crs = src.crs.to_string()
        pp = D.pour_points_file(sub, work_dir / slug / "pour_points.shp", crs=crs)
        outs = D.delineate(cem, pp, work_dir / slug, stream_threshold=threshold, snap_dist=snap_dist)
        gdf = D.basin_attributes(outs, cem, sub, unit=nombre)
        polys = gdf[gdf["tiene_poligono"]]
        pts = gdf.drop(columns="geometry")
        import geopandas as gpd
        pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts["lon_ajustada"], pts["lat_ajustada"]),
                               crs=crs).to_crs(polys.crs)
        dest = out_dir / f"{slug}.gpkg"
        if dest.exists():
            dest.unlink()
        polys.to_file(dest, layer="cuenca", driver="GPKG")
        pts.to_file(dest, layer="pour_points", driver="GPKG")
        p = D.delineation_params(cem, threshold, snap_dist)
        p.update(n_estaciones=len(sub), n_poligonos=int(len(polys)))
        params["unidades"][nombre] = p
        log.info("%s: %d/%d con polígono", nombre, len(polys), len(sub))
    (out_dir / "delineation_params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")


if __name__ == "__main__":
    main()

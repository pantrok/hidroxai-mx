#!/usr/bin/env python
"""Etapa 06 — Delineación de cuencas (CEM + WhiteboxTools) y unión espacial.

Para cada cuenca piloto:
  1) toma las estaciones hidrométricas seleccionadas como pour points,
  2) recorta el CEM al bbox de la cuenca (si está completo) y delinea parteaguas,
  3) calcula atributos (área, elevación y pendiente medias) y guarda un GeoPackage.

Requisitos: pip install -e ".[geo]" y el CEM por cuenca en
data/raw/inegi/cem_<cuenca>.tif (descargado del portal INEGI a la resolución de conf).

Uso:  python scripts/06_delineate_basins.py [--threshold 1000]
"""
from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from hidroxai_mx.geo import delineate, spatial
from hidroxai_mx.io import inegi
from hidroxai_mx.utils import INTERIM, PROCESSED, RAW, get_logger, load_cuencas

log = get_logger("06_delineate")


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


@click.command()
@click.option("--threshold", type=int, default=1000, help="Umbral de celdas para extraer cauces.")
@click.option("--snap-dist", type=float, default=0.01, help="Distancia de ajuste de pour points (grados).")
def main(threshold: int, snap_dist: float) -> None:
    cfg = load_cuencas()
    sel = PROCESSED / "estaciones_seleccionadas_hidrometricas.csv"
    if not sel.exists():
        sel = PROCESSED / "estaciones_candidatas_hidrometricas.csv"
    if not sel.exists():
        raise SystemExit("Faltan estaciones. Corre 01 y 05 primero.")
    est = pd.read_csv(sel, dtype={"clave": str})

    out_dir = PROCESSED / "cuencas"
    out_dir.mkdir(parents=True, exist_ok=True)
    for c in cfg["cuencas_piloto"]:
        nombre, rh = c["nombre"], str(c["region_hidrologica"])
        res = c.get("cem_resolucion_m", cfg.get("cem_resolucion_default", 30))
        sub = est[est["region_hidrologica"].astype(str) == rh]
        if sub.empty:
            log.warning("%s (RH %s): sin estaciones seleccionadas, se omite.", nombre, rh)
            continue
        slug = _slug(nombre)
        cem = RAW / "inegi" / f"cem_{slug}.tif"
        if not cem.exists():
            bbox = spatial.bbox_from_latlon(sub["latitud"], sub["longitud"])
            log.warning("Falta CEM %s. Descárgalo a %sm y recórtalo al bbox %s. Guía: %s",
                        cem.name, res, [round(b, 3) for b in bbox], inegi.cem_download_hint(nombre, res))
            continue
        work = INTERIM / "delineacion" / slug
        pp = delineate.pour_points_file(sub, work / "pour_points.shp")
        outs = delineate.delineate(cem, pp, work, stream_threshold=threshold, snap_dist=snap_dist)
        gdf = delineate.basin_attributes(outs["watersheds"], cem)
        spatial.write_geopackage(gdf, out_dir / f"{slug}.gpkg", layer="cuenca")
        log.info("%s: %d cuencas delineadas (res %sm)", nombre, len(gdf), res)

    log.info("Listo. GeoPackages en %s", out_dir)


if __name__ == "__main__":
    main()

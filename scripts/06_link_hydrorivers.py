#!/usr/bin/env python
"""Etapa 06 — Vínculo de cada estación hidrométrica con la red HydroRIVERS v1.0.

Para cada estación del conjunto principal busca los tramos de HydroRIVERS (Lehner & Grill,
2013) a menos de ``radio_grados`` de su coordenada de catálogo y reporta:

- el tramo más cercano (id, distancia, área aportante UPLAND_SKM);
- el tramo de mayor área aportante dentro del radio (normalmente el cauce principal que
  mide el aforo) y su distancia;
- ``tramos_distintos`` cuando ambos no coinciden (coordenada ambigua entre dos cauces);
- la unidad piloto cuyo bbox contiene la estación, si alguna.

El área aportante permite dimensionar la cuenca de cada aforo y recuperar su polígono de
HydroBASINS/HydroSHEDS por ``hyriv_id``. Sustituye a los polígonos de subcuencas de
v2026.06, que se retiraron porque no representaban la cuenca completa de los aforos.

HydroRIVERS se descarga de https://www.hydrosheds.org (ver conf/sources.yaml) y se pasa
con --hydrorivers (shapefile de Norteamérica).

Salida: data/processed/estaciones_hidrorivers.csv
Uso:  python scripts/06_link_hydrorivers.py --hydrorivers PATH/HydroRIVERS_v10_na.shp
"""
from __future__ import annotations

from pathlib import Path

import click
import geopandas as gpd
import numpy as np
import pandas as pd

from hidroxai_mx.geo.spatial import meters_per_degree
from hidroxai_mx.utils import PROCESSED, get_logger, load_cuencas

log = get_logger("06_hydrorivers")
CRS_M = "EPSG:6372"


def _unit_of(lon: float, lat: float, region: str, units: list[dict]) -> str | None:
    inside = [u for u in units if u["bbox"][0] <= lon <= u["bbox"][2] and u["bbox"][1] <= lat <= u["bbox"][3]]
    same = [u for u in inside if str(u["region_hidrologica"]) == str(region)]
    return (same or inside)[0]["nombre"] if inside else None


@click.command()
@click.option("--hydrorivers", type=click.Path(path_type=Path, exists=True), required=True)
def main(hydrorivers: Path) -> None:
    cfg = load_cuencas()
    radius_deg = float(cfg["vinculo_hydrorivers"]["radio_grados"])
    est = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv",
                      dtype={"clave": str, "region_hidrologica": str})
    pad = 1.0
    bbox = (est["longitud"].min() - pad, est["latitud"].min() - pad,
            est["longitud"].max() + pad, est["latitud"].max() + pad)
    hr = gpd.read_file(hydrorivers, bbox=bbox, columns=["HYRIV_ID", "UPLAND_SKM"]).to_crs(CRS_M)
    pts = gpd.GeoSeries(gpd.points_from_xy(est["longitud"], est["latitud"]), crs="EPSG:4326").to_crs(CRS_M)

    rows = []
    for (_, s), p in zip(est.iterrows(), pts, strict=True):
        m_lat, m_lon = meters_per_degree(s["latitud"])
        r_m = radius_deg * float(np.mean([m_lat, m_lon]))
        cand = hr.iloc[hr.sindex.query(p.buffer(r_m))].copy()
        cand["d"] = cand.geometry.distance(p)
        cand = cand[cand["d"] <= r_m]
        row = {"clave": s["clave"], "unidad_piloto": _unit_of(s["longitud"], s["latitud"],
                                                              s["region_hidrologica"], cfg["cuencas_piloto"])}
        if cand.empty:
            row.update(hyriv_id=None, dist_m=None, upland_km2=None,
                       hyriv_id_cercano=None, dist_cercano_m=None, upland_cercano_km2=None,
                       tramos_distintos=None)
        else:
            big, near = cand.loc[cand["UPLAND_SKM"].idxmax()], cand.loc[cand["d"].idxmin()]
            row.update(hyriv_id=int(big["HYRIV_ID"]), dist_m=round(float(big["d"]), 1),
                       upland_km2=float(big["UPLAND_SKM"]),
                       hyriv_id_cercano=int(near["HYRIV_ID"]), dist_cercano_m=round(float(near["d"]), 1),
                       upland_cercano_km2=float(near["UPLAND_SKM"]),
                       tramos_distintos=bool(big["HYRIV_ID"] != near["HYRIV_ID"]))
        rows.append(row)
    out = pd.DataFrame(rows)
    for c in ("hyriv_id", "hyriv_id_cercano"):
        out[c] = out[c].astype("Int64")
    dest = PROCESSED / "estaciones_hidrorivers.csv"
    out.to_csv(dest, index=False)
    log.info("%d estaciones; %d con tramo a ≤ %.3f°; %d con tramo más cercano ≠ de mayor área → %s",
             len(out), int(out["hyriv_id"].notna().sum()), radius_deg,
             int(out["tramos_distintos"].fillna(False).sum()), dest)


if __name__ == "__main__":
    main()

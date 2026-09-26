"""Utilidades espaciales: bbox, GeoDataFrame, reproyección y uniones."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..utils import get_logger, load_sources

log = get_logger("geo.spatial")
_CFG = load_sources()
CRS_GEO = _CFG.get("crs_geografico", "EPSG:4326")
CRS_PIPE = _CFG.get("crs_pipeline", "EPSG:6372")


def meters_per_degree(lat_deg):
    """Metros por grado de latitud y de longitud en el elipsoide GRS80 (el de EPSG:6365)."""
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    phi = np.radians(np.asarray(lat_deg, dtype=float))
    s2 = np.sin(phi) ** 2
    m_lat = np.pi / 180 * a * (1 - e2) / (1 - e2 * s2) ** 1.5
    m_lon = np.pi / 180 * a * np.cos(phi) / np.sqrt(1 - e2 * s2)
    return m_lat, m_lon


def bbox_from_latlon(lats, lons, margin_deg: float = 0.15) -> tuple[float, float, float, float]:
    """Caja envolvente (minlon, minlat, maxlon, maxlat) con margen, en grados.

    Pura (numpy); sirve para recortar el CEM al área de una cuenca.
    """
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    return (float(np.nanmin(lons) - margin_deg), float(np.nanmin(lats) - margin_deg),
            float(np.nanmax(lons) + margin_deg), float(np.nanmax(lats) + margin_deg))


def to_geodataframe(df: pd.DataFrame, lon: str = "longitud", lat: str = "latitud",
                    crs: str = CRS_GEO):
    """DataFrame -> GeoDataFrame de puntos (geopandas diferido)."""
    import geopandas as gpd

    return gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df[lon], df[lat]), crs=crs)


def reproject(gdf, crs: str = CRS_PIPE):
    return gdf.to_crs(crs)


def assign_basin(stations_gdf, basins_gdf, basin_cols=("region_hidrologica", "cuenca")):
    """Etiqueta cada estación con los atributos de la cuenca/subcuenca que la contiene."""
    import geopandas as gpd

    cols = [c for c in basin_cols if c in basins_gdf.columns] + [basins_gdf.geometry.name]
    joined = gpd.sjoin(stations_gdf, basins_gdf[cols], predicate="within", how="left")
    return joined.drop(columns=[c for c in joined.columns if c.startswith("index_right")])


def write_geopackage(gdf, path: Path, layer: str = "data") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, layer=layer, driver="GPKG")
    log.info("GeoPackage -> %s (capa=%s, %d geom)", path, layer, len(gdf))
    return path

"""Delineación de cuencas a partir del CEM con WhiteboxTools.

Pipeline (por cuenca):
  CEM(tif) -> fill_depressions -> d8_pointer + d8_flow_accumulation
           -> extract_streams(umbral) -> snap pour points (estaciones)
           -> watershed -> polígonos + atributos (área, elevación, pendiente).

Todas las dependencias (whitebox, rasterio, geopandas) se importan diferido.
"""
from __future__ import annotations

from pathlib import Path

from ..utils import get_logger

log = get_logger("geo.delineate")


def clip_cem_to_bbox(cem_tif: Path, bbox: tuple[float, float, float, float], out_tif: Path) -> Path:
    """Recorta el CEM al bbox (minlon,minlat,maxlon,maxlat). rasterio diferido."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    out_tif = Path(out_tif)
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(cem_tif) as src:
        left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox)
        win = from_bounds(left, bottom, right, top, src.transform)
        data = src.read(window=win)
        prof = src.profile
        prof.update(height=data.shape[1], width=data.shape[2],
                    transform=src.window_transform(win))
        with rasterio.open(out_tif, "w", **prof) as dst:
            dst.write(data)
    return out_tif


def pour_points_file(stations_df, out_path: Path, lon="longitud", lat="latitud") -> Path:
    """Escribe las estaciones como shapefile de puntos (pour points) para whitebox."""
    from ..geo.spatial import to_geodataframe

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf = to_geodataframe(stations_df, lon=lon, lat=lat)
    gdf.to_file(out_path)
    return out_path


def delineate(dem_tif: Path, pour_points: Path, work_dir: Path,
              stream_threshold: int = 1000, snap_dist: float = 0.01) -> dict[str, Path]:
    """Ejecuta el pipeline WhiteboxTools y devuelve rutas de salidas clave."""
    import whitebox

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(work_dir))
    wbt.verbose = False

    filled = "cem_filled.tif"
    pntr = "d8_pointer.tif"
    accum = "d8_accum.tif"
    streams = "streams.tif"
    snapped = "pour_snapped.shp"
    wsheds = "watersheds.tif"
    wsheds_v = "watersheds.shp"

    wbt.fill_depressions(str(dem_tif), filled)
    wbt.d8_pointer(filled, pntr)
    wbt.d8_flow_accumulation(filled, accum, out_type="cells")
    wbt.extract_streams(accum, streams, threshold=stream_threshold)
    wbt.jenson_snap_pour_points(str(pour_points), streams, snapped, snap_dist=snap_dist)
    wbt.watershed(pntr, snapped, wsheds)
    wbt.raster_to_vector_polygons(wsheds, wsheds_v)
    log.info("Delineación lista en %s", work_dir)
    return {k: work_dir / v for k, v in {
        "filled": filled, "pointer": pntr, "accum": accum, "streams": streams,
        "snapped": snapped, "watersheds_raster": wsheds, "watersheds": wsheds_v}.items()}


def basin_attributes(watersheds_shp: Path, dem_tif: Path) -> "object":
    """Calcula área_km2, elevación_media y pendiente_media por polígono de cuenca."""
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.mask import mask

    gdf = gpd.read_file(watersheds_shp)
    gdf = gdf.to_crs("EPSG:6372")
    gdf["area_km2"] = gdf.geometry.area / 1e6
    elev_mean, slope_mean = [], []
    with rasterio.open(dem_tif) as src:
        g = gdf.to_crs(src.crs)
        for geom in g.geometry:
            try:
                arr, _ = mask(src, [geom.__geo_interface__], crop=True, nodata=np.nan)
                vals = arr[0]
                elev_mean.append(float(np.nanmean(vals)))
                gy, gx = np.gradient(vals)
                slope = np.degrees(np.arctan(np.hypot(gx, gy)))
                slope_mean.append(float(np.nanmean(slope)))
            except Exception:  # noqa: BLE001
                elev_mean.append(np.nan); slope_mean.append(np.nan)
    gdf["elevacion_media"] = elev_mean
    gdf["pendiente_media"] = slope_mean
    return gdf

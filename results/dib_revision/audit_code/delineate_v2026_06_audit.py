"""Código de auditoría (no forma parte del pipeline de v2026.10).

Delineación por unidad con los parámetros de v2026.06 (WhiteboxTools: fill_depressions →
d8_pointer → d8_flow_accumulation → extract_streams → jenson_snap_pour_points →
watershed), con tres correcciones respecto del código publicado, para poder auditar los
polígonos: (1) rutas absolutas y error explícito si una herramienta falla; (2) atributos
por estadística zonal (el código publicado dejaba elevación y pendiente en NaN);
(3) ``clave_estacion`` explícita por polígono, tomada del raster en el punto ajustado.

Con esto se obtuvieron los resultados E2, E5 y E5b de results/dib_revision (los polígonos
de subcuencas se retiraron en v2026.10; ver proof_ledger.md).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)


def meters_per_degree(lat_deg):
    phi = np.radians(np.asarray(lat_deg, dtype=float))
    s2 = np.sin(phi) ** 2
    m_lat = np.pi / 180 * _A * (1 - _E2) / (1 - _E2 * s2) ** 1.5
    m_lon = np.pi / 180 * _A * np.cos(phi) / np.sqrt(1 - _E2 * s2)
    return m_lat, m_lon


def delineation_params(dem_tif: Path, stream_threshold: int, snap_dist: float) -> dict:
    import rasterio

    with rasterio.open(dem_tif) as src:
        res = (abs(src.res[0]), abs(src.res[1]))
        lat = (src.bounds.top + src.bounds.bottom) / 2
        epsg = src.crs.to_epsg() if src.crs else None
    m_lat, m_lon = meters_per_degree(lat)
    dx, dy = res[0] * m_lon, res[1] * m_lat
    return {"dem": Path(dem_tif).name, "dem_epsg": epsg, "latitud_media": round(lat, 4),
            "celda_grados": res, "celda_m_aprox": [round(float(dx), 2), round(float(dy), 2)],
            "stream_threshold_celdas": int(stream_threshold),
            "stream_threshold_km2": round(float(stream_threshold * dx * dy / 1e6), 4),
            "snap_dist_unidades_mapa": snap_dist, "snap_dist_unidades": "grados",
            "snap_dist_m_aprox": round(float(snap_dist * np.mean([m_lat, m_lon])), 1)}


def pour_points_file(stations_df, out_path: Path, crs: str) -> Path:
    import geopandas as gpd

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    d = stations_df.reset_index(drop=True)
    gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d["longitud"], d["latitud"]),
                     crs="EPSG:4326").to_crs(crs).to_file(out_path)
    return out_path


def delineate(dem_tif: Path, pour_points: Path, work_dir: Path,
              stream_threshold: int = 1000, snap_dist: float = 0.01) -> dict[str, Path]:
    import whitebox

    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(work_dir))
    wbt.verbose = False

    def _run(name, *args, **kwargs):
        rc = getattr(wbt, name)(*args, **kwargs)
        if rc != 0:
            raise RuntimeError(f"WhiteboxTools {name} devolvió código {rc} en {work_dir}")

    _run("fill_depressions", str(Path(dem_tif).resolve()), "cem_filled.tif")
    _run("d8_pointer", "cem_filled.tif", "d8_pointer.tif")
    _run("d8_flow_accumulation", "cem_filled.tif", "d8_accum.tif", out_type="cells")
    _run("extract_streams", "d8_accum.tif", "streams.tif", threshold=stream_threshold)
    _run("jenson_snap_pour_points", str(Path(pour_points).resolve()), "streams.tif",
         "pour_snapped.shp", snap_dist=snap_dist)
    _run("watershed", "d8_pointer.tif", "pour_snapped.shp", "watersheds.tif")
    return {k: work_dir / v for k, v in {
        "filled": "cem_filled.tif", "pointer": "d8_pointer.tif", "accum": "d8_accum.tif",
        "streams": "streams.tif", "snapped": "pour_snapped.shp",
        "watersheds_raster": "watersheds.tif"}.items()}


def _zonal_stats(wsheds_tif: Path, dem_tif: Path, n_ids: int, block_rows: int = 1024) -> dict:
    import rasterio
    from rasterio.windows import Window

    size = n_ids + 1
    n_cells, area = np.zeros(size), np.zeros(size)
    z_sum, z_n, s_sum, s_n = np.zeros(size), np.zeros(size), np.zeros(size), np.zeros(size)
    big = np.iinfo(np.int64).max
    rmin, rmax = np.full(size, big, np.int64), np.full(size, -1, np.int64)
    cmin, cmax = np.full(size, big, np.int64), np.full(size, -1, np.int64)
    with rasterio.open(wsheds_tif) as ws, rasterio.open(dem_tif) as dem:
        rx, ry = abs(dem.res[0]), abs(dem.res[1])
        H, W = dem.height, dem.width
        top, step = dem.transform.f, dem.transform.e
        for r0 in range(0, H, block_rows):
            r1 = min(H, r0 + block_rows)
            ids = ws.read(1, window=Window(0, r0, W, r1 - r0))
            valid = ids > 0
            if ws.nodata is not None:
                valid &= ids != ws.nodata
            if not valid.any():
                continue
            p0, p1 = max(0, r0 - 1), min(H, r1 + 1)
            z = dem.read(1, window=Window(0, p0, W, p1 - p0)).astype("float64")
            if dem.nodata is not None:
                z[z == dem.nodata] = np.nan
            lat = top + (np.arange(r0, r1) + 0.5) * step
            m_lat, m_lon = meters_per_degree(lat)
            dx, dy = rx * m_lon, ry * m_lat
            off = r0 - p0
            gy = np.gradient(z, axis=0)[off:off + (r1 - r0)] / dy[:, None]
            gx = np.gradient(z, axis=1)[off:off + (r1 - r0)] / dx[:, None]
            slope, zc = np.hypot(gx, gy), z[off:off + (r1 - r0)]
            idv = ids[valid].astype(np.int64)
            n_cells += np.bincount(idv, minlength=size)
            area += np.bincount(idv, weights=((dx * dy)[:, None] * np.ones((1, W)))[valid], minlength=size)
            zv, sv = zc[valid], slope[valid]
            ok = ~np.isnan(zv)
            z_sum += np.bincount(idv[ok], weights=zv[ok], minlength=size)
            z_n += np.bincount(idv[ok], minlength=size)
            ok = ~np.isnan(sv)
            s_sum += np.bincount(idv[ok], weights=sv[ok], minlength=size)
            s_n += np.bincount(idv[ok], minlength=size)
            rr, cc = np.nonzero(valid)
            np.minimum.at(rmin, idv, rr + r0); np.maximum.at(rmax, idv, rr + r0)
            np.minimum.at(cmin, idv, cc); np.maximum.at(cmax, idv, cc)
    bounds = np.stack([rmin, rmax, cmin, cmax], axis=1)
    bounds[rmax < 0] = -1
    with np.errstate(invalid="ignore", divide="ignore"):
        return {"n_celdas": n_cells, "area_km2": area / 1e6, "elevacion_media_m": z_sum / z_n,
                "pendiente_media": s_sum / s_n, "bounds": bounds}


def _vectorize(wsheds_tif: Path, ids, bounds: np.ndarray) -> dict:
    import rasterio
    from rasterio.features import shapes
    from rasterio.windows import Window
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    out = {}
    with rasterio.open(wsheds_tif) as ws:
        for i in ids:
            r0, r1, c0, c1 = bounds[i]
            if r0 < 0:
                continue
            win = Window(c0, r0, c1 - c0 + 1, r1 - r0 + 1)
            m = ws.read(1, window=win) == i
            geoms = [shape(g) for g, v in shapes(m.astype("uint8"), mask=m,
                                                 transform=ws.window_transform(win)) if v == 1]
            out[i] = make_valid(unary_union(geoms))
    return out


def basin_attributes(outs: dict[str, Path], dem_tif: Path, stations, unit: str,
                     crs_out: str = "EPSG:6372"):
    import geopandas as gpd
    import pandas as pd
    import rasterio
    from pyproj import Geod

    stations = stations.reset_index(drop=True)
    snapped = gpd.read_file(outs["snapped"])
    n = len(stations)
    with rasterio.open(outs["watersheds_raster"]) as ws:
        crs_dem = ws.crs
        snapped = snapped.set_crs(crs_dem, allow_override=True)
        at_snap = np.array([v[0] for v in ws.sample([(p.x, p.y) for p in snapped.geometry])], dtype=np.int64)
    stats = _zonal_stats(outs["watersheds_raster"], dem_tif, n)
    polys = _vectorize(outs["watersheds_raster"], range(1, n + 1), stats["bounds"])
    geod = Geod(ellps="GRS80")
    rows = []
    for idx in range(n):
        wid, st = idx + 1, stations.iloc[idx]
        own = at_snap[idx] == wid and wid in polys
        shared = stations.iloc[at_snap[idx] - 1]["clave"] if (not own and 0 < at_snap[idx] <= n) else None
        sp = snapped.geometry.iloc[idx]
        _, _, snap_m = geod.inv(st["longitud"], st["latitud"], sp.x, sp.y)
        rows.append({"clave_estacion": str(st["clave"]), "unidad": unit, "watershed_id": wid,
                     "region_hidrologica_estacion": str(st.get("region_hidrologica", "")),
                     "tiene_poligono": bool(own), "salida_compartida_con": shared,
                     "snap_dist_m": round(float(snap_m), 1), "lon_ajustada": sp.x, "lat_ajustada": sp.y,
                     "n_celdas": int(stats["n_celdas"][wid]) if own else 0,
                     "area_km2": float(stats["area_km2"][wid]) if own else np.nan,
                     "elevacion_media_m": float(stats["elevacion_media_m"][wid]) if own else np.nan,
                     "pendiente_media": float(stats["pendiente_media"][wid]) if own else np.nan,
                     "geometry": polys.get(wid) if own else None})
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=crs_dem).to_crs(crs_out)

#!/usr/bin/env python
"""Etapa 06b — Mosaico + recorte del CEM por cuenca.

Toma los GeoTIFFs estatales del CEM 3.0 de INEGI (que SÍ se pueden descargar por
entidad federativa sin dibujar a mano) y produce un único CEM por cuenca,
recortado al bbox curado en conf/cuencas_piloto.yaml. Es el insumo que necesita
scripts/06_delineate_basins.py.

Flujo manual de descarga (una sola vez):
    1. Ir a https://www.inegi.org.mx/temas/relieve/continental/ (CEM 3.0).
    2. Descargar el CEM de cada entidad federativa que cubra alguna cuenca piloto
       (ver lista sugerida que imprime este script con --list-states).
    3. Guardar los TIFFs así:
         data/scratch/cem_estados/30m/<estado>.tif
         data/scratch/cem_estados/15m/<estado>.tif   # solo para Alta del Balsas
       (el nombre del archivo es libre; el script detecta intersección con bbox).
    4. Ejecutar:
         python scripts/06b_build_cem_per_basin.py
       Salida: data/raw/inegi/cem_<slug>.tif por cuenca.

Los TIFFs estatales son grandes (~200-400 MB c/u); por eso viven en
`data/scratch/`, que no entra a DVC ni al guardarraíl 08. Solo los recortados
por cuenca se versionan.

Uso:
    python scripts/06b_build_cem_per_basin.py [--list-states] [--overwrite]
"""
from __future__ import annotations

from pathlib import Path

import click
import rasterio
from rasterio.io import MemoryFile
from rasterio.mask import mask as rio_mask
from rasterio.merge import merge as rio_merge
from shapely.geometry import box, mapping

from hidroxai_mx.utils import RAW, get_logger, load_cuencas

log = get_logger("06b_cem")

# Carpeta scratch fuera de DVC para los CEM crudos por estado.
# Estructura esperada: data/scratch/<res>m/<archivo>.tif (p.ej. 15m/, 30m/).
SCRATCH = Path("data/scratch")

# Estados sugeridos por cuenca (referencia para descarga manual; no se valida).
ESTADOS_SUGERIDOS: dict[str, list[str]] = {
    "Cutzamala": ["Mexico", "Michoacan", "Guerrero"],
    "Lerma-Santiago": ["Jalisco", "Guanajuato", "Michoacan", "Queretaro",
                       "Mexico", "Aguascalientes", "Zacatecas", "SanLuisPotosi",
                       "Nayarit"],
    "Panuco": ["SanLuisPotosi", "Tamaulipas", "Hidalgo", "Veracruz",
               "Queretaro", "Mexico", "Puebla", "Tlaxcala"],
    "Alta del Balsas": ["Morelos", "Puebla", "Tlaxcala", "Mexico",
                        "Guerrero", "Oaxaca"],
}


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


def _tif_intersects_bbox(tif_path: Path, bbox: tuple[float, float, float, float]) -> bool:
    """True si el extent del TIFF intersecta el bbox dado (en EPSG:4326 lon/lat)."""
    with rasterio.open(tif_path) as src:
        l, b, r, t = src.bounds
        if src.crs and src.crs.to_epsg() != 4326:
            # bbox en lat/lon: reproyectar bounds del TIFF a 4326 para comparar.
            from rasterio.warp import transform_bounds
            l, b, r, t = transform_bounds(src.crs, "EPSG:4326", l, b, r, t, densify_pts=21)
    min_lon, min_lat, max_lon, max_lat = bbox
    return not (r < min_lon or l > max_lon or t < min_lat or b > max_lat)


def _find_cem_source_dir(resolucion_m: int) -> tuple[Path | None, int | None]:
    """Devuelve (subdir con TIFFs, resolución real). Hace fallback a otra resolución si la
    pedida no está disponible (por ejemplo: pediste 30m pero solo descargaron 15m).
    """
    preferred = SCRATCH / f"{resolucion_m}m"
    if preferred.exists() and any(preferred.glob("*.tif")):
        return preferred, resolucion_m
    if SCRATCH.exists():
        for sub in sorted(SCRATCH.iterdir()):
            if sub.is_dir() and any(sub.glob("*.tif")):
                # Espera nombres tipo "15m", "30m"; si no parsea, se devuelve sin resolución.
                actual = None
                name = sub.name.lower()
                if name.endswith("m") and name[:-1].isdigit():
                    actual = int(name[:-1])
                return sub, actual
    return None, None


def _build_cem_for_basin(
    nombre: str,
    bbox: tuple[float, float, float, float],
    resolucion_m: int,
    dest: Path,
    overwrite: bool,
) -> bool:
    """Mosaico + clip de los TIFFs estatales que intersectan `bbox`. Devuelve True si escribió."""
    if dest.exists() and not overwrite:
        log.info("%s: cache-hit %s", nombre, dest.name)
        return True

    subdir, actual_res = _find_cem_source_dir(resolucion_m)
    if subdir is None:
        log.warning("%s: no hay TIFFs en %s/. Sugeridos: %s",
                    nombre, SCRATCH, ", ".join(ESTADOS_SUGERIDOS.get(nombre, [])))
        return False
    if actual_res is not None and actual_res != resolucion_m:
        log.warning("%s: se pidió %sm pero solo hay %sm en %s/. Se usa %sm (sin resamplear).",
                    nombre, resolucion_m, actual_res, subdir, actual_res)

    candidatos = sorted(subdir.glob("*.tif"))

    usables = [p for p in candidatos if _tif_intersects_bbox(p, bbox)]
    if not usables:
        log.warning("%s: ninguno de los %d TIFFs en %s/ intersecta el bbox %s. "
                    "Verifica que descargaste los estados correctos: %s",
                    nombre, len(candidatos), subdir, bbox,
                    ", ".join(ESTADOS_SUGERIDOS.get(nombre, [])))
        return False

    import numpy as np
    log.info("%s: %d TIFF(s) usables de %d (resolución %sm)",
             nombre, len(usables), len(candidatos), actual_res or resolucion_m)
    sources = [rasterio.open(p) for p in usables]
    try:
        mosaic, out_transform = rio_merge(sources)
        meta = sources[0].meta.copy()
        # LZW predictor: 3 solo aplica a floats; 2 para enteros (delta).
        pred = 3 if np.issubdtype(np.dtype(meta["dtype"]), np.floating) else 2
        meta.update(
            driver="GTiff",
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=out_transform,
            compress="lzw",
            predictor=pred,
            tiled=True,
        )
    finally:
        for s in sources:
            s.close()

    # Recortar al bbox curado en memoria (evita bloqueos de archivo en Windows/GDrive).
    dest.parent.mkdir(parents=True, exist_ok=True)
    geom = [mapping(box(*bbox))]
    with MemoryFile() as memfile:
        with memfile.open(**meta) as dst:
            dst.write(mosaic)
        with memfile.open() as src:
            clipped, clipped_transform = rio_mask(src, geom, crop=True)
            clip_meta = src.meta.copy()
    pred = 3 if np.issubdtype(np.dtype(clip_meta["dtype"]), np.floating) else 2
    clip_meta.update(
        driver="GTiff",
        height=clipped.shape[1],
        width=clipped.shape[2],
        transform=clipped_transform,
        compress="lzw",
        predictor=pred,
        tiled=True,
    )
    with rasterio.open(dest, "w", **clip_meta) as dst:
        dst.write(clipped)

    size_mb = dest.stat().st_size / (1 << 20)
    log.info("%s: %s escrito (%.1f MB, %dx%d píxeles)",
             nombre, dest.name, size_mb, clipped.shape[2], clipped.shape[1])
    return True


@click.command()
@click.option("--list-states", is_flag=True,
              help="Solo imprime qué estados descargar por cuenca y sale.")
@click.option("--overwrite", is_flag=True, help="Re-generar aunque exista cem_<cuenca>.tif.")
def main(list_states: bool, overwrite: bool) -> None:
    cfg = load_cuencas()
    if list_states:
        log.info("Estados sugeridos por cuenca (descarga manual desde INEGI):")
        for c in cfg["cuencas_piloto"]:
            nombre = c["nombre"]
            res = c.get("cem_resolucion_m", 30)
            ests = ESTADOS_SUGERIDOS.get(nombre, [])
            log.info("  %-20s @ %sm — %s", nombre, res, ", ".join(ests))
        log.info("Guarda los TIFFs en %s/<resolución>m/<estado>.tif", SCRATCH)
        return

    out_dir = RAW / "inegi"
    out_dir.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    for c in cfg["cuencas_piloto"]:
        nombre = c["nombre"]
        bbox = c.get("bbox")
        if bbox is None:
            log.warning("%s: sin bbox en YAML, se omite.", nombre)
            continue
        res = c.get("cem_resolucion_m", 30)
        dest = out_dir / f"cem_{_slug(nombre)}.tif"
        if _build_cem_for_basin(nombre, tuple(bbox), res, dest, overwrite):
            n_ok += 1
    log.info("Listo: %d/%d cuencas con CEM listo en %s",
             n_ok, len(cfg["cuencas_piloto"]), out_dir)


if __name__ == "__main__":
    main()

"""Conector SMN: catálogos KMZ (climatológicas y EMAS) + EMAS.xlsx.

El servidor del SMN requiere User-Agent de navegador (lo inyecta download.fetch).
geopandas se importa de forma diferida para no exigirlo en tareas que no usan geo.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from ..utils import RAW, get_logger, load_sources
from ..utils.download import fetch

log = get_logger("io.smn")
SRC = load_sources()["fuentes"]["smn"]


def download_smn_catalogs(overwrite: bool = False) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for name, meta in SRC["recursos"].items():
        ext = meta["formato"]
        dest = RAW / "smn" / f"{name}.{ext}"
        out[name] = fetch(meta["url"], dest, headers=SRC.get("headers"), overwrite=overwrite)
    return out


def read_kmz_points(kmz_path: Path):
    """Extrae el doc.kml interno de un KMZ y lo lee como GeoDataFrame de puntos."""
    import geopandas as gpd  # import diferido

    kmz_path = Path(kmz_path)
    with zipfile.ZipFile(kmz_path) as zf:
        kml_name = next((n for n in zf.namelist() if n.lower().endswith(".kml")), None)
        if kml_name is None:
            raise ValueError(f"{kmz_path.name} no contiene un .kml")
        tmp = kmz_path.with_suffix(".kml")
        tmp.write_bytes(zf.read(kml_name))
    gdf = gpd.read_file(tmp, driver="KML")
    return gdf.set_crs("EPSG:4326", allow_override=True)


def read_emas_xlsx(xlsx_path: Path) -> pd.DataFrame:
    return pd.read_excel(xlsx_path)

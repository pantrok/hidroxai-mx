"""Conector INEGI: CEM 3.0 (GeoTIFF) y red hidrográfica SIATL (shapefile).

El CEM y SIATL se descargan por área geográfica (estado/cuenca) desde un portal
interactivo. Aquí se documenta el flujo; la selección concreta del recurso suele
requerir resolver el formulario del portal o usar el espejo de CONABIO.
"""
from __future__ import annotations

from pathlib import Path

from ..utils import RAW, get_logger, load_sources

log = get_logger("io.inegi")
SRC = load_sources()["fuentes"]


def cem_download_hint(estado: str, resolucion_m: int = 30) -> str:
    """Devuelve la URL del portal del CEM para descargar manual o semi-automáticamente."""
    portal = SRC["inegi_cem"]["portal"]
    if resolucion_m not in SRC["inegi_cem"]["resoluciones_m"]:
        raise ValueError(f"Resolución no disponible: {resolucion_m}")
    log.info(
        "CEM 3.0: descargar %s @ %sm desde %s (seleccionar 'Por área geográfica').",
        estado, resolucion_m, portal,
    )
    return portal


def siatl_download_hint(region_hidrologica: str) -> str:
    portal = SRC["inegi_siatl"]["portal"]
    log.info("SIATL: descargar capas de la RH '%s' desde %s", region_hidrologica, portal)
    return portal


def raw_dir() -> Path:
    d = RAW / "inegi"
    d.mkdir(parents=True, exist_ok=True)
    return d

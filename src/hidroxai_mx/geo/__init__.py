"""Capa geoespacial (parte de L3): delineación de cuencas y uniones espaciales.

Las dependencias pesadas (geopandas, rasterio, whitebox) se importan de forma
diferida dentro de cada función para no exigirlas en tareas que no las usan.
Instálalas con el extra:  pip install -e ".[geo]"
"""
from . import delineate, spatial  # noqa: F401

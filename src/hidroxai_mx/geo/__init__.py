"""Capa geoespacial (parte de L3): utilidades espaciales y vínculo con HydroRIVERS.

Las dependencias pesadas (geopandas, rasterio) se importan de forma diferida dentro de
cada función para no exigirlas en tareas que no las usan.
Instálalas con el extra:  pip install -e ".[geo]"
"""
from . import spatial  # noqa: F401

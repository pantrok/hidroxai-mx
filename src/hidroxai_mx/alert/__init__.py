"""Alertas difusas Mamdani del benchmark (protocolo, sección 6)."""
from .fuzzy import LEVELS, build_protocol_fis, level_index, station_percentile

__all__ = ["LEVELS", "build_protocol_fis", "level_index", "station_percentile"]

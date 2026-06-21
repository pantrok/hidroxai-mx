"""Esquema canónico del dataset y validación con pandera."""
from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema

CLAVE_REGEX = r"^[0-9A-Za-z]{1,8}$"  # claves del SIH (típ. 5 chars)

# Catálogo de estaciones (geometría/metadatos). Columnas opcionales salvo clave/coords.
catalog_schema = DataFrameSchema(
    {
        "clave": Column(str, pa.Check.str_matches(CLAVE_REGEX), nullable=False, unique=True),
        "nombre": Column(str, nullable=True, required=False),
        "latitud": Column(float, pa.Check.in_range(14.0, 33.0)),
        "longitud": Column(float, pa.Check.in_range(-118.5, -86.0)),
        "altitud": Column(float, pa.Check.ge(-50), nullable=True, required=False),
        "estado": Column(str, nullable=True, required=False),
        "municipio": Column(str, nullable=True, required=False),
        "region_hidrologica": Column(str, nullable=True, required=False),
        "cuenca": Column(str, nullable=True, required=False),
    },
    coerce=True,
    strict=False,
)

# Series temporales (una fila = estación-día). Solo clave/fecha/fuente/calidad obligatorias;
# las columnas de medición son opcionales (un archivo hidro no trae las de clima y viceversa).
series_schema = DataFrameSchema(
    {
        "clave_estacion": Column(str, pa.Check.str_matches(CLAVE_REGEX), nullable=False),
        "fecha": Column("datetime64[ns]", nullable=False),
        "gasto_medio_m3s": Column(float, pa.Check.ge(0), nullable=True, required=False),
        "nivel_m": Column(float, nullable=True, required=False),
        "precip_mm": Column(float, pa.Check.ge(0), nullable=True, required=False),
        "tmax_c": Column(float, pa.Check.in_range(-30, 60), nullable=True, required=False),
        "tmin_c": Column(float, pa.Check.in_range(-40, 50), nullable=True, required=False),
        "tmed_c": Column(float, pa.Check.in_range(-40, 55), nullable=True, required=False),
        "evap_mm": Column(float, pa.Check.ge(0), nullable=True, required=False),
        "fuente": Column(str, pa.Check.isin(["SIH", "BANDAS", "CLICOM", "EMAS"])),
        "calidad": Column(int, pa.Check.isin([0, 1, 2])),
    },
    coerce=True,
    strict=False,
)


def validate_series(df, lazy: bool = True):
    return series_schema.validate(df, lazy=lazy)


def validate_catalog(df, lazy: bool = True):
    return catalog_schema.validate(df, lazy=lazy)

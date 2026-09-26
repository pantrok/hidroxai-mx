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

def _nonneg_unless_flagged(col: str) -> pa.Check:
    """Valor ≥ 0 salvo que esté marcado como outlier (calidad == 2): los valores físicos
    imposibles se conservan marcados, no se eliminan."""
    def _check(df):
        if col not in df:
            return True
        return df[col].isna() | (df[col] >= 0) | (df["calidad"] == 2)
    return pa.Check(_check, name=f"{col}_ge_0_salvo_calidad_2", element_wise=False)


# Series temporales (una fila = estación-día). Solo clave/fecha/fuente/calidad obligatorias;
# las columnas de medición son opcionales (un archivo hidro no trae las de clima y viceversa).
series_schema = DataFrameSchema(
    {
        "clave_estacion": Column(str, pa.Check.str_matches(CLAVE_REGEX), nullable=False),
        "fecha": Column("datetime64[ns]", nullable=False),
        "gasto_medio_m3s": Column(float, nullable=True, required=False),
        "nivel_m": Column(float, nullable=True, required=False),
        "precip_mm": Column(float, nullable=True, required=False),
        "tmax_c": Column(float, pa.Check.in_range(-30, 60), nullable=True, required=False),
        "tmin_c": Column(float, pa.Check.in_range(-40, 50), nullable=True, required=False),
        "tmed_c": Column(float, pa.Check.in_range(-40, 55), nullable=True, required=False),
        "evap_mm": Column(float, pa.Check.ge(0), nullable=True, required=False),
        "fuente": Column(str, pa.Check.isin(["SIH", "BANDAS", "CLICOM", "EMAS"])),
        "calidad": Column(int, pa.Check.isin([0, 1, 2])),
    },
    checks=[_nonneg_unless_flagged("gasto_medio_m3s"), _nonneg_unless_flagged("precip_mm")],
    coerce=True,
    strict=False,
)


def validate_series(df, lazy: bool = True):
    return series_schema.validate(df, lazy=lazy)


def validation_report(df) -> dict:
    """Valida contra ``series_schema`` y resume las fallas por columna y regla.

    Devuelve {"valido": bool, "filas": n, "fallas": [{columna, regla, n_filas}]}. Las
    fallas no bloquean la persistencia (los valores crudos fuera de rango se conservan),
    pero quedan registradas para el usuario.
    """
    from pandera.errors import SchemaErrors

    try:
        validate_series(df, lazy=True)
        return {"valido": True, "filas": int(len(df)), "fallas": []}
    except SchemaErrors as exc:
        fc = exc.failure_cases
        grp = fc.groupby(["column", "check"], dropna=False).size().reset_index(name="n_filas")
        return {"valido": False, "filas": int(len(df)),
                "fallas": [{"columna": None if r.column != r.column else str(r.column),
                            "regla": str(r.check), "n_filas": int(r.n_filas)}
                           for r in grp.itertuples()]}


def validate_catalog(df, lazy: bool = True):
    return catalog_schema.validate(df, lazy=lazy)

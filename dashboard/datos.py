"""Lectura de los datos precalculados del dashboard (``dashboard/data/``).

Los genera ``scripts/dash_01_build_data.py`` a partir de los resultados del benchmark, sin
recalcular nada. Las rutas se resuelven desde este archivo, así que funcionan igual con
``streamlit run dashboard/app.py`` que en el navegador con stlite.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parent / "data"

MODELOS = {"persistencia": "Persistencia", "arima": "ARIMA", "xgboost": "XGBoost", "tcn": "TCN",
           "convnext": "ConvNeXt-1D", "patchtst": "PatchTST", "lstm": "LSTM (descriptivo)"}
EXPLICABLES = ["xgboost", "tcn", "convnext", "patchtst", "lstm"]
CANALES = {"gasto_medio_m3s": "gasto", "gasto_medio_m3s_ma7": "media 7 d", "gasto_medio_m3s_ma30": "media 30 d",
           "precip_idw_mm": "precipitación IDW", "doy_sin": "día del año (sen)", "doy_cos": "día del año (cos)"}
CUENCAS = ["Lerma–Santiago", "Pánuco", "Alta del Balsas", "Cutzamala"]
HORIZONTES = [1, 7, 14]
NIVELES = ["normal", "vigilancia", "alerta", "emergencia"]
COLORES_NIVEL = ["#4DAF4A", "#FFD92F", "#FF7F00", "#E41A1C"]
AVISO = "Pronósticos retrospectivos sobre 2023–2025 con fines de investigación; no es un sistema de alerta operativo."


@st.cache_data(show_spinner=False)
def estaciones() -> pd.DataFrame:
    e = pd.read_csv(DATA / "estaciones.csv", dtype={"clave": str})
    e["etiqueta"] = e["clave"] + " · " + e["nombre"] + " (" + e["cuenca"] + ")"
    return e.sort_values(["cuenca", "clave"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def metricas_estacion() -> pd.DataFrame:
    return pd.read_csv(DATA / "metricas_estacion.csv", dtype={"clave": str})


@st.cache_data(show_spinner=False)
def metricas_cuenca() -> pd.DataFrame:
    return pd.read_csv(DATA / "metricas_cuenca.csv")


@st.cache_data(show_spinner=False)
def pronosticos() -> pd.DataFrame:
    return pd.read_parquet(DATA / "pronosticos.parquet")


@st.cache_data(show_spinner=False)
def alertas() -> pd.DataFrame:
    return pd.read_parquet(DATA / "alertas.parquet")


@st.cache_data(show_spinner=False)
def umbrales() -> pd.DataFrame:
    return pd.read_csv(DATA / "umbrales.csv", dtype={"clave": str}, float_precision="round_trip").set_index("clave")


@st.cache_data(show_spinner=False)
def importancia() -> pd.DataFrame:
    return pd.read_parquet(DATA / "importancia.parquet")


@st.cache_data(show_spinner=False)
def concordancia() -> pd.DataFrame:
    return pd.read_csv(DATA / "concordancia.csv")


@st.cache_data(show_spinner=False)
def contingencia() -> pd.DataFrame:
    return pd.read_csv(DATA / "contingencia.csv", dtype={"clave": str})


@st.cache_data(show_spinner=False)
def resumen_alertas() -> pd.DataFrame:
    return pd.read_csv(DATA / "resumen_alertas.csv")


@st.cache_data(show_spinner=False)
def contornos() -> dict:
    return json.loads((DATA / "contornos.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def meta() -> dict:
    return json.loads((DATA / "meta.json").read_text(encoding="utf-8"))


def puntajes(fila) -> dict:
    """POD, FAR y CSI de una tabla de contingencia (aciertos, fallos, falsas alarmas)."""
    a, f, fa = int(fila["aciertos"]), int(fila["fallos"]), int(fila["falsas"])
    return {"POD": a / (a + f) if a + f else float("nan"),
            "FAR": fa / (a + fa) if a + fa else float("nan"),
            "CSI": a / (a + f + fa) if a + f + fa else float("nan")}

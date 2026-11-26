"""Dashboard de HidroXAI-MX: resultados retrospectivos del benchmark de pronóstico explicable.

Streamlit puro. En local: ``streamlit run dashboard/app.py``. En GitHub Pages corre en el
navegador con stlite (``dashboard/index.html``). Lee ``dashboard/data/``, que genera
``scripts/dash_01_build_data.py`` sin recalcular resultados.

Solo se dibuja la vista elegida, para que la carga inicial y cada interacción sean rápidas.
"""
import datos
import streamlit as st
import vistas

VISTAS = {"Mapa": vistas.mapa, "Estación": vistas.estacion, "Explicabilidad": vistas.explicabilidad,
          "Alertas": vistas.alertas, "Acerca de": vistas.acerca}

st.set_page_config(page_title="HidroXAI-MX · dashboard", layout="wide")
st.title("HidroXAI-MX · pronósticos retrospectivos de gasto")
st.warning(datos.AVISO)

vista = st.segmented_control("Vista", list(VISTAS), default="Mapa", key="vista", label_visibility="collapsed")
VISTAS[vista or "Mapa"]()

st.caption("IPN · Convocatoria PICDT2026 · proyecto IND-2026-0335. Datos: CONAGUA (SIH), INEGI, HydroSHEDS; "
           "contornos: CONABIO. " + datos.AVISO)

"""Dashboard de HidroXAI-MX: resultados retrospectivos del benchmark de pronóstico explicable.

Streamlit puro. En local: ``streamlit run dashboard/app.py``. En GitHub Pages corre en el
navegador con stlite (``dashboard/index.html``). Lee ``dashboard/data/``, que genera
``scripts/dash_01_build_data.py`` sin recalcular resultados.
"""
import datos
import streamlit as st
import vistas

st.set_page_config(page_title="HidroXAI-MX · dashboard", layout="wide")
st.title("HidroXAI-MX · pronósticos retrospectivos de gasto")
st.warning(datos.AVISO)

pestanas = st.tabs(["Mapa", "Estación", "Explicabilidad", "Alertas", "Acerca de"])
with pestanas[0]:
    vistas.mapa()
with pestanas[1]:
    vistas.estacion()
with pestanas[2]:
    vistas.explicabilidad()
with pestanas[3]:
    vistas.alertas()
with pestanas[4]:
    vistas.acerca()

st.caption("IPN · Convocatoria PICDT2026 · proyecto IND-2026-0335. Datos: CONAGUA (SIH), INEGI, HydroSHEDS; "
           "contornos: CONABIO. " + datos.AVISO)

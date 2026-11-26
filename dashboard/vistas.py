"""Vistas del dashboard. Muestran resultados existentes del benchmark; no recalculan nada."""
from __future__ import annotations

import datos as D
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

MAPA = {"style": "carto-positron", "center": {"lat": 20.6, "lon": -100.4}, "zoom": 5.2}
FUENTE_CONTORNOS = ("Contornos: regiones hidrológicas 12, 18 y 26 y cuenca del Río Cutzamala "
                    "(CNA, 1998, 1:250 000; distribuidos por CONABIO). Mapa base: © OpenStreetMap, © CARTO.")


def _selector_estacion(clave_widget: str) -> str:
    est = D.estaciones()
    etiqueta = st.selectbox("Estación", est["etiqueta"], key=clave_widget)
    return etiqueta.split(" · ")[0]


def _diario(g: pd.DataFrame) -> pd.DataFrame:
    """Reindexa a días consecutivos para que las líneas se corten donde no hay pronóstico."""
    g = g.set_index("fecha").sort_index()
    return g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))


# --------------------------------------------------------------------------- 1. mapa
def mapa() -> None:
    c1, c2 = st.columns([3, 1])
    modelo = c1.radio("Modelo", list(D.MODELOS), format_func=D.MODELOS.get, horizontal=True, key="mapa_modelo")
    h = c2.radio("Horizonte (días)", D.HORIZONTES, horizontal=True, key="mapa_h")
    met = D.metricas_estacion()
    m = met[(met["modelo"] == modelo) & (met["h"] == h)][["clave", "nse", "kge", "ss"]]
    d = D.estaciones().merge(m, on="clave", how="left")
    texto = (d["clave"] + " · " + d["nombre"] + "<br>" + d["cuenca"] + " · unidad " + d["unidad_piloto"].fillna("—")
             + "<br>NSE " + d["nse"].map("{:.3f}".format) + " · KGE " + d["kge"].map("{:.3f}".format)
             + " · SS " + d["ss"].map("{:.3f}".format))
    fig = go.Figure()
    for nombre, xy in D.contornos().items():
        fig.add_trace(go.Scattermap(lon=xy["lon"], lat=xy["lat"], mode="lines", line={"width": 1.3, "color": "#666"},
                                    name=nombre, hoverinfo="name", showlegend=False))
    fig.add_trace(go.Scattermap(
        lon=d["longitud"], lat=d["latitud"], mode="markers", text=texto, hovertemplate="%{text}<extra></extra>",
        marker={"size": 11, "color": d["nse"].clip(-1, 1), "colorscale": "RdYlBu", "cmin": -1, "cmax": 1,
                "colorbar": {"title": "NSE"}}, showlegend=False))
    fig.update_layout(map=MAPA, height=560, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(fig, width="stretch")
    st.caption(f"{len(d)} estaciones evaluables. Color: NSE de {D.MODELOS[modelo]} a {h} día(s), recortado a "
               f"[−1, 1]; el valor exacto aparece al pasar el cursor. {FUENTE_CONTORNOS}")
    res = D.metricas_cuenca()
    r = res[(res["modelo"] == modelo) & (res["h"] == h)].copy()
    r["grupo"] = r["grupo"].replace({"agregado": "Todas las cuencas"})
    st.markdown("**Mediana por cuenca** (`rq1_summary.csv`; LSTM: `mese/lstm_skill.csv`)")
    st.dataframe(r.rename(columns={"grupo": "cuenca", "nse_mediana": "NSE", "kge_mediana": "KGE",
                                   "ss_mediana": "skill score", "rmse_mediana": "RMSE (m³/s)"})
                 [["cuenca", "estaciones", "NSE", "KGE", "skill score", "RMSE (m³/s)"]].round(3),
                 hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 2. estación
def estacion() -> None:
    c1, c2, c3 = st.columns([2.2, 1.2, 1])
    with c1:
        clave = _selector_estacion("est_estacion")
    opciones = [m for m in D.MODELOS if m != "persistencia"]
    modelo = c2.selectbox("Modelo", opciones, index=opciones.index("xgboost"), format_func=D.MODELOS.get,
                          key="est_modelo")
    h = c3.radio("Horizonte (días)", D.HORIZONTES, horizontal=True, key="est_h")
    p = D.pronosticos()
    g = _diario(p[(p["clave"] == clave) & (p["h"] == h)])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=g.index, y=g["observado"], name="observado", line={"color": "black", "width": 1.2}))
    if st.checkbox("Mostrar persistencia", value=True, key="est_pers"):
        fig.add_trace(go.Scatter(x=g.index, y=g["persistencia"], name="persistencia",
                                 line={"color": "#999", "width": 1, "dash": "dot"}))
    fig.add_trace(go.Scatter(x=g.index, y=g[modelo], name=D.MODELOS[modelo], line={"color": "#0072B2", "width": 1.2}))
    fig.update_layout(height=430, margin={"l": 10, "r": 10, "t": 30, "b": 10}, yaxis_title="m³/s",
                      legend={"orientation": "h", "y": 1.08}, hovermode="x unified",
                      xaxis={"rangeslider": {"visible": True}})
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Pronóstico de gasto a {h} día(s) contra lo observado, en la fecha objetivo. Promedio de las tres "
               "semillas de la configuración elegida, el mismo con el que se calcularon las métricas.")
    met = D.metricas_estacion()
    t = met[(met["clave"] == clave) & (met["h"] == h)].set_index("modelo").reindex(list(D.MODELOS)).reset_index()
    t["modelo"] = t["modelo"].map(D.MODELOS)
    st.markdown("**Métricas de la estación en el periodo de prueba** (`rq1_station_metrics.csv`; "
                "LSTM: `mese/lstm_station_metrics.csv`)")
    st.dataframe(t.rename(columns={"n": "días", "nse": "NSE", "kge": "KGE", "rmse": "RMSE (m³/s)", "ss": "skill score"})
                 [["modelo", "días", "NSE", "KGE", "RMSE (m³/s)", "skill score"]].round(3),
                 hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 3. explicabilidad
def explicabilidad() -> None:
    c1, c2, c3 = st.columns([1.3, 2.4, 1])
    cuenca = c1.selectbox("Cuenca", D.CUENCAS, key="xai_cuenca")
    modelo = c2.radio("Modelo", D.EXPLICABLES, format_func=D.MODELOS.get, horizontal=True, key="xai_modelo")
    h = c3.radio("Horizonte (días)", D.HORIZONTES, horizontal=True, key="xai_h")
    imp = D.importancia()
    d = imp[(imp["cuenca"] == cuenca) & (imp["modelo"] == modelo) & (imp["h"] == h)]
    if d.empty:
        st.info("No hay mapa para esta combinación.")
    else:
        z = (d.pivot_table(index="canal", columns="rezago_ventana", values="importancia")
             .reindex(list(D.CANALES)).sort_index(axis=1, ascending=False))
        fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=[-int(r) for r in z.columns], y=[D.CANALES[c] for c in z.index],
                                   colorscale="Viridis", colorbar={"title": "importancia"},
                                   hovertemplate="día %{x}<br>%{y}<br>%{z:.4f}<extra></extra>"))
        fig.update_layout(height=330, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                          xaxis_title="día de la ventana (0 = día de emisión)", yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, width="stretch")
        metodo = "TreeSHAP" if modelo == "xgboost" else "Integrated Gradients"
        st.caption(f"{D.MODELOS[modelo]}, {cuenca}, {h} día(s): {metodo}. Importancia = |atribución| normalizada a "
                   "suma 1 por ventana y promediada (`rq2_importance.csv`; LSTM: `mese/lstm_importance.csv`).")

    st.markdown("**Acuerdo entre modelos y techo de semillas** (Spearman sobre los 180 valores del mapa)")
    c = D.concordancia()
    c = c[(c["cuenca"] == cuenca) & (c["h"] == h)]
    techo = c[c["tipo"] == "entre_semillas"].groupby("modelo_a")["valor"].median()
    pares = (c[c["tipo"] == "entre_modelos"].groupby(["modelo_a", "modelo_b"], as_index=False)["valor"].median())
    col1, col2 = st.columns(2)
    if not techo.empty:
        t = techo.reindex([m for m in D.EXPLICABLES if m in techo.index])
        fig = go.Figure(go.Bar(x=[D.MODELOS[m] for m in t.index], y=t.to_numpy(), marker_color="#0072B2",
                               hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
        fig.update_layout(height=300, margin={"l": 10, "r": 10, "t": 30, "b": 10}, yaxis={"range": [0, 1]},
                          title={"text": "Techo: misma arquitectura, otra semilla", "font": {"size": 13}})
        col1.plotly_chart(fig, width="stretch")
    if not pares.empty:
        pares["techo menor"] = [min(techo.get(a, float("nan")), techo.get(b, float("nan")))
                                for a, b in zip(pares["modelo_a"], pares["modelo_b"], strict=True)]
        pares["modelo_a"] = pares["modelo_a"].map(D.MODELOS)
        pares["modelo_b"] = pares["modelo_b"].map(D.MODELOS)
        col2.dataframe(pares.rename(columns={"modelo_a": "modelo A", "modelo_b": "modelo B", "valor": "Spearman"})
                       .round(3), hide_index=True, width="stretch")
    st.caption("El acuerdo entre dos arquitecturas solo es informativo si se compara con el techo: el acuerdo de una "
               "misma arquitectura entrenada con otra semilla (`rev_rr2_medidas.csv`; LSTM: "
               "`mese/lstm_concordance.csv`).")


# --------------------------------------------------------------------------- 4. alertas
def alertas() -> None:
    c1, c2 = st.columns([3, 1])
    with c1:
        clave = _selector_estacion("al_estacion")
    h = c2.radio("Horizonte (días)", D.HORIZONTES, horizontal=True, key="al_h")
    a = D.alertas()
    g = _diario(a[(a["clave"] == clave) & (a["h"] == h)])
    u = D.umbrales().loc[clave]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.66, 0.34], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=g.index, y=g["observado"], name="observado", line={"color": "black", "width": 1.1}),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=g.index, y=g["ensamble"], name="media del ensamble", line={"color": "#0072B2", "width": 1}),
                  row=1, col=1)
    for e, color in (("p90", "#E69F00"), ("p99", "#D55E00")):
        fig.add_hline(y=float(u[e]), line={"color": color, "dash": "dash", "width": 1}, row=1, col=1,
                      annotation_text=f"{e.upper()} entrenamiento", annotation_position="top left")
    ok = g["nivel"].notna()
    niveles = g.loc[ok, "nivel"].astype(int)
    fig.add_trace(go.Scatter(x=g.index[ok], y=niveles, mode="markers", name="nivel difuso",
                             marker={"size": 5, "color": [D.COLORES_NIVEL[n] for n in niveles]},
                             text=[D.NIVELES[n] for n in niveles], hovertemplate="%{x|%Y-%m-%d}: %{text}<extra></extra>"),
                  row=2, col=1)
    for e, y, simbolo in (("p90", 3.45, "line-ns-open"), ("p99", 3.8, "line-ns-open")):
        ev = g["observado"] > float(u[e])
        fig.add_trace(go.Scatter(x=g.index[ev], y=[y] * int(ev.sum()), mode="markers", name=f"evento {e.upper()} observado",
                                 marker={"symbol": simbolo, "size": 9, "color": "#D55E00" if e == "p99" else "#333"}),
                      row=2, col=1)
    fig.update_yaxes(title_text="m³/s", row=1, col=1)
    fig.update_yaxes(tickvals=[0, 1, 2, 3], ticktext=D.NIVELES, range=[-0.5, 4.0], row=2, col=1)
    fig.update_layout(height=540, margin={"l": 10, "r": 10, "t": 70, "b": 10},
                      legend={"orientation": "h", "y": 1.13, "x": 0})
    st.plotly_chart(fig, width="stretch")
    st.caption("Nivel del sistema Mamdani del benchmark (percentil y dispersión del ensamble de 12 miembros). Un evento "
               "es un gasto observado mayor que el percentil 90 o 99 del entrenamiento de la estación. El sistema difuso "
               "alerta un evento P90 con nivel alerta o mayor y un P99 con emergencia; el umbral simple, cuando el "
               "percentil de la media del ensamble pasa de 0.90 o 0.99.")
    cont = D.contingencia()
    s = cont[(cont["clave"] == clave) & (cont["h"] == h)].copy()
    s = pd.concat([s.reset_index(drop=True), pd.DataFrame([D.puntajes(r) for _, r in s.iterrows()])], axis=1)
    for c in ("POD", "FAR", "CSI"):                 # sin eventos o sin alertas el puntaje no está definido
        s[c] = s[c].map(lambda v: "—" if pd.isna(v) else f"{v:.3f}")
    col1, col2 = st.columns(2)
    col1.markdown("**Esta estación** (`rq3_contingency.csv`)")
    col1.dataframe(s[["evento", "metodo", "aciertos", "fallos", "falsas", "POD", "FAR", "CSI"]].round(3),
                   hide_index=True, width="stretch")
    cuenca = D.estaciones().set_index("clave").loc[clave, "cuenca"]
    r = D.resumen_alertas()
    r = r[(r["grupo"] == cuenca) & (r["h"] == h)]
    filas = [{"evento": x["evento"], "método": met, "estaciones": x["estaciones"], "POD": x[f"{met}_pod"],
              "FAR": x[f"{met}_far"], "CSI": x[f"{met}_csi"]} for _, x in r.iterrows() for met in ("difuso", "umbral")]
    col2.markdown(f"**{cuenca}** (`rq3_summary.csv`)")
    col2.dataframe(pd.DataFrame(filas).round(3), hide_index=True, width="stretch")


# --------------------------------------------------------------------------- 5. acerca de
def acerca() -> None:
    m = D.meta()
    st.markdown(f"""
### Qué muestra

Los resultados del benchmark de pronóstico explicable de HidroXAI-MX sobre el periodo de prueba
({m["periodo_prueba"][0]} a {m["periodo_prueba"][1]}): pronósticos de gasto a 1, 7 y 14 días en
{m["estaciones_evaluables"]} estaciones evaluables de cuatro cuencas piloto, sus métricas, los mapas de
explicabilidad y las alertas difusas. **No recalcula nada**: los datos salen de los archivos de resultados
del benchmark (tag `{m["benchmark_tag"]}`).

### Metodología, en breve

- **Datos:** dataset Hidro-MX, series diarias de gasto y precipitación del SIH de CONAGUA. Ventanas de 30 días
  con 6 canales; entrenamiento 2010–2020, validación 2021–2022, prueba 2023 – 3 sep 2025.
- **Modelos:** persistencia, ARIMA, XGBoost, TCN, ConvNeXt-1D y PatchTST, con protocolo congelado antes de
  entrenar; el LSTM se agregó después como modelo descriptivo. XGBoost y las redes se promedian sobre tres
  semillas.
- **Explicabilidad:** TreeSHAP (XGBoost) e Integrated Gradients (redes), comparados con el acuerdo entre semillas.
- **Alertas:** sistema difuso tipo Mamdani con dos entradas (percentil y dispersión del ensamble) y cuatro niveles,
  comparado con un umbral simple mediante POD, FAR y CSI.

### Créditos

Instituto Politécnico Nacional (IPN) · Convocatoria PICDT2026 · proyecto **IND-2026-0335**.
Datos: **CONAGUA** (Sistema de Información Hidrológica), **INEGI** y **HydroSHEDS** (HydroRIVERS v1.0).
Contornos del mapa: CNA (1998), *Cuencas hidrológicas* y *Regiones hidrológicas*, 1:250 000, distribuidos por
**CONABIO**. Mapa base: © OpenStreetMap, © CARTO.

### Licencias

Código: MIT. Datos derivados: CC BY 4.0. Los contornos de CONABIO se usan con su licencia CC BY-NC 2.5 MX.

### Citar

- Artículo de datos: [10.1016/j.dib.2026.113442](https://doi.org/{m["articulo_doi"]}) (*Data in Brief*, 69, 113442).
- Dataset Hidro-MX: [{m["dataset"]["doi"]}](https://doi.org/{m["dataset"]["doi"]}); todas las versiones:
  [{m["dataset"]["doi_concepto"]}](https://doi.org/{m["dataset"]["doi_concepto"]}).

[Documentación](https://pantrok.github.io/hidroxai-mx/) ·
[Código](https://github.com/pantrok/hidroxai-mx) ·
Datos del dashboard generados el {m["generado"]} con `{m["script"]}`.
""")

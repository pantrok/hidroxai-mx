#!/usr/bin/env python
"""Benchmark XAI · MESE (T3 y T4): figuras para Modeling Earth Systems and Environment.

Reutiliza el estilo y las funciones de `xai_12_figures_esi.py` (sin modificarlo): tamaño final de
84 o 174 mm, Arial 8 pt (≥ 7 pt), paleta Okabe-Ito con un marcador fijo por modelo o grupo, sin
transparencias. Escribe en results/xai_benchmark/figures_mese/:
  Fig1.pdf … Fig6.pdf          texto principal
  ESM_FigS1.pdf …              Online Resource 1 (numeración propia)
  (cada una también en EPS, TIFF-LZW y PNG de revisión) y figures_mese.csv

Fig. 2 (T4) es un mapa propio, distinto del de Data in Brief: solo las estaciones modeladas
(las 91 evaluables con símbolo lleno y las no evaluables huecas), color por grupo conectado de
HydroRIVERS (los 23 grupos de RR-3; las aisladas en gris), marcador por régimen (RR-6),
contornos mínimos de cuenca, EPSG:6372, escala y norte. Sin regiones hidrológicas de contexto
ni cajas de unidades.

Uso:  python scripts/xai_17_figures_mese.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from hidroxai_mx.models import data as D
from hidroxai_mx.utils import PROCESSED, ROOT, get_logger

log = get_logger("xai_17")


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ESI = _load_script("xai_12_figures_esi")
plt = ESI.plt
OUT = ESI.OUT
MESE = OUT / "mese"
FIGM = OUT / "figures_mese"
MM, W1, W2 = ESI.MM, ESI.W1, ESI.W2
HS, LEARNED, DEEP = ESI.HS, ESI.LEARNED, ESI.DEEP
STYLE = ESI.STYLE
STYLE["lstm"] = {"color": "#009E73", "marker": "P", "label": "LSTM (descriptive)"}
# Salidas de T1.c (xai_18); si aún no existen, las figuras salen sin el LSTM.
LSTM_FILES = {"skill": "lstm_skill.csv", "delta": "lstm_vs_xgboost.csv", "imp": "lstm_importance.csv",
              "conc": "lstm_concordance.csv", "wf": "lstm_walkforward.csv"}
# Figuras de xai_12 y xai_14 que pasan al Online Resource 1 con numeración propia.
ESM_NAMES = {"fig8_rq3_fuzzy_decision_surface": "ESM_FigS1", "fig6_rq2_precip_lag_profiles": "ESM_FigS3",
             "fig11_drought_2023": "ESM_FigS5", "fig2_rq1_nse_by_basin": "ESM_FigS6",
             "fig9_rq3_alert_timeline_example": "ESM_FigS7", "figS3_rr1_alert_ablations": "ESM_FigS8",
             "figS4_rr2_noise_ceiling": "ESM_FigS9", "figS5_rr6_nse_by_regime": "ESM_FigS10"}
CONTENT = {
    "Fig1": "Flujo del estudio (datos, RQ1–RQ3); el LSTM descriptivo con borde discontinuo, fuera del ensamble",
    "Fig2":"Mapa: estaciones modeladas por grupo conectado (HydroRIVERS) y régimen",
    "Fig3": "Habilidad en la partición principal: NSE (mediana, IQR) y SS contra persistencia (mediana, IC 95 %)",
    "Fig4": "Mapas de importancia (variable × día de entrada), cuencas con ≥ 8 estaciones",
    "Fig5": "Acuerdo entre explicaciones y techo de ruido entre semillas y mitades (Spearman, 180 importancias)",
    "Fig6": "Alertas: CSI difuso y umbral (P90, P99) y descomposición del ΔCSI P90 (F − T = A + B; C, D)",
    "ESM_FigS1": "Superficie de decisión del sistema Mamdani",
    "ESM_FigS2": "ΔNSE contra XGBoost (mediana, IC 95 %)",
    "ESM_FigS3": "Perfiles de importancia de la precipitación por rezago respecto al objetivo",
    "ESM_FigS4": "Walk-forward anual 2021–2025",
    "ESM_FigS5": "Sequía de 2023: anomalía de precipitación y razón de gasto por cuenca",
    "ESM_FigS6": "NSE mediana por cuenca, modelo y horizonte",
    "ESM_FigS7": "Ejemplo de serie con niveles de alerta",
    "ESM_FigS8": "Ablaciones de las alertas (contrastes A–D) y valor económico relativo",
    "ESM_FigS9": "Techo de ruido con las cinco medidas de acuerdo",
    "ESM_FigS10": "NSE por régimen (fracción de días con gasto cero)",
}
_orig_save = ESI.save


def _save(fig, name: str, width_mm: float, **kw) -> None:
    _orig_save(fig, ESM_NAMES.get(name, name), width_mm, **kw)


ESI.save = _save


def _lstm(key: str) -> pd.DataFrame | None:
    p = MESE / LSTM_FILES[key]
    return pd.read_csv(p) if p.exists() else None


def mst(m: str, **kw) -> dict:
    """Estilo de marcador; el LSTM (descriptivo) va con relleno blanco."""
    s = ESI.mstyle(m, **kw)
    if m == "lstm":
        s.setdefault("mfc", "white")
    return s

# Okabe-Ito (8 colores) para los grupos conectados con más de una estación, del mayor al menor.
GROUP_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442", "#000000"]
ISOLATED = "#A6A6A6"
REGIME_MARKER = {"perenne": "o", "intermitente": "^"}
REGIME_LABEL = {"perenne": "Perennial", "intermitente": "Intermittent (> 5 % zero-flow days)"}


def _stations() -> pd.DataFrame:
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    modeled = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    grp = pd.read_csv(OUT / "rev_rr3_grupos.csv", dtype={"clave": str}).set_index("clave")["grupo"]
    reg = pd.read_csv(OUT / "tables" / "S1_descriptores.csv", dtype={"clave": str}).set_index("clave")["regimen"]
    st = sel[sel["clave"].isin(modeled)][["clave", "latitud", "longitud"]].copy()
    st["cuenca"] = st["clave"].map(basin_of)
    st["evaluable"] = st["clave"].isin(grp.index)
    st["grupo"] = st["clave"].map(grp)
    st["regimen"] = st["clave"].map(reg)
    assert len(st) == len(modeled) and st["evaluable"].sum() == len(grp) and st.loc[st["evaluable"], "regimen"].notna().all()
    return st


def fig_map(layers) -> dict:
    """Fig. 2: estaciones modeladas por grupo conectado y régimen (T4)."""
    import geopandas as gpd
    rh, cutz, states, _, crs = layers
    st = _stations()
    nation = states.dissolve()
    pts = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st["longitud"], st["latitud"]), crs="EPSG:4326").to_crs(crs)
    ev = pts[pts["evaluable"]]
    sizes = ev["grupo"].value_counts()
    multi = sizes[sizes > 1].sort_values(ascending=False, kind="stable")
    assert len(multi) <= len(GROUP_COLORS)
    letter = {g: chr(65 + i) for i, g in enumerate(multi.index)}
    color = {g: GROUP_COLORS[i] for i, g in enumerate(multi.index)}

    fig, ax = plt.subplots(figsize=(W2, 150 * MM))
    nation.plot(ax=ax, color="#F7F7F7", edgecolor="none")
    states.boundary.plot(ax=ax, color="#D0D0D0", lw=0.3)
    nation.boundary.plot(ax=ax, color="#7F7F7F", lw=0.5)
    rh[rh["clave_rh"].isin([12, 26])].boundary.plot(ax=ax, color="#4D4D4D", lw=0.8)
    cutz.boundary.plot(ax=ax, color="#4D4D4D", lw=0.8, ls="-.")
    for reg, mk in REGIME_MARKER.items():
        iso = ev[(ev["regimen"] == reg) & ~ev["grupo"].isin(multi.index)]
        ax.scatter(iso.geometry.x, iso.geometry.y, s=16, marker=mk, color=ISOLATED, edgecolor="#4D4D4D", lw=0.35,
                   zorder=4)
        for g in multi.index:
            sub = ev[(ev["regimen"] == reg) & (ev["grupo"] == g)]
            ax.scatter(sub.geometry.x, sub.geometry.y, s=18, marker=mk, color=color[g], edgecolor="black", lw=0.35,
                       zorder=5)
    ne = pts[~pts["evaluable"]]
    ax.scatter(ne.geometry.x, ne.geometry.y, s=18, marker="o", facecolor="white", edgecolor="black", lw=0.8, zorder=5)

    xmin, ymin, xmax, ymax = pd.concat([rh[rh["clave_rh"].isin([12, 26])].geometry, cutz.geometry,
                                        pts.geometry]).total_bounds
    pad = 40_000
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - 2.2 * pad, ymax + pad)
    halo = [ESI.pe.withStroke(linewidth=2.2, foreground="white")]
    for k, name, dx in ((12, "Lerma–Santiago", 0.0), (26, "Pánuco", -40_000)):
        x0g, _, x1g, y1g = rh[rh["clave_rh"] == k].total_bounds
        ax.text((x0g + x1g) / 2 + dx, y1g + 12_000, name, ha="center", va="bottom", fontsize=8, path_effects=halo)
    cx, cy = cutz.geometry.iloc[0].representative_point().coords[0]
    ax.text(cx - 75_000, cy - 30_000, "Cutzamala", ha="right", va="center", fontsize=8, path_effects=halo)
    ab = pts[pts["cuenca"] == "Alta del Balsas"]
    ax.text(ab.geometry.x.mean(), ab.geometry.y.min() - 35_000, "Alta del Balsas\n(no official outline)",
            ha="center", va="top", fontsize=8, path_effects=halo)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.8)
    # barra de escala (200 km) y norte, arriba a la izquierda (abajo están el recuadro y Alta del Balsas)
    x0, y0 = ax.get_xlim()[0] + 0.6 * pad, ax.get_ylim()[1] - 1.0 * pad
    for i in range(4):
        ax.add_patch(plt.Rectangle((x0 + i * 50_000, y0), 50_000, 7_000, facecolor="black" if i % 2 == 0 else "white",
                                   edgecolor="black", lw=0.5))
    for d in (0, 100_000, 200_000):
        ax.text(x0 + d, y0 + 12_000, f"{d // 1000}", ha="center", va="bottom")
    ax.text(x0 + 200_000 + 8_000, y0 + 3_500, "km", ha="left", va="center")
    ax.annotate("N", xy=(x0 + 275_000, y0 + 30_000), xytext=(x0 + 275_000, y0 - 12_000), ha="center", va="center",
                fontsize=9, fontweight="bold", arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 0.8})
    inset = ax.inset_axes([0.0, 0.0, 0.25, 0.25])
    nation.plot(ax=inset, color="#E0E0E0", edgecolor="#4D4D4D", lw=0.3)
    inset.add_patch(plt.Rectangle((ax.get_xlim()[0], ax.get_ylim()[0]), ax.get_xlim()[1] - ax.get_xlim()[0],
                                  ax.get_ylim()[1] - ax.get_ylim()[0], fill=False, color="black", lw=0.8))
    inset.set_xticks([])
    inset.set_yticks([])
    for sp in inset.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.6)

    n_iso = int((sizes == 1).sum())
    handles = [Line2D([], [], ls="none", marker="s", color=color[g], mec="black", mew=0.35, ms=5,
                      label=f"Group {letter[g]} ({multi[g]} gauges)") for g in multi.index]
    handles += [Line2D([], [], ls="none", marker="s", color=ISOLATED, mec="#4D4D4D", mew=0.35, ms=5,
                       label=f"Isolated gauge ({n_iso})"),
                *[Line2D([], [], ls="none", marker=mk, color="#7F7F7F", mec="black", mew=0.35, ms=5,
                         label=REGIME_LABEL[r]) for r, mk in REGIME_MARKER.items()],
                Line2D([], [], ls="none", marker="o", mfc="white", mec="black", mew=0.8, ms=5,
                       label=f"Modeled, not evaluable ({len(ne)})"),
                Line2D([], [], color="#4D4D4D", lw=0.8, label="Hydrological region outline"),
                Line2D([], [], color="#4D4D4D", lw=0.8, ls="-.", label="Cutzamala basin outline")]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), handletextpad=0.4,
               columnspacing=1.0)
    fig.tight_layout(rect=(0, 0.17, 1, 1))
    ESI.save(fig, "Fig2", 174)
    return {"estaciones_modeladas": int(len(pts)), "estaciones_evaluables": int(len(ev)),
            "no_evaluables": sorted(ne["clave"]), "grupos": int(sizes.size), "grupos_con_varias": int(len(multi)),
            "aisladas": n_iso, "tamano_grupos": {letter[g]: int(n) for g, n in multi.items()},
            "regimen": ev["regimen"].value_counts().to_dict()}


# ----------------------------------------------------------------------------- texto principal
def fig1_workflow() -> None:
    """Fig. 1: flujo del estudio; el LSTM (descriptivo) con borde discontinuo y sin entrar al ensamble."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    W, H = 174.0, 104.0
    fig = plt.figure(figsize=(W * MM, H * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    grey, lstm = "#4D4D4D", STYLE["lstm"]["color"]
    fills = {"data": "#EEF3F8", "rq1": "#E8F1FA", "rq2": "#FBEFF5", "rq3": "#E9EEF6"}

    def box(x, y, w, h, text, fill="white", edge=grey, ls="-", lw=0.8, weight="normal"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", facecolor=fill,
                                    edgecolor=edge, linestyle=ls, linewidth=lw))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7, fontweight=weight,
                linespacing=1.25)
        return (x, y, w, h)

    def arrow(p, q, color=grey, ls="-"):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color=color, lw=0.8, linestyle=ls,
                                     shrinkA=0, shrinkB=0))

    # columnas (x, ancho) y filas (y0, y1); las cajas dejan 2 mm a cada lado de su columna
    cols = {"data": (1.5, 38, "Data and samples"), "rq1": (41, 43, "RQ1 · Forecast skill"),
            "rq2": (85.5, 43, "RQ2 · Explanations"), "rq3": (130, 43, "RQ3 · Fuzzy alerts")}
    rows = {1: (68, 90), 2: (46, 64), 3: (16, 42)}
    for key, (x, w, title) in cols.items():
        ax.add_patch(FancyBboxPatch((x, 2), w, H - 4, boxstyle="round,pad=0,rounding_size=2", facecolor=fills[key],
                                    edgecolor="none"))
        ax.text(x + w / 2, 97, title, ha="center", va="center", fontsize=8, fontweight="bold")

    def cell(col, row, text, **kw):
        x, w, _ = cols[col]
        y0, y1 = rows[row]
        return box(x + 2, y0, w - 4, y1 - y0, text, **kw)

    def cx(col):
        return cols[col][0] + cols[col][1] / 2

    boxes = [
        cell("data", 1, "Hidro-MX v2026.10\n(CONAGUA-SIH; Zenodo)\n95 gauges in\n4 pilot basins"),
        cell("data", 2, "6 inputs × 30 days:\nQ, MA7, MA30, P,\nsin/cos(day of year);\ntarget Q(t + h),\nh = 1, 7, 14 d"),
        cell("data", 3, "Chronological split\ntrain 2010–2020\nvalidation 2021–2022\ntest 2023 – 09/2025;\nannual walk-forward\n2021–2025"),
        cell("rq1", 1, "References: persistence,\nclimatology; ARIMA per gauge\nGlobal per basin and lead:\nXGBoost, TCN,\nConvNeXt-1D, PatchTST"),
        cell("rq1", 3, "Skill on the test period\nNSE, KGE, SS vs persistence\nstation bootstrap (10,000)\nH1, H1-b"),
        cell("rq2", 1, "TreeSHAP (XGBoost);\nIntegrated Gradients\n(networks, 64 steps);\nfixed sample of\n≤ 2,000 test windows"),
        cell("rq2", 2, "Importance maps\n(input × input day, 6 × 30)"),
        cell("rq2", 3, "Agreement between models\n(Spearman) vs seed noise\nceiling; precipitation lag\nH2-a, H2-b"),
        cell("rq3", 1, "Ensemble: 4 learned\nmodels × 3 seeds\n= 12 members"),
        cell("rq3", 2, "Percentile + dispersion\n→ Mamdani FIS, 4 levels"),
        cell("rq3", 3, "Events > P90 and > P99\nCSI, fuzzy vs threshold\nstation bootstrap of ΔCSI\nH3"),
    ]
    x1 = cols["rq1"][0]
    boxes.append(box(x1 + 13, 50, cols["rq1"][1] - 15, 10, "LSTM, descriptive\n(added later)", edge=lstm, ls="--",
                     lw=1.0))
    lstm_cx = x1 + 13 + (cols["rq1"][1] - 15) / 2
    for col in ("data", "rq2", "rq3"):                       # flujo dentro de cada columna
        arrow((cx(col), rows[1][0]), (cx(col), rows[2][1]))
        arrow((cx(col), rows[2][0]), (cx(col), rows[3][1]))
    arrow((x1 + 7, rows[1][0]), (x1 + 7, rows[3][1]))        # modelos → habilidad (a la izquierda del LSTM)
    arrow((lstm_cx, 50), (lstm_cx, rows[3][1]), color=lstm, ls="--")
    data_r, rq1_l, rq1_r, rq2_l = 37.5, x1 + 2, x1 + cols["rq1"][1] - 2, cols["rq2"][0] + 2
    arrow((data_r, 29), (rq1_l, 76))                         # partición → modelos
    arrow((rq1_r, 79), (rq2_l, 79))                          # modelos → explicaciones
    arrow((rq1_r, 55), (rq2_l, 71), color=lstm, ls="--")     # LSTM → explicaciones
    # modelos → ensamble, por encima de las cajas de RQ2
    xb = rq1_r - 4
    ax.plot([xb, xb, cx("rq3")], [rows[1][1], 93, 93], color=grey, lw=0.8, solid_capstyle="butt")
    arrow((cx("rq3"), 93), (cx("rq3"), rows[1][1]))
    ax.text(W / 2, 8, "LSTM: not part of H1–H3 nor of the alert ensemble; reported as a descriptive comparison.",
            ha="center", va="center", fontsize=7, color=lstm)
    for b in boxes:
        assert b[0] + b[2] <= W and b[1] + b[3] <= H
    ESI.save(fig, "Fig1", 174)


def fig3_skill(sm: pd.DataFrame, lsm: pd.DataFrame | None) -> None:
    order = ESI.ORDER + (["lstm"] if lsm is not None else [])
    allm = pd.concat([sm, lsm], ignore_index=True) if lsm is not None else sm
    agg = allm[allm["grupo"] == "agregado"]
    n = int(agg.loc[agg["modelo"] == "persistencia", "estaciones"].iloc[0])
    fig, axes = plt.subplots(1, 2, figsize=(W2, 78 * MM))
    x = np.arange(len(HS))
    for i, m in enumerate(order):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(order) - 1) / 2) * 0.09
        axes[0].errorbar(x + off, r["nse_mediana"], yerr=[r["nse_mediana"] - r["nse_q25"], r["nse_q75"] - r["nse_mediana"]],
                         ls="none", capsize=1.5, elinewidth=0.8, label=STYLE[m]["label"], **mst(m))
    axes[0].axhline(0, color="black", lw=0.6)
    axes[0].set_ylabel(f"NSE (median and IQR, {n} gauges)")
    lo_lim = -0.4
    mb = [m for m in order if m != "persistencia"]
    for i, m in enumerate(mb):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(mb) - 1) / 2) * 0.1
        for j, h in enumerate(HS):
            med, lo, hi = r.loc[h, ["ss_mediana", "ss_ic_lo", "ss_ic_hi"]]
            if med < lo_lim:
                axes[1].plot(x[j] + off, lo_lim + 0.03, ls="none", **mst(m, marker="v"))
                axes[1].annotate(f"{med:.2f}", (x[j] + off, lo_lim + 0.03), xytext=(4, 0), textcoords="offset points",
                                 ha="left", va="center", color="#333333")
            else:
                axes[1].errorbar(x[j] + off, med, yerr=ESI.ci_err(med, lo, hi), ls="none", capsize=1.5,
                                 elinewidth=0.8, **mst(m))
    axes[1].axhline(0, color="black", lw=0.6)
    axes[1].set_ylim(lo_lim, 0.45)
    axes[1].set_ylabel("Skill score vs persistence\n(median, 95% CI)")
    for ax, s in zip(axes, "ab", strict=True):
        ax.set_xticks(x, [str(h) for h in HS])
        ax.set_xlabel("Lead time (d)")
        ESI.letter(ax, s)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=4, handletextpad=0.3,
               columnspacing=1.0, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    ESI.save(fig, "Fig3", 174)


def fig4_importance(imp: pd.DataFrame, limp: pd.DataFrame | None, big: list[str]) -> None:
    models = LEARNED + (["lstm"] if limp is not None else [])
    allimp = pd.concat([imp, limp], ignore_index=True) if limp is not None else imp
    ib = allimp[allimp["cuenca"].isin(big)].groupby(["h", "modelo", "canal", "rezago_ventana"])["importancia"].mean()
    vmax = float(ib.max())
    fig, axes = plt.subplots(len(HS), len(models), figsize=(W2, (112 if len(models) == 4 else 100) * MM),
                             sharex=True, sharey=True)
    for i, h in enumerate(HS):
        for j, m in enumerate(models):
            mat = ib.loc[(h, m)].unstack("rezago_ventana").reindex(index=D.CHANNELS)
            mat = mat[sorted(mat.columns, reverse=True)]
            im = axes[i, j].imshow(mat.to_numpy(), aspect="auto", cmap="viridis", norm=ESI.PowerNorm(0.4, 0, vmax),
                                   interpolation="nearest")
            for sp in axes[i, j].spines.values():
                sp.set_visible(True)
            if i == 0:
                axes[i, j].text(0.5, 1.04, STYLE[m]["label"], transform=axes[i, j].transAxes, ha="center", va="bottom")
        axes[i, 0].set_ylabel(f"Lead time {h} d")
        ESI.letter(axes[i, 0], "abc"[i], x=-0.42)
    axes[0, 0].set_yticks(range(len(D.CHANNELS)), [ESI.CH_LABEL[c] for c in D.CHANNELS])
    for ax in axes[-1]:
        ax.set_xticks([0, 14, 29], ["t−29", "t−15", "t"])
        labels = ax.get_xticklabels()
        labels[0].set_ha("left")
        labels[-1].set_ha("right")
        ax.set_xlabel("Input day")
    fig.subplots_adjust(left=0.12, right=0.86, top=0.94, bottom=0.1, wspace=0.1, hspace=0.18)
    cax = fig.add_axes([0.885, 0.1, 0.018, 0.84])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Mean normalized |attribution|")
    cb.outline.set_linewidth(0.6)
    ESI.save(fig, "Fig4", 174, dpi=600)


def fig5_agreement(conc: pd.DataFrame, rr2: pd.DataFrame, lconc: pd.DataFrame | None, big: list[str]) -> None:
    """a: mediana de los 6 pares (H2-a); b: pares de modelos; c: techo de ruido (Spearman, 180)."""
    basins = list(D.BASINS)
    cmap, norm = plt.get_cmap("cividis"), ESI.mcolors.Normalize(-0.1, 0.5)
    fig, axes = plt.subplots(1, 3, figsize=(W2, 80 * MM), gridspec_kw={"width_ratios": [0.9, 1.2, 1.1]},
                             layout="constrained")
    med = conc.groupby(["cuenca", "h"])["spearman"].median().unstack("h").reindex(index=basins)[HS]
    im = axes[0].imshow(med.to_numpy(), cmap=cmap, norm=norm, aspect="auto")
    ESI._annot_heatmap(axes[0], med.to_numpy(), cmap, norm)
    axes[0].set_xticks(range(len(HS)), [str(h) for h in HS])
    axes[0].set_xlabel("Lead time (d)")
    axes[0].set_yticks(range(len(basins)), [ESI.BASIN_TICK[b] for b in basins])
    models = LEARNED + (["lstm"] if lconc is not None else [])
    pairs = conc[conc["cuenca"].isin(big)].groupby(["modelo_a", "modelo_b"])["spearman"].mean()
    if lconc is not None:
        lp = lconc[(lconc["medida"] == "spearman_180") & (lconc["tipo"] == "entre_modelos") & lconc["cuenca"].isin(big)]
        pairs = pd.concat([pairs, lp.groupby(["modelo_a", "modelo_b"])["valor"].mean()])
    mat = np.full((len(models), len(models)), np.nan)
    for (a, b), v in pairs.items():
        i, j = models.index(a), models.index(b)
        mat[i, j] = mat[j, i] = v
    mask = np.eye(len(models), dtype=bool)
    axes[1].imshow(np.where(mask, np.nan, mat), cmap=cmap, norm=norm)
    ESI._annot_heatmap(axes[1], mat, cmap, norm, mask=mask)
    if lconc is not None:                      # el LSTM es descriptivo: separado del bloque de H2-a
        axes[1].axhline(len(LEARNED) - 0.5, color="black", lw=1.0)
        axes[1].axvline(len(LEARNED) - 0.5, color="black", lw=1.0)
    names = [STYLE[m]["label"].replace(" (descriptive)", "\n(descr.)") for m in models]
    axes[1].set_xticks(range(len(models)), names, rotation=30, ha="right", rotation_mode="anchor")
    axes[1].set_yticks(range(len(models)), names)
    r = rr2[rr2["medida"] == "spearman_180"]
    boxes = [("Between models", r[r["tipo"] == "entre_modelos"]["valor"], "#D55E00"),
             ("Across seeds", r[r["tipo"] == "entre_semillas"]["valor"], ESI.FUZZY),
             ("Across halves", r[r["tipo"] == "entre_mitades"]["valor"], "#767676")]
    if lconc is not None:
        lr = lconc[lconc["medida"] == "spearman_180"]
        boxes += [("LSTM vs others", lr[lr["tipo"] == "entre_modelos"]["valor"], STYLE["lstm"]["color"]),
                  ("LSTM across seeds", lr[lr["tipo"] == "entre_semillas"]["valor"], STYLE["lstm"]["color"])]
    for k, (_, v, col) in enumerate(boxes):
        axes[2].boxplot(v.to_numpy(), positions=[k], widths=0.55, patch_artist=True, showfliers=False,
                        boxprops={"facecolor": ESI.lighten(col, 0.35), "edgecolor": col, "linewidth": 0.8},
                        medianprops={"color": col, "linewidth": 1.2}, whiskerprops={"color": col},
                        capprops={"color": col})
    axes[2].set_xticks(range(len(boxes)), [b[0] for b in boxes], rotation=35, ha="right", rotation_mode="anchor")
    axes[2].set_ylabel("Spearman ρ, 180 importances")
    for ax, s in zip(axes, "abc", strict=True):
        if ax is not axes[2]:
            for sp in ax.spines.values():
                sp.set_visible(True)
        ESI.letter(ax, s)
    cb = fig.colorbar(im, ax=axes[:2], shrink=0.9, pad=0.02, extend="both")
    cb.set_label("Spearman ρ between importance maps")
    cb.outline.set_linewidth(0.6)
    ESI.save(fig, "Fig5", 174)


def fig6_alerts(rs: pd.DataFrame, e3: dict, pre: dict, con: pd.DataFrame) -> None:
    """a, b: CSI difuso y umbral; c: descomposición del ΔCSI P90 (F − T = A + B; C y D)."""
    agg = rs[rs["grupo"] == "agregado"]
    fig = plt.figure(figsize=(W2, 124 * MM))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])
    axa, axb, axc = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
    x = np.arange(len(HS))
    for ax, ev, s in ((axa, "P90", "a"), (axb, "P99", "b")):
        d = agg[agg["evento"] == ev].set_index("h").loc[HS]
        ax.bar(x - 0.19, d["difuso_csi"], 0.38, color=ESI.FUZZY, edgecolor=ESI.FUZZY, lw=0.6, label="Mamdani (F)")
        ax.bar(x + 0.19, d["umbral_csi"], 0.38, color=ESI.THRESH, edgecolor=ESI.THRESH_EDGE, hatch="///", lw=0.6,
               label="Threshold (T)")
        ax.set_xticks(x, [str(h) for h in HS])
        ax.set_xlabel("Lead time (d)")
        ax.set_ylabel(f"CSI (discharge > {ev})")
        ESI.letter(ax, s)
    axb.legend(*axa.get_legend_handles_labels(), loc="upper right")
    cols = {1: ESI.FUZZY, 7: "#767676", 14: "#E69F00"}
    mk = {1: "o", 7: "s", 14: "^"}
    rows = [("F − T (H3)", None), ("A: F0 − T", "A"), ("B: F − F0", "B"), ("C: TV − T", "C"), ("D: F − TV", "D")]
    c = con[(con["remuestreo"] == "estaciones") & (con["evento"] == "P90")]
    for i, (_, code) in enumerate(rows):
        for j, h in enumerate(HS):
            yy = -i + (j - 1) * 0.22
            if code is None:
                med, lo, hi = e3["H3"]["delta_csi_ic"][f"P90_h{h}"]
                pm = pre["H3"]["delta_csi_ic"][f"P90_h{h}"][0]
                axc.plot(pm, yy + 0.09, ls="none", marker=mk[h], ms=4, mfc="white", mec=cols[h], mew=0.8)
            else:
                r = c[(c["contraste"] == code) & (c["h"] == h)].iloc[0]
                med, lo, hi = r.delta_csi, r.ic_lo, r.ic_hi
            axc.errorbar(med, yy, xerr=ESI.ci_err(med, lo, hi), ls="none", marker=mk[h], ms=4, capsize=2,
                         elinewidth=0.9, color=cols[h])
    axc.set_yticks([-i for i in range(len(rows))], [r[0] for r in rows])
    axc.axvline(0, color="black", lw=0.6)
    axc.set_xlabel("ΔCSI, discharge > P90 (95% CI). F0: no dispersion; TV: threshold with dispersion veto")
    handles = [Line2D([], [], ls="none", marker=mk[h], color=cols[h], label=f"{h} d") for h in HS]
    handles.append(Line2D([], [], ls="none", marker="o", mfc="white", mec="#4D4D4D", label="F − T before correction"))
    axc.legend(handles=handles, title="Lead time", loc="lower right", ncol=2)
    ESI.letter(axc, "c")
    fig.tight_layout()
    ESI.save(fig, "Fig6", 174)


# ----------------------------------------------------------------------------- Online Resource 1
def esm_delta(e1: dict, ldelta: pd.DataFrame | None) -> None:
    ci = e1["H1b"]["ic_mediana_delta_nse"]
    models = DEEP + (["lstm"] if ldelta is not None else [])
    fig, ax = plt.subplots(figsize=(W1, (78 if ldelta is None else 96) * MM))
    labels, ys, y = [], [], 0.0
    for h in HS:
        for m in models:
            if m == "lstm":
                r = ldelta[(ldelta["h"] == h) & (ldelta["remuestreo"] == "estaciones")].iloc[0]
                med, lo, hi = r["mediana"], r["ic_lo"], r["ic_hi"]
            else:
                med, lo, hi = ci[f"{m}_h{h}"]
            ax.errorbar(med, -y, xerr=ESI.ci_err(med, lo, hi), capsize=2, elinewidth=0.9, ls="none", **mst(m))
            labels.append(f"{STYLE[m]['label'].replace(' (descriptive)', '*')}, {h} d")
            ys.append(-y)
            y += 1
        y += 0.6
    ax.set_yticks(ys, labels)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("Median ΔNSE, model − XGBoost\n(95% CI)" + ("\n*descriptive model" if ldelta is not None else ""))
    fig.tight_layout()
    ESI.save(fig, "ESM_FigS2", 84)


def esm_walk_forward(wfs: pd.DataFrame, lwf: pd.DataFrame | None, ewf: dict, e3: dict) -> None:
    order = ESI.ORDER + (["lstm"] if lwf is not None else [])
    allw = pd.concat([wfs, lwf[wfs.columns]], ignore_index=True) if lwf is not None else wfs
    agg = allw[allw["grupo"] == "agregado"]
    years = ewf["años"]
    shown = [m for m in order if m != "climatologia"]
    fig, axes = plt.subplots(2, 2, figsize=(W2, 132 * MM))
    ax = axes[0, 0]
    for m in shown:
        s = agg[(agg["h"] == 1) & (agg["modelo"] == m)].set_index("año").reindex(years)
        ax.plot(years, s["nse_mediana"], lw=0.9, ls="--" if m == "lstm" else "-", label=STYLE[m]["label"], **mst(m))
    ax.set_ylabel("Median NSE (lead time 1 d)")
    for ax, h in ((axes[0, 1], 7), (axes[1, 0], 14)):
        mb = [m for m in shown if m != "persistencia"]
        for i, m in enumerate(mb):
            s = agg[(agg["h"] == h) & (agg["modelo"] == m)].set_index("año").reindex(years)
            xx = np.array(years) + (i - (len(mb) - 1) / 2) * 0.1
            ax.errorbar(xx, s["ss_mediana"], yerr=[s["ss_mediana"] - s["ss_ic_lo"], s["ss_ic_hi"] - s["ss_mediana"]],
                        lw=0.9, ls="--" if m == "lstm" else "-", capsize=1.5, elinewidth=0.8, **mst(m))
        ax.axhline(0, color="black", lw=0.6)
        ax.set_ylabel(f"Skill score vs persistence\n(lead time {h} d; median, 95% CI)")
    ax = axes[1, 1]
    cols = {"P90_h1": (ESI.FUZZY, "o", "1 d"), "P90_h7": ("#767676", "s", "7 d")}
    handles = []
    for j, (key, (col, mk, lab)) in enumerate(cols.items()):
        v = np.array([ewf["H3"]["por_año"][str(y)]["delta_csi_ic"][key] for y in years])
        xx = np.array(years) + (j - 0.5) * 0.16
        ax.errorbar(xx, v[:, 0], yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], ls="none", marker=mk, ms=4,
                    capsize=2, elinewidth=0.9, color=col)
        ax.axhline(ewf["H3"]["referencia_principal_4_miembros"]["delta_csi_ic"][key][0], color=col, ls="--", lw=0.8)
        ax.axhline(e3["H3"]["delta_csi_ic"][key][0], color=col, ls=":", lw=0.9)
        handles.append(Line2D([], [], color=col, marker=mk, ls="none", ms=4, label=f"{lab}, annual fold (4 members)"))
    handles += [Line2D([], [], color="black", ls="--", lw=0.8, label="main split, 4 members"),
                Line2D([], [], color="black", ls=":", lw=0.9, label="main split, 12 members")]
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylim(top=float(np.max([ewf["H3"]["por_año"][str(y)]["delta_csi_ic"]["P90_h1"][2] for y in years])) * 1.85)
    ax.legend(handles=handles, loc="upper right", ncol=1, fontsize=8, handlelength=1.6, borderaxespad=0.2)
    ax.set_ylabel("ΔCSI (fuzzy − threshold),\ndischarge > P90; 95% CI")
    for ax, s in zip(axes.ravel(), "abcd", strict=True):
        ax.set_xticks(years, [str(y) for y in years])
        ESI.letter(ax, s)
    for ax in axes[1]:
        ax.set_xlabel("Test year")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="lower center", ncol=4, handletextpad=0.3,
               bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    ESI.save(fig, "ESM_FigS4", 174)


def main() -> None:
    global MESE
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lstm-dir", type=Path, default=MESE, help="Solo pruebas: carpeta con las salidas del LSTM.")
    ap.add_argument("--out", type=Path, default=FIGM, help="Solo pruebas: carpeta de salida de las figuras.")
    a = ap.parse_args()
    MESE = a.lstm_dir
    a.out.mkdir(parents=True, exist_ok=True)
    ESI.FIG = a.out
    js = ESI._json
    nums, e1, e2, e3 = js("numbers.json"), js("e_rq1.json"), js("e_rq2.json"), js("e_rq3.json")
    pre, ewf, erev = js("rq3_pre_correccion/e_rq3.json"), js("e_walkforward.json"), js("e_revision.json")
    sm, imp, conc = (pd.read_csv(OUT / f"{n}.csv") for n in ("rq1_summary", "rq2_importance", "rq2_concordance"))
    rs, wfs, dq = (pd.read_csv(OUT / f"{n}.csv") for n in ("rq3_summary", "wf_summary", "diag_sequia_2023"))
    rr2, con, curve = (pd.read_csv(OUT / f"{n}.csv") for n in ("rev_rr2_medidas", "rev_rr1_contrastes",
                                                               "rev_rr11_valor_relativo"))
    s1 = pd.read_csv(OUT / "tables" / "S1_descriptores.csv", dtype={"clave": str})
    best = {int(k[1:]): v for k, v in erev["rr6_descriptores"]["mejor_modelo"].items()}
    big = e2["cuencas_con_inferencia"]
    lstm = {k: _lstm(k) for k in LSTM_FILES}
    res = {"lstm_incluido": {k: v is not None for k, v in lstm.items()}}

    fig1_workflow()
    res["fig2_mapa"] = fig_map(ESI.official_layers())
    fig3_skill(sm, lstm["skill"])
    fig4_importance(imp, lstm["imp"], big)
    fig5_agreement(conc, rr2, lstm["conc"], big)
    fig6_alerts(rs, e3, pre, con)

    ESI.fig_surface()
    esm_delta(e1, lstm["delta"])
    ESI.fig_precip(imp, big)
    esm_walk_forward(wfs, lstm["wf"], ewf, e3)
    ESI.fig_drought(dq)
    order = ESI.ORDER
    if lstm["skill"] is not None:
        ESI.ORDER = order + ["lstm"]
    ESI.fig_basins_nse(pd.concat([sm, lstm["skill"]], ignore_index=True) if lstm["skill"] is not None else sm)
    ESI.ORDER = order
    ESI.fig_timeline(nums["figuras"]["estacion_ejemplo_fig9"])
    _load_script("xai_14_review_analyses").figures(con, curve, rr2, s1, best)

    rec = pd.DataFrame(ESI.RECORD)
    rec["contenido"] = rec["archivo"].map(CONTENT)
    rec.to_csv(a.out / "figures_mese.csv", index=False)
    (a.out / "figures_mese.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("%d figuras; LSTM: %s", len(rec), res["lstm_incluido"])


if __name__ == "__main__":
    main()

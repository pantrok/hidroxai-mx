#!/usr/bin/env python
"""Benchmark XAI · paso 12: figuras en formato Earth Science Informatics (Springer).

Rehace en formato de revista las figuras del benchmark y agrega el mapa del área de estudio.
- Mismo contenido que `xai_08_report.py`, sin recalcular métricas: lee `numbers.json` y los
  archivos de resultados.
- No modifica `xai_08_report.py` ni `results/xai_benchmark/figures/`.

Estilo (normas de Springer con convenciones de figures4papers):
- **Tamaño:** se dibuja al tamaño final, 84 o 174 mm de ancho.
- **Texto:** Arial de 8–9 pt, inglés americano; sin títulos; paneles a, b, c en negritas.
- **Ejes:** sin bordes superior ni derecho.
- **Color y patrón:** un color Okabe-Ito y un marcador fijos por modelo; referencias en gris;
  Mamdani en #0F4D92 contra umbral gris con trama.
- **Sin transparencias**, para que el EPS sea fiel.

Exporta PDF y EPS (fuentes TrueType incrustadas), TIFF-LZW RGB a 300 dpi (600 en los mapas de
importancia) y PNG de revisión.

Además agrega `datos.por_cuenca` (descriptivo) a `numbers.json`, con los datos de la Tabla 1.
Correrlo después de `xai_08_report.py`, que reescribe `numbers.json`.

Límites oficiales (ya registrados en conf/sources.yaml):
- CONAGUA (2007), Regiones Hidrológicas 1:250 000 (rh250kgw);
- CNA (1998), Cuencas Hidrológicas 1:250 000 (cue250kgw).

La correspondencia con las cuencas piloto es la regla de `dib_14`:
- Lerma–Santiago = región 12;
- Pánuco = región 26;
- Cutzamala = cuenca "Río Cutzamala";
- Alta del Balsas no tiene equivalente oficial y no se dibuja su contorno.

Salidas: results/xai_benchmark/figures_esi/<nombre>.{pdf,eps,tif,png}, figures_esi.csv,
         tables/T9_cuencas_piloto.csv y numbers.json → datos.por_cuenca
Uso:  python scripts/xai_12_figures_esi.py
"""
from __future__ import annotations

import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap, PowerNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from PIL import Image  # noqa: E402

from hidroxai_mx.alert import fuzzy as F  # noqa: E402
from hidroxai_mx.models import data as D  # noqa: E402
from hidroxai_mx.utils import DATA, FEATURES, PROCESSED, ROOT, get_logger  # noqa: E402

log = get_logger("xai_12")
OUT = ROOT / "results" / "xai_benchmark"
FIG = OUT / "figures_esi"
LIM = DATA / "scratch" / "limites"
ALERTS = ROOT / "data" / "interim" / "xai_benchmark" / "alerts"
MM = 1 / 25.4
W1, W2, HMAX = 84 * MM, 174 * MM, 234 * MM
HS = list(D.HORIZONS)
ORDER = ["persistencia", "climatologia", "arima", "xgboost", "tcn", "convnext", "patchtst"]
LEARNED, DEEP = ["xgboost", "tcn", "convnext", "patchtst"], ["tcn", "convnext", "patchtst"]
STYLE = {  # Okabe-Ito sin verde; referencias en grises; marcador fijo por modelo
    "persistencia": {"color": "#767676", "marker": "X", "label": "Persistence"},
    "climatologia": {"color": "#CFCECE", "marker": "p", "label": "Climatology", "mec": "#767676"},
    "arima": {"color": "#E69F00", "marker": "s", "label": "ARIMA"},
    "xgboost": {"color": "#0072B2", "marker": "o", "label": "XGBoost"},
    "tcn": {"color": "#56B4E9", "marker": "^", "label": "TCN"},
    "convnext": {"color": "#CC79A7", "marker": "D", "label": "ConvNeXt-1D"},
    "patchtst": {"color": "#D55E00", "marker": "v", "label": "PatchTST"},
}
FUZZY, THRESH, THRESH_EDGE = "#0F4D92", "#C8C8C8", "#4D4D4D"
LEVEL_COLORS = ["#F0F0F0", "#FDD49E", "#FC8D59", "#B30000"]   # secuencial (OrRd), apta para daltonismo
LEVEL_NAMES = ["normal", "watch", "alert", "emergency"]
CH_LABEL = {"gasto_medio_m3s": "Q", "gasto_medio_m3s_ma7": "Q MA7", "gasto_medio_m3s_ma30": "Q MA30",
            "precip_idw_mm": "P", "doy_sin": "sin(doy)", "doy_cos": "cos(doy)"}
BASIN_LABEL = {"Lerma–Santiago": "Lerma–Santiago", "Pánuco": "Pánuco", "Alta del Balsas": "Alta del Balsas",
               "Cutzamala": "Cutzamala\n(one gauge)"}
BASIN_TICK = {"Lerma–Santiago": "Lerma–\nSantiago", "Pánuco": "Pánuco", "Alta del Balsas": "Alta del\nBalsas",
              "Cutzamala": "Cutzamala\n(one gauge)"}
BASIN_STYLE = {"Lerma–Santiago": ("#0072B2", "o"), "Pánuco": ("#E69F00", "s"),
               "Alta del Balsas": ("#CC79A7", "^"), "Cutzamala": ("#000000", "D")}
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
RECORD: list[dict] = []

plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8, "legend.title_fontsize": 8,
    "axes.linewidth": 0.8, "xtick.major.width": 0.8, "ytick.major.width": 0.8,
    "xtick.major.size": 3, "ytick.major.size": 3, "lines.linewidth": 1.0, "lines.markersize": 4,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "hatch.linewidth": 0.6,
    "axes.unicode_minus": True, "figure.dpi": 100,
})


# ----------------------------------------------------------------------------- utilidades
def _json(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def lighten(color: str, f: float) -> tuple:
    """Mezcla con blanco (sin transparencia, para EPS)."""
    r, g, b = mcolors.to_rgb(color)
    return (1 - f * (1 - r), 1 - f * (1 - g), 1 - f * (1 - b))


def text_color(rgba) -> str:
    lum = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
    return "white" if lum < 0.45 else "black"


def letter(ax, s: str, x: float = -0.02, y: float = 1.02) -> None:
    ax.text(x, y, s, transform=ax.transAxes, fontsize=9, fontweight="bold", ha="right", va="bottom")


def mstyle(m: str, **kw) -> dict:
    s = STYLE[m]
    return {"color": s["color"], "marker": s["marker"], "mec": s.get("mec", s["color"]), **kw}


def save(fig, name: str, width_mm: float, dpi: int = 300, raster_dpi: int | float | str = "figure") -> None:
    h_mm = fig.get_size_inches()[1] / MM
    assert h_mm <= 234.01, f"{name}: alto {h_mm:.0f} mm > 234 mm"
    # raster_dpi solo importa a las capas rasterizadas (fig8); en EPS también remuestrea imshow, por eso no se sube
    fig.savefig(FIG / f"{name}.pdf", dpi=raster_dpi, metadata={"CreationDate": None})
    fig.savefig(FIG / f"{name}.eps", dpi=raster_dpi)
    fig.savefig(FIG / f"{name}.png", dpi=dpi)
    with Image.open(FIG / f"{name}.png") as im:
        im.convert("RGB").save(FIG / f"{name}.tif", compression="tiff_lzw", dpi=(dpi, dpi))
        w_px, h_px = im.size
    plt.close(fig)
    RECORD.append({"archivo": name, "ancho_mm": round(width_mm), "alto_mm": round(h_mm, 1), "dpi_tiff": dpi,
                   "ancho_px": w_px, "alto_px": h_px})
    log.info("%s: %d × %.0f mm", name, width_mm, h_mm)


def ci_err(med, lo, hi):
    return [[med - lo], [hi - med]]


# ----------------------------------------------------------------------------- figuras de resultados
def fig_skill(sm: pd.DataFrame) -> None:
    agg = sm[sm["grupo"] == "agregado"]
    n = int(agg["estaciones"].iloc[0])
    fig, axes = plt.subplots(1, 2, figsize=(W2, 72 * MM))
    x = np.arange(len(HS))
    for i, m in enumerate(ORDER):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(ORDER) - 1) / 2) * 0.1
        axes[0].errorbar(x + off, r["nse_mediana"], yerr=[r["nse_mediana"] - r["nse_q25"], r["nse_q75"] - r["nse_mediana"]],
                         ls="none", capsize=1.5, elinewidth=0.8, label=STYLE[m]["label"], **mstyle(m))
    axes[0].axhline(0, color="black", lw=0.6)
    axes[0].set_ylabel(f"NSE (median and IQR, {n} gauges)")
    lo_lim = -0.4
    mb = [m for m in ORDER if m != "persistencia"]
    for i, m in enumerate(mb):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(mb) - 1) / 2) * 0.12
        for j, h in enumerate(HS):
            med, lo, hi = r.loc[h, ["ss_mediana", "ss_ic_lo", "ss_ic_hi"]]
            if med < lo_lim:
                axes[1].plot(x[j] + off, lo_lim + 0.03, ls="none", **mstyle(m, marker="v"))
                axes[1].annotate(f"{med:.2f}", (x[j] + off, lo_lim + 0.03), xytext=(4, 0), textcoords="offset points",
                                 ha="left", va="center", color="#333333")
            else:
                axes[1].errorbar(x[j] + off, med, yerr=ci_err(med, lo, hi), ls="none", capsize=1.5, elinewidth=0.8,
                                 **mstyle(m))
    axes[1].axhline(0, color="black", lw=0.6)
    axes[1].set_ylim(lo_lim, 0.45)
    axes[1].set_ylabel("Skill score vs persistence\n(median, 95% CI)")
    for ax, s in zip(axes, "ab", strict=True):
        ax.set_xticks(x, [str(h) for h in HS])
        ax.set_xlabel("Lead time (d)")
        letter(ax, s)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=7, handletextpad=0.3,
               columnspacing=1.0, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "fig1_rq1_skill_by_horizon", 174)


def fig_delta(e1: dict) -> None:
    ci = e1["H1b"]["ic_mediana_delta_nse"]
    fig, ax = plt.subplots(figsize=(W1, 78 * MM))
    labels, ys, y = [], [], 0.0
    for h in HS:
        for m in DEEP:
            med, lo, hi = ci[f"{m}_h{h}"]
            ax.errorbar(med, -y, xerr=ci_err(med, lo, hi), capsize=2, elinewidth=0.9, ls="none", **mstyle(m))
            labels.append(f"{STYLE[m]['label']}, {h} d")
            ys.append(-y)
            y += 1
        y += 0.6
    ax.set_yticks(ys, labels)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("Median ΔNSE, deep model − XGBoost\n(95% CI)")
    fig.tight_layout()
    save(fig, "fig3_rq1_delta_nse_vs_xgboost", 84)


def fig_importance(imp: pd.DataFrame, big: list[str]) -> None:
    ib = imp[imp["cuenca"].isin(big)].groupby(["h", "modelo", "canal", "rezago_ventana"])["importancia"].mean()
    vmax = float(ib.max())
    fig, axes = plt.subplots(len(HS), len(LEARNED), figsize=(W2, 112 * MM), sharex=True, sharey=True)
    for i, h in enumerate(HS):
        for j, m in enumerate(LEARNED):
            mat = ib.loc[(h, m)].unstack("rezago_ventana").reindex(index=D.CHANNELS)
            mat = mat[sorted(mat.columns, reverse=True)]
            im = axes[i, j].imshow(mat.to_numpy(), aspect="auto", cmap="viridis", norm=PowerNorm(0.4, 0, vmax),
                                   interpolation="nearest")
            for sp in axes[i, j].spines.values():
                sp.set_visible(True)
            if i == 0:
                axes[i, j].text(0.5, 1.04, STYLE[m]["label"], transform=axes[i, j].transAxes, ha="center", va="bottom")
        axes[i, 0].set_ylabel(f"Lead time {h} d")
        letter(axes[i, 0], "abc"[i], x=-0.42)
    axes[0, 0].set_yticks(range(len(D.CHANNELS)), [CH_LABEL[c] for c in D.CHANNELS])
    for ax in axes[-1]:
        ax.set_xticks([0, 14, 29], ["t−29", "t−15", "t"])
        labels = ax.get_xticklabels()
        labels[0].set_ha("left")          # evita que choquen los rótulos de paneles vecinos
        labels[-1].set_ha("right")
        ax.set_xlabel("Input day")
    fig.subplots_adjust(left=0.12, right=0.86, top=0.94, bottom=0.1, wspace=0.1, hspace=0.18)
    cax = fig.add_axes([0.885, 0.1, 0.018, 0.84])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Mean normalized |attribution|")
    cb.outline.set_linewidth(0.6)
    save(fig, "fig4_rq2_importance_maps", 174, dpi=600)


def _annot_heatmap(ax, mat: np.ndarray, cmap, norm, fmt: str = "{:.2f}", mask=None) -> None:
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if mask is not None and mask[i, j]:
                ax.text(j, i, "—", ha="center", va="center")
                continue
            ax.text(j, i, fmt.format(mat[i, j]), ha="center", va="center", color=text_color(cmap(norm(mat[i, j]))))


def fig_concordance(conc: pd.DataFrame, big: list[str]) -> None:
    basins = list(D.BASINS)
    cmap, norm = plt.get_cmap("cividis"), mcolors.Normalize(-0.1, 0.5)
    fig, axes = plt.subplots(1, 2, figsize=(W2, 78 * MM), gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.15},
                             layout="constrained")
    med = conc.groupby(["cuenca", "h"])["spearman"].median().unstack("h").reindex(index=basins)[HS]
    im = axes[0].imshow(med.to_numpy(), cmap=cmap, norm=norm, aspect="auto")
    _annot_heatmap(axes[0], med.to_numpy(), cmap, norm)
    axes[0].set_xticks(range(len(HS)), [str(h) for h in HS])
    axes[0].set_xlabel("Lead time (d)")
    axes[0].set_yticks(range(len(basins)), [BASIN_LABEL[b] for b in basins])
    pairs = conc[conc["cuenca"].isin(big)].groupby(["modelo_a", "modelo_b"])["spearman"].mean()
    mat = np.full((len(LEARNED), len(LEARNED)), np.nan)
    for (a, b), v in pairs.items():
        i, j = LEARNED.index(a), LEARNED.index(b)
        mat[i, j] = mat[j, i] = v
    mask = np.eye(len(LEARNED), dtype=bool)
    axes[1].imshow(np.where(mask, np.nan, mat), cmap=cmap, norm=norm)
    _annot_heatmap(axes[1], mat, cmap, norm, mask=mask)
    names = [STYLE[m]["label"] for m in LEARNED]
    axes[1].set_xticks(range(len(LEARNED)), names, rotation=30, ha="right", rotation_mode="anchor")
    axes[1].set_yticks(range(len(LEARNED)), names)
    for ax, s in zip(axes, "ab", strict=True):
        for sp in ax.spines.values():
            sp.set_visible(True)
        letter(ax, s)
    cb = fig.colorbar(im, ax=axes, shrink=0.9, pad=0.02, extend="both")
    cb.set_label("Spearman ρ between\nimportance maps")
    cb.outline.set_linewidth(0.6)
    save(fig, "fig5_rq2_concordance", 174)


def fig_precip(imp: pd.DataFrame, big: list[str]) -> None:
    p = imp[(imp["canal"] == "precip_idw_mm") & imp["cuenca"].isin(big)]
    fig, axes = plt.subplots(len(HS), len(big), figsize=(W2, 118 * MM), sharex=True)
    for i, h in enumerate(HS):
        for j, b in enumerate(big):
            ax = axes[i, j]
            if h == 1:
                ax.axvspan(1, 3, color="#E3E3E3", lw=0, zorder=0)
            for m in LEARNED:
                s = p[(p["h"] == h) & (p["cuenca"] == b) & (p["modelo"] == m)].sort_values("rezago_objetivo")
                ax.plot(s["rezago_objetivo"], s["importancia"], color=STYLE[m]["color"], lw=0.9, label=STYLE[m]["label"])
                k = s["importancia"].idxmax()
                ax.plot(s.loc[k, "rezago_objetivo"], s.loc[k, "importancia"], ls="none", ms=4, **mstyle(m))
            if i == 0:
                ax.text(0.5, 1.04, b, transform=ax.transAxes, ha="center", va="bottom")
            if j == 0:
                ax.set_ylabel(f"P importance\n(lead time {h} d)")
        letter(axes[i, 0], "abc"[i], x=-0.28)
    for ax in axes[-1]:
        ax.set_xlabel("Lag before target day (d)")
    handles = [Line2D([], [], lw=0.9, **mstyle(m)) for m in LEARNED]
    handles.append(Patch(facecolor="#E3E3E3", label="1–3 d window (H2-b)"))
    fig.legend(handles, [STYLE[m]["label"] for m in LEARNED] + ["1–3 d window (H2-b)"], loc="lower center",
               ncol=5, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "fig6_rq2_precip_lag_profiles", 174)


def fig_alerts(rs: pd.DataFrame, e3: dict, pre: dict) -> None:
    agg = rs[rs["grupo"] == "agregado"]
    fig, axes = plt.subplots(1, 3, figsize=(W2, 66 * MM), gridspec_kw={"width_ratios": [1, 1, 1.35]})
    x = np.arange(len(HS))
    for ax, ev, s in ((axes[0], "P90", "a"), (axes[1], "P99", "b")):
        d = agg[agg["evento"] == ev].set_index("h").loc[HS]
        ax.bar(x - 0.19, d["difuso_csi"], 0.38, color=FUZZY, edgecolor=FUZZY, lw=0.6, label="Mamdani")
        ax.bar(x + 0.19, d["umbral_csi"], 0.38, color=THRESH, edgecolor=THRESH_EDGE, hatch="///", lw=0.6,
               label="Threshold")
        ax.set_xticks(x, [str(h) for h in HS])
        ax.set_xlabel("Lead time (d)")
        ax.set_ylabel(f"CSI (discharge > {ev})")
        letter(ax, s)
    axes[1].legend(*axes[0].get_legend_handles_labels(), loc="upper right")   # en b, sobre las barras bajas
    keys = [f"{e}_h{h}" for e in ("P90", "P99") for h in HS]
    for src, lab, filled in ((e3, "corrected", True), (pre, "before correction", False)):
        for i, key in enumerate(keys):
            med, lo, hi = src["H3"]["delta_csi_ic"][key]
            yy = -i + (0.16 if filled else -0.16)
            axes[2].errorbar(med, yy, xerr=ci_err(med, lo, hi), capsize=2, elinewidth=0.9, ls="none",
                             marker="o" if filled else "s", ms=4, color=FUZZY if filled else "#767676",
                             mfc=FUZZY if filled else "white", label=lab if i == 0 else None)
    axes[2].set_yticks([-i for i in range(len(keys))],
                       [f"{k.split('_')[0]}, {k.split('_h')[1]} d" for k in keys])
    axes[2].axvline(0, color="black", lw=0.6)
    axes[2].set_xlabel("ΔCSI (fuzzy − threshold), 95% CI")
    axes[2].legend(loc="lower right")
    letter(axes[2], "c")
    fig.tight_layout()
    save(fig, "fig7_rq3_alert_skill", 174)


def fig_surface() -> None:
    fis = F.build_protocol_fis()
    pg, dg = np.linspace(0.6, 1.0, 321), np.linspace(0.0, 0.6, 241)
    P, Dd = np.meshgrid(pg, dg)
    lv = F.level_index(fis.infer_array({"percentil": P.ravel(), "dispersion": Dd.ravel()})).reshape(P.shape)
    fig, ax = plt.subplots(figsize=(W1, 66 * MM))
    cmap = ListedColormap(LEVEL_COLORS)
    im = ax.pcolormesh(P, Dd, lv, cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4), shading="auto",
                       rasterized=True)   # 77k celdas: raster a 300 dpi dentro del PDF/EPS
    ax.contour(P, Dd, lv, levels=[0.5, 1.5, 2.5], colors="#333333", linewidths=0.5)
    for q, ls in ((0.90, "--"), (0.99, ":")):
        ax.axvline(q, color="black", ls=ls, lw=0.8)
    ax.set_xlabel("Percentile of ensemble mean")
    ax.set_ylabel("Member dispersion\n(IQR of percentiles)")
    for sp in ax.spines.values():
        sp.set_visible(True)
    cb = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3], pad=0.03)
    cb.ax.set_yticklabels(LEVEL_NAMES)
    cb.outline.set_linewidth(0.6)
    fig.tight_layout()
    save(fig, "fig8_rq3_fuzzy_decision_surface", 84, raster_dpi=300)


def fig_walk_forward(wfs: pd.DataFrame, ewf: dict, e3: dict) -> None:
    agg = wfs[wfs["grupo"] == "agregado"]
    years = ewf["años"]
    shown = [m for m in ORDER if m != "climatologia"]
    fig, axes = plt.subplots(2, 2, figsize=(W2, 128 * MM))
    ax = axes[0, 0]
    for m in shown:
        s = agg[(agg["h"] == 1) & (agg["modelo"] == m)].set_index("año").reindex(years)
        ax.plot(years, s["nse_mediana"], lw=0.9, label=STYLE[m]["label"], **mstyle(m))
    ax.set_ylabel("Median NSE (lead time 1 d)")
    for ax, h in ((axes[0, 1], 7), (axes[1, 0], 14)):
        mb = [m for m in shown if m != "persistencia"]
        for i, m in enumerate(mb):
            s = agg[(agg["h"] == h) & (agg["modelo"] == m)].set_index("año").reindex(years)
            xx = np.array(years) + (i - (len(mb) - 1) / 2) * 0.1
            ax.errorbar(xx, s["ss_mediana"], yerr=[s["ss_mediana"] - s["ss_ic_lo"], s["ss_ic_hi"] - s["ss_mediana"]],
                        lw=0.9, capsize=1.5, elinewidth=0.8, **mstyle(m))
        ax.axhline(0, color="black", lw=0.6)
        ax.set_ylabel(f"Skill score vs persistence\n(lead time {h} d; median, 95% CI)")
    ax = axes[1, 1]
    cols = {"P90_h1": (FUZZY, "o", "1 d"), "P90_h7": ("#767676", "s", "7 d")}
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
        letter(ax, s)
    for ax in axes[1]:
        ax.set_xlabel("Test year")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="lower center", ncol=6, handletextpad=0.3,
               bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    save(fig, "fig10_walk_forward", 174)


def fig_drought(dq: pd.DataFrame) -> None:
    years = sorted(dq["año"].unique())
    basins = list(D.BASINS)
    blues = ["#DEEBF7", "#9ECAE1", None, "#4292C6", "#08519C"]
    style = {y: ({"color": "#D55E00", "hatch": "///", "edgecolor": "#5A2000"} if y == 2023 else
                 {"color": c, "edgecolor": "#4D4D4D"}) for y, c in zip(years, blues, strict=True)}
    fig, axes = plt.subplots(1, 2, figsize=(W2, 68 * MM))
    w = 0.16
    for ax, var, lab, scale, ref in ((axes[0], "anomalia_precip_mediana",
                                      "Precipitation anomaly vs\n2010–2020 median (%)", 100, 0),
                                     (axes[1], "razon_gasto_mediana", "Discharge ratio vs\n2010–2020 mean", 1, 1)):
        for i, y in enumerate(years):
            v = np.array([dq.loc[(dq["cuenca"] == b) & (dq["año"] == y), var].squeeze() for b in basins], dtype=float)
            ax.bar(np.arange(len(basins)) + (i - 2) * w, v * scale, w, lw=0.5, label=str(y), **style[y])
        ax.axhline(ref, color="black", lw=0.6)
        ax.set_xticks(range(len(basins)), [BASIN_TICK[b] for b in basins])
        ax.set_ylabel(lab)
    for ax, s in zip(axes, "ab", strict=True):
        letter(ax, s)
    fig.legend(*axes[1].get_legend_handles_labels(), ncol=5, loc="lower center", bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "fig11_drought_2023", 174)


# ----------------------------------------------------------------------------- suplemento
def fig_basins_nse(sm: pd.DataFrame) -> None:
    basins = list(D.BASINS)
    cmap, norm = plt.get_cmap("cividis"), mcolors.Normalize(-0.5, 1.0)
    fig, axes = plt.subplots(1, 3, figsize=(W2, 98 * MM), sharey=True, layout="constrained")
    for ax, h, s in zip(axes, HS, "abc", strict=True):
        sub = sm[sm["h"] == h]
        mat = np.array([[sub[(sub["grupo"] == b) & (sub["modelo"] == m)]["nse_mediana"].item() for b in basins]
                        for m in ORDER])
        im = ax.imshow(mat, cmap=cmap, norm=norm, aspect="auto")
        _annot_heatmap(ax, mat, cmap, norm)
        n = [int(sub[sub["grupo"] == b]["estaciones"].iloc[0]) for b in basins]
        ax.set_xticks(range(len(basins)), [f"{b} ({k})" for b, k in zip(basins, n, strict=True)],
                      rotation=40, ha="right", rotation_mode="anchor")
        ax.set_xlabel(f"Lead time {h} d")
        for sp in ax.spines.values():
            sp.set_visible(True)
        letter(ax, s)
    axes[0].set_yticks(range(len(ORDER)), [STYLE[m]["label"] for m in ORDER])
    cb = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02, extend="min")
    cb.set_label("Median NSE")
    cb.outline.set_linewidth(0.6)
    save(fig, "fig2_rq1_nse_by_basin", 174)


def fig_timeline(clave: str) -> None:
    a = pd.read_parquet(ALERTS / "lerma_santiago_h1.parquet")
    a = a[a["clave"] == clave].sort_values("target_date")
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", D.TARGET],
                         filters=[("clave_estacion", "==", clave)])
    ft["fecha"] = pd.to_datetime(ft["fecha"])
    tr = ft[(ft["fecha"] >= D.PARTITIONS["train"][0]) & (ft["fecha"] <= D.PARTITIONS["train"][1]) & (ft["calidad"] == 0)]
    q90, q99 = np.quantile(tr[D.TARGET], [0.90, 0.99])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(W2, 74 * MM), sharex=True, gridspec_kw={"height_ratios": [4, 0.7]})
    ax.plot(a["target_date"], a["observado"], color="black", lw=0.7, label="Observed")
    ax.plot(a["target_date"], a["ensamble"], color=FUZZY, lw=0.7, ls="-", label="Ensemble mean (12 members)")
    ax.axhline(q90, color="#767676", ls="--", lw=0.8, label="P90 (training)")
    ax.axhline(q99, color="#767676", ls=":", lw=0.9, label="P99 (training)")
    ax.set_ylabel("Discharge (m³/s)")
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0.0, 1.0), borderaxespad=0.2)
    ax2.bar(a["target_date"], np.ones(len(a)), width=1.0, color=[LEVEL_COLORS[v] for v in a["nivel"]], lw=0)
    ax2.set_yticks([])
    ax2.set_ylabel("Level", rotation=0, ha="right", va="center")
    ax2.spines["left"].set_visible(False)
    handles = [Patch(facecolor=c, edgecolor="#767676", lw=0.4, label=n) for c, n in zip(LEVEL_COLORS, LEVEL_NAMES,
                                                                                        strict=True)]
    ax2.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.55))
    letter(ax, "a")
    letter(ax2, "b", y=1.0)
    fig.tight_layout()
    save(fig, "fig9_rq3_alert_timeline_example", 174)


# ----------------------------------------------------------------------------- mapa y Tabla 1
def official_layers():
    import geopandas as gpd
    crs = "EPSG:6372"
    rh = gpd.read_file(LIM / "rh250kgw" / "rh250kgw.shp")
    rh["clave_rh"] = rh["CLAVE"].astype(int)
    rh = rh[rh["clave_rh"].isin([12, 18, 26])].dissolve(by="clave_rh").reset_index().to_crs(crs)
    cue = gpd.read_file(LIM / "cue250kgw" / "cue250kgw.shp").to_crs(crs)
    cutz = cue[cue["CUENCA"] == "Río Cutzamala"].dissolve()
    areas = {"Lerma–Santiago": cue[cue["ID_RH"].astype(int) == 12].area.sum() / 1e6,
             "Pánuco": cue[cue["ID_RH"].astype(int) == 26].area.sum() / 1e6,
             "Cutzamala": float(cutz.area.sum()) / 1e6, "Alta del Balsas": None}
    states = gpd.read_file(LIM / "ne_10m_admin_1" / "ne_10m_admin_1_states_provinces.shp")
    states = states[states["admin"] == "Mexico"].to_crs(crs)
    return rh, cutz, states, areas, crs


def fig_study_area(stations: pd.DataFrame, layers) -> None:
    import geopandas as gpd
    rh, cutz, states, _, crs = layers
    nation = states.dissolve()
    pts = gpd.GeoDataFrame(stations, geometry=gpd.points_from_xy(stations["longitud"], stations["latitud"]),
                           crs="EPSG:4326").to_crs(crs)
    fig, ax = plt.subplots(figsize=(W2, 132 * MM))
    nation.plot(ax=ax, color="#F4F4F4", edgecolor="none")
    states.boundary.plot(ax=ax, color="#BDBDBD", lw=0.3)
    nation.boundary.plot(ax=ax, color="#4D4D4D", lw=0.6)
    fills = {12: "Lerma–Santiago", 26: "Pánuco"}
    for k, b in fills.items():
        g = rh[rh["clave_rh"] == k]
        g.plot(ax=ax, color=lighten(BASIN_STYLE[b][0], 0.18), edgecolor="none")
        g.boundary.plot(ax=ax, color=BASIN_STYLE[b][0], lw=1.0)
    rh[rh["clave_rh"] == 18].boundary.plot(ax=ax, color="#767676", lw=0.8, ls="--")
    cutz.plot(ax=ax, color=lighten("#000000", 0.15), edgecolor="none")
    cutz.boundary.plot(ax=ax, color="#000000", lw=0.9, ls="-.")
    for b, g in pts.groupby("cuenca"):
        col, mk = BASIN_STYLE[b]
        ev = g[g["evaluable"]]
        ne = g[~g["evaluable"]]
        ax.scatter(ev.geometry.x, ev.geometry.y, s=14, marker=mk, color=col, edgecolor="white", lw=0.4, zorder=5)
        if len(ne):
            ax.scatter(ne.geometry.x, ne.geometry.y, s=16, marker=mk, facecolor="white", edgecolor=col, lw=0.9,
                       zorder=5)
    xmin, ymin, xmax, ymax = pd.concat([rh[rh["clave_rh"].isin([12, 26])].geometry, cutz.geometry,
                                        pts.geometry]).total_bounds
    pad = 40_000
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - 2.2 * pad, ymax + pad)
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    # rótulos junto al borde norte de cada región, lejos de las estaciones
    for k, name, dx in ((12, "Lerma–Santiago (RH 12)", 0.0), (26, "Pánuco (RH 26)", -40_000)):
        x0g, _, x1g, y1g = rh[rh["clave_rh"] == k].total_bounds
        ax.text((x0g + x1g) / 2 + dx, y1g + 12_000, name, ha="center", va="bottom", fontsize=8, path_effects=halo)
    cx, cy = cutz.geometry.iloc[0].representative_point().coords[0]
    ax.text(cx - 75_000, cy - 30_000, "Cutzamala", ha="right", va="center", fontsize=8, path_effects=halo)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.8)
    # barra de escala (200 km) y norte, abajo a la derecha
    x0, y0 = ax.get_xlim()[1] - pad - 200_000, ax.get_ylim()[0] + 0.6 * pad
    for i in range(4):
        ax.add_patch(plt.Rectangle((x0 + i * 50_000, y0), 50_000, 7_000, facecolor="black" if i % 2 == 0 else "white",
                                   edgecolor="black", lw=0.5))
    for d in (0, 100_000, 200_000):
        ax.text(x0 + d, y0 + 12_000, f"{d // 1000}", ha="center", va="bottom")
    ax.text(x0 + 200_000 + 8_000, y0 + 3_500, "km", ha="left", va="center")
    ax.annotate("N", xy=(x0 + 100_000, y0 + 95_000), xytext=(x0 + 100_000, y0 + 45_000), ha="center", va="center",
                fontsize=9, fontweight="bold", arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 0.8})
    inset = ax.inset_axes([0.0, 0.0, 0.27, 0.27])
    nation.plot(ax=inset, color="#E0E0E0", edgecolor="#4D4D4D", lw=0.3)
    inset.add_patch(plt.Rectangle((ax.get_xlim()[0], ax.get_ylim()[0]), np.diff(ax.get_xlim())[0],
                                  np.diff(ax.get_ylim())[0], fill=False, color="black", lw=0.8))
    inset.set_xticks([])
    inset.set_yticks([])
    inset.set_xlabel("")
    inset.set_ylabel("")
    for sp in inset.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.6)
    ax.set_xlabel("")
    ax.set_ylabel("")
    handles = [Patch(facecolor=lighten(BASIN_STYLE["Lerma–Santiago"][0], 0.18), edgecolor=BASIN_STYLE["Lerma–Santiago"][0],
                     label="Lerma–Santiago (hydrological region 12)"),
               Patch(facecolor=lighten(BASIN_STYLE["Pánuco"][0], 0.18), edgecolor=BASIN_STYLE["Pánuco"][0],
                     label="Pánuco (hydrological region 26)"),
               Patch(facecolor=lighten("#000000", 0.15), edgecolor="black", ls="-.", label="Cutzamala basin"),
               Line2D([], [], color="#767676", lw=0.8, ls="--", label="Balsas region (RH 18), context"),
               *[Line2D([], [], ls="none", marker=BASIN_STYLE[b][1], color=BASIN_STYLE[b][0], mec="white", ms=5,
                        label=f"{b} gauges" + (" (no official outline)" if b == "Alta del Balsas" else ""))
                 for b in D.BASINS],
               Line2D([], [], ls="none", marker="o", mfc="white", mec="#4D4D4D", ms=5,
                      label="Modeled, not evaluable (open symbol)")]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), handletextpad=0.4,
               columnspacing=1.0)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    save(fig, "fig02_study_area", 174)


def basin_table(stations: pd.DataFrame, areas: dict) -> dict:
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", D.TARGET],
                         filters=[("clave_estacion", "in", stations["clave"].tolist())])
    ft["fecha"] = pd.to_datetime(ft["fecha"])
    days = pd.date_range("2010-01-01", D.PARTITIONS["test"][1], freq="D")
    rows = {}
    for b, g in stations.groupby("cuenca"):
        means, p50s, p90s, maxs, missing = [], [], [], [], []
        for k in g["clave"]:
            s = ft[ft["clave_estacion"] == k].set_index("fecha")
            orig = s[D.TARGET].where(s["calidad"] == 0).reindex(days)
            tr = orig.loc[D.PARTITIONS["train"][0]:D.PARTITIONS["train"][1]].dropna()
            means.append(tr.mean())
            p50s.append(tr.median())
            maxs.append(tr.max())
            p90s.append(tr.quantile(0.90))
            missing.append(orig.isna().mean())
        rows[b] = {"estaciones_modeladas": int(len(g)), "estaciones_evaluables": int(g["evaluable"].sum()),
                   "area_km2_oficial": None if areas[b] is None else round(areas[b], 1),
                   "gasto_medio_entrenamiento_m3s_mediana": round(float(np.median(means)), 3),
                   "gasto_mediano_entrenamiento_m3s_mediana": round(float(np.median(p50s)), 3),
                   "p90_entrenamiento_m3s_mediana": round(float(np.median(p90s)), 3),
                   "dias_sin_observacion_original_pct": round(100 * float(np.mean(missing)), 1),
                   "max_entrenamiento_m3s": round(float(np.max(maxs)), 1),
                   "estaciones_media_mayor_que_p90": int(sum(m > q for m, q in zip(means, p90s, strict=True)))}
    return rows


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    nums = _json("numbers.json")
    e1, e2, e3 = _json("e_rq1.json"), _json("e_rq2.json"), _json("e_rq3.json")
    pre, ewf = _json("rq3_pre_correccion/e_rq3.json"), _json("e_walkforward.json")
    sm = pd.read_csv(OUT / "rq1_summary.csv")
    big = e2["cuencas_con_inferencia"]
    imp, conc = pd.read_csv(OUT / "rq2_importance.csv"), pd.read_csv(OUT / "rq2_concordance.csv")
    rs, wfs = pd.read_csv(OUT / "rq3_summary.csv"), pd.read_csv(OUT / "wf_summary.csv")
    dq = pd.read_csv(OUT / "diag_sequia_2023.csv")

    fig_skill(sm)
    fig_delta(e1)
    fig_importance(imp, big)
    fig_concordance(conc, big)
    fig_precip(imp, big)
    fig_alerts(rs, e3, pre)
    fig_surface()
    fig_walk_forward(wfs, ewf, e3)
    fig_drought(dq)
    fig_basins_nse(sm)
    fig_timeline(nums["figuras"]["estacion_ejemplo_fig9"])

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    evaluable = set(st.loc[(st["h"] == 1) & (st["modelo"] == "persistencia"), "clave"])
    stations = sel[sel["clave"].map(lambda k: pd.notna(basin_of.get(k)))].copy()
    stations["cuenca"] = stations["clave"].map(basin_of)
    stations["evaluable"] = stations["clave"].isin(evaluable)
    assert len(stations) == nums["datos"]["estaciones_modeladas"]
    layers = official_layers()
    fig_study_area(stations, layers)
    pd.DataFrame(RECORD).to_csv(FIG / "figures_esi.csv", index=False)

    tab = basin_table(stations, layers[3])
    import geopandas as gpd
    rh, cutz = layers[0], layers[1]
    outline = {"Lerma–Santiago": rh[rh["clave_rh"] == 12].geometry.iloc[0],
               "Pánuco": rh[rh["clave_rh"] == 26].geometry.iloc[0], "Cutzamala": cutz.geometry.iloc[0]}
    pts = gpd.GeoSeries(gpd.points_from_xy(stations["longitud"], stations["latitud"]), crs="EPSG:4326").to_crs(layers[4])
    for b, geom in outline.items():
        inside = pts[stations["cuenca"].to_numpy() == b].within(geom)
        tab[b]["estaciones_fuera_del_contorno_dibujado"] = int((~inside).sum())
    tab["Alta del Balsas"]["estaciones_fuera_del_contorno_dibujado"] = None
    nums["datos"]["por_cuenca"] = {
        "tipo": "descriptivo",
        "fuente": "scripts/xai_12_figures_esi.py; feature_table.parquet (v2026.10); CNA (1998) cue250kgw",
        "definiciones": {
            "area_km2_oficial": "área en EPSG:6372 de la capa CNA (1998) Cuencas Hidrológicas 1:250 000: región 12 "
                                "(Lerma–Santiago), región 26 (Pánuco) y cuenca Río Cutzamala; Alta del Balsas sin "
                                "equivalente oficial",
            "gasto_medio_y_p90": "mediana entre estaciones de la media, la mediana y el P90 de gasto 2010–2020 con "
                                 "calidad = 0; max_entrenamiento_m3s es el máximo de la cuenca. Una media por encima "
                                 "del P90 indica valores extremos con calidad = 0 en el conjunto v2026.10 (no se "
                                 "modifican aquí); la mediana es la cifra robusta",
            "dias_sin_observacion_original_pct": "media entre estaciones del % de días 2010-01-01 – 2025-09-03 sin "
                                                 "observación original (calidad ≠ 0 o sin dato)"},
        "fecha": date.today().isoformat(), "valores": tab}
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")
    t9 = pd.DataFrame([{"cuenca": b, **v} for b, v in tab.items()])
    t9.to_csv(OUT / "tables" / "T9_cuencas_piloto.csv", index=False)
    log.info("Tabla 1: %s", t9.to_dict("records"))


if __name__ == "__main__":
    main()

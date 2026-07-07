#!/usr/bin/env python
"""Etapa 12 — Diagrama de flujo compacto del pipeline (para la sección Methods).

Salida: data/processed/reportes/fig0_workflow.png (300 dpi).
Se agrupa el trabajo en cuatro fases con textos cortos en dos líneas para
que ningún subtítulo se salga del recuadro.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

from hidroxai_mx.utils import PROCESSED, get_logger

log = get_logger("12_workflow")
OUT = PROCESSED / "reportes"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

INPUT = "#DFE6EC"
INPUT_EDGE = "#3E5B78"
PHASE = "#F1E7EA"
PHASE_EDGE = "#7A1737"
OUTPUT = "#FFEEDD"
OUTPUT_EDGE = "#B26D2A"

# Bigger canvas, taller rows.
fig, ax = plt.subplots(figsize=(11.5, 6.4))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, title, body_lines=None, fill=PHASE, edge=PHASE_EDGE,
        title_size=10, body_size=8):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.35,rounding_size=1.2",
                                fc=fill, ec=edge, linewidth=1.2))
    if body_lines:
        ax.text(x + w / 2, y + h * 0.78, title,
                ha="center", va="center",
                fontsize=title_size, fontweight="bold")
        body = "\n".join(body_lines)
        ax.text(x + w / 2, y + h * 0.32, body,
                ha="center", va="center", fontsize=body_size,
                linespacing=1.15)
    else:
        ax.text(x + w / 2, y + h / 2, title,
                ha="center", va="center",
                fontsize=title_size, fontweight="bold")


def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 arrowstyle="->", mutation_scale=14,
                                 color="#333", linewidth=1.1))


# ---- Row 1 : sources ----
box(2, 82, 46, 14,
    "Primary sources",
    ["CONAGUA-SIH catalogs and daily series",
     "INEGI CEM 3.0 tiles"],
    fill=INPUT, edge=INPUT_EDGE)
box(52, 82, 46, 14,
    "Pilot-basin configuration",
    ["Names, region codes, bounding boxes,",
     "target grid resolution"],
    fill=INPUT, edge=INPUT_EDGE)

# ---- Row 2 : phases 1 and 3 ----
box(2, 60, 46, 14,
    "Phase 1  ·  Data ingestion",
    ["Catalogs + candidate filter",
     "+ per-station daily records"])
arrow(25, 82, 25, 74)

box(52, 60, 46, 14,
    "Phase 3  ·  Basin geometry",
    ["Per-basin DEM mosaic and clip",
     "+ sub-basin delineation"])
arrow(75, 82, 75, 74)

# ---- Row 3 : phases 2 and 4 ----
box(2, 38, 46, 14,
    "Phase 2  ·  Curation and QC",
    ["Parsing, outlier flag,",
     "short-gap imputation, schema check"])
arrow(25, 60, 25, 52)

box(52, 38, 46, 14,
    "Phase 4  ·  Selection and features",
    ["Coverage thresholds + climate",
     "neighbours + lags / rolling means"])
arrow(75, 60, 75, 52)
arrow(48, 45, 52, 45)

# ---- Row 4 : outputs (four narrow boxes with two-line subtitles) ----
box(2, 8, 23, 18,
    "Output 1",
    ["Canonical", "time-series tables"],
    fill=OUTPUT, edge=OUTPUT_EDGE, title_size=9.5, body_size=8)
box(27, 8, 23, 18,
    "Output 2",
    ["Station manifests", "(main + extended)"],
    fill=OUTPUT, edge=OUTPUT_EDGE, title_size=9.5, body_size=8)
box(52, 8, 23, 18,
    "Output 3",
    ["Per-basin DEM and", "sub-basin polygons"],
    fill=OUTPUT, edge=OUTPUT_EDGE, title_size=9.5, body_size=8)
box(77, 8, 21, 18,
    "Output 4",
    ["Model-ready", "feature table"],
    fill=OUTPUT, edge=OUTPUT_EDGE, title_size=9.5, body_size=8)

arrow(13, 38, 13, 26)
arrow(30, 38, 38, 26)
arrow(75, 38, 62, 26)
arrow(75, 38, 88, 26)

# Legend outside the drawing area
handles = [
    Rectangle((0, 0), 1, 1, fc=INPUT, ec=INPUT_EDGE),
    Rectangle((0, 0), 1, 1, fc=PHASE, ec=PHASE_EDGE),
    Rectangle((0, 0), 1, 1, fc=OUTPUT, ec=OUTPUT_EDGE),
]
labels = ["Primary sources / configuration", "Processing phase", "Distributed output"]
ax.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
          fontsize=9, bbox_to_anchor=(0.5, -0.05))

out_path = OUT / "fig0_workflow.png"
plt.savefig(out_path)
plt.close(fig)
log.info("Workflow figure -> %s", out_path)

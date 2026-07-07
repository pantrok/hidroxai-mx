#!/usr/bin/env python
"""Etapa 12 — Diagrama de flujo compacto del pipeline (para la sección Methods).

Salida: data/processed/reportes/fig0_workflow.png (300 dpi, formato 8x4 in).
Se agrupa el trabajo en cuatro fases y se mantienen los textos cortos para
que el texto del artículo pueda cargar la descripción larga.
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

fig, ax = plt.subplots(figsize=(9.2, 4.6))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, title, subtitle="", fill=PHASE, edge=PHASE_EDGE):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.35,rounding_size=1.2",
                                fc=fill, ec=edge, linewidth=1.2))
    if subtitle:
        ax.text(x + w / 2, y + h * 0.72, title,
                ha="center", va="center", fontsize=9.5, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.32, subtitle,
                ha="center", va="center", fontsize=8.3)
    else:
        ax.text(x + w / 2, y + h / 2, title,
                ha="center", va="center", fontsize=9.5, fontweight="bold")


def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 arrowstyle="->", mutation_scale=14,
                                 color="#333", linewidth=1.1))


# ---- Row 1: sources ----
box(3, 78, 42, 14,
    "Primary sources",
    "CONAGUA-SIH catalogs and daily series  ·  INEGI CEM 3.0 tiles",
    fill=INPUT, edge=INPUT_EDGE)
box(55, 78, 42, 14,
    "Pilot-basin configuration",
    "Names, region codes, bounding boxes, target grid",
    fill=INPUT, edge=INPUT_EDGE)

# ---- Row 2: acquisition + curation ----
box(3, 56, 42, 14,
    "Phase 1 · Data ingestion",
    "Catalogs + candidate filter + per-station daily records")
arrow(24, 78, 24, 70)
arrow(76, 78, 76, 62)

box(55, 56, 42, 14,
    "Phase 3 · Basin geometry",
    "Per-basin DEM mosaic + clip + sub-basin delineation")

# ---- Row 3: canonical QC ----
box(3, 34, 42, 14,
    "Phase 2 · Curation and QC",
    "Parsing, outlier flag, short-gap imputation, schema check")
arrow(24, 56, 24, 48)

# ---- Row 3b: features ----
box(55, 34, 42, 14,
    "Phase 4 · Selection and features",
    "Coverage thresholds + climate neighbours + lags/rolling means")
arrow(76, 56, 76, 48)
arrow(45, 41, 55, 41)

# ---- Row 4: outputs ----
box(3, 8, 22, 16,
    "Output 1",
    "Canonical time-series tables (hydro + climate)",
    fill=OUTPUT, edge=OUTPUT_EDGE)
box(28, 8, 22, 16,
    "Output 2",
    "Station manifests (main and extended sets)",
    fill=OUTPUT, edge=OUTPUT_EDGE)
box(53, 8, 22, 16,
    "Output 3",
    "Per-basin DEM and sub-basin polygons",
    fill=OUTPUT, edge=OUTPUT_EDGE)
box(78, 8, 19, 16,
    "Output 4",
    "Model-ready feature table",
    fill=OUTPUT, edge=OUTPUT_EDGE)

arrow(14, 34, 14, 24)
arrow(30, 34, 36, 24)
arrow(76, 34, 62, 24)
arrow(76, 34, 88, 24)

# Legend
handles = [
    Rectangle((0, 0), 1, 1, fc=INPUT, ec=INPUT_EDGE),
    Rectangle((0, 0), 1, 1, fc=PHASE, ec=PHASE_EDGE),
    Rectangle((0, 0), 1, 1, fc=OUTPUT, ec=OUTPUT_EDGE),
]
labels = ["Primary sources / configuration", "Processing phase", "Distributed output"]
ax.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8.5,
          bbox_to_anchor=(0.5, -0.08))

out_path = OUT / "fig0_workflow.png"
plt.savefig(out_path)
plt.close(fig)
log.info("Workflow figure -> %s", out_path)

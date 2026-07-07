#!/usr/bin/env python
"""Etapa 12 — Diagrama de flujo del proceso de construcción del dataset.

Genera una figura estilo "workflow" del pipeline (para la sección Experimental
Design del data paper), independiente de nombres de scripts o del repositorio.
Salida: data/processed/reportes/fig0_workflow.png (300 dpi).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D

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

# Colours
INPUT = "#DFE6EC"
STAGE = "#F1E7EA"
STAGE_EDGE = "#7A1737"
QC = "#EAF3EA"
OUTPUT = "#FFEEDD"
OUT_EDGE = "#B26D2A"

fig, ax = plt.subplots(figsize=(11, 8.5))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, text, fill=STAGE, edge=STAGE_EDGE, fontsize=8.5, weight="normal"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                       fc=fill, ec=edge, linewidth=1.2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight=weight, wrap=True)


def arrow(x1, y1, x2, y2, style="->", color="#333333"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=13,
                        color=color, linewidth=1.1)
    ax.add_patch(a)


# ---- Row 0 : title band ----
ax.text(50, 96, "Hidro-MX: dataset construction workflow",
        ha="center", va="center", fontsize=13, fontweight="bold", color=STAGE_EDGE)

# ---- Row 1 : primary data sources ----
box(3, 82, 28, 8,
    "SOURCE A\nCONAGUA-SIH\nmaster catalogs and\nper-station daily series",
    fill=INPUT, edge="#3E5B78", fontsize=8.5, weight="bold")
box(37, 82, 26, 8,
    "SOURCE B\nBasin configuration\n(pilot basins, bounding\nboxes, target resolution)",
    fill=INPUT, edge="#3E5B78", fontsize=8.5, weight="bold")
box(69, 82, 28, 8,
    "SOURCE C\nINEGI CEM 3.0\nstate-level digital\nelevation model tiles",
    fill=INPUT, edge="#3E5B78", fontsize=8.5, weight="bold")

# ---- Row 2: Stage 1 catalog + Stage 2 candidate selection ----
box(3, 68, 41, 10,
    "STAGE 1 — Catalog acquisition\n"
    "Download master catalogs; normalise headers to canonical schema\n"
    "(clave, name, coordinates, hydrological region, basin, altitude).\n"
    "Record source URL, SHA-256 and UTC timestamp per file.")
arrow(17, 82, 17, 78)

box(56, 68, 41, 10,
    "STAGE 2 — Candidate-station filter\n"
    "Retain stations whose hydrological region matches\n"
    "the pilot configuration → candidate universe\n"
    "(hydrometric and climatological).")
arrow(50, 82, 76, 78)
arrow(24, 73, 56, 73)

# ---- Row 3: Stage 3 time-series download ----
box(3, 54, 94, 10,
    "STAGE 3 — Time-series retrieval\n"
    "For every candidate station, download the daily record over the full historical horizon.\n"
    "Rate-limit and back-off policies for provider WAF; per-file SHA-256 registered in the provenance manifest.")
arrow(76, 68, 76, 64)
arrow(24, 68, 24, 64)

# ---- Row 4: Stage 4 canonical + QC ----
box(3, 38, 55, 12,
    "STAGE 4 — Canonical schema and quality control\n"
    "Robust parser (header variants, date formats).\n"
    "Sentinel → NaN; per-station outlier flag (physical bounds);\n"
    "short-gap imputation (cubic spline, linear fallback).\n"
    "Schema validation (types, ranges, allowed labels).\n"
    "Quality flags: 0 = original, 1 = imputed, 2 = outlier.",
    fill=QC, edge="#2E7D5B")
arrow(30, 54, 30, 50)

# ---- Row 4b: Stage 5 DEM preparation ----
box(63, 38, 34, 12,
    "STAGE 5 — DEM preparation per basin\n"
    "Mosaic of state tiles;\n"
    "clip to curated bounding box;\n"
    "resample to target grid.")
arrow(83, 82, 83, 50)
arrow(50, 82, 80, 50)

# ---- Row 5: Stage 6 delineation ----
box(63, 22, 34, 12,
    "STAGE 6 — Watershed delineation\n"
    "Fill → flow direction → flow accumulation → snap\n"
    "pour points (gauged stations) → watershed.\n"
    "Per-basin polygons with area, mean elevation, mean slope.")
arrow(80, 38, 80, 34)

# ---- Row 5b: Stage 7 coverage refinement + features ----
box(3, 22, 55, 12,
    "STAGE 7 — Coverage refinement and feature engineering\n"
    "Compute per-station coverage over the target window;\n"
    "apply per-type thresholds (main and extended sets).\n"
    "Match hydrometric stations to k nearest climate neighbours.\n"
    "Generate lagged features and rolling means per station.",
    fill=QC, edge="#2E7D5B")
arrow(30, 38, 30, 34)

# ---- Row 6: outputs ----
box(3, 4, 22, 12,
    "OUTPUT 1\nCanonical time-series tables\n(hydrometric + climatological,\npartitioned by year).",
    fill=OUTPUT, edge=OUT_EDGE, weight="bold", fontsize=8.5)
box(28, 4, 22, 12,
    "OUTPUT 2\nStation manifests\n(candidates, main set,\nextended set + neighbours).",
    fill=OUTPUT, edge=OUT_EDGE, weight="bold", fontsize=8.5)
box(53, 4, 22, 12,
    "OUTPUT 3\nPer-basin geospatial\nlayer + polygons of\ndelineated sub-basins.",
    fill=OUTPUT, edge=OUT_EDGE, weight="bold", fontsize=8.5)
box(78, 4, 19, 12,
    "OUTPUT 4\nModel-ready\nfeature table\n(lags + rolling means).",
    fill=OUTPUT, edge=OUT_EDGE, weight="bold", fontsize=8.5)

arrow(14, 22, 14, 16)
arrow(36, 22, 36, 16)
arrow(80, 22, 63, 16)
arrow(45, 22, 88, 16)

# ---- Legend ----
handles = [
    Rectangle((0, 0), 1, 1, fc=INPUT, ec="#3E5B78"),
    Rectangle((0, 0), 1, 1, fc=STAGE, ec=STAGE_EDGE),
    Rectangle((0, 0), 1, 1, fc=QC, ec="#2E7D5B"),
    Rectangle((0, 0), 1, 1, fc=OUTPUT, ec=OUT_EDGE),
]
labels = ["Primary source", "Processing stage", "Quality control / feature stage", "Distributed output"]
ax.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
          bbox_to_anchor=(0.5, -0.03))

out_path = OUT / "fig0_workflow.png"
plt.savefig(out_path)
plt.close(fig)
log.info("Workflow figure -> %s", out_path)

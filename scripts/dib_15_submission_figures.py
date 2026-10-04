#!/usr/bin/env python
"""Paso 2, T6 — figuras con los nombres de la guía de autores de Data in Brief.

Copia los TIFF de data/processed/reportes/ (Fig1–Fig7) y de results/dib_revision/figs/
(suplementarias) a dist/figuras_envio/ como Figure_1.tif … Figure_7.tif, Figure_S1.tif y
Figure_S2.tif, y registra tamaño en píxeles y dpi. Ancho mínimo a página completa:
2244 px (190 mm a 300 dpi).

Salida: dist/figuras_envio/*.tif y results/dib_revision/figuras_envio.csv
Uso:  python scripts/dib_15_submission_figures.py
"""
from __future__ import annotations

import shutil

import pandas as pd
from PIL import Image

from hidroxai_mx.utils import PROCESSED, ROOT, get_logger

log = get_logger("dib_15")
OUT = ROOT / "dist" / "figuras_envio"
REP = PROCESSED / "reportes"
FIGS = ROOT / "results" / "dib_revision" / "figs"
MIN_FULL_PAGE_PX = 2244

MAPA = {
    "Figure_1.tif": REP / "Fig1_workflow.tif",
    "Figure_2.tif": REP / "Fig2_station_map.tif",
    "Figure_3.tif": REP / "Fig3_quality_flags.tif",
    "Figure_4.tif": REP / "Fig4_inventory_coverage.tif",
    "Figure_5.tif": REP / "Fig5_streamflow_by_region.tif",
    "Figure_6.tif": REP / "Fig6_climatology_annual.tif",
    "Figure_7.tif": REP / "Fig7_precip_streamflow.tif",
    "Figure_S1.tif": FIGS / "figS_imputation_error_vs_L.tif",
    "Figure_S2.tif": FIGS / "figS_outliers_examples.tif",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for dest, src in MAPA.items():
        shutil.copy2(src, OUT / dest)
        with Image.open(src) as im:
            w, h = im.size
            dpi = im.info.get("dpi", (None, None))[0]
        rows.append({"archivo": dest, "origen": src.relative_to(ROOT).as_posix(), "ancho_px": w,
                     "alto_px": h, "dpi": round(float(dpi)) if dpi else None,
                     "ancho_mm_a_300dpi": round(w / 300 * 25.4, 1),
                     "apta_pagina_completa": w >= MIN_FULL_PAGE_PX})
    t = pd.DataFrame(rows)
    t.to_csv(ROOT / "results" / "dib_revision" / "figuras_envio.csv", index=False)
    log.info("%d figuras -> %s; %d con ancho ≥ %d px", len(t), OUT,
             int(t["apta_pagina_completa"].sum()), MIN_FULL_PAGE_PX)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E5 — validación independiente del área de las subcuencas.

Verificador congelado (results/dib_revision/proof_ledger.md, E5):
- Referencia A (área de cuenca en el catálogo SIH): no disponible, el catálogo no la trae.
- Referencia B: UPLAND_SKM de HydroRIVERS v1.0 (Lehner & Grill, 2013) en el tramo más
  cercano al pour point ajustado, a ≤ 1,000 m. Sin tramo a ≤ 1,000 m → "sin referencia".
- Métricas: error relativo de área, mediana |error|, fracción dentro de ±20 %, lista de
  casos > 50 % con diagnóstico basado solo en evidencia del archivo.

Diagnóstico adicional (no sustituye al verificador): como el área aportante crece a lo
largo del tramo, se reporta también si el área delineada cae dentro del intervalo del
tramo [UPLAND_SKM − CATCH_SKM, UPLAND_SKM].

HydroRIVERS se lee del archivo local indicado con --hydrorivers (shapefile NA v1.0,
https://www.hydrosheds.org; términos de uso de HydroSHEDS, atribución requerida).

Salidas: results/dib_revision/subbasin_validation.csv y e5_validation.json
Uso:  python scripts/dib_05_subbasin_validation.py --hydrorivers PATH/HydroRIVERS_v10_na.shp
"""
from __future__ import annotations

import json
from pathlib import Path

import click
import geopandas as gpd
import pandas as pd

from hidroxai_mx.utils import ROOT, get_logger, load_cuencas

log = get_logger("dib_05")
OUT = ROOT / "results" / "dib_revision"
CRS_M = "EPSG:6372"
MAX_DIST_M = 1000.0
HR_MIN_KM2 = 10.0


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


@click.command()
@click.option("--hydrorivers", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--cuencas-dir", type=click.Path(path_type=Path), default=None,
              help="GeoPackages a validar (def.: polígonos re-delineados y deduplicados de la auditoría).")
@click.option("--published-dir", type=click.Path(path_type=Path), default=None,
              help="GeoPackages v2026.06 para comparar las áreas publicadas (opcional).")
def main(hydrorivers: Path, cuencas_dir: Path | None, published_dir: Path | None) -> None:
    cfg = load_cuencas()
    cuencas_dir = cuencas_dir or ROOT / "data/interim/dib_revision/cuencas_redelin_dedup"
    polys, pts = [], []
    for c in cfg["cuencas_piloto"]:
        g = cuencas_dir / f"{_slug(c['nombre'])}.gpkg"
        polys.append(gpd.read_file(g, layer="cuenca"))
        pts.append(gpd.read_file(g, layer="pour_points"))
    polys = pd.concat(polys, ignore_index=True)
    pts = gpd.GeoDataFrame(pd.concat(pts, ignore_index=True)).to_crs(CRS_M)
    pts = pts[pts["poligono_en_unidad"] == pts["unidad"]]
    df = pts[["clave_estacion", "unidad", "snap_dist_m", "geometry"]].merge(
        polys[["clave_estacion", "area_km2", "toca_bbox"]], on="clave_estacion")

    xs = [b for c in cfg["cuencas_piloto"] for b in (c["bbox"][0], c["bbox"][2])]
    ys = [b for c in cfg["cuencas_piloto"] for b in (c["bbox"][1], c["bbox"][3])]
    hr = gpd.read_file(hydrorivers, bbox=(min(xs), min(ys), max(xs), max(ys)),
                       columns=["HYRIV_ID", "UPLAND_SKM", "CATCH_SKM", "ORD_STRA"])
    hr = hr.to_crs(CRS_M)
    log.info("HydroRIVERS: %d tramos en la extensión de las unidades", len(hr))

    joined = gpd.sjoin_nearest(gpd.GeoDataFrame(df, geometry="geometry", crs=CRS_M), hr,
                               how="left", max_distance=MAX_DIST_M, distance_col="dist_tramo_m")
    joined = joined.sort_values("dist_tramo_m").drop_duplicates("clave_estacion")
    joined["area_ref_km2"] = joined["UPLAND_SKM"]
    joined["err_rel"] = joined["area_km2"] / joined["area_ref_km2"] - 1
    lo = joined["UPLAND_SKM"] - joined["CATCH_SKM"]
    joined["dentro_intervalo_tramo"] = joined["area_km2"].between(lo * 0.999, joined["UPLAND_SKM"] * 1.001)

    def _diag(r) -> str:
        if pd.isna(r["area_ref_km2"]):
            return "sin tramo HydroRIVERS a ≤ 1 km"
        if abs(r["err_rel"]) <= 0.5:
            return ""
        why = []
        if r["toca_bbox"]:
            why.append("truncada por el bbox de la unidad")
        if r["area_km2"] < HR_MIN_KM2:
            why.append(f"cuenca < {HR_MIN_KM2:.0f} km² (bajo el umbral de HydroRIVERS)")
        ratio = r["area_km2"] / r["area_ref_km2"]
        if ratio > 5 or ratio < 0.2:
            why.append(f"razón de áreas {ratio:.2g}: posible ajuste a un cauce distinto (inferencia)")
        return "; ".join(why) or "sin causa identificable en el archivo"

    joined["diagnostico"] = joined.apply(_diag, axis=1)

    if published_dir is not None:
        mp = pd.read_csv(OUT / "published_polygon_mapping.csv", dtype={"clave": str})
        pub = mp.groupby("clave")["area_km2_publicada"].max().rename("area_km2_v2026_06")
        joined = joined.merge(pub, left_on="clave_estacion", right_index=True, how="left")
        joined["err_rel_v2026_06"] = joined["area_km2_v2026_06"] / joined["area_ref_km2"] - 1

    cols = [c for c in ["clave_estacion", "unidad", "area_km2", "area_km2_v2026_06", "area_ref_km2",
                        "CATCH_SKM", "ORD_STRA", "dist_tramo_m", "snap_dist_m", "toca_bbox",
                        "err_rel", "err_rel_v2026_06", "dentro_intervalo_tramo", "diagnostico"]
            if c in joined.columns]
    out = joined[cols].sort_values("err_rel", key=lambda s: s.abs(), ascending=False)
    out.to_csv(OUT / "subbasin_validation.csv", index=False)

    m = out[out["area_ref_km2"].notna()]
    big = m[m["area_km2"] >= HR_MIN_KM2]
    res = {
        "subcuencas": int(len(out)),
        "con_referencia": int(len(m)),
        "sin_referencia": int(out["area_ref_km2"].isna().sum()),
        "mediana_abs_err_pct": round(float(m["err_rel"].abs().median() * 100), 1),
        "frac_dentro_20pct": round(float((m["err_rel"].abs() <= 0.2).mean()), 3),
        "frac_dentro_intervalo_tramo": round(float(m["dentro_intervalo_tramo"].mean()), 3),
        "solo_area_ge_10km2": {
            "n": int(len(big)),
            "mediana_abs_err_pct": round(float(big["err_rel"].abs().median() * 100), 1) if len(big) else None,
            "frac_dentro_20pct": round(float((big["err_rel"].abs() <= 0.2).mean()), 3) if len(big) else None,
        },
        "casos_mayores_50pct": m.loc[m["err_rel"].abs() > 0.5,
                                     ["clave_estacion", "unidad", "area_km2", "area_ref_km2",
                                      "diagnostico"]].round(3).to_dict("records"),
    }
    if "err_rel_v2026_06" in m.columns:
        both = m[m["area_km2_v2026_06"].notna()]
        res["comparacion_v2026_06"] = {
            "n": int(len(both)),
            "mediana_abs_err_pct_v2026_06": round(float(both["err_rel_v2026_06"].abs().median() * 100), 1),
            "mediana_abs_err_pct_v2026_10": round(float(both["err_rel"].abs().median() * 100), 1),
        }
    (OUT / "e5_validation.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("E5: %s", {k: v for k, v in res.items() if k != "casos_mayores_50pct"})


if __name__ == "__main__":
    main()

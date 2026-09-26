#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E2 — deduplicación de subcuencas.

Los bbox de las unidades operativas se traslapan, así que una estación puede delinearse
en dos unidades. Regla congelada (results/dib_revision/proof_ledger.md, E2), aplicada en
orden a cada estación con más de un polígono:

  1. Descartar el polígono que toca el borde del bbox de su unidad: distancia mínima
     entre el contorno del polígono y el contorno del bbox ≤ 1.5 × tamaño de celda del
     CEM de esa unidad, medida en EPSG:6372.
  2. Si ninguno o ambos lo tocan: conservar el de la unidad cuyo region_hidrologica (conf)
     coincide con el de la estación en el catálogo.
  3. Si persiste el empate: conservar el de mayor área.

Entrada: GeoPackages re-delineados (capas cuenca y pour_points, etapa 06).
Salida:
    <out-dir>/<unidad>.gpkg         capas `cuenca` (sin duplicados) y `pour_points`
    <out-dir>/delineation_params.json (copia)
    results/dib_revision/dedup_log.csv
    results/dib_revision/table3_dedup_audit.csv
    results/dib_revision/e2_dedup.json

Uso:  python scripts/dib_02_dedup_subbasins.py --in-dir DIR --out-dir DIR
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import click
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from hidroxai_mx.utils import ROOT, get_logger, load_cuencas

log = get_logger("dib_02")
OUT = ROOT / "results" / "dib_revision"
CRS_M = "EPSG:6372"


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


def _bbox_boundary_m(bbox) -> object:
    """Contorno del bbox (EPSG:4326) en EPSG:6372, densificado para seguir la curvatura."""
    g = gpd.GeoSeries([box(*bbox).segmentize(0.01)], crs="EPSG:4326").to_crs(CRS_M)
    return g.iloc[0].boundary


@click.command()
@click.option("--in-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--out-dir", type=click.Path(path_type=Path), required=True)
def main(in_dir: Path, out_dir: Path) -> None:
    cfg = load_cuencas()
    params = json.loads((in_dir / "delineation_params.json").read_text(encoding="utf-8"))
    polys, points = [], []
    for c in cfg["cuencas_piloto"]:
        unit, slug = c["nombre"], _slug(c["nombre"])
        gpkg = in_dir / f"{slug}.gpkg"
        p = gpd.read_file(gpkg, layer="cuenca").to_crs(CRS_M)
        q = gpd.read_file(gpkg, layer="pour_points").to_crs(CRS_M)
        cell = max(params["unidades"][unit]["celda_m_aprox"])
        edge = _bbox_boundary_m(c["bbox"])
        p["dist_borde_bbox_m"] = p.geometry.boundary.distance(edge).round(1)
        p["toca_bbox"] = p["dist_borde_bbox_m"] <= 1.5 * cell
        p["region_unidad"] = str(c["region_hidrologica"])
        p["tol_borde_m"] = round(1.5 * cell, 1)
        polys.append(p)
        points.append(q)
    polys = gpd.GeoDataFrame(pd.concat(polys, ignore_index=True), crs=CRS_M)
    points = gpd.GeoDataFrame(pd.concat(points, ignore_index=True), crs=CRS_M)

    log_rows, keep_idx = [], []
    for clave, g in polys.groupby("clave_estacion"):
        if len(g) == 1:
            keep_idx.append(g.index[0])
            log_rows.append({"clave_estacion": clave, "unidades": g["unidad"].iloc[0],
                             "n_poligonos": 1, "regla": "unica", "unidad_conservada": g["unidad"].iloc[0],
                             "toca_bbox_conservado": bool(g["toca_bbox"].iloc[0]),
                             "detalle": ""})
            continue
        cand, rule = g, None
        touch = cand["toca_bbox"]
        if touch.any() and not touch.all():
            cand, rule = cand[~touch], "1_borde_bbox"
        if len(cand) > 1:
            reg = cand[cand["region_unidad"] == cand["region_hidrologica_estacion"]]
            if 0 < len(reg) < len(cand):
                cand, rule = reg, (rule + "+" if rule else "") + "2_region"
        if len(cand) > 1:
            cand = cand.loc[[cand["area_km2"].idxmax()]]
            rule = (rule + "+" if rule else "") + "3_area"
        kept = cand.index[0]
        keep_idx.append(kept)
        detail = "; ".join(f"{r.unidad}: toca={bool(r.toca_bbox)} d={r.dist_borde_bbox_m} m "
                           f"RH={r.region_unidad} área={r.area_km2:.2f} km²"
                           for r in g.itertuples())
        log_rows.append({"clave_estacion": clave, "unidades": ";".join(g["unidad"]),
                         "n_poligonos": len(g), "regla": rule,
                         "unidad_conservada": polys.loc[kept, "unidad"],
                         "toca_bbox_conservado": bool(polys.loc[kept, "toca_bbox"]),
                         "detalle": detail})

    no_poly = sorted(set(points["clave_estacion"]) - set(polys["clave_estacion"]))
    for clave in no_poly:
        q = points[points["clave_estacion"] == clave]
        log_rows.append({"clave_estacion": clave, "unidades": ";".join(q["unidad"]),
                         "n_poligonos": 0, "regla": "sin_poligono", "unidad_conservada": None,
                         "toca_bbox_conservado": None,
                         "detalle": "salida compartida con " + ", ".join(
                             sorted(set(q["salida_compartida_con"].dropna())))})
    dlog = pd.DataFrame(log_rows).sort_values(["n_poligonos", "clave_estacion"], ascending=[False, True])
    dlog.to_csv(OUT / "dedup_log.csv", index=False)

    kept = polys.loc[keep_idx].copy()
    assigned = dict(zip(kept["clave_estacion"], kept["unidad"], strict=True))
    points["poligono_en_unidad"] = points["clave_estacion"].map(assigned)

    out_dir.mkdir(parents=True, exist_ok=True)
    table3 = []
    for c in cfg["cuencas_piloto"]:
        unit, slug = c["nombre"], _slug(c["nombre"])
        dest = out_dir / f"{slug}.gpkg"
        if dest.exists():
            dest.unlink()
        ku = kept[kept["unidad"] == unit].drop(columns=["region_unidad", "tol_borde_m"])
        pu = points[points["unidad"] == unit]
        ku.to_file(dest, layer="cuenca", driver="GPKG")
        pu.to_file(dest, layer="pour_points", driver="GPKG")
        table3.append({"unidad": unit, "region_hidrologica": c["region_hidrologica"],
                       "resolucion_cem_m": c.get("cem_resolucion_m", 30),
                       "estaciones_en_bbox": int(len(pu)),
                       "poligonos_tras_dedup": int(len(ku)),
                       "poligonos_que_tocan_bbox": int(ku["toca_bbox"].sum())})
    shutil.copy(in_dir / "delineation_params.json", out_dir / "delineation_params.json")
    t3 = pd.DataFrame(table3)
    t3.loc[len(t3)] = {"unidad": "Total (únicas)", "region_hidrologica": "",
                       "resolucion_cem_m": "",
                       "estaciones_en_bbox": int(points["clave_estacion"].nunique()),
                       "poligonos_tras_dedup": int(len(kept)),
                       "poligonos_que_tocan_bbox": int(kept["toca_bbox"].sum())}
    t3.to_csv(OUT / "table3_dedup_audit.csv", index=False)

    counts = dlog["n_poligonos"].value_counts().to_dict()
    result = {
        "filas_estacion_unidad": int(len(points)),
        "poligonos_antes": int(len(polys)),
        "estaciones_unicas_en_bbox": int(points["clave_estacion"].nunique()),
        "estaciones_con_mas_de_un_poligono": int((dlog["n_poligonos"] > 1).sum()),
        "reglas_aplicadas": dlog.loc[dlog["n_poligonos"] > 1, "regla"].value_counts().to_dict(),
        "poligonos_despues": int(len(kept)),
        "estaciones_sin_poligono": no_poly,
        "conservados_que_tocan_bbox": kept.loc[kept["toca_bbox"], ["clave_estacion", "unidad",
                                                                    "dist_borde_bbox_m", "area_km2"]
                                               ].to_dict("records"),
        "gate_una_por_estacion": bool(set(counts) <= {1}),
        "n_por_estacion": {int(k): int(v) for k, v in counts.items()},
    }
    (OUT / "e2_dedup.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str),
                                       encoding="utf-8")
    log.info("E2: %d polígonos → %d; sin polígono: %s; conservados que tocan bbox: %d",
             len(polys), len(kept), no_poly, int(kept["toca_bbox"].sum()))


if __name__ == "__main__":
    main()

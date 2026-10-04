#!/usr/bin/env python
"""Paso 2, T3 — correspondencia de las cuencas piloto con cuencas oficiales (revisor 4).

Regla congelada (proof_ledger.md, P2-T3): solo se dibuja un contorno oficial cuando la
correspondencia es inequívoca por nombre oficial; si no, se anota y no se fuerza.

Capa: CNA (1998) "Cuencas Hidrológicas" 1:250 000, distribuida por CONABIO (cue250kgw).
Entrada: conf/cuencas_piloto.yaml (contornos_cuencas_piloto, cuencas_piloto)
Salida : results/dib_revision/pilot_basin_outlines.csv

Uso:  python scripts/dib_14_pilot_basin_outlines.py
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from hidroxai_mx.utils import DATA, ROOT, get_logger, load_cuencas

log = get_logger("dib_14")
LAYER = DATA / "scratch" / "limites" / "cue250kgw" / "cue250kgw.shp"
OUT = ROOT / "results" / "dib_revision" / "pilot_basin_outlines.csv"
CRS_M = "EPSG:6372"


def main() -> None:
    cfg = load_cuencas()
    cu = gpd.read_file(LAYER).to_crs(CRS_M)
    cu = cu.dissolve(by=["IDCUENCA", "CUENCA", "ID_RH", "REGION"]).reset_index()
    cu["area_km2"] = cu.area / 1e6
    units = {u["nombre"]: u for u in cfg["cuencas_piloto"]}
    rows = []
    for e in cfg["contornos_cuencas_piloto"]:
        if "cuencas_oficiales" in e:
            sel = cu[cu["CUENCA"].isin(e["cuencas_oficiales"])]
            missing = set(e["cuencas_oficiales"]) - set(sel["CUENCA"])
            if missing:
                raise SystemExit(f"Cuencas no encontradas en la capa: {missing}")
            corr, dib, nota = "inequívoca por nombre oficial de cuenca", True, ""
        elif "region_oficial" in e:
            sel = cu[cu["REGION"] == e["region_oficial"]]
            corr, dib = "inequívoca por nombre oficial de región", False
            nota = (f"coincide con la región hidrológica {int(sel['ID_RH'].iloc[0])}, "
                    "cuyo contorno ya se dibuja en Fig. 2")
        else:
            u = units[e["unidad"]]
            b = gpd.GeoSeries([box(*u["bbox"])], crs="EPSG:4326").to_crs(CRS_M).iloc[0]
            sel = cu[(cu["ID_RH"] == u["region_hidrologica"]) & cu.intersects(b)].copy()
            sel["frac_recuadro"] = sel.intersection(b).area / b.area
            sel = sel.sort_values("frac_recuadro", ascending=False)
            corr, dib = "no inequívoca", False
            nota = ("ninguna cuenca oficial lleva ese nombre; la unidad se define por su recuadro. "
                    "Cuencas que lo cruzan (fracción del recuadro): "
                    + "; ".join(f"{r.CUENCA} {r.frac_recuadro:.2f}" for r in sel.itertuples()))
        for r in sel.itertuples():
            rows.append({"cuenca_piloto": e["cuenca_piloto"], "id_rh": int(r.ID_RH), "region": r.REGION,
                         "idcuenca": int(r.IDCUENCA), "cuenca_oficial": r.CUENCA,
                         "area_km2": round(r.area_km2, 1), "correspondencia": corr,
                         "se_dibuja": dib, "nota": nota})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    log.info("%d filas -> %s", len(rows), OUT)


if __name__ == "__main__":
    main()

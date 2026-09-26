#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E1 — conciliación de conteos del release v2026.06.

Reconstruye, desde los archivos distribuidos, el embudo de estaciones por tipo:

    catálogo → región hidrológica (candidatas) → archivo descargado
    → ≥1 dato en 2010–2025 → cobertura ≥ umbral → dentro de algún bbox → con polígono

y cuenta las observaciones de tres formas (filas totales, filas con valor, filas con
valor en 2010–2025), las filas (clave, fecha) duplicadas y la composición de `calidad`
sobre todas las filas y solo sobre filas con valor.

Las funciones de lectura y cobertura son las mismas que usa el pipeline (etapas 04/05).
Con --probe consulta de nuevo, secuencialmente, las URLs de las estaciones sin archivo
para registrar el motivo (estado HTTP a la fecha de la consulta).

Salidas en results/dib_revision/:
    counts_reconciliation.csv        embudo agregado por tipo
    station_funnel_<tipo>.csv        embudo por estación
    missing_downloads.csv            estaciones sin archivo y motivo
    observation_counts.csv           filas, filas con valor, ventana, duplicados
    calidad_composition.csv          composición de la bandera de calidad
    published_polygon_mapping.csv    polígono publicado ↔ estación (reconstruido y verificado)
    e1_counts.json                   cifras para numbers.json

Uso:  python scripts/dib_01_reconcile_counts.py [--probe]
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import click
import numpy as np
import pandas as pd

from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, RAW, ROOT, get_logger, load_cuencas

log = get_logger("dib_01")
OUT = ROOT / "results" / "dib_revision"
TYPES = {"hidrometricas": "gasto_medio_m3s", "climatologicas": "precip_mm"}
# Polígonos de subcuencas de v2026.06 (retirados en v2026.10), conservados para auditoría.
PUBLISHED_CUENCAS = ROOT / "data" / "interim" / "dib_revision" / "v2026.06_processed" / "cuencas"


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_").replace("-", "_")


def _station_window_stats(tipo: str, clave: str, value_col: str, t0: str, t1: str) -> dict:
    """Días con valor en la ventana, igual que `05_select_stations._coverage`."""
    f = RAW / "sih_series" / tipo / f"{clave}.csv"
    if not f.exists():
        return {"downloaded": False, "readable": False, "n_valid_window": 0}
    try:
        df = conagua.read_series_csv(f)
    except Exception as exc:  # noqa: BLE001
        log.warning("%s/%s ilegible: %s", tipo, clave, exc)
        return {"downloaded": True, "readable": False, "n_valid_window": 0}
    if value_col not in df.columns:
        return {"downloaded": True, "readable": True, "n_valid_window": 0}
    w = df[(df["fecha"] >= t0) & (df["fecha"] <= t1)]
    return {"downloaded": True, "readable": True, "n_valid_window": int(w[value_col].notna().sum())}


def _probe(url: str) -> dict:
    import requests

    try:
        with requests.get(url, stream=True, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0 (HidroXAI-MX ingest)"}) as r:
            head = next(r.iter_content(512), b"")
            ctype = r.headers.get("Content-Type", "")
            status = r.status_code
    except Exception as exc:  # noqa: BLE001
        return {"http_status": None, "reason": f"error de red: {type(exc).__name__}"}
    text = head.decode("latin-1", "replace").lower()
    if status == 404:
        reason = "no existe en el portal (HTTP 404)"
    elif status in (403, 429, 503):
        reason = f"bloqueo/limitación del servidor (HTTP {status})"
    elif status == 200 and ("<html" in text or "html" in ctype.lower()):
        reason = "HTTP 200 con página HTML, no CSV (redirección o firewall)"
    elif status == 200 and not head.strip():
        reason = "HTTP 200 con cuerpo vacío"
    elif status == 200 and "fecha" in text:
        reason = "disponible a la fecha de consulta; no se obtuvo en la descarga original"
    elif status == 200:
        reason = "HTTP 200 sin encabezado de serie reconocible"
    else:
        reason = f"HTTP {status}"
    return {"http_status": status, "reason": reason}


def _observation_counts_pandas(tipo: str, value_col: str, t0: str, t1: str) -> tuple[dict, pd.DataFrame]:
    df = pd.read_parquet(PROCESSED / f"series_{tipo}.parquet",
                         columns=["clave_estacion", "fecha", value_col, "calidad"])
    return _summarise(df, tipo, value_col, t0, t1)


def _observation_counts_arrow(tipo: str, value_col: str, t0: str, t1: str) -> tuple[dict, pd.DataFrame]:
    """Igual que la versión pandas pero por partición anual (la serie clima tiene ~55 M filas)."""
    import pyarrow.dataset as pads

    dset = pads.dataset(PROCESSED / f"series_{tipo}.parquet", format="parquet", partitioning="hive")
    acc = {"rows_total": 0, "rows_with_value": 0, "rows_window": 0, "with_value_window": 0,
           "duplicate_rows": 0}
    comp = {}
    for frag in dset.get_fragments():
        t = frag.to_table(columns=["clave_estacion", "fecha", value_col, "calidad"])
        part = t.to_pandas()
        part["clave_estacion"] = part["clave_estacion"].astype("category")
        s, c = _summarise(part, tipo, value_col, t0, t1, raw=True)
        for k in acc:
            acc[k] += s[k]
        for key, n in c.items():
            comp[key] = comp.get(key, 0) + n
    return _finish(acc, comp, tipo)


def _summarise(df: pd.DataFrame, tipo: str, value_col: str, t0: str, t1: str, raw: bool = False):
    fecha = pd.to_datetime(df["fecha"])
    has = df[value_col].notna()
    win = (fecha >= t0) & (fecha <= t1)
    acc = {
        "rows_total": int(len(df)),
        "rows_with_value": int(has.sum()),
        "rows_window": int(win.sum()),
        "with_value_window": int((has & win).sum()),
        "duplicate_rows": int(df.duplicated(["clave_estacion", "fecha"]).sum()),
    }
    cal = df["calidad"].fillna(0).astype(int)
    comp = {}
    for scope, mask in (("todas_las_filas", np.ones(len(df), bool)),
                        ("filas_con_valor", has.to_numpy()),
                        ("filas_con_valor_2010_2025", (has & win).to_numpy())):
        vc = cal[mask].value_counts()
        for q, n in vc.items():
            comp[(scope, int(q))] = comp.get((scope, int(q)), 0) + int(n)
    if raw:
        return acc, comp
    return _finish(acc, comp, tipo)


def _finish(acc: dict, comp: dict, tipo: str):
    rows = []
    for (scope, q), n in sorted(comp.items()):
        rows.append({"tipo": tipo, "ambito": scope, "calidad": q, "n": n})
    cdf = pd.DataFrame(rows)
    cdf["pct"] = cdf["n"] / cdf.groupby("ambito")["n"].transform("sum") * 100
    return {"tipo": tipo, **acc}, cdf


def _published_polygon_mapping(sel_pub: pd.DataFrame, cfg: dict, cuencas_dir) -> pd.DataFrame:
    """VALUE de cada polígono publicado ↔ estación, reconstruido como lo hizo la etapa 06
    (pour points = estaciones seleccionadas dentro del bbox, en orden del archivo; whitebox
    numera las salidas por registro, desde 1) y verificado por distancia estación→polígono."""
    import geopandas as gpd

    rows = []
    for c in cfg["cuencas_piloto"]:
        slug = _slug(c["nombre"])
        min_lon, min_lat, max_lon, max_lat = c["bbox"]
        sub = sel_pub[sel_pub["longitud"].between(min_lon, max_lon)
                      & sel_pub["latitud"].between(min_lat, max_lat)].reset_index(drop=True)
        gpkg = cuencas_dir / f"{slug}.gpkg"
        polys = gpd.read_file(gpkg)
        pts = gpd.GeoDataFrame(sub, geometry=gpd.points_from_xy(sub["longitud"], sub["latitud"]),
                               crs="EPSG:4326").to_crs(polys.crs)
        by_value = polys.dissolve(by="VALUE", as_index=True)
        n_parts = polys.groupby("VALUE").size()
        for i, r in sub.iterrows():
            value = i + 1
            if value in by_value.index:
                geom = by_value.loc[value, "geometry"]
                dist = float(pts.geometry.iloc[i].distance(geom))
                area = float(polys.loc[polys["VALUE"] == value, "area_km2"].sum())
                parts = int(n_parts.get(value, 0))
            else:
                dist, area, parts = np.nan, np.nan, 0
            rows.append({"unidad": c["nombre"], "region_unidad": c["region_hidrologica"],
                         "VALUE": value, "clave": r["clave"],
                         "region_estacion": r["region_hidrologica"],
                         "tiene_poligono": parts > 0, "partes": parts,
                         "dist_estacion_poligono_m": round(dist, 1) if dist == dist else np.nan,
                         "area_km2_publicada": area})
    return pd.DataFrame(rows)


@click.command()
@click.option("--probe", is_flag=True, help="Re-consultar las URLs de estaciones sin archivo.")
@click.option("--probe-delay", type=float, default=3.0, show_default=True)
@click.option("--published-cuencas", type=click.Path(path_type=Path), default=PUBLISHED_CUENCAS,
              show_default=True, help="GeoPackages de subcuencas v2026.06 (auditoría); se omite si no existe.")
@click.option("--suffix", default="", help="Sufijo para los archivos de salida (p. ej. _v2026_10).")
def main(probe: bool, probe_delay: float, published_cuencas: Path, suffix: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_cuencas()
    regiones = {str(r) for r in cfg["regiones_hidrologicas"]}
    crit = cfg["criterios_seleccion_estaciones"]
    t0, t1 = crit["periodo"]["inicio"], crit["periodo"]["fin"]
    n_days = (pd.Timestamp(t1) - pd.Timestamp(t0)).days + 1
    thr = crit["cobertura_minima"]

    funnel, missing_rows, e1 = [], [], {"fecha_conciliacion": date.today().isoformat(),
                                         "ventana": [t0, t1], "dias_ventana": n_days}
    sel_pub_h = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})

    for tipo, value_col in TYPES.items():
        cat = conagua.read_catalog(RAW / "sih" / f"catalogo_{tipo}.csv")
        cand = cat[cat["region_hidrologica"].isin(regiones)].copy()
        cand_pub = pd.read_csv(PROCESSED / f"estaciones_candidatas_{tipo}.csv", dtype={"clave": str})
        log.info("%s: catálogo=%d candidatas=%d (publicadas=%d)", tipo, len(cat), len(cand), len(cand_pub))

        stats = [_station_window_stats(tipo, k, value_col, t0, t1) for k in cand["clave"]]
        st = pd.concat([cand.reset_index(drop=True), pd.DataFrame(stats)], axis=1)
        st["cobertura"] = st["n_valid_window"] / n_days
        st["principal"] = st["cobertura"] >= float(thr[tipo])

        steps = [("catalogo_maestro", len(cat)),
                 ("candidatas_region_12_18_26", len(cand)),
                 ("archivo_descargado", int(st["downloaded"].sum())),
                 ("archivo_legible", int(st["readable"].sum())),
                 ("con_dato_2010_2025", int((st["n_valid_window"] > 0).sum())),
                 (f"cobertura_ge_{thr[tipo]}", int(st["principal"].sum()))]

        if tipo == "hidrometricas":
            units = []
            for _, r in st.iterrows():
                inside = [c["nombre"] for c in cfg["cuencas_piloto"]
                          if c["bbox"][0] <= r["longitud"] <= c["bbox"][2]
                          and c["bbox"][1] <= r["latitud"] <= c["bbox"][3]]
                units.append(";".join(inside))
            st["unidades_bbox"] = units
            st["n_unidades_bbox"] = st["unidades_bbox"].map(lambda s: len(s.split(";")) if s else 0)
            main_in = st["principal"] & (st["n_unidades_bbox"] > 0)
            steps.append(("dentro_de_algun_bbox", int(main_in.sum())))
            steps.append(("filas_estacion_unidad", int(st.loc[main_in, "n_unidades_bbox"].sum())))
            steps.append(("estaciones_en_2_o_mas_unidades", int((main_in & (st["n_unidades_bbox"] > 1)).sum())))

            link = PROCESSED / "estaciones_hidrorivers.csv"
            if link.exists():
                lk = pd.read_csv(link, dtype={"clave": str})
                steps.append(("vinculadas_hydrorivers", int(lk["hyriv_id"].notna().sum())))
                steps.append(("vinculadas_hydrorivers_en_unidad", int(
                    (lk["hyriv_id"].notna() & lk["unidad_piloto"].notna()).sum())))
                e1["tramo_cercano_distinto_de_mayor_area"] = int(lk["tramos_distintos"].fillna(False).sum())

            if Path(published_cuencas).exists():
                mapping = _published_polygon_mapping(sel_pub_h, cfg, Path(published_cuencas))
                mapping.to_csv(OUT / f"published_polygon_mapping{suffix}.csv", index=False)
                with_poly = mapping.groupby("clave")["tiene_poligono"].any()
                steps.append(("v2026_06_poligonos_publicados", int(mapping["partes"].sum())))
                steps.append(("v2026_06_estaciones_con_poligono", int(with_poly.sum())))
                e1["v2026_06_estaciones_sin_poligono_en_su_unidad"] = mapping.loc[
                    ~mapping["tiene_poligono"], ["unidad", "VALUE", "clave"]].to_dict("records")
                e1["v2026_06_distancia_estacion_poligono_m"] = {
                    "mediana": float(mapping["dist_estacion_poligono_m"].median()),
                    "p95": float(mapping["dist_estacion_poligono_m"].quantile(0.95)),
                    "max": float(mapping["dist_estacion_poligono_m"].max())}
            e1["seleccionadas_publicadas_filas"] = int(len(sel_pub_h))
            e1["seleccionadas_publicadas_igual_a_principal_en_bbox"] = (
                set(sel_pub_h["clave"]) == set(st.loc[main_in, "clave"]))
            e1["principal_fuera_de_bbox"] = st.loc[st["principal"] & (st["n_unidades_bbox"] == 0),
                                                   "clave"].tolist()

        for name, n in steps:
            funnel.append({"tipo": tipo, "etapa": name, "n": n})
        st.to_csv(OUT / f"station_funnel_{tipo}{suffix}.csv", index=False)
        e1[tipo] = {name: n for name, n in steps}
        e1[tipo]["candidatas_publicadas_coinciden"] = set(cand_pub["clave"]) == set(cand["clave"])
        e1[tipo]["cobertura_media_pct_descargadas"] = float(st.loc[st["downloaded"], "cobertura"].mean() * 100)
        e1[tipo]["cobertura_mediana_pct_descargadas"] = float(st.loc[st["downloaded"], "cobertura"].median() * 100)

        for clave in st.loc[~st["downloaded"], "clave"]:
            row = {"tipo": tipo, "clave": clave, "url": conagua.series_url(tipo, clave),
                   "http_status": None, "motivo": "no consultado (correr con --probe)",
                   "fecha_consulta": None}
            if probe:
                res = _probe(row["url"])
                row.update(http_status=res["http_status"], motivo=res["reason"],
                           fecha_consulta=date.today().isoformat())
                time.sleep(probe_delay)
            missing_rows.append(row)

    pd.DataFrame(funnel).to_csv(OUT / f"counts_reconciliation{suffix}.csv", index=False)
    pd.DataFrame(missing_rows).to_csv(OUT / f"missing_downloads{suffix}.csv", index=False)

    obs, comps = [], []
    s, c = _observation_counts_pandas("hidrometricas", "gasto_medio_m3s", t0, t1)
    obs.append(s); comps.append(c)
    s, c = _observation_counts_arrow("climatologicas", "precip_mm", t0, t1)
    obs.append(s); comps.append(c)
    pd.DataFrame(obs).to_csv(OUT / f"observation_counts{suffix}.csv", index=False)
    comp = pd.concat(comps, ignore_index=True)
    comp.to_csv(OUT / f"calidad_composition{suffix}.csv", index=False)
    e1["observaciones"] = {o["tipo"]: {k: v for k, v in o.items() if k != "tipo"} for o in obs}
    e1["calidad"] = {f"{r.tipo}|{r.ambito}|{r.calidad}": {"n": int(r.n), "pct": round(float(r.pct), 4)}
                     for r in comp.itertuples()}

    (OUT / f"e1_counts{suffix}.json").write_text(json.dumps(e1, indent=2, ensure_ascii=False, default=str),
                                        encoding="utf-8")
    log.info("E1 listo → %s", OUT)


if __name__ == "__main__":
    main()

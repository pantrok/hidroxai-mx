#!/usr/bin/env python
"""Datos precalculados del dashboard (``dashboard/data/``), sin recalcular ningún resultado.

Reorganiza archivos existentes del benchmark para que el dashboard los lea en el navegador:

- métricas, importancias, concordancias y contingencias: copia de
  ``results/xai_benchmark/`` (y ``mese/`` para el LSTM descriptivo);
- pronósticos del periodo de prueba (2023-01-01 – 2025-09-03): promedio de las tres semillas
  de la configuración elegida, el mismo pronóstico con el que ``xai_05`` y ``xai_18``
  calcularon las métricas. Se leen de ``data/interim/xai_benchmark/`` (no versionado);
- alertas: niveles del ensamble guardados por ``xai_07``; los umbrales P90/P99 de cada
  estación se toman del gasto de entrenamiento con ``calidad = 0``, como en ``xai_07``;
- estaciones (catálogo publicado) y contornos simplificados de las regiones hidrológicas 12,
  18 y 26 y de la cuenca del Río Cutzamala (CNA, 1998, 1:250 000, distribuidos por CONABIO).

Antes de escribir, comprueba que las tablas de contingencia rehechas con esos niveles y
umbrales son idénticas a ``rq3_contingency.csv`` y que el NSE de los pronósticos coincide con
``rq1_station_metrics.csv``.

Uso: python scripts/dash_01_build_data.py [--limites data/scratch/limites]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hidroxai_mx.models import data as D  # noqa: E402
from hidroxai_mx.models import metrics as M  # noqa: E402

RES = ROOT / "results" / "xai_benchmark"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
PROCESSED = ROOT / "data" / "processed"
FEATURES = ROOT / "data" / "features"
OUT = ROOT / "dashboard" / "data"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
SEEDS = (20261010, 20261011, 20261012)
def _csv(path: Path, **kw) -> pd.DataFrame:
    """CSV de resultados leído sin perder dígitos (``float_precision="round_trip"``)."""
    return pd.read_csv(path, float_precision="round_trip", **kw)


MODELOS = ["persistencia", "arima", "xgboost", "tcn", "convnext", "patchtst", "lstm"]
EVENTOS = {"P90": (0.90, 2), "P99": (0.99, 3)}        # percentil del evento; nivel difuso mínimo


def _chosen() -> dict[tuple[str, int], str]:
    elegida = json.loads((RES / "e_rq1.json").read_text(encoding="utf-8"))["configuracion_elegida"]
    out = {}
    for k, v in elegida.items():
        modelo, h = k.rsplit("_h", 1)
        out[(modelo, int(h))] = v
    lstm = pd.read_csv(RES / "mese" / "lstm_selection.csv")
    for r in lstm[lstm["elegida"]].itertuples():
        out[("lstm", int(r.h))] = f"lstm-{int(r.config)}"
    return out


def _seed_mean(folder: Path, config: str, tag: str) -> np.ndarray:
    return np.stack([np.load(folder / f"{config}_{tag}_s{s}.npz")["flow_test"] for s in SEEDS]).mean(0)


def pronosticos(chosen: dict, evaluables: set[str]) -> pd.DataFrame:
    marcos = []
    for slug in SLUG.values():
        for h in D.HORIZONS:
            tag = f"{slug}_h{h}"
            meta = pd.read_parquet(INTERIM / "cpu" / "meta" / f"{tag}_test.parquet")
            base = np.load(INTERIM / "cpu" / "preds" / f"baselines_{tag}.npz")
            sim = {"persistencia": base["persistence_test"], "arima": base["arima_test"],
                   "xgboost": _seed_mean(INTERIM / "cpu" / "preds", chosen[("xgboost", h)], tag)}
            for m in ("tcn", "convnext", "patchtst"):
                sim[m] = _seed_mean(INTERIM / "nets" / "preds", chosen[(m, h)], tag)
            run = INTERIM / "mese" / "lstm_lns" / "runs" / "split" / f"{tag}_{chosen[('lstm', h)]}"
            lmeta = pd.read_parquet(run / "meta" / f"{tag}_test.parquet")
            if not (lmeta["clave"].to_numpy() == meta["clave"].to_numpy()).all():
                raise SystemExit(f"las muestras del LSTM no coinciden con las del benchmark: {tag}")
            sim["lstm"] = _seed_mean(run / "preds", chosen[("lstm", h)], tag)
            df = pd.DataFrame({"clave": meta["clave"], "h": np.int8(h), "fecha": meta["target_date"],
                               "observado": meta["y_flow"], **sim})
            marcos.append(df[df["clave"].isin(evaluables)])
    out = pd.concat(marcos, ignore_index=True)
    for c in ["observado", *MODELOS]:
        out[c] = out[c].astype("float32")          # sin redondear: en series casi planas el NSE es sensible
    return out


def verificar_nse(pron: pd.DataFrame, met: pd.DataFrame, tol: float = 1e-3) -> float:
    """NSE de los pronósticos guardados (float32) contra el publicado, en escala relativa:
    |Δ| ≤ tol · max(1, |NSE|). Devuelve el mayor cociente |Δ| / max(1, |NSE|)."""
    peor = 0.0
    for (clave, h), g in pron.groupby(["clave", "h"]):
        pub = met[(met["clave"] == clave) & (met["h"] == h)].set_index("modelo")["nse"]
        for m in MODELOS:
            if m in pub.index and np.isfinite(pub[m]):
                dif = abs(M.nse(g["observado"].to_numpy(float), g[m].to_numpy(float)) - pub[m])
                peor = max(peor, dif / max(1.0, abs(pub[m])))
    if peor > tol:
        raise SystemExit(f"el NSE de los pronósticos se aparta del publicado: {peor:.2e} (relativo)")
    return peor


def umbrales(evaluables: set[str]) -> pd.DataFrame:
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", D.TARGET],
                         filters=[("clave_estacion", "in", sorted(evaluables))])
    ft["fecha"] = pd.to_datetime(ft["fecha"])
    tr = ft[(ft["fecha"] >= D.PARTITIONS["train"][0]) & (ft["fecha"] <= D.PARTITIONS["train"][1])
            & (ft["calidad"] == 0)]
    filas = [{"clave": k, **{e.lower(): float(np.quantile(g[D.TARGET].to_numpy(), q)) for e, (q, _) in EVENTOS.items()}}
             for k, g in tr.groupby("clave_estacion")]
    return pd.DataFrame(filas)


def alertas(evaluables: set[str]) -> pd.DataFrame:
    marcos = []
    for slug in SLUG.values():
        for h in D.HORIZONS:
            a = pd.read_parquet(INTERIM / "alerts" / f"{slug}_h{h}.parquet")
            a = a[a["clave"].isin(evaluables)]
            marcos.append(pd.DataFrame({"clave": a["clave"], "h": np.int8(h), "fecha": a["target_date"],
                                        "observado": a["observado"], "ensamble": a["ensamble"],
                                        "percentil": a["percentil"], "dispersion": a["dispersion"],
                                        "nivel": a["nivel"].astype("int8")}))
    return pd.concat(marcos, ignore_index=True)


def contingencia_desde(al: pd.DataFrame, um: pd.DataFrame) -> pd.DataFrame:
    """Tablas por estación, evento y método con la lógica de ``alert.evaluation.contingency``."""
    d = al.merge(um, on="clave")
    filas = []
    for (clave, h), g in d.groupby(["clave", "h"]):
        for e, (q, nivel_min) in EVENTOS.items():
            obs = g["observado"].to_numpy() > g[e.lower()].to_numpy()
            for metodo, pred in (("difuso", g["nivel"].to_numpy() >= nivel_min),
                                 ("umbral", g["percentil"].to_numpy() >= q)):
                filas.append({"clave": clave, "h": int(h), "evento": e, "metodo": metodo,
                              "aciertos": int((obs & pred).sum()), "fallos": int((obs & ~pred).sum()),
                              "falsas": int((~obs & pred).sum()), "negativos": int((~obs & ~pred).sum())})
    return pd.DataFrame(filas)


def contornos(limites: Path, tolerancia: float = 0.01) -> dict:
    """Contornos simplificados como listas lon/lat (``None`` separa partes) para Plotly."""
    import geopandas as gpd

    rh = gpd.read_file(limites / "rh250kgw" / "rh250kgw.shp").to_crs(4326)
    cue = gpd.read_file(limites / "cue250kgw" / "cue250kgw.shp").to_crs(4326)
    piezas = {
        "Región hidrológica 12 (Lerma–Santiago)": rh[rh["CLAVE"].astype(int) == 12],
        "Región hidrológica 18 (Balsas)": rh[rh["CLAVE"].astype(int) == 18],
        "Región hidrológica 26 (Pánuco)": rh[rh["CLAVE"].astype(int) == 26],
        "Cuenca del Río Cutzamala": cue[cue["IDCUENCA"].astype(int) == 71],
    }
    out = {}
    for nombre, g in piezas.items():
        if g.empty:
            raise SystemExit(f"contorno vacío: {nombre}")
        geom = g.geometry.union_all().simplify(tolerancia, preserve_topology=True)
        lon, lat = [], []
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            lon += [round(v, 4) for v in x] + [None]
            lat += [round(v, 4) for v in y] + [None]
        out[nombre] = {"lon": lon, "lat": lat}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limites", type=Path, default=ROOT / "data" / "scratch" / "limites",
                    help="Carpeta con rh250kgw/ y cue250kgw/ (CONABIO); ver conf/sources.yaml, sección 10")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    met = pd.concat([_csv(RES / "rq1_station_metrics.csv"),
                     _csv(RES / "mese" / "lstm_station_metrics.csv")], ignore_index=True)
    met = met[met["modelo"].isin(MODELOS)]
    evaluables = set(met.loc[met["modelo"] == "persistencia", "clave"])
    chosen = _chosen()

    pron = pronosticos(chosen, evaluables)
    peor_nse = verificar_nse(pron, met)
    al = alertas(evaluables)
    um = umbrales(evaluables)
    # Se verifica con lo que queda escrito (float64), releído, para que el dashboard rehaga lo mismo.
    al.to_parquet(OUT / "alertas.parquet", index=False, compression="gzip")
    um.to_csv(OUT / "umbrales.csv", index=False)
    al = pd.read_parquet(OUT / "alertas.parquet")
    um = _csv(OUT / "umbrales.csv")
    cont_pub = _csv(RES / "rq3_contingency.csv")
    cont_rehecha = contingencia_desde(al, um)
    claves = ["clave", "h", "evento", "metodo"]
    comp = cont_pub.merge(cont_rehecha, on=claves, suffixes=("", "_dash"), how="outer", indicator=True)
    if (comp["_merge"] != "both").any() or not all(
            (comp[c] == comp[f"{c}_dash"]).all() for c in ("aciertos", "fallos", "falsas", "negativos")):
        raise SystemExit("las contingencias rehechas no coinciden con rq3_contingency.csv")

    cat = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    vinc = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    cuenca = met.drop_duplicates("clave").set_index("clave")["cuenca"]
    est = (cat[cat["clave"].isin(evaluables)][["clave", "nombre", "estado", "latitud", "longitud"]]
           .merge(vinc[["clave", "unidad_piloto"]], on="clave", how="left"))
    est["cuenca"] = est["clave"].map(cuenca)

    imp = pd.concat([_csv(RES / "rq2_importance.csv"), _csv(RES / "mese" / "lstm_importance.csv")],
                    ignore_index=True)[["cuenca", "h", "modelo", "canal", "rezago_ventana", "importancia"]]
    medidas = pd.concat([_csv(RES / "rev_rr2_medidas.csv"),
                         _csv(RES / "mese" / "lstm_concordance.csv")], ignore_index=True)
    conc = medidas[medidas["medida"] == "spearman_180"][["cuenca", "h", "tipo", "modelo_a", "modelo_b", "valor"]]
    resumen = pd.concat([_csv(RES / "rq1_summary.csv"), _csv(RES / "mese" / "lstm_skill.csv")],
                        ignore_index=True)
    resumen = resumen[resumen["modelo"].isin(MODELOS)][
        ["grupo", "h", "modelo", "estaciones", "nse_mediana", "kge_mediana", "rmse_mediana", "ss_mediana"]]

    pron.to_parquet(OUT / "pronosticos.parquet", index=False, compression="gzip")
    imp.to_parquet(OUT / "importancia.parquet", index=False, compression="gzip")
    met[["cuenca", "h", "clave", "modelo", "n", "nse", "kge", "rmse", "ss"]].to_csv(OUT / "metricas_estacion.csv", index=False)
    resumen.to_csv(OUT / "metricas_cuenca.csv", index=False)
    conc.to_csv(OUT / "concordancia.csv", index=False)
    cont_pub.to_csv(OUT / "contingencia.csv", index=False)
    _csv(RES / "rq3_summary.csv").to_csv(OUT / "resumen_alertas.csv", index=False)
    est.to_csv(OUT / "estaciones.csv", index=False)
    (OUT / "contornos.json").write_text(json.dumps(contornos(a.limites), ensure_ascii=False), encoding="utf-8")
    meta = {
        "generado": date.today().isoformat(), "script": "scripts/dash_01_build_data.py",
        "dataset": {"version": "v2026.10 (datos idénticos a v2026.11)", "doi": "10.5281/zenodo.24119292",
                    "doi_concepto": "10.5281/zenodo.21231600"},
        "articulo_doi": "10.1016/j.dib.2026.113442", "benchmark_tag": "xai-benchmark-v1.5",
        "periodo_prueba": list(D.PARTITIONS["test"]), "horizontes": list(D.HORIZONS), "modelos": MODELOS,
        "configuracion_elegida": {f"{m}_h{h}": v for (m, h), v in sorted(chosen.items())},
        "estaciones_evaluables": len(evaluables),
        "verificacion": {"contingencias_iguales_a_rq3": True, "max_dif_nse_relativa_float32": float(f"{peor_nse:.2e}")},
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    tam = {p.name: round(p.stat().st_size / 1e6, 2) for p in sorted(OUT.iterdir())}
    print(json.dumps({"archivos_mb": tam, "total_mb": round(sum(tam.values()), 2),
                      "filas_pronosticos": len(pron), "max_dif_nse": peor_nse}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Paso 2, T1 — cifras faltantes para el artículo (revisión DIB-D-26-01662).

Calcula, solo a partir de archivos del repositorio:
  1. Tabla 3 v2026.10 por unidad operativa -> tabla3_v2026_10.csv
  2. Seleccionadas sin vínculo HydroRIVERS y su motivo -> hidrorivers_sin_vinculo.csv
  3. Composición de data/raw/_manifest.json
  4. Duplicados y `fuente` vacía en el release v2026.06 (parquets archivados)
  5. Curva del experimento de enmascaramiento por L (imputation_masking_summary.csv)
  6. Columnas, unidades y definición operativa de la feature table (leídas del código)
  7. Estaciones excluidas del baseline (baseline_excluidas.csv)
Salida: results/dib_revision/e13_paso2_t1.json (+ los dos CSV)

Uso:  python scripts/dib_13_paso2_tables.py
"""
from __future__ import annotations

import importlib.util
import inspect
import json
from collections import Counter
from datetime import date

import pandas as pd
import pyarrow.dataset as pads
import pyarrow.parquet as pq

from hidroxai_mx import features as F
from hidroxai_mx.utils import FEATURES, INTERIM, PROCESSED, RAW, ROOT, get_logger, load_cuencas

log = get_logger("dib_13")
R = ROOT / "results" / "dib_revision"
ARCH = INTERIM / "dib_revision" / "v2026.06_processed"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tabla3(cfg: dict, link: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    rows = []
    for u in cfg["cuencas_piloto"]:
        g = link[link["unidad_piloto"] == u["nombre"]]
        rows.append({"unidad": u["nombre"], "region_hidrologica": u["region_hidrologica"],
                     "estaciones_asignadas": len(g),
                     "vinculadas_hydrorivers": int(g["hyriv_id"].notna().sum()),
                     "tramo_cercano_distinto": int(g["tramos_distintos"].fillna(False).astype(bool).sum()),
                     "cem_resolucion_m": u["cem_resolucion_m"]})
    t = pd.DataFrame(rows)
    regla = ("Cada estación seleccionada se asigna a una sola unidad: entre los recuadros (bbox) de "
             "conf/cuencas_piloto.yaml que contienen su coordenada de catálogo, se prefieren los de la "
             "misma región hidrológica que la estación según el catálogo SIH, y entre ellos el primero en "
             "el orden del archivo; si ninguno es de su región, el primero que la contiene "
             "(scripts/06_link_hydrorivers.py, función _unit_of).")
    return t, regla


def sin_vinculo(link: pd.DataFrame, radio: float) -> pd.DataFrame:
    s = link[link["hyriv_id"].isna()].copy()
    s["fuera_de_toda_unidad"] = s["unidad_piloto"].isna()
    s["motivo"] = [f"sin tramo HydroRIVERS a ≤ {radio}°" + ("; además fuera de toda unidad" if f else "")
                   for f in s["fuera_de_toda_unidad"]]
    return s[["clave", "unidad_piloto", "fuera_de_toda_unidad", "motivo"]]


def manifest_raw() -> dict:
    m = json.loads((RAW / "_manifest.json").read_text(encoding="utf-8"))
    carpetas = Counter(k.split("/")[0] if "/" in k else k for k in m)
    datos = {k: v for k, v in m.items() if not k.endswith(".gitkeep")}
    return {"entradas": len(m), "archivos_de_datos": len(datos),
            "por_carpeta": dict(sorted(carpetas.items())),
            "con_fecha_de_descarga": sum(v.get("descargado_utc") is not None for v in datos.values()),
            "solo_fecha_de_modificacion": sum(v.get("descargado_utc") is None for v in datos.values()),
            "con_url": sum(v.get("url") is not None for v in datos.values())}


def v2026_06() -> dict:
    """El parquet hidrométrico publicado = 104 fragmentos vigentes (archivados en
    v2026.06_processed) + 93 fragmentos obsoletos de corridas de prueba (stale_fragments).
    Esos archivos no se distribuyen en Zenodo: fuera del repositorio se omite el bloque."""
    if not ARCH.exists():
        return {"nota": "parquets v2026.06 archivados no disponibles en esta copia"}
    out = {}
    parts = [pads.dataset(p, format="parquet", partitioning="hive").to_table(
                 columns=["clave_estacion", "fecha"]).to_pandas()
             for p in (ARCH / "series_hidrometricas.parquet", ARCH.parent / "stale_fragments")]
    t = pd.concat(parts, ignore_index=True)
    d = t[t.duplicated(["clave_estacion", "fecha"], keep="first")]
    out["hidro_filas_publicadas"] = int(len(t))
    out["hidro_fragmentos_obsoletos_filas"] = int(len(parts[1]))
    out["hidro_estacion_dias_duplicados"] = int(len(d))
    out["hidro_estaciones_con_duplicados"] = int(d["clave_estacion"].nunique())
    out["hidro_estaciones_con_duplicados_lista"] = sorted(d["clave_estacion"].unique())
    c = pads.dataset(ARCH / "series_climatologicas.parquet", format="parquet", partitioning="hive")
    out["clima_filas"] = c.count_rows()
    out["clima_filas_fuente_vacia"] = int(c.to_table(columns=["fuente"]).column("fuente").null_count)
    return out


def curva_por_L() -> list[dict]:
    s = pd.read_csv(R / "imputation_masking_summary.csv")
    s = s[s["subconjunto"] == "todos"]
    return [{"metodo": r.metodo, "L": int(r.L), "nRMSE": round(r.nRMSE, 4), "nMAE": round(r.nMAE, 4),
             "tasa_sobreoscilacion": round(r.tasa_sobreoscilacion, 4), "n_huecos": int(r.n_huecos)}
            for r in s.sort_values(["metodo", "L"]).itertuples()]


def feature_table(sel: pd.DataFrame) -> dict:
    p = FEATURES / "feature_table.parquet"
    cols = pq.read_schema(p).names
    t = pq.read_table(p, columns=["clave_estacion", "precip_idw_mm"]).to_pandas()
    power = inspect.signature(F.idw_to_station).parameters["power"].default
    k_default = _script("05_select_stations.py").main.params
    k_default = next(o.default for o in k_default if o.name == "k")
    k_obs = sel["vecinos_clima"].dropna().str.split(",").map(len).value_counts().to_dict()
    target = "gasto_medio_m3s"
    unidades = {"fecha": "día (YYYY-MM-DD)", "clave_estacion": "clave SIH", "nivel_m": "m",
                target: "m³/s", "fuente": "texto (SIH)", "calidad": "0/1/2 (bandera del gasto)",
                "anio": "año", "precip_idw_mm": "mm/día"}
    unidades.update({f"{target}_lag{k}": "m³/s" for k in F.LAGS})
    unidades.update({f"{target}_ma{w}": "m³/s" for w in F.ROLLING})
    return {
        "filas": int(len(t)), "estaciones": int(t["clave_estacion"].nunique()),
        "estaciones_con_precip_idw": int(t.loc[t["precip_idw_mm"].notna(), "clave_estacion"].nunique()),
        "columnas": [{"columna": c, "unidad": unidades.get(c, "—")} for c in cols],
        "filas_incluidas": f"días con valor de {target} (se descartan filas sin objetivo)",
        "lags_dias": list(F.LAGS),
        "medias_moviles": [{"ventana_dias": w, "incluye_dia_t": True, "min_periods": max(2, w // 2)}
                           for w in F.ROLLING],
        "precip_idw_mm": {
            "vecinos": "estaciones climatológicas seleccionadas más cercanas por distancia haversine "
                       "(columna vecinos_clima de estaciones_seleccionadas_hidrometricas.csv, etapa 05 --refine)",
            "k_por_defecto_05": int(k_default), "k_observado": {str(a): int(b) for a, b in k_obs.items()},
            "potencia_idw": int(power),
            "faltantes": "los pesos se renormalizan cada día entre los vecinos con dato; NaN si ningún "
                         "vecino tiene dato",
            "valores_de_vecinos": "precip_mm tal como está en la serie climatológica (no se filtra calidad)",
            "solo_estaciones_seleccionadas": True,
            "codigo": "scripts/07_build_features.py; hidroxai_mx.features.idw_to_station",
        },
    }


def main() -> None:
    cfg = load_cuencas()
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    radio = cfg["vinculo_hydrorivers"]["radio_grados"]

    t3, regla = tabla3(cfg, link)
    t3.to_csv(R / "tabla3_v2026_10.csv", index=False)
    sv = sin_vinculo(link, radio)
    sv.to_csv(R / "hidrorivers_sin_vinculo.csv", index=False)
    exc = pd.read_csv(R / "baseline_excluidas.csv", dtype={"clave": str})
    exc = exc[exc["variante"] == "sin_outliers_en_predictores"]

    res = {
        "fecha": date.today().isoformat(),
        "tabla3_v2026_10": {"fuente": "results/dib_revision/tabla3_v2026_10.csv "
                                      "(data/processed/estaciones_hidrorivers.csv, conf/cuencas_piloto.yaml)",
                            "regla_asignacion": regla, "total_asignadas": int(t3["estaciones_asignadas"].sum()),
                            "por_unidad": t3.to_dict("records")},
        "hidrorivers_sin_vinculo": {"fuente": "results/dib_revision/hidrorivers_sin_vinculo.csv",
                                    "n": len(sv), "seleccionadas": len(link),
                                    "vinculadas": int(link["hyriv_id"].notna().sum()),
                                    "estaciones": sv.to_dict("records")},
        "manifest_raw": {"fuente": "data/raw/_manifest.json", **manifest_raw()},
        "duplicados_v2026_06": {"fuente": "data/interim/dib_revision/v2026.06_processed y "
                                          "data/interim/dib_revision/stale_fragments (parquets del "
                                          "release v2026.06 archivados durante la revisión)", **v2026_06()},
        "curva_por_L": {"fuente": "results/dib_revision/imputation_masking_summary.csv (subconjunto todos)",
                        "filas": curva_por_L()},
        "feature_table_v2026_10": {"fuente": "data/features/feature_table.parquet; "
                                             "scripts/07_build_features.py; src/hidroxai_mx/features",
                                   **feature_table(sel)},
        "baseline_excluidas": {"fuente": "results/dib_revision/baseline_excluidas.csv",
                               "variante": "sin_outliers_en_predictores",
                               "estaciones": exc[["clave", "n_train", "n_val", "n_test", "motivo"]].to_dict("records")},
    }
    (R / "e13_paso2_t1.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str),
                                         encoding="utf-8")
    log.info("Tabla 3: %d estaciones; sin vínculo: %d; manifest: %d entradas",
             res["tabla3_v2026_10"]["total_asignadas"], len(sv), res["manifest_raw"]["entradas"])


if __name__ == "__main__":
    main()

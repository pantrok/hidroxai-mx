#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · numbers.json — todas las cifras que cita el artículo.

Lee exclusivamente archivos generados por los scripts de la revisión y del pipeline
(results/dib_revision/*, data/processed/reportes/*, data/processed/*.csv); no contiene
ninguna cifra escrita a mano salvo las del manuscrito original sometido (v2026.06), que
se incluyen como "dice" para construir la tabla de correcciones.

Salida: results/dib_revision/numbers.json
Uso:  python scripts/dib_11_numbers.py
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from hidroxai_mx.utils import PROCESSED, ROOT

R = ROOT / "results" / "dib_revision"
REP = PROCESSED / "reportes"


def _j(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _clima_imputed_v2026_06() -> dict:
    """Precipitación imputada (calidad == 1) y cuántas negativas, en el parquet v2026.06
    archivado durante la revisión."""
    import pyarrow.compute as pc
    import pyarrow.dataset as pads

    p = ROOT / "data/interim/dib_revision/v2026.06_processed/series_climatologicas.parquet"
    if not p.exists():
        return {"nota": "parquet v2026.06 no disponible"}
    t = pads.dataset(p, format="parquet", partitioning="hive").to_table(
        columns=["precip_mm"], filter=pc.field("calidad") == 1)
    v = t.column("precip_mm")
    return {"imputados": int(len(v)), "negativos": int(pc.sum(pc.less(v, 0)).as_py() or 0)}


def main() -> None:
    e1 = _j(R / "e1_counts_v2026_10.json")
    funnel = pd.read_csv(R / "counts_reconciliation_v2026_10.csv").set_index(["tipo", "etapa"])["n"]
    obs = pd.read_csv(R / "observation_counts_v2026_10.csv").set_index("tipo")
    cal = pd.read_csv(R / "calidad_composition_v2026_10.csv")
    miss = pd.read_csv(R / "missing_downloads_v2026_06.csv")
    met = _j(REP / "metrics.json")
    e3, e4, e5 = _j(R / "e3_imputation.json"), _j(R / "e4_outliers.json"), _j(R / "e5_validation.json")
    e5b, e6, e9 = _j(R / "e5b_snap_diagnosis.json"), _j(R / "e6_dem.json"), _j(R / "e9_baseline.json")
    dparams = _j(R / "delineation_params.json")
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    ext = pd.read_csv(PROCESSED / "estaciones_extendidas_hidrometricas.csv", dtype={"clave": str})
    val = {t: _j(REP / f"validacion_{t}.json") for t in ("hidrometricas", "climatologicas")}

    def comp(tipo, ambito):
        c = cal[(cal["tipo"] == tipo) & (cal["ambito"] == ambito)].set_index("calidad")
        return {int(k): {"n": int(r["n"]), "pct": round(float(r["pct"]), 3)} for k, r in c.iterrows()}

    h, c = obs.loc["hidrometricas"], obs.loc["climatologicas"]
    bl = {f"{r['variante']}|{r['modelo']}": {k: r[k] for k in r if k not in ("variante", "modelo")}
          for r in e9["tabla"]}
    num = {
        "version": "v2026.10", "generado": date.today().isoformat(),
        "estaciones": {
            "hidro_catalogo": int(funnel["hidrometricas", "catalogo_maestro"]),
            "hidro_candidatas": int(funnel["hidrometricas", "candidatas_region_12_18_26"]),
            "hidro_descargadas": int(funnel["hidrometricas", "archivo_descargado"]),
            "hidro_con_dato_2010_2025": int(funnel["hidrometricas", "con_dato_2010_2025"]),
            "hidro_seleccionadas": int(funnel["hidrometricas", "cobertura_ge_0.6"]),
            "hidro_seleccionadas_en_unidad": int(funnel["hidrometricas", "dentro_de_algun_bbox"]),
            "hidro_seleccionadas_fuera_de_unidad": e1["principal_fuera_de_bbox"],
            "hidro_en_2_o_mas_unidades": int(funnel["hidrometricas", "estaciones_en_2_o_mas_unidades"]),
            "hidro_extendidas_0.30_0.60": int(len(ext)),
            "hidro_vinculadas_hydrorivers": int(link["hyriv_id"].notna().sum()),
            "hidro_tramo_cercano_distinto_de_mayor_area": int(link["tramos_distintos"].fillna(False).sum()),
            "clima_catalogo": int(funnel["climatologicas", "catalogo_maestro"]),
            "clima_candidatas": int(funnel["climatologicas", "candidatas_region_12_18_26"]),
            "clima_descargadas": int(funnel["climatologicas", "archivo_descargado"]),
            "clima_seleccionadas": int(funnel["climatologicas", "cobertura_ge_0.8"]),
            "seleccionadas_por_rh": met["fig2"]["seleccionadas_por_rh"],
            "inventario_hidro_por_rh": met["fig4"]["inventario_por_rh"],
        },
        "descargas_faltantes": {
            "hidro": int((miss["tipo"] == "hidrometricas").sum()),
            "clima": int((miss["tipo"] == "climatologicas").sum()),
            "motivo": miss["motivo"].value_counts().to_dict(),
            "fecha_consulta": miss["fecha_consulta"].dropna().unique().tolist(),
        },
        "observaciones": {
            "hidro_filas_registro_completo": int(h["rows_total"]),
            "hidro_con_valor": int(h["rows_with_value"]),
            "hidro_con_valor_2010_2025": int(h["with_value_window"]),
            "hidro_duplicados": int(h["duplicate_rows"]),
            "clima_filas_registro_completo": int(c["rows_total"]),
            "clima_precip_con_valor": int(c["rows_with_value"]),
            "clima_precip_con_valor_2010_2025": int(c["with_value_window"]),
            "hidro_fechas": [met["dataset"]["hidrometricas"]["fecha_min"], met["dataset"]["hidrometricas"]["fecha_max"]],
            "clima_fechas": [met["dataset"]["climatologicas"]["fecha_min"], met["dataset"]["climatologicas"]["fecha_max"]],
        },
        "cobertura_hidro": {k: met["fig4"][k] for k in ("cobertura_media_pct", "cobertura_mediana_pct", "estaciones_ge_60pct")},
        "calidad_hidro": {"dias_con_valor": comp("hidrometricas", "filas_con_valor"),
                          "dias_con_valor_2010_2025": comp("hidrometricas", "filas_con_valor_2010_2025")},
        "imputacion_E3": {
            "huecos_por_L": e3["huecos_por_L"], "global_L1_6": e3["global_L1_6"]["todos"],
            "ascensos_L1_6": e3["global_L1_6"]["ascensos"], "regla_a": e3["regla_a"], "regla_b": e3["regla_b"],
            "dato_v2026_06": e3["diagnostico_dato_publicado"],
            "clima_precip_imputada_v2026_06": _clima_imputed_v2026_06(),
        },
        "outliers_E4": e4,
        "subcuencas_v2026_06_E5": {"validacion": e5, "diagnostico": e5b},
        "parametros_delineacion_v2026_06_E7": dparams,
        "dem_15_vs_30_E6": e6,
        "baseline_E9": {"estaciones": e9["variantes"], "tabla": bl, "segundos": e9["segundos"]},
        "correlacion_precip_gasto_E8": met["fig7"],
        "validacion_esquema": val,
        "dois": {"dataset_concepto": "10.5281/zenodo.21231600", "dataset_v2026_06": "10.5281/zenodo.21231601",
                 "dataset_v2026_10": None, "software_github_zenodo": None,
                 "nota": "Los DOI de v2026.10 y del software los asigna Zenodo al publicar."},
    }
    g = e3["global_L1_6"]["todos"]
    num["correcciones_articulo"] = [
        {"donde": "Abstract, Value of the data, Data description", "dice": "547 / 2,659 stations; 10,594,758 and 55,590,466 daily observations over 2010–2025",
         "debe_decir": f"{num['estaciones']['hidro_descargadas']} / {num['estaciones']['clima_descargadas']} stations; "
                       f"{num['observaciones']['hidro_filas_registro_completo']:,} and {num['observaciones']['clima_filas_registro_completo']:,} station-days over the full record, "
                       f"of which {num['observaciones']['hidro_con_valor_2010_2025']:,} streamflow and {num['observaciones']['clima_precip_con_valor_2010_2025']:,} precipitation values fall in 2010–2025"},
        {"donde": "Abstract, Value of the data, Limitations, Table 1", "dice": "108 hydrometric stations with ≥60 % completeness",
         "debe_decir": f"{num['estaciones']['hidro_seleccionadas']} (coverage computed on original observations, the selection rule)"},
        {"donde": "Abstract, Value of the data, Table 3", "dice": "101 lie within the curated basin boundaries",
         "debe_decir": f"{num['estaciones']['hidro_seleccionadas_en_unidad']} lie inside at least one operational unit"},
        {"donde": "Abstract, Value of the data, Methods, Table 3, Fig. 4", "dice": "automatic delineation of 123 sub-basins",
         "debe_decir": "sub-basin polygons removed; station–HydroRIVERS link provided "
                       f"({num['estaciones']['hidro_vinculadas_hydrorivers']} stations linked)"},
        {"donde": "Value of the data, Fig. 3 caption", "dice": "98.78 % original, 1.21 % imputed, 0.005 % outliers",
         "debe_decir": "{0} % / {1} % / {2} % of daily streamflow values".format(
             *[num["calidad_hidro"]["dias_con_valor"][k]["pct"] for k in (0, 1, 2)])},
        {"donde": "Methods (canonical schema and QC), Value of the data", "dice": "gaps shorter than seven days imputed by cubic spline",
         "debe_decir": f"internal gaps of 1–6 days filled by linear interpolation (masking test: nRMSE {g['lineal']['nRMSE']:.2f} linear, "
                       f"{g['pchip']['nRMSE']:.2f} PCHIP, {g['spline_pipeline']['nRMSE']:.2f} cubic spline); precipitation not interpolated"},
        {"donde": "Limitations", "dice": "average coverage 29.2 % (median 24.6 %)",
         "debe_decir": f"{num['cobertura_hidro']['cobertura_media_pct']} % (median {num['cobertura_hidro']['cobertura_mediana_pct']} %)"},
        {"donde": "Table 2 (cuencas/<basin>.gpkg)", "dice": "EPSG:6362", "debe_decir": "row removed (polygons withdrawn); DEMs are EPSG:6365; map in EPSG:6372"},
        {"donde": "Table 2 (feature_table.parquet)", "dice": "m³/s", "debe_decir": "m³/s (v2026.06 file was z-scored; fixed); ma7/ma30 include day t; add precip_idw_mm"},
        {"donde": "Table 1 (processed/)", "dice": "main sets: 108 hydro / 415 climate rows",
         "debe_decir": f"{num['estaciones']['hidro_seleccionadas']} hydro / {num['estaciones']['clima_seleccionadas']} climate rows"},
        {"donde": "Fig. 8 → Fig. 7", "dice": "Lagged Pearson correlation between the daily national means",
         "debe_decir": "Pearson and Spearman correlation of deseasonalized anomalies, aggregate of hydrological regions 12, 18 and 26 "
                       f"(peak at {met['fig7']['lag_max_pearson']} d, r = {met['fig7']['pearson_max']})"},
    ]
    (R / "numbers.json").write_text(json.dumps(num, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("numbers.json:", len(num), "secciones;", len(num["correcciones_articulo"]), "correcciones")


if __name__ == "__main__":
    main()

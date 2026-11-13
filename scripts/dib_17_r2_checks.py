#!/usr/bin/env python
"""Revisión DIB-D-26-01662R1 · E14 — verificaciones de la segunda ronda (T1–T5).

Criterios congelados en results/dib_revision/proof_ledger.md (E14) antes de ejecutar.
No modifica dib_09_baseline.py ni sus salidas: importa sus funciones y repite su bucle con
una variante más, y primero comprueba que reproduce baseline_por_estacion.csv.

Tareas:
  t1  dependencia temporal y fuga por imputación en el baseline (R2-i)
  t2  fin del registro frente al periodo de prueba (R2-iv)
  t3  faltantes y cobertura por unidad operativa (R2-ii)
  t4  exactitud espacial del vínculo con HydroRIVERS (R2-iii, R3)
  copia  reproducibilidad desde el archivo de Zenodo (R2-v)
  reporte  results/dib_revision/r2/R2_report.md a partir de las salidas
  reproduce  REPRODUCE.md (inglés) en la raíz, a partir de r2/reproducibilidad.json y
             r2/clean_copy_check_r2.json

Uso:  python scripts/dib_17_r2_checks.py --tareas t1,t2,t3,t4 --hydrorivers PATH/HydroRIVERS_v10_na.shp
      python scripts/dib_17_r2_checks.py --tareas copia --zip dist/HidroXAI-MX-v2026.10.zip --work <dir nuevo> --hydrorivers PATH
      (con --reusar-copia, usa la copia de --work ya instalada por dib_16 y solo repite dib_09, dib_15 y dib_17)
      python scripts/dib_17_r2_checks.py --tareas reporte
"""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads

from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("dib_17")
OUT = ROOT / "results" / "dib_revision"
R2 = OUT / "r2"
MAIN = "sin_outliers_en_predictores"
NEW = "sin_imputados_en_ventana"
UMBRAL_T1 = 0.02
FIN_PERIODO = ("2010-01-01", "2025-12-31")
TEST = ("2023-01-01", "2025-12-31")
RADIOS = (0.005, 0.01, 0.02)
LIMITE_LECTURA_S = 300
IGNORAR = {"fecha", "segundos", "generado", "minutos", "segundos_lectura"}


def baseline_module():
    spec = importlib.util.spec_from_file_location("dib_09_baseline", ROOT / "scripts" / "dib_09_baseline.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, obj) -> None:
    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating, float)):
            return None if not np.isfinite(o) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, pd.Timestamp):
            return str(o.date())
        return o

    path.write_text(json.dumps(clean(obj), indent=2, ensure_ascii=False), encoding="utf-8")


def line_of(path: Path, snippet: str) -> str:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return f"{path.relative_to(ROOT).as_posix()}:{i}"
    raise SystemExit(f"no se encontró {snippet!r} en {path}")


def units() -> pd.Series:
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    return link.set_index("clave")["unidad_piloto"].fillna("fuera de unidad")


def iqr(s: pd.Series) -> dict:
    q = s.quantile([0.25, 0.5, 0.75])
    return {"mediana": q[0.5], "q25": q[0.25], "q75": q[0.75], "n": int(s.notna().sum())}


# --------------------------------------------------------------------------- #
# T1
# --------------------------------------------------------------------------- #
def run_variant(B, ft: pd.DataFrame, variant: str):
    """El bucle de dib_09_baseline.py, con una variante más y los datos de prueba guardados."""
    rows, excluded, tests = [], [], []
    for k, g in ft.groupby("clave_estacion"):
        g = g.set_index("fecha").sort_index()
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        d = pd.DataFrame(g[B.PRED].to_numpy(), index=g.index, columns=B.PRED)
        d["y"] = g[B.T].shift(-1)
        d["y_cal"] = g["calidad"].shift(-1)
        d["outlier_en_ventana"] = (g["calidad"] == 2).astype(float).rolling(31, min_periods=1).max()
        d["imputado_en_ventana"] = (g["calidad"] == 1).astype(float).rolling(31, min_periods=1).max()
        d["q_t_imputado"] = (g["calidad"] == 1).astype(float)
        d["fecha_obj"] = d.index + pd.Timedelta(days=1)
        keep = (d["y_cal"] == 0) & (d["outlier_en_ventana"] == 0)
        if variant == NEW:
            keep &= d["imputado_en_ventana"] == 0
        d = d[keep].dropna(subset=B.PRED + ["y"])
        parts = {s: d[d["fecha_obj"].between(a, b)] for s, (a, b) in B.SPLITS.items()}
        n = {s: len(p) for s, p in parts.items()}
        yte = parts["test"]["y"].to_numpy()
        if any(n[s] < B.MINS[s] for s in B.MINS) or np.std(yte) == 0:
            excluded.append({"variante": variant, "clave": k, **{f"n_{s}": v for s, v in n.items()},
                             "motivo": "sin varianza en test" if n["test"] >= B.MINS["test"] else "pocos datos"})
            continue
        Xtr, ytr = parts["train"][B.PRED].to_numpy(), parts["train"]["y"].to_numpy()
        Xva, yva = parts["val"][B.PRED].to_numpy(), parts["val"]["y"].to_numpy()
        Xte = parts["test"][B.PRED].to_numpy()
        scores = [(B.nse(yva, B.ridge_fit(Xtr, ytr, a)(Xva)), a) for a in B.ALPHAS]
        best_alpha = max(scores)[1]
        pred = B.ridge_fit(Xtr, ytr, best_alpha)(Xte)
        pers = parts["test"][B.T].to_numpy()
        rows.append({"variante": variant, "clave": k, **{f"n_{s}": v for s, v in n.items()},
                     "alpha": best_alpha,
                     "NSE_persistencia": B.nse(yte, pers), "KGE_persistencia": B.kge(yte, pers),
                     "NSE_ridge": B.nse(yte, pred), "KGE_ridge": B.kge(yte, pred),
                     "MSE_ridge": float(np.mean((pred - yte) ** 2)),
                     "MSE_persistencia": float(np.mean((pers - yte) ** 2))})
        tests.append(parts["test"][["fecha_obj", "imputado_en_ventana", "q_t_imputado"]].assign(clave=k))
    test = pd.concat(tests, ignore_index=True) if tests else pd.DataFrame()
    return pd.DataFrame(rows), pd.DataFrame(excluded), test


def summary(per: pd.DataFrame) -> pd.DataFrame:
    """Mismo formato que baseline_summary.csv."""
    summ = []
    for variant, pv in per.groupby("variante", sort=False):
        for m in ("persistencia", "ridge"):
            row = {"variante": variant, "modelo": m, "n_estaciones": len(pv)}
            for met in ("NSE", "KGE"):
                q = pv[f"{met}_{m}"].quantile([0.25, 0.5, 0.75])
                row.update({f"{met}_mediana": round(q[0.5], 3), f"{met}_q25": round(q[0.25], 3),
                            f"{met}_q75": round(q[0.75], 3)})
            summ.append(row)
    return pd.DataFrame(summ)


def documentation() -> dict:
    b = ROOT / "scripts" / "dib_09_baseline.py"
    f = ROOT / "src" / "hidroxai_mx" / "features" / "__init__.py"
    s7 = ROOT / "scripts" / "07_build_features.py"
    text = b.read_text(encoding="utf-8")
    return {
        "particion_por_fecha_del_objetivo": [line_of(b, 'd["fecha_obj"] = d.index + pd.Timedelta(days=1)'),
                                             line_of(b, 'parts = {s: d[d["fecha_obj"].between(a, b)]')],
        "sin_barajar": {"llamadas_aleatorias_en_dib_09": bool(re.search(r"random|shuffle|\.sample\(|permutation", text)),
                        "ajuste_cerrado": line_of(b, "beta = np.linalg.solve(")},
        "estandarizacion_con_entrenamiento": [line_of(b, "mu, sd = X.mean(0), X.std(0)"),
                                              line_of(b, "pred = ridge_fit(Xtr, ytr, best_alpha)(Xte)")],
        "alpha_en_validacion": [line_of(b, "scores = [(nse(yva, ridge_fit(Xtr, ytr, a)(Xva)), a) for a in ALPHAS]"),
                                line_of(b, "best_alpha = max(scores)[1]")],
        "rezagos_shift": [line_of(f, 'df[f"{col}_lag{k}"] = df.groupby(group)[col].shift(k)'),
                          line_of(s7, "g = F.add_lags(g, target)")],
        "medias_moviles_hasta_t": [line_of(f, "s.rolling(w, min_periods=max(2, w // 2)).mean())"),
                                   line_of(s7, "g = F.add_rolling(g, target)")],
        "objetivo_t_mas_1": line_of(b, 'd["y"] = g[T].shift(-1)'),
        "modelo_por_estacion": line_of(b, 'for k, g in ft.groupby("clave_estacion"):'),
    }


def calendar_check(ft: pd.DataFrame) -> dict:
    """shift(k) desplaza filas. 07_build_features.py lo aplica a la serie procesada antes del dropna,
    así que equivale a k días si esa serie tiene calendario diario completo. Se comprueba en la serie
    y, directamente, que lag1 y lag30 de la tabla de predictores sean Q(t−1 día) y Q(t−30 días)."""
    s = read_series(sorted(ft["clave_estacion"].unique()), None)
    g = s.groupby("clave_estacion")["fecha"]
    span = (g.max() - g.min()).dt.days + 1
    out = {"serie_estaciones": int(len(span)), "serie_con_calendario_completo": int((g.size() == span).sum()),
           "serie_filas_duplicadas": int(s.duplicated(["clave_estacion", "fecha"]).sum())}
    q = s.set_index(["clave_estacion", "fecha"])["gasto_medio_m3s"]
    for k in (1, 30):
        col = f"gasto_medio_m3s_lag{k}"
        f = ft.loc[ft[col].notna(), ["clave_estacion", "fecha", col]]
        prev = q.reindex(pd.MultiIndex.from_arrays([f["clave_estacion"], f["fecha"] - pd.Timedelta(days=k)])).to_numpy()
        out[f"lag{k}_no_nulos"] = int(len(f))
        out[f"lag{k}_igual_a_Q_t_menos_{k}_dias"] = int(np.sum(f[col].to_numpy() == prev))
    return out


def t1() -> dict:
    B = baseline_module()
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad"] + B.PRED,
                         filters=[("clave_estacion", "in", sel["clave"].tolist())])
    ft["fecha"] = pd.to_datetime(ft["fecha"])

    main, main_exc, main_test = run_variant(B, ft, MAIN)
    frozen = pd.read_csv(OUT / "baseline_por_estacion.csv", dtype={"clave": str})
    frozen = frozen[frozen["variante"] == MAIN].set_index("clave").sort_index()
    mine = main.set_index("clave").sort_index()
    cols = ["n_train", "n_val", "n_test", "alpha", "NSE_persistencia", "KGE_persistencia", "NSE_ridge", "KGE_ridge"]
    if list(frozen.index) != list(mine.index):
        raise SystemExit("la variante principal no reproduce las estaciones de baseline_por_estacion.csv")
    worst = float(np.max(np.abs(frozen[cols].to_numpy(float) - mine[cols].to_numpy(float))))
    if worst > 1e-9:
        raise SystemExit(f"la variante principal no reproduce baseline_por_estacion.csv ({worst:.2e})")

    new, new_exc, new_test = run_variant(B, ft, NEW)
    both = pd.concat([main, new], ignore_index=True)
    both["skill"] = 1 - both["MSE_ridge"] / both["MSE_persistencia"]
    summ = summary(both)
    summ.to_csv(R2 / "baseline_sin_imputados_summary.csv", index=False)
    new.drop(columns=["MSE_ridge", "MSE_persistencia"]).to_csv(R2 / "baseline_sin_imputados_por_estacion.csv", index=False)
    both[["variante", "clave", "MSE_ridge", "MSE_persistencia", "skill"]].to_csv(R2 / "skill_vs_persistencia.csv", index=False)

    n_test = len(main_test)
    leak = {
        "emisiones_prueba": n_test, "estaciones": int(main_test["clave"].nunique()),
        "con_imputado_en_ventana": int((main_test["imputado_en_ventana"] == 1).sum()),
        "fraccion_imputado_en_ventana": float((main_test["imputado_en_ventana"] == 1).mean()),
        "con_q_t_imputado": int((main_test["q_t_imputado"] == 1).sum()),
        "fraccion_q_t_imputado": float((main_test["q_t_imputado"] == 1).mean()),
        "estaciones_con_q_t_imputado": int(main_test.loc[main_test["q_t_imputado"] == 1, "clave"].nunique()),
        "lectura": "Q(t) imputado implica un hueco que termina en t; su interpolación usa Q(t+1), el objetivo.",
    }
    write_json(R2 / "fraccion_imputados_test.json", {"fecha": time.strftime("%Y-%m-%d"), **leak})

    ref = float(pd.read_csv(OUT / "baseline_summary.csv").query("variante == @MAIN and modelo == 'ridge'")["NSE_mediana"].iloc[0])
    nueva = float(new["NSE_ridge"].median())
    diff = nueva - ref
    lost_test = n_test - len(new_test)
    res = {
        "fecha": time.strftime("%Y-%m-%d"),
        "control": {"estaciones": len(mine), "max_diferencia": worst},
        "documentacion": documentation(), "calendario_feature_table": calendar_check(ft),
        "fuga": leak,
        "variantes": {v: {"estaciones_evaluadas": int(len(p)), "estaciones_excluidas": int(len(e)),
                          "ridge_mejor_que_persistencia_NSE": int((p["NSE_ridge"] > p["NSE_persistencia"]).sum()),
                          "emisiones_prueba": int(len(t))}
                      for v, p, e, t in ((MAIN, main, main_exc, main_test), (NEW, new, new_exc, new_test))},
        "emisiones_prueba_perdidas": {"n": lost_test, "fraccion": lost_test / n_test if n_test else None},
        "estaciones_perdidas": sorted(set(main["clave"]) - set(new["clave"])),
        "skill": {v: {**iqr(g["skill"]), "skill_positivo": int((g["skill"] > 0).sum())}
                  for v, g in both.groupby("variante", sort=False)},
        "criterio": {"referencia_NSE_ridge": ref, "nueva_NSE_ridge": nueva, "diferencia": diff,
                     "umbral": UMBRAL_T1,
                     "resultado": "sin cambio material" if abs(diff) < UMBRAL_T1 else "detenerse"},
    }
    # Diagnóstico no preregistrado en E14 (agregado tras ver el resultado): separa el efecto de la
    # muestra (estaciones que la variante nueva deja fuera) del efecto de quitar los imputados.
    same = main[main["clave"].isin(new["clave"])].set_index("clave").loc[new["clave"]]
    lost = main[~main["clave"].isin(new["clave"])]
    paired = new.set_index("clave")
    res["diagnostico_no_preregistrado"] = {
        "nota": "No forma parte del criterio de E14; se calculó después de ver el resultado.",
        "mismas_estaciones": int(len(same)),
        "principal_en_mismas_estaciones": {"NSE_ridge_mediana": same["NSE_ridge"].median(),
                                           "NSE_persistencia_mediana": same["NSE_persistencia"].median(),
                                           "KGE_ridge_mediana": same["KGE_ridge"].median(),
                                           "KGE_persistencia_mediana": same["KGE_persistencia"].median()},
        "nueva": {"NSE_ridge_mediana": paired["NSE_ridge"].median(),
                  "NSE_persistencia_mediana": paired["NSE_persistencia"].median()},
        "diferencia_NSE_ridge_mediana_mismas_estaciones": paired["NSE_ridge"].median() - same["NSE_ridge"].median(),
        "mediana_de_diferencias_por_estacion_NSE_ridge": float((paired["NSE_ridge"] - same["NSE_ridge"]).median()),
        "estaciones_perdidas": {"n": int(len(lost)), "NSE_ridge_mediana_en_principal": lost["NSE_ridge"].median(),
                                "NSE_persistencia_mediana_en_principal": lost["NSE_persistencia"].median()},
    }
    write_json(R2 / "t1_resumen.json", res)
    log.info("T1: %s", res["criterio"])
    return res


# --------------------------------------------------------------------------- #
# T2 y T3
# --------------------------------------------------------------------------- #
def read_series(claves: list[str], years) -> pd.DataFrame:
    dataset = pads.dataset(str(PROCESSED / "series_hidrometricas.parquet"), format="parquet", partitioning="hive")
    keep = pc.is_in(pc.field("clave_estacion"), value_set=pa.array(claves, type=pa.string()))
    if years is not None:
        keep = keep & pc.is_in(pc.field("anio"), value_set=pa.array(list(years), type=pa.int32()))
    df = dataset.to_table(columns=["clave_estacion", "fecha", "gasto_medio_m3s", "calidad"], filter=keep).to_pandas()
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def date_stats(s: pd.Series) -> dict:
    s = s.dropna().sort_values()
    return {"minimo": str(s.iloc[0].date()), "mediana": str(s.iloc[(len(s) - 1) // 2].date()),
            "maximo": str(s.iloc[-1].date()), "n": int(len(s))}


def t2() -> dict:
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    df = read_series(sel["clave"].tolist(), range(2023, 2026))
    df = df[df["fecha"].between(*TEST) & df["gasto_medio_m3s"].notna() & (df["calidad"] != 2)]
    last = df.groupby("clave_estacion")["fecha"].max()
    unit = units()
    unit_of = unit.reindex(last.index).fillna("fuera de unidad")
    by_unit = {u: date_stats(last[unit_of == u]) for u in sorted(unit_of.unique())}
    B = baseline_module()
    sel_ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad"] + B.PRED,
                             filters=[("clave_estacion", "in", sel["clave"].tolist())])
    sel_ft["fecha"] = pd.to_datetime(sel_ft["fecha"])
    _, _, test = run_variant(B, sel_ft, MAIN)
    global_last = last.max()
    res = {"fecha": time.strftime("%Y-%m-%d"), "ultima_fecha_global": str(global_last.date()),
           "por_estacion": date_stats(last), "estaciones_con_dato_en_prueba": int(len(last)),
           "estaciones_en_ultima_fecha": int((last == global_last).sum()),
           "por_unidad": by_unit,
           "fin_declarado_en_SPLITS": B.SPLITS["test"][1],
           "emisiones_prueba_variante_principal": int(len(test)),
           "ultima_fecha_objetivo_de_prueba": str(test["fecha_obj"].max().date()),
           "emisiones_despues_de_la_ultima_fecha": int((test["fecha_obj"] > global_last).sum()),
           "estaciones_sin_dato_en_prueba": sorted(set(sel["clave"]) - set(last.index))}
    write_json(R2 / "fin_registro_test.json", res)
    log.info("T2: %s", {k: res[k] for k in ("ultima_fecha_global", "emisiones_despues_de_la_ultima_fecha")})
    return res


def gaps(missing: np.ndarray) -> list[int]:
    """Rachas de faltantes con dato a ambos lados (huecos internos)."""
    runs, n, seen = [], 0, False
    for m in missing:
        if m:
            n += 1
        else:
            if n and seen:
                runs.append(n)
            n, seen = 0, True
    return runs


def t3() -> pd.DataFrame:
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    unit = units()
    df = read_series(sel["clave"].tolist(), range(2010, 2026))
    df = df[df["fecha"].between(*FIN_PERIODO)].drop_duplicates(["clave_estacion", "fecha"], keep="last")
    calendar = pd.date_range(*FIN_PERIODO, freq="D")
    end_record = df["fecha"].max()  # fin del registro (T2); los días posteriores también son faltantes
    per = pd.read_csv(OUT / "baseline_por_estacion.csv", dtype={"clave": str})
    per = per[per["variante"] == MAIN].set_index("clave")
    stations = []
    for clave in sel["clave"]:
        s = df[df["clave_estacion"] == clave].set_index("fecha").reindex(calendar)
        has = s["gasto_medio_m3s"].notna()
        stations.append({"clave": clave, "unidad": unit.get(clave, "fuera de unidad"), "dias": len(calendar),
                         "faltantes": int((~has).sum()), "huecos": gaps((~has).to_numpy()),
                         "dias_hasta_fin": int((calendar <= end_record).sum()),
                         "faltantes_hasta_fin": int((~has[calendar <= end_record]).sum()),
                         "con_dato": int(has.sum()), "calidad_1": int((s.loc[has, "calidad"] == 1).sum()),
                         "calidad_2": int((s.loc[has, "calidad"] == 2).sum())})
    st = pd.DataFrame(stations).merge(sel[["clave", "cobertura"]], on="clave")
    rows = []
    order = [u for u in sorted(st["unidad"].unique()) if u != "fuera de unidad"] + ["fuera de unidad", "total"]
    for u in order:
        g = st if u == "total" else st[st["unidad"] == u]
        lengths = [x for runs in g["huecos"] for x in runs]
        ev = per.loc[per.index.intersection(g["clave"])]
        rows.append({
            "unidad": u, "estaciones_seleccionadas": len(g),
            "cobertura_mediana": g["cobertura"].median(), "cobertura_min": g["cobertura"].min(),
            "cobertura_max": g["cobertura"].max(),
            "fraccion_dias_faltantes": g["faltantes"].sum() / g["dias"].sum(),
            "fin_registro": str(end_record.date()),
            "fraccion_dias_faltantes_hasta_fin_registro": g["faltantes_hasta_fin"].sum() / g["dias_hasta_fin"].sum(),
            "huecos": len(lengths),
            "hueco_mediana_dias": float(np.median(lengths)) if lengths else np.nan,
            "hueco_p90_dias": float(np.quantile(lengths, 0.9)) if lengths else np.nan,
            "hueco_max_dias": int(max(lengths)) if lengths else np.nan,
            "fraccion_calidad_1": g["calidad_1"].sum() / g["con_dato"].sum(),
            "fraccion_calidad_2": g["calidad_2"].sum() / g["con_dato"].sum(),
            "estaciones_evaluables_baseline": len(ev),
            "NSE_ridge_mediana": ev["NSE_ridge"].median() if len(ev) else np.nan,
        })
    out = pd.DataFrame(rows)
    out.to_csv(R2 / "cobertura_por_unidad.csv", index=False)
    log.info("T3: %d filas", len(out))
    return out


# --------------------------------------------------------------------------- #
# T4
# --------------------------------------------------------------------------- #
GRIDS = (("minuto", 1 / 60, 1e-6), ("0.01°", 0.01, 1e-6), ("0.001°", 0.001, 1e-6), ("segundo", 1 / 3600, 0.01 / 3600))


def on_grid(x: float, step: float, tol: float) -> bool:
    return abs(x - round(x / step) * step) <= tol


def rounding_table(sel: pd.DataFrame) -> pd.DataFrame:
    from hidroxai_mx.geo.spatial import meters_per_degree
    rows = []
    for _, s in sel.iterrows():
        grid, step = "más fina que segundo", None
        for name, st, tol in GRIDS:
            if on_grid(s["latitud"], st, tol) and on_grid(s["longitud"], st, tol):
                grid, step = name, st
                break
        m_lat, m_lon = meters_per_degree(s["latitud"])
        rows.append({"clave": s["clave"], "malla": grid,
                     "parece_redondeada": grid in ("minuto", "0.01°", "0.001°"),
                     "incertidumbre_lat_m": step / 2 * float(m_lat) if step else np.nan,
                     "incertidumbre_lon_m": step / 2 * float(m_lon) if step else np.nan})
    return pd.DataFrame(rows)


def read_rivers(path: Path, sel: pd.DataFrame):
    import geopandas as gpd
    pad = 1.0
    bbox = (sel["longitud"].min() - pad, sel["latitud"].min() - pad, sel["longitud"].max() + pad, sel["latitud"].max() + pad)
    t0 = time.time()
    hr = gpd.read_file(path, bbox=bbox, columns=["HYRIV_ID", "UPLAND_SKM"]).to_crs("EPSG:6372")
    return hr, time.time() - t0


def link(hr, sel: pd.DataFrame, radius_deg: float) -> pd.DataFrame:
    """La regla de scripts/06_link_hydrorivers.py con otro radio."""
    import geopandas as gpd

    from hidroxai_mx.geo.spatial import meters_per_degree
    pts = gpd.GeoSeries(gpd.points_from_xy(sel["longitud"], sel["latitud"]), crs="EPSG:4326").to_crs("EPSG:6372")
    rows = []
    for (_, s), p in zip(sel.iterrows(), pts, strict=True):
        m_lat, m_lon = meters_per_degree(s["latitud"])
        r_m = radius_deg * float(np.mean([m_lat, m_lon]))
        cand = hr.iloc[hr.sindex.query(p.buffer(r_m))].copy()
        cand["d"] = cand.geometry.distance(p)
        cand = cand[cand["d"] <= r_m]
        if cand.empty:
            rows.append({"clave": s["clave"], "hyriv_id": pd.NA, "dist_m": np.nan, "upland_km2": np.nan})
        else:
            big = cand.loc[cand["UPLAND_SKM"].idxmax()]
            rows.append({"clave": s["clave"], "hyriv_id": int(big["HYRIV_ID"]), "dist_m": round(float(big["d"]), 1),
                         "upland_km2": float(big["UPLAND_SKM"])})
    out = pd.DataFrame(rows)
    out["hyriv_id"] = out["hyriv_id"].astype("Int64")
    return out


def t4(hydrorivers: Path | None) -> dict:
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    link_pub = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    link_pub["unidad"] = link_pub["unidad_piloto"].fillna("fuera de unidad")

    def dist_rows(frame: pd.DataFrame, label: str) -> dict:
        out = {"ambito": label, "estaciones": len(frame), "con_tramo": int(frame["hyriv_id"].notna().sum())}
        for col in ("dist_m", "dist_cercano_m"):
            v = frame[col].dropna()
            out.update({f"{col}_mediana": v.median(), f"{col}_p90": v.quantile(0.9), f"{col}_max": v.max()})
        return out

    dist = [dist_rows(link_pub, "global")] + [dist_rows(g, u) for u, g in link_pub.groupby("unidad")]
    rnd = rounding_table(sel)
    dist_df = pd.DataFrame(dist)
    dist_df.to_csv(R2 / "hydrorivers_distancias.csv", index=False)
    rnd.to_csv(R2 / "coordenadas_redondeo.csv", index=False)

    diff = link_pub[link_pub["tramos_distintos"].fillna(False).astype(bool)].copy()
    diff["razon_area_cercano_mayor"] = diff["upland_cercano_km2"] / diff["upland_km2"]
    diff["difiere_mas_de_factor_2"] = (diff["razon_area_cercano_mayor"] < 0.5) | (diff["razon_area_cercano_mayor"] > 2)
    diff[["clave", "unidad", "hyriv_id", "dist_m", "upland_km2", "hyriv_id_cercano", "dist_cercano_m",
          "upland_cercano_km2", "razon_area_cercano_mayor", "difiere_mas_de_factor_2"]].to_csv(
        R2 / "hydrorivers_tramos_distintos.csv", index=False)

    none = link_pub[link_pub["hyriv_id"].isna()][["clave", "unidad"]].copy()
    res = {"fecha": time.strftime("%Y-%m-%d"), "shapefile_disponible": hydrorivers is not None}
    if hydrorivers is not None:
        hr, seconds = read_rivers(hydrorivers, sel)
        res["segundos_lectura"] = seconds
        import geopandas as gpd
        pts = gpd.GeoSeries(gpd.points_from_xy(sel["longitud"], sel["latitud"]), crs="EPSG:4326",
                            index=sel["clave"]).to_crs("EPSG:6372")
        near = []
        for clave in none["clave"]:
            d = hr.geometry.distance(pts[clave])
            i = d.idxmin()
            near.append({"clave": clave, "dist_tramo_mas_cercano_m": round(float(d[i]), 1),
                         "hyriv_id_mas_cercano": int(hr.loc[i, "HYRIV_ID"]), "upland_km2": float(hr.loc[i, "UPLAND_SKM"])})
        none = none.merge(pd.DataFrame(near), on="clave", how="left")
        if seconds <= LIMITE_LECTURA_S:
            ref = link(hr, sel, 0.01)
            pub = link_pub.set_index("clave").loc[ref["clave"]]
            same_id = (ref["hyriv_id"].astype("Float64").fillna(-1).to_numpy() ==
                       pub["hyriv_id"].astype("Float64").fillna(-1).to_numpy())
            same_d = np.allclose(ref["dist_m"].to_numpy(float), pub["dist_m"].to_numpy(float), equal_nan=True)
            reproduced = bool(same_id.all() and same_d)
            res["radio_0_01_reproduce_vinculo_publicado"] = reproduced
            if reproduced:
                rows = []
                for r in RADIOS:
                    alt = link(hr, sel, r)
                    a = alt["hyriv_id"].astype("Float64").fillna(-1).to_numpy()
                    b = ref["hyriv_id"].astype("Float64").fillna(-1).to_numpy()
                    gained = int((alt["hyriv_id"].notna() & ref["hyriv_id"].isna()).sum())
                    lost = int((alt["hyriv_id"].isna() & ref["hyriv_id"].notna()).sum())
                    other = (a != b) & (a != -1) & (b != -1)
                    ratio = (alt["upland_km2"] / ref["upland_km2"])[other]
                    rows.append({"radio_grados": r, "con_tramo": int(alt["hyriv_id"].notna().sum()),
                                 "asignaciones_que_cambian": int((a != b).sum()),
                                 "otro_tramo_asignado": int(other.sum()),
                                 "ganan_tramo": gained, "pierden_tramo": lost,
                                 "razon_area_otro_tramo_mediana": ratio.median() if len(ratio) else np.nan,
                                 "otro_tramo_difiere_mas_de_factor_2": int(((ratio < 0.5) | (ratio > 2)).sum())})
                pd.DataFrame(rows).to_csv(R2 / "hydrorivers_sensibilidad_radio.csv", index=False)
        else:
            res["radio_0_01_reproduce_vinculo_publicado"] = None
            res["sensibilidad_omitida"] = f"lectura de {seconds:.0f} s > {LIMITE_LECTURA_S} s"
    none.to_csv(R2 / "hydrorivers_sin_vinculo.csv", index=False)
    res.update({"tramos_distintos": int(len(diff)), "difieren_mas_de_factor_2": int(diff["difiere_mas_de_factor_2"].sum()),
                "sin_tramo": int(len(none)),
                "redondeo": rnd["malla"].value_counts().to_dict(),
                "parecen_redondeadas": int(rnd["parece_redondeada"].sum()),
                "redondeadas_sin_tramo": int(rnd["parece_redondeada"][rnd["clave"].isin(none["clave"])].sum()),
                "redondeadas_en_tramos_distintos": int(rnd["parece_redondeada"][rnd["clave"].isin(diff["clave"])].sum())})
    write_json(R2 / "t4_resumen.json", res)
    log.info("T4: %s", {k: v for k, v in res.items() if k != "redondeo"})
    return res


# --------------------------------------------------------------------------- #
# T5
# --------------------------------------------------------------------------- #
def run(cmd: list, cwd: Path) -> float:
    """Sin PYTHONPATH: la copia limpia debe usar solo su propia instalación del paquete."""
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "HIDROXAI_DATA")}
    t0 = time.time()
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    if r.returncode != 0:
        raise SystemExit(f"Falló: {' '.join(map(str, cmd))}\n{(r.stdout + r.stderr)[-3000:]}")
    return time.time() - t0


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in IGNORAR}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


REL_TOL, ABS_TOL = 1e-12, 1e-12   # JSON: números con tolerancia (como los CSV); abs_tol para valores ≈ 0


def same_file(a: Path, b: Path) -> tuple[bool, str]:
    """CSV por valor con rtol 1e-12; JSON por valor sin fechas de ejecución, los números con
    rel_tol = abs_tol = 1e-12 (un residuo de control de 5.7e-14 frente a 0.0 cuenta como igual)."""
    if not a.exists() or not b.exists():
        return False, f"regenerado={a.exists()} repositorio={b.exists()}"
    if a.suffix == ".json":
        ja, jb = strip(json.loads(a.read_text(encoding="utf-8"))), strip(json.loads(b.read_text(encoding="utf-8")))
        diffs = []

        def num(x):
            return isinstance(x, (int, float)) and not isinstance(x, bool)

        def walk(x, y, path):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in sorted(set(x) | set(y)):
                    walk(x.get(k), y.get(k), f"{path}.{k}" if path else k)
            elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
                for i, (u, v) in enumerate(zip(x, y, strict=True)):
                    walk(u, v, f"{path}[{i}]")
            elif num(x) and num(y):
                if not math.isclose(x, y, rel_tol=REL_TOL, abs_tol=ABS_TOL):
                    diffs.append(f"{path}: copia {x!r}, repositorio {y!r}")
            elif x != y:
                diffs.append(f"{path}: copia {x!r}, repositorio {y!r}")

        walk(ja, jb, "")
        if not diffs:
            return True, "valores sin fechas de ejecución (números con tolerancia 1e-12)"
        return False, "difiere en " + "; ".join(diffs)[:400]
    try:
        pd.testing.assert_frame_equal(pd.read_csv(a), pd.read_csv(b), check_exact=False, rtol=1e-12)
        return True, "valores, rtol 1e-12"
    except AssertionError as e:
        return False, str(e)[:200]


def copia(zip_path: Path, work: Path, hydrorivers: Path | None, reuse: bool = False) -> dict:
    """reuse: la copia de `work` ya pasó por dib_16 (r2/clean_copy_check_r2.json); no se repite la
    instalación, pero dib_09, dib_15 y dib_17 vuelven a correr dentro de ella."""
    t0 = time.time()
    if reuse:
        if not ((work / "hidromx").is_dir() and (R2 / "clean_copy_check_r2.json").exists()):
            raise SystemExit("--reusar-copia requiere una copia de dib_16 en --work y r2/clean_copy_check_r2.json")
    else:
        # dib_16 escribe un registro nuevo con fecha y hora (clean_copy_check_<AAAAMMDD-HHMMSS>.*), sin
        # sobrescribir los anteriores; aquí se copia el de esta corrida a r2/.
        before = set(OUT.glob("clean_copy_check_*.json"))
        # Intérprete base (no el del .venv del repositorio), como en la prueba de v2026.10: el
        # registro de dib_16 guarda el comando y no debe llevar rutas locales del repositorio.
        base_py = getattr(sys, "_base_executable", sys.executable)
        run([sys.executable, ROOT / "scripts" / "dib_16_clean_copy_check.py", "--zip", zip_path, "--work", work,
             "--python", base_py], ROOT)
        new = sorted(set(OUT.glob("clean_copy_check_*.json")) - before)
        if not new:
            raise SystemExit("dib_16 no dejó un registro nuevo clean_copy_check_*.json")
        for suf in (".json", ".md"):
            shutil.copy2(new[-1].with_suffix(suf), R2 / f"clean_copy_check_r2{suf}")
    root = work / "hidromx"
    py = work / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    shutil.copy2(Path(__file__), root / "scripts" / Path(__file__).name)
    (root / "results" / "dib_revision" / "r2").mkdir(parents=True, exist_ok=True)
    times = {"dib_09": run([py, "-W", "ignore", "scripts/dib_09_baseline.py"], root)}
    try:
        times["dib_15"] = run([py, "-W", "ignore", "scripts/dib_15_submission_figures.py"], root)
    except SystemExit as e:
        times["dib_15"] = f"falló: {str(e)[:200]}"
    # Figuras S1 y S2 (experimentos E3 y E4); no forman parte del criterio de T5 en E14.
    for s in ("dib_03", "dib_04"):
        name = {"dib_03": "dib_03_imputation_masking.py", "dib_04": "dib_04_outliers.py"}[s]
        try:
            times[s] = run([py, "-W", "ignore", f"scripts/{name}"], root)
        except SystemExit as e:
            times[s] = f"falló: {str(e)[:200]}"
    extra = ["--hydrorivers", hydrorivers] if hydrorivers else []
    for task in ("t1", "t2", "t3", "t4"):  # una por una, para el tiempo de cada cifra
        times[f"dib_17_{task}"] = run([py, "-W", "ignore", "scripts/dib_17_r2_checks.py", "--tareas", task,
                                       *(extra if task == "t4" else [])], root)

    regen = root / "results" / "dib_revision"
    summ = pd.read_csv(regen / "baseline_summary.csv").set_index(["variante", "modelo"])
    e9 = json.loads((regen / "e9_baseline.json").read_text(encoding="utf-8"))
    v = e9["variantes"][MAIN]
    clean = json.loads((R2 / "clean_copy_check_r2.json").read_text(encoding="utf-8"))
    tabla3 = next(c for c in clean["comparaciones"] if c["archivo"].endswith("tabla3_v2026_10.csv"))
    items = [
        {"cifra": "NSE mediana persistencia", "esperado": 0.528, "obtenido": summ.loc[(MAIN, "persistencia"), "NSE_mediana"], "archivo": "baseline_summary.csv:NSE_mediana"},
        {"cifra": "NSE mediana Ridge", "esperado": 0.594, "obtenido": summ.loc[(MAIN, "ridge"), "NSE_mediana"], "archivo": "baseline_summary.csv:NSE_mediana"},
        {"cifra": "KGE mediana persistencia", "esperado": 0.764, "obtenido": summ.loc[(MAIN, "persistencia"), "KGE_mediana"], "archivo": "baseline_summary.csv:KGE_mediana"},
        {"cifra": "KGE mediana Ridge", "esperado": 0.642, "obtenido": summ.loc[(MAIN, "ridge"), "KGE_mediana"], "archivo": "baseline_summary.csv:KGE_mediana"},
        {"cifra": "Ridge > persistencia (de evaluadas)", "esperado": "75 de 97",
         "obtenido": f"{v['ridge_mejor_que_persistencia_NSE']} de {v['estaciones_evaluadas']}", "archivo": "e9_baseline.json"},
        {"cifra": "Tabla 3", "esperado": "igual", "obtenido": tabla3["resultado"], "archivo": "tabla3_v2026_10.csv (vía dib_16)"},
    ]
    items.append({"cifra": "Datos fuente de Fig. 1–7 (metrics.json y CSV de reportes)", "esperado": "igual",
                  "obtenido": "igual" if clean["valores_identicos"] else "difiere",
                  "archivo": "clean_copy_check_r2.json:valores_identicos"})
    fa, fb = regen / "figuras_envio.csv", OUT / "figuras_envio.csv"
    if fa.exists():
        # La columna origen es relativa a la raíz: data/processed/… en el repositorio y processed/… en
        # el archivo de Zenodo, que no tiene data/ (hidroxai_mx.utils._data_root). Se compara sin ese prefijo.
        ta, tb = pd.read_csv(fa), pd.read_csv(fb)
        tb["origen"] = tb["origen"].str.replace(r"^data/", "", regex=True)
        try:
            pd.testing.assert_frame_equal(ta, tb)
            det_fig = "igual"
        except AssertionError as e:
            det_fig = str(e)[:200]
    else:
        det_fig = f"no se generó ({times['dib_15']})"
    items.append({"cifra": "Figuras de envío (figuras_envio.csv)", "esperado": "igual", "obtenido": det_fig,
                  "archivo": "figuras_envio.csv (origen sin el prefijo data/)"})
    for it in items:
        it["coincide"] = it["obtenido"] == it["esperado"]
    comps = []
    for name in ("baseline_summary.csv", "baseline_por_estacion.csv", "baseline_excluidas.csv", "e9_baseline.json"):
        ok, det = same_file(regen / name, OUT / name)
        comps.append({"archivo": name, "coincide": ok, "detalle": det})
    r2_files = [p for p in sorted(R2.iterdir()) if p.suffix in (".csv", ".json")
                and not p.name.startswith(("reproducibilidad", "clean_copy_check"))]
    for p in r2_files:
        ok, det = same_file(regen / "r2" / p.name, p)
        comps.append({"archivo": f"r2/{p.name}", "coincide": ok, "detalle": det})
    supl = []
    for name in ("imputation_masking_summary.csv", "imputation_masking_gaps.csv", "e3_imputation.json",
                 "outliers_hidro.csv", "outliers_por_estacion.csv", "e4_outliers.json"):
        ok, det = same_file(regen / name, OUT / name)
        supl.append({"archivo": name, "coincide": ok, "detalle": det})
    res = {"fecha": time.strftime("%Y-%m-%d"), "zip": zip_path.name, "minutos": round((time.time() - t0) / 60, 1),
           "copia_reusada": reuse,
           "python_entorno": clean.get("python_entorno"), "dib_16": {k: clean[k] for k in ("ok", "valores_identicos", "figuras_identicas", "minutos_total", "minutos_pip_install")},
           "segundos_por_script": times, "cifras": items, "salidas_r2": comps,
           "todo_coincide": all(i["coincide"] for i in items) and all(c["coincide"] for c in comps),
           "figuras_suplementarias_fuera_de_E14": supl}
    write_json(R2 / "reproducibilidad.json", res)
    log.info("T5: todo_coincide=%s", res["todo_coincide"])
    return res


# --------------------------------------------------------------------------- #
# Reporte
# --------------------------------------------------------------------------- #
LOCKS = ("requirements.txt", "requirements-lock.txt", "uv.lock", "poetry.lock", "pdm.lock",
         "environment.yml", "conda-lock.yml", "Pipfile.lock")


def fmt(x, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    if isinstance(x, (bool, np.bool_)):
        return "sí" if x else "no"
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}".replace(",", " ")
    if isinstance(x, (float, np.floating)):
        return f"{x:.{nd}f}"
    return str(x)


def pct(x) -> str:
    return f"{100 * x:.1f} %"


def table(df: pd.DataFrame, nd: int = 3) -> list[str]:
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    out += ["| " + " | ".join(fmt(v, nd) for v in row) + " |" for row in df.itertuples(index=False)]
    return out


def write_report(r2: Path) -> None:
    rd = lambda n: json.loads((r2 / n).read_text(encoding="utf-8"))  # noqa: E731
    t1r, leak, t2r, t4r = rd("t1_resumen.json"), rd("fraccion_imputados_test.json"), rd("fin_registro_test.json"), rd("t4_resumen.json")
    summ = pd.read_csv(r2 / "baseline_sin_imputados_summary.csv")
    cov = pd.read_csv(r2 / "cobertura_por_unidad.csv")
    dist = pd.read_csv(r2 / "hydrorivers_distancias.csv")
    diff = pd.read_csv(r2 / "hydrorivers_tramos_distintos.csv", dtype={"clave": str})
    none = pd.read_csv(r2 / "hydrorivers_sin_vinculo.csv", dtype={"clave": str})
    sens_p = r2 / "hydrorivers_sensibilidad_radio.csv"
    rep_p = r2 / "reproducibilidad.json"
    rep = json.loads(rep_p.read_text(encoding="utf-8")) if rep_p.exists() else None
    crit = t1r["criterio"]
    rounded = ", ".join(f"{k} {n}" for k, n in t4r["redondeo"].items() if k in ("minuto", "0.01°", "0.001°"))
    if rep and not rep["todo_coincide"]:
        bad = [i["cifra"] for i in rep["cifras"] if not i["coincide"]] + \
              [f"`{c['archivo']}` ({c['detalle']})" for c in rep["salidas_r2"] if not c["coincide"]]
        t5_line = (f"- **T5:** de las {len(rep['cifras'])} cifras del manuscrito, "
                   f"{sum(i['coincide'] for i in rep['cifras'])} coinciden; de las {len(rep['salidas_r2'])} salidas "
                   f"regeneradas, {sum(c['coincide'] for c in rep['salidas_r2'])} coinciden. Difiere: {'; '.join(bad)}.")
    elif rep:
        t5_line = "- **T5:** todo coincide."
    else:
        t5_line = "- **T5:** pendiente (`r2/reproducibilidad.json` no existe)."
    L = ["# R2_report · DIB-D-26-01662R1, segunda revisión", "",
         f"Generado por `scripts/dib_17_r2_checks.py --tareas reporte` el {time.strftime('%Y-%m-%d')}. Criterios "
         "congelados en `results/dib_revision/proof_ledger.md` (E14). Rutas relativas a "
         "`results/dib_revision/`. Cada cifra sale del archivo y la columna o campo indicados.", "",
         "## Resumen", "",
         f"- **T1:** criterio de E14 = **{crit['resultado']}** (diferencia {crit['diferencia']:+.3f} en la mediana de "
         f"NSE de Ridge; umbral {crit['umbral']}). La diferencia viene de la muestra: en las mismas "
         f"{t1r['diagnostico_no_preregistrado']['mismas_estaciones']} estaciones es "
         f"{t1r['diagnostico_no_preregistrado']['diferencia_NSE_ridge_mediana_mismas_estaciones']:+.4f} (diagnóstico no "
         "preregistrado). Decisión del autor (2026-11-10): las cifras del manuscrito se quedan y la variante se "
         "reporta como verificación.",
         f"- **T2:** el registro termina el {t2r['ultima_fecha_global']}; "
         f"{t2r['emisiones_despues_de_la_ultima_fecha']} emisiones de prueba después de esa fecha.",
         "- **T3:** tabla por unidad en `r2/cobertura_por_unidad.csv`.",
         f"- **T4:** {t4r['tramos_distintos']} estaciones con tramos distintos ({t4r['difieren_mas_de_factor_2']} difieren "
         f"por más de un factor 2 en área), {t4r['sin_tramo']} sin tramo, {t4r['parecen_redondeadas']} con coordenadas "
         f"que parecen redondeadas (malla: {rounded or 'ninguna'}).",
         t5_line, ""]

    # ---- T1
    doc = t1r["documentacion"]
    cal = t1r["calendario_feature_table"]
    L += ["## T1 · R2-i, dependencia temporal y fuga en el baseline", "",
          "### Lo que ya hace `dib_09_baseline.py` (sin cambios)", "",
          "| Punto | Código | Fuente |", "|---|---|---|",
          f"| Partición cronológica por fecha del objetivo | `{'`, `'.join(doc['particion_por_fecha_del_objetivo'])}` | `r2/t1_resumen.json:documentacion` |",
          f"| Sin barajar (ajuste cerrado, sin llamadas aleatorias: {fmt(not doc['sin_barajar']['llamadas_aleatorias_en_dib_09'])}) | `{doc['sin_barajar']['ajuste_cerrado']}` | ídem |",
          f"| Estandarización con estadísticos de entrenamiento | `{'`, `'.join(doc['estandarizacion_con_entrenamiento'])}` | ídem |",
          f"| α elegido en validación | `{'`, `'.join(doc['alpha_en_validacion'])}` | ídem |",
          f"| Rezagos con `shift(k)` | `{'`, `'.join(doc['rezagos_shift'])}` | ídem |",
          f"| Medias móviles hasta *t* | `{'`, `'.join(doc['medias_moviles_hasta_t'])}` | ídem |",
          f"| Objetivo Q(*t*+1) | `{doc['objetivo_t_mas_1']}` | ídem |",
          f"| Modelo por estación | `{doc['modelo_por_estacion']}` | ídem |", "",
          "| Cifra | Valor | Archivo: campo |", "|---|---|---|",
          f"| Control: estaciones reproducidas de `baseline_por_estacion.csv` | {t1r['control']['estaciones']} | `r2/t1_resumen.json:control.estaciones` |",
          f"| Control: diferencia máxima | {t1r['control']['max_diferencia']:.1e} | `r2/t1_resumen.json:control.max_diferencia` |",
          f"| Estaciones con calendario diario completo en la serie procesada | {cal['serie_con_calendario_completo']} de {cal['serie_estaciones']} | `r2/t1_resumen.json:calendario_feature_table` |",
          f"| `lag1` = Q(t−1 día) | {fmt(cal['lag1_igual_a_Q_t_menos_1_dias'])} de {fmt(cal['lag1_no_nulos'])} | ídem |",
          f"| `lag30` = Q(t−30 días) | {fmt(cal['lag30_igual_a_Q_t_menos_30_dias'])} de {fmt(cal['lag30_no_nulos'])} | ídem |",
          f"| Emisiones de prueba (variante principal) | {fmt(leak['emisiones_prueba'])} | `r2/fraccion_imputados_test.json:emisiones_prueba` |",
          f"| Con algún `calidad = 1` en t−30…t | {fmt(leak['con_imputado_en_ventana'])} ({pct(leak['fraccion_imputado_en_ventana'])}) | `r2/fraccion_imputados_test.json:fraccion_imputado_en_ventana` |",
          f"| Con Q(t) imputado | {fmt(leak['con_q_t_imputado'])} ({pct(leak['fraccion_q_t_imputado'])}) | `r2/fraccion_imputados_test.json:fraccion_q_t_imputado` |",
          f"| Estaciones con algún Q(t) imputado en prueba | {leak['estaciones_con_q_t_imputado']} | `r2/fraccion_imputados_test.json:estaciones_con_q_t_imputado` |", "",
          "Lectura: un Q(t) imputado viene de un hueco que termina en t, y su interpolación usa Q(t+1), el objetivo. "
          "Un imputado anterior a t solo usa observaciones ≤ t.", "",
          "### Variante `sin_imputados_en_ventana` (formato de `baseline_summary.csv`)", "",
          "Fuente: `r2/baseline_sin_imputados_summary.csv` (todas las columnas).", ""]
    L += table(summ)
    v = t1r["variantes"]
    L += ["", "| Cifra | Principal | Sin imputados | Archivo: campo |", "|---|---|---|---|",
          f"| Estaciones evaluables | {v[MAIN]['estaciones_evaluadas']} | {v[NEW]['estaciones_evaluadas']} | `r2/t1_resumen.json:variantes.*.estaciones_evaluadas` |",
          f"| Ridge > persistencia (NSE) | {v[MAIN]['ridge_mejor_que_persistencia_NSE']} | {v[NEW]['ridge_mejor_que_persistencia_NSE']} | `r2/t1_resumen.json:variantes.*.ridge_mejor_que_persistencia_NSE` |",
          f"| Emisiones de prueba | {fmt(v[MAIN]['emisiones_prueba'])} | {fmt(v[NEW]['emisiones_prueba'])} | `r2/t1_resumen.json:variantes.*.emisiones_prueba` |",
          f"| Emisiones de prueba perdidas | — | {fmt(t1r['emisiones_prueba_perdidas']['n'])} ({pct(t1r['emisiones_prueba_perdidas']['fraccion'])}) | `r2/t1_resumen.json:emisiones_prueba_perdidas` |",
          f"| Estaciones perdidas | — | {len(t1r['estaciones_perdidas'])} | `r2/t1_resumen.json:estaciones_perdidas` |"]
    sk = t1r["skill"]
    L += ["", "### Skill contra persistencia (1 − MSE_ridge / MSE_persistencia)", "",
          "Fuente: `r2/skill_vs_persistencia.csv:skill`, resumido en `r2/t1_resumen.json:skill`.", "",
          "| Variante | Estaciones | Mediana | Q25 | Q75 | Skill > 0 |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {s['n']} | {fmt(s['mediana'])} | {fmt(s['q25'])} | {fmt(s['q75'])} | {s['skill_positivo']} |" for k, s in sk.items()]
    dg = t1r["diagnostico_no_preregistrado"]
    L += ["", "### Criterio de E14", "",
          "| Cifra | Valor | Archivo: campo |", "|---|---|---|",
          f"| Referencia: mediana NSE Ridge, variante principal | {fmt(crit['referencia_NSE_ridge'])} | `baseline_summary.csv:NSE_mediana` |",
          f"| Variante nueva | {fmt(crit['nueva_NSE_ridge'])} | `r2/t1_resumen.json:criterio.nueva_NSE_ridge` |",
          f"| Diferencia | {crit['diferencia']:+.3f} | `r2/t1_resumen.json:criterio.diferencia` |",
          f"| **Resultado** | **{crit['resultado']}** | `r2/t1_resumen.json:criterio.resultado` |", "",
          "### Diagnóstico no preregistrado (calculado después de ver el resultado)", "",
          "| Cifra | Valor | Archivo: campo |", "|---|---|---|",
          f"| Variante principal en las mismas {dg['mismas_estaciones']} estaciones: mediana NSE Ridge | {fmt(dg['principal_en_mismas_estaciones']['NSE_ridge_mediana'])} | `r2/t1_resumen.json:diagnostico_no_preregistrado.principal_en_mismas_estaciones` |",
          f"| Ídem, mediana NSE persistencia | {fmt(dg['principal_en_mismas_estaciones']['NSE_persistencia_mediana'])} | ídem |",
          f"| Diferencia de medianas, mismas estaciones | {dg['diferencia_NSE_ridge_mediana_mismas_estaciones']:+.4f} | `…diferencia_NSE_ridge_mediana_mismas_estaciones` |",
          f"| Mediana de diferencias por estación | {dg['mediana_de_diferencias_por_estacion_NSE_ridge']:+.4f} | `…mediana_de_diferencias_por_estacion_NSE_ridge` |",
          f"| Estaciones perdidas: mediana NSE Ridge en la variante principal | {fmt(dg['estaciones_perdidas']['NSE_ridge_mediana_en_principal'])} ({dg['estaciones_perdidas']['n']} estaciones) | `…estaciones_perdidas` |", ""]

    # ---- T2
    L += ["## T2 · R2-iv, fin del registro frente al periodo de prueba", "",
          "Fuente: `r2/fin_registro_test.json`. No se cambia el script.", "",
          "| Cifra | Valor | Campo |", "|---|---|---|",
          f"| Última fecha con dato válido (global) | {t2r['ultima_fecha_global']} | `ultima_fecha_global` |",
          f"| Por estación: mínimo / mediana / máximo | {t2r['por_estacion']['minimo']} / {t2r['por_estacion']['mediana']} / {t2r['por_estacion']['maximo']} | `por_estacion` |",
          f"| Estaciones con dato en prueba | {t2r['estaciones_con_dato_en_prueba']} | `estaciones_con_dato_en_prueba` |",
          f"| Estaciones cuyo último dato es la fecha global | {t2r['estaciones_en_ultima_fecha']} | `estaciones_en_ultima_fecha` |",
          f"| Fin declarado en `SPLITS[\"test\"]` | {t2r['fin_declarado_en_SPLITS']} | `fin_declarado_en_SPLITS` |",
          f"| Última fecha objetivo de prueba (variante principal) | {t2r['ultima_fecha_objetivo_de_prueba']} | `ultima_fecha_objetivo_de_prueba` |",
          f"| Emisiones de prueba después de la última fecha | {t2r['emisiones_despues_de_la_ultima_fecha']} | `emisiones_despues_de_la_ultima_fecha` |", "",
          "| Unidad | Estaciones | Mínimo | Mediana | Máximo |", "|---|---|---|---|---|"]
    L += [f"| {u} | {s['n']} | {s['minimo']} | {s['mediana']} | {s['maximo']} |" for u, s in t2r["por_unidad"].items()]

    # ---- T3
    c3 = cov.rename(columns={"estaciones_seleccionadas": "sel.", "cobertura_mediana": "cob. med.", "cobertura_min": "cob. mín.",
                             "cobertura_max": "cob. máx.", "fraccion_dias_faltantes": "faltantes",
                             "fraccion_dias_faltantes_hasta_fin_registro": "faltantes hasta fin", "huecos": "huecos",
                             "hueco_mediana_dias": "hueco med. (d)", "hueco_p90_dias": "hueco p90 (d)",
                             "hueco_max_dias": "hueco máx. (d)", "fraccion_calidad_1": "cal. 1",
                             "fraccion_calidad_2": "cal. 2", "estaciones_evaluables_baseline": "evaluables",
                             "NSE_ridge_mediana": "NSE Ridge med."}).drop(columns=["fin_registro"])
    c3["cal. 2"] = c3["cal. 2"].map(lambda x: f"{x:.5f}")
    for c in ("hueco med. (d)", "hueco p90 (d)"):
        c3[c] = c3[c].map(lambda x: f"{x:.1f}")
    L += ["", "## T3 · R2-ii (Q5), faltantes y cobertura por unidad operativa", "",
          "Fuente: `r2/cobertura_por_unidad.csv` (una columna por cifra; aquí con nombres abreviados).", ""]
    L += table(c3)
    L += ["", "Definiciones (E14):",
          "- *cob.* = columna `cobertura` del catálogo seleccionado: días con gasto observado antes de imputar entre "
          "2010-01-01 y 2025-12-31, sobre los 5 844 días del periodo (`scripts/05_select_stations.py`, `_coverage`).",
          "- *faltantes* = días sin gasto en la serie procesada (después de imputar) sobre el mismo calendario. "
          f"*faltantes hasta fin* = lo mismo hasta el fin del registro ({cov['fin_registro'].iloc[0]}); los días "
          "posteriores cuentan como faltantes en las demás columnas.",
          "- *huecos* = rachas de faltantes entre dos días con dato; las colas del periodo no cuentan como hueco.",
          "- *cal. 1* y *cal. 2* = fracción de días con dato con `calidad` 1 (imputado) o 2 (atípico).",
          "- *evaluables* y *NSE Ridge med.* = `baseline_por_estacion.csv`, variante principal.", ""]

    # ---- T4
    d4 = dist.rename(columns={"ambito": "ámbito", "con_tramo": "con tramo", "dist_m_mediana": "dist. asignado med. (m)",
                              "dist_m_p90": "p90", "dist_m_max": "máx.", "dist_cercano_m_mediana": "dist. más cercano med. (m)",
                              "dist_cercano_m_p90": "p90 ", "dist_cercano_m_max": "máx. "})
    L += ["## T4 · R2-iii y R3, exactitud espacial del vínculo con HydroRIVERS", "",
          "No se cambia `estaciones_hidrorivers.csv` ni el método de vínculo.", "",
          "### Distancia estación–tramo", "", "Fuente: `r2/hydrorivers_distancias.csv`.", ""]
    L += table(d4, 1)
    red = t4r["redondeo"]
    L += ["", "### Precisión de coordenadas del catálogo", "",
          "Fuente: `r2/coordenadas_redondeo.csv` (columnas `malla`, `parece_redondeada`, `incertidumbre_*_m`) y `r2/t4_resumen.json`.", "",
          "| Cifra | Valor | Campo |", "|---|---|---|"]
    L += [f"| Estaciones en la malla «{k}» | {n} | `t4_resumen.json:redondeo` |" for k, n in red.items()]
    rnd = pd.read_csv(r2 / "coordenadas_redondeo.csv")
    for name, g in rnd.dropna(subset=["incertidumbre_lat_m"]).groupby("malla"):
        L.append(f"| Incertidumbre (medio paso), malla «{name}»: latitud / longitud | {g['incertidumbre_lat_m'].median():.0f} m / "
                 f"{g['incertidumbre_lon_m'].median():.0f} m (mediana) | `coordenadas_redondeo.csv:incertidumbre_lat_m`, `incertidumbre_lon_m` |")
    L += [f"| Parecen redondeadas (minuto, 0.01° o 0.001°) | {t4r['parecen_redondeadas']} | `t4_resumen.json:parecen_redondeadas` |",
          f"| … de ellas, entre las {t4r['sin_tramo']} sin tramo | {t4r['redondeadas_sin_tramo']} | `t4_resumen.json:redondeadas_sin_tramo` |",
          f"| … de ellas, entre las {t4r['tramos_distintos']} con tramos distintos | {t4r['redondeadas_en_tramos_distintos']} | `t4_resumen.json:redondeadas_en_tramos_distintos` |", "",
          f"### Las {len(diff)} estaciones con `tramos_distintos`", "",
          "Fuente: `r2/hydrorivers_tramos_distintos.csv`. Razón = `upland_cercano_km2 / upland_km2`.", ""]
    d17 = diff[["clave", "unidad", "dist_m", "upland_km2", "dist_cercano_m", "upland_cercano_km2",
                "razon_area_cercano_mayor", "difiere_mas_de_factor_2"]].copy()
    d17["razon_area_cercano_mayor"] = d17["razon_area_cercano_mayor"].map(lambda x: f"{x:.3f}")
    L += table(d17, 1)
    L += ["", f"Difieren por más de un factor 2 en área: {t4r['difieren_mas_de_factor_2']} (`t4_resumen.json:difieren_mas_de_factor_2`).", "",
          f"### Las {len(none)} estaciones sin tramo a ≤ 0.01°", "",
          "Fuente: `r2/hydrorivers_sin_vinculo.csv`; distancia al tramo más cercano con el shapefile local de "
          "HydroRIVERS v1.0 NA en EPSG:6372.", ""]
    n8 = none.copy()
    if "hyriv_id_mas_cercano" in n8:
        n8["hyriv_id_mas_cercano"] = n8["hyriv_id_mas_cercano"].map(lambda x: str(int(x)) if pd.notna(x) else "—")
    L += table(n8, 1)
    L += ["", "### Sensibilidad al radio", ""]
    if sens_p.exists():
        L += [f"Shapefile leído en {t4r['segundos_lectura']:.0f} s (límite 300 s). El radio 0.01° reproduce el vínculo "
              f"publicado: {fmt(t4r['radio_0_01_reproduce_vinculo_publicado'])} (`t4_resumen.json`). Fuente: "
              "`r2/hydrorivers_sensibilidad_radio.csv`; cambios frente a 0.01°. *otro_tramo_asignado* = el tramo de "
              "mayor área dentro del radio es otro; *razon_area_otro_tramo_mediana* = área del nuevo / área del de 0.01°.", ""]
        sens = pd.read_csv(sens_p)
        sens["radio_grados"] = sens["radio_grados"].map(lambda x: f"{x:g}°")
        L += table(sens, 2)
    else:
        L += [f"Omitida: {t4r.get('sensibilidad_omitida', 'sin shapefile local')}."]

    # ---- T5
    L += ["", "## T5 · R2-v, Q6 y Q7, reproducibilidad", ""]
    if rep:
        L += [f"Copia limpia de `{rep['zip']}` (venv nuevo, Python {rep['python_entorno']}); fuente: `r2/reproducibilidad.json` "
              "y `r2/clean_copy_check_r2.json`."
              + (" `dib_16` creó la copia y su entorno; después `dib_09`, `dib_15` y la versión final de `dib_17` se "
                 "corrieron otra vez dentro de esa misma copia (`reproducibilidad.json:copia_reusada`)."
                 if rep.get("copia_reusada") else ""), "",
              "| Cifra | Esperado | Obtenido | Coincide | Archivo |", "|---|---|---|---|---|"]
        L += [f"| {i['cifra']} | {fmt(i['esperado'])} | {fmt(i['obtenido'])} | {fmt(i['coincide'])} | `{i['archivo']}` |" for i in rep["cifras"]]
        d16 = rep["dib_16"]
        L += ["", f"`dib_16`: valores idénticos = {fmt(d16['valores_identicos'])}; figuras idénticas por píxel = "
              f"{d16['figuras_identicas']} (`clean_copy_check_r2.json`). Una figura con píxeles distintos y valores idénticos "
              "refleja versiones distintas de las bibliotecas de dibujo, no un cambio del dato.", "",
              "Salidas regeneradas en la copia limpia frente al repositorio (CSV por valor con rtol 1e-12; JSON sin fechas "
              "de ejecución):", "", "| Archivo | Coincide | Detalle |", "|---|---|---|"]
        L += [f"| `{c['archivo']}` | {fmt(c['coincide'])} | {c['detalle']} |" for c in rep["salidas_r2"]]
    else:
        L += ["Pendiente."]
    locks = [n for n in LOCKS if (ROOT / n).exists()]
    sec = rep["segundos_por_script"] if rep else {}
    L += ["", "### Cómo reproducir", "",
          "Desde la raíz del archivo de Zenodo v2026.10 descomprimido (o de un clon del tag `v2026.10`), con el entorno "
          "activado (`venv\\Scripts\\activate` en Windows, `source venv/bin/activate` en Linux y macOS). "
          "`dib_17_r2_checks.py` es nuevo y no viene en v2026.10: se copia a `scripts/`. T1–T3 no necesitan nada más; "
          "T4 usa el shapefile de HydroRIVERS v1.0 para Norteamérica (`HydroRIVERS_v10_na.shp`, de HydroSHEDS), el mismo "
          "que usa `06_link_hydrorivers.py`.", "",
          "```bash", "python -m venv venv", "pip install -e \".[dev,geo]\"",
          "python scripts/dib_09_baseline.py            # NSE 0.528/0.594, KGE 0.764/0.642, 75 de 97",
          "python scripts/dib_13_paso2_tables.py        # Tabla 3",
          "python scripts/09_make_report_figures.py     # Fig. 2–7 y sus datos fuente",
          "python scripts/12_make_workflow_figure.py    # Fig. 1",
          "python scripts/dib_15_submission_figures.py  # figuras de envío",
          "python scripts/dib_17_r2_checks.py --tareas t1,t2,t3,t4 --hydrorivers <HydroRIVERS_v10_na.shp>  # T1–T4",
          "```", "",
          "| Cifra | Comando | Archivo de salida |", "|---|---|---|",
          "| NSE y KGE (mediana e IQR) | `dib_09_baseline.py` | `results/dib_revision/baseline_summary.csv` |",
          "| 75 de 97, 4 excluidas | `dib_09_baseline.py` | `results/dib_revision/e9_baseline.json` |",
          "| Tabla 3 | `dib_13_paso2_tables.py` | `results/dib_revision/tabla3_v2026_10.csv` |",
          "| Datos fuente de Fig. 2–7 | `09_make_report_figures.py` | `processed/reportes/metrics.json`, `cobertura_por_estacion.csv`, `precip_streamflow_lagcorr.csv` |",
          "| Figuras de envío | `dib_15_submission_figures.py` | `results/dib_revision/figuras_envio.csv` |",
          "| T1–T4 | `dib_17_r2_checks.py` | `results/dib_revision/r2/*.csv`, `*.json` |", "",
          f"- Python: {rep['python_entorno'] if rep else '—'} en la copia limpia (`clean_copy_check_r2.json:python_entorno`).",
          "- Dependencias: " + (f"archivo con versiones fijas: {', '.join(locks)}." if locks else
                                "no hay archivo con versiones fijas (lock o requirements). `pyproject.toml` declara versiones "
                                "mínimas; las versiones instaladas en la copia limpia están en "
                                "`clean_copy_check_r2.json:versiones.entorno_nuevo`. `dvc.lock` fija las etapas del pipeline, "
                                "no las bibliotecas."),
          (f"- Tiempo: {rep['dib_16']['minutos_total']} min la copia limpia completa con `dib_16` "
           f"({rep['dib_16']['minutos_pip_install']} min de instalación); en la copia, `dib_09` {fmt(sec.get('dib_09'), 0)} s, "
           f"`dib_15` {fmt(sec.get('dib_15'), 0)} s y `dib_17` (T1–T4) "
           f"{fmt(sum(v for k, v in sec.items() if k.startswith('dib_17') and isinstance(v, (int, float))), 0)} s "
           "(`reproducibilidad.json:segundos_por_script`).") if rep else "- Tiempo: pendiente.", ""]

    # ---- hallazgos y T6
    hp = r2 / "hallazgos_colaterales.md"
    titles = [re.sub(r"^\d+\.\s*", "", ln[3:].strip()) for ln in hp.read_text(encoding="utf-8").splitlines()
              if ln.startswith("## ")] if hp.exists() else []
    L += ["## Hallazgos colaterales registrados (solo títulos)", "",
          "Detalle en `r2/hallazgos_colaterales.md` (local, no se sube).", ""]
    L += [f"- {t}" for t in titles] or ["- Ninguno."]
    L += ["", "## T6 · versión del depósito", "",
          "Hace falta solo si alguna cifra nueva de T1–T4 entra al texto del manuscrito (por ejemplo, la tabla por unidad "
          "de T3 o las fracciones de T1). Si entra: commit de `scripts/dib_17_r2_checks.py`, `results/dib_revision/r2/` "
          "(sin `hallazgos_colaterales.md`) y E14 del ledger; push y tag `v2026.11`, cada paso con confirmación; después, "
          "nueva versión en Zenodo. El DOI concepto 10.5281/zenodo.21231600 no cambia.", "",
          "Estado: **pendiente de tu decisión**; no se ha hecho ningún commit, push ni tag.", ""]
    (r2 / "R2_report.md").write_text("\n".join(L), encoding="utf-8")
    log.info("R2_report.md escrito")


def secs(x) -> str:
    if not isinstance(x, (int, float)):
        return "—"
    return f"{x / 60:.1f} min" if x >= 90 else f"{x:.0f} s"


def write_reproduce(r2: Path, version: str) -> None:
    """REPRODUCE.md (inglés) en la raíz: elemento del artículo, comando, salida y tiempo en la copia limpia.
    Tiempos y versiones de r2/reproducibilidad.json y r2/clean_copy_check_r2.json."""
    rep = json.loads((r2 / "reproducibilidad.json").read_text(encoding="utf-8"))
    clean = json.loads((r2 / "clean_copy_check_r2.json").read_text(encoding="utf-8"))
    sec = rep["segundos_por_script"]

    def cmd_time(snippet: str):
        return next((c.get("segundos") for c in clean["comandos"] if snippet in c["comando"]), None)

    t = {"09": cmd_time("09_make_report_figures"), "12": cmd_time("12_make_workflow_figure"),
         "dib_01": cmd_time("dib_01_reconcile_counts"), "dib_13": cmd_time("dib_13_paso2_tables"),
         "pip": cmd_time("pip install -q -e"), "pytest": cmd_time("pytest")}
    t.update(sec)
    pix = [c["archivo"].rsplit("/", 1)[-1] for c in clean["comparaciones"]
           if c["archivo"].endswith(".png") and c["resultado"] != "igual"]
    dr = "results/dib_revision"
    rows = [
        ("Table 1 (directory structure; station and record counts)",
         "`python scripts/dib_01_reconcile_counts.py --suffix _v2026_10`",
         f"`{dr}/counts_reconciliation_v2026_10.csv`, `{dr}/observation_counts_v2026_10.csv`", t["dib_01"]),
        ("Table 2 (columns, data types and units; feature-table definition)",
         "`python scripts/dib_13_paso2_tables.py`", f"`{dr}/e13_paso2_t1.json`", t["dib_13"]),
        ("Table 3 (stations per pilot basin)", "`python scripts/dib_13_paso2_tables.py`",
         f"`{dr}/tabla3_v2026_10.csv`", t["dib_13"]),
        ("Table 4 (missing data and coverage per operational unit)",
         "`python scripts/dib_17_r2_checks.py --tareas t3`", f"`{dr}/r2/cobertura_por_unidad.csv`", t.get("dib_17_t3")),
        ("Fig. 1", "`python scripts/12_make_workflow_figure.py`", "`processed/reportes/Fig1_workflow.{png,tif}`", t["12"]),
        ("Figs. 2–7 and their source data", "`python scripts/09_make_report_figures.py`",
         "`processed/reportes/Fig2…Fig7.{png,tif}`, `metrics.json`, `cobertura_por_estacion.csv`, "
         "`precip_streamflow_lagcorr.csv`", t["09"]),
        ("Fig. S1 (imputation error vs gap length)", "`python scripts/dib_03_imputation_masking.py`",
         f"`{dr}/figs/figS_imputation_error_vs_L.{{png,tif}}`, `{dr}/imputation_masking_summary.csv`, "
         f"`{dr}/e3_imputation.json`", t.get("dib_03")),
        ("Fig. S2 (flagged outliers)", "`python scripts/dib_04_outliers.py`",
         f"`{dr}/figs/figS_outliers_examples.{{png,tif}}`, `{dr}/outliers_hidro.csv`, `{dr}/e4_outliers.json`",
         t.get("dib_04")),
        ("Submission files Figure_1–7, S1–S2 (TIFF)", "`python scripts/dib_15_submission_figures.py`",
         f"`dist/figuras_envio/`, `{dr}/figuras_envio.csv`", t.get("dib_15")),
        ("Baseline metrics: median NSE 0.528 (persistence) and 0.594 (ridge), median KGE 0.764 and 0.642, "
         "ridge better than persistence at 75 of 97 stations", "`python scripts/dib_09_baseline.py`",
         f"`{dr}/baseline_summary.csv` (`NSE_mediana`, `KGE_mediana`), `{dr}/e9_baseline.json`", t.get("dib_09")),
        ("Baseline without imputed values in the predictor window; skill against persistence",
         "`python scripts/dib_17_r2_checks.py --tareas t1`",
         f"`{dr}/r2/baseline_sin_imputados_summary.csv`, `{dr}/r2/fraccion_imputados_test.json`, "
         f"`{dr}/r2/skill_vs_persistencia.csv`, `{dr}/r2/t1_resumen.json`", t.get("dib_17_t1")),
        ("End of the record within the test period", "`python scripts/dib_17_r2_checks.py --tareas t2`",
         f"`{dr}/r2/fin_registro_test.json`", t.get("dib_17_t2")),
        ("Station–reach distances, coordinate precision, differing reaches, unlinked stations and "
         "sensitivity to the search radius",
         "`python scripts/dib_17_r2_checks.py --tareas t4 --hydrorivers <path>/HydroRIVERS_v10_na.shp`",
         f"`{dr}/r2/hydrorivers_distancias.csv`, `coordenadas_redondeo.csv`, `hydrorivers_tramos_distintos.csv`, "
         "`hydrorivers_sin_vinculo.csv`, `hydrorivers_sensibilidad_radio.csv`, `t4_resumen.json` (all in "
         f"`{dr}/r2/`)", t.get("dib_17_t4")),
    ]
    vers = clean["versiones"]["entorno_nuevo"]
    L = [f"# Reproducing the article from the {version} archive", "",
         "This file maps every table, figure and number of the *Data in Brief* article to the command that "
         "produces it and the file where it is written. It applies to the Zenodo archive "
         f"`HidroXAI-MX-{version}.zip` (concept DOI [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600)) "
         f"and to a clone of the repository at tag `{version}` (the data are then fetched with `dvc pull`).", "",
         "## Setup", "",
         "Run every command from the root of the unzipped archive (or of the repository clone; the package "
         "finds `raw/`, `processed/` and `features/` at the archive root, or `data/` in the repository).", "",
         "```bash", f"unzip HidroXAI-MX-{version}.zip -d hidromx && cd hidromx", "python -m venv venv",
         "# activate it: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Linux, macOS)",
         "pip install -e \".[dev,geo]\"", "```", "",
         "Fig. 2 needs three boundary layers that are not redistributed; download the layers listed in "
         "`conf/sources.yaml` (section 10) into `scratch/limites/` (`ne_10m_admin_1/`, `rh250kgw/`, `cue250kgw/`).", "",
         "## Commands", "",
         "```bash",
         "python scripts/dib_01_reconcile_counts.py --suffix _v2026_10  # Table 1",
         "python scripts/dib_13_paso2_tables.py        # Tables 2 and 3",
         "python scripts/12_make_workflow_figure.py    # Fig. 1",
         "python scripts/09_make_report_figures.py     # Figs. 2–7 and their source data",
         "python scripts/dib_03_imputation_masking.py  # Fig. S1",
         "python scripts/dib_04_outliers.py            # Fig. S2",
         "python scripts/dib_15_submission_figures.py  # submission TIFF files",
         "python scripts/dib_09_baseline.py            # baseline metrics",
         "python scripts/dib_17_r2_checks.py --tareas t1,t2,t3,t4 --hydrorivers <path>/HydroRIVERS_v10_na.shp",
         "```", "",
         "**HydroRIVERS.** The `t4` task needs `HydroRIVERS_v10_na.shp` (HydroRIVERS v1.0, North America; "
         "HydroSHEDS, https://www.hydrosheds.org; Lehner & Grill, 2013, https://doi.org/10.1002/hyp.9740). It is not "
         "included in the archive. Without `--hydrorivers`, `t4` still writes the distances, coordinate precision and "
         "differing reaches from `processed/estaciones_hidrorivers.csv`, but not the distance to the nearest reach "
         "of the unlinked stations or the radius sensitivity. Tasks `t1`–`t3` need nothing else.", "",
         "## Article element, command, output and time", "",
         f"Times were measured on a clean copy of the previous archive, `{rep['zip']}`, whose data are identical "
         f"to {version}, with `scripts/dib_17_r2_checks.py` added: the archive unzipped into an empty folder, a new "
         f"virtual environment, Python {clean['python_entorno']}, {clean['sistema']}.", "",
         "| Article element | Command | Output file | Time in the clean copy |", "|---|---|---|---|"]
    L += [f"| {a} | {c} | {o} | {secs(s)} |" for a, c, o, s in rows]
    L += ["", f"Installing the package took {secs(t['pip'])} and the test suite {secs(t['pytest'])}. "
          f"The whole clean-copy check, including installation and the download of the boundary layers, took "
          f"{clean['minutos_total']} min.", "",
          "## Automated check", "",
          "`scripts/dib_16_clean_copy_check.py` unzips an archive into a new folder, creates a new environment, "
          "installs the package, regenerates the products and figures and compares them with the packaged ones "
          "(JSON and CSV by value, figures by pixel). `scripts/dib_17_r2_checks.py --tareas copia` runs it and then "
          "repeats the baseline and the checks above inside the same copy:", "",
          "```bash",
          f"python scripts/dib_17_r2_checks.py --tareas copia --zip HidroXAI-MX-{version}.zip --work <new folder> "
          "--hydrorivers <path>/HydroRIVERS_v10_na.shp", "```", "",
          "In our check every number of the article was reproduced exactly (CSV compared with a relative "
          "tolerance of 1e-12, JSON by value). "
          + (f"Figure files may differ at pixel level with other plotting-library versions while their data are "
             f"identical ({', '.join(pix)} in our check)." if pix else "Figures were identical pixel by pixel.")]
    other = [c for c in rep["salidas_r2"] if not c["coincide"]]
    e3 = next((c for c in rep.get("figuras_suplementarias_fuera_de_E14", []) if c["archivo"] == "e3_imputation.json"), None)
    if any(c["archivo"] == "r2/t1_resumen.json" and "control.max_diferencia" in c["detalle"] for c in other):
        ctrl = json.loads((r2 / "t1_resumen.json").read_text(encoding="utf-8"))["control"]["max_diferencia"]
        L += ["", "`control.max_diferencia` in `r2/t1_resumen.json` records the floating-point difference with which "
              "each environment recomputes its own `baseline_por_estacion.csv`; it differs between environments "
              f"({ctrl:.1e} in the repository) and is the only value of the checks that does."]
    if e3 and not e3["coincide"]:
        L += ["", "The block `diagnostico_dato_publicado` of `results/dib_revision/e3_imputation.json` describes the "
              "imputed values of the data present when `dib_03_imputation_masking.py` runs. The packaged file was "
              "computed on the v2026.06 data (cubic spline), so the regenerated block describes the current data "
              "instead. Fig. S1 and its source tables (`imputation_masking_summary.csv`, `imputation_masking_gaps.csv`) "
              "are reproduced exactly."]
    L += ["", "## Environment", "",
          f"- Python {clean['python_entorno']}.",
          "- `pyproject.toml` sets only minimum versions of the dependencies; there is no lock file. The versions "
          "installed in the clean copy were:", "",
          "| Package | Version |", "|---|---|"]
    L += [f"| {p} | {v} |" for p, v in vers.items()]
    L += [""]
    (ROOT / "REPRODUCE.md").write_text("\n".join(L), encoding="utf-8")
    log.info("REPRODUCE.md escrito")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tareas", default="t1,t2,t3,t4")
    ap.add_argument("--hydrorivers", type=Path)
    ap.add_argument("--zip", type=Path)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--reusar-copia", action="store_true",
                    help="Con --tareas copia: usar la copia de --work ya instalada por dib_16.")
    ap.add_argument("--version", default="v2026.11", help="Con --tareas reproduce: versión del archivo.")
    a = ap.parse_args()
    R2.mkdir(parents=True, exist_ok=True)
    tasks = [t.strip() for t in a.tareas.split(",")]
    if "t1" in tasks:
        t1()
    if "t2" in tasks:
        t2()
    if "t3" in tasks:
        t3()
    if "t4" in tasks:
        t4(a.hydrorivers)
    if "copia" in tasks:
        if not (a.zip and a.work):
            raise SystemExit("copia requiere --zip y --work")
        copia(a.zip.resolve(), a.work.resolve(), a.hydrorivers.resolve() if a.hydrorivers else None, a.reusar_copia)
    if "reporte" in tasks:
        write_report(R2)
    if "reproduce" in tasks:
        write_reproduce(R2, a.version)


if __name__ == "__main__":
    main()

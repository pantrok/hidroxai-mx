#!/usr/bin/env python
"""Benchmark XAI · paso 11: diagnósticos post hoc D1 (¿fue 2023 un año seco?) y D2 (¿por qué α, β < 1?).

Criterios y detalles escritos antes de calcular en proof_ledger.md ("Diagnósticos post hoc",
2026-10-11). Son descriptivos (no preregistrados, post hoc): no cambian veredictos ni métricas
del diseño principal y no reentrenan ninguno de sus modelos.

- D1: anomalía de precipitación (`precip_idw_mm`) y razón de gasto (`calidad = 0`) por estación,
  año 2021–2025 y cuenca piloto frente a 2010–2020; contraste con el walk-forward y con el β de
  la climatología.
- D2-a: corrección por smearing de Duan con residuales de validación (modelos aprendidos, media
  de semillas, y ARIMA).
- D2-b: XGBoost con objetivo en m³/s estandarizado (sin log1p), misma configuración y semillas.

Salidas: results/xai_benchmark/diag_sequia_2023.csv, diag_sequia_2023_estaciones.csv,
         diag_kge_log1p.csv, diag_kge_log1p_estaciones.csv, e_diagnosticos.json
Uso:  python scripts/xai_11_diagnostics.py [--skip-xgb-raw]
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.models import manifest
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_11")
OUT = ROOT / "results" / "xai_benchmark"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
INFERENCE = ("Lerma–Santiago", "Pánuco", "Alta del Balsas")
YEARS, REF = (2021, 2022, 2023, 2024, 2025), range(2010, 2021)
LAST_DAY_2025 = "09-03"
COV_P, COV_Q, MIN_REF_YEARS = 0.90, 0.70, 5
SEEDS = (20261010, 20261011, 20261012)
LEARNED = ("xgboost", "tcn", "convnext", "patchtst")
TAG = "descriptivo (no preregistrado, post hoc)"


def _r(x, n: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), n)


# ----------------------------------------------------------------------------- D1
def _period(year: int, end_md: str) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-01-01", f"{year}-{end_md}", freq="D")


def _station_year(series: pd.Series, year: int, end_md: str, cov: float, how: str) -> float:
    days = _period(year, end_md)
    v = series.reindex(days)
    if v.notna().mean() < cov:
        return np.nan
    return float(v.sum()) if how == "sum" else float(v.mean())


def drought_2023(ft: pd.DataFrame, basin_of: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    rows = []
    for k, g in ft.groupby("clave_estacion"):
        g = g.set_index("fecha").sort_index()
        p = g["precip_idw_mm"]
        q = g["gasto_medio_m3s"].where(g["calidad"] == 0)
        for y in YEARS:
            end = LAST_DAY_2025 if y == 2025 else "12-31"
            ref_p = [v for r in REF if np.isfinite(v := _station_year(p, r, end, COV_P, "sum"))]
            ref_q = [v for r in REF if np.isfinite(v := _station_year(q, r, end, COV_Q, "mean"))]
            tot = _station_year(p, y, end, COV_P, "sum")
            mean_q = _station_year(q, y, end, COV_Q, "mean")
            med_p = np.median(ref_p) if len(ref_p) >= MIN_REF_YEARS else np.nan
            mu_q = np.mean(ref_q) if len(ref_q) >= MIN_REF_YEARS else np.nan
            rows.append({"clave": k, "cuenca": basin_of[k], "año": y,
                         "anomalia_precip": tot / med_p - 1 if med_p and np.isfinite(med_p) and med_p > 0 else np.nan,
                         "razon_gasto": mean_q / mu_q if np.isfinite(mu_q) and mu_q > 0 else np.nan})
    st = pd.DataFrame(rows)
    agg = (st.groupby(["cuenca", "año"])
           .agg(anomalia_precip_mediana=("anomalia_precip", "median"),
                estaciones_precip=("anomalia_precip", "count"),
                razon_gasto_mediana=("razon_gasto", "median"),
                estaciones_gasto=("razon_gasto", "count")).reset_index())
    per_basin = {}
    for b in D.BASINS:
        x = agg[agg["cuenca"] == b].set_index("año")
        min_year = int(x["razon_gasto_mediana"].idxmin()) if x["razon_gasto_mediana"].notna().any() else None
        per_basin[b] = {"año_menor_razon_gasto": min_year,
                        "anomalia_precip_2023": _r(x.loc[2023, "anomalia_precip_mediana"]),
                        "razon_gasto_2023": _r(x.loc[2023, "razon_gasto_mediana"]),
                        "cumple": bool(min_year == 2023 and x.loc[2023, "anomalia_precip_mediana"] < 0),
                        "con_inferencia": b in INFERENCE}
    n_ok = sum(per_basin[b]["cumple"] for b in INFERENCE)
    n_min = sum(per_basin[b]["año_menor_razon_gasto"] == 2023 for b in INFERENCE)
    verdict = "SUPPORTED" if n_ok >= 2 else ("REJECTED" if n_min == 0 else "OPEN")
    return {"por_cuenca": per_basin, "cuencas_que_cumplen": n_ok, "cuencas_2023_menor_gasto": n_min,
            "veredicto": verdict}, agg, st


def climatology_beta_by_year(wf: Path) -> dict:
    out = {}
    for y in YEARS:
        betas = []
        for b in D.BASINS:
            tag = f"{SLUG[b]}_h1_y{y}"
            meta = pd.read_parquet(wf / "meta" / f"{tag}_test.parquet")
            clim = np.load(wf / "preds" / f"baselines_{tag}.npz")["climatology_test"]
            g = meta.groupby("clave")["y_flow"]
            ok = (g.size() >= 180) & (g.var() > 0)
            for k, idx in meta.groupby("clave").indices.items():
                if ok.get(k, False):
                    betas.append(M.kge_components(meta["y_flow"].to_numpy()[idx], clim[idx])[2])
        out[str(y)] = _r(np.nanmedian(betas))
    return out


# ----------------------------------------------------------------------------- D2
def _metrics(o: np.ndarray, s: np.ndarray) -> dict:
    r, a, b = M.kge_components(o, s)
    return {"r": r, "alpha": a, "beta": b, "nse": M.nse(o, s), "kge": M.kge(o, s)}


def smearing(cpu: Path, nets: Path, chosen: dict, evaluable: dict) -> tuple[pd.DataFrame, dict]:
    rows, no_val = [], {}
    for b in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[b]}_h{h}"
            meta = {p: pd.read_parquet(cpu / "meta" / f"{tag}_{p}.parquet") for p in ("val", "test")}
            base = np.load(cpu / "preds" / f"baselines_{tag}.npz")
            pred = {"arima": {p: base[f"arima_{p}"] for p in ("val", "test")}}
            for m in LEARNED:
                src = cpu if m == "xgboost" else nets
                arr = [np.load(src / "preds" / f"{chosen[f'{m}_h{h}']}_{tag}_s{s}.npz") for s in SEEDS]
                pred[m] = {p: np.stack([x[f"flow_{p}"] for x in arr]).mean(0) for p in ("val", "test")}
            val_idx = meta["val"].groupby("clave").indices
            for k, idx in meta["test"].groupby("clave").indices.items():
                if k not in evaluable[h]:
                    continue
                o = meta["test"]["y_flow"].to_numpy()[idx]
                for m, pp in pred.items():
                    if k in val_idx:
                        vi = val_idx[k]
                        ratio = (1 + meta["val"]["y_flow"].to_numpy()[vi]) / (1 + pp["val"][vi])
                        f = float(np.nanmean(ratio))
                    else:
                        f = 1.0
                        no_val[(m, h)] = no_val.get((m, h), 0) + 1
                    s = pp["test"][idx]
                    rows.append({"cuenca": b, "h": h, "clave": k, "modelo": m, "factor_smearing": f,
                                 **{f"{key}_original": v for key, v in _metrics(o, s).items()},
                                 **{f"{key}_smearing": v for key, v in _metrics(o, (1 + s) * f - 1).items()}})
    return pd.DataFrame(rows), {f"{m}_h{h}": n for (m, h), n in no_val.items()}


def _z_raw(meta: pd.DataFrame, stats: pd.DataFrame) -> np.ndarray:
    """Gasto en m³/s estandarizado por estación (media y desviación de entrenamiento), sin log1p."""
    return ((meta["y_flow"] - stats.loc[meta["clave"], "mean"].to_numpy())
            / stats.loc[meta["clave"], "std"].to_numpy()).to_numpy(dtype=np.float32)


def xgb_raw(panels: dict, basin_of: dict, chosen: dict, evaluable: dict, threads: int) -> tuple[pd.DataFrame, float]:
    from hidroxai_mx.models import xgb as XG
    rows, t0 = [], time.perf_counter()
    for b in D.BASINS:
        bp = {k: p for k, p in panels.items() if basin_of[k] == b}
        for h in D.HORIZONS:
            g = D.group_arrays(bp, h)
            stats = g["train"]["meta"].groupby("clave")["y_flow"].agg(["mean", "std"])
            stats["std"] = stats["std"].where(stats["std"] > 1e-8, 1.0)
            ztr, zva = _z_raw(g["train"]["meta"], stats), _z_raw(g["val"]["meta"], stats)
            depth = int(chosen[f"xgboost_h{h}"].split("-")[1])
            mt = g["test"]["meta"]
            preds = []
            for seed in SEEDS:
                booster = XG.fit(g["train"]["X"], ztr, g["val"]["X"], zva, max_depth=depth, seed=seed,
                                 n_jobs=threads)
                zt = XG.predict(booster, g["test"]["X"])
                preds.append(zt * stats.loc[mt["clave"], "std"].to_numpy() + stats.loc[mt["clave"], "mean"].to_numpy())
            flow = np.clip(np.mean(preds, axis=0), 0, None)
            for k, idx in mt.groupby("clave").indices.items():
                if k in evaluable[h]:
                    rows.append({"cuenca": b, "h": h, "clave": k, "modelo": "xgboost_espacio_original",
                                 **_metrics(mt["y_flow"].to_numpy()[idx], flow[idx])})
            log.info("XGBoost sin log1p %s h=%d listo", b, h)
    return pd.DataFrame(rows), time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=INTERIM / "cpu")
    ap.add_argument("--nets", type=Path, default=INTERIM / "nets")
    ap.add_argument("--wf", type=Path, default=INTERIM / "walk_forward")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--skip-xgb-raw", action="store_true")
    a = ap.parse_args()
    t0 = time.perf_counter()
    e1 = json.loads((OUT / "e_rq1.json").read_text(encoding="utf-8"))
    chosen = e1["configuracion_elegida"]
    st_main = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    evaluable = {h: set(st_main.loc[(st_main["h"] == h) & (st_main["modelo"] == "persistencia"), "clave"])
                 for h in D.HORIZONS}

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    ft["fecha"] = pd.to_datetime(ft["fecha"])

    # ---- D1
    d1, agg, st1 = drought_2023(ft, basin_of)
    agg.round(4).to_csv(OUT / "diag_sequia_2023.csv", index=False)
    st1.round(4).to_csv(OUT / "diag_sequia_2023_estaciones.csv", index=False)
    wfs = pd.read_csv(OUT / "wf_summary.csv")
    wa = wfs[(wfs["grupo"] == "agregado") & (wfs["h"] == 1)]
    clim_main = st_main[(st_main["modelo"] == "climatologia")].groupby("h")["kge_beta"].median()
    d1.update({
        "fuente": "scripts/xai_11_diagnostics.py; results/xai_benchmark/diag_sequia_2023*.csv",
        "datos": {"precipitacion": "precip_idw_mm de las 95 estaciones hidrométricas modeladas",
                  "gasto": "gasto_medio_m3s con calidad = 0", "referencia": "2010–2020, mismo periodo calendario",
                  "periodo_2025": f"01-01 a {LAST_DAY_2025}"},
        "contraste": {"nse_mediana_walk_forward_h1": {m: {str(r.año): _r(r.nse_mediana) for r in wa[wa["modelo"] == m].itertuples()}
                                                      for m in ("persistencia", "arima", *LEARNED)},
                      "beta_climatologia_prueba_principal": {f"h{h}": _r(v) for h, v in clim_main.items()},
                      "beta_climatologia_walk_forward_h1": climatology_beta_by_year(a.wf)},
        "no_realizado": "cruce con el Monitor de Sequía municipal (requiere descargar el archivo oficial)"})
    log.info("D1 %s", d1["veredicto"])

    # ---- D2-a
    sm, no_val = smearing(a.cpu, a.nets, chosen, evaluable)
    chk = sm.merge(st_main[["h", "clave", "modelo", "nse"]], on=["h", "clave", "modelo"])
    assert len(chk) == len(sm) and np.allclose(chk["nse_original"], chk["nse"], equal_nan=True), \
        "las métricas originales no reproducen rq1_station_metrics.csv"
    keys = ("beta", "alpha", "r", "nse", "kge")
    med = {f"{m}_h{h}": {f"{k}_{v}": _r(x[f"{k}_{v}"].median()) for k in keys for v in ("original", "smearing")}
           | {"factor_mediano": _r(x["factor_smearing"].median()), "estaciones": int(x["clave"].nunique())}
           for (m, h), x in sm.groupby(["modelo", "h"])}
    closer = {m: (abs(med[f"{m}_h1"]["beta_original"] - 1) - abs(med[f"{m}_h1"]["beta_smearing"] - 1)) for m in LEARNED}
    dbeta = {m: med[f"{m}_h1"]["beta_smearing"] - med[f"{m}_h1"]["beta_original"] for m in LEARNED}
    va = ("SUPPORTED" if sum(c >= 0.03 for c in closer.values()) >= 3 else
          "REJECTED" if all(abs(d) < 0.01 for d in dbeta.values()) else "OPEN")
    d2 = {"fuente": "scripts/xai_11_diagnostics.py; results/xai_benchmark/diag_kge_log1p*.csv",
          "a_smearing": {"medianas": med, "acercamiento_beta_a_1_h1": {m: _r(v) for m, v in closer.items()},
                         "delta_beta_h1": {m: _r(v) for m, v in dbeta.items()},
                         "estaciones_sin_validacion_f1": no_val, "veredicto": va,
                         "comprobacion": "las métricas originales reproducen rq1_station_metrics.csv"}}
    log.info("D2-a %s", va)

    # ---- D2-b
    frames = [sm]
    if not a.skip_xgb_raw:
        panels = {k: D.daily_panel(ft, k) for k in claves}
        raw, sec = xgb_raw(panels, basin_of, chosen, evaluable, a.threads)
        frames.append(raw)
        mraw = {f"h{h}": {k: _r(x[k].median()) for k in keys} | {"estaciones": int(x["clave"].nunique())}
                for h, x in raw.groupby("h")}
        alpha1 = mraw["h1"]["alpha"]
        vb = "SUPPORTED" if alpha1 < 0.9 else ("REJECTED" if alpha1 >= 0.95 else "OPEN")
        d2["b_xgboost_espacio_original"] = {
            "medianas": mraw,
            "xgboost_log1p": {f"h{h}": {k: med[f"xgboost_h{h}"][f"{k}_original"] for k in keys} for h in D.HORIZONS},
            "veredicto": vb, "horas_cpu": round(sec / 3600, 3),
            "nota": "horas incluidas en la fila xai_11_diagnostics del manifiesto"}
        log.info("D2-b %s (α mediana h=1: %.3f)", vb, alpha1)
    pd.concat(frames, ignore_index=True).round(6).to_csv(OUT / "diag_kge_log1p_estaciones.csv", index=False)
    long = []
    for (m, h), x in pd.concat(frames, ignore_index=True).groupby(["modelo", "h"]):
        variants = ("original", "smearing") if m != "xgboost_espacio_original" else ("",)
        for v in variants:
            sfx = f"_{v}" if v else ""
            long.append({"modelo": m, "h": h, "variante": v or "espacio_original",
                         **{k: _r(x[f"{k}{sfx}"].median()) for k in keys}, "estaciones": int(x["clave"].nunique())})
    pd.DataFrame(long).to_csv(OUT / "diag_kge_log1p.csv", index=False)

    res = {"fecha": date.today().isoformat(), "fuente": "scripts/xai_11_diagnostics.py", "tipo": TAG,
           "criterios": "proof_ledger.md, sección 'Diagnósticos post hoc' (2026-10-11, escritos antes de calcular)",
           "sequia_2023": d1, "kge_log1p": d2}
    (OUT / "e_diagnosticos.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    sec = round(time.perf_counter() - t0, 1)
    manifest.replace(OUT / "compute_manifest.csv", fecha=date.today().isoformat(), tipo="evaluacion",
                     run="xai_11_diagnostics", modelo="diagnosticos", dispositivo=platform.processor() or "cpu",
                     hilos=a.threads, segundos=sec, pared_s=sec)


if __name__ == "__main__":
    main()

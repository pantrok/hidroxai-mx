#!/usr/bin/env python
"""Benchmark XAI · MESE (M2): valores imputados en la ventana, solo evaluación.

Criterios en results/xai_benchmark/proof_ledger.md, "Enmienda MESE", M2 (versionados antes de
correr). Descriptivo: no reentrena nada ni cambia ningún veredicto.

Subconjuntos de la prueba principal:
  (i)  sin las emisiones con Q(t) imputado (calidad = 1 en el día de emisión);
  (ii) sin las emisiones con algún imputado en la ventana de 30 días (t−29…t).
Para cada uno, en las estaciones evaluables de la prueba principal que siguen siendo
evaluables en el subconjunto (≥ 180 muestras y varianza > 0):
  - fracción de emisiones excluidas (global y por horizonte);
  - mediana de NSE por modelo y horizonte, en el subconjunto y en la prueba completa de esas
    mismas estaciones;
  - ΔNSE (modelo profundo − XGBoost), mediana con IC por bootstrap de estaciones;
  - ΔCSI P90 (difuso − umbral) a h = 1 y 7, con tablas sumadas y bootstrap de estaciones (H3).
Controles previos: el NSE recalculado reproduce rq1_station_metrics.csv y el ΔCSI de la prueba
completa reproduce e_rq3.json.

Salidas: results/xai_benchmark/mese/imputados_test.csv, e_mese_imputados.json y
numbers.json → mese_imputados (correr después de xai_08, xai_12 y xai_14, que reescriben
numbers.json).
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

from hidroxai_mx.alert import evaluation as AE
from hidroxai_mx.models import data as D
from hidroxai_mx.models import metrics as M
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_16")
OUT = ROOT / "results" / "xai_benchmark"
MESE = OUT / "mese"
INTERIM = ROOT / "data" / "interim" / "xai_benchmark"
TAG = "descriptivo (post hoc, MESE M2)"
SEEDS = (20261010, 20261011, 20261012)
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
LEARNED, DEEP = ("xgboost", "tcn", "convnext", "patchtst"), ("tcn", "convnext", "patchtst")
MODELS = ("persistencia", "climatologia", "arima", *LEARNED)
SUBSETS = {"i_sin_qt_imputado": "q_t_imputado", "ii_sin_imputados_en_ventana": "imputado_en_ventana"}
MIN_N = 180
P90 = (0.90, 2)          # percentil del evento y nivel difuso mínimo (protocolo §6)


def _r(x, n: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def load_predictions(cpu: Path, nets: Path, chosen: dict, basin: str, h: int) -> tuple[pd.DataFrame, dict]:
    """Muestras de prueba y predicción evaluada (media de semillas) de los 7 modelos."""
    tag = f"{SLUG[basin]}_h{h}"
    meta = pd.read_parquet(cpu / "meta" / f"{tag}_test.parquet")
    base = np.load(cpu / "preds" / f"baselines_{tag}.npz")
    pred = {"persistencia": base["persistence_test"], "climatologia": base["climatology_test"],
            "arima": base["arima_test"]}
    for m in LEARNED:
        cfg = chosen[f"{m}_h{h}"]
        src = cpu if m == "xgboost" else nets
        stack = np.stack([np.load(src / "preds" / f"{cfg}_{tag}_s{s}.npz")["flow_test"] for s in SEEDS])
        pred[m] = stack.mean(0)
    return meta, pred


def imputed_flags(panel: pd.DataFrame, issues: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Q(t) imputado y algún imputado en t−29…t, para cada fecha de emisión."""
    imp = (panel["calidad"] == 1).astype(float)
    win = imp.rolling(D.WINDOW, min_periods=1).max()
    idx = pd.DatetimeIndex(issues)
    return imp.reindex(idx).to_numpy() == 1, win.reindex(idx).to_numpy() == 1


def train_p90(panel: pd.DataFrame) -> float:
    p = panel.loc[D.PARTITIONS["train"][0]:D.PARTITIONS["train"][1]]
    v = p.loc[p["calidad"] == 0, D.TARGET].to_numpy(dtype=float)
    return float(np.quantile(v[np.isfinite(v)], P90[0]))


def station_nse(meta: pd.DataFrame, pred: dict, keep: np.ndarray, stations: set) -> pd.DataFrame:
    obs = meta["y_flow"].to_numpy()
    rows = []
    for k, idx in meta.groupby("clave").indices.items():
        if k not in stations:
            continue
        idx = idx[keep[idx]]
        rows += [{"clave": k, "modelo": m, "nse": M.nse(obs[idx], pred[m][idx])} for m in MODELS]
    return pd.DataFrame(rows)


def contingency(alerts: pd.DataFrame, keep: np.ndarray, stations: set, thr: dict) -> pd.DataFrame:
    rows = []
    for k, idx in alerts.groupby("clave").indices.items():
        if k not in stations:
            continue
        idx = idx[keep[idx]]
        obs = alerts["observado"].to_numpy()[idx] > thr[k]
        for metodo, pred in (("difuso", alerts["nivel"].to_numpy()[idx] >= P90[1]),
                             ("umbral", alerts["percentil"].to_numpy()[idx] >= P90[0])):
            rows.append({"clave": k, "metodo": metodo, **AE.counts(obs, pred)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=INTERIM / "cpu")
    ap.add_argument("--nets", type=Path, default=INTERIM / "nets")
    a = ap.parse_args()
    t0 = time.perf_counter()
    MESE.mkdir(parents=True, exist_ok=True)
    e1 = json.loads((OUT / "e_rq1.json").read_text(encoding="utf-8"))
    e3 = json.loads((OUT / "e_rq3.json").read_text(encoding="utf-8"))
    chosen = e1["configuracion_elegida"]
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    evaluable = {h: set(st.loc[(st["h"] == h) & (st["modelo"] == "persistencia"), "clave"]) for h in D.HORIZONS}

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]],
                         filters=[("clave_estacion", "in", claves)])
    panels = {k: D.daily_panel(ft, k) for k in claves}
    del ft
    thr = {k: train_p90(p) for k, p in panels.items()}

    # ---- muestras, banderas y predicciones por horizonte (las 4 cuencas juntas)
    data = {}
    for h in D.HORIZONS:
        metas, preds, alerts = [], {m: [] for m in MODELS}, []
        for b in D.BASINS:
            meta, pred = load_predictions(a.cpu, a.nets, chosen, b, h)
            q_imp, w_imp = np.zeros(len(meta), bool), np.zeros(len(meta), bool)
            for k, idx in meta.groupby("clave").indices.items():
                q_imp[idx], w_imp[idx] = imputed_flags(panels[k], meta["issue"].iloc[idx])
            metas.append(meta.assign(q_t_imputado=q_imp, imputado_en_ventana=w_imp))
            for m in MODELS:
                preds[m].append(pred[m])
            al = pd.read_parquet(INTERIM / "alerts" / f"{SLUG[b]}_h{h}.parquet")
            assert len(al) == len(meta) and (al["clave"].to_numpy() == meta["clave"].to_numpy()).all() \
                and (al["issue"].to_numpy("datetime64[D]") == meta["issue"].to_numpy("datetime64[D]")).all(), \
                f"alertas y muestras distintas {b} h{h}"
            alerts.append(al.assign(q_t_imputado=q_imp, imputado_en_ventana=w_imp))
        meta = pd.concat(metas, ignore_index=True)
        data[h] = {"meta": meta, "pred": {m: np.concatenate(v) for m, v in preds.items()},
                   "alerts": pd.concat(alerts, ignore_index=True)}

    # ---- controles: la prueba completa reproduce rq1_station_metrics.csv y e_rq3.json
    worst = 0.0
    for h in D.HORIZONS:
        d = data[h]
        full = station_nse(d["meta"], d["pred"], np.ones(len(d["meta"]), bool), evaluable[h])
        ref = st[st["h"] == h].set_index(["clave", "modelo"])["nse"]
        mine = full.set_index(["clave", "modelo"])["nse"].reindex(ref.index)
        worst = max(worst, float(np.nanmax(np.abs(mine.to_numpy() - ref.to_numpy()))))
    if worst > 1e-9:
        raise SystemExit(f"El NSE recalculado no reproduce rq1_station_metrics.csv ({worst:.2e})")
    for h in (1, 7):
        d = data[h]
        tab = contingency(d["alerts"], np.ones(len(d["alerts"]), bool), evaluable[h], thr)
        ci = [_r(x) for x in AE.boot_delta_csi(tab)]
        if ci != [_r(x) for x in e3["H3"]["delta_csi_ic"][f"P90_h{h}"]]:
            raise SystemExit(f"El ΔCSI de la prueba completa no reproduce e_rq3.json (h = {h}): {ci}")
    log.info("controles superados (NSE máx. dif. %.1e; ΔCSI de e_rq3 reproducido)", worst)

    # ---- subconjuntos
    rows, res = [], {"fuente": "scripts/xai_16_mese_imputados.py", "tipo": TAG,
                     "control_nse_max_diferencia": worst, "subconjuntos": {}}
    for sname, flag in SUBSETS.items():
        out = {"fraccion_excluida": {}, "por_horizonte": {}}
        tot_n = tot_x = 0
        for h in D.HORIZONS:
            d = data[h]
            meta = d["meta"]
            ev = meta["clave"].isin(evaluable[h]).to_numpy()
            drop = meta[flag].to_numpy()
            n, x = int(ev.sum()), int((ev & drop).sum())
            tot_n, tot_x = tot_n + n, tot_x + x
            out["fraccion_excluida"][f"h{h}"] = {"emisiones": n, "excluidas": x, "fraccion": _r(x / n, 5)}
            rows.append({"subconjunto": sname, "h": h, "bloque": "fraccion_excluida", "modelo": None,
                         "estaciones": len(evaluable[h]), "valor_principal": n, "valor_subconjunto": n - x,
                         "diferencia": _r(x / n, 5)})
            keep = ~drop
            # estaciones que siguen siendo evaluables en el subconjunto
            y = meta["y_flow"].to_numpy()
            same = {k for k, idx in meta.groupby("clave").indices.items()
                    if k in evaluable[h] and keep[idx].sum() >= MIN_N and np.var(y[idx][keep[idx]]) > 0}
            full = station_nse(meta, d["pred"], np.ones(len(meta), bool), same).pivot(index="clave", columns="modelo", values="nse")
            sub = station_nse(meta, d["pred"], keep, same).pivot(index="clave", columns="modelo", values="nse")
            hres = {"estaciones_evaluables": len(evaluable[h]), "estaciones_mismas": len(same),
                    "estaciones_que_salen": sorted(evaluable[h] - same), "nse_mediana": {}, "delta_nse_vs_xgboost": {}}
            for m in MODELS:
                p, s = float(full[m].median()), float(sub[m].median())
                hres["nse_mediana"][m] = {"principal_mismas": _r(p), "subconjunto": _r(s), "diferencia": _r(s - p)}
                rows.append({"subconjunto": sname, "h": h, "bloque": "nse_mediana", "modelo": m, "estaciones": len(same),
                             "valor_principal": _r(p), "valor_subconjunto": _r(s), "diferencia": _r(s - p)})
            for m in DEEP:
                cp = M.bootstrap_median_ci((full[m] - full["xgboost"]).dropna())
                cs = M.bootstrap_median_ci((sub[m] - sub["xgboost"]).dropna())
                hres["delta_nse_vs_xgboost"][m] = {"principal_mismas": [_r(v) for v in cp],
                                                   "subconjunto": [_r(v) for v in cs], "diferencia": _r(cs[0] - cp[0])}
                rows.append({"subconjunto": sname, "h": h, "bloque": "delta_nse_vs_xgboost", "modelo": m,
                             "estaciones": len(same), "valor_principal": _r(cp[0]), "valor_subconjunto": _r(cs[0]),
                             "diferencia": _r(cs[0] - cp[0]), "ic_principal": f"[{_r(cp[1])}, {_r(cp[2])}]",
                             "ic_subconjunto": f"[{_r(cs[1])}, {_r(cs[2])}]"})
            if h in (1, 7):
                al = d["alerts"]
                keep_al = ~al[flag].to_numpy()
                cp = AE.boot_delta_csi(contingency(al, np.ones(len(al), bool), same, thr))
                cs = AE.boot_delta_csi(contingency(al, keep_al, same, thr))
                hres["delta_csi_p90"] = {"principal_mismas": [_r(v) for v in cp], "subconjunto": [_r(v) for v in cs],
                                         "diferencia": _r(cs[0] - cp[0])}
                rows.append({"subconjunto": sname, "h": h, "bloque": "delta_csi_p90", "modelo": "difuso - umbral",
                             "estaciones": len(same), "valor_principal": _r(cp[0]), "valor_subconjunto": _r(cs[0]),
                             "diferencia": _r(cs[0] - cp[0]), "ic_principal": f"[{_r(cp[1])}, {_r(cp[2])}]",
                             "ic_subconjunto": f"[{_r(cs[1])}, {_r(cs[2])}]"})
            out["por_horizonte"][f"h{h}"] = hres
        out["fraccion_excluida"]["global"] = {"emisiones": tot_n, "excluidas": tot_x, "fraccion": _r(tot_x / tot_n, 5)}
        res["subconjuntos"][sname] = out

    sec = round(time.perf_counter() - t0, 1)
    res["computo"] = {"fecha": date.today().isoformat(), "segundos": sec, "cpu": platform.processor() or "cpu"}
    pd.DataFrame(rows).to_csv(MESE / "imputados_test.csv", index=False)
    (MESE / "e_mese_imputados.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    nums = json.loads((OUT / "numbers.json").read_text(encoding="utf-8"))
    nums["mese_imputados"] = {**res, "tabla": "mese/imputados_test.csv"}
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("listo en %.0f s", sec)


if __name__ == "__main__":
    main()

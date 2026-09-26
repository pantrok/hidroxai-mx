#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E9 — baseline reproducible a 1 día: persistencia vs Ridge.

Criterios congelados en results/dib_revision/proof_ledger.md (E9):
- Datos: data/features/feature_table.parquet tal como se distribuye (unidades físicas).
- Emisión en el día t; objetivo Q(t+1), solo si su calidad == 0.
- Predictores en t: Q(t), lag1, lag3, lag7, lag14, lag30, ma7, ma30 (columnas de la tabla).
- Persistencia: Q̂(t+1) = Q(t).
- Ridge por estación, predictores estandarizados con estadísticas de entrenamiento,
  intercepto sin penalizar; alpha en logspace(-3, 3, 13) elegido por NSE de validación.
- Partición por fecha del objetivo: 2010–2020 / 2021–2022 / 2023–2025.
- Mínimos por estación: 365 / 90 / 90 objetivos válidos; las excluidas se cuentan.
- Métricas en test: NSE y KGE (Gupta et al., 2009); mediana e IQR entre estaciones.

Se reportan dos variantes (enmienda del 2026-09-26 en el ledger, sin borrar la original):
- ``congelada``: filtro de calidad solo en el objetivo, tal como se congeló;
- ``sin_outliers_en_predictores``: además excluye emisiones cuya ventana de predictores
  (t−30 … t) contiene algún valor calidad == 2; es el uso recomendado de la bandera.
Una estación sin varianza en test (NSE indefinido) se excluye y se cuenta.

Salidas: results/dib_revision/baseline_por_estacion.csv, baseline_summary.csv, e9_baseline.json
Uso:  python scripts/dib_09_baseline.py
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("dib_09")
OUT = ROOT / "results" / "dib_revision"
T = "gasto_medio_m3s"
PRED = [T, f"{T}_lag1", f"{T}_lag3", f"{T}_lag7", f"{T}_lag14", f"{T}_lag30", f"{T}_ma7", f"{T}_ma30"]
SPLITS = {"train": ("2010-01-01", "2020-12-31"), "val": ("2021-01-01", "2022-12-31"),
          "test": ("2023-01-01", "2025-12-31")}
MINS = {"train": 365, "val": 90, "test": 90}
ALPHAS = np.logspace(-3, 3, 13)


def nse(o: np.ndarray, s: np.ndarray) -> float:
    return float(1 - np.sum((s - o) ** 2) / np.sum((o - o.mean()) ** 2))


def kge(o: np.ndarray, s: np.ndarray) -> float:
    r = np.corrcoef(o, s)[0, 1]
    return float(1 - np.sqrt((r - 1) ** 2 + (s.std() / o.std() - 1) ** 2 + (s.mean() / o.mean() - 1) ** 2))


def ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    ym = y.mean()
    beta = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - ym))
    return lambda Xn: ((Xn - mu) / sd) @ beta + ym


def main() -> None:
    t_start = time.time()
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad"] + PRED,
                         filters=[("clave_estacion", "in", sel["clave"].tolist())])
    ft["fecha"] = pd.to_datetime(ft["fecha"])

    rows, excluded = [], []
    for variant in ("congelada", "sin_outliers_en_predictores"):
        for k, g in ft.groupby("clave_estacion"):
            g = g.set_index("fecha").sort_index()
            g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
            d = pd.DataFrame(g[PRED].to_numpy(), index=g.index, columns=PRED)
            d["y"] = g[T].shift(-1)
            d["y_cal"] = g["calidad"].shift(-1)
            d["outlier_en_ventana"] = (g["calidad"] == 2).astype(float).rolling(31, min_periods=1).max()
            d["fecha_obj"] = d.index + pd.Timedelta(days=1)
            keep = d["y_cal"] == 0
            if variant == "sin_outliers_en_predictores":
                keep &= d["outlier_en_ventana"] == 0
            d = d[keep].dropna(subset=PRED + ["y"])
            parts = {s: d[d["fecha_obj"].between(a, b)] for s, (a, b) in SPLITS.items()}
            n = {s: len(p) for s, p in parts.items()}
            yte = parts["test"]["y"].to_numpy()
            if any(n[s] < MINS[s] for s in MINS) or np.std(yte) == 0:
                excluded.append({"variante": variant, "clave": k, **{f"n_{s}": v for s, v in n.items()},
                                 "motivo": "sin varianza en test" if n["test"] >= MINS["test"] else "pocos datos"})
                continue
            Xtr, ytr = parts["train"][PRED].to_numpy(), parts["train"]["y"].to_numpy()
            Xva, yva = parts["val"][PRED].to_numpy(), parts["val"]["y"].to_numpy()
            Xte = parts["test"][PRED].to_numpy()
            scores = [(nse(yva, ridge_fit(Xtr, ytr, a)(Xva)), a) for a in ALPHAS]
            best_alpha = max(scores)[1]
            pred = ridge_fit(Xtr, ytr, best_alpha)(Xte)
            pers = parts["test"][T].to_numpy()
            rows.append({"variante": variant, "clave": k, **{f"n_{s}": v for s, v in n.items()},
                         "alpha": best_alpha,
                         "NSE_persistencia": nse(yte, pers), "KGE_persistencia": kge(yte, pers),
                         "NSE_ridge": nse(yte, pred), "KGE_ridge": kge(yte, pred)})

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "baseline_por_estacion.csv", index=False)
    exc = pd.DataFrame(excluded)
    exc.to_csv(OUT / "baseline_excluidas.csv", index=False)
    summ = []
    for variant, pv in per.groupby("variante"):
        for m in ("persistencia", "ridge"):
            row = {"variante": variant, "modelo": m, "n_estaciones": len(pv)}
            for met in ("NSE", "KGE"):
                q = pv[f"{met}_{m}"].quantile([0.25, 0.5, 0.75])
                row.update({f"{met}_mediana": round(q[0.5], 3), f"{met}_q25": round(q[0.25], 3),
                            f"{met}_q75": round(q[0.75], 3)})
            summ.append(row)
    summary = pd.DataFrame(summ)
    summary.to_csv(OUT / "baseline_summary.csv", index=False)
    res = {"variantes": {
        v: {"estaciones_evaluadas": int(len(pv)),
            "estaciones_excluidas": int((exc["variante"] == v).sum()) if len(exc) else 0,
            "ridge_mejor_que_persistencia_NSE": int((pv["NSE_ridge"] > pv["NSE_persistencia"]).sum())}
        for v, pv in per.groupby("variante")},
        "tabla": summary.to_dict("records"),
        "segundos": round(time.time() - t_start, 1)}
    (OUT / "e9_baseline.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("E9: %s", res)


if __name__ == "__main__":
    main()

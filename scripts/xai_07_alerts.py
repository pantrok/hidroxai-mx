#!/usr/bin/env python
"""Benchmark XAI · paso 7: alertas difusas y RQ3 (protocolo, secciones 6 y 7).

Ensamble de 12 miembros (XGBoost, TCN, ConvNeXt-1D, PatchTST con la configuración elegida ×
3 semillas). Por muestra de prueba:
- percentil = percentil de la media del ensamble en la distribución de entrenamiento de la
  estación (observaciones originales);
- dispersión = rango intercuartílico de los percentiles de los 12 miembros.
El sistema Mamdani del protocolo da el nivel 0–3. Se compara contra el umbral simple sobre la
media del ensamble para eventos P90 y P99 del gasto observado (percentiles de entrenamiento).

Salidas: results/xai_benchmark/rq3_contingency.csv, rq3_summary.csv, rq3_rules.csv, e_rq3.json
         y niveles por muestra en data/interim/xai_benchmark/alerts/<cuenca>_h<h>.parquet
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from hidroxai_mx.alert import fuzzy as F
from hidroxai_mx.models import data as D
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_07")
OUT = ROOT / "results" / "xai_benchmark"
SLUG = {"Lerma–Santiago": "lerma_santiago", "Pánuco": "panuco", "Alta del Balsas": "alta_balsas",
        "Cutzamala": "cutzamala"}
SEEDS = (20261010, 20261011, 20261012)
MODELS = ("xgboost", "tcn", "convnext", "patchtst")
EVENTS = {"P90": (0.90, 2), "P99": (0.99, 3)}   # percentil del evento; nivel difuso mínimo
N_BOOT, BOOT_SEED = 10_000, 20261010


def _counts(obs: np.ndarray, pred: np.ndarray) -> dict:
    return {"aciertos": int((obs & pred).sum()), "fallos": int((obs & ~pred).sum()),
            "falsas": int((~obs & pred).sum()), "negativos": int((~obs & ~pred).sum())}


def _scores(c) -> dict:
    a, f, fa = c["aciertos"], c["fallos"], c["falsas"]
    return {"pod": a / (a + f) if a + f else np.nan, "far": fa / (a + fa) if a + fa else np.nan,
            "csi": a / (a + f + fa) if a + f + fa else np.nan}


def _boot_delta_csi(tab: pd.DataFrame) -> tuple[float, float, float]:
    """IC del ΔCSI (difuso − umbral) remuestreando estaciones y sumando sus tablas."""
    piv = tab.pivot_table(index="clave", columns="metodo", values=["aciertos", "fallos", "falsas"], aggfunc="sum")
    arr = {m: piv.xs(m, axis=1, level=1)[["aciertos", "fallos", "falsas"]].to_numpy() for m in ("difuso", "umbral")}
    def csi(x):
        s = x.sum(0)
        return s[0] / s.sum() if s.sum() else np.nan
    point = csi(arr["difuso"]) - csi(arr["umbral"])
    rng = np.random.default_rng(BOOT_SEED)
    n = len(piv)
    bs = []
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        bs.append(csi(arr["difuso"][i]) - csi(arr["umbral"][i]))
    return float(point), float(np.nanquantile(bs, 0.025)), float(np.nanquantile(bs, 0.975))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "cpu")
    ap.add_argument("--nets", type=Path, default=ROOT / "data" / "interim" / "xai_benchmark" / "nets")
    a = ap.parse_args()
    alerts_dir = ROOT / "data" / "interim" / "xai_benchmark" / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    chosen = json.loads((OUT / "e_rq1.json").read_text(encoding="utf-8"))["configuracion_elegida"]
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    evaluable = {h: set(st.loc[(st["h"] == h) & (st["modelo"] == "persistencia"), "clave"]) for h in D.HORIZONS}

    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin_of = D.station_basins(link)
    claves = [k for k in link["clave"] if pd.notna(basin_of.get(k))]
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", D.TARGET],
                         filters=[("clave_estacion", "in", claves)])
    ft["fecha"] = pd.to_datetime(ft["fecha"])
    tr = ft[(ft["fecha"] >= D.PARTITIONS["train"][0]) & (ft["fecha"] <= D.PARTITIONS["train"][1])
            & (ft["calidad"] == 0)]
    train_obs = {k: g[D.TARGET].to_numpy() for k, g in tr.groupby("clave_estacion")}

    fis = F.build_protocol_fis()
    fis.rules_table().to_csv(OUT / "rq3_rules.csv", index=False)
    cont = []
    for basin in D.BASINS:
        for h in D.HORIZONS:
            tag = f"{SLUG[basin]}_h{h}"
            meta = pd.read_parquet(a.cpu / "meta" / f"{tag}_test.parquet")
            members = []
            for model in MODELS:
                src = a.cpu if model == "xgboost" else a.nets
                for seed in SEEDS:
                    members.append(np.load(src / "preds" / f"{chosen[f'{model}_h{h}']}_{tag}_s{seed}.npz")["flow_test"])
            members = np.stack(members)                     # [12, n]
            ens = members.mean(0)
            pct = np.empty(len(meta))
            disp = np.empty(len(meta))
            thr = {e: np.empty(len(meta)) for e in EVENTS}
            for k, idx in meta.groupby("clave").indices.items():
                ref = train_obs[k]
                pct[idx] = F.station_percentile(ens[idx], ref)
                mp = np.stack([F.station_percentile(m[idx], ref) for m in members])
                disp[idx] = np.quantile(mp, 0.75, axis=0) - np.quantile(mp, 0.25, axis=0)
                for e, (q, _) in EVENTS.items():
                    thr[e][idx] = np.quantile(ref, q)
            level = F.level_index(fis.infer_array({"percentil": pct, "dispersion": disp}))
            pd.DataFrame({"clave": meta["clave"], "issue": meta["issue"], "target_date": meta["target_date"],
                          "observado": meta["y_flow"], "ensamble": ens, "percentil": pct, "dispersion": disp,
                          "nivel": level}).to_parquet(alerts_dir / f"{tag}.parquet", index=False)
            obs_flow = meta["y_flow"].to_numpy()
            for k, idx in meta.groupby("clave").indices.items():
                if k not in evaluable[h]:
                    continue
                for e, (q, min_level) in EVENTS.items():
                    obs = obs_flow[idx] > thr[e][idx]
                    for metodo, pred in (("difuso", level[idx] >= min_level), ("umbral", pct[idx] >= q)):
                        cont.append({"cuenca": basin, "h": h, "clave": k, "evento": e, "metodo": metodo,
                                     **_counts(obs, pred)})
    ct = pd.DataFrame(cont)
    ct.to_csv(OUT / "rq3_contingency.csv", index=False)

    summ, deltas = [], {}
    groups = [(b, ct[ct["cuenca"] == b]) for b in D.BASINS] + [("agregado", ct)]
    for gname, sub in groups:
        for (h, e), x in sub.groupby(["h", "evento"]):
            row = {"grupo": gname, "h": h, "evento": e, "estaciones": int(x["clave"].nunique())}
            for metodo, y in x.groupby("metodo"):
                s = _scores(y[["aciertos", "fallos", "falsas", "negativos"]].sum())
                row.update({f"{metodo}_{k}": round(v, 4) for k, v in s.items()})
                row[f"{metodo}_eventos_observados"] = int(y["aciertos"].sum() + y["fallos"].sum())
            if gname == "agregado":
                deltas[f"{e}_h{h}"] = _boot_delta_csi(x)
                row.update({"delta_csi": round(deltas[f"{e}_h{h}"][0], 4),
                            "delta_csi_ic_lo": round(deltas[f"{e}_h{h}"][1], 4),
                            "delta_csi_ic_hi": round(deltas[f"{e}_h{h}"][2], 4)})
            summ.append(row)
    pd.DataFrame(summ).to_csv(OUT / "rq3_summary.csv", index=False)

    key = [deltas["P90_h1"], deltas["P90_h7"]]
    if all(d[1] > 0 for d in key):
        v3 = "SUPPORTED"
    elif any(d[2] < 0 for d in key) or all(d[1] <= 0 <= d[2] for d in key):
        v3 = "REJECTED"
    else:
        v3 = "OPEN"
    res = {"fecha": date.today().isoformat(),
           "fuente": "scripts/xai_07_alerts.py; results/xai_benchmark/rq3_contingency.csv",
           "ensamble": {"miembros": len(MODELS) * len(SEEDS), "modelos": MODELS},
           "H3": {"delta_csi_ic": {k: [round(x, 4) for x in v] for k, v in deltas.items()}, "veredicto": v3}}
    (OUT / "e_rq3.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("H3 %s", v3)


if __name__ == "__main__":
    main()

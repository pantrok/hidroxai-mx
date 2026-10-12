#!/usr/bin/env python
"""Benchmark XAI · paso 8: numbers.json, figuras, tablas y report.md.

No recalcula las métricas del protocolo: lee las salidas de los pasos 1–7 y el manifiesto de
cómputo. Los únicos cálculos nuevos son resúmenes descriptivos, marcados como
"descriptivo (no preregistrado)" en numbers.json:
- participación de cada grupo de canales en la importancia;
- ΔNSE contra ARIMA;
- frecuencia con que el rezago de precipitación más importante es el mínimo posible (= h);
- frontera de decisión del sistema difuso congelado.

Las figuras llevan rótulos en inglés (pensadas para un manuscrito); el reporte va en español.

Salidas (results/xai_benchmark/): numbers.json, report.md, figures/fig*.png|pdf,
tables/T*.csv y tables/tables.md
Uso:  python scripts/xai_08_report.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap, PowerNorm  # noqa: E402

from hidroxai_mx.alert import fuzzy as F  # noqa: E402
from hidroxai_mx.models import data as D  # noqa: E402
from hidroxai_mx.models import metrics as M  # noqa: E402
from hidroxai_mx.utils import FEATURES, ROOT, get_logger  # noqa: E402

log = get_logger("xai_08")
OUT = ROOT / "results" / "xai_benchmark"
FIG, TAB = OUT / "figures", OUT / "tables"
ALERTS = ROOT / "data" / "interim" / "xai_benchmark" / "alerts"
FROZEN_SHA = "8df99290b17bfc8a5a15dd46492772866ace00ec57d9687d0b5e73809db05799"
BUDGET_H = 40
HS = list(D.HORIZONS)
ORDER = ["persistencia", "climatologia", "arima", "xgboost", "tcn", "convnext", "patchtst"]
LEARNED, DEEP = ["xgboost", "tcn", "convnext", "patchtst"], ["tcn", "convnext", "patchtst"]
LABEL = {"persistencia": "Persistence", "climatologia": "Climatology", "arima": "ARIMA", "xgboost": "XGBoost",
         "tcn": "TCN", "convnext": "ConvNeXt-1D", "patchtst": "PatchTST"}
COLOR = {"persistencia": "#9e9e9e", "climatologia": "#a1887f", "arima": "#5d4037", "xgboost": "#1b9e77",
         "tcn": "#d95f02", "convnext": "#7570b3", "patchtst": "#e7298a"}
CH_LABEL = {"gasto_medio_m3s": "Q", "gasto_medio_m3s_ma7": "Q MA7", "gasto_medio_m3s_ma30": "Q MA30",
            "precip_idw_mm": "P", "doy_sin": "sin(doy)", "doy_cos": "cos(doy)"}
CH_GROUP = {"gasto_medio_m3s": "gasto", "gasto_medio_m3s_ma7": "gasto", "gasto_medio_m3s_ma30": "gasto",
            "precip_idw_mm": "precipitacion", "doy_sin": "estacionalidad", "doy_cos": "estacionalidad"}
LEVEL_COLORS = ["#e0e0e0", "#fdd835", "#fb8c00", "#c62828"]
CRITERIA = {
    "H1": "IC 95 % de la mediana de SS > 0 para ≥ 3 de 4 modelos aprendidos a 7 y 14 días (agregado)",
    "H1-b": "IC 95 % de la mediana de ΔNSE (profundo − XGBoost) > 0, por horizonte",
    "H2-a": "mediana de Spearman ≥ 0.5 en ≥ 2/3 de las combinaciones cuenca (≥ 8 est.) × horizonte",
    "H2-b": "≥ 75 % de los pares (modelo, cuenca) con rezago de precipitación más importante en 1–3 días (h = 1)",
    "H3": "IC 95 % de ΔCSI (difuso − umbral) > 0 para P90 en h = 1 y h = 7 (agregado)",
}


def _json(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _r(x, n: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def _save(fig, name: str) -> None:
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", dpi=300, bbox_inches="tight", metadata={"CreationDate": None})  # PDF reproducible
    plt.close(fig)


def _md(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def _ci(v) -> str:
    return f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]"


# ----------------------------------------------------------------------------- bloques de numbers.json
def block_data(prof: dict, e1: dict, st: pd.DataFrame) -> dict:
    pc = prof["por_cuenca"]
    return {
        "fuente": "results/xai_benchmark/sample_profile.json (scripts/xai_01_profile_samples.py); "
                  "rq1_station_metrics.csv",
        "snapshot": "v2026.10 (10.5281/zenodo.23150556)",
        "estaciones_universo": prof["estaciones"],
        "fuera_de_unidad": prof["fuera_de_unidad"],
        "estaciones_modeladas": sum(v["estaciones"] for v in pc.values()),
        "estaciones_por_cuenca": {b: v["estaciones"] for b, v in pc.items()},
        "evaluables": e1["estaciones_evaluables"],
        "evaluables_por_cuenca": {b: int(n) for b, n in st[st["h"] == 1].groupby("cuenca")["clave"].nunique().items()},
        "no_evaluables": sorted({x["clave"] for v in pc.values() for h in HS for x in v[f"h{h}"]["no_evaluables"]}),
        "muestras": {f"h{h}": {p: sum(v[f"h{h}"]["muestras"][p] for v in pc.values()) for p in ("train", "val", "test")}
                     for h in HS},
    }


def block_compute(man: pd.DataFrame, kag: dict) -> dict:
    gpu = man["dispositivo"].fillna("").str.contains("Tesla|GPU|cuda", case=False)
    main = man["tipo"] == "principal"

    def hrs(mask) -> float:
        return round(float(man.loc[mask, "segundos"].sum()) / 3600, 3)

    nets = man[main & gpu].copy()
    nets["parada_temprana"] = nets["parada_temprana"].astype(str).str.lower() == "true"
    wf = man["tipo"] == "walk_forward"
    return {
        "fuente": "results/xai_benchmark/compute_manifest.csv; kaggle_import.json",
        "nota": "horas = suma de la columna 'segundos' (tiempo de pared por corrida; en ARIMA, suma por estación)",
        "gpu": {"dispositivo": sorted(man.loc[gpu, "dispositivo"].unique().tolist()),
                "corridas": int((main & gpu).sum()),
                "horas_por_modelo": {m: hrs(main & gpu & (man["modelo"] == m)) for m in DEEP},
                "horas_total": hrs(main & gpu),
                "walk_forward": {"corridas": int((wf & gpu).sum()), "horas": hrs(wf & gpu)},
                "horas_total_con_walk_forward": hrs(gpu)},
        "cpu": {"procesador": "Intel Core Ultra 7 155H (22 hilos)",
                "horas_por_modelo": {m: hrs(main & ~gpu & (man["modelo"] == m)) for m in ("arima", "xgboost")},
                "horas_walk_forward": {m: hrs(wf & ~gpu & (man["modelo"] == m)) for m in ("arima", "xgboost")},
                "horas_piloto": hrs((man["tipo"] == "piloto") & ~gpu),
                "horas_evaluacion": {r: hrs(man["run"] == r) for r in man.loc[man["tipo"] == "evaluacion", "run"]},
                "horas_total": hrs(~gpu)},
        "presupuesto_cpu_h": BUDGET_H,
        "epocas_redes": {m: {"mediana": _r(g["epocas"].median(), 1), "min": int(g["epocas"].min()),
                             "max": int(g["epocas"].max()), "parada_temprana_frac": _r(g["parada_temprana"].mean(), 3)}
                         for m, g in nets.groupby("modelo")},
        "verificacion_kaggle": {k: kag[k] for k in ("ok", "corridas_esperadas", "predicciones", "pesos", "zip_md5")},
    }


def block_rq1(e1: dict, sm: pd.DataFrame, st: pd.DataFrame, big: list[str]) -> dict:
    def row(r) -> dict:
        d = {"estaciones": int(r["estaciones"]), "nse_mediana": _r(r["nse_mediana"]),
             "nse_iqr": [_r(r["nse_q25"]), _r(r["nse_q75"])], "kge_mediana": _r(r["kge_mediana"]),
             "rmse_mediana_m3s": _r(r["rmse_mediana"]), "ss_mediana": _r(r["ss_mediana"])}
        if pd.notna(r.get("ss_ic_lo")):
            d["ss_ic95"] = [_r(r["ss_ic_lo"]), _r(r["ss_ic_hi"])]
        return d

    agg = sm[sm["grupo"] == "agregado"]
    res = {"fuente": "scripts/xai_05_evaluate.py; results/xai_benchmark/e_rq1.json, rq1_summary.csv, "
                     "rq1_station_metrics.csv",
           "configuracion_elegida": e1["configuracion_elegida"],
           "agregado": {f"h{h}": {m: row(agg[(agg["h"] == h) & (agg["modelo"] == m)].iloc[0]) for m in ORDER}
                        for h in HS},
           "por_cuenca": {b: {f"h{h}": {m: row(sm[(sm["grupo"] == b) & (sm["h"] == h) & (sm["modelo"] == m)].iloc[0])
                                        for m in ORDER} for h in HS} for b in D.BASINS},
           "cuencas_con_inferencia": big,
           "mejor_por_nse_mediana": {f"h{h}": agg[agg["h"] == h].sort_values("nse_mediana").iloc[-1]["modelo"]
                                     for h in HS},
           "sd_nse_entre_semillas_mediana": {f"{m}_h{h}": _r(st[(st["modelo"] == m) & (st["h"] == h)]
                                                              ["nse_semillas_sd"].median())
                                             for m in LEARNED for h in HS},
           "H1": e1["H1"], "H1b": e1["H1b"]}
    dn = {}
    for h in HS:
        x = st[st["h"] == h].pivot_table(index="clave", columns="modelo", values="nse")
        for m in LEARNED:
            med, lo, hi = M.bootstrap_median_ci((x[m] - x["arima"]).dropna())
            dn[f"{m}_h{h}"] = [_r(med), _r(lo), _r(hi)]
    res["delta_nse_vs_arima"] = {"tipo": "descriptivo (no preregistrado)",
                                 "metodo": "mediana por estación de NSE_modelo − NSE_ARIMA; bootstrap de estaciones "
                                           "(10,000, semilla 20261010)", "ic95": dn}

    def comps(x: pd.DataFrame) -> dict:
        return {"kge_mediana": _r(x["kge"].median()), "r_mediana": _r(x["kge_r"].median()),
                "alpha_mediana": _r(x["kge_alpha"].median()), "beta_mediana": _r(x["kge_beta"].median()),
                "fraccion_alpha_lt_1": _r((x["kge_alpha"] < 1).mean(), 3), "estaciones": int(x["clave"].nunique())}

    res["kge_componentes"] = {
        "tipo": "descriptivo (no preregistrado)",
        "fuente": "scripts/xai_05_evaluate.py (columnas kge_r, kge_alpha, kge_beta de rq1_station_metrics.csv)",
        "nota": "KGE = 1 − √((r − 1)² + (α − 1)² + (β − 1)²); α = σ_sim/σ_obs, β = μ_sim/μ_obs",
        "agregado": {f"h{h}": {m: comps(st[(st["h"] == h) & (st["modelo"] == m)]) for m in ORDER} for h in HS},
        "por_cuenca": {b: {f"h{h}": {m: comps(st[(st["cuenca"] == b) & (st["h"] == h) & (st["modelo"] == m)])
                                     for m in ORDER} for h in HS} for b in D.BASINS}}
    return res


def block_walk_forward(ewf: dict, wfs: pd.DataFrame) -> dict:
    agg = wfs[wfs["grupo"] == "agregado"]
    out = {"fuente": "scripts/xai_09_walk_forward.py, scripts/xai_10_walk_forward_eval.py; "
                     "results/xai_benchmark/e_walkforward.json, wf_*.csv",
           "tipo": "robustez (protocolo §3); no cambia los veredictos de §7",
           **{k: ewf[k] for k in ("especificacion", "años", "semilla", "consistencia", "estaciones_evaluables",
                                  "redes_disponibles", "verificacion_redes", "ranking")},
           "agregado": {str(y): {f"h{h}": {r.modelo: {"nse_mediana": _r(r.nse_mediana), "ss_mediana": _r(r.ss_mediana),
                                                    **({"ss_ic95": [_r(r.ss_ic_lo), _r(r.ss_ic_hi)]}
                                                       if pd.notna(r.ss_ic_lo) else {})}
                                          for r in agg[(agg["año"] == y) & (agg["h"] == h)].itertuples()}
                                 for h in HS} for y in ewf["años"]}}
    for k in ("H1", "H1b", "H2a", "H2b", "H3", "pendiente"):
        if k in ewf:
            out[k] = ewf[k]
    return out


def block_rq2(e2: dict, imp: pd.DataFrame, conc: pd.DataFrame, lags: pd.DataFrame, igd: pd.DataFrame,
              att: pd.DataFrame) -> dict:
    big = e2["cuencas_con_inferencia"]
    ib = imp[imp["cuenca"].isin(big)].assign(grupo=lambda d: d["canal"].map(CH_GROUP))
    share = (ib.groupby(["h", "modelo", "cuenca", "grupo"])["importancia"].sum()
             .groupby(["h", "modelo", "grupo"]).mean())
    recent = (ib[ib["rezago_ventana"] <= 2].groupby(["h", "modelo", "cuenca"])["importancia"].sum()
              .groupby(["h", "modelo"]).mean())
    pairs = conc[conc["cuenca"].isin(big)].groupby(["modelo_a", "modelo_b"])["spearman"].mean()
    lb = lags[lags["cuenca"].isin(big)]
    return {
        "fuente": "scripts/xai_06_explain.py; results/xai_benchmark/e_rq2.json, rq2_*.csv",
        "muestra": e2["muestra"], "cuencas_con_inferencia": big,
        "H2a": e2["H2a"], "H2b": e2["H2b"],
        "spearman_mediano_todas": {f"{b}_h{h}": _r(v, 3) for (b, h), v in
                                   conc.groupby(["cuenca", "h"])["spearman"].median().items()},
        "spearman_medio_por_par": {f"{a}~{b}": _r(v, 3) for (a, b), v in pairs.items()},
        "rezago_precip_mas_importante": {f"{r.cuenca}_h{r.h}_{r.modelo}": int(r.rezago_precip_mas_importante)
                                         for r in lags.itertuples()},
        "rezago_igual_al_minimo": {
            "tipo": "descriptivo (no preregistrado)",
            "nota": "rezago respecto al objetivo = h equivale a la precipitación del día de emisión",
            "fraccion_por_h": {f"h{h}": _r((lb[lb["h"] == h]["rezago_precip_mas_importante"] == h).mean(), 3)
                               for h in HS}},
        "participacion_canales": {"tipo": "descriptivo (no preregistrado)",
                                  "nota": "suma de importancias por grupo de canales, media de las cuencas con inferencia",
                                  "valores": {f"{m}_h{h}": {g: _r(share[(h, m, g)], 3)
                                                            for g in ("gasto", "precipitacion", "estacionalidad")}
                                              for h in HS for m in LEARNED}},
        "participacion_ultimos_3_dias": {"tipo": "descriptivo (no preregistrado)",
                                         "valores": {f"{m}_h{h}": _r(recent[(h, m)], 3) for h in HS for m in LEARNED}},
        "ig_error_completitud": {m: {"mediana_abs": float(f"{g['delta_abs_mediana'].median():.3g}"),
                                     "p95_abs_max": float(f"{g['delta_abs_p95'].max():.3g}")}
                                 for m, g in igd.groupby("modelo")},
        "atencion_patchtst_por_parche": {f"h{h}": {str(p): _r(v, 4) for p, v in
                                                   att[(att["h"] == h) & att["cuenca"].isin(big)]
                                                   .groupby("dias_ventana", sort=False)["atencion_recibida"].mean().items()}
                                         for h in HS},
    }


def fis_boundary() -> dict:
    fis = F.build_protocol_fis()
    p = np.round(np.arange(0.5, 1.00001, 0.0005), 4)
    out = {}
    for d in (0.0, 0.05, 0.10, 0.15, 0.30):
        lv = F.level_index(fis.infer_array({"percentil": p, "dispersion": np.full(len(p), d)}))
        out[f"dispersion_{d:.2f}"] = {"percentil_min_alerta": _r(p[np.argmax(lv >= 2)]) if (lv >= 2).any() else None,
                                      "percentil_min_emergencia": _r(p[np.argmax(lv >= 3)]) if (lv >= 3).any() else None}
    return out


def edge_cases() -> dict:
    """Muestras afectadas por la corrección del TrapezoidalMF (todas las estaciones modeladas)."""
    al = pd.concat([pd.read_parquet(f, columns=["percentil", "dispersion"]) for f in sorted(ALERTS.glob("*.parquet"))])
    hi = al["percentil"] >= 0.90
    return {"muestras": len(al), "fraccion_dispersion_cero": _r((al["dispersion"] == 0).mean()),
            "fraccion_percentil_uno": _r((al["percentil"] == 1).mean()),
            "fraccion_dispersion_cero_si_percentil_ge_0.90": _r((al.loc[hi, "dispersion"] == 0).mean())}


def block_rq3(e3: dict, pre: dict, rs: pd.DataFrame, pre_rs: pd.DataFrame) -> dict:
    agg = rs[rs["grupo"] == "agregado"]
    keep = ["difuso_pod", "difuso_far", "difuso_csi", "umbral_pod", "umbral_far", "umbral_csi",
            "difuso_eventos_observados", "estaciones"]
    pa = pre_rs[pre_rs["grupo"] == "agregado"].set_index(["evento", "h"])
    return {
        "fuente": "scripts/xai_07_alerts.py; results/xai_benchmark/e_rq3.json, rq3_summary.csv, rq3_contingency.csv",
        "ensamble": e3["ensamble"], "H3": e3["H3"],
        "agregado": {f"{r.evento}_h{r.h}": {k: (_r(getattr(r, k)) if "eventos" not in k and k != "estaciones"
                                               else int(getattr(r, k))) for k in keep} for r in agg.itertuples()},
        "variante_pre_correccion": {
            "fuente": "results/xai_benchmark/rq3_pre_correccion/ (misma versión de xai_07 con el TrapezoidalMF anterior)",
            "motivo": "pertenencia 0 en los hombros verticales de los trapecios (dispersión = 0 o percentil = 1)",
            "H3": pre["H3"], "muestras_afectadas": edge_cases(),
            "agregado": {f"{e}_h{h}": {"difuso_pod": _r(r["difuso_pod"]), "difuso_far": _r(r["difuso_far"]),
                                       "difuso_csi": _r(r["difuso_csi"])} for (e, h), r in pa.iterrows()}},
        "frontera_decision_difusa": {"tipo": "descriptivo (propiedad del sistema congelado)", "valores": fis_boundary()},
        "mecanismo": {"tipo": "descriptivo (no preregistrado)", "fuente": "results/xai_benchmark/rq3_mechanism.csv",
                      "nota": "alarmas de ambos métodos, solo del umbral (suprimidas por el sistema difuso) y solo "
                              "difusas; dispersion_alta = dispersión ≥ 0.15",
                      "valores": {f"{r.evento}_h{r.h}_{r.categoria}": {"alarmas": int(r.alarmas),
                                                                       "aciertos": int(r.aciertos),
                                                                       "dispersion_alta": int(r.dispersion_alta),
                                                                       "tasa_acierto": _r(r.tasa_acierto)}
                                  for r in pd.read_csv(OUT / "rq3_mechanism.csv").itertuples()}},
    }


# ----------------------------------------------------------------------------- figuras
def fig_rq1_skill(sm: pd.DataFrame) -> None:
    agg = sm[sm["grupo"] == "agregado"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3))
    x = np.arange(len(HS))
    for i, m in enumerate(ORDER):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(ORDER) - 1) / 2) * 0.11
        axes[0].errorbar(x + off, r["nse_mediana"], yerr=[r["nse_mediana"] - r["nse_q25"], r["nse_q75"] - r["nse_mediana"]],
                         fmt="o", ms=3.5, lw=0.9, capsize=1.5, color=COLOR[m], label=LABEL[m])
    axes[0].axhline(0, color="k", lw=0.5)
    axes[0].set_ylabel("NSE (median and IQR, 91 stations)")
    lo_lim = -0.4
    models_b = [m for m in ORDER if m != "persistencia"]
    for i, m in enumerate(models_b):
        r = agg[agg["modelo"] == m].set_index("h").loc[HS]
        off = (i - (len(models_b) - 1) / 2) * 0.13
        for j, h in enumerate(HS):
            med, lo, hi = r.loc[h, ["ss_mediana", "ss_ic_lo", "ss_ic_hi"]]
            if med < lo_lim:
                axes[1].plot(x[j] + off, lo_lim + 0.03, marker="v", color=COLOR[m], ms=4)
                axes[1].annotate(f"{med:.2f}", (x[j] + off, lo_lim + 0.07), fontsize=6, ha="center", color=COLOR[m])
            else:
                axes[1].errorbar(x[j] + off, med, yerr=[[med - lo], [hi - med]], fmt="o", ms=3.5, lw=0.9,
                                 capsize=1.5, color=COLOR[m])
    axes[1].axhline(0, color="k", lw=0.5)
    axes[1].set_ylim(lo_lim, 0.45)
    axes[1].set_ylabel("Skill vs persistence (median, 95% CI)")
    for ax, t in zip(axes, ("a", "b"), strict=True):
        ax.set_xticks(x, [f"h = {h} d" for h in HS])
        ax.set_title(f"({t})", loc="left", fontsize=9)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=7, fontsize=7, frameon=False,
               bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    _save(fig, "fig1_rq1_skill_by_horizon")


def fig_rq1_basins(sm: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.4), sharey=True)
    basins = list(D.BASINS)
    for ax, h in zip(axes, HS, strict=True):
        sub = sm[sm["h"] == h]
        mat = np.array([[sub[(sub["grupo"] == b) & (sub["modelo"] == m)]["nse_mediana"].item() for b in basins]
                        for m in ORDER])
        im = ax.imshow(mat, cmap="RdYlBu", vmin=-0.5, vmax=1.0, aspect="auto")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=6.5)
        n = [int(sub[(sub["grupo"] == b)]["estaciones"].iloc[0]) for b in basins]
        ax.set_xticks(range(len(basins)), [f"{b}\n(n = {k})" for b, k in zip(basins, n, strict=True)], fontsize=6.5)
        ax.set_title(f"h = {h} d", fontsize=9)
    axes[0].set_yticks(range(len(ORDER)), [LABEL[m] for m in ORDER], fontsize=7.5)
    fig.colorbar(im, ax=axes, shrink=0.8, label="Median NSE")
    _save(fig, "fig2_rq1_nse_by_basin")


def fig_rq1_delta(e1: dict) -> None:
    ci = e1["H1b"]["ic_mediana_delta_nse"]
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    y, labels = 0, []
    for h in HS:
        for m in DEEP:
            med, lo, hi = ci[f"{m}_h{h}"]
            ax.errorbar(med, -y, xerr=[[med - lo], [hi - med]], fmt="o", ms=4, color=COLOR[m], capsize=2, lw=1)
            labels.append(f"{LABEL[m]}, h = {h}")
            y += 1
        y += 0.6
    ys = [-v for v in (0, 1, 2, 3.6, 4.6, 5.6, 7.2, 8.2, 9.2)]
    ax.set_yticks(ys, labels, fontsize=7)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel("Median ΔNSE (deep − XGBoost), 95% CI")
    _save(fig, "fig3_rq1_delta_nse_vs_xgboost")


def fig_rq2_maps(imp: pd.DataFrame, big: list[str]) -> None:
    ib = imp[imp["cuenca"].isin(big)].groupby(["h", "modelo", "canal", "rezago_ventana"])["importancia"].mean()
    vmax = float(ib.max())
    fig, axes = plt.subplots(len(HS), len(LEARNED), figsize=(10, 5.6), sharex=True, sharey=True)
    for i, h in enumerate(HS):
        for j, m in enumerate(LEARNED):
            mat = ib.loc[(h, m)].unstack("rezago_ventana").reindex(index=D.CHANNELS)
            mat = mat[sorted(mat.columns, reverse=True)]
            im = axes[i, j].imshow(mat.to_numpy(), aspect="auto", cmap="viridis", norm=PowerNorm(0.4, 0, vmax))
            if i == 0:
                axes[i, j].set_title(LABEL[m], fontsize=9)
            if j == 0:
                axes[i, j].set_ylabel(f"h = {h} d", fontsize=9)
    axes[0, 0].set_yticks(range(len(D.CHANNELS)), [CH_LABEL[c] for c in D.CHANNELS])
    for ax in axes[:, 0]:
        ax.tick_params(axis="y", labelsize=7)
    for ax in axes[-1]:
        ax.set_xticks([0, 9, 19, 29], ["t−29", "t−20", "t−10", "t"], fontsize=7)
    fig.colorbar(im, ax=axes, shrink=0.85, label="Mean normalised |attribution|")
    fig.suptitle("Importance by input and window day (mean of Lerma–Santiago, Pánuco, Alta del Balsas)", fontsize=9)
    _save(fig, "fig4_rq2_importance_maps")


def fig_rq2_concordance(conc: pd.DataFrame, big: list[str]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.3), gridspec_kw={"width_ratios": [1.1, 1]})
    basins = list(D.BASINS)
    med = conc.groupby(["cuenca", "h"])["spearman"].median().unstack("h").reindex(index=basins)[HS]
    im = axes[0].imshow(med.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    for i in range(med.shape[0]):
        for j in range(med.shape[1]):
            axes[0].text(j, i, f"{med.iat[i, j]:.2f}", ha="center", va="center", fontsize=7.5)
    axes[0].set_xticks(range(len(HS)), [f"h = {h}" for h in HS], fontsize=7.5)
    axes[0].set_yticks(range(len(basins)), [b if b in big else f"{b} (descr.)" for b in basins], fontsize=7.5)
    axes[0].set_title("(a) Median pairwise Spearman", loc="left", fontsize=9)
    pairs = conc[conc["cuenca"].isin(big)].groupby(["modelo_a", "modelo_b"])["spearman"].mean()
    mat = np.eye(len(LEARNED))
    for (a, b), v in pairs.items():
        i, j = LEARNED.index(a), LEARNED.index(b)
        mat[i, j] = mat[j, i] = v
    axes[1].imshow(mat, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(len(LEARNED)):
        for j in range(len(LEARNED)):
            axes[1].text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7.5)
    axes[1].set_xticks(range(len(LEARNED)), [LABEL[m] for m in LEARNED], fontsize=7, rotation=20)
    axes[1].set_yticks(range(len(LEARNED)), [LABEL[m] for m in LEARNED], fontsize=7)
    axes[1].set_title("(b) Mean Spearman by model pair", loc="left", fontsize=9)
    fig.colorbar(im, ax=axes, shrink=0.8, label="Spearman ρ")
    _save(fig, "fig5_rq2_concordance")


def fig_rq2_precip(imp: pd.DataFrame, big: list[str]) -> None:
    p = imp[(imp["canal"] == "precip_idw_mm") & imp["cuenca"].isin(big)]
    fig, axes = plt.subplots(len(HS), len(big), figsize=(9, 6), sharex=True)
    for i, h in enumerate(HS):
        for j, b in enumerate(big):
            ax = axes[i, j]
            if h == 1:
                ax.axvspan(1, 3, color="#bbdefb", alpha=0.6, lw=0)
            for m in LEARNED:
                s = p[(p["h"] == h) & (p["cuenca"] == b) & (p["modelo"] == m)].sort_values("rezago_objetivo")
                ax.plot(s["rezago_objetivo"], s["importancia"], color=COLOR[m], lw=1, label=LABEL[m])
                k = s["importancia"].idxmax()
                ax.plot(s.loc[k, "rezago_objetivo"], s.loc[k, "importancia"], "o", color=COLOR[m], ms=3)
            if i == 0:
                ax.set_title(b, fontsize=9)
            if j == 0:
                ax.set_ylabel(f"h = {h} d\nP importance", fontsize=8)
            ax.tick_params(labelsize=7)
    for ax in axes[-1]:
        ax.set_xlabel("Lag relative to target day (d)", fontsize=8)
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="lower center", ncol=4, fontsize=7, frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "fig6_rq2_precip_lag_profiles")


def fig_rq3_skill(rs: pd.DataFrame, e3: dict, pre: dict) -> None:
    agg = rs[rs["grupo"] == "agregado"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), gridspec_kw={"width_ratios": [1, 1, 1.3]})
    x = np.arange(len(HS))
    for ax, ev, t in ((axes[0], "P90", "a"), (axes[1], "P99", "b")):
        s = agg[agg["evento"] == ev].set_index("h").loc[HS]
        ax.bar(x - 0.18, s["difuso_csi"], 0.36, color="#c62828", label="Mamdani")
        ax.bar(x + 0.18, s["umbral_csi"], 0.36, color="#90a4ae", label="Threshold")
        ax.set_xticks(x, [f"h = {h}" for h in HS])
        ax.set_title(f"({t}) CSI, events > {ev}", loc="left", fontsize=9)
    axes[0].legend(fontsize=7, frameon=False)
    keys = [f"{e}_h{h}" for e in ("P90", "P99") for h in HS]
    for k, (src, mk, lab) in enumerate(((e3, "o", "corrected"), (pre, "s", "pre-correction"))):
        for i, key in enumerate(keys):
            med, lo, hi = src["H3"]["delta_csi_ic"][key]
            yy = -i + (0.15 if k == 0 else -0.15)
            axes[2].errorbar(med, yy, xerr=[[med - lo], [hi - med]], fmt=mk, ms=4, capsize=2, lw=1,
                             color="#c62828" if k == 0 else "#bdbdbd", mfc="#c62828" if k == 0 else "white",
                             label=lab if i == 0 else None)
    axes[2].set_yticks([-i for i in range(len(keys))], [k.replace("_", ", ") for k in keys], fontsize=7)
    axes[2].axvline(0, color="k", lw=0.6)
    axes[2].set_xlabel("ΔCSI (Mamdani − threshold), 95% CI", fontsize=8)
    axes[2].set_title("(c) Station-bootstrap ΔCSI", loc="left", fontsize=9)
    axes[2].legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    _save(fig, "fig7_rq3_alert_skill")


def fig_rq3_surface() -> None:
    fis = F.build_protocol_fis()
    pg, dg = np.linspace(0.6, 1.0, 321), np.linspace(0.0, 0.6, 241)
    P, Dd = np.meshgrid(pg, dg)
    lv = F.level_index(fis.infer_array({"percentil": P.ravel(), "dispersion": Dd.ravel()})).reshape(P.shape)
    fig, ax = plt.subplots(figsize=(5, 3.4))
    cmap = ListedColormap(LEVEL_COLORS)
    im = ax.pcolormesh(P, Dd, lv, cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4), shading="auto")
    for q in (0.90, 0.99):
        ax.axvline(q, color="k", ls="--", lw=0.7)
    ax.set_xlabel("Ensemble-mean percentile (station training distribution)")
    ax.set_ylabel("Member dispersion (IQR of percentiles)")
    cb = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cb.ax.set_yticklabels(["normal", "watch", "alert", "emergency"], fontsize=7)
    _save(fig, "fig8_rq3_fuzzy_decision_surface")


def fig_rq3_timeline(ct: pd.DataFrame) -> str:
    c = ct[(ct["cuenca"] == "Lerma–Santiago") & (ct["h"] == 1) & (ct["evento"] == "P90") & (ct["metodo"] == "difuso")]
    c = c.assign(ev=c["aciertos"] + c["fallos"]).sort_values(["ev", "clave"], ascending=[False, True])
    clave = c.iloc[0]["clave"]
    a = pd.read_parquet(ALERTS / "lerma_santiago_h1.parquet")
    a = a[a["clave"] == clave].sort_values("target_date")
    ft = pd.read_parquet(FEATURES / "feature_table.parquet", columns=["clave_estacion", "fecha", "calidad", D.TARGET],
                         filters=[("clave_estacion", "==", clave)])
    ft["fecha"] = pd.to_datetime(ft["fecha"])
    tr = ft[(ft["fecha"] >= D.PARTITIONS["train"][0]) & (ft["fecha"] <= D.PARTITIONS["train"][1]) & (ft["calidad"] == 0)]
    q90, q99 = np.quantile(tr[D.TARGET], [0.90, 0.99])
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9, 3.6), sharex=True, gridspec_kw={"height_ratios": [4, 0.6]})
    ax.plot(a["target_date"], a["observado"], color="k", lw=0.7, label="Observed")
    ax.plot(a["target_date"], a["ensamble"], color="#1565c0", lw=0.7, label="Ensemble mean (12 members)")
    ax.axhline(q90, color="#fb8c00", ls="--", lw=0.7, label="P90 (training)")
    ax.axhline(q99, color="#c62828", ls="--", lw=0.7, label="P99 (training)")
    ax.set_ylabel("Q (m³/s)")
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper left")
    ax.set_title(f"Station {clave} (Lerma–Santiago), h = 1 d, test period", fontsize=9, loc="left")
    ax2.bar(a["target_date"], np.ones(len(a)), width=1.0, color=[LEVEL_COLORS[v] for v in a["nivel"]], lw=0)
    ax2.set_yticks([])
    ax2.set_ylabel("Level", fontsize=7)
    _save(fig, "fig9_rq3_alert_timeline_example")
    return clave


def fig_walk_forward(wfs: pd.DataFrame, ewf: dict, e3: dict) -> None:
    agg = wfs[wfs["grupo"] == "agregado"]
    years = ewf["años"]
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.4))
    shown = [m for m in ORDER if m != "climatologia"]   # su escala (NSE −2.4 en 2023) taparía al resto; ver T7b
    ax = axes[0, 0]
    for m in shown:
        s = agg[(agg["h"] == 1) & (agg["modelo"] == m)].set_index("año").reindex(years)
        if s["nse_mediana"].notna().any():
            ax.plot(years, s["nse_mediana"], "o-", ms=3.5, lw=1, color=COLOR[m], label=LABEL[m])
    ax.set_ylabel("Median NSE")
    ax.set_title("(a) h = 1 d", loc="left", fontsize=9)
    for ax, h, t in ((axes[0, 1], 7, "b"), (axes[1, 0], 14, "c")):
        models = [m for m in shown if m != "persistencia"]
        for i, m in enumerate(models):
            s = agg[(agg["h"] == h) & (agg["modelo"] == m)].set_index("año").reindex(years)
            if s["ss_mediana"].isna().all():
                continue
            x = np.array(years) + (i - (len(models) - 1) / 2) * 0.1
            ax.errorbar(x, s["ss_mediana"], yerr=[s["ss_mediana"] - s["ss_ic_lo"], s["ss_ic_hi"] - s["ss_mediana"]],
                        fmt="o-", ms=3.5, lw=0.9, capsize=1.5, color=COLOR[m])
        ax.axhline(0, color="k", lw=0.5)
        ax.set_ylabel("Skill vs persistence (median, 95% CI)")
        ax.set_title(f"({t}) h = {h} d", loc="left", fontsize=9)
    ax = axes[1, 1]
    if "H3" in ewf:
        for j, (key, col) in enumerate((("P90_h1", "#c62828"), ("P90_h7", "#1565c0"))):
            v = np.array([ewf["H3"]["por_año"][str(y)]["delta_csi_ic"][key] for y in years])
            x = np.array(years) + (j - 0.5) * 0.15
            ax.errorbar(x, v[:, 0], yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], fmt="o", ms=4, capsize=2,
                        color=col, label=f"{key.replace('_', ', ')} (4 members, fold)")
            ax.axhline(ewf["H3"]["referencia_principal_4_miembros"]["delta_csi_ic"][key][0], color=col, ls="--", lw=0.8)
            ax.axhline(e3["H3"]["delta_csi_ic"][key][0], color=col, ls=":", lw=0.8)
        ax.axhline(0, color="k", lw=0.5)
        ax.legend(fontsize=6.5, frameon=False, loc="upper right")
        ax.text(0.01, 0.02, "dashed: main split, 4 members · dotted: main split, 12 members",
                transform=ax.transAxes, fontsize=6.5)
    else:
        ax.text(0.5, 0.5, "pending (network runs)", ha="center", va="center", transform=ax.transAxes)
    ax.set_ylabel("ΔCSI (Mamdani − threshold), 95% CI")
    ax.set_title("(d) Alerts, events > P90", loc="left", fontsize=9)
    for ax in axes.ravel():
        ax.set_xticks(years, [str(y) for y in years])
        ax.tick_params(labelsize=7.5)
    for ax in axes[1]:
        ax.set_xlabel("Test year (training 2010 to year − 2, validation year − 1)", fontsize=8)
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="lower center", ncol=6, fontsize=7, frameon=False,
               bbox_to_anchor=(0.5, -0.03), title="Climatology omitted (see table T7b)", title_fontsize=7)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save(fig, "fig10_walk_forward")


def tables_walk_forward(ewf: dict, wfs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def get(*keys):
        x = ewf
        for k in keys:
            if k not in x:
                return "pendiente"
            x = x[k]
        return x

    rk = ewf["ranking"]
    rows = []
    for y in ewf["años"]:
        ys = str(y)
        rows.append({"año de prueba": y, "estaciones (h = 1)": ewf["estaciones_evaluables"][ys]["h1"],
                     "H1": get("H1", "por_año", ys, "veredicto"),
                     "H1-b (h1 / h7 / h14)": " / ".join(str(get("H1b", "por_año", ys, f"h{h}", "veredicto")) for h in HS),
                     "H2-a": get("H2a", "por_año", ys, "veredicto_h2a"),
                     "H2-b": get("H2a", "por_año", ys, "veredicto_h2b"),
                     "H3 (4 miembros)": get("H3", "por_año", ys, "veredicto"),
                     "mejor NSE (h1 / h7 / h14)": " / ".join(LABEL[rk[f"h{h}"]["mejor_por_año"][ys]] for h in HS)})
    rob = {"H1": get("H1", "robustez", "robustez"), "H2-a": get("H2a", "robustez", "robustez"),
           "H2-b": get("H2b", "robustez", "robustez"), "H3 (4 miembros)": get("H3", "robustez", "robustez"),
           "H1-b (h1 / h7 / h14)": " / ".join(str(get("H1b", "robustez", f"h{h}", "robustez")) for h in HS),
           "mejor NSE (h1 / h7 / h14)": "W de Kendall " + " / ".join(str(rk[f"h{h}"]["kendall_w"]) for h in HS)}
    rows.append({"año de prueba": "robustez", "estaciones (h = 1)": "", **rob})
    agg = wfs[wfs["grupo"] == "agregado"]
    t7b = pd.DataFrame([{"año": r.año, "h": r.h, "modelo": LABEL[r.modelo], "estaciones": int(r.estaciones),
                         "NSE mediana": f"{r.nse_mediana:.3f}",
                         "SS mediana [IC 95 %]": (f"{r.ss_mediana:.3f} [{r.ss_ic_lo:.3f}, {r.ss_ic_hi:.3f}]"
                                                  if pd.notna(r.ss_ic_lo) else f"{r.ss_mediana:.3f}")}
                        for r in agg.sort_values(["h", "año"]).itertuples()])
    return {"T7_walk_forward": pd.DataFrame(rows), "T7b_walk_forward_metricas": t7b}


# ----------------------------------------------------------------------------- tablas y reporte
def tables(nums: dict, sm: pd.DataFrame, conc: pd.DataFrame, lags: pd.DataFrame, rs: pd.DataFrame,
           pre: dict, e3: dict) -> dict[str, pd.DataFrame]:
    agg = sm[sm["grupo"] == "agregado"]
    t1 = pd.DataFrame([{"h": h, "modelo": LABEL[m],
                        "NSE mediana [IQR]": f"{r.nse_mediana:.3f} [{r.nse_q25:.3f}, {r.nse_q75:.3f}]",
                        "KGE mediana": f"{r.kge_mediana:.3f}", "RMSE mediana (m³/s)": f"{r.rmse_mediana:.2f}",
                        "SS mediana [IC 95 %]": (f"{r.ss_mediana:.3f} [{r.ss_ic_lo:.3f}, {r.ss_ic_hi:.3f}]"
                                                 if m != "persistencia" else "0 (referencia)")}
                       for h in HS for m in ORDER
                       for r in [agg[(agg["h"] == h) & (agg["modelo"] == m)].iloc[0]]])
    big = nums["rq1"]["cuencas_con_inferencia"]
    t2 = pd.DataFrame([{"cuenca": b, "estaciones": int(r.estaciones), "h": h, "modelo": LABEL[m],
                        "NSE mediana": f"{r.nse_mediana:.3f}",
                        "SS mediana [IC 95 %]": (f"{r.ss_mediana:.3f} [{r.ss_ic_lo:.3f}, {r.ss_ic_hi:.3f}]"
                                                 if b in big and m != "persistencia" else f"{r.ss_mediana:.3f}")}
                       for b in D.BASINS for h in HS for m in ORDER
                       for r in [sm[(sm["grupo"] == b) & (sm["h"] == h) & (sm["modelo"] == m)].iloc[0]]])
    med = conc.groupby(["cuenca", "h"])["spearman"].median()
    lp = lags.pivot_table(index=["cuenca", "h"], columns="modelo", values="rezago_precip_mas_importante")
    t3 = pd.DataFrame([{"cuenca": b, "h": h, "Spearman mediano": f"{med[(b, h)]:.2f}",
                        **{f"rezago P {LABEL[m]} (d)": int(lp.loc[(b, h), m]) for m in LEARNED}}
                       for b in D.BASINS for h in HS])
    a3 = rs[rs["grupo"] == "agregado"]
    t4 = pd.DataFrame([{"evento": r.evento, "h": r.h, "eventos": int(r.difuso_eventos_observados),
                        "POD difuso": f"{r.difuso_pod:.3f}", "FAR difuso": f"{r.difuso_far:.3f}",
                        "CSI difuso": f"{r.difuso_csi:.3f}", "POD umbral": f"{r.umbral_pod:.3f}",
                        "FAR umbral": f"{r.umbral_far:.3f}", "CSI umbral": f"{r.umbral_csi:.3f}",
                        "ΔCSI [IC 95 %]": _ci(e3["H3"]["delta_csi_ic"][f"{r.evento}_h{r.h}"]),
                        "ΔCSI pre-corrección": _ci(pre["H3"]["delta_csi_ic"][f"{r.evento}_h{r.h}"])}
                       for r in a3.sort_values(["evento", "h"]).itertuples()])
    v = nums["veredictos"]
    t5 = pd.DataFrame([{"ID": k, "criterio SUPPORTED": CRITERIA[k],
                        "veredicto": v[k] if isinstance(v[k], str) else ", ".join(f"{a}: {b}" for a, b in v[k].items())}
                       for k in CRITERIA])
    c = nums["computo"]
    t6 = pd.DataFrame([*({"recurso": "GPU " + "/".join(c["gpu"]["dispositivo"]), "componente": LABEL[m], "horas": h}
                         for m, h in c["gpu"]["horas_por_modelo"].items()),
                       *({"recurso": "CPU", "componente": LABEL[m], "horas": h}
                         for m, h in c["cpu"]["horas_por_modelo"].items()),
                       {"recurso": "CPU", "componente": "piloto de tiempos", "horas": c["cpu"]["horas_piloto"]},
                       *({"recurso": "CPU", "componente": r, "horas": h}
                         for r, h in c["cpu"]["horas_evaluacion"].items()),
                       *({"recurso": "CPU", "componente": f"walk-forward {LABEL[m]}", "horas": h}
                         for m, h in c["cpu"]["horas_walk_forward"].items()),
                       {"recurso": "GPU", "componente": "walk-forward (redes)", "horas": c["gpu"]["walk_forward"]["horas"]},
                       {"recurso": "GPU", "componente": "total diseño principal", "horas": c["gpu"]["horas_total"]},
                       {"recurso": "GPU", "componente": "total con walk-forward",
                        "horas": c["gpu"]["horas_total_con_walk_forward"]},
                       {"recurso": "CPU", "componente": "total", "horas": c["cpu"]["horas_total"]}])
    kc = nums["rq1"]["kge_componentes"]["agregado"]
    t1b = pd.DataFrame([{"h": h, "modelo": LABEL[m], "KGE mediana": f"{x['kge_mediana']:.3f}",
                         "r mediana": f"{x['r_mediana']:.3f}", "α mediana": f"{x['alpha_mediana']:.3f}",
                         "β mediana": f"{x['beta_mediana']:.3f}", "fracción con α < 1": f"{x['fraccion_alpha_lt_1']:.3f}"}
                        for h in HS for m in ORDER for x in [kc[f"h{h}"][m]]])
    return {"T1_rq1_agregado": t1, "T1b_rq1_kge_componentes": t1b, "T2_rq1_por_cuenca": t2,
            "T3_rq2_concordancia_rezagos": t3, "T4_rq3_alertas": t4, "T5_hipotesis": t5, "T6_computo": t6}


def walk_forward_section(nums: dict, tabs: dict[str, pd.DataFrame]) -> list[str]:
    if "walk_forward" not in nums:
        return []
    w = nums["walk_forward"]
    out = ["## 6. Robustez · walk-forward anual", "",
           f"- Pliegues del protocolo §3 (entrenamiento 2010 – Y−2, validación Y−1, prueba Y; Y = "
           f"{w['años'][0]}–{w['años'][-1]}), una semilla ({w['semilla']}); especificación: {w['especificacion']}.",
           "- Comprobaciones: las funciones de criterios reproducen los veredictos oficiales y la evaluación de "
           "alertas con 12 miembros reproduce `e_rq3.json`.",
           "- Ranking por NSE mediana (descriptivo): W de Kendall entre años "
           + ", ".join(f"h = {h}: {w['ranking'][f'h{h}']['kendall_w']}" for h in HS) + "."]
    if "pendiente" in w:
        out.append(f"- Pendiente: {w['pendiente']}.")
    else:
        out.append("- Robustez (veredicto anual contra el principal): "
                   + "; ".join([f"H1 {w['H1']['robustez']['robustez']}",
                                *(f"H1-b h = {h} {w['H1b']['robustez'][f'h{h}']['robustez']}" for h in HS),
                                *([f"H2-a {w['H2a']['robustez']['robustez']}", f"H2-b {w['H2b']['robustez']['robustez']}"]
                                  if "H2a" in w else []),
                                f"H3 (4 miembros) {w['H3']['robustez']['robustez']}"]) + ".")
        out.append("- H3 con 4 miembros en la partición principal (referencia): "
                   f"{w['H3']['referencia_principal_4_miembros']['veredicto']}.")
    out += ["", _md(tabs["T7_walk_forward"]), ""]
    return out


def report(nums: dict, tabs: dict[str, pd.DataFrame]) -> str:
    d, c, r1, r2, r3, v = (nums[k] for k in ("datos", "computo", "rq1", "rq2", "rq3", "veredictos"))
    a = r1["agregado"]
    ss = {h: {m: a[f"h{h}"][m]["ss_mediana"] for m in ORDER} for h in HS}
    fb, mech = r3["frontera_decision_difusa"]["valores"], r3["mecanismo"]["valores"]
    lines = [
        "# Reporte técnico · benchmark de arquitecturas, explicabilidad y alertas difusas",
        "",
        f"Generado por `scripts/xai_08_report.py` el {nums['generado']}. Todas las cifras vienen de "
        "`numbers.json`; cada bloque indica su fuente. Protocolo: `protocol.md` "
        f"(SHA-256 {'coincide' if nums['protocolo']['coincide_con_congelado'] else 'NO coincide'} con el congelado).",
        "",
        "> Pronósticos retrospectivos sobre 2023–2025; no es un sistema operativo.",
        "",
        "## 1. Veredictos",
        "",
        _md(tabs["T5_hipotesis"]),
        "",
        "## 2. Datos y diseño",
        "",
        f"- Snapshot {d['snapshot']}. {d['estaciones_modeladas']} estaciones modeladas en 4 cuencas piloto "
        f"({', '.join(f'{b}: {n}' for b, n in d['estaciones_por_cuenca'].items())}); "
        f"{len(d['fuera_de_unidad'])} fuera de toda unidad ({', '.join(d['fuera_de_unidad'])}).",
        f"- Estaciones evaluables en prueba: {d['evaluables']['h1']} por horizonte "
        f"(no evaluables: {', '.join(d['no_evaluables'])}).",
        "- Muestras (entrenamiento / validación / prueba): "
        + "; ".join(f"h = {h}: {m['train']:,} / {m['val']:,} / {m['test']:,}" for h, m in
                    zip(HS, d["muestras"].values(), strict=True)) + ".",
        "",
        "## 3. RQ1 · desempeño",
        "",
        "- Configuración elegida en validación: "
        + ", ".join(f"{k} → {val}" for k, val in r1["configuracion_elegida"].items()) + ".",
        "- Mejor mediana de NSE por horizonte: "
        + ", ".join(f"h = {h}: {LABEL[r1['mejor_por_nse_mediana'][f'h{h}']]}" for h in HS) + ".",
        f"- SS mediano contra persistencia a h = 1: ARIMA {ss[1]['arima']:.3f}, XGBoost {ss[1]['xgboost']:.3f}, "
        f"TCN {ss[1]['tcn']:.3f}, ConvNeXt-1D {ss[1]['convnext']:.3f}, PatchTST {ss[1]['patchtst']:.3f}.",
        f"- H1: {v['H1']}. Modelos con IC > 0: h = 7 → {r1['H1']['modelos_con_ic_positivo']['h7']}, "
        f"h = 14 → {r1['H1']['modelos_con_ic_positivo']['h14']}.",
        "- H1-b: " + ", ".join(f"{k}: {val}" for k, val in v["H1-b"].items()) + ". ΔNSE (profundo − XGBoost): "
        + ", ".join(f"{k} {_ci(val)}" for k, val in r1["H1b"]["ic_mediana_delta_nse"].items()) + ".",
        "- Descriptivo (no preregistrado), ΔNSE contra ARIMA: "
        + ", ".join(f"{k} {_ci(val)}" for k, val in r1["delta_nse_vs_arima"]["ic95"].items()) + ".",
        "- Descriptivo (no preregistrado), componentes del KGE a h = 1 (α = σ_sim/σ_obs; mediana y fracción "
        "de estaciones con α < 1): "
        + ", ".join(f"{LABEL[m]} α {x['alpha_mediana']:.3f} ({x['fraccion_alpha_lt_1']:.3f}), r {x['r_mediana']:.3f}"
                    for m, x in r1["kge_componentes"]["agregado"]["h1"].items() if m != "climatologia") + ".",
        "",
        _md(tabs["T1_rq1_agregado"]),
        "",
        _md(tabs["T1b_rq1_kge_componentes"]),
        "",
        "## 4. RQ2 · explicabilidad",
        "",
        f"- Muestra fija: hasta {r2['muestra']['max_ventanas']} ventanas por cuenca y horizonte, semilla "
        f"{r2['muestra']['semilla']}; IG con {r2['muestra']['ig_pasos']} pasos. Error de completitud de IG "
        "(mediana |δ|): " + ", ".join(f"{LABEL[m]} {x['mediana_abs']}" for m, x in r2["ig_error_completitud"].items())
        + ".",
        f"- H2-a: {v['H2-a']}. Fracción de combinaciones con Spearman ≥ 0.5: {r2['H2a']['fraccion_ge_0.5']}; "
        f"< 0.3: {r2['H2a']['fraccion_lt_0.3']}.",
        f"- H2-b: {v['H2-b']}. Proporción de pares en 1–3 días: {r2['H2b']['proporcion_1_3_dias']}.",
        "- Descriptivo: fracción de pares cuyo rezago más importante es el mínimo posible (= h, precipitación del "
        "día de emisión): " + ", ".join(f"{k} {val}" for k, val in r2["rezago_igual_al_minimo"]["fraccion_por_h"].items())
        + ". Con h = 1 el criterio de H2-b no distingue un efecto físico de un efecto de recencia.",
        "- Descriptivo: participación de la precipitación en la importancia total, h = 1: "
        + ", ".join(f"{LABEL[m]} {r2['participacion_canales']['valores'][f'{m}_h1']['precipitacion']}"
                    for m in LEARNED) + ".",
        "",
        _md(tabs["T3_rq2_concordancia_rezagos"]),
        "",
        "## 5. RQ3 · alertas difusas",
        "",
        f"- H3: {v['H3']} (variante pre-corrección: {v['H3_pre_correccion']}).",
        "- Corrección del 2026-10-10: el `TrapezoidalMF` copiado de forecasting daba pertenencia 0 en los hombros "
        "verticales (dispersión = 0, percentil = 1), así que esas muestras quedaban en nivel normal. Se corrigió para "
        "que implemente los trapecios del protocolo; ambas variantes se reportan (proof ledger).",
        f"- Frontera del sistema congelado: alerta desde el percentil {fb['dispersion_0.00']['percentil_min_alerta']} "
        f"con dispersión 0 y desde {fb['dispersion_0.30']['percentil_min_alerta']} con dispersión 0.30; emergencia "
        f"desde {fb['dispersion_0.00']['percentil_min_emergencia']} con dispersión 0.",
        "- Descriptivo, de dónde sale la diferencia (h = 1): "
        + "; ".join(f"{e}: {mech[f'{e}_h1_solo_umbral']['alarmas']} alarmas solo del umbral "
                    f"({mech[f'{e}_h1_solo_umbral']['dispersion_alta']} con dispersión alta, tasa de acierto "
                    f"{mech[f'{e}_h1_solo_umbral']['tasa_acierto']}) y {mech[f'{e}_h1_solo_difuso']['alarmas']} solo "
                    f"difusas (tasa de acierto {mech[f'{e}_h1_solo_difuso']['tasa_acierto']})" for e in ("P90", "P99"))
        + ". En P90 la ganancia viene de suprimir alarmas con miembros en desacuerdo; en P99, de la frontera de "
        "emergencia más baja que 0.99.",
        "",
        _md(tabs["T4_rq3_alertas"]),
        "",
        *walk_forward_section(nums, tabs),
        "## 7. Cómputo",
        "",
        f"- GPU ({', '.join(c['gpu']['dispositivo'])}, Kaggle): {c['gpu']['horas_total']} h en "
        f"{c['gpu']['corridas']} corridas del diseño principal y {c['gpu']['walk_forward']['horas']} h en "
        f"{c['gpu']['walk_forward']['corridas']} del walk-forward. CPU local: {c['cpu']['horas_total']} h en total "
        f"(presupuesto {c['presupuesto_cpu_h']} h).",
        "- Épocas de las redes (mediana; fracción con parada temprana): "
        + ", ".join(f"{LABEL[m]} {x['mediana']} ({x['parada_temprana_frac']})" for m, x in c["epocas_redes"].items())
        + ".",
        "",
        _md(tabs["T6_computo"]),
        "",
        "## 8. No realizado",
        "",
        *[f"- {x['item']}: {x['motivo']}" for x in nums["no_realizado"]],
        "",
        "## 9. Archivos",
        "",
        "- Figuras: `results/xai_benchmark/figures/` (PNG a 300 dpi y PDF).",
        "- Tablas: `results/xai_benchmark/tables/` (CSV y `tables.md`).",
        "- Cifras: `results/xai_benchmark/numbers.json`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    prof, kag = _json("sample_profile.json"), _json("kaggle_import.json")
    e1, e2, e3 = _json("e_rq1.json"), _json("e_rq2.json"), _json("e_rq3.json")
    pre = _json("rq3_pre_correccion/e_rq3.json")
    sm = pd.read_csv(OUT / "rq1_summary.csv")
    st = pd.read_csv(OUT / "rq1_station_metrics.csv", dtype={"clave": str})
    imp, conc = pd.read_csv(OUT / "rq2_importance.csv"), pd.read_csv(OUT / "rq2_concordance.csv")
    lags, igd = pd.read_csv(OUT / "rq2_top_precip_lag.csv"), pd.read_csv(OUT / "rq2_ig_delta.csv")
    att = pd.read_csv(OUT / "rq2_attention.csv")
    rs, pre_rs = pd.read_csv(OUT / "rq3_summary.csv"), pd.read_csv(OUT / "rq3_pre_correccion" / "rq3_summary.csv")
    ct = pd.read_csv(OUT / "rq3_contingency.csv", dtype={"clave": str})
    man = pd.read_csv(OUT / "compute_manifest.csv")
    big = e2["cuencas_con_inferencia"]

    sha = hashlib.sha256((OUT / "protocol.md").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    nums = {"proyecto": "HidroXAI-MX · IND-2026-0335 (IPN, PICDT 2026), OE2–OE5",
            "generado": date.today().isoformat(), "fuente": "scripts/xai_08_report.py",
            "protocolo": {"fuente": "results/xai_benchmark/protocol.md", "sha256": sha,
                          "coincide_con_congelado": sha == FROZEN_SHA},
            "datos": block_data(prof, e1, st), "computo": block_compute(man, kag),
            "rq1": block_rq1(e1, sm, st, big), "rq2": block_rq2(e2, imp, conc, lags, igd, att),
            "rq3": block_rq3(e3, pre, rs, pre_rs)}
    nums["veredictos"] = {"fuente": "e_rq1.json, e_rq2.json, e_rq3.json", "H1": e1["H1"]["veredicto"],
                          "H1-b": e1["H1b"]["veredicto"], "H2-a": e2["H2a"]["veredicto"],
                          "H2-b": e2["H2b"]["veredicto"], "H3": e3["H3"]["veredicto"],
                          "H3_pre_correccion": pre["H3"]["veredicto"]}
    nums["no_realizado"] = []
    ewf = _json("e_walkforward.json") if (OUT / "e_walkforward.json").exists() else None
    if ewf is None:
        nums["no_realizado"].append({"item": "Walk-forward anual (protocolo §3)",
                                     "motivo": "no corrido todavía; requiere reentrenar por año (redes en Kaggle)"})
    else:
        wfs = pd.read_csv(OUT / "wf_summary.csv")
        nums["walk_forward"] = block_walk_forward(ewf, wfs)
        if "pendiente" in ewf:
            nums["no_realizado"].append({"item": "Walk-forward anual, parte de redes", "motivo": ewf["pendiente"]})
        nums["veredictos"]["robustez_walk_forward"] = {
            k: (ewf[k]["robustez"]["robustez"] if k != "H1b" else
                {h: v["robustez"] for h, v in ewf[k]["robustez"].items()})
            for k in ("H1", "H1b", "H2a", "H2b", "H3") if k in ewf}
    nums["no_realizado"].append({"item": "Informer", "motivo": "fuera del diseño principal (protocolo §4)"})

    fig_rq1_skill(sm)
    fig_rq1_basins(sm)
    fig_rq1_delta(e1)
    fig_rq2_maps(imp, big)
    fig_rq2_concordance(conc, big)
    fig_rq2_precip(imp, big)
    fig_rq3_skill(rs, e3, pre)
    fig_rq3_surface()
    nums["figuras"] = {"fuente": "scripts/xai_08_report.py", "carpeta": "results/xai_benchmark/figures",
                       "estacion_ejemplo_fig9": fig_rq3_timeline(ct),
                       "regla_estacion_ejemplo": "estación de Lerma–Santiago con más eventos P90 observados a h = 1"}

    tabs = tables(nums, sm, conc, lags, rs, pre, e3)
    if ewf is not None:
        fig_walk_forward(wfs, ewf, e3)
        tabs.update(tables_walk_forward(ewf, wfs))
    for name, t in tabs.items():
        t.to_csv(TAB / f"{name}.csv", index=False)
    (TAB / "tables.md").write_text("\n\n".join(f"## {n}\n\n{_md(t)}" for n, t in tabs.items()) + "\n",
                                   encoding="utf-8")
    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "report.md").write_text(report(nums, tabs), encoding="utf-8")
    log.info("veredictos: %s", {k: v for k, v in nums["veredictos"].items() if k != "fuente"})


if __name__ == "__main__":
    main()

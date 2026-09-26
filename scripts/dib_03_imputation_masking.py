#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E3 — experimento de imputación por enmascaramiento.

Criterios congelados en results/dib_revision/proof_ledger.md (E3). Resumen:

- Universo: estaciones de estaciones_seleccionadas_hidrometricas.csv; verdad = valores
  calidad == 0 en 2010–2025.
- Serie base = la que veía el pipeline antes de imputar: gasto con calidad == 1 → NaN
  (los outliers, calidad == 2, se conservan como nodos, igual que en la etapa 04).
- Huecos artificiales de L = 1…10 días, ≥ 2,000 por L, repartidos por igual entre
  estaciones; cada hueco con ≥ 3 días observados a cada lado y separado ≥ 30 días de otro
  hueco de la misma estación.
- Métodos sobre el registro completo de la estación (como `clean.impute_short_gaps`):
  lineal, PCHIP y spline cúbico del pipeline (limit=7, limit_area="inside", respaldo lineal).
- Métricas por día enmascarado, normalizadas por la desviación estándar de la estación.

Salidas en results/dib_revision/:
    imputation_masking_summary.csv   método × L × subconjunto
    imputation_masking_gaps.csv      detalle por hueco (para auditoría)
    e3_imputation.json               global L=1–6, evaluación de las reglas, diagnóstico
                                     del dato publicado
    figs/figS_imputation_error_vs_L.{png,tif}

Uso:  python scripts/dib_03_imputation_masking.py [--seed 20260926]
"""
from __future__ import annotations

import json

import click
import numpy as np
import pandas as pd

from hidroxai_mx.utils import PROCESSED, ROOT, get_logger

log = get_logger("dib_03")
OUT = ROOT / "results" / "dib_revision"
T0, T1 = pd.Timestamp("2010-01-01"), pd.Timestamp("2025-12-31")
LS = range(1, 11)
N_PER_L = 2000
SIDE = 3
SEP = 30
MAX_GAP_PIPELINE = 7


def _pipeline_spline(s: pd.Series) -> pd.Series:
    """Copia literal de la lógica de `clean.impute_short_gaps` para una estación."""
    try:
        return s.interpolate(method="cubic", limit=MAX_GAP_PIPELINE, limit_area="inside")
    except (ValueError, TypeError):
        return s.interpolate(method="linear", limit=MAX_GAP_PIPELINE, limit_area="inside")


METHODS = {
    "lineal": lambda s: s.interpolate(method="linear", limit_area="inside"),
    "pchip": lambda s: s.interpolate(method="pchip", limit_area="inside"),
    "spline_pipeline": _pipeline_spline,
}


def _candidates(obs0: np.ndarray, inwin: np.ndarray, L: int) -> np.ndarray:
    """Inicios s tales que [s-3, s+L+3) son todos calidad==0 dentro de la ventana."""
    ok = (obs0 & inwin).astype(np.int32)
    w = L + 2 * SIDE
    if len(ok) < w:
        return np.array([], dtype=int)
    c = np.convolve(ok, np.ones(w, dtype=np.int32), mode="valid")  # c[i] = sum ok[i:i+w]
    starts = np.nonzero(c == w)[0] + SIDE
    return starts


def _pool(starts: np.ndarray, L: int, rng: np.random.Generator, cap: int = 400) -> list[int]:
    """Inicios en orden aleatorio, separados ≥ SEP días entre huecos (hasta `cap`)."""
    chosen: list[int] = []
    taken = np.array([], dtype=int)
    for s in rng.permutation(starts):
        if taken.size == 0 or np.min(np.abs(taken - s)) >= SEP + L:
            chosen.append(int(s))
            taken = np.append(taken, s)
            if len(chosen) == cap:
                break
    return chosen


def _allocate(pools: dict[str, list[int]], n: int) -> dict[str, list[int]]:
    """Reparto round-robin: una estación a la vez hasta completar n o agotar los pools."""
    picks = {k: [] for k in pools}
    pos = {k: 0 for k in pools}
    total, keys = 0, sorted(pools)
    while total < n:
        progressed = False
        for k in keys:
            if pos[k] < len(pools[k]) and total < n:
                picks[k].append(pools[k][pos[k]])
                pos[k] += 1
                total += 1
                progressed = True
        if not progressed:
            break
    return {k: sorted(v) for k, v in picks.items()}


def _published_diagnostics(df: pd.DataFrame) -> dict:
    """Rachas de calidad==1 en el dato publicado y si dejan hueco sin llenar detrás."""
    imp = (df["calidad"] == 1).to_numpy()
    nan = df["gasto_medio_m3s"].isna().to_numpy()
    key = df["clave_estacion"].to_numpy()
    new_run = imp & ~np.r_[False, imp[:-1] & (key[1:] == key[:-1])]
    run_id = np.cumsum(new_run) * imp
    runs = pd.DataFrame({"run": run_id[imp], "i": np.nonzero(imp)[0]}).groupby("run")["i"].agg(["min", "max"])
    lengths = (runs["max"] - runs["min"] + 1).to_numpy()
    nxt = runs["max"].to_numpy() + 1
    valid_next = nxt < len(df)
    partial = np.zeros(len(runs), bool)
    partial[valid_next] = nan[nxt[valid_next]] & (key[nxt[valid_next]] == key[runs["max"].to_numpy()[valid_next]])
    return {
        "dias_imputados": int(imp.sum()),
        "rachas_imputadas": int(len(runs)),
        "rachas_por_longitud": {int(k): int(v) for k, v in pd.Series(lengths).value_counts().sort_index().items()},
        "rachas_que_dejan_hueco_sin_llenar": int(partial.sum()),
        "dias_imputados_en_huecos_mayores_a_7": int(lengths[partial].sum()),
        "pct_dias_imputados_en_huecos_mayores_a_7": round(float(lengths[partial].sum() / imp.sum() * 100), 2),
        "imputados_negativos": int(((df["calidad"] == 1) & (df["gasto_medio_m3s"] < 0)).sum()),
    }


@click.command()
@click.option("--seed", type=int, default=20260926, show_default=True)
def main(seed: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figs").mkdir(exist_ok=True)
    rng = np.random.default_rng(seed)

    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})
    df = pd.read_parquet(PROCESSED / "series_hidrometricas.parquet",
                         columns=["clave_estacion", "fecha", "gasto_medio_m3s", "calidad"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["clave_estacion", "fecha"]).reset_index(drop=True)
    dups = int(df.duplicated(["clave_estacion", "fecha"]).sum())
    if dups:
        raise SystemExit(f"La serie tiene {dups} filas (clave, fecha) duplicadas; límpiala antes.")
    diag = _published_diagnostics(df)
    log.info("Diagnóstico del dato publicado: %s", diag)

    stations = {}
    for k, g in df[df["clave_estacion"].isin(set(sel["clave"]))].groupby("clave_estacion"):
        g = g.reset_index(drop=True)
        base = g["gasto_medio_m3s"].where(g["calidad"] != 1)
        obs0 = (g["calidad"] == 0).to_numpy() & base.notna().to_numpy()
        inwin = g["fecha"].between(T0, T1).to_numpy()
        truth = base[obs0 & inwin]
        sd = float(truth.std())
        if not np.isfinite(sd) or sd == 0:
            continue
        stations[k] = {"base": base, "obs0": obs0, "inwin": inwin, "sd": sd}
    log.info("Estaciones utilizables: %d de %d", len(stations), len(sel))

    gap_rows = []
    for L in LS:
        pools = {k: _pool(_candidates(v["obs0"], v["inwin"], L), L, rng)
                 for k, v in stations.items()}
        picks = _allocate(pools, N_PER_L)

        for k, starts in picks.items():
            if not starts:
                continue
            st = stations[k]
            masked = st["base"].copy()
            idx = np.concatenate([np.arange(s, s + L) for s in starts])
            truth = st["base"].to_numpy()[idx]
            masked.iloc[idx] = np.nan
            preds = {m: f(masked).to_numpy() for m, f in METHODS.items()}
            b = st["base"].to_numpy()
            for s in starts:
                before, after = b[s - 1], b[s + L]
                neigh = np.r_[b[s - SIDE:s], b[s + L:s + L + SIDE]]
                lo, hi = neigh.min(), neigh.max()
                rising = after > 1.5 * before
                t = b[s:s + L]
                for m, p in preds.items():
                    pv = p[s:s + L]
                    filled = ~np.isnan(pv)
                    gap_rows.append({
                        "L": L, "clave": k, "inicio": s, "metodo": m, "ascenso": bool(rising),
                        "n_dias": L, "n_llenos": int(filled.sum()),
                        "sq_err": float(np.nansum(((pv - t) / st["sd"]) ** 2)),
                        "abs_err": float(np.nansum(np.abs(pv - t) / st["sd"])),
                        "err": float(np.nansum((pv - t) / st["sd"])),
                        "sq_err_clip": float(np.nansum(((np.clip(pv, 0, None) - t) / st["sd"]) ** 2)),
                        "sobreoscila": int(np.sum(filled & ((pv < lo) | (pv > hi)))),
                        "negativos": int(np.sum(filled & (pv < 0))),
                    })
        log.info("L=%d: %d huecos en %d estaciones", L, sum(len(v) for v in picks.values()),
                 sum(1 for v in picks.values() if v))

    gaps = pd.DataFrame(gap_rows)
    gaps.to_csv(OUT / "imputation_masking_gaps.csv", index=False)

    def _agg(d: pd.DataFrame) -> pd.Series:
        n = d["n_llenos"].sum()
        return pd.Series({
            "n_huecos": len(d), "n_dias": int(d["n_dias"].sum()), "n_dias_llenos": int(n),
            "frac_llenado": n / d["n_dias"].sum(),
            "nMAE": d["abs_err"].sum() / n, "nRMSE": np.sqrt(d["sq_err"].sum() / n),
            "nRMSE_recorte0": np.sqrt(d["sq_err_clip"].sum() / n),
            "sesgo_norm": d["err"].sum() / n,
            "tasa_sobreoscilacion": d["sobreoscila"].sum() / n,
            "negativos": int(d["negativos"].sum()),
        })

    summ = []
    for subset, d in (("todos", gaps), ("ascensos", gaps[gaps["ascenso"]])):
        s = d.groupby(["metodo", "L"]).apply(_agg, include_groups=False).reset_index()
        s.insert(0, "subconjunto", subset)
        summ.append(s)
    summary = pd.concat(summ, ignore_index=True)
    summary.to_csv(OUT / "imputation_masking_summary.csv", index=False)

    glob = {}
    for subset, d in (("todos", gaps), ("ascensos", gaps[gaps["ascenso"]])):
        g16 = d[d["L"] <= 6]
        glob[subset] = {m: {k: (float(v) if isinstance(v, (float, np.floating)) else int(v))
                            for k, v in _agg(x).items()}
                        for m, x in g16.groupby("metodo")}
    best = min(v["nRMSE"] for v in glob["todos"].values())
    spl = glob["todos"]["spline_pipeline"]["nRMSE"]
    gate_a = spl <= 1.10 * best
    gate_b = diag["imputados_negativos"] == 0
    result = {
        "semilla": seed, "estaciones": len(stations),
        "huecos_por_L": gaps[gaps["metodo"] == "lineal"].groupby("L").size().to_dict(),
        "global_L1_6": glob,
        "regla_a": {"nRMSE_spline": spl, "mejor_nRMSE": best, "limite": 1.10 * best, "cumple": bool(gate_a)},
        "regla_b": {"imputados_negativos_publicados": diag["imputados_negativos"],
                    "negativos_spline_experimento_L1_6": glob["todos"]["spline_pipeline"]["negativos"],
                    "cumple": bool(gate_b)},
        "spline_se_sostiene": bool(gate_a and gate_b),
        "diagnostico_dato_publicado": diag,
    }
    (OUT / "e3_imputation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                            encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {"lineal": "Linear", "pchip": "PCHIP", "spline_pipeline": "Cubic spline (pipeline)"}
    colors = {"lineal": "#0072B2", "pchip": "#009E73", "spline_pipeline": "#D55E00"}
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), constrained_layout=True)
    for ax, (subset, col, ttl) in zip(axes, [("todos", "nRMSE", "(a) All gaps"),
                                               ("ascensos", "nRMSE", "(b) Rising-limb gaps"),
                                               ("todos", "tasa_sobreoscilacion", "(c) Overshoot rate")],
                                      strict=True):
        for m in METHODS:
            d = summary[(summary["subconjunto"] == subset) & (summary["metodo"] == m)]
            ax.plot(d["L"], d[col], marker="o", ms=3, color=colors[m], label=labels[m])
        ax.axvline(MAX_GAP_PIPELINE + 0.5, color="0.5", ls="--", lw=0.8)
        ax.set_xlabel("Gap length L (days)")
        ax.set_title(ttl, loc="left", fontsize=9)
        ax.set_xticks(list(LS))
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("RMSE / station SD")
    axes[1].set_ylabel("RMSE / station SD")
    axes[2].set_ylabel("Fraction outside neighbour range")
    axes[0].legend(fontsize=7, frameon=False)
    for ext in ("png", "tif"):
        fig.savefig(OUT / "figs" / f"figS_imputation_error_vs_L.{ext}", dpi=300,
                    **({"pil_kwargs": {"compression": "tiff_lzw"}} if ext == "tif" else {}))
    plt.close(fig)
    log.info("E3: spline se sostiene = %s (a=%s, b=%s)", result["spline_se_sostiene"], gate_a, gate_b)


if __name__ == "__main__":
    main()

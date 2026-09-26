#!/usr/bin/env python
"""Revisión DIB-D-26-01662 · E4 — auditoría de los valores marcados como outlier (calidad = 2).

Criterios congelados en results/dib_revision/proof_ledger.md (E4). Para cada registro
hidrométrico con calidad == 2 se reporta estación, fecha, valor, P99.9 local (calculado
igual que `clean.flag_outliers`: sobre todo el registro de la estación), razón
valor/P99.9, tipo (negativo o > 3 × P99.9) y dos evidencias internas de plausibilidad:

- ``razon_vecinos``: valor / máximo de los días t−1 y t+1 (pico aislado si ≫ 1);
- ``q_especifico_m3s_km2``: valor / área aportante de HydroRIVERS (estaciones_hidrorivers.csv).

También se verifica que todo registro marcado conserve su valor (no se elimina).

Salidas: results/dib_revision/outliers_hidro.csv, outliers_por_estacion.csv, e4_outliers.json,
         figs/figS_outliers_examples.{png,tif}
Uso:  python scripts/dib_04_outliers.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from hidroxai_mx.utils import PROCESSED, ROOT, get_logger

log = get_logger("dib_04")
OUT = ROOT / "results" / "dib_revision"
# Eventos documentados dentro del registro hidrométrico (termina el 2025-09-03, así que las
# inundaciones de octubre de 2025 no son evaluables). DOI verificado en Crossref.
EVENTS = [{
    "evento": "Inundaciones de septiembre de 2013 (Ingrid y Manuel)",
    "inicio": "2013-09-12", "fin": "2013-09-25",
    "referencia": "Pedrozo-Acuña, Breña-Naranjo & Domínguez-Mora (2014), Weather 69(11):295-302",
    "doi": "10.1002/wea.2355",
}]


def main() -> None:
    (OUT / "figs").mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PROCESSED / "series_hidrometricas.parquet",
                         columns=["clave_estacion", "fecha", "gasto_medio_m3s", "calidad"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["clave_estacion", "fecha"]).reset_index(drop=True)
    p999 = df.groupby("clave_estacion")["gasto_medio_m3s"].quantile(0.999).rename("p999_local")
    df["prev"] = df.groupby("clave_estacion")["gasto_medio_m3s"].shift(1)
    df["next"] = df.groupby("clave_estacion")["gasto_medio_m3s"].shift(-1)

    out = df[df["calidad"] == 2].merge(p999, left_on="clave_estacion", right_index=True)
    out["tipo"] = np.where(out["gasto_medio_m3s"] < 0, "negativo", "alto")
    out["razon_p999"] = out["gasto_medio_m3s"] / out["p999_local"]
    neigh = out[["prev", "next"]].max(axis=1)
    out["razon_vecinos"] = np.where(neigh > 0, out["gasto_medio_m3s"] / neigh, np.nan)
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    out = out.merge(link[["clave", "upland_km2"]], left_on="clave_estacion", right_on="clave", how="left")
    out["q_especifico_m3s_km2"] = out["gasto_medio_m3s"] / out["upland_km2"]
    sel = set(pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv", dtype={"clave": str})["clave"])
    out["en_conjunto_principal"] = out["clave_estacion"].isin(sel)
    cols = ["clave_estacion", "fecha", "gasto_medio_m3s", "tipo", "p999_local", "razon_p999", "prev",
            "next", "razon_vecinos", "upland_km2", "q_especifico_m3s_km2", "en_conjunto_principal"]
    out = out[cols].sort_values(["clave_estacion", "fecha"])
    out.to_csv(OUT / "outliers_hidro.csv", index=False)

    n_valid = df.groupby("clave_estacion")["gasto_medio_m3s"].count()
    per = out.groupby("clave_estacion").agg(n=("fecha", "size"),
                                            negativos=("tipo", lambda s: int((s == "negativo").sum())),
                                            altos=("tipo", lambda s: int((s == "alto").sum())))
    per["fraccion_de_dias_con_valor"] = per["n"] / n_valid.reindex(per.index)
    per = per.sort_values("n", ascending=False)
    per.to_csv(OUT / "outliers_por_estacion.csv")

    hi = out[out["tipo"] == "alto"]
    res = {
        "registros_calidad_2": int(len(out)),
        "con_valor_nulo": int(out["gasto_medio_m3s"].isna().sum()),
        "negativos": int((out["tipo"] == "negativo").sum()),
        "altos": int(len(hi)),
        "estaciones_con_marcas": int(len(per)),
        "estaciones_principales_con_marcas": int(out.loc[out["en_conjunto_principal"], "clave_estacion"].nunique()),
        "marcas_en_conjunto_principal": int(out["en_conjunto_principal"].sum()),
        "fraccion_max_por_estacion": float(per["fraccion_de_dias_con_valor"].max()),
        "altos_pico_aislado_razon_vecinos_gt_10": int((hi["razon_vecinos"] > 10).sum()),
        "altos_con_area_hydrorivers": int(hi["upland_km2"].notna().sum()),
        "altos_q_especifico_gt_10": int((hi["q_especifico_m3s_km2"] > 10).sum()),
        "valor_max": float(out["gasto_medio_m3s"].max()),
        "anios_de_altos": hi["fecha"].dt.year.value_counts().sort_index().to_dict(),
        "altos_2010_2025": int((hi["fecha"] >= "2010-01-01").sum()),
    }
    ev_rows = []
    for e in EVENTS:
        w = df[df["fecha"].between(e["inicio"], e["fin"]) & df["clave_estacion"].isin(sel)
               & df["gasto_medio_m3s"].notna()]
        pk = w.loc[w.groupby("clave_estacion")["gasto_medio_m3s"].idxmax()]
        pk = pk.merge(p999, left_on="clave_estacion", right_index=True)
        pk["pico_vs_p999"] = pk["gasto_medio_m3s"] / pk["p999_local"]
        pk = pk[pk["pico_vs_p999"] >= 1.0]
        for r in pk.itertuples():
            ev_rows.append({"evento": e["evento"], "doi": e["doi"], "clave_estacion": r.clave_estacion,
                            "fecha_pico": r.fecha.date(), "gasto_pico_m3s": r.gasto_medio_m3s,
                            "pico_vs_p999": round(r.pico_vs_p999, 2), "calidad": int(r.calidad)})
    evdf = pd.DataFrame(ev_rows)
    evdf.to_csv(OUT / "outliers_event_check.csv", index=False)
    res["eventos_documentados"] = [
        {"evento": e["evento"], "referencia": e["referencia"], "doi": e["doi"],
         "estaciones_con_pico_ge_p999": int((evdf["evento"] == e["evento"]).sum()),
         "picos_marcados_calidad_2": evdf.loc[(evdf["evento"] == e["evento"]) & (evdf["calidad"] == 2),
                                              "clave_estacion"].tolist()}
        for e in EVENTS]
    (OUT / "e4_outliers.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str),
                                          encoding="utf-8")
    log.info("E4: %s", res)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cand = per[per["altos"] > 0].index.intersection(sorted(sel))[:3].tolist() or per.index[:3].tolist()
    fig, axes = plt.subplots(len(cand), 1, figsize=(8, 2.4 * len(cand)), constrained_layout=True)
    for ax, k in zip(np.atleast_1d(axes), cand, strict=True):
        g = df[df["clave_estacion"] == k]
        m = g[g["calidad"] == 2]
        ax.plot(g["fecha"], g["gasto_medio_m3s"], lw=0.5, color="0.35", label="daily mean discharge")
        ax.scatter(m["fecha"], m["gasto_medio_m3s"], s=14, color="#D55E00", zorder=3,
                   label="flagged (quality = 2), retained")
        ax.axhline(3 * p999.loc[k], color="#0072B2", ls="--", lw=0.8, label="3 × local P99.9")
        ax.set_yscale("symlog", linthresh=1)
        ax.set_ylabel("m³ s⁻¹")
        ax.set_title(k, loc="left", fontsize=9)
    np.atleast_1d(axes)[0].legend(fontsize=7, frameon=False, loc="upper left")
    for ext in ("png", "tif"):
        fig.savefig(OUT / "figs" / f"figS_outliers_examples.{ext}", dpi=300,
                    **({"pil_kwargs": {"compression": "tiff_lzw"}} if ext == "tif" else {}))
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Análisis de validación del dataset (para el data paper / OE1).

Funciones puras (pandas/numpy) que alimentan el notebook de reporte de cobertura.
No incluyen modelado: solo describen y validan el dataset.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def station_inventory(df: pd.DataFrame, by: str = "region_hidrologica") -> pd.DataFrame:
    """Nº de estaciones únicas por agrupador (región/cuenca/estado)."""
    if by in df.columns:
        return (df.groupby(by)["clave_estacion"].nunique()
                .rename("n_estaciones").reset_index().sort_values("n_estaciones", ascending=False))
    return pd.DataFrame({"n_estaciones": [df["clave_estacion"].nunique()]})


def coverage_table(df: pd.DataFrame, value_col: str, group: str = "clave_estacion",
                   inicio: str | None = None, fin: str | None = None) -> pd.DataFrame:
    """% de días con dato (no NaN) por estación en el periodo dado."""
    d = df.copy()
    if inicio:
        d = d[d["fecha"] >= pd.Timestamp(inicio)]
    if fin:
        d = d[d["fecha"] <= pd.Timestamp(fin)]
    exp_fijo = (pd.Timestamp(fin) - pd.Timestamp(inicio)).days + 1 if (inicio and fin) else None
    rows = []
    for k, g in d.groupby(group):
        valid = int(g[value_col].notna().sum()) if value_col in g else 0
        exp = exp_fijo or ((g["fecha"].max() - g["fecha"].min()).days + 1)
        rows.append({group: k, "n_obs": valid, "dias_periodo": int(exp),
                     "cobertura": (valid / exp) if exp else np.nan,
                     "inicio": g["fecha"].min(), "fin": g["fecha"].max()})
    return pd.DataFrame(rows).sort_values("cobertura", ascending=False)


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Conteo y % de banderas de calidad (0=ok, 1=imputado, 2=outlier)."""
    counts = df["calidad"].value_counts().reindex([0, 1, 2]).fillna(0).astype(int)
    total = int(counts.sum()) or 1
    return pd.DataFrame({"calidad": [0, 1, 2], "etiqueta": ["ok", "imputado", "outlier"],
                         "n": counts.to_numpy(), "pct": counts.to_numpy() / total * 100})


def monthly_climatology(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Climatología mensual (media/desv/conteo) de una variable."""
    d = df.dropna(subset=[col]).copy()
    d["mes"] = d["fecha"].dt.month
    return d.groupby("mes")[col].agg(["mean", "std", "count"]).reset_index()


def annual_means(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df.dropna(subset=[col]).copy()
    d["anio"] = d["fecha"].dt.year
    return d.groupby("anio")[col].mean().reset_index()


def lagged_corr(df: pd.DataFrame, a: str, b: str, max_lag: int = 30,
                group: str = "clave_estacion") -> pd.Series:
    """Correlación media (entre estaciones) de a(t-lag) vs b(t) para lag=0..max_lag.

    Útil para verificar la respuesta hidrológica esperable precipitación -> gasto.
    """
    res = {}
    for lag in range(max_lag + 1):
        cs = []
        for _, g in df.groupby(group):
            g = g.sort_values("fecha")
            c = g[a].shift(lag).corr(g[b])
            if pd.notna(c):
                cs.append(c)
        res[lag] = float(np.mean(cs)) if cs else np.nan
    return pd.Series(res, name=f"corr_{a}(t-lag)_vs_{b}")


def cross_source_agreement(df_a: pd.DataFrame, df_b: pd.DataFrame, value_col: str,
                           group: str = "clave_estacion") -> pd.DataFrame:
    """Correlación y sesgo entre dos fuentes para estaciones en común (face validity)."""
    rows = []
    common = set(df_a[group]) & set(df_b[group])
    for k in common:
        a = df_a[df_a[group] == k].set_index("fecha")[value_col]
        b = df_b[df_b[group] == k].set_index("fecha")[value_col]
        j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
        if len(j) >= 10:
            rows.append({group: k, "n": len(j), "corr": j["a"].corr(j["b"]),
                         "sesgo": float((j["a"] - j["b"]).mean())})
    return pd.DataFrame(rows)

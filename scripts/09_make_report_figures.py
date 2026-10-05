#!/usr/bin/env python
"""Etapa 09 — Figuras y métricas del data paper (numeración del artículo).

Genera en data/processed/reportes/ (PNG a 300 dpi y TIFF-LZW a 600 dpi) y exporta metrics.json:

    Fig2_station_map           estaciones sobre límites nacional/estatales, regiones
                               hidrológicas 12, 18 y 26 y bbox de las unidades (EPSG:6372)
    Fig3_quality_flags         composición de la bandera de calidad (días con valor)
    Fig4_inventory_coverage    inventario por región y cobertura 2010–2025 (observaciones
                               originales, misma regla que la selección de estaciones)
    Fig5_streamflow_by_region  gasto diario por región (sin valores marcados como outlier)
    Fig6_climatology_annual    climatología mensual y media anual (sin outliers)
    Fig7_precip_streamflow     correlación rezagada Pearson/Spearman entre anomalías
                               desestacionalizadas de precipitación y gasto (agregado de
                               las regiones 12, 18 y 26); en gris, la curva sin desestacionalizar
    cobertura_por_estacion.csv, metrics.json

La Fig. 1 (flujo de trabajo) la genera scripts/12_make_workflow_figure.py.

Capas externas para la Fig. 2 (no se versionan; ver conf/sources.yaml):
    data/scratch/limites/ne_10m_admin_1/  Natural Earth 10m admin-1 (dominio público)
    data/scratch/limites/rh250kgw/        CONAGUA (2007) Regiones Hidrológicas 1:250 000,
                                          distribuido por CONABIO
    data/scratch/limites/cue250kgw/       CNA (1998) Cuencas Hidrológicas 1:250 000, distribuido
                                          por CONABIO (contornos de cuencas piloto declarados en
                                          conf/cuencas_piloto.yaml: contornos_cuencas_piloto)

Uso:  python scripts/09_make_report_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.dataset as pa_ds

from hidroxai_mx import report
from hidroxai_mx.io import conagua
from hidroxai_mx.utils import DATA, PROCESSED, RAW, get_logger, load_cuencas

log = get_logger("09_report")
OUT = PROCESSED / "reportes"
OUT.mkdir(parents=True, exist_ok=True)
LIMITES = DATA / "scratch" / "limites"
CRS_MAP = "EPSG:6372"
T0, T1 = "2010-01-01", "2025-12-31"
RH_COLORS = {"12": "#1F3D5C", "18": "#7A1737", "26": "#2E7D5B"}
RH_NAMES = {"12": "Lerma–Santiago", "18": "Balsas", "26": "Pánuco"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.titlesize": 11, "axes.labelsize": 10,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
})


TIF_DPI = 600  # ancho ≥ 2244 px a página completa (190 mm) en todas las figuras


def _save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.png")
    fig.savefig(OUT / f"{name}.tif", dpi=TIF_DPI, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
    log.info("%s OK", name)


def load_partitioned(path: Path, columns=None) -> pd.DataFrame:
    return pa_ds.dataset(path, format="parquet", partitioning="hive").to_table(columns=columns).to_pandas()


def attach_catalog(df: pd.DataFrame, catalog_path: Path) -> pd.DataFrame:
    cat = conagua.read_catalog(catalog_path).rename(columns={"clave": "clave_estacion"})
    return df.merge(cat[["clave_estacion", "latitud", "longitud", "region_hidrologica", "estado"]],
                    on="clave_estacion", how="left")


# --------------------------------------------------------------------------- #
def fig2_station_map(metrics: dict) -> None:
    import geopandas as gpd
    from shapely.geometry import box

    states = gpd.read_file(LIMITES / "ne_10m_admin_1" / "ne_10m_admin_1_states_provinces.shp")
    states = states[states["admin"] == "Mexico"].to_crs(CRS_MAP)
    nation = states.dissolve()
    rh = gpd.read_file(LIMITES / "rh250kgw" / "rh250kgw.shp")
    rh["clave_rh"] = rh["CLAVE"].astype(int).astype(str)
    rh = rh[rh["clave_rh"].isin(RH_COLORS)].dissolve(by="clave_rh").reset_index().to_crs(CRS_MAP)
    cfg = load_cuencas()
    units = gpd.GeoDataFrame({"nombre": [c["nombre"] for c in cfg["cuencas_piloto"]]},
                             geometry=[box(*c["bbox"]).segmentize(0.02) for c in cfg["cuencas_piloto"]],
                             crs="EPSG:4326").to_crs(CRS_MAP)
    # Contornos oficiales de cuencas piloto con correspondencia inequívoca por nombre de cuenca
    # (Lerma–Santiago y Pánuco coinciden con las regiones 12 y 26, ya dibujadas).
    oficiales = [n for e in cfg.get("contornos_cuencas_piloto", []) for n in e.get("cuencas_oficiales", [])]
    cuencas = gpd.read_file(LIMITES / "cue250kgw" / "cue250kgw.shp")
    cuencas = cuencas[cuencas["CUENCA"].isin(oficiales)].dissolve(by="CUENCA").reset_index().to_crs(CRS_MAP)
    cand = pd.read_csv(PROCESSED / "estaciones_candidatas_hidrometricas.csv", dtype={"clave": str})
    downloaded = {p.stem for p in (RAW / "sih_series" / "hidrometricas").glob("*.csv")}
    cand = cand[cand["clave"].isin(downloaded)]
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv",
                      dtype={"clave": str, "region_hidrologica": str})

    def pts(d):
        return gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d["longitud"], d["latitud"]),
                                crs="EPSG:4326").to_crs(CRS_MAP)

    fig, ax = plt.subplots(figsize=(8.0, 6.6))
    for k, g in rh.groupby("clave_rh"):
        g.plot(ax=ax, color=RH_COLORS[k], alpha=0.10, edgecolor="none")
        g.boundary.plot(ax=ax, color=RH_COLORS[k], linewidth=1.2,
                        label=f"Hydrological region {k} ({RH_NAMES[k]})")
    states.boundary.plot(ax=ax, color="0.55", linewidth=0.4)
    nation.boundary.plot(ax=ax, color="0.15", linewidth=0.9)
    for c in cuencas.itertuples():
        gpd.GeoSeries([c.geometry], crs=CRS_MAP).boundary.plot(
            ax=ax, color="#C9971B", linewidth=1.3, linestyle="-.",
            label=f"Pilot basin outline: {c.CUENCA} (CNA, 1998)")
    units.boundary.plot(ax=ax, color="black", linewidth=0.7, linestyle="--",
                        label="Operational units (curated bounding boxes)")
    pts(cand).plot(ax=ax, color="0.72", markersize=5, zorder=3,
                   label=f"Hydrometric stations downloaded (n = {len(cand)})")
    for k, g in sel.groupby("region_hidrologica"):
        pts(g).plot(ax=ax, color=RH_COLORS.get(k, "black"), markersize=12, edgecolor="white",
                    linewidth=0.3, zorder=4,
                    label=f"Selected stations, coverage ≥ 0.60, RH {k} (n = {len(g)})")
    # Etiqueta de cada unidad en una esquina de su bbox que no choque con las vecinas.
    corner = {"Cutzamala": ("left", "bottom"), "Lerma Alto": ("right", "top"),
              "Alta del Balsas": ("right", "bottom")}
    for u in units.itertuples():
        x0, y0, x1, y1 = u.geometry.bounds
        hx, vy = corner.get(u.nombre, ("left", "top"))
        ax.annotate(u.nombre.replace("Bajio", "Bajío").replace("Panuco", "Pánuco"),
                    (x0 if hx == "left" else x1, y1 if vy == "top" else y0),
                    xytext=(2 if hx == "left" else -2, -8 if vy == "top" else 3),
                    textcoords="offset points", fontsize=6.5, ha=hx,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))
    xmin, ymin, xmax, ymax = pd.concat([rh.geometry, units.geometry]).total_bounds
    pad = 60_000
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    inset = ax.inset_axes([0.005, 0.765, 0.26, 0.23])
    nation.plot(ax=inset, color="0.9", edgecolor="0.3", linewidth=0.4)
    inset.add_patch(plt.Rectangle((xmin - pad, ymin - pad), xmax - xmin + 2 * pad, ymax - ymin + 2 * pad,
                                  fill=False, color="red", linewidth=0.8))
    inset.set_xticks([])
    inset.set_yticks([])
    # geopandas ≥ 1.2 rotula los ejes con el CRS al dibujar; se fijan aquí para que la
    # figura no dependa de la versión instalada.
    inset.set_xlabel("")
    inset.set_ylabel("")
    ax.set_xlabel("Easting (m, EPSG:6372)", fontsize=plt.rcParams["axes.labelsize"])
    ax.set_ylabel("Northing (m, EPSG:6372)", fontsize=plt.rcParams["axes.labelsize"])
    ax.ticklabel_format(style="plain")
    ax.tick_params(labelsize=7)
    ax.legend(loc="lower left", fontsize=6.5, frameon=True)
    _save(fig, "Fig2_station_map")
    metrics["fig2"] = {"estaciones_descargadas": int(len(cand)), "estaciones_seleccionadas": int(len(sel)),
                       "seleccionadas_por_rh": sel["region_hidrologica"].value_counts().sort_index().to_dict(),
                       "contornos_cuencas_piloto": cuencas["CUENCA"].tolist(), "crs": CRS_MAP}


def fig3_quality(hid: pd.DataFrame, metrics: dict) -> None:
    q = report.quality_summary(hid, "gasto_medio_m3s")
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    bars = ax.bar(["original", "imputed", "flagged outlier"], q["pct"],
                  color=["#2E7D5B", "#C9971B", "#B23A48"], edgecolor="white")
    for b, n, p in zip(bars, q["n"], q["pct"], strict=True):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{int(n):,}\n({p:.3f} %)",
                ha="center", fontsize=7)
    ax.set_ylabel("% of daily values")
    ax.set_ylim(0, 115)
    _save(fig, "Fig3_quality_flags")
    metrics["fig3"] = {"ambito": "dias con valor de gasto", **q.set_index("etiqueta")[["n", "pct"]].round(4).to_dict()}


def fig4_inventory_coverage(hid: pd.DataFrame, metrics: dict) -> None:
    inv = report.station_inventory(hid, by="region_hidrologica")
    orig = hid.assign(v=hid["gasto_medio_m3s"].where(hid["calidad"] != 1))
    cov = report.coverage_table(orig, "v", inicio=T0, fin=T1)
    cov.to_csv(OUT / "cobertura_por_estacion.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].bar(inv["region_hidrologica"].astype(str), inv["n_estaciones"], color="#7A1737")
    ax[0].set_xlabel("Hydrological region")
    ax[0].set_ylabel("Number of stations")
    for i, v in enumerate(inv["n_estaciones"]):
        ax[0].text(i, v + 2, str(int(v)), ha="center", fontsize=8)
    ax[1].hist(cov["cobertura"] * 100, bins=20, color="#1F3D5C", edgecolor="white")
    ax[1].axvline(60, color="orange", ls="--", label="selection threshold (60 %)")
    ax[1].set_xlabel("Coverage 2010–2025 (% of days with an original observation)")
    ax[1].set_ylabel("Number of stations")
    ax[1].legend()
    ax[0].set_title("(a)", loc="left")
    ax[1].set_title("(b)", loc="left")
    plt.tight_layout()
    _save(fig, "Fig4_inventory_coverage")
    metrics["fig4"] = {
        "inventario_por_rh": inv.set_index("region_hidrologica")["n_estaciones"].to_dict(),
        "cobertura_media_pct": round(float(cov["cobertura"].mean() * 100), 2),
        "cobertura_mediana_pct": round(float(cov["cobertura"].median() * 100), 2),
        "estaciones_ge_60pct": int((cov["cobertura"] >= 0.60).sum()),
        "n_estaciones_total": int(len(cov)),
    }


def fig5_streamflow_by_region(hid: pd.DataFrame, metrics: dict) -> None:
    d = hid[(hid["calidad"] != 2)].dropna(subset=["gasto_medio_m3s"])
    rhs = sorted(d["region_hidrologica"].dropna().unique())
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    bp = ax.boxplot([d.loc[d["region_hidrologica"] == r, "gasto_medio_m3s"].clip(lower=1e-3).values
                     for r in rhs], tick_labels=[f"RH {r}" for r in rhs], showfliers=False, patch_artist=True)
    for b, r in zip(bp["boxes"], rhs, strict=True):
        b.set(facecolor=RH_COLORS.get(str(r), "0.5"), alpha=0.5)
    ax.set_yscale("log")
    ax.set_ylabel("Daily mean streamflow (m³ s⁻¹, log scale)")
    ax.set_xlabel("Hydrological region")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, "Fig5_streamflow_by_region")
    metrics["fig5"] = {"describe_sin_outliers": d["gasto_medio_m3s"].describe().round(3).to_dict()}


def fig6_climatology_annual(hid: pd.DataFrame, metrics: dict) -> None:
    d = hid[hid["calidad"] != 2]
    mc = report.monthly_climatology(d, "gasto_medio_m3s")
    an = report.annual_means(d, "gasto_medio_m3s")
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].plot(mc["mes"], mc["mean"], marker="o", color="#1F3D5C")
    ax[0].set_xlabel("Month")
    ax[0].set_ylabel("Mean daily streamflow (m³ s⁻¹)")
    ax[0].set_xticks(range(1, 13))
    ax[0].grid(alpha=0.3)
    ax[1].plot(an["anio"], an["gasto_medio_m3s"], marker="o", ms=3, color="#7A1737")
    for yr in (2011, 2021, 2023):
        ax[1].axvline(yr, color="gray", alpha=0.4, ls=":")
    ax[1].set_xlabel("Year")
    ax[1].set_ylabel("Annual mean (m³ s⁻¹)")
    ax[1].grid(alpha=0.3)
    ax[0].set_title("(a)", loc="left")
    ax[1].set_title("(b)", loc="left")
    plt.tight_layout()
    _save(fig, "Fig6_climatology_annual")
    metrics["fig6"] = {"climatologia_mensual": mc.set_index("mes")["mean"].round(2).to_dict()}


def fig7_precip_streamflow(hid: pd.DataFrame, cli: pd.DataFrame, metrics: dict) -> None:
    q = hid[hid["calidad"] == 0]
    p = cli[cli["calidad"] != 2]
    qa = report.deseasonalized_anomalies(q, "gasto_medio_m3s", inicio=T0, fin=T1)
    pa = report.deseasonalized_anomalies(p, "precip_mm", inicio=T0, fin=T1)
    q_idx = qa.groupby("fecha")["anomalia"].mean()
    p_idx = pa.groupby("fecha")["anomalia"].mean()
    des = report.regional_lag_correlation(p_idx, q_idx, max_lag=30)

    def zraw(df, col):
        w = df[(df["fecha"] >= T0) & (df["fecha"] <= T1)].dropna(subset=[col])
        z = (w[col] - w.groupby("clave_estacion")[col].transform("mean")) / \
            w.groupby("clave_estacion")[col].transform("std")
        return z.groupby(w["fecha"]).mean()

    raw = report.regional_lag_correlation(zraw(p, "precip_mm"), zraw(q, "gasto_medio_m3s"), max_lag=30)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(raw["lag"], raw["pearson"], color="0.7", lw=1, label="Pearson, raw standardized series")
    ax.plot(des["lag"], des["pearson"], marker="o", ms=3, color="#2E7D5B", label="Pearson, deseasonalized anomalies")
    ax.plot(des["lag"], des["spearman"], marker="s", ms=3, color="#C9971B", label="Spearman, deseasonalized anomalies")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("Lag (days): precipitation(t − lag) vs streamflow(t)")
    ax.set_ylabel("Correlation")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, "Fig7_precip_streamflow")
    des.assign(pearson_crudo=raw["pearson"], spearman_crudo=raw["spearman"]).to_csv(
        OUT / "precip_streamflow_lagcorr.csv", index=False)
    metrics["fig7"] = {
        "agregado": "regiones hidrologicas 12, 18 y 26", "ventana": [T0, T1],
        "estaciones_gasto": int(qa["clave_estacion"].nunique()),
        "estaciones_precip": int(pa["clave_estacion"].nunique()),
        "lag_max_pearson": int(des.loc[des["pearson"].idxmax(), "lag"]),
        "pearson_max": round(float(des["pearson"].max()), 3),
        "lag_max_spearman": int(des.loc[des["spearman"].idxmax(), "lag"]),
        "spearman_max": round(float(des["spearman"].max()), 3),
        "lag_max_pearson_crudo": int(raw.loc[raw["pearson"].idxmax(), "lag"]),
        "pearson_max_crudo": round(float(raw["pearson"].max()), 3),
    }


def main() -> None:
    metrics: dict = {}
    hid = load_partitioned(PROCESSED / "series_hidrometricas.parquet",
                           columns=["clave_estacion", "fecha", "gasto_medio_m3s", "calidad"])
    hid["fecha"] = pd.to_datetime(hid["fecha"])
    hid = attach_catalog(hid, RAW / "sih" / "catalogo_hidrometricas.csv")
    cli = load_partitioned(PROCESSED / "series_climatologicas.parquet",
                           columns=["clave_estacion", "fecha", "precip_mm", "calidad"])
    cli["fecha"] = pd.to_datetime(cli["fecha"])
    metrics["dataset"] = {
        t: {"n_estaciones": int(d["clave_estacion"].nunique()), "n_filas": int(len(d)),
            "fecha_min": str(d["fecha"].min().date()), "fecha_max": str(d["fecha"].max().date())}
        for t, d in (("hidrometricas", hid), ("climatologicas", cli))}

    fig2_station_map(metrics)
    fig3_quality(hid, metrics)
    fig4_inventory_coverage(hid, metrics)
    fig5_streamflow_by_region(hid, metrics)
    fig6_climatology_annual(hid, metrics)
    fig7_precip_streamflow(hid, cli, metrics)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
                                      encoding="utf-8")
    log.info("Métricas -> %s", OUT / "metrics.json")


if __name__ == "__main__":
    main()

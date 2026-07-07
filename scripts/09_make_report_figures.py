#!/usr/bin/env python
"""Etapa 09 — Figuras y métricas del reporte de cobertura para el data paper.

Ejecuta las funciones de hidroxai_mx.report sobre los Parquet reales (no demo),
joinea con el catálogo SIH para agregar lat/lon/RH, y guarda figuras a 300 DPI en
data/processed/reportes/. También exporta data/processed/reportes/metrics.json
con números listos para citarse en el manuscrito.

Salidas (todas a 300 dpi, formato PNG):
    fig1_inventario_cobertura.png
    fig2_descriptiva.png
    fig3_calidad.png
    fig5_mapa.png
    fig6_temporal.png
    fig7_precip_gasto.png
    fig8_cuencas_subcuencas.png  (NUEVA: mapa de las 6 cuencas + subcuencas delineadas)
    metrics.json
    cobertura_por_estacion.csv

Uso:  python scripts/09_make_report_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.dataset as pa_ds

from hidroxai_mx import report
from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, RAW, get_logger

log = get_logger("09_report")
OUT = PROCESSED / "reportes"
OUT.mkdir(parents=True, exist_ok=True)

DPI = 300
BBOX = "tight"
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
    "savefig.bbox": BBOX,
})


# --------------------------------------------------------------------------- #
# Carga de Parquet particionado y joins con catálogo
# --------------------------------------------------------------------------- #
def load_partitioned(path: Path) -> pd.DataFrame:
    """Lee un Parquet particionado por año (hive)."""
    ds = pa_ds.dataset(path, format="parquet", partitioning="hive")
    return ds.to_table().to_pandas()


def attach_catalog(df: pd.DataFrame, catalog_path: Path) -> pd.DataFrame:
    """Añade latitud, longitud, region_hidrologica y estado al DF de series."""
    cat = conagua.read_catalog(catalog_path)
    cat = cat.rename(columns={"clave": "clave_estacion"})[
        ["clave_estacion", "latitud", "longitud", "region_hidrologica", "estado"]
    ]
    return df.merge(cat, on="clave_estacion", how="left")


# --------------------------------------------------------------------------- #
# Figuras 1-7 (versión 300 dpi del notebook 02)
# --------------------------------------------------------------------------- #
def fig1_inventario_cobertura(hid: pd.DataFrame, metrics: dict) -> None:
    inv = report.station_inventory(hid, by="region_hidrologica")
    cov = report.coverage_table(hid, "gasto_medio_m3s", inicio="2010-01-01", fin="2025-12-31")
    cov.to_csv(OUT / "cobertura_por_estacion.csv", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].bar(inv["region_hidrologica"].astype(str), inv["n_estaciones"], color="#7A1737")
    ax[0].set_title("Hydrometric stations per hydrological region")
    ax[0].set_xlabel("Hydrological region")
    ax[0].set_ylabel("Number of stations")
    for i, v in enumerate(inv["n_estaciones"]):
        ax[0].text(i, v + 0.5, str(int(v)), ha="center", fontsize=8)
    ax[1].hist(cov["cobertura"] * 100, bins=20, color="#1F3D5C", edgecolor="white")
    ax[1].axvline(60, color="orange", ls="--", label="hydro threshold (0.60)")
    ax[1].axvline(80, color="red", ls="--", label="climate threshold (0.80)")
    ax[1].set_title("Coverage distribution (2010–2025)")
    ax[1].set_xlabel("Coverage (%)")
    ax[1].set_ylabel("Number of stations")
    ax[1].legend()
    plt.tight_layout()
    plt.savefig(OUT / "fig1_inventario_cobertura.png")
    plt.close(fig)

    metrics["fig1"] = {
        "inventario_por_rh": inv.set_index("region_hidrologica")["n_estaciones"].to_dict(),
        "cobertura_media_pct": float(cov["cobertura"].mean() * 100),
        "estaciones_ge_60pct": int((cov["cobertura"] >= 0.60).sum()),
        "estaciones_ge_80pct": int((cov["cobertura"] >= 0.80).sum()),
        "n_estaciones_total": int(len(cov)),
    }
    log.info("Fig.1 OK")


def fig2_descriptiva(hid: pd.DataFrame, metrics: dict) -> None:
    d = hid.dropna(subset=["gasto_medio_m3s"]).copy()
    d["temporada"] = np.where(d["fecha"].dt.month.isin([5, 6, 7, 8, 9, 10]), "lluviosa", "seca")
    rh_groups = sorted(d["region_hidrologica"].dropna().unique())
    grupos = [d[d["region_hidrologica"] == rh]["gasto_medio_m3s"].values for rh in rh_groups]

    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    bp = ax.boxplot(grupos, tick_labels=[f"RH {r}" for r in rh_groups], showfliers=False, patch_artist=True)
    for box in bp["boxes"]:
        box.set(facecolor="#1F3D5C", alpha=0.5)
    ax.set_yscale("log")
    ax.set_title("Daily mean streamflow by hydrological region (log scale)")
    ax.set_ylabel("Streamflow (m³/s, log)")
    ax.set_xlabel("Hydrological region")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / "fig2_descriptiva.png")
    plt.close(fig)

    season_stats = d.groupby("temporada")["gasto_medio_m3s"].agg(["mean", "median", "max"])
    metrics["fig2"] = {
        "describe_global": hid["gasto_medio_m3s"].describe().round(2).to_dict(),
        "por_temporada": season_stats.round(2).to_dict(),
    }
    log.info("Fig.2 OK")


def fig3_calidad(hid: pd.DataFrame, metrics: dict) -> None:
    q = report.quality_summary(hid)
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    colors = ["#2E7D5B", "#C9971B", "#B23A48"]
    bars = ax.bar(q["etiqueta"], q["pct"], color=colors, edgecolor="white")
    for b, n in zip(bars, q["n"]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5, f"{int(n):,}", ha="center", fontsize=8)
    ax.set_ylabel("% of observations")
    ax.set_title("Distribution of quality flags")
    ax.set_ylim(0, 100)
    plt.tight_layout()
    plt.savefig(OUT / "fig3_calidad.png")
    plt.close(fig)
    metrics["fig3"] = q.set_index("etiqueta")[["n", "pct"]].round(3).to_dict()
    log.info("Fig.3 OK")


def fig5_mapa(hid: pd.DataFrame, metrics: dict) -> None:
    if not {"latitud", "longitud"}.issubset(hid.columns):
        log.warning("Sin lat/lon: omito Fig.5")
        return
    pts = hid.drop_duplicates("clave_estacion").dropna(subset=["latitud", "longitud"])
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    palette = {"12": "#1F3D5C", "18": "#7A1737", "26": "#2E7D5B"}
    for rh, g in pts.groupby("region_hidrologica"):
        ax.scatter(g["longitud"], g["latitud"], s=14, alpha=0.7,
                   c=palette.get(str(rh), "gray"),
                   label=f"RH {rh} (n={len(g)})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Location of selected hydrometric stations")
    ax.legend(loc="lower left")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / "fig5_mapa.png")
    plt.close(fig)
    metrics["fig5"] = {"n_estaciones_geolocalizadas": int(len(pts))}
    log.info("Fig.5 OK")


def fig6_temporal(hid: pd.DataFrame, metrics: dict) -> None:
    mc = report.monthly_climatology(hid, "gasto_medio_m3s")
    an = report.annual_means(hid, "gasto_medio_m3s")
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].plot(mc["mes"], mc["mean"], marker="o", color="#1F3D5C")
    ax[0].fill_between(mc["mes"], mc["mean"] - mc["std"], mc["mean"] + mc["std"],
                       alpha=0.2, color="#1F3D5C")
    ax[0].set_title("Monthly streamflow climatology")
    ax[0].set_xlabel("Month")
    ax[0].set_ylabel("Streamflow (m³/s, mean ± 1σ)")
    ax[0].set_xticks(range(1, 13))
    ax[0].grid(alpha=0.3)
    ax[1].plot(an["anio"], an["gasto_medio_m3s"], marker="o", color="#7A1737")
    for yr in (2011, 2021, 2023):
        if yr in an["anio"].values:
            ax[1].axvline(yr, color="gray", alpha=0.4, ls=":")
    ax[1].set_title("Annual mean streamflow (dotted lines mark 2011, 2021, 2023)")
    ax[1].set_xlabel("Year")
    ax[1].set_ylabel("m³/s")
    ax[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / "fig6_temporal.png")
    plt.close(fig)
    metrics["fig6"] = {
        "climatologia_mensual": mc.set_index("mes")["mean"].round(2).to_dict(),
        "media_anual": an.set_index("anio")["gasto_medio_m3s"].round(2).to_dict(),
    }
    log.info("Fig.6 OK")


def fig7_precip_gasto(hid: pd.DataFrame, cli: pd.DataFrame, metrics: dict) -> None:
    """Correlación rezagada precip vs gasto. Como cada parquet vive por separado,
    usamos la precipitación media diaria de TODAS las estaciones de clima como
    una serie agregada por fecha y la correlacionamos con el gasto medio diario
    nacional. Resultado: relación física esperable precip→gasto."""
    if cli.empty or "precip_mm" not in cli.columns:
        log.warning("Sin precip_mm en clima: omito Fig.7")
        return
    precip_diaria = cli.dropna(subset=["precip_mm"]).groupby("fecha")["precip_mm"].mean()
    gasto_diario = hid.dropna(subset=["gasto_medio_m3s"]).groupby("fecha")["gasto_medio_m3s"].mean()
    merged = pd.concat([precip_diaria.rename("precip"), gasto_diario.rename("gasto")], axis=1).dropna()
    if len(merged) < 30:
        log.warning("Pocas fechas comunes precip/gasto: omito Fig.7")
        return

    lags = range(0, 16)
    cors = [merged["precip"].shift(L).corr(merged["gasto"]) for L in lags]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(list(lags), cors, marker="o", color="#2E7D5B")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Correlation")
    ax.set_title("Lagged correlation: precipitation(t−lag) vs streamflow(t) — national aggregates")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT / "fig7_precip_gasto.png")
    plt.close(fig)

    max_lag = int(np.nanargmax(cors))
    metrics["fig7"] = {
        "lag_max_correlacion_dias": max_lag,
        "correlacion_max": float(np.nanmax(cors)),
        "n_fechas_comunes": int(len(merged)),
    }
    log.info("Fig.7 OK (lag máx = %d días, corr = %.3f)", max_lag, np.nanmax(cors))


# --------------------------------------------------------------------------- #
# Figura nueva: mapa de cuencas + subcuencas + estaciones
# --------------------------------------------------------------------------- #
def fig8_basin_map(metrics: dict) -> None:
    try:
        import geopandas as gpd
    except Exception:
        log.warning("geopandas no disponible: omito Fig.8")
        return
    import yaml
    cuencas_dir = PROCESSED / "cuencas"
    gpkgs = sorted(cuencas_dir.glob("*.gpkg"))
    if not gpkgs:
        log.warning("Sin GeoPackages en %s: omito Fig.8", cuencas_dir)
        return

    cfg = yaml.safe_load(Path("conf/cuencas_piloto.yaml").read_text(encoding="utf-8"))
    bbox_por_nombre = {c["nombre"]: c.get("bbox") for c in cfg.get("cuencas_piloto", []) if c.get("bbox")}

    # Cuenca slug -> nombre legible (para leyenda)
    slug_a_nombre = {
        "cutzamala": "Cutzamala",
        "lerma_alto": "Lerma Alto",
        "bajio": "Bajío",
        "santiago": "Santiago",
        "panuco": "Pánuco",
        "alta_del_balsas": "Alta del Balsas",
    }
    colors = {
        "Cutzamala": "#7A1737",
        "Lerma Alto": "#1F3D5C",
        "Bajío": "#2E7D5B",
        "Santiago": "#C9971B",
        "Pánuco": "#5B3A8C",
        "Alta del Balsas": "#B23A48",
    }

    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    subbasin_count = {}
    for g in gpkgs:
        slug = g.stem
        nombre = slug_a_nombre.get(slug, slug)
        gdf = gpd.read_file(g)
        subbasin_count[nombre] = len(gdf)
        try:
            # Si shapely se queja por topología, reparar antes de plotear.
            gdf["geometry"] = gdf.geometry.buffer(0)
        except Exception:
            pass
        # Reproyectar a lat/lon para que coincida con bboxes/estaciones.
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf.boundary.plot(ax=ax, color=colors.get(nombre, "gray"), linewidth=0.8)
        # Centro del label = punto medio del bounding box de toda la cuenca.
        minx, miny, maxx, maxy = gdf.total_bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        ax.annotate(f"{nombre}\n({len(gdf)} subcuencas)", (cx, cy),
                    ha="center", fontsize=8, fontweight="bold",
                    color=colors.get(nombre, "black"),
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=colors.get(nombre, "gray"), alpha=0.85))

    # Bboxes curados como rectángulos punteados
    from matplotlib.patches import Rectangle
    for nombre, bb in bbox_por_nombre.items():
        rect = Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1],
                         fill=False, edgecolor=colors.get(nombre, "gray"),
                         linestyle=":", linewidth=0.8, alpha=0.6)
        ax.add_patch(rect)

    # Estaciones seleccionadas
    sel = pd.read_csv(PROCESSED / "estaciones_seleccionadas_hidrometricas.csv")
    ax.scatter(sel["longitud"], sel["latitud"], s=8, c="black", alpha=0.5,
               label=f"Hydrometric stations ≥60% coverage (n={len(sel)})", zorder=3)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Hidro-MX pilot basins: 123 delineated sub-basins and curated bounding boxes")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT / "fig8_cuencas_subcuencas.png")
    plt.close(fig)

    metrics["fig8"] = {
        "subcuencas_por_cuenca": subbasin_count,
        "subcuencas_total": int(sum(subbasin_count.values())),
        "n_estaciones_seleccionadas": int(len(sel)),
    }
    log.info("Fig.8 OK (%d subcuencas en %d cuencas)", sum(subbasin_count.values()), len(subbasin_count))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    metrics: dict = {}
    cat_hid = RAW / "sih" / "catalogo_hidrometricas.csv"
    hid = load_partitioned(PROCESSED / "series_hidrometricas.parquet")
    hid["fecha"] = pd.to_datetime(hid["fecha"])
    hid = attach_catalog(hid, cat_hid)
    log.info("Hidro: %d filas, %d estaciones", len(hid), hid["clave_estacion"].nunique())

    clima_path = PROCESSED / "series_climatologicas.parquet"
    cli = pd.DataFrame()
    if clima_path.exists() and any(clima_path.glob("*/*.parquet")):
        try:
            cli = load_partitioned(clima_path)
            cli["fecha"] = pd.to_datetime(cli["fecha"])
            log.info("Clima: %d filas, %d estaciones", len(cli), cli["clave_estacion"].nunique())
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo leer clima: %s", exc)

    metrics["dataset"] = {
        "hidrometricas": {
            "n_estaciones": int(hid["clave_estacion"].nunique()),
            "n_filas": int(len(hid)),
            "fecha_min": str(hid["fecha"].min().date()),
            "fecha_max": str(hid["fecha"].max().date()),
        },
        "climatologicas": {
            "n_estaciones": int(cli["clave_estacion"].nunique()) if not cli.empty else 0,
            "n_filas": int(len(cli)) if not cli.empty else 0,
            "fecha_min": str(cli["fecha"].min().date()) if not cli.empty else None,
            "fecha_max": str(cli["fecha"].max().date()) if not cli.empty else None,
        },
    }

    fig1_inventario_cobertura(hid, metrics)
    fig2_descriptiva(hid, metrics)
    fig3_calidad(hid, metrics)
    fig5_mapa(hid, metrics)
    fig6_temporal(hid, metrics)
    fig7_precip_gasto(hid, cli, metrics)
    fig8_basin_map(metrics)

    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Métricas -> %s", OUT / "metrics.json")
    log.info("Figuras en %s", OUT)


if __name__ == "__main__":
    main()

# hidroxai-mx

[![Dataset DOI (Zenodo, all versions)](https://zenodo.org/badge/DOI/10.5281/zenodo.21231600.svg)](https://doi.org/10.5281/zenodo.21231600)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data%20license-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Code license: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)

Reproducible library and data pipeline for **HidroXAI-MX** (IPN · PICDT2026):
a curated hydroclimatic dataset for pilot basins in Mexico built from open data
of CONAGUA (SIH) and INEGI (CEM 3.0).

> **Dataset:** cite the concept DOI [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600),
> which resolves to the latest snapshot. Snapshot `v2026.06`:
> [10.5281/zenodo.21231601](https://doi.org/10.5281/zenodo.21231601). Changes between
> snapshots are listed in [`CHANGELOG.md`](CHANGELOG.md). A versioned mirror is also
> available through the DVC remote on Cloudflare R2 (`dvc pull`).

## Layout

```
hidroxai-mx/
├── conf/
│   ├── sources.yaml           # Source registry (verified URLs, formats, licenses)
│   └── cuencas_piloto.yaml    # Pilot units, hydrological regions, selection criteria
├── data/                      # Not tracked in git (DVC)
│   ├── raw/                   # As downloaded (immutable) + _manifest.json
│   ├── processed/             # Canonical series, station tables, reports
│   └── features/              # Model-ready feature table
├── src/hidroxai_mx/           # io/, data/ (schema, cleaning, persistence), features/, geo/, report.py
├── scripts/                   # Pipeline stages (01–12) and revision audits (dib_*)
├── results/dib_revision/      # Audit of the v2026.06 release (see below)
├── notebooks/                 # Data access and coverage report
└── tests/
```

## Pipeline

| Stage | Script | Output |
|---|---|---|
| Catalogs | `01_download_sih_catalogs.py` | `data/raw/sih/catalogo_*.csv` |
| Candidates | `05_select_stations.py` | `data/processed/estaciones_candidatas_*.csv` (hydrological regions 12, 18, 26) |
| Series | `03_download_sih_series.py --tipo {hidrometricas,climatologicas}` | `data/raw/sih_series/<tipo>/<KEY>.csv` |
| Canonical + QC | `04_build_canonical.py --tipo ...` | `data/processed/series_<tipo>.parquet`, `reportes/validacion_<tipo>.json` |
| Selection | `05_select_stations.py --refine` | `estaciones_seleccionadas_*.csv`, `estaciones_extendidas_hidrometricas.csv` |
| Per-unit DEM | `06b_build_cem_per_basin.py` | `data/raw/inegi/cem_<unit>.tif` |
| Station–river link | `06_link_hydrorivers.py --hydrorivers PATH` | `data/processed/estaciones_hidrorivers.csv` |
| Features | `07_build_features.py --no-save-tensors` | `data/features/feature_table.parquet` (m³/s) |
| Storage guardrail | `08_storage_report.py` | fails above 9.5 GB |
| Figures | `09_make_report_figures.py`, `12_make_workflow_figure.py` | `data/processed/reportes/Fig1–Fig7.{png,tif}`, `metrics.json` |
| Provenance | `10_rebuild_manifest.py` | `data/raw/_manifest.json` |
| Zenodo archive | `11_build_zenodo_bundle.py --version v2026.10` | `dist/HidroXAI-MX-<version>.zip` |

```bash
pip install -e ".[dev,geo]"
python scripts/01_download_sih_catalogs.py
python scripts/05_select_stations.py
python scripts/03_download_sih_series.py --tipo hidrometricas
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/05_select_stations.py --refine
python scripts/06_link_hydrorivers.py --hydrorivers PATH/HydroRIVERS_v10_na.shp
python scripts/07_build_features.py --no-save-tensors
python scripts/09_make_report_figures.py
python scripts/12_make_workflow_figure.py
python scripts/10_rebuild_manifest.py
```

### Quality flag (`calidad`)

| Value | Meaning |
|---|---|
| 0 | Original observation |
| 1 | Streamflow linearly interpolated inside an internal gap of 1–6 days, using original observations only. Precipitation is not interpolated. |
| 2 | Flagged outlier (negative value or > 3 × the station's 99.9th percentile), retained. Flagged values include single-day capture errors and a few real flood peaks; see `results/dib_revision/outliers_hidro.csv` before discarding them. |

## Data → figure map

| Article figure | File (`data/processed/reportes/`) | Script | Input data |
|---|---|---|---|
| Fig. 1 Workflow | `Fig1_workflow.{png,tif}` | `12_make_workflow_figure.py` | — |
| Fig. 2 Station map | `Fig2_station_map.{png,tif}` | `09_make_report_figures.py` | `estaciones_candidatas_hidrometricas.csv`, `estaciones_seleccionadas_hidrometricas.csv`, `raw/sih_series/hidrometricas/`, `conf/cuencas_piloto.yaml`; boundary layers in `conf/sources.yaml` |
| Fig. 3 Quality flags | `Fig3_quality_flags.{png,tif}` | `09_make_report_figures.py` | `series_hidrometricas.parquet` |
| Fig. 4 Inventory and coverage | `Fig4_inventory_coverage.{png,tif}`, `cobertura_por_estacion.csv` | `09_make_report_figures.py` | `series_hidrometricas.parquet`, `raw/sih/catalogo_hidrometricas.csv` |
| Fig. 5 Streamflow by region | `Fig5_streamflow_by_region.{png,tif}` | `09_make_report_figures.py` | same as Fig. 4 |
| Fig. 6 Climatology and annual means | `Fig6_climatology_annual.{png,tif}` | `09_make_report_figures.py` | same as Fig. 4 |
| Fig. 7 Precipitation–streamflow lag correlation | `Fig7_precip_streamflow.{png,tif}`, `precip_streamflow_lagcorr.csv` | `09_make_report_figures.py` | `series_hidrometricas.parquet`, `series_climatologicas.parquet` |

Numbers cited in the tables of the article come from `data/processed/reportes/metrics.json`
and `results/dib_revision/numbers.json`.

## Revision of the v2026.06 release

`results/dib_revision/` documents the audit carried out in response to the review of the
associated *Data in Brief* article: pre-registered criteria and outcomes
(`proof_ledger.md`), a summary (`report.md`), the scripts `scripts/dib_*.py` and every table
they produce. The changes it led to are listed in `CHANGELOG.md`.

## Source decision

The **SIH portal** (`https://sih.conagua.gob.mx`) publishes daily historical series for
climatological and hydrometric stations as per-station CSV files
(`/basedatos/{Hidros|Climas}/<KEY>.csv`, Latin-1, missing values as `-` or empty, dates
`YYYY/MM/DD`), which makes ingestion catalog-driven with no scraping. **BANDAS**
(`https://app.conagua.gob.mx/bandas`) remains a deep historical backup. See
`conf/sources.yaml` and `docs/fuentes_verificacion.md`.

## DEM (INEGI CEM 3.0)

State-level CEM 3.0 tiles (15 m) are mosaicked and clipped to each unit's bounding box
(`06b_build_cem_per_basin.py`). Alta del Balsas is delivered at 15 m and the other five
units at 30 m (`Resampling.average`); the rasters are in geographic coordinates
(EPSG:6365). The effect of the 30 m aggregation on slope is quantified in
`results/dib_revision/e6_dem.json`.

## Remote storage: Cloudflare R2 (DVC)

```bash
cp .env.example .env          # fill in R2_ENDPOINT_URL and the R2 S3 keys
bash scripts/setup_dvc_r2.sh  # configures the 'r2' remote (keys land in .dvc/config.local)
dvc pull                      # or: dvc add data/processed data/features && dvc push
```

Never version the sliding-window `.npz` tensors; `08_storage_report.py` enforces the
9.5 GB budget. `notebooks/01_acceso_datos_r2.ipynb` shows remote access from Colab.

## Licenses and credits

Code: **MIT** (`LICENSE`). Derived data: **CC BY 4.0** (`LICENSE-DATA.md`), with
mandatory attribution to CONAGUA (SIH), INEGI (CEM 3.0) and, for the station–river
link, HydroSHEDS (Lehner & Grill, 2013).

Project **IND-2026-0335**, Instituto Politécnico Nacional (IPN), Unidad Profesional
Interdisciplinaria de Ingeniería campus Tlaxcala (**UPIIT**), 2026 Call for Scientific
Research and Technological Development Projects, Secretaría de Investigación y Posgrado.
Technical lead: **Daniel Sánchez Ruiz**. Citation: `CITATION.cff`. Full credits:
`CREDITOS.md`.

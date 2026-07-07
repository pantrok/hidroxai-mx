# hidroxai-mx

[![Dataset DOI (Zenodo)](https://zenodo.org/badge/DOI/10.5281/zenodo.21231601.svg)](https://doi.org/10.5281/zenodo.21231601)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data%20license-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Code license: MIT](https://img.shields.io/badge/code%20license-MIT-blue.svg)](LICENSE)

Reproducible library and data pipeline for **HidroXAI-MX** (IPN · PICDT2026):
explainable forecasting of streamflow gauge levels and local climate in Mexico
on top of open data from CONAGUA, SMN and INEGI.

> **Dataset snapshot `v2026.06`** — DOI [10.5281/zenodo.21231601](https://doi.org/10.5281/zenodo.21231601).
> Full versioned mirror also available via the DVC remote on Cloudflare R2 (`dvc pull`).

This repository covers **OE1 — National dataset integration and curation**
(Month 2 of the roadmap). The downstream layers (modeling, explainability,
fuzzy rules, dashboard) are built on top of this modular structure.

> Source status verified on **2026-06-18**. See `conf/sources.yaml` and
> `docs/fuentes_verificacion.md` for the per-endpoint details.

## Layout

```
hidroxai-mx/
├── conf/
│   ├── sources.yaml          # Source registry (verified URLs, formats, licenses)
│   └── cuencas_piloto.yaml    # Target basins and hydrological regions
├── data/                      # Do NOT track contents in git (managed by DVC)
│   ├── raw/                   # As downloaded (immutable)
│   ├── interim/               # Intermediate conversions (mdb→csv, kmz→parquet)
│   ├── processed/             # Cleaned + imputed series (canonical schema)
│   └── features/              # Training-ready tensors
├── src/hidroxai_mx/
│   ├── io/                    # Download connectors (CONAGUA/SMN/INEGI/DataMéxico)
│   ├── data/                  # Schemas (pandera), cleaning, imputation, persistence
│   ├── features/              # Lags, SPI/SPEI, STL, windows, tensors
│   └── utils/                 # Logging, cache, geo, dates
├── scripts/                   # Executable entrypoints, one per stage (01..08)
├── notebooks/                 # Exploration and coverage reports
├── tests/                     # Schema and I/O tests
├── pyproject.toml
├── dvc.yaml                    # Data pipeline stages
└── Makefile
```

## Quickstart

```bash
# 1. Environment (uv recommended; plain pip works as well)
uv venv && source .venv/bin/activate        # or: python -m venv .venv
uv pip install -e ".[dev]"                   # or: pip install -e ".[dev]"

# 2. Download SIH master catalogs (fast, ~1 MB)
python scripts/01_download_sih_catalogs.py

# 3. Download spatial catalogs of weather networks (KMZ/XLSX)
python scripts/02_download_smn_kmz.py

# 4. Download daily historical SIH series (CSV, recent coverage 2010–2025)
python scripts/03_download_sih_series.py --tipo hidrometricas

# 5. Build the canonical schema and persist as partitioned Parquet
python scripts/04_build_canonical.py

# 6. (Optional) Version the snapshot with DVC
dvc add data/processed && git add data/processed.dvc && git commit -m "dataset v0.1"
```

## Source decision (important)

The original inventory (`datasets_HidroXAI_MX.docx`) pointed at the static catalogs
on `datos.gob.mx` and at the deep historical archives stored as `.mdb` files in
**BANDAS**. Live verification (2026-06-18) found that:

- The **SIH portal** (`https://sih.conagua.gob.mx`) now publishes the **daily
  historical series for climatological and hydrometric stations as UTF-8 CSV**,
  refreshed weekly. It is the **recommended primary source** for the 2010–2025
  coverage (no `.mdb` conversion required).
- **BANDAS** (`https://app.conagua.gob.mx/bandas`) is still online and is used as
  the **deep historical backup** (pre-2013) and for the dam catalog and series.
- **DataMéxico** migrated to `https://www.economia.gob.mx/datamexico`; its
  Tesseract API must be re-confirmed before use (auxiliary socioeconomic layer,
  low priority).

See `docs/fuentes_verificacion.md`.

## Licenses

Code: **MIT**. Redistributable derived data: **CC BY 4.0** (compatible with the
*Libre Uso MX* terms). Attribution to CONAGUA, SMN, INEGI and CICESE-CLICOM is
mandatory where applicable.

---

## Updated ingestion flow (verified 2026-06-18)

The SIH publishes **direct per-station CSVs** at
`/basedatos/{Hidros|Climas}/<CLAVE>.csv`, so ingestion is driven by the catalog
(no HTML scraping, no JS selectors):

```bash
python scripts/01_download_sih_catalogs.py     # hydro + climate catalogs (CSV)
python scripts/05_select_stations.py            # candidates by hydrological region (12,18,26)
python scripts/03_download_sih_series.py --tipo hidrometricas    # catalog-driven download
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/04_build_canonical.py --tipo hidrometricas        # canonical schema -> Parquet
python scripts/05_select_stations.py --refine   # filter by >=80% coverage + climate neighbors
```

Format notes: encoding **Latin-1**; missing values encoded as `-` or empty;
date format `YYYY/MM/DD`; the reader skips the metadata block and normalizes
column headers automatically.

## CEM (INEGI): resolution

`conf/sources.yaml` sets `resolucion_default: 30` m. In `conf/cuencas_piloto.yaml`
the **Alta del Balsas** basin uses **15 m** (small headwater basin); everything
else uses 30 m. Always download clipped to each basin's bounding box (never the
national mosaic).

## Remote storage: Cloudflare R2 (DVC)

R2 is S3-compatible with no egress fees (10 GB free tier). Setup:

```bash
cp .env.example .env          # fill in R2_ENDPOINT_URL and the R2 S3 keys
bash scripts/setup_dvc_r2.sh  # configures the 'r2' remote (keys land in .dvc/config.local)
dvc add data/processed && dvc push   # version and upload the snapshot
git add data/processed.dvc .dvc/config && git commit -m "dataset v0.1" && git tag v2026.06
```

## Remote access from a notebook

See `notebooks/01_acceso_datos_r2.ipynb` (Colab/Jupyter): it installs
`dvc[s3]`, sets R2 credentials as environment variables, and pulls data with
`dvc pull` (whole dataset) or `dvc.api.get_url(...)` (single file), then
`pd.read_parquet(...)`.

## Geospatial sub-flow (script 06) and features (script 07)

Requires the `geo` extra:  `pip install -e ".[geo]"`

```bash
# 06 — basin delineation (needs the per-basin DEM at data/raw/inegi/cem_<cuenca>.tif)
python scripts/06_delineate_basins.py --threshold 1000
#   DEM(tif) -> fill_depressions -> d8_pointer + flow_accumulation -> extract_streams
#   -> snap pour points (stations) -> watershed -> per-basin GeoPackage
#   (area_km2, mean elevation, mean slope) in data/processed/cuencas/<cuenca>.gpkg

# 07 — features and tensors
python scripts/07_build_features.py --t-in 256 --horizon 7
#   joins nearest-climate stations via IDW (power 2) to each hydrometric station,
#   generates lags (1/3/7/14/30) and rolling means, normalizes per station, and
#   assembles (B,T,F) tensors -> data/features/feature_table.parquet and
#   data/features/tensors_h7.npz
```

The `hidroxai_mx.geo` module (delineation + spatial joins) and the
`hidroxai_mx.features` helpers (lags, SPI/SPEI, STL, IDW, windows) lazy-import
the heavy dependencies (whitebox/rasterio/geopandas).

## Coverage report and validation (notebook 02)

`notebooks/02_reporte_cobertura.ipynb` produces the tables and figures used in
the *data paper* validation (inventory, coverage, descriptive statistics,
quality, cross-source consistency, spatial coherence, temporal patterns,
precip→discharge response, and provenance). The logic lives in
`hidroxai_mx.report` (with tests). If no Parquet is available yet, the notebook
simulates a demo dataset. Outputs are written to `data/processed/reportes/`.

## Official staged runs (R2 budget = 10 GB)

> `dvc push` runs on **your** machine with **your** R2 credentials (the repo
> does not ship any). **Golden rule: never version the `.npz` tensors** (they
> are regenerated at training time); with that rule in place even the full
> national catalog (~5 GB) fits within 10 GB.

**Measured** budget (Parquet, no tensors):

| Scope | raw CSV | canonical | features | Total |
|---|---|---|---|---|
| Pilot (~20 stations) | ~1 MB | ~2 MB | ~10 MB | **~13 MB** |
| OE1 (~200 stations) | ~10 MB | ~24 MB | ~100 MB | **~134 MB** |
| 4 basins (~600 stations) | ~30 MB | ~71 MB | ~301 MB | **~402 MB** |
| Full catalog (~7400 stations) | ~370 MB | ~878 MB | ~3.7 GB | **~5.0 GB** |

Risk: the sliding-window `.npz` tensors (stride 1) weigh ~9 GB at 200 stations
and ~336 GB at the full catalog. That is why `07` does not materialize them by
default and `08` fails if the versioned footprint exceeds 9.5 GB. Add the
per-basin DEM on top (30 m: ~0.1–0.5 GB each); it still fits comfortably.

### Stage 1 — Smoke test (small data, ~13 MB)
```bash
python scripts/01_download_sih_catalogs.py
python scripts/05_select_stations.py
python scripts/03_download_sih_series.py --tipo hidrometricas  --limit 5
python scripts/03_download_sih_series.py --tipo climatologicas --limit 5
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py        # must say OK (within budget)
dvc add data/processed data/features && dvc push
```

### Stage 2 — Consolidation (4 pilot basins, ~0.4 GB)
```bash
python scripts/03_download_sih_series.py --tipo hidrometricas     # all candidates
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/05_select_stations.py --refine                     # >=80% coverage + neighbors
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py        # guardrail: fails if > 9.5 GB
dvc add data/processed data/features && dvc push && git tag v2026.06
```

`03 --all` downloads the full national catalog (~5 GB without tensors): it
fits, but use it only if you actually need nation-wide coverage. Tune the cap
with `R2_CAP_GB` if you switch plan.

## Credits and funding

Project **IND-2026-0335** — "Explainable forecasting of streamflow gauge
levels and local climate in Mexico via temporal deep learning and fuzzy rules,
on top of CONAGUA and Servicio Meteorológico Nacional open data".

Developed at the **Instituto Politécnico Nacional (IPN)**, Unidad Profesional
Interdisciplinaria de Ingeniería campus Tlaxcala (**UPIIT**), under the
**2026 Call for Scientific Research and Technological Development Projects**
of the **Secretaría de Investigación y Posgrado**. Technical lead:
**Daniel Sánchez Ruiz**.

Licenses: code **MIT** (`LICENSE`); derived data **CC BY 4.0**
(`LICENSE-DATA.md`). Citation: see `CITATION.cff`. Full credits: `CREDITOS.md`.

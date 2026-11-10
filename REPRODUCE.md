# Reproducing the article from the v2026.11 archive

This file maps every table, figure and number of the *Data in Brief* article to the command that produces it and the file where it is written. It applies to the Zenodo archive `HidroXAI-MX-v2026.11.zip` (concept DOI [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600)) and to a clone of the repository at tag `v2026.11` (the data are then fetched with `dvc pull`).

## Setup

Run every command from the root of the unzipped archive (or of the repository clone; the package finds `raw/`, `processed/` and `features/` at the archive root, or `data/` in the repository).

```bash
unzip HidroXAI-MX-v2026.11.zip -d hidromx && cd hidromx
python -m venv venv
# activate it: venv\Scripts\activate (Windows) or source venv/bin/activate (Linux, macOS)
pip install -e ".[dev,geo]"
```

Fig. 2 needs three boundary layers that are not redistributed; download the layers listed in `conf/sources.yaml` (section 10) into `scratch/limites/` (`ne_10m_admin_1/`, `rh250kgw/`, `cue250kgw/`).

## Commands

```bash
python scripts/dib_01_reconcile_counts.py --suffix _v2026_10  # Table 1
python scripts/dib_13_paso2_tables.py        # Tables 2 and 3
python scripts/12_make_workflow_figure.py    # Fig. 1
python scripts/09_make_report_figures.py     # Figs. 2–7 and their source data
python scripts/dib_03_imputation_masking.py  # Fig. S1
python scripts/dib_04_outliers.py            # Fig. S2
python scripts/dib_15_submission_figures.py  # submission TIFF files
python scripts/dib_09_baseline.py            # baseline metrics
python scripts/dib_17_r2_checks.py --tareas t1,t2,t3,t4 --hydrorivers <path>/HydroRIVERS_v10_na.shp
```

**HydroRIVERS.** The `t4` task needs `HydroRIVERS_v10_na.shp` (HydroRIVERS v1.0, North America; HydroSHEDS, https://www.hydrosheds.org; Lehner & Grill, 2013, https://doi.org/10.1002/hyp.9740). It is not included in the archive. Without `--hydrorivers`, `t4` still writes the distances, coordinate precision and differing reaches from `processed/estaciones_hidrorivers.csv`, but not the distance to the nearest reach of the unlinked stations or the radius sensitivity. Tasks `t1`–`t3` need nothing else.

## Article element, command, output and time

Times were measured on a clean copy of the previous archive, `HidroXAI-MX-v2026.10.zip`, whose data are identical to v2026.11, with `scripts/dib_17_r2_checks.py` added: the archive unzipped into an empty folder, a new virtual environment, Python 3.12.6, Windows-11-10.0.26300-SP0.

| Article element | Command | Output file | Time in the clean copy |
|---|---|---|---|
| Table 1 (directory structure; station and record counts) | `python scripts/dib_01_reconcile_counts.py --suffix _v2026_10` | `results/dib_revision/counts_reconciliation_v2026_10.csv`, `results/dib_revision/observation_counts_v2026_10.csv` | 2.1 min |
| Table 2 (columns, data types and units; feature-table definition) | `python scripts/dib_13_paso2_tables.py` | `results/dib_revision/e13_paso2_t1.json` | 1 s |
| Table 3 (stations per pilot basin) | `python scripts/dib_13_paso2_tables.py` | `results/dib_revision/tabla3_v2026_10.csv` | 1 s |
| Table 4 (missing data and coverage per operational unit) | `python scripts/dib_17_r2_checks.py --tareas t3` | `results/dib_revision/r2/cobertura_por_unidad.csv` | 2 s |
| Fig. 1 | `python scripts/12_make_workflow_figure.py` | `processed/reportes/Fig1_workflow.{png,tif}` | 2 s |
| Figs. 2–7 and their source data | `python scripts/09_make_report_figures.py` | `processed/reportes/Fig2…Fig7.{png,tif}`, `metrics.json`, `cobertura_por_estacion.csv`, `precip_streamflow_lagcorr.csv` | 59 s |
| Fig. S1 (imputation error vs gap length) | `python scripts/dib_03_imputation_masking.py` | `results/dib_revision/figs/figS_imputation_error_vs_L.{png,tif}`, `results/dib_revision/imputation_masking_summary.csv`, `results/dib_revision/e3_imputation.json` | 22 s |
| Fig. S2 (flagged outliers) | `python scripts/dib_04_outliers.py` | `results/dib_revision/figs/figS_outliers_examples.{png,tif}`, `results/dib_revision/outliers_hidro.csv`, `results/dib_revision/e4_outliers.json` | 7 s |
| Submission files Figure_1–7, S1–S2 (TIFF) | `python scripts/dib_15_submission_figures.py` | `dist/figuras_envio/`, `results/dib_revision/figuras_envio.csv` | 1 s |
| Baseline metrics: median NSE 0.528 (persistence) and 0.594 (ridge), median KGE 0.764 and 0.642, ridge better than persistence at 75 of 97 stations | `python scripts/dib_09_baseline.py` | `results/dib_revision/baseline_summary.csv` (`NSE_mediana`, `KGE_mediana`), `results/dib_revision/e9_baseline.json` | 3 s |
| Baseline without imputed values in the predictor window; skill against persistence | `python scripts/dib_17_r2_checks.py --tareas t1` | `results/dib_revision/r2/baseline_sin_imputados_summary.csv`, `results/dib_revision/r2/fraccion_imputados_test.json`, `results/dib_revision/r2/skill_vs_persistencia.csv`, `results/dib_revision/r2/t1_resumen.json` | 4 s |
| End of the record within the test period | `python scripts/dib_17_r2_checks.py --tareas t2` | `results/dib_revision/r2/fin_registro_test.json` | 2 s |
| Station–reach distances, coordinate precision, differing reaches, unlinked stations and sensitivity to the search radius | `python scripts/dib_17_r2_checks.py --tareas t4 --hydrorivers <path>/HydroRIVERS_v10_na.shp` | `results/dib_revision/r2/hydrorivers_distancias.csv`, `coordenadas_redondeo.csv`, `hydrorivers_tramos_distintos.csv`, `hydrorivers_sin_vinculo.csv`, `hydrorivers_sensibilidad_radio.csv`, `t4_resumen.json` (all in `results/dib_revision/r2/`) | 17 s |

Installing the package took 4.6 min and the test suite 12 s. The whole clean-copy check, including installation and the download of the boundary layers, took 8.8 min.

## Automated check

`scripts/dib_16_clean_copy_check.py` unzips an archive into a new folder, creates a new environment, installs the package, regenerates the products and figures and compares them with the packaged ones (JSON and CSV by value, figures by pixel). `scripts/dib_17_r2_checks.py --tareas copia` runs it and then repeats the baseline and the checks above inside the same copy:

```bash
python scripts/dib_17_r2_checks.py --tareas copia --zip HidroXAI-MX-v2026.11.zip --work <new folder> --hydrorivers <path>/HydroRIVERS_v10_na.shp
```

In our check every number of the article was reproduced exactly (CSV compared with a relative tolerance of 1e-12, JSON by value). Figure files may differ at pixel level with other plotting-library versions while their data are identical (Fig2_station_map.png in our check).

`control.max_diferencia` in `r2/t1_resumen.json` records the floating-point difference with which each environment recomputes its own `baseline_por_estacion.csv`; it differs between environments (5.7e-14 in the repository) and is the only value of the checks that does.

The block `diagnostico_dato_publicado` of `results/dib_revision/e3_imputation.json` describes the imputed values of the data present when `dib_03_imputation_masking.py` runs. The packaged file was computed on the v2026.06 data (cubic spline), so the regenerated block describes the current data instead. Fig. S1 and its source tables (`imputation_masking_summary.csv`, `imputation_masking_gaps.csv`) are reproduced exactly.

## Environment

- Python 3.12.6.
- `pyproject.toml` sets only minimum versions of the dependencies; there is no lock file. The versions installed in the clean copy were:

| Package | Version |
|---|---|
| matplotlib | 3.11.2 |
| geopandas | 1.2.0 |
| shapely | 2.2.0 |
| pyproj | 3.8.0 |
| pyogrio | 0.13.0 |
| numpy | 2.5.4 |
| pandas | 3.1.1 |
| pyarrow | 26.0.1 |
| pandera | 0.36.0 |
| pillow | 13.0.0 |

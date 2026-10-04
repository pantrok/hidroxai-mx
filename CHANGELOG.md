# Changelog

All changes to the Hidro-MX dataset snapshots deposited on Zenodo
(concept DOI [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600)).
The scripts and outputs that support every item below are in
`results/dib_revision/` of the source repository.

## v2026.10 — 2026-10

Revision prompted by the peer review of the associated *Data in Brief* article.
The raw SIH and INEGI inputs are unchanged; the processed products were rebuilt.

### Changed
- **Short-gap imputation (streamflow).** Internal gaps of 1–6 days are now filled by
  linear interpolation between original observations (`calidad = 0`). A masking
  experiment on the 101 selected stations (12,000 artificial gaps of 1–6 days) gave a
  normalized RMSE of 0.73 for linear, 0.75 for PCHIP and 2.10 for the cubic spline
  used in v2026.06, which also overshot the neighbouring observations in 52 % of the
  imputed days and produced negative flows. Gaps of 7 days or longer are now left
  entirely missing (v2026.06 filled the first seven days of longer gaps).
- **Precipitation is no longer interpolated in time.** Gaps remain missing; a
  spatial estimate from the three nearest selected climatological stations is
  provided as `precip_idw_mm` in the feature table.
- **Feature table in physical units.** `features/feature_table.parquet` now stores
  streamflow, lags and rolling means in m³/s (v2026.06 stored them z-scored per
  station with full-period statistics). The 7- and 30-day rolling means include
  day t.
- **Report figures** are named after the article numbering (`Fig1`–`Fig7`, PNG and
  TIFF at 300 dpi). The station map uses EPSG:6372 with national, state and
  hydrological-region boundaries; the precipitation–streamflow correlation is
  computed on deseasonalized anomalies over hydrological regions 12, 18 and 26.
- **Schema validation** results are written to
  `processed/reportes/validacion_<type>.json`; non-negative checks on streamflow and
  precipitation apply to original and imputed values, while negative raw values are
  retained with `calidad = 2`. Both canonical series pass the validation.
- **Physical limits of the climatological variables.** A station-day with any
  climatological variable outside its physical limits (maximum temperature −30 to 60 °C,
  minimum −40 to 50 °C, mean −40 to 55 °C, evaporation ≥ 0) is flagged `calidad = 2`
  and the value is retained: 24 values in 15 station-days, including seven maximum
  temperatures recorded as −99999 by the SIH and the mean temperatures the SIH derived
  from them. They are listed in `results/dib_revision/clima_fuera_de_rango.csv`.
- **Figure 2** also shows the official outline of the Río Cutzamala basin (CNA, 1998,
  1:250 000); the Lerma–Santiago and Pánuco pilot basins coincide with hydrological
  regions 12 and 26, already outlined. Report figures are written as PNG at 300 dpi and
  TIFF at 600 dpi.

### Removed
- **Sub-basin polygons** (`processed/cuencas/*.gpkg`). An independent comparison with
  the upstream areas of HydroRIVERS v1.0 showed that the polygons did not represent
  the drainage area of the gauges (median absolute area error 99.5 %): the DEMs
  clipped to each unit's bounding box do not contain the full upstream area of most
  gauges, and the multi-outlet delineation returned incremental rather than complete
  catchments. The per-basin DEMs are still distributed. The parameters used in
  v2026.06 are documented in `results/dib_revision/delineation_params.json`.

### Added
- `processed/estaciones_hidrorivers.csv`: for every selected hydrometric station,
  the HydroRIVERS v1.0 reach with the largest upstream area and the nearest reach
  within 0.01° (≈1.1 km), their distance and upstream area, and a flag when the two
  differ.
- `raw/_manifest.json` now covers every raw file (source URL, SHA-256, size; the
  download timestamp when it was recorded and the file modification time
  otherwise). It is included in the Zenodo archive.
- The Zenodo archive now also contains the code (`src/`, `scripts/`, `tests/`,
  `pyproject.toml`), the configuration (`conf/`) and the revision audit
  (`results/dib_revision/`), so products and figures can be regenerated from the archive
  alone; the package finds the data at the archive root.
- `CHANGELOG.md`.

### Fixed
- **Maximum and minimum temperature were missing for most climatological stations.**
  The SIH per-station CSV files are UTF-8 and were decoded as Latin-1, so the headers
  "Temperatura Máxima" and "Temperatura Mínima" were not recognised and both columns
  were dropped for 1,961 of the 2,659 stations. The files are now decoded as UTF-8:
  23,459,380 maximum and 23,459,380 minimum temperature values were recovered, and
  `tmax_c` and `tmin_c` now hold every value of the source files (29,230,620 and
  25,960,196). Precipitation, mean temperature, evaporation and the hydrometric series
  were not affected; a row-by-row comparison with the previous build is in
  `results/dib_revision/e12_clima_limites.json`.
- 204,614 duplicated station-days in `processed/series_hidrometricas.parquet`
  (12 stations), caused by leftover partition files from test runs of June 2026;
  the parquet writer now clears the target directory before writing.
- Rows added to complete the daily calendar of climatological series now carry
  `fuente = "SIH"` (they were empty in v2026.06).

## v2026.06 — 2026-06-26

First public snapshot (DOI [10.5281/zenodo.21231601](https://doi.org/10.5281/zenodo.21231601)).

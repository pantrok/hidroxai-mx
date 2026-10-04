# Revisión DIB-D-26-01662 (Hidro-MX) — reporte técnico

Fecha: 2026-09-26. Snapshot resultante: **v2026.10**. Toda cifra de este reporte sale de
`numbers.json`, generado por `scripts/dib_11_numbers.py` a partir de los archivos que
producen los scripts; los criterios de cada experimento se congelaron antes de correrlos
en `proof_ledger.md`.

## Resumen

- Las verificaciones que pidieron los revisores (conteos, imputación, outliers,
  validación de subcuencas, reproducibilidad) se hicieron sobre el release publicado. Sus
  resultados obligan a corregir cifras del artículo y a reconstruir los productos
  procesados; los insumos crudos (SIH, INEGI) no cambian.
- **Imputación:** el spline cúbico tuvo 2.9 veces el error del método lineal y producía
  gastos negativos; se adopta interpolación lineal en huecos de 1–6 días y la precipitación
  deja de interpolarse.
- **Subcuencas:** la validación contra HydroRIVERS mostró que los polígonos no representan
  la cuenca de los aforos (mediana del error de área 99.5 %); se retiran y se entrega en su
  lugar el vínculo estación–tramo HydroRIVERS con su área aportante.
- **Baseline, correlación desestacionalizada (Fig. 8 del artículo, Fig7 en v2026.10), mapa,
  parámetros y mapa datos→figura** quedan listos para el artículo.

## Por punto del brief

### 1. Conciliación de conteos (R2) — `dib_01_reconcile_counts.py`

| Concepto | Artículo | v2026.10 |
|---|---|---|
| Estaciones hidro / clima con archivo | 547 / 2,659 | 547 / 2,659 (sin cambio) |
| Candidatas sin archivo | — | 3 hidro + 72 clima: HTTP 404 en el portal (consulta 2026-09-26) |
| Seleccionadas hidro (cobertura ≥ 0.60) | 108 | **101** (108 salía de calcular la cobertura con valores imputados y duplicados) |
| Seleccionadas dentro de alguna unidad | 101 | **95** (CHAMC, CMNMC, LPNMC, LPSMC, LPZMC, TLAMC quedan fuera) |
| Seleccionadas clima (≥ 0.80) | 415 | 415 |
| Observaciones hidro | 10,594,758 "en 2010–2025" | 10,390,144 estación-día en todo el registro (1922–2025); **815,348** gastos con valor en 2010–2025 |
| Observaciones clima | 55,590,466 "en 2010–2025" | 55,590,466 estación-día en todo el registro; **6,532,136** precipitaciones con valor en 2010–2025 |
| Bandera de calidad | 98.78 / 1.21 / 0.005 % | **98.59 / 1.40 / 0.009 %** de los días con gasto (el valor anterior contaba días vacíos como "originales"); en 2010–2025: 94.52 / 5.46 / 0.023 % |
| Cobertura media (mediana) | 29.2 % (24.6 %) | **24.11 % (13.16 %)** con observaciones originales |
| "2 estaciones sin polígono" | Bajío 26→25, Pánuco 52→51 | Es una sola, BRAGJ: su punto ajustado caía en la misma celda que SL2GJ |

Además se corrigieron en el dato: 204,614 filas estación-día duplicadas en 12 estaciones
de Guanajuato (restos de corridas de prueba de junio en las particiones del parquet) y la
columna `fuente` vacía en 3,337,622 filas de relleno de calendario de la serie clima.

### 2. Deduplicación de subcuencas (R2, R3) — `dib_02_dedup_subbasins.py`

Se aplicó la regla congelada (borde de bbox → región hidrológica → área): 123 polígonos →
94; 22 estaciones tenían dos; BRAGJ queda sin polígono; 9 conservados tocan el bbox.
**Superado por el punto 5**: los polígonos se retiran. El registro queda en
`dedup_log.csv` y `e2_dedup.json`.

### 3. Imputación (R2, R4) — `dib_03_imputation_masking.py`

12,000 huecos artificiales de 1–6 días (2,000 por longitud) en las 101 estaciones:

| Método | nRMSE | nMAE | Sobreoscilación | Negativos |
|---|---|---|---|---|
| Lineal | 0.734 | 0.187 | 0 % | 0 |
| PCHIP | 0.746 | 0.185 | 0 % | 0 |
| Spline del pipeline | 2.098 | 0.357 | 52.5 % | 5,740 |

El spline es peor que lineal en 95 de 101 estaciones. Además, en el dato publicado el
29.8 % de lo imputado estaba dentro de huecos de más de 7 días (`limit=7` de pandas rellena
los primeros 7 días de cualquier hueco) y 13,279 gastos imputados eran negativos; en clima,
228,533 de 556,208 precipitaciones imputadas eran negativas. **Decisión del autor:**
interpolación lineal solo en huecos internos completos de 1–6 días, con nodos únicamente en
observaciones originales; la precipitación no se imputa. Figura suplementaria:
`figs/figS_imputation_error_vs_L.png` (error vs longitud de hueco, 1–10 días).
Referencias verificadas para el texto: `references_verified.json`.

### 4. Outliers (R2) — `dib_04_outliers.py`

507 registros `calidad = 2`, ninguno eliminado (la regla marca y conserva). 243 son
negativos (242 en una estación) y 264 altos; de estos, 114 son picos de un solo día ≥ 10
veces ambos vecinos, con máximos físicamente imposibles (293,588 m³/s en ATCHD, 336 m³/s/km²).
En las inundaciones de septiembre de 2013 (Pedrozo-Acuña et al., 2014, doi:10.1002/wea.2355),
18 estaciones principales tuvieron picos ≥ P99.9 y **3 de esos picos quedaron marcados**
(TMTSL, TBLSL, SGBTP, Pánuco). Mensaje para el artículo: la regla captura sobre todo errores
de captura, pero también algunos picos reales; por eso los valores se conservan y se entrega
la tabla de auditoría (`outliers_hidro.csv`). Las inundaciones de octubre de 2025 no son
evaluables: el registro hidrométrico termina el 2025-09-03. Figura suplementaria:
`figs/figS_outliers_examples.png`.

### 5. Validación de subcuencas (R2) — `dib_05_subbasin_validation.py`, `dib_05b_snap_diagnosis.py`

Contra el área aportante de HydroRIVERS v1.0 (88 de 94 polígonos con tramo a ≤ 1 km):
mediana |error de área| **99.5 %**; 1 de 88 dentro de ±20 %. Causas con evidencia: (1) los
DEM recortados al bbox no contienen la cuenca aguas arriba (Santiago tiene 48.9 % de celdas
sin dato); (2) el ajuste Jenson cae en arroyos laterales (39 de 88); (3) `watershed` con
varios puntos da áreas incrementales, no la cuenca completa. Además, el relleno de
depresiones sobre el DEM geográfico produce elevaciones irreales (hasta 175 km) y la cadena
no es determinista entre corridas; el resultado de la validación es el mismo con dos
corridas. **Decisión del autor:** retirar los polígonos en v2026.10 y entregar
`processed/estaciones_hidrorivers.csv` (93 estaciones vinculadas; en 17 el tramo más
cercano no es el de mayor área, lo que se marca).

### 6. DEM 15 m vs 30 m (R2) — `dib_06_dem_resolution.py`

Alta del Balsas, 15 m vs agregado a 30 m: elevación sin sesgo (−0.02 m; RMSD 2.4 m);
pendiente media 0.197 → 0.185 m/m (**−6.1 %**), P90 −3.4 %; celdas con pendiente > 0.3:
22.8 % → 20.8 %. Va a Limitations como tabla corta.

### 7. Parámetros de delineación (R3) — `delineation_params.json`

v2026.06: `extract_streams` 1000 celdas (≈ 0.89 km² a 30 m; 0.23 km² a 15 m) y
`jenson_snap_pour_points` 0.01° (≈ 1.07–1.08 km), sobre el CEM en EPSG:6365. Como los
polígonos se retiran, se reportan en la carta y en el CHANGELOG para trazabilidad; el
vínculo con HydroRIVERS usa un radio de 0.01°, declarado en `conf/cuencas_piloto.yaml`.

### 8. Figuras (R4) — `09_make_report_figures.py`, `12_make_workflow_figure.py`

Nueva numeración (`data/processed/reportes/`, PNG y TIFF a 300 dpi): Fig1 flujo de trabajo;
**Fig2 mapa** en EPSG:6372 con límites nacional y estatales, regiones hidrológicas 12, 18 y
26 (CONAGUA 1:250 000), unidades operativas, 547 estaciones descargadas y 101 seleccionadas
(46 / 16 / 39 por región); Fig3 banderas de calidad; Fig4 inventario y cobertura; Fig5
gasto por región; Fig6 climatología y medias anuales; **Fig7** correlación de anomalías
desestacionalizadas del agregado de las regiones 12, 18 y 26 (máximo a 2 días: Pearson
0.54, Spearman 0.44; sin desestacionalizar 0.62–0.70 en todos los rezagos). La antigua
Fig. 4 (subcuencas) desaparece.

### 9. Baseline (R2) — `dib_09_baseline.py`

Pronóstico a 1 día, 97 estaciones, partición 2010–2020 / 2021–2022 / 2023–2025, 1.9 s:

| Modelo | NSE mediana [IQR] | KGE mediana [IQR] |
|---|---|---|
| Persistencia | 0.528 [0.125, 0.772] | 0.764 [0.545, 0.882] |
| Ridge sobre lags | 0.594 [0.293, 0.717] | 0.642 [0.353, 0.815] |

Variante recomendada: se excluyen emisiones cuya ventana de predictores contiene valores
`calidad = 2` (enmienda documentada; la variante congelada también se reporta en el ledger).

### 10. Repositorio y Zenodo

Hecho: `CHANGELOG.md`; README con mapa datos→figura; `raw/_manifest.json` con los 3,215
archivos crudos; bundle actualizado (`11_build_zenodo_bundle.py --version v2026.10`, incluye
manifest y CHANGELOG); validación de esquema en `reportes/validacion_*.json`;
`conf/sources.yaml` con HydroRIVERS y las capas del mapa; `CITATION.cff` con el concept DOI.
Pendiente del autor: ver abajo.

### 11. Entregables

`numbers.json` (todas las cifras y la tabla "dice → debe decir"), este reporte y
`proof_ledger.md`.

## Estado del proof ledger

| Exp. | Estado |
|---|---|
| E1 conteos | Cifras del artículo `REJECTED`; embudo reconstruido `SUPPORTED` |
| E2 deduplicación | `REJECTED` como producto (superado por E5) |
| E3 imputación | Spline `REJECTED` (fallan ambas reglas); se adopta lineal |
| E4 outliers | "Conserva" `SUPPORTED`; "no marca extremos reales" `REJECTED` (3/18) |
| E5 subcuencas | `REJECTED`; polígonos retirados |
| E6 DEM 15 vs 30 m | `SUPPORTED` (descriptivo, a nivel DEM) |
| E7 parámetros | `SUPPORTED` (documentados) |
| E8 Fig. 7 | `SUPPORTED` |
| E9 baseline | `SUPPORTED` (descriptivo) |

## Cómo presentarlo en la carta

Cada cambio se presenta como el resultado de la verificación que pidió cada revisor, con
su número y su archivo de respaldo. Por ejemplo: "Following Reviewer 2's request, we
verified the station and observation statistics against the archived files; the verification
corrected …", o "As suggested by Reviewers 2 and 4, we compared linear, PCHIP and cubic-spline
gap filling in a masking experiment; linear interpolation had the lowest error and no
negative values, so v2026.10 adopts it". El CHANGELOG ya lista todos los cambios con su
motivo.

## Pendientes del autor

1. `git push` de los commits de la revisión (el repositorio pide confirmación antes de
   `git commit`/`push`/`tag` y `dvc push`).
2. Hecho el 2026-10-03: `08_storage_report.py` (3.13 GB / 9.5 GB), `dvc commit` y
   `dvc push` (225 archivos a R2). Los datos se versionan como salidas de las etapas de
   `dvc.yaml`; `dvc.lock` registra el snapshot v2026.10.
3. `python scripts/11_build_zenodo_bundle.py --version v2026.10` y subir el ZIP como
   **New version** del registro existente en Zenodo; comprobar que el concept DOI
   10.5281/zenodo.21231600 resuelve a v2026.10.
4. Crear el tag `v2026.10` en GitHub y activar la integración GitHub–Zenodo para el DOI del
   software; anotar ambos DOI en `numbers.json` (`dois`) y en `CITATION.cff`.
5. Editar el manuscrito con la tabla "dice → debe decir" de `numbers.json` y redactar la carta.

## Paso 2 (2026-10-04)

Segunda lista de tareas de la revisión. Cada cifra está en `numbers.json` con su
`"fuente"`; las decisiones que cambian datos quedaron congeladas antes en `proof_ledger.md`
(P2-T2, enmienda P2-T2a y P2-T3).

- **T1, cifras faltantes** (`dib_13_paso2_tables.py`):
  - **Tabla 3** por unidad (asignadas / vinculadas a HydroRIVERS / tramo cercano ≠ de mayor
    área / DEM): Cutzamala 1/1/0/30 m, Lerma Alto 8/8/3/30 m, Bajío 26/23/2/30 m, Santiago
    9/9/1/30 m, Pánuco 39/38/5/30 m, Alta del Balsas 12/11/5/15 m; suma 95. La regla de
    asignación para las 23 estaciones en dos o más recuadros está escrita en `numbers.json`.
  - **Sin vínculo HydroRIVERS:** 8 de 101; ninguna tiene tramo a ≤ 0.01°, y 3 de ellas
    además caen fuera de toda unidad.
  - **Manifest:** 3,215 entradas = 3,214 archivos + `.gitkeep`. 49 tienen fecha de
    descarga, 3,165 solo fecha de modificación y 3,208 tienen URL (faltan los 6 CEM).
  - **Release v2026.06:** 204,614 estación-días duplicados en 12 estaciones de Guanajuato,
    y 3,337,622 filas de clima con `fuente` vacía, contados sobre los parquets archivados.
  - **Curva del enmascaramiento** por L = 1…10 para los tres métodos.
  - **Feature table:** 5,831,035 filas, 479 estaciones y 15 columnas con unidades.
    `precip_idw_mm`: 3 vecinos, potencia 2, pesos renormalizados por día y solo para las
    101 seleccionadas.
  - **Baseline:** 4 estaciones excluidas, con su motivo.
- **T2, validación del clima:**
  - Al preparar T2 apareció un error de lectura: los CSV de series del SIH están en UTF-8
    y se leían como Latin-1. Por eso se descartaban `tmax`/`tmin` en 1,961 de 2,659
    estaciones.
  - Con decisión del autor (enmienda P2-T2a) se corrigió y se recuperaron 23,459,380
    valores de cada una.
  - Después se marcaron con `calidad = 2` 24 valores fuera de límites en 15 estación-días,
    sin borrarlos.
  - Ambas series pasan la validación; la verificación fila por fila cumple el criterio
    congelado.
  - No cambian 415 seleccionadas, 55,590,466 filas, 6,532,136 precipitaciones con valor
    en 2010–2025 ni Fig7.
- **T3, contornos de cuencas piloto** (`dib_14_pilot_basin_outlines.py`, capa CNA 1998
  de CONABIO, sin restricciones de uso):
  - Fig. 2 añade el contorno oficial de Río Cutzamala.
  - Lerma–Santiago y Pánuco coinciden con las regiones 12 y 26, ya dibujadas.
  - Alta del Balsas no tiene una cuenca oficial equivalente y no se fuerza.
  - La capa CONAGUA 2020 de 757 cuencas (IDEFOR) se descartó por su licencia NC-SA.
- **T4, reproducibilidad:** el ZIP incluye `src/`, `scripts/`, `tests/`, `conf/`,
  `results/dib_revision/` (sin `audit_code/` ni logs), `pyproject.toml`, `LICENSE` y
  `CITATION.cff`. El paquete encuentra los datos en la raíz del archivo. La prueba desde
  copia limpia (`dib_16_clean_copy_check.py`) queda en `clean_copy_check.md`.
- **T5:** `CITATION.cff` en inglés, versión 2026.10, autor único. Los DOI se llenan al
  publicar.
- **T6:** `dist/figuras_envio/` con Figure_1…7, S1 y S2. Las figuras de la etapa 09 se
  guardan en TIFF a 600 dpi; las 9 tienen ≥ 2244 px de ancho (`figuras_envio.csv`).
- **Observación sin cambio:** `precip_idw_mm` usa la precipitación de los vecinos tal como
  está en la serie, sin filtrar `calidad = 2` (213 valores en toda la serie climatológica).
  Se documenta en `numbers.json`.

## Lo que no se hizo

- Rediseño completo de la delineación: descartado por el autor (requería teselas CEM
  adicionales y un nuevo acondicionamiento del DEM).
- Verificación desde una copia limpia del ZIP v2026.10: se hace después de construirlo.

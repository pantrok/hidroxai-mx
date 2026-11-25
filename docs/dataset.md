# El dataset Hidro-MX

Series diarias de gasto y de variables climatológicas del Sistema de Información Hidrológica
(SIH) de CONAGUA para cuatro cuencas piloto, con modelos digitales de elevación de INEGI y el
vínculo de cada estación con la red de ríos HydroRIVERS. Se publica en Zenodo bajo licencia
CC BY 4.0 y lo describe el artículo de *Data in Brief*
[10.1016/j.dib.2026.113442](https://doi.org/10.1016/j.dib.2026.113442).

## Versiones

| Versión | Fecha | DOI | Qué cambió |
|---|---|---|---|
| v2026.06 | 2026-07-07 | [10.5281/zenodo.21231601](https://doi.org/10.5281/zenodo.21231601) | Primera versión pública |
| v2026.10 | 2026-10-05 | [10.5281/zenodo.23150556](https://doi.org/10.5281/zenodo.23150556) | Revisión del artículo; los productos procesados se reconstruyeron (detalle abajo) |
| v2026.11 | 2026-11-10 | [10.5281/zenodo.24119292](https://doi.org/10.5281/zenodo.24119292) | Mismos datos que v2026.10 (SHA-256 idénticos); agrega `REPRODUCE.md` y las comprobaciones de la segunda revisión |

El DOI de concepto [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600) apunta
siempre a la versión más reciente. El detalle completo está en
[`CHANGELOG.md`](https://github.com/pantrok/hidroxai-mx/blob/main/CHANGELOG.md).

**De v2026.06 a v2026.10:**

- **Imputación del gasto.** Los huecos internos de 1 a 6 días se rellenan por interpolación
  lineal entre observaciones originales; los de 7 días o más quedan vacíos. En v2026.06 se usaba
  un spline cúbico, que en un experimento de enmascaramiento tuvo un error mucho mayor y producía
  gastos negativos.
- **Precipitación.** Ya no se interpola en el tiempo. La tabla de características agrega una
  estimación espacial, `precip_idw_mm`, con las tres estaciones climatológicas seleccionadas más
  cercanas.
- **Tabla de características.** Queda en unidades físicas (m³/s); antes estaba estandarizada por
  estación.
- **Temperaturas máxima y mínima.** Se recuperaron: los archivos del SIH se leían con una
  codificación equivocada y esas columnas se perdían en 1,961 estaciones.
- **Duplicados.** Se eliminaron 204,614 estación-días duplicados.
- **Subcuencas.** Se retiraron los polígonos de subcuenca, que no representaban el área de
  drenaje de los aforos.
- **Agregados.** El vínculo estación–río con HydroRIVERS (`estaciones_hidrorivers.csv`), el
  manifiesto completo de las descargas y el código del pipeline dentro del ZIP.

## Estructura del ZIP

| Carpeta o archivo | Contenido |
|---|---|
| `raw/sih/` | Catálogos maestros de estaciones hidrométricas y climatológicas del SIH |
| `raw/sih_series/` | Un CSV por estación tal como se descargó: 547 hidrométricas y 2,659 climatológicas |
| `raw/inegi/` | Modelos digitales de elevación (CEM 3.0) recortados a cada unidad: `cem_<unidad>.tif` |
| `raw/_manifest.json` | URL de origen, SHA-256 y tamaño de cada archivo crudo |
| `processed/series_hidrometricas.parquet/` | Serie diaria canónica de gasto y nivel, particionada por año (`anio=AAAA/`) |
| `processed/series_climatologicas.parquet/` | Serie diaria canónica climatológica, particionada por año |
| `processed/estaciones_*.csv` | Catálogos de estaciones candidatas, seleccionadas y extendidas |
| `processed/estaciones_hidrorivers.csv` | Unidad piloto y tramo de HydroRIVERS v1.0 de cada estación hidrométrica |
| `processed/reportes/` | Figuras del artículo, métricas y validación del esquema |
| `features/feature_table.parquet` | Tabla diaria de características para modelado |
| `src/`, `scripts/`, `conf/`, `tests/` | Código y configuración para regenerar todo; ver `REPRODUCE.md` |
| `results/dib_revision/` | Auditoría de la revisión del artículo |

## Productos y columnas

**Series hidrométricas.** Columnas: `clave_estacion`, `fecha`, `gasto_medio_m3s` (m³/s),
`nivel_m` (m), `fuente` y `calidad`.

**Series climatológicas.** Columnas: `clave_estacion`, `fecha`, `precip_mm`, `evap_mm`,
`tmax_c`, `tmin_c`, `tmed_c`, `fuente` y `calidad`.

En las dos series, `fuente` vale `SIH` en todas las filas.

**Catálogos.** Columnas: `clave`, `nombre`, `latitud`, `longitud`, `altitud`, `estado`,
`municipio`, `region_hidrologica`, `cuenca` y `cobertura`. El catálogo hidrométrico agrega
`vecinos_clima`, las claves de sus tres estaciones climatológicas vecinas.

**Vínculo con HydroRIVERS.** Columnas: `clave` y `unidad_piloto`; el tramo de mayor área
aportante a menos de 0.01° (`hyriv_id`, `dist_m`, `upland_km2`); el tramo más cercano
(`*_cercano`); y `tramos_distintos`, que marca cuando los dos difieren.

**Tabla de características.** Columnas:

- `clave_estacion`, `fecha`, `anio`, `fuente` y `calidad`;
- `gasto_medio_m3s` y `nivel_m`;
- rezagos del gasto a 1, 3, 7, 14 y 30 días;
- medias móviles de 7 y 30 días, que incluyen el día *t*;
- `precip_idw_mm`.

## Banderas de calidad

| `calidad` | Significado |
|---|---|
| 0 | Observación original |
| 1 | Gasto interpolado linealmente en un hueco interno de 1 a 6 días, solo con observaciones originales |
| 2 | Valor marcado y conservado. Gasto y precipitación: negativo o mayor que 3 veces el percentil 99.9 de la estación; incluye errores de captura de un día y algunas crecidas reales. Series climatológicas: estación-día con alguna variable fuera de sus límites físicos |

## Estaciones y periodo

Las estaciones candidatas están en las regiones hidrológicas 12 (Lerma–Santiago),
18 (Balsas) y 26 (Pánuco). La cobertura se mide entre el 1 de enero de 2010 y el 31 de
diciembre de 2025. El registro descargado termina el 3 de septiembre de 2025; ver la
[nota sobre la cobertura](nota_diseno_cobertura.md).

| Etapa | Hidrométricas | Climatológicas |
|---|---:|---:|
| Catálogo maestro del SIH | 1,189 | 7,499 |
| Candidatas en las regiones 12, 18 y 26 | 550 | 2,731 |
| Archivo de serie descargado | 547 | 2,659 |
| Con algún dato en 2010–2025 | 325 | 1,899 |
| Seleccionadas (cobertura ≥ 0.60 hidrométricas, ≥ 0.80 climatológicas) | 101 | 415 |

Fuente: `results/dib_revision/counts_reconciliation_v2026_10.csv`.

Las 101 estaciones hidrométricas seleccionadas por unidad operativa, según
`results/dib_revision/r2/cobertura_por_unidad.csv`:

| Unidad | Pánuco | Bajío | Alta del Balsas | Santiago | Lerma Alto | Cutzamala | Fuera de unidad |
|---|---:|---:|---:|---:|---:|---:|---:|
| Estaciones | 39 | 26 | 12 | 9 | 8 | 1 | 6 |

El tutorial [2 · Cobertura y selección](tutoriales/02_cobertura_seleccion.ipynb) reproduce
esta selección a partir de las series.

## Fuentes y atribución

- CONAGUA, Sistema de Información Hidrológica (<https://sih.conagua.gob.mx>): series y catálogos.
- INEGI, Continuo de Elevaciones Mexicano 3.0: modelos de elevación.
- HydroSHEDS, HydroRIVERS v1.0 (Lehner & Grill, 2013,
  <https://doi.org/10.1002/hyp.9740>): vínculo estación–río.

Los términos de uso de cada fuente están en
[`LICENSE-DATA.md`](https://github.com/pantrok/hidroxai-mx/blob/main/LICENSE-DATA.md).

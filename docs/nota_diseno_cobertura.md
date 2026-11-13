# Nota de diseño · ventana de la cobertura (2010–2025)

**Estado:** documentado, no se cambia. Es parte de la definición publicada del dataset (Data in
Brief y las versiones v2026.06, v2026.10 y v2026.11 en Zenodo).

## Definición publicada

- La cobertura de una estación es el número de días con gasto observado, antes de imputar, entre
  el 2010-01-01 y el 2025-12-31, dividido entre el total de días de ese periodo.
  - Código: `scripts/05_select_stations.py`, función `_coverage`.
  - Periodo y umbrales en `conf/cuencas_piloto.yaml`: `periodo` y `cobertura_minima` (0.60 para
    las hidrométricas, 0.80 para las climatológicas).
- La selección de las 101 estaciones hidrométricas (cobertura ≥ 0.60) se hizo con esa definición.

## Lo que hay que saber

- El registro descargado del SIH termina el **2025-09-03**
  (`results/dib_revision/r2/fin_registro_test.json` → `ultima_fecha_global`).
- Los días posteriores, hasta el 2025-12-31, entran en el denominador sin observación posible.
  Por eso la cobertura y la fracción de días faltantes describen el periodo calendario completo,
  no el periodo con registro.
- El efecto se mide en `results/dib_revision/r2/cobertura_por_unidad.csv`, fila `total`:
  - días faltantes sobre el calendario completo: 17.95 % (`fraccion_dias_faltantes`);
  - días faltantes hasta el fin del registro: 16.24 %
    (`fraccion_dias_faltantes_hasta_fin_registro`).

## Por qué no se cambia

- Cambiar el denominador cambiaría la cobertura de todas las estaciones y podría cambiar qué
  estaciones pasan el umbral de 0.60. Eso alteraría el conjunto seleccionado y todas las cifras
  publicadas que dependen de él.
- La definición está escrita en el código y en la configuración, así que es reproducible tal como
  está. Las estaciones seleccionadas cumplen el umbral con un criterio más exigente que el que
  daría el periodo con registro.
- Si una versión futura del dataset amplía el registro más allá del 2025-09-03, la diferencia se
  reduce sola.

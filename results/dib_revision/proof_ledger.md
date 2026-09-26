# Proof ledger — revisión DIB-D-26-01662 (Hidro-MX)

Criterios congelados el **2026-09-26**, antes de ejecutar los experimentos E2–E9, sobre el
commit `255e840` (idéntico a `origin/main` y al bundle publicado `HidroXAI-MX-v2026.06.zip`).
Ningún verificador, umbral ni regla de rechazo se modifica después de ver resultados; si uno
resulta mal planteado se añade una entrada nueva en *Enmiendas* con fecha y motivo, sin borrar
la original.

Etiquetas: `PROVEN` (solo dentro del verificador), `SUPPORTED`, `REJECTED`, `OPEN`.

## Hechos observados antes de congelar (sobre el release publicado, no son resultados de E2–E9)

- GeoPackages: `elevacion_media` y `pendiente_media` = NaN en 123/123 polígonos; sin
  `clave_estacion` (solo `VALUE`); CRS EPSG:6372; área mínima −0.017 km² (Bajío).
- DEMs en EPSG:6365 (geográfico): celda 1″ (≈30 m) y 0.5″ (≈15 m, Alta del Balsas).
  `threshold=1000` celdas, `snap_dist=0.01` grados.
- `estaciones_seleccionadas_hidrometricas.csv`: 101 filas (el texto dice 108).
- Serie hidrométrica: 10,594,758 filas en todo el registro (1922–2025); 934,402 gastos no
  nulos en 2010–2025.
- Imputación publicada: 128,195 días `calidad==1` en 49,576 rachas; 37,639 días (29 %) están
  dentro de huecos > 7 d (pandas `limit=7` rellena los primeros 7 días de cualquier hueco);
  16,007 valores imputados < 0 (no hay recorte a ≥ 0); existen rachas de 14 y 28 días
  (sospecha de filas `(clave, fecha)` duplicadas, se verifica en E1).
- `raw/_manifest.json` local: 49 entradas; no está en el bundle. `manifest_zenodo.json` sí
  cubre 3,587 archivos (SHA-256 + bytes + ruta).
- `ma7`/`ma30` del feature table incluyen el día t (`rolling` sin `shift`).
- El catálogo SIH no tiene campo de área de cuenca.

---

## E1 — Conciliación de conteos (R2)

- **Claim:** los conteos del artículo (547/2,659 estaciones; 10,594,758/55,590,466
  observaciones; 108 seleccionadas; composición de `calidad`; 101 → 123 subcuencas) se
  reproducen desde los archivos publicados, o se reemplazan por el valor que sí se reproduce.
- **Verificador:** `scripts/dib_01_reconcile_counts.py` sobre `data/` local (= bundle).
  Embudo por tipo: catálogo → región hidrológica → archivo descargado → ≥1 dato en 2010–2025
  → cobertura ≥ umbral (0.60 / 0.80) → dentro de algún bbox → con polígono.
  Cada observación se cuenta en tres formas: filas totales, filas no nulas, no nulas en
  2010–2025; y filas `(clave, fecha)` duplicadas.
- **Rechazo:** una cifra del artículo que no coincide con ninguna de las tres formas de
  conteo se marca `REJECTED` y se sustituye; no se admite "redondeo" ni "versión anterior"
  como explicación sin archivo que lo respalde. Cada estación faltante lleva motivo
  verificable (HTTP, archivo vacío, sin fila en catálogo); si no se puede determinar, se
  registra `motivo = desconocido`, no se infiere.

## E2 — Deduplicación de subcuencas (decisión 2 del autor)

- **Claim:** cada estación queda con un único polígono aplicando la regla congelada.
- **Regla (congelada, se aplica en este orden a cada estación con > 1 polígono):**
  1. Descartar el polígono que toca el borde del bbox de su unidad. "Toca" = distancia
     mínima entre el contorno del polígono y el contorno del bbox ≤ 1.5 × tamaño de celda
     del DEM de esa unidad, medida en EPSG:6372.
  2. Si ninguno o ambos tocan: conservar el de la unidad cuyo `region_hidrologica` (conf)
     coincide con el `region_hidrologica` de la estación en el catálogo.
  3. Si persiste el empate: conservar el de mayor área.
- **Verificador:** `scripts/dib_02_dedup_subbasins.py` sobre GeoPackages re-delineados con
  `clave_estacion` explícita. Salida `dedup_log.csv` con estación, unidades, distancia al
  borde, regla aplicada y polígono conservado.
- **Rechazo:** falla si alguna estación queda con 0 o > 1 polígono, si la regla se aplica
  fuera de orden, o si algún conservado toca el bbox sin quedar listado para Limitations.

## E3 — Imputación por enmascaramiento (R2, R4; decisión 1 del autor)

- **Claim:** el spline cúbico del pipeline (con respaldo lineal) es aceptable para huecos
  cortos frente a lineal y PCHIP.
- **Verificador:** `scripts/dib_03_imputation_masking.py`, semilla 20260926.
  - Universo: las 101 estaciones de `estaciones_seleccionadas_hidrometricas.csv`; verdad =
    valores `calidad==0` en 2010–2025.
  - Huecos artificiales L = 1…10 días; ≥ 2,000 por L, estratificados por estación (reparto
    igual; si una estación no tiene candidatos suficientes, el faltante se reparte entre las
    demás). Posición válida: L días observados más ≥ 3 días observados a cada lado; huecos de
    una misma estación separados ≥ 30 días.
  - Métodos: lineal; PCHIP; spline exacto del pipeline (`interpolate(method="cubic",
    limit=7, limit_area="inside")` sobre el registro completo de la estación, respaldo lineal
    si falla). Para L > 7, el spline del pipeline deja días sin imputar; se reportan aparte.
  - Métricas por día enmascarado: MAE y RMSE normalizados por la desviación estándar de la
    estación (valores `calidad==0`, 2010–2025); sesgo normalizado; tasa de sobreoscilación
    (valor fuera de [mín, máx] de los 3+3 vecinos observados); conteo de negativos antes y
    después de recortar a ≥ 0. Subconjunto de ascensos: primer valor posterior > 1.5 × último
    valor anterior.
  - "Global" = todos los días enmascarados de L = 1…6 juntos (mismo número de huecos por L).
- **Rechazo (congelado del brief):** el spline se sostiene solo si
  (a) nRMSE_global(spline) ≤ 1.10 × min(nRMSE_global de los tres métodos), **y**
  (b) el pipeline publicado no produce negativos. Nota de congelación: (b) "cero negativos
  tras el recorte" es cierto por construcción; como el pipeline publicado **no recorta** y
  tiene 16,007 imputados negativos, (b) se evalúa sobre la salida tal como la produce el
  pipeline, y aparte se reporta la variante con recorte.
- Si falla (a) o (b): **detenerse e informar al autor** antes de cambiar cualquier dato.
- También se reporta: curva de error vs L (1…10) y dónde el nRMSE del mejor método supera
  0.5 (umbral descriptivo para discutir el límite de 7 días, no es regla de rechazo), y el
  diagnóstico de rellenos parciales de huecos > 7 d en el dato publicado.

## E4 — Outliers (R2)

- **Claim:** la regla 3 × P99.9 marca y conserva valores; no borra extremos reales.
- **Verificador:** `scripts/dib_04_outliers.py`. Lista de todos los `calidad==2` con
  estación, fecha, valor, P99.9 local y razón valor/P99.9; separación negativos vs > 3×P99.9;
  conteo y fracción por estación; figura con 2–3 series de ejemplo.
- **Cruce con eventos:** solo eventos con fuente verificable (DOI o reporte oficial
  consultado). El registro hidrométrico termina el 2025-09-03, así que las inundaciones de
  octubre de 2025 **no son evaluables**; se buscan eventos documentados dentro del registro.
- **Rechazo:** falla "conserva" si algún `calidad==2` tiene valor nulo; falla "no borra
  extremos reales" si algún pico de un evento documentado queda marcado como `calidad==2`
  (se reporta cuál). Sin evento verificable, el cruce queda `OPEN`, no `SUPPORTED`.

## E5 — Validación independiente de subcuencas (R2; no bloqueante)

- **Claim:** el área delineada concuerda con una referencia independiente.
- **Verificador:** `scripts/dib_05_subbasin_validation.py`. Referencia A (catálogo SIH): no
  disponible, el catálogo no trae área. Referencia B: `UPLAND_SKM` de HydroRIVERS en el
  tramo más cercano al pour point ajustado, dentro de 1,000 m; si no hay tramo a ≤ 1,000 m,
  "sin referencia" (HydroRIVERS omite cauces < 10 km² de área aportante).
- **Métricas:** error relativo de área; mediana |error|; fracción dentro de ±20 %; lista de
  casos > 50 % con diagnóstico (snap a cauce equivocado, truncamiento por bbox, presa/canal,
  cuenca menor al umbral de HydroRIVERS).
- **Rechazo:** no bloquea la revisión; se reporta lo que salga. Se rechaza la atribución de
  un diagnóstico si no hay evidencia del archivo (p. ej. distancia de snap, contacto con bbox).

## E6 — Sensibilidad DEM 15 m vs 30 m (R2)

- **Claim:** cuantificar cuánto cambian área, elevación media, pendiente media e IoU al
  pasar Alta del Balsas de 15 a 30 m.
- **Verificador:** re-delineación de Alta del Balsas a 30 m desde el mismo mosaico de 15 m
  con `Resampling.average`. Primaria: mismos parámetros (1000 celdas, 0.01°). Secundaria:
  umbral equivalente en área (250 celdas a 30 m) para separar el efecto de resolución del
  efecto de umbral. Pendiente calculada con tamaño de celda en metros (ver corrección de
  atributos).
- **Rechazo:** descriptivo; falla solo si la comparación se hace con atributos calculados de
  forma distinta entre resoluciones.

## E7 — Parámetros de delineación (R3)

- **Verificador:** extraer de código y config `extract_streams` (celdas y km² a 15 y 30 m,
  calculado con el tamaño real de celda a la latitud media de cada bbox) y `snap_pour_points`
  (grados y metros). Salida `delineation_params.json`; los parámetros pasan al YAML.
- **Rechazo:** falla si el valor reportado no es el que ejecutó la corrida que produjo los
  GeoPackages publicados.

## E8 — Fig. 8 desestacionalizada (R4)

- **Verificador:** anomalía por estación = valor − climatología de día del año (media
  2010–2025 suavizada con media móvil circular de 31 días), dividida entre la desviación
  estándar de la estación; índice regional = media diaria de anomalías entre estaciones de
  RH 12, 18 y 26. Correlación de Pearson y Spearman con rezagos 0–30 días.
- **Rechazo:** falla si la etiqueta sigue diciendo "national" o si la curva mostrada es la
  cruda.

## E9 — Baseline (R2; decisión 3 del autor)

- **Claim:** una regresión Ridge por estación sobre lags supera o no a persistencia a 1 día.
- **Verificador:** `scripts/dib_09_baseline.py` + notebook equivalente. Emisión en t,
  objetivo Q(t+1) con `calidad==0`; predictores en t: Q(t), lag1, lag3, lag7, lag14, lag30,
  ma7, ma30. Persistencia = Q(t). Partición 2010–2020 / 2021–2022 / 2023–2025; alpha en
  `logspace(-3, 3, 13)` elegido por NSE de validación. Mínimos por estación: 365 / 90 / 90
  objetivos válidos en train / val / test; las excluidas se cuentan. Métricas: NSE y KGE en
  test; mediana e IQR entre estaciones.
- **Rechazo:** falla si algún predictor usa información posterior a t, o si alpha se elige
  con datos de test. No se reporta la tabla si se excede el límite de 10 min en laptop sin
  declararlo.

---

## Estado

| Exp. | Estado | Evidencia | Decisión |
| --- | --- | --- | --- |
| E1 | REJECTED (cifras del artículo) / SUPPORTED (embudo reconstruido) | `*_v2026_06.*`, `*_v2026_10.*` | Cifras finales sobre v2026.10 en `numbers.json` |
| E2 | OPEN | — | — |
| E3 | REJECTED (el spline no se sostiene; fallan a y b) | ver abajo | Detenido; consulta al autor (regla del brief) |
| E4 | SUPPORTED (conserva) / REJECTED (no marca extremos: 3/18 picos de sep-2013 marcados) | ver abajo | Declarar en el artículo; no cambiar la regla |
| E5 | REJECTED (polígonos v2026.06 no representan la cuenca aforada) | ver abajo | PIVOT: polígonos retirados en v2026.10 |
| E6 | SUPPORTED (a nivel DEM, ver Enmiendas) | `e6_dem.json` | Tabla corta en Limitations |
| E7 | SUPPORTED (parámetros de v2026.06 documentados) | `delineation_params.json` | Se reportan para trazabilidad; el producto se retira |
| E8 | SUPPORTED | `precip_streamflow_lagcorr.csv` | Fig. 7 nueva (antes Fig. 8) |
| E9 | SUPPORTED (baseline descriptivo) | ver abajo | Tabla de 2 filas con la variante enmendada |

## Evidencia por experimento

### E1 (2026-09-26, `dib_01_reconcile_counts.py`, sobre el release publicado)

Evidencia cruda:
- Hidro: catálogo 1,189 → candidatas 550 → descargadas 547 → con dato 2010–2025: 325 →
  cobertura ≥ 0.60 (regla de `05 --refine`, sobre CSV crudos): **101** (el artículo dice 108;
  108 es `metrics.json`, calculado sobre el parquet con imputados y duplicados) → dentro de
  algún bbox: **95** (el artículo dice 101). 6 principales fuera de todo bbox: CHAMC, CMNMC,
  LPNMC, LPSMC, LPZMC, TLAMC. 125 filas estación–unidad; 23 estaciones en ≥ 2 unidades.
- Clima: 7,499 → 2,731 → 2,659 → 1,899 con dato → 415 con cobertura ≥ 0.80 (coincide).
- Faltantes (3 hidro, 72 clima): las 75 URLs responden HTTP 404 al 2026-09-26.
- Filas hidro: 10,594,758 totales en todo el registro (1922–2025), de las cuales **204,614 son
  (clave, fecha) duplicadas** (12 estaciones GJ; causa: 3 fragmentos de corridas de prueba
  del 20, 21 y 23 de junio que `to_parquet` no borró; están en el zip de Zenodo). Con valor:
  6,028,438; con valor en 2010–2025: 934,402. Clima: 55,590,466 filas; 36,744,755 con valor;
  6,794,778 en 2010–2025; 0 duplicados.
- `calidad` hidro 98.78/1.21/0.005 % del artículo cuenta filas vacías como "originales"; sobre
  filas con valor es 97.86/2.13/0.0086 %, y en 2010–2025 93.12/6.86/0.02 % (con duplicados).
- "2 estaciones sin polígono" = una sola, **BRAGJ**, sin polígono en Bajío y en Pánuco: su
  punto ajustado cae en la misma celda que SL2GJ.
- Correspondencia VALUE→estación de los polígonos publicados reconstruida y verificada:
  estación→polígono mediana 15.7 m, máx. 499 m (< radio de ajuste ≈ 1.07 km).

Veredicto: las cifras 108, 101-en-bbox, 10.6 M/55.6 M "en 2010–2025" y 98.78/1.21/0.005 %
son `REJECTED`; se sustituyen tras limpiar el dato. Acción ya autorizada: fragmentos
movidos a `data/interim/dib_revision/stale_fragments/` (93 archivos); `persist.write_parquet`
ahora limpia el directorio antes de escribir.

### E3 (2026-09-26, `dib_03_imputation_masking.py`, semilla 20260926, dato sin duplicados)

Evidencia cruda (L = 1–6, 12,000 huecos, 42,000 días, 101 estaciones):

| Método | nRMSE | nRMSE recorte ≥0 | nMAE | sobreoscilación | negativos | nRMSE ascensos |
| --- | --- | --- | --- | --- | --- | --- |
| lineal | 0.734 | 0.734 | 0.187 | 0 % | 0 | 1.212 |
| PCHIP | 0.746 | 0.746 | 0.185 | 0 % | 0 | 1.243 |
| spline pipeline | 2.098 | 1.086 | 0.357 | 52.5 % | 5,740 | 2.086 |

- Regla (a): 2.098 > 1.10 × 0.734 = 0.807 → **falla**. Robustez: spline peor que lineal en
  95/101 estaciones (91 por > 10 %); sin las 5 estaciones más extremas, 1.117 vs 0.632.
- Regla (b): el dato publicado (sin duplicados) tiene **13,279** gastos imputados < 0 → **falla**.
- Diagnóstico del dato publicado: 120,919 días imputados; 29.8 % de ellos dentro de huecos
  > 7 días (el `limit=7` de pandas llena los primeros 7 días de cualquier hueco).
- Clima (fuera del alcance de E3, mismo mecanismo): 228,533 de 556,208 precipitaciones
  imputadas son negativas (41 %).
- Curva nRMSE(lineal) vs L: 0.63, 0.61, 0.57, 0.61, 0.70, 0.94, 0.92, 0.75, 0.71, 0.85 para
  L = 1…10. El umbral descriptivo 0.5 congelado no discrimina (lineal lo supera desde L = 1).

Veredicto: `REJECTED` para "el spline es aceptable". Por la regla del brief, se detiene
cualquier cambio de imputación hasta la decisión del autor.

### E2 (2026-09-26, `dib_02_dedup_subbasins.py`, sobre la re-delineación con parámetros publicados)

- La re-delineación con el código corregido reproduce 108/123 polígonos publicados con
  IoU ≥ 0.999; 15 difieren (7 con IoU ≈ 0: estaciones junto a confluencias).
- 125 filas estación–unidad → 123 polígonos → 94 tras deduplicar; reglas: 14 × región,
  4 × borde, 3 × área, 1 × borde+área. BRAGJ queda con 0 polígonos (salida compartida con
  SL2GJ) → la regla "una por estación" **falla** por esa estación. 9 conservados tocan el bbox.
- Veredicto: `REJECTED` como producto final (ver E5); queda como registro del problema de
  v2026.06. **Superado por el rediseño**: con una cuenca completa por aforo no hay duplicados.

### E5 (2026-09-26, `dib_05_subbasin_validation.py`, 94 polígonos deduplicados)

- 88/94 con tramo HydroRIVERS a ≤ 1 km. Mediana |error de área| = **99.5 %**; dentro de
  ±20 %: 1/88. Mismo resultado para las áreas publicadas v2026.06 (mediana 99.5 %).
- E5b (`dib_05b_snap_diagnosis.py`): en 39/88 el ajuste Jenson fue a una celda con ≥ 10×
  menos acumulación que la máxima en el radio; aun con la máxima acumulación en el radio
  la mediana |error| es 97.3 % (72 % subestima > 50 %). Celdas sin dato del CEM por unidad:
  Santiago 48.9 %, Alta del Balsas 19.8 %, Cutzamala 11.1 %, Pánuco 6.2 %, Bajío 3.0 %.
- Causas con evidencia: (1) ajuste al cauce más cercano en una red densa; (2) el DEM de
  cada unidad no contiene la cuenca aguas arriba; (3) `watershed` con varios pour points
  produce áreas incrementales (cada celda va al primer aforo aguas abajo), no la cuenca
  completa de cada aforo.
- Veredicto: `REJECTED` — el diseño por bbox no recupera la cuenca aforada. Decisión del
  autor (2026-09-26): **rediseñar** (E5-R), después sustituida por retirar los polígonos
  (ver Enmiendas).
- Reproducibilidad (2026-09-26): una segunda corrida con el mismo código de auditoría
  (`audit_code/redelineate_v2026_06.py`) reproduce los conteos y los polígonos de Cutzamala
  y Lerma Alto, pero no bit a bit los de Santiago, Alta del Balsas y Pánuco (diferencias de
  área de hasta 55.6 km²): la cadena no es determinista en estaciones junto a confluencias.
  E2 y E5 sobre la segunda corrida dan el mismo resultado (94 polígonos; BRAGJ sin polígono;
  9 truncados; mediana |error| 99.5 %; 1/88 dentro de ±20 %). La conclusión no depende de
  la corrida.

### E4 (2026-09-26, `dib_04_outliers.py`, dato v2026.10)

- 507 registros `calidad == 2`; **0 con valor nulo** → "marca y conserva": `SUPPORTED`.
- 243 negativos (242 en B26424) y 264 altos; 130 estaciones (56 del conjunto principal).
  De los altos, 114 son picos de un día ≥ 10 × ambos vecinos; máximo 293,588 m³/s (ATCHD,
  2025-01-15; 336 m³/s/km² con el área HydroRIVERS): errores de captura evidentes.
- Evento documentado (inundaciones de sep-2013, Ingrid y Manuel; Pedrozo-Acuña et al., 2014,
  doi:10.1002/wea.2355, verificado en Crossref): 18 estaciones principales con pico ≥ P99.9;
  **3 picos marcados** (TMTSL 4,023; TBLSL 2,172; SGBTP 1,205 m³/s; Pánuco), coherentes con
  picos de estaciones vecinas el mismo día.
- Veredicto: "no marca extremos reales" `REJECTED` (3/18); "los conserva" `SUPPORTED`.
  Consecuencia para el artículo: no descartar `calidad == 2` a ciegas; se entrega la tabla de
  auditoría (razón con vecinos, caudal específico). Oct-2025: no evaluable (registro termina
  2025-09-03).

### E9 (2026-09-26, `dib_09_baseline.py`, feature table v2026.10 en m³/s; 1.9 s)

| Variante | Modelo | n | NSE mediana [IQR] | KGE mediana [IQR] |
| --- | --- | --- | --- | --- |
| congelada | persistencia | 97 | 0.453 [−0.033, 0.699] | 0.712 [0.464, 0.851] |
| congelada | Ridge | 97 | 0.330 [−0.033, 0.657] | 0.421 [−0.063, 0.708] |
| sin outliers en predictores | persistencia | 97 | 0.528 [0.125, 0.772] | 0.764 [0.545, 0.882] |
| sin outliers en predictores | Ridge | 97 | 0.594 [0.293, 0.717] | 0.642 [0.353, 0.815] |

- 4 estaciones excluidas (pocos datos o sin varianza en test). Ridge > persistencia en NSE:
  69/97 (congelada), 75/97 (enmendada).
- La variante congelada deja entrar valores `calidad == 2` como predictores (CHPMX: NSE de
  persistencia −28,509). Ver enmienda. Veredicto: `SUPPORTED` como baseline descriptivo.

### E6 (2026-09-26, `dib_06_dem_resolution.py`, reformulado a nivel DEM)

- Alta del Balsas, CEM 0.5″ (≈14.7 × 15.4 m) vs agregado a 1″ con Resampling.average.
- Elevación: sesgo −0.02 m, RMSD 2.38 m. Pendiente (m/m): media 0.197 → 0.185 (−6.1 %),
  mediana 0.142 → 0.131, P90 0.431 → 0.416 (−3.4 %); celdas > 0.3: 22.8 % → 20.8 %.
- Veredicto: `SUPPORTED` como cuantificación descriptiva para Limitations.

### E8 (2026-09-26, `09_make_report_figures.py` → Fig7_precip_streamflow, 2010–2025)

- Agregado de las regiones 12, 18 y 26 (ya no "national"). Anomalías estandarizadas por
  estación respecto de su climatología de día del año (media móvil circular de 31 días);
  gasto con `calidad == 0`, precipitación sin outliers.
- Desestacionalizado: máximo a 2 días (Pearson 0.54; Spearman 0.44), cae a ≈ 0.15 a 20–30
  días. Sin desestacionalizar: Pearson 0.62–0.70 en todos los rezagos (inflado por el ciclo
  estacional compartido). Veredicto: `SUPPORTED`.

## E5-R — delineación rediseñada (congelado 2026-09-26, antes de ejecutarla)

- **Claim:** una cuenca completa por aforo, delineada sobre el CEM 3.0 en un dominio que
  contiene toda la red aguas arriba, concuerda en área con HydroRIVERS.
- **Método (congelado):** dominio = extensión de la red HydroRIVERS aguas arriba del tramo
  de mayor `UPLAND_SKM` a ≤ 0.01° de la estación + 0.1° de margen (estaciones sin tramo:
  ±0.25°); si el polígono resultante toca el borde del dominio (≤ 2 celdas) se amplía 50 %
  y se repite (máx. 3 veces) y si sigue tocando se marca `truncada`. Mosaico de teselas
  estatales CEM 3.0 15 m remuestreado con `Resampling.average` a 30 m (15 m en las
  estaciones de Alta del Balsas), o a la resolución más fina que quepa en 220 M celdas.
  Cadena: fill_depressions → d8_pointer → d8_flow_accumulation → `snap_pour_points`
  (máxima acumulación a ≤ 0.01°) → `watershed` con **un solo** pour point por estación.
- **Verificador:** área geodésica del polígono vs `UPLAND_SKM` del tramo de mayor área a
  ≤ 0.01° de la estación (mismo criterio de ajuste en ambos lados, para que se comparen
  áreas y no la elección del río). Solo estaciones con tramo HydroRIVERS y cobertura CEM
  completa; se reporta aparte la sensibilidad usando el tramo más cercano.
- **Rechazo / éxito (congelados):** `SUPPORTED` si mediana |error| ≤ 10 % **y** ≥ 75 % de
  estaciones dentro de ±20 %. `REJECTED` si mediana |error| > 25 % **o** < 50 % dentro de
  ±20 %. Intermedio → `OPEN` (se reporta tal cual). No se ajustan radio, umbral ni margen
  después de ver el resultado. Rechazo adicional: un polígono `truncada` no cuenta como
  acierto aunque su área coincida.

## Enmiendas

- **2026-09-26 — E5-R retirado antes de evaluarse.** Al probar la delineación rediseñada se
  encontró evidencia adicional: (i) `snap_pour_points` de WhiteboxTools no eligió la celda
  de máxima acumulación del radio sobre el CEM geográfico (ATOMX: 5.3 km² elegidos habiendo
  121 km² dentro del radio); (ii) el acondicionamiento hidrológico produce elevaciones
  irreales sobre el CEM en grados: máximo del DEM rellenado 47,985 m (Lerma Alto), 149,494 m
  (Bajío) y 175,060 m (Pánuco) en el diseño publicado, y 162,129 m en un dominio de prueba
  con `fill_depressions` (con y sin `flat_increment=0.001`) y con
  `breach_depressions_least_cost`. Corregirlo exigiría teselas CEM adicionales, un nuevo
  acondicionamiento y otra validación. **Decisión del autor:** retirar los polígonos de
  subcuencas en v2026.10 y entregar en su lugar el vínculo de cada estación con HydroRIVERS
  (tramo y área aportante de referencia). E5-R no se ejecuta; ningún resultado de E5-R se
  reporta. E6 se reformula a nivel de DEM (sin polígonos).
- **2026-09-26 — E9, variante adicional (después de ver resultados).** El verificador
  congelado filtraba la calidad solo en el objetivo; los predictores podían contener valores
  `calidad == 2` (errores de captura de hasta 293,588 m³/s), lo que no representa el uso
  recomendado de la bandera. Se añade la variante "sin outliers en predictores" (excluye
  emisiones cuya ventana t−30…t contiene `calidad == 2`). La variante congelada se conserva
  y se reporta; el artículo usa la enmendada y lo declara.

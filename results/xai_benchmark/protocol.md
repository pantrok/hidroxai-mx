# Protocolo · comparación de arquitecturas, explicabilidad y alertas difusas (HidroXAI-MX)

Proyecto IND-2026-0335 (IPN, PICDT 2026), objetivos OE2–OE5.

**Estado: CONGELADO el 2026-10-10, con aprobación del autor, antes de entrenar o evaluar
cualquier modelo.** El SHA-256 de este archivo y el commit quedan en `proof_ledger.md`. Desde
aquí ningún umbral ni criterio cambia: un cambio posterior es una enmienda fechada,
etiquetada *post hoc*, y la variante original también se reporta.

## 1. Datos

- Snapshot **v2026.10** (Zenodo 10.5281/zenodo.23150556), sin modificar:
  `data/features/feature_table.parquet` (gasto en m³/s, `precip_idw_mm`) y las series
  canónicas. Huella del archivo registrada en `dvc.lock`.
- Ninguna cifra se escribe a mano: todas salen de los scripts `scripts/xai_*.py` hacia
  `results/xai_benchmark/numbers.json`, cada bloque con su campo `"fuente"`.

## 2. Estaciones y grupos

- Universo: las 101 estaciones hidrométricas seleccionadas (`estaciones_hidrorivers.csv`).
- **Cuencas piloto** (grupo de entrenamiento y de reporte), a partir de `unidad_piloto`:
  Lerma–Santiago = Lerma Alto + Bajío + Santiago; Pánuco; Alta del Balsas; Cutzamala.
- **Las 6 estaciones fuera de toda unidad** (CHAMC, TLAMC en la región 12; CMNMC, LPNMC,
  LPSMC, LPZMC en la región 18) **no se modelan ni se evalúan**: no pertenecen a ninguna
  cuenca piloto. Se listan en el reporte.
- **Cutzamala tiene una sola estación**: se entrena su modelo de cuenca y se reportan sus
  métricas, pero no entra en inferencias por cuenca (no hay bootstrap con n = 1). Sí entra
  en el agregado de las 95 estaciones.
- Inferencia por cuenca solo con ≥ 8 estaciones evaluables. Inferencia agregada: todas las
  estaciones evaluables de las cuatro cuencas.

## 3. Muestras, entradas y particiones

- Calendario diario por estación. Fecha de emisión *t*; ventana de entrada *t*−29…*t*
  (30 días); objetivo: gasto en *t*+*h*, con *h* ∈ {1, 7, 14} días.
- Entradas (6 canales × 30 días): gasto, media móvil de 7 días, media móvil de 30 días
  (columnas de la feature table), `precip_idw_mm`, seno y coseno del día del año
  (2π·doy/365.25). Ningún modelo recibe precipitación futura.
- **Muestra válida** si: los 30 días tienen gasto, medias móviles y precipitación (sin NaN);
  ningún día de la ventana tiene `calidad = 2` (misma regla que la variante enmendada del
  baseline E9, aquí preregistrada); el objetivo existe y tiene `calidad = 0` (observación
  original). Se admiten valores imputados (`calidad = 1`) en las entradas.
- Transformación: gasto y medias móviles con log1p; precipitación con log1p; luego
  estandarización por estación con media y desviación **del periodo de entrenamiento**.
  Las métricas se calculan en m³/s, tras invertir la transformación.
- **Particiones cronológicas.** Una muestra pertenece a un periodo si el primer día de la
  ventana y el día objetivo caen en él:
  - entrenamiento 2010-01-01 – 2020-12-31;
  - validación 2021-01-01 – 2022-12-31;
  - prueba 2023-01-01 – 2025-09-03 (fin del registro).
- **Estación evaluable** en prueba, por horizonte: ≥ 180 muestras válidas y varianza > 0 del
  gasto observado. Las no evaluables se listan con su motivo.
- **Walk-forward anual (robustez):** para cada año *Y* = 2021…2025: entrenamiento
  2010 – *Y*−2, validación *Y*−1, prueba *Y* (2025 hasta 09-03). Configuraciones fijadas en la
  partición principal, una semilla.

## 4. Modelos (RQ1)

Referencias: **persistencia** Q̂(*t*+*h*) = Q(*t*); **climatología** = media por día del año
del periodo de entrenamiento de la estación, con suavizado circular de 31 días.

| Modelo | Ámbito | Configuración fija | Malla (2 valores) |
|---|---|---|---|
| ARIMA (statsmodels) | por estación, CPU | log1p(Q) de entrenamiento; orden por AIC con p, q ∈ {0…3}, d ∈ {0, 1}; pronóstico a *h* pasos con filtro de Kalman actualizado con las observaciones, sin reestimar | — |
| XGBoost | global por cuenca y horizonte | entrada = ventana aplanada (180 columnas); lr 0.05; hasta 2000 árboles con early stopping de 100 rondas en validación; subsample 0.8; colsample 0.8 | max_depth ∈ {4, 6} |
| TCN | global por cuenca y horizonte | 4 bloques residuales, kernel 3, dilaciones 1-2-4-8 (campo receptivo 31), dropout 0.1 | canales ∈ {32, 64} |
| ConvNeXt-1D | global por cuenca y horizonte | proyección 1×1; 3 bloques (convolución depthwise kernel 7, LayerNorm, MLP ×4, GELU); pooling global | dimensión ∈ {32, 64} |
| PatchTST | global por cuenca y horizonte | parches de 5 días con paso 5 (6 parches) por canal, 2 capas, 4 cabezas, dropout 0.1; cabeza lineal sobre las representaciones de todos los canales | d_model ∈ {32, 64} |

- Informer: fuera, salvo que sobre presupuesto (sección 8).
- Entrenamiento profundo común: PyTorch puro; AdamW (lr 1e-3, weight decay 1e-4); lote 256;
  pérdida MSE sobre el objetivo estandarizado; hasta 100 épocas; early stopping con
  paciencia 10 sobre la pérdida de validación; checkpoint por época (reanudable).
- **Semillas:** 20261010, 20261011, 20261012 (XGBoost y modelos profundos). La predicción
  evaluada es la media de las tres semillas; su dispersión se reporta.
- **Selección de configuración:** por modelo y horizonte, la de mayor mediana de NSE de
  validación (media de semillas) sobre las cuatro cuencas; en empate, la más pequeña.
- **Métricas por estación (prueba):** NSE, KGE (Gupta et al., 2009), RMSE (m³/s) y
  *skill score* contra persistencia SS = 1 − MSE_modelo / MSE_persistencia.
- **Agregación:** mediana e IQR por cuenca, horizonte y agregado.
- **Comparación pareada:** diferencias por estación; bootstrap de estaciones con 10,000
  réplicas (semilla 20261010) → IC 95 % de la mediana.

## 5. Explicabilidad (RQ2)

- **Muestra fija:** por cuenca y horizonte, hasta 2,000 ventanas de prueba, estratificadas por
  estación (semilla 20261010). Es la misma muestra para todos los modelos.
- **XGBoost:** TreeSHAP (contribuciones nativas de XGBoost) → 180 atribuciones.
- **Modelos profundos:** Integrated Gradients (Captum).
  - Línea base: vector cero en el espacio estandarizado, es decir, la media de entrenamiento
    de la estación para cada canal (0 para seno y coseno).
  - 64 pasos; se reporta el error de completitud.
- **PatchTST:** además, mapas de atención por parche (promedio de capas y cabezas);
  descriptivo.
- **Importancia:** |atribución| normalizada a suma 1 por ventana y promediada en la muestra
  (y entre semillas). Resultado: una matriz variable × rezago (6 × 30) por modelo, cuenca y
  horizonte.
- **Concordancia:** correlación de Spearman entre los vectores de 180 importancias para cada
  par de modelos. Se resume por cuenca y horizonte con la mediana de los 6 pares.
- **Contraste físico:** pico de correlación precipitación–gasto a 2 días en el artículo de
  datos (`metrics.json`, `fig7`). El rezago se mide **respecto al día objetivo**
  (rezago de ventana + *h*).

## 6. Alertas difusas (RQ3)

- **Eventos de referencia:** gasto observado en *t*+*h* > P90 y > P99 de la estación
  (percentiles de las observaciones originales del periodo de entrenamiento).
- **Ensamble:** 4 modelos aprendidos (XGBoost, TCN, ConvNeXt-1D, PatchTST) × 3 semillas
  = 12 miembros.
- **Entradas del sistema Mamdani:**
  - *percentil* = percentil, en la distribución de entrenamiento de la estación, de la media
    del ensamble;
  - *dispersión* = rango intercuartílico de los percentiles de los 12 miembros.
- **Funciones de pertenencia (fijas):**
  - percentil: bajo = trapecio (0, 0, 0.70, 0.80); alto = triángulo (0.70, 0.85, 0.92);
    muy alto = triángulo (0.88, 0.94, 0.985); extremo = trapecio (0.97, 0.99, 1, 1);
  - dispersión: baja = trapecio (0, 0, 0.05, 0.15); alta = trapecio (0.05, 0.15, 1, 1);
  - salida *nivel* ∈ [0, 3]: triángulos centrados en 0 normal, 1 vigilancia, 2 alerta y
    3 emergencia.
- **Inferencia:** mín–máx y defuzzificación por centroide; el nivel es el entero más cercano.
- **Reglas:**

| Percentil | Dispersión baja | Dispersión alta |
|---|---|---|
| bajo | normal | normal |
| alto | vigilancia | vigilancia |
| muy alto | alerta | vigilancia |
| extremo | emergencia | alerta |

- **Decisión binaria:**
  - sistema difuso: evento P90 si el nivel es ≥ alerta; evento P99 si el nivel es
    emergencia;
  - referencia (umbral simple sobre la media del ensamble): evento P90 si el percentil es
    ≥ 0.90; evento P99 si es ≥ 0.99.
- **Métricas:** tasa de aciertos (POD), razón de falsas alarmas (FAR) y CSI, con tablas de
  contingencia sumadas sobre las estaciones del grupo. Bootstrap de estaciones (10,000)
  para ΔCSI = CSI_difuso − CSI_umbral.

## 7. Hipótesis y criterios (congelados al aprobar)

| ID | Afirmación | SUPPORTED | REJECTED | Intermedio |
|---|---|---|---|---|
| H1 | Los modelos aprendidos superan a la persistencia a 7 y 14 días (agregado). | IC 95 % de la mediana de SS > 0 para ≥ 3 de los 4 modelos aprendidos en ambos horizontes | ningún modelo con IC > 0 en ningún horizonte | OPEN |
| H1-b | Algún modelo profundo supera a XGBoost (agregado, por horizonte). | IC 95 % de la mediana de ΔNSE (profundo − XGBoost) > 0 | IC < 0 para los tres modelos profundos | OPEN |
| H2-a | Las arquitecturas coinciden en qué variables y rezagos importan. | mediana de Spearman entre pares ≥ 0.5 en ≥ 2/3 de las combinaciones cuenca (≥ 8 estaciones) × horizonte | mediana < 0.3 en la mayoría | OPEN |
| H2-b | El rezago de precipitación más importante es físicamente consistente (*h* = 1). | ≥ 75 % de los pares (modelo, cuenca con ≥ 8 estaciones) con el rezago de precipitación más importante en 1–3 días respecto al objetivo | < 50 % | OPEN |
| H3 | El sistema Mamdani da mejores alertas que el umbral simple. | IC 95 % de ΔCSI > 0 para eventos P90 en *h* = 1 y *h* = 7 (agregado) | IC < 0 en alguno de los dos, o IC que contiene 0 en ambos | OPEN |

- Para *h* = 7 y 14, el análisis H2-b es descriptivo: ahí el rezago respecto al objetivo es
  siempre ≥ *h*.
- P99 y *h* = 14 en H3 son descriptivos, porque hay pocos eventos.
- Las métricas por cuenca son descriptivas, salvo en las cuencas con ≥ 8 estaciones, donde
  también se reportan sus IC.

## 8. Cómputo y presupuesto

- **Todo en CPU local** (decisión del autor, 2026-10-10): Intel Core Ultra 7 155H, 22 hilos,
  sin GPU NVIDIA. Incluye ARIMA, referencias, XGBoost, modelos profundos (PyTorch CPU),
  explicaciones y alertas.
- **Reanudación:** checkpoint por época de los modelos profundos. Si el presupuesto no
  alcanza, se prepara un notebook de Kaggle de respaldo, que clona el repositorio y descarga
  el ZIP público de Zenodo.
- **Fuera de git:** ni datos ni checkpoints ni artefactos pesados se versionan
  (`data/interim/xai_benchmark/`).
- **Manifiesto:** `results/xai_benchmark/compute_manifest.csv`, una fila por corrida (modelo,
  cuenca, horizonte, semilla, configuración, dispositivo, hilos, épocas, segundos, fecha). El
  reporte técnico da las horas de CPU; las de GPU, si se usa el respaldo.
- **Corridas del diseño principal:** 4 cuencas × 3 horizontes × 3 modelos profundos ×
  2 configuraciones × 3 semillas = 216 entrenamientos profundos, más XGBoost con la misma
  malla y ARIMA por estación.
- **Presupuesto:** ≤ 40 h de CPU para el diseño principal. El walk-forward profundo solo se
  corre si quedan ≥ 10 h. Lo que no se corra por presupuesto se reporta como no realizado.

## 9. Limitaciones declaradas de antemano

- Sin precipitación pronosticada: a 7 y 14 días, los modelos dependen de la persistencia y la
  estacionalidad.
- Seis estaciones excluidas y Cutzamala con una sola estación (sección 2; tratamiento
  aprobado por el autor el 2026-10-10).
- Integrated Gradients depende de la línea base elegida; se documenta y no se cambia.
- Los niveles de alerta son retrospectivos sobre 2023–2025; no son un sistema operativo.

# Proof ledger · HidroXAI-MX (modelos, explicabilidad, alertas difusas)

**Estado: protocolo CONGELADO el 2026-10-10.** Ningún modelo se había entrenado ni
evaluado al congelarlo.

## Congelamiento

| Campo | Valor |
|---|---|
| Fecha de aprobación | 2026-10-10 (autor) |
| SHA-256 de `protocol.md` | `8df99290b17bfc8a5a15dd46492772866ace00ec57d9687d0b5e73809db05799` (contenido con fin de línea LF, como queda en git) |
| Commit | el primero que contiene `results/xai_benchmark/protocol.md` |

Para verificarlo: `git show <commit>:results/xai_benchmark/protocol.md | sha256sum`.

## Afirmaciones, verificadores y criterios

Los criterios SUPPORTED/REJECTED son los de `protocol.md`, sección 7. Cada afirmación
queda `OPEN` hasta tener evidencia.

| ID | Verificador | Estado (2026-10-10) | Evidencia |
|---|---|---|---|
| H1 | Bootstrap de estaciones (10,000) de la mediana de SS contra persistencia, *h* = 7 y 14, agregado | **SUPPORTED** (4 de 4 modelos con IC > 0 en ambos horizontes) | `e_rq1.json` → `H1` |
| H1-b | Bootstrap de la mediana de ΔNSE (profundo − XGBoost), por horizonte | **h = 1: SUPPORTED** (solo TCN); **h = 7: OPEN; h = 14: OPEN** | `e_rq1.json` → `H1b` |
| H2-a | Mediana de Spearman entre pares de modelos sobre importancias 6 × 30 | **REJECTED** (0 de 9 combinaciones ≥ 0.5; 7 de 9 < 0.3) | `e_rq2.json` → `H2a` |
| H2-b | Proporción de pares (modelo, cuenca) con el rezago de precipitación más importante en 1–3 días respecto al objetivo, *h* = 1 | **SUPPORTED** (12 de 12) | `e_rq2.json` → `H2b` |
| H3 | Bootstrap de ΔCSI (difuso − umbral), eventos P90, *h* = 1 y 7, agregado | **SUPPORTED** (también en la variante pre-corrección) | `e_rq3.json` → `H3`; `rq3_pre_correccion/` |

Las cifras de cada veredicto están en `numbers.json` (bloques `rq1`, `rq2`, `rq3` y
`veredictos`), generado por `scripts/xai_08_report.py`.

## Enmiendas

El protocolo no ha cambiado (su SHA-256 coincide con el congelado; `numbers.json` →
`protocolo`). Hubo una corrección de implementación, posterior a ver resultados:

- **2026-10-10 · corrección *post hoc* del motor difuso.**
  - **Qué:** `TrapezoidalMF`, copiado de forecasting, daba pertenencia 0 en los hombros verticales
    de los trapecios (a = b o c = d): dispersión = 0 en "baja" y percentil = 1 en "extremo".
    Con miembros idénticos o un pronóstico por encima del máximo de entrenamiento, ninguna
    regla se activaba y el nivel quedaba en "normal". La fracción de muestras afectadas está en
    `numbers.json` → `rq3.variante_pre_correccion.muestras_afectadas`; por ejemplo, el 12.76 %
    de las muestras con percentil ≥ 0.90 tiene dispersión exactamente 0, típicamente en
    estaciones intermitentes con muchos empates en cero.
  - **Cuándo se detectó:** al revisar los resultados de `xai_07`, después de la primera
    ejecución.
  - **Corrección:** implementar los trapecios como los define el protocolo §6 (pertenencia 1 en
    el vértice). No cambia ninguna función de pertenencia, regla, umbral ni criterio. La prueba
    `test_vertical_shoulders_are_full_membership` lo cubre.
  - **Efecto:** H3 sigue SUPPORTED, con un efecto menor: ΔCSI P90 *h* = 1 pasa de 0.0918
    [0.0039, 0.174] a 0.0385 [0.0038, 0.0685] (`e_rq3.json` y `rq3_pre_correccion/e_rq3.json`).
  - **Reporte:** ambas variantes se reportan; la previa está en `rq3_pre_correccion/` y en
    `numbers.json` → `rq3.variante_pre_correccion`.
  - **Pendiente fuera de este repo:** el mismo defecto existe en `hidroxmx-forecasting`
    (`src/hidroxmx/alert/fuzzy.py`); no se toca porque ese repositorio está congelado.

## Notas de ejecución

- **2026-10-10, antes de cualquier resultado:**
  - **Piloto de tiempos** (`timing_pilot.json` y `timing_pilot_parallel.json`; solo
    entrenamiento y validación, sin tocar la prueba). En CPU local, las 216 redes del diseño
    principal requieren unas 30–35 h con dos procesos en paralelo si se detienen hacia la época
    40, y hasta ~80 h en el peor caso, frente al tope de 40 h de la sección 8.
  - **Decisión del autor:** las redes se entrenan en GPU de Kaggle, el respaldo previsto en
    la sección 8 (notebook `notebooks/kaggle_xai_train_nets.ipynb`, código fijado por
    commit). ARIMA, XGBoost, evaluación, explicaciones y alertas siguen en CPU local.
  - **Lo que no cambia:** arquitecturas, malla, semillas, entrenamiento, particiones y
    criterios. El manifiesto registra horas de GPU para las redes y de CPU para lo demás.
- **2026-10-10, integración de Kaggle:** `scripts/xai_03c_import_kaggle.py` → `kaggle_import.json`.
  - Están las 216 corridas con predicciones y pesos.
  - Las muestras coinciden una por una con las de CPU; solo difiere la precisión de las fechas
    (ns frente a µs).
  - No hay NaN.
  - Horas de GPU: `kaggle_import.json` → `gpu_h`.
  - La comprobación de muestras de `xai_05` se ajustó para comparar valores, no tipos.
- **2026-10-10, resúmenes descriptivos añadidos después de ver resultados** (no preregistrados;
  marcados como tales en `numbers.json`). Ninguno entra en un veredicto:
  - ΔNSE contra ARIMA;
  - participación de cada grupo de canales en la importancia;
  - fracción de pares cuyo rezago de precipitación más importante es el mínimo posible (= *h*);
  - frontera de decisión del sistema difuso;
  - desglose de alarmas por método (`rq3_mechanism.csv`).

## Especificación de ejecución del walk-forward (2026-10-11, antes de correrlo)

El protocolo §3 define el walk-forward:
- años de prueba *Y* = 2021…2025;
- entrenamiento 2010 – *Y*−2, validación *Y*−1 y prueba *Y* (2025 hasta el 09-03);
- configuraciones fijadas en la partición principal y una semilla.

Aquí se completan los detalles de ejecución. No cambia ningún criterio de H1–H3.

**Datos, modelos y cómputo**

- **Pliegues:** se mantienen los del protocolo (`walk_forward_partitions`). La propuesta del
  brief de robustez (entrenar hasta *Y*−1) no se adopta, porque dejaría al early stopping sin
  año de validación.
- **Semilla:** 20261010, para XGBoost y las redes.
- **Configuraciones:** las de `e_rq1.json` → `configuracion_elegida`, por modelo y horizonte.
- **ARIMA:** orden fijo por estación, el elegido en la partición principal
  (`arima_orders.csv`). Los coeficientes se reestiman en 2010 – *Y*−2 y el filtro corre como
  en el diseño principal. Una estación cuyo ajuste no converja queda fuera de ese año y se
  reporta.
- **Referencias:** climatología del entrenamiento del pliegue; persistencia sin cambios.
- **Escalado:** estadísticos por estación del entrenamiento del pliegue.
- **Reglas sin cambio:** muestra válida, pertenencia a la partición y estación evaluable
  (≥ 180 muestras y varianza > 0), aplicadas a cada año de prueba.
- **Salvedad conocida:** para *Y* = 2021 y 2022, la configuración (2 tamaños) se eligió con la
  validación principal 2021–2022, es decir, con esos años. Para 2023–2025 no hay traslape. Se
  declara y no se corrige.
- **Cómputo:**
  - redes en GPU de Kaggle (`notebooks/kaggle_xai_walk_forward.ipynb`, código fijado por
    commit); lo demás en CPU local;
  - filas `tipo = walk_forward` en el manifiesto.

**Análisis por año**

- **H1:** regla congelada en cada año. Nota: aquí se usa una semilla; el diseño principal
  promedia tres.
- **H1-b:** regla congelada por año y horizonte.
- **Ranking:** los 7 modelos se ordenan por NSE mediana en cada año y horizonte. Se reportan la
  W de Kendall entre los 5 años y la τ de Kendall media entre pares de años.
- **H2-a:** TreeSHAP e IG con el modelo del pliegue y la misma regla de muestra (≤ 2,000
  ventanas de la prueba del año, semilla 20261010). Regla congelada sobre las cuencas con
  ≥ 8 estaciones evaluables ese año.
- **H2-b:** por año, descriptivo.
- **H3:** con una semilla el ensamble tiene 4 miembros, no 12, y la dispersión es el IQR de 4
  percentiles. Por eso el ΔCSI anual es descriptivo. Como referencia se reporta también la
  partición principal con ese mismo ensamble de 4 miembros (semilla 20261010).

**Veredicto de robustez por hipótesis**

- Se aplica el criterio congelado en cada año y se compara con el veredicto principal (por
  horizonte en H1-b):
  - **estable** si coincide en 5 de 5 años;
  - **estable con excepciones** si coincide en 3 o 4, y se listan los años;
  - **inestable** si coincide en 2 o menos.
- No cambia los veredictos de §7.
- El ranking y el ΔCSI con 4 miembros se marcan "descriptivo (no preregistrado)".

### Ejecución del walk-forward

- **2026-10-11:**
  - **CPU** (`scripts/xai_09_walk_forward.py --models baselines xgboost`): referencias, ARIMA
    con el orden principal y XGBoost, en los 5 pliegues; filas `walk_forward` en el
    manifiesto.
  - **Evaluación parcial sin redes** (`scripts/xai_10_walk_forward_eval.py`).
  - **Comprobaciones superadas:** las funciones de `models/criteria.py` reproducen los
    veredictos oficiales, y `alert/evaluation.py` con 12 miembros reproduce el ΔCSI de
    `e_rq3.json`.
  - **Redes:** 180 corridas en Kaggle (`notebooks/kaggle_xai_walk_forward.ipynb`, código
    fijado en `b341ab3`). Verificación y horas de GPU: `e_walkforward.json` →
    `verificacion_redes`.
  - **Evaluación completa** con `xai_10` (todos los modelos y explicabilidad por año).

### Robustez (walk-forward; no cambia los veredictos de §7)

Veredicto anual con la regla congelada contra el veredicto principal, según la especificación
de arriba. Las cifras están en `e_walkforward.json` y en `numbers.json` → `walk_forward`.

| ID | Principal | 2021 | 2022 | 2023 | 2024 | 2025 | Robustez |
|---|---|---|---|---|---|---|---|
| H1 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | estable |
| H1-b, *h* = 1 | SUPPORTED | SUPPORTED | OPEN | OPEN | OPEN | OPEN | inestable |
| H1-b, *h* = 7 | OPEN | OPEN | OPEN | OPEN | REJECTED | OPEN | estable con excepciones (2024) |
| H1-b, *h* = 14 | OPEN | OPEN | REJECTED | OPEN | REJECTED | OPEN | estable con excepciones (2022, 2024) |
| H2-a | REJECTED | REJECTED | REJECTED | REJECTED | REJECTED | REJECTED | estable |
| H2-b | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | estable |
| H3 (4 miembros, descriptivo) | SUPPORTED | SUPPORTED | REJECTED | OPEN | SUPPORTED | SUPPORTED | estable con excepciones (2022, 2023) |

- **H3 de referencia:** en la partición principal, con el mismo ensamble de 4 miembros, H3 es
  SUPPORTED (`referencia_principal_4_miembros`).
- **Lectura de H1-b:** las excepciones son siempre a favor de XGBoost (REJECTED = los tres
  modelos profundos por debajo). El SUPPORTED principal a *h* = 1 no se repite fuera de 2021.
- **Semillas:** el walk-forward usa una semilla, mientras que el diseño principal promedia
  tres. Eso puede penalizar más a las redes que a XGBoost.
- **2026-10-11, descomposición del KGE** (descriptivo, no preregistrado; brief de robustez,
  tarea 2):
  - `xai_05` añade r, α y β por estación sin cambiar ninguna otra cifra (`rq1_summary.csv` y
    `e_rq1.json` idénticos);
  - el resumen está en `numbers.json` → `rq1.kge_componentes` y en la tabla T1b.

## Diagnósticos post hoc (2026-10-11, criterios escritos antes de calcular)

Vienen de la Fase A del manuscrito (afirmaciones C16 y C17). Son descriptivos (no
preregistrados, post hoc): no cambian ningún veredicto de §7, las métricas principales, H1,
H1-b ni el ranking. No se reentrena ningún modelo del diseño principal. Código:
`scripts/xai_11_diagnostics.py`; salida en `numbers.json` → `diagnosticos`.

### D1. ¿Fue 2023 un año seco en las cuencas piloto?

**Fuentes y estaciones**

- **Precipitación:** `precip_idw_mm` de las 95 estaciones hidrométricas modeladas (la misma
  entrada de los modelos). No se usan las 415 estaciones climatológicas.
- **Gasto:** `gasto_medio_m3s` con `calidad = 0`, de las mismas 95 estaciones.

**Periodos**

- **Periodo de cada año:** para 2021–2024, del 1-ene al 31-dic; para 2025, del 1-ene al 09-03.
- **Referencia:** el mismo periodo calendario en cada año de 2010–2020.

**Cobertura mínima**

- Una estación-año cuenta si tiene datos en ≥ 90 % de los días del periodo (precipitación) o
  `calidad = 0` en ≥ 70 % de los días (gasto).
- La referencia de una estación exige ≥ 5 años válidos en 2010–2020.

**Indicadores por estación**

- **Anomalía de precipitación:** total del periodo / mediana de los totales de referencia − 1.
- **Razón de gasto:** media del periodo / media de las medias anuales de referencia.

**Valor por cuenca:** mediana de las estaciones válidas de la cuenca en ese año. Las cuencas
con inferencia son Lerma–Santiago, Pánuco y Alta del Balsas; Cutzamala va solo como
descriptiva.

**Criterio**

- **SUPPORTED:** en ≥ 2 de las 3 cuencas con inferencia, 2023 tiene la menor razón de gasto
  de 2021–2025 **y** una anomalía de precipitación < 0.
- **REJECTED:** 2023 no es el año de menor razón de gasto en ninguna de las 3.
- **OPEN:** cualquier otro caso.

**Contraste** (descriptivo): NSE mediana por año del walk-forward (`e_walkforward.json`) y β
mediana de la climatología, en la prueba principal y por año del walk-forward.

**No se hace:** el cruce opcional con el Monitor de Sequía municipal, porque requiere
descargar un archivo oficial con autorización expresa.

### D2. ¿Por qué α y β < 1?

**(a) Corrección por *smearing* de Duan (1983)**

- **Predicción base:** la evaluada en el diseño principal. Para los 4 modelos aprendidos es la
  media de las 3 semillas en m³/s; también se aplica a ARIMA. ŷ_log = log1p(Q̂), que es exacto
  porque Q̂ = expm1(ŷ_log).
- **Factor por estación y horizonte:** f = media de exp(e) sobre las muestras de **validación**
  (2021–2022), con e = log1p(Q_obs) − log1p(Q̂). Una estación sin muestras de validación usa
  f = 1 y se cuenta.
- **Predicción corregida en prueba:** Q̂_c = (1 + Q̂)·f − 1.
- **Métricas:** mediana de β, α, r, NSE y KGE sobre las estaciones evaluables (las de
  `rq1_station_metrics.csv`), con y sin corrección, para h = 1, 7 y 14.
- **Criterio, a h = 1:**
  - **SUPPORTED (a)** si en ≥ 3 de los 4 modelos aprendidos |β_mediana − 1| se reduce en
    ≥ 0.03 con la corrección;
  - **REJECTED (a)** si |Δβ_mediana| < 0.01 en los cuatro;
  - **OPEN** en otro caso. α se reporta pero no decide.

**(b) XGBoost en espacio original** (solo CPU)

- **Diseño:** igual al de XGBoost del diseño principal (mismas entradas, profundidad elegida en
  `e_rq1.json`, 3 semillas, misma partición). Lo único que cambia es el objetivo: m³/s
  estandarizado por estación con media y desviación de las muestras de entrenamiento, sin
  log1p.
- **Predicción:** se devuelve a m³/s y se recorta en 0.
- **Métricas:** α, β, r, NSE y KGE medianas en las mismas estaciones evaluables, comparadas con
  XGBoost en log1p.
- **Criterio, a h = 1:**
  - **SUPPORTED (b)** si la mediana de α < 0.9;
  - **REJECTED (b)** si α ≥ 0.95;
  - **OPEN** si 0.9 ≤ α < 0.95.

### Resultados de los diagnósticos

`scripts/xai_11_diagnostics.py` → `e_diagnosticos.json`; `numbers.json` → `diagnosticos`.

| Diagnóstico | Veredicto | Evidencia |
|---|---|---|
| D1. 2023, año más seco del periodo de prueba en nuestros datos | **SUPPORTED** (3 de 3 cuencas con inferencia) | `sequia_2023.por_cuenca`, `diag_sequia_2023.csv` |
| D2-a. Sesgo de retransformación (smearing) | **SUPPORTED** (4 de 4 modelos aprendidos) | `kge_log1p.a_smearing`, `diag_kge_log1p.csv` |
| D2-b. Contracción de un predictor de media condicional (XGBoost sin log1p) | **SUPPORTED** | `kge_log1p.b_xgboost_espacio_original` |

**Notas sobre D1 y D2**

- **Cobertura en 2023:** en 2023 hay menos estación-años con cobertura suficiente de
  precipitación (`estaciones_precip` en `diag_sequia_2023.csv`). Las cuentas por cuenca y año se
  reportan.
- **Estaciones sin validación:** una estación evaluable no tiene muestras de validación y usa
  f = 1 (`estaciones_sin_validacion_f1`).
- **Alcance:** las métricas corregidas son diagnósticas y no sustituyen a las del diseño
  principal.

## Análisis de revisión (2026-10-16, criterios escritos antes de calcular)

**Origen y alcance**

- Vienen de la revisión simulada v0.6 del manuscrito: RR-1 a RR-4 y RR-6, más los opcionales
  RR-5 y RR-11.
- Son descriptivos (post hoc, posteriores a la revisión). No cambian ningún veredicto de §7 ni
  las cifras del diseño principal, y no se reentrena ningún modelo.

**Ejecución**

- Código: `scripts/xai_14_review_analyses.py`; salida en `numbers.json` → `revision_pares`.
- Semilla 20261010; bootstrap de 10,000 réplicas; IC percentiles.
- Esta sección se versiona en un commit propio, antes de cualquier resultado.

**Estado de lo guardado**

- Se usan las predicciones, los niveles de alerta por muestra (`data/interim/xai_benchmark/alerts`)
  y las métricas por estación ya guardadas.
- Las atribuciones por semilla y por ventana **no** se guardaron: `xai_06` solo escribió el
  mapa promedio de semillas. RR-2 requiere recalcularlas con los pesos guardados, y eso se hace
  solo con autorización del autor.

### RR-1. Separar el efecto del desacuerdo en H3

**Datos**
- Ensamble de 12 miembros del diseño principal; percentil *p* y dispersión *s* por muestra (los
  de `xai_07`).
- Eventos P90 y P99 con los percentiles de entrenamiento de cada estación.
- Estaciones evaluables y h = 1, 7 y 14.

**Variantes**

| Código | Variante | Decisión |
|---|---|---|
| F | Mamdani del diseño principal (corregido) | P90 si nivel ≥ alerta; P99 si nivel = emergencia |
| F0 | Mismas funciones y reglas, con *s* = 0 en todas las muestras | Igual que F |
| T | Umbral simple | *p* ≥ 0.90 (P90); *p* ≥ 0.99 (P99) |
| TV | Umbral con veto | *p* ≥ 0.90 y *s* < 0.15 (P90); *p* ≥ 0.99 y *s* < 0.15 (P99) |

Se comprueba que F reproduce `rq3_contingency.csv`.

**Contrastes**
- A = F0 − T; B = F − F0; C = TV − T; D = F − TV.
- Cada uno es un ΔCSI con tablas sumadas sobre las estaciones evaluables y bootstrap pareado de
  estaciones.
- Se reportan POD, FAR y CSI de cada variante.

**Criterios** (P90, h = 1; h = 7 como confirmación)
- **"Desacuerdo":** IC de B > 0 **y** IC de C > 0.
- **"Frontera":** IC de A > 0.
- **"Difuso aporta"** si IC de D > 0; **"equivalente"** si contiene 0; **"nítido mejor"** si
  IC de D < 0.

**Opcional**
- B por año del walk-forward (ensamble de 4 miembros), h = 1, P90.
- RR-11: valor económico relativo (Richardson, 2000) de F, F0, T y TV con P90, h = 1. Razón
  costo/pérdida de 0.01 a 0.99 en pasos de 0.01; tablas sumadas.

### RR-2. Techo de ruido de la concordancia de explicaciones

**Alcance**
- Cuencas con ≥ 8 estaciones (Lerma–Santiago, Pánuco, Alta del Balsas) × h = 1, 7 y 14.
- Misma muestra fija de `xai_06` (≤ 2,000 ventanas estratificadas, semilla 20261010).

**Recálculo**
- TreeSHAP para XGBoost e IG para las redes (64 pasos, línea base cero), por semilla y por
  ventana, con los pesos guardados.
- Comprobación: el mapa promedio de semillas debe reproducir `rq2_importance.csv` (diferencia
  absoluta máxima < 1e-6).

**Mapas**
- Importancia |atribución| normalizada por ventana y promediada (6 × 30), como en el protocolo.
- **Intra-modelo entre semillas:** medida entre los mapas de los 3 pares de semillas, y mediana
  por modelo.
- **Intra-modelo entre mitades:** dentro de cada estación, las ventanas se permutan al azar
  (semilla 20261010) y se parten en dos mitades (⌊n/2⌋ y el resto). Mapas con la media de
  semillas; medida entre las mitades.
- **Entre modelos:** mapas con la media de semillas de toda la muestra (los del diseño
  principal).

**Medidas**
1. Spearman sobre los 180 valores.
2. Jaccard de los 10 y de los 20 elementos más importantes.
3. Spearman sobre la importancia sumada por canal (6 valores).
4. Spearman sobre la importancia sumada por día de ventana (30 valores).

**Criterio** (por medida)
- **Definición base:** un par (a, b) en una combinación cuenca × horizonte está "bajo el
  techo" si la medida entre modelos < mín(mediana entre semillas de a, mediana entre semillas
  de b).
- **"El desacuerdo supera el ruido":** en ≥ 2/3 de las 9 combinaciones, al menos 4 de los 6
  pares están bajo el techo.
- **"Indistinguible del ruido":** en más de la mitad de las combinaciones, la mediana entre
  pares de la medida entre modelos es ≥ la mediana entre modelos de la medida intra-modelo
  entre semillas.
- **"Intermedio":** cualquier otro caso.
- El techo entre mitades se reporta con las mismas comparaciones, como secundario.

### RR-3. Bootstrap por grupos de estaciones

**Grupos principales**
- Componentes conexas de las estaciones evaluables sobre la red HydroRIVERS v1.0 (Norteamérica).
- Dos estaciones quedan conectadas si el tramo de una está en la trayectoria aguas abajo del
  tramo de la otra (vía `NEXT_DOWN`, desde el `hyriv_id` de `estaciones_hidrorivers.csv`).
- Las estaciones sin tramo vinculado son grupos de un elemento.
- Topología leída de la capa registrada en `conf/sources.yaml` (`hydrorivers`), mediante un
  extracto local de columnas en `data/scratch/hydrorivers/` (no versionado).
- Es la agrupación más fina que mantiene juntas las estaciones conectadas. Al definirla salen
  23 grupos (≥ 15); `xai_14` los recalcula y registra el número.

**Peor caso** (secundario): las 6 unidades piloto.

**IC que se recalculan** (bootstrap de grupos: se remuestrean grupos con reemplazo y se toman
todas sus estaciones)
- H1: SS, 4 modelos × h = 7 y 14.
- H1-b: ΔNSE, 3 × 3.
- ΔNSE contra ARIMA (descriptivo): 4 × 3.
- H3: ΔCSI P90, h = 1 y 7, sumando las tablas de las estaciones remuestreadas.

**Criterio:** se reaplican las reglas de §7 (`models/criteria.py`) y se reporta si cada
veredicto cambia. Es sensibilidad: **no cambia el veredicto oficial.**

### RR-4. Comparaciones múltiples

**Familias de Bonferroni**

| Familia | Pruebas (*m*) | Nivel del IC |
|---|---|---|
| H1 | 8 | 1 − 0.05/8 |
| H1-b | 9 | 1 − 0.05/9 |
| H3 | 2 | 1 − 0.05/2 |

**Cálculo:** con bootstrap de estaciones (como el diseño principal) y de grupos (RR-3). Se
reaplican las reglas de §7 y se reporta si cambia algún veredicto. ΔNSE contra ARIMA no es una
hipótesis y no se ajusta.

### RR-6. Descriptores por estación (suplemento)

Por estación evaluable:
- **Área de drenaje:** `upland_km2` de HydroRIVERS (en `estaciones_hidrorivers.csv`).
- **Gasto:** media y P90 de 2010–2020 con `calidad = 0`.
- **Régimen:** fracción de días con gasto = 0 entre los días con `calidad = 0` de 2010-01-01 a
  2025-09-03. **"Intermitente" si la fracción es > 0.05**; si no, "perenne".
- **Precipitación:** número de estaciones climatológicas de la interpolación (`vecinos_clima`) y
  fracción de días con `precip_idw_mm` válida en el mismo periodo.
- **NSE a h = 1 y 7 del mejor modelo de cada horizonte**, el de mayor NSE mediana agregada en
  `rq1_summary.csv`.

Resumen por cuenca (mediana y rango) y, de forma descriptiva, NSE por régimen.

### RR-5. Regulación por presas (opcional)

Se usa solo si los datos ya están en el conjunto o en los atributos de HydroRIVERS incluidos.
No se descarga ninguna base nueva.

### Versiones de software

Las del entorno local (ARIMA, XGBoost, explicaciones, alertas y evaluación). Las de la imagen
de Kaggle donde se entrenaron las redes se reportan solo si quedaron registradas.

### Resultados del análisis de revisión (2026-10-16/17)

`scripts/xai_14_review_analyses.py` → `e_revision.json` y `numbers.json` → `revision_pares`.

**Comprobaciones internas superadas**
- F y T reproducen `rq3_contingency.csv`, y su bootstrap reproduce el ΔCSI de `e_rq3.json`.
- El bootstrap de estaciones sin ajuste reproduce los veredictos de §7.
- El recálculo de RR-2 reproduce `rq2_importance.csv` (diferencia máxima 1e-16).

| Análisis | Resultado según los criterios de arriba |
|---|---|
| RR-1, P90, h = 1 | **"Desacuerdo": no** (IC de B contiene 0; IC de C > 0). **"Frontera": no.** D: **equivalente** |
| RR-1, P90, h = 7 (confirmación) | "Desacuerdo": no; **"Frontera": sí** (IC de A > 0); D: equivalente |
| RR-2, Spearman sobre 180 | **El desacuerdo supera el ruido** (9 de 9 combinaciones) |
| RR-2, Jaccard top-20 | Supera el ruido (6 de 9) |
| RR-2, Spearman por día de ventana | Supera el ruido (8 de 9) |
| RR-2, Jaccard top-10 | Intermedio (2 de 9) |
| RR-2, Spearman por canal | Intermedio (3 de 9) |
| RR-3, grupos conectados (23) | H1 sin cambio; **H1-b h = 1 pasa a OPEN; H3 pasa a OPEN** |
| RR-3, peor caso (6 unidades) | Ningún veredicto cambia |
| RR-4, Bonferroni con estaciones | H1 y H3 sin cambio; **H1-b h = 1 pasa a OPEN** |
| RR-4, Bonferroni con grupos | H1 sin cambio; H1-b h = 1 OPEN; **H3 pasa a REJECTED** |
| RR-5 | Sin datos de presas en el conjunto ni en HydroRIVERS; no se descargó nada |

**Cifras e interpretación:** en `e_revision.json` y en la respuesta al brief. **Los
veredictos oficiales de §7 no cambian:** son análisis de sensibilidad.

## Evidencia

- `e_rq1.json`, `e_rq2.json` y `e_rq3.json`: veredictos con sus IC.
- `rq1_*.csv`, `rq2_*.csv` y `rq3_*.csv`: datos por estación, cuenca y par de modelos.
- `numbers.json`, `report.md`, `figures/` y `tables/`: salidas de `scripts/xai_08_report.py`.
- `compute_manifest.csv`: una fila por corrida, CPU y GPU.

### No realizado

- **Informer:** fuera del diseño principal (protocolo §4).

# HidroXAI-MX

HidroXAI-MX es una biblioteca de Python y un conjunto de datos abiertos para el pronóstico
explicable de gasto en ríos de México. Lo desarrolla el Instituto Politécnico Nacional (IPN)
en el proyecto IND-2026-0335.

- **Dataset Hidro-MX.** Series diarias de gasto y de variables climatológicas del Sistema de
  Información Hidrológica (SIH) de CONAGUA para cuatro cuencas piloto (Lerma–Santiago, Pánuco,
  Alta del Balsas y Cutzamala), divididas en seis unidades operativas.
    - Estaciones seleccionadas: 101 hidrométricas y 415 climatológicas.
    - Modelos digitales de elevación de INEGI.
    - Vínculo de cada estación con la red de ríos HydroRIVERS (HydroSHEDS).
    - Depositado en Zenodo con DOI. Ver [El dataset](dataset.md).
- **Biblioteca `hidroxai_mx`.**
    - Lectura del dataset directamente desde Zenodo.
    - Esquema y limpieza de las series.
    - Ventanas de entrenamiento.
    - Modelos: persistencia, ARIMA, XGBoost, TCN, ConvNeXt-1D, PatchTST y LSTM.
    - Explicaciones: TreeSHAP, Integrated Gradients y atención.
    - Sistema de alertas difusas tipo Mamdani.
- **Benchmark de pronóstico explicable** sobre 91 estaciones evaluables y horizontes de 1, 7 y
  14 días, con protocolo congelado antes de entrenar. Sus resultados están en
  [`results/xai_benchmark/`](https://github.com/pantrok/hidroxai-mx/tree/main/results/xai_benchmark).
- **Tutoriales** en Google Colab, sin credenciales. Ver [Tutoriales](tutoriales/index.md).
- **Dashboard** con los pronósticos retrospectivos del benchmark. Ver [Dashboard](acerca_dashboard.md).

## Cómo citar

Si usas el dataset, cita el artículo que lo describe y la versión que usaste.

**Artículo de datos**

> Sánchez-Ruiz, D., Reyes-Peña, C., Reyes-Cocoletzi, L., García-Ramírez, J., Ramos-Aguilar, E.,
> & Ramos-Aguilar, R. (2026). Hidro-MX: daily hydroclimatic dataset for four pilot basins in
> Mexico from National Water Commission and National Institute of Statistics and Geography
> sources, with digital elevation models and station–river network links. *Data in Brief*, 69,
> 113442. <https://doi.org/10.1016/j.dib.2026.113442>

**Dataset (versión vigente)**

> Sánchez-Ruiz, D., Ramos Aguilar, E., Ramos-Aguilar, R., Reyes-Peña, C., Reyes-Cocoletzi, L.,
> & García-Ramírez, J. (2026). *Hidro-MX v2026.11: a reproducible hydroclimatic dataset for
> Mexican pilot basins (CONAGUA-SIH and INEGI)* [Data set]. Zenodo.
> <https://doi.org/10.5281/zenodo.24119292>

El DOI de concepto [10.5281/zenodo.21231600](https://doi.org/10.5281/zenodo.21231600) apunta
siempre a la versión más reciente. La función `hidroxai_mx.dataset.como_citar()` imprime estas
referencias para cualquier versión.

## Créditos

Instituto Politécnico Nacional (IPN), Unidad Profesional Interdisciplinaria de Ingeniería campus
Tlaxcala (UPIIT). Convocatoria de Proyectos de Investigación Científica y Desarrollo Tecnológico
2026 (PICDT2026), Secretaría de Investigación y Posgrado, proyecto **IND-2026-0335**.

Datos: **CONAGUA** (Sistema de Información Hidrológica), **INEGI** (Continuo de Elevaciones
Mexicano 3.0) y **HydroSHEDS** (HydroRIVERS v1.0; Lehner & Grill, 2013).

## Licencias

Código: MIT. Datos derivados: CC BY 4.0, con la atribución a las fuentes que piden sus términos
de uso (`LICENSE-DATA.md`).

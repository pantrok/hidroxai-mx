# Referencia de la API

Módulos públicos de `hidroxai_mx`. La documentación se genera de las cadenas de documentación
del código.

| Página | Módulos | Para qué |
|---|---|---|
| [Acceso al dataset](dataset.md) | `dataset` | Leer el ZIP de Zenodo (remoto o local) y citar el dataset |
| [Datos y esquema](data.md) | `data.schema`, `data.clean`, `data.persist` | Esquema canónico, banderas de calidad, limpieza e imputación |
| [Características](features.md) | `features` | Rezagos, medias móviles, precipitación interpolada (IDW), ventanas |
| [Modelos](models.md) | `models.*` | Muestras y particiones del benchmark, referencias, ARIMA, XGBoost, redes, entrenamiento y métricas |
| [Explicabilidad](xai.md) | `xai.attributions` | TreeSHAP, Integrated Gradients, atención, importancias y concordancia |
| [Alertas difusas](alert.md) | `alert.fuzzy`, `alert.evaluation` | Sistema Mamdani, niveles del ensamble y tablas de contingencia |
| [Ingesta y geografía](ingesta.md) | `io.conagua`, `io.inegi`, `geo.spatial` | Descarga y lectura de las fuentes, utilidades espaciales |
| [Reportes y ejemplos](ejemplos.md) | `report`, `ejemplos` | Tablas de inventario y cobertura; funciones de apoyo de los tutoriales |

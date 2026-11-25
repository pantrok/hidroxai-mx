# Guía rápida

## Leer el dataset

`abrir_dataset()` abre la versión vigente (v2026.11) en Zenodo y solo descarga los archivos
que se leen. Cada archivo queda en caché, así que la segunda lectura no usa la red.

```python
from hidroxai_mx.dataset import abrir_dataset

ds = abrir_dataset()
est = ds.estaciones()                                   # 101 hidrométricas seleccionadas
vinculo = ds.vinculo_hidrorivers()                      # unidad y tramo de cada estación
q = ds.series_hidrometricas(claves=["SLVGJ"], anios=range(2020, 2026))
clima = ds.series_climatologicas(claves=["CSTGJ"], anios=[2024])
ft = ds.tabla_caracteristicas(claves=est["clave"])       # ~96 MB la primera vez
```

Otros lectores:

- `ds.miembros()` lista los archivos del ZIP.
- `ds.leer_csv(...)` y `ds.leer_parquet(...)` leen cualquier archivo.
- `ds.configuracion()` lee `conf/cuencas_piloto.yaml`, la configuración con que se construyó la
  versión.

## Entrenar y evaluar en una cuenca

`hidroxai_mx.ejemplos` encadena las funciones del benchmark en una versión pequeña: ventanas
de 30 días, partición cronológica (entrenamiento 2010–2020, validación 2021–2022, prueba
2023 – 3 sep 2025), XGBoost y una TCN.

```python
from hidroxai_mx import ejemplos as E

claves = E.claves_cuenca(vinculo, "Alta del Balsas")
paneles = E.paneles(ds.tabla_caracteristicas(claves=claves), claves)
res = E.entrenar(paneles, h=1)                          # XGBoost y TCN, dos semillas
prueba = res["arr"]["test"]["meta"]
tabla = E.tabla_metricas(prueba, res["pronosticos"])    # NSE, KGE y skill por estación
E.resumen_metricas(tabla)
```

!!! warning "Cifras ilustrativas"
    Estas cifras ilustran el procedimiento. Las del benchmark (91 estaciones, cuatro cuencas,
    tres horizontes, tres semillas y mallas de hiperparámetros) están en
    [`results/xai_benchmark/`](https://github.com/pantrok/hidroxai-mx/tree/main/results/xai_benchmark).

## Explicar y alertar

```python
import numpy as np
from hidroxai_mx.models import xgb
from hidroxai_mx.xai import attributions as A
from hidroxai_mx.alert import evaluation as AE, fuzzy as F

X = res["arr"]["test"]["X"]
idx = A.stratified_sample(prueba, n_max=500)
mapa = A.importance(xgb.tree_shap(res["modelos"][("xgboost", E.SEMILLAS[0])], X[idx]))  # [30 días, 6 canales]

miembros = np.stack(list(res["pronosticos"].values()))
niveles = AE.ensemble_levels(F.build_protocol_fis(), miembros, prueba,
                             E.observaciones_entrenamiento(paneles))
```

Los [tutoriales](tutoriales/index.md) recorren cada paso con explicaciones y figuras.

## Citar

```python
from hidroxai_mx.dataset import como_citar
print(como_citar())
```

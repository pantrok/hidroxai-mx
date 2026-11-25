"""Funciones de apoyo de los tutoriales (``notebooks/tutoriales/``).

Encadenan las piezas del benchmark (`models.data`, `models.xgb`, `models.nets`, `models.train`
y `models.metrics`) en una versión pequeña para la CPU de Colab: una cuenca, un horizonte y
pocas épocas. Las cifras que producen son **ilustrativas**; los resultados del benchmark
están en ``results/xai_benchmark/`` del repositorio.

La variable de entorno ``HIDROXAI_TUTORIAL_REDUCIDO=1`` activa un modo reducido (pocas
estaciones, una época) para que la integración continua ejecute los notebooks rápido.
"""
from __future__ import annotations

import os
from collections.abc import Iterable

import numpy as np
import pandas as pd

from .models import data as D
from .models import metrics as M

ENV_REDUCIDO = "HIDROXAI_TUTORIAL_REDUCIDO"
SEMILLAS = (20261010, 20261011)              # las dos primeras semillas del benchmark
CUENCA = "Alta del Balsas"


def modo_reducido() -> bool:
    """True si ``HIDROXAI_TUTORIAL_REDUCIDO`` vale 1, true, sí o yes."""
    return os.environ.get(ENV_REDUCIDO, "").strip().lower() in {"1", "true", "si", "sí", "yes"}


def claves_cuenca(vinculo: pd.DataFrame, cuenca: str = CUENCA) -> list[str]:
    """Estaciones hidrométricas de una cuenca piloto, según su unidad en HydroRIVERS."""
    cuencas = D.station_basins(vinculo)
    if cuenca not in set(cuencas.dropna()):
        raise ValueError(f"cuenca desconocida {cuenca!r}; disponibles: {', '.join(D.BASINS)}")
    return sorted(cuencas[cuencas == cuenca].index)


def paneles(ft: pd.DataFrame, claves: Iterable[str]) -> dict[str, pd.DataFrame]:
    """Panel diario (6 canales y bandera de calidad) de cada estación con datos en ``ft``."""
    presentes = set(ft["clave_estacion"])
    return {k: D.daily_panel(ft, k) for k in claves if k in presentes}


def a_gasto(z: np.ndarray, meta: pd.DataFrame, escaladores: dict[str, D.Scaler]) -> np.ndarray:
    """Pronóstico estandarizado → m³/s con el escalador de la estación de cada muestra."""
    z = np.asarray(z, dtype=float)
    out = np.empty(len(z))
    for clave, idx in meta.groupby("clave").indices.items():
        out[idx] = escaladores[clave].target_to_flow(z[idx])
    return out


def observaciones_entrenamiento(paneles_: dict[str, pd.DataFrame],
                                particion: tuple[str, str] = D.PARTITIONS["train"]) -> dict[str, np.ndarray]:
    """Gasto observado (``calidad = 0``) del periodo de entrenamiento, por estación.

    Es la referencia de los percentiles de las alertas, como en ``scripts/xai_07_alerts.py``.
    """
    out = {}
    for clave, p in paneles_.items():
        g = p.loc[particion[0]:particion[1]]
        out[clave] = g.loc[g["calidad"] == 0, D.TARGET].dropna().to_numpy()
    return out


def tabla_metricas(meta: pd.DataFrame, pronosticos: dict[str, np.ndarray]) -> pd.DataFrame:
    """NSE, KGE y skill score contra persistencia (1 − MSE/MSE_persistencia) por estación.

    ``meta`` es el de una partición de :func:`models.data.group_arrays` (con ``y_flow`` y
    ``q_issue``); ``pronosticos`` mapea nombre → gasto pronosticado en m³/s.
    """
    todos = {"persistencia": meta["q_issue"].to_numpy(dtype=float), **pronosticos}
    filas = []
    for clave, idx in meta.groupby("clave").indices.items():
        obs, ref = meta["y_flow"].to_numpy(dtype=float)[idx], todos["persistencia"][idx]
        for nombre, sim in todos.items():
            filas.append({"clave": clave, "modelo": nombre, "n": len(idx),
                          "nse": M.nse(obs, sim[idx]), "kge": M.kge(obs, sim[idx]),
                          "skill": M.skill_mse(obs, sim[idx], ref)})
    return pd.DataFrame(filas)


def resumen_metricas(tabla: pd.DataFrame) -> pd.DataFrame:
    """Mediana por modelo de las métricas de :func:`tabla_metricas`."""
    return (tabla.groupby("modelo", sort=False)[["nse", "kge", "skill"]].median()
            .assign(estaciones=tabla.groupby("modelo", sort=False)["clave"].nunique()))


def entrenar(paneles_: dict[str, pd.DataFrame], h: int = 1, semillas: Iterable[int] = SEMILLAS,
             epocas: int | None = None, canales_tcn: int = 32, max_depth: int = 4) -> dict:
    """Entrena XGBoost y una TCN pequeña por semilla en el grupo de estaciones dado.

    Devuelve ``arr`` (salida de :func:`models.data.group_arrays`), ``modelos`` con llaves
    ``("xgboost", semilla)`` y ``("tcn", semilla)``, y ``pronosticos`` de prueba en m³/s con
    llaves ``"xgboost_s<semilla>"`` y ``"tcn_s<semilla>"``.
    """
    from .models import nets as N
    from .models import train as T
    from .models import xgb as X

    if epocas is None:
        epocas = 1 if modo_reducido() else 3
    arr = D.group_arrays(paneles_, h)
    tr, va, te = arr["train"], arr["val"], arr["test"]
    if min(len(tr["y"]), len(va["y"]), len(te["y"])) == 0:
        raise ValueError("alguna partición quedó sin muestras válidas")
    modelos, pronosticos = {}, {}
    for s in semillas:
        b = X.fit(tr["X"], tr["y"], va["X"], va["y"], max_depth=max_depth, seed=s)
        modelos[("xgboost", s)] = b
        pronosticos[f"xgboost_s{s}"] = a_gasto(X.predict(b, te["X"]), te["meta"], arr["scalers"])
        red = N.build("tcn", canales_tcn)
        T.fit(red, tr["X"], tr["y"], va["X"], va["y"], seed=s, max_epochs=epocas)
        red.eval()
        modelos[("tcn", s)] = red
        pronosticos[f"tcn_s{s}"] = a_gasto(T.predict(red, te["X"]), te["meta"], arr["scalers"])
    return {"arr": arr, "modelos": modelos, "pronosticos": pronosticos, "h": h, "epocas": epocas}

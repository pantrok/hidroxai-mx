"""Funciones de apoyo de los tutoriales sobre una tabla de características sintética."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hidroxai_mx import ejemplos as E
from hidroxai_mx.models import data as D


def _tabla(claves=("AAAMX", "BBBMX"), seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    fechas = pd.date_range("2010-01-01", "2025-09-03", freq="D")
    marcos = []
    for k, clave in enumerate(claves):
        doy = fechas.dayofyear.to_numpy()
        q = 5 + 3 * np.sin(2 * np.pi * doy / 365.25) + rng.gamma(1.0, 0.5 + k, len(fechas))
        g = pd.DataFrame({"clave_estacion": clave, "fecha": fechas, "gasto_medio_m3s": q,
                          "precip_idw_mm": rng.gamma(0.5, 4.0, len(fechas)), "calidad": 0})
        g.loc[g.index[::50], "calidad"] = 1                        # algunos imputados
        g["gasto_medio_m3s_ma7"] = g["gasto_medio_m3s"].rolling(7, min_periods=1).mean()
        g["gasto_medio_m3s_ma30"] = g["gasto_medio_m3s"].rolling(30, min_periods=1).mean()
        marcos.append(g)
    return pd.concat(marcos, ignore_index=True)


def test_modo_reducido(monkeypatch):
    monkeypatch.delenv(E.ENV_REDUCIDO, raising=False)
    assert not E.modo_reducido()
    for v in ("1", "true", "Sí"):
        monkeypatch.setenv(E.ENV_REDUCIDO, v)
        assert E.modo_reducido()
    monkeypatch.setenv(E.ENV_REDUCIDO, "0")
    assert not E.modo_reducido()


def test_claves_cuenca():
    vinculo = pd.DataFrame({"clave": ["A", "B", "C", "D"],
                            "unidad_piloto": ["Bajio", "Alta del Balsas", "Santiago", None]})
    assert E.claves_cuenca(vinculo, "Lerma–Santiago") == ["A", "C"]
    assert E.claves_cuenca(vinculo, "Alta del Balsas") == ["B"]
    with pytest.raises(ValueError, match="desconocida"):
        E.claves_cuenca(vinculo, "Nilo")


def test_a_gasto_invierte_el_escalado_y_observaciones_de_entrenamiento():
    ft = _tabla()
    p = E.paneles(ft, ["AAAMX", "BBBMX", "NOEXISTE"])
    assert set(p) == {"AAAMX", "BBBMX"}
    arr = D.group_arrays(p, h=1)
    te = arr["test"]
    np.testing.assert_allclose(E.a_gasto(te["y"], te["meta"], arr["scalers"]), te["meta"]["y_flow"], rtol=1e-4)
    obs = E.observaciones_entrenamiento(p)
    g = ft[(ft["clave_estacion"] == "AAAMX") & (ft["fecha"] <= "2020-12-31") & (ft["calidad"] == 0)]
    np.testing.assert_allclose(np.sort(obs["AAAMX"]), np.sort(g["gasto_medio_m3s"].to_numpy()))


def test_tabla_metricas_referencias():
    meta = pd.DataFrame({"clave": ["A"] * 4 + ["B"] * 4,
                         "y_flow": [1.0, 2.0, 3.0, 4.0, 2.0, 2.0, 5.0, 1.0],
                         "q_issue": [1.5, 1.0, 2.5, 3.0, 1.0, 3.0, 4.0, 2.0]})
    t = E.tabla_metricas(meta, {"perfecto": meta["y_flow"].to_numpy()})
    pers = t[t["modelo"] == "persistencia"]
    perf = t[t["modelo"] == "perfecto"]
    assert np.allclose(pers["skill"], 0.0)
    assert np.allclose(perf["nse"], 1.0) and np.allclose(perf["skill"], 1.0)
    r = E.resumen_metricas(t)
    assert list(r.index) == ["persistencia", "perfecto"] and (r["estaciones"] == 2).all()


def test_entrenar_una_semilla_una_epoca():
    pytest.importorskip("torch")
    pytest.importorskip("xgboost")
    p = E.paneles(_tabla(), ["AAAMX", "BBBMX"])
    res = E.entrenar(p, h=1, semillas=[7], epocas=1, canales_tcn=8)
    n = len(res["arr"]["test"]["y"])
    assert set(res["modelos"]) == {("xgboost", 7), ("tcn", 7)}
    assert set(res["pronosticos"]) == {"xgboost_s7", "tcn_s7"}
    for v in res["pronosticos"].values():
        assert v.shape == (n,) and np.isfinite(v).all() and (v >= 0).all()
    assert res["epocas"] == 1

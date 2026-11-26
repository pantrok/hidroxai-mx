"""Los datos del dashboard coinciden con los archivos de resultados del benchmark.

Comprueba sobre una muestra de estaciones que las métricas mostradas son las publicadas, que el
NSE de los pronósticos guardados reproduce el publicado, que las alertas rehacen las tablas de
contingencia y que ``dashboard/index.html`` monta todos los archivos de ``dashboard/data/``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hidroxai_mx.models import metrics as M

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
DATA = DASH / "data"
RES = ROOT / "results" / "xai_benchmark"
MODELOS = ["persistencia", "arima", "xgboost", "tcn", "convnext", "patchtst", "lstm"]
MUESTRA = 12

def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, float_precision="round_trip")


pytestmark = pytest.mark.skipif(not (DATA / "meta.json").exists(), reason="sin dashboard/data")


@pytest.fixture(scope="module")
def publicadas() -> pd.DataFrame:
    met = pd.concat([_csv(RES / "rq1_station_metrics.csv"),
                     _csv(RES / "mese" / "lstm_station_metrics.csv")], ignore_index=True)
    return met[met["modelo"].isin(MODELOS)]


@pytest.fixture(scope="module")
def muestra(publicadas) -> list[str]:
    claves = sorted(publicadas["clave"].unique())
    rng = np.random.default_rng(20261125)
    return sorted(rng.choice(claves, size=MUESTRA, replace=False))


def test_metricas_mostradas_son_las_publicadas(publicadas, muestra):
    dash = _csv(DATA / "metricas_estacion.csv")
    cols = ["cuenca", "h", "clave", "modelo"]
    a = dash[dash["clave"].isin(muestra)].set_index(cols).sort_index()
    b = publicadas[publicadas["clave"].isin(muestra)].set_index(cols).sort_index()
    assert a.index.equals(b.index)
    for c in ("n", "nse", "kge", "rmse", "ss"):
        np.testing.assert_allclose(a[c].to_numpy(float), b[c].to_numpy(float), rtol=0, atol=0, equal_nan=True)
    assert dash["clave"].nunique() == publicadas["clave"].nunique() == 91


def test_pronosticos_reproducen_el_nse_publicado(publicadas, muestra):
    pron = pd.read_parquet(DATA / "pronosticos.parquet", filters=[("clave", "in", muestra)])
    for (clave, h), g in pron.groupby(["clave", "h"]):
        pub = publicadas[(publicadas["clave"] == clave) & (publicadas["h"] == h)].set_index("modelo")["nse"]
        for m in MODELOS:
            ref = pub[m]
            nse = M.nse(g["observado"].to_numpy(float), g[m].to_numpy(float))
            assert abs(nse - ref) <= 1e-3 * max(1.0, abs(ref)), (clave, h, m, nse, ref)
    assert pron["fecha"].min() >= pd.Timestamp("2023-01-01") and pron["fecha"].max() <= pd.Timestamp("2025-09-03")


def test_alertas_rehacen_la_contingencia_publicada(muestra):
    al = pd.read_parquet(DATA / "alertas.parquet", filters=[("clave", "in", muestra)])
    um = _csv(DATA / "umbrales.csv").set_index("clave")
    pub = pd.read_csv(RES / "rq3_contingency.csv")
    pub = pub[pub["clave"].isin(muestra)].set_index(["clave", "h", "evento", "metodo"]).sort_index()
    filas = []
    for (clave, h), g in al.groupby(["clave", "h"]):
        for e, q, nivel in (("P90", 0.90, 2), ("P99", 0.99, 3)):
            obs = g["observado"].to_numpy() > um.loc[clave, e.lower()]
            for metodo, pred in (("difuso", g["nivel"].to_numpy() >= nivel), ("umbral", g["percentil"].to_numpy() >= q)):
                filas.append({"clave": clave, "h": int(h), "evento": e, "metodo": metodo,
                              "aciertos": int((obs & pred).sum()), "fallos": int((obs & ~pred).sum()),
                              "falsas": int((~obs & pred).sum()), "negativos": int((~obs & ~pred).sum())})
    rehecha = pd.DataFrame(filas).set_index(["clave", "h", "evento", "metodo"]).sort_index()
    pd.testing.assert_frame_equal(rehecha, pub[rehecha.columns], check_dtype=False)
    dash = pd.read_csv(DATA / "contingencia.csv")
    pd.testing.assert_frame_equal(dash, pd.read_csv(RES / "rq3_contingency.csv"))


def test_importancias_y_resumenes_son_copias():
    imp = pd.read_parquet(DATA / "importancia.parquet")
    pub = pd.concat([_csv(RES / "rq2_importance.csv"), _csv(RES / "mese" / "lstm_importance.csv")],
                    ignore_index=True)[imp.columns]
    pd.testing.assert_frame_equal(imp.reset_index(drop=True), pub.reset_index(drop=True))
    pd.testing.assert_frame_equal(_csv(DATA / "resumen_alertas.csv"), _csv(RES / "rq3_summary.csv"))


def test_index_monta_todos_los_archivos():
    html = (DASH / "index.html").read_text(encoding="utf-8")
    bloque = re.search(r"const ARCHIVOS = \[(.*?)\];", html, re.S).group(1)
    montados = set(re.findall(r'"([^"]+)"', bloque))
    esperados = {f"data/{p.name}" for p in DATA.iterdir() if p.is_file()} | {"app.py", "datos.py", "vistas.py"}
    assert montados == esperados
    assert re.search(r"@stlite/browser@\d+\.\d+\.\d+/build/stlite\.js", html)      # versión fija
    assert "Cargando Python en tu navegador, puede tardar 15–30 s la primera vez" in html


def test_tamano_y_metadatos():
    total = sum(p.stat().st_size for p in DATA.iterdir()) / 1e6
    assert total <= 30, f"dashboard/data pesa {total:.1f} MB"
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    assert meta["verificacion"]["contingencias_iguales_a_rq3"] is True
    assert meta["estaciones_evaluables"] == 91 and meta["horizontes"] == [1, 7, 14]

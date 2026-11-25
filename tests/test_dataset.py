"""Acceso al dataset publicado: ZIP local y remoto (sesión HTTP simulada con rangos)."""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import pytest

from hidroxai_mx import dataset as D


def _zip_de_prueba() -> bytes:
    """ZIP con la estructura del depósito: catálogo, serie particionada, tabla y conf."""
    est = pd.DataFrame({"clave": ["00001", "AAAMX"], "nombre": ["Uno", "Dos"]})
    filas = []
    for anio in (2020, 2021):
        for clave in ("00001", "AAAMX"):
            filas.append({"clave_estacion": clave, "fecha": pd.Timestamp(f"{anio}-01-01"),
                          "gasto_medio_m3s": float(anio % 100), "fuente": "SIH", "calidad": 0})
    serie = pd.DataFrame(filas)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("processed/estaciones_seleccionadas_hidrometricas.csv", est.to_csv(index=False))
        for anio, g in serie.groupby(serie["fecha"].dt.year):
            pq = io.BytesIO()
            g.to_parquet(pq, index=False)
            z.writestr(f"processed/series_hidrometricas.parquet/anio={anio}/p-0.parquet", pq.getvalue())
        ft = io.BytesIO()
        serie.assign(anio=serie["fecha"].dt.year).to_parquet(ft, index=False)
        z.writestr("features/feature_table.parquet", ft.getvalue())
        z.writestr("conf/cuencas_piloto.yaml", "criterios:\n  cobertura_minima: 0.6\n")
    return buf.getvalue()


class _Respuesta:
    def __init__(self, status: int, contenido: bytes = b"", encabezados: dict | None = None):
        self.status_code, self.content, self.headers = status, contenido, encabezados or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise OSError(self.status_code)


class _SesionRangos:
    """Sirve `datos` como un servidor que acepta Range; cuenta los bytes enviados."""

    def __init__(self, datos: bytes, status: int = 206, recorte: int = 0):
        self.datos, self.status, self.recorte, self.enviados = datos, status, recorte, 0

    def head(self, url, **kw):
        return _Respuesta(200, encabezados={"Content-Length": str(len(self.datos))})

    def get(self, url, headers=None, **kw):
        a, b = map(int, re.match(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
        parte = self.datos[a:b + 1]
        if self.recorte:
            parte = parte[: len(parte) - self.recorte]
        self.enviados += len(parte)
        return _Respuesta(self.status, parte)


@pytest.fixture()
def zip_local(tmp_path):
    p = tmp_path / "hidro.zip"
    p.write_bytes(_zip_de_prueba())
    return p


def test_lectores_sobre_zip_local(zip_local, tmp_path):
    ds = D.abrir_dataset(zip_local=zip_local, cache=tmp_path / "cache")
    est = ds.estaciones()
    assert est["clave"].tolist() == ["00001", "AAAMX"]          # claves como texto
    q = ds.series_hidrometricas(claves=["AAAMX"], anios=[2021])
    assert len(q) == 1 and q["anio"].tolist() == [2021] and q["gasto_medio_m3s"].tolist() == [21.0]
    assert len(ds.series_hidrometricas()) == 4
    ft = ds.tabla_caracteristicas(claves=["00001"], columnas=["clave_estacion", "gasto_medio_m3s"])
    assert list(ft.columns) == ["clave_estacion", "gasto_medio_m3s"] and len(ft) == 2
    assert ds.configuracion()["criterios"]["cobertura_minima"] == 0.6
    assert set(ds.miembros("processed/")["archivo"]) >= {"processed/estaciones_seleccionadas_hidrometricas.csv"}
    # la caché guarda el miembro y se reutiliza
    assert (tmp_path / "cache" / D.VERSION_ACTUAL / "features" / "feature_table.parquet").is_file()


def test_variable_de_entorno_para_zip_local(zip_local, tmp_path, monkeypatch):
    monkeypatch.setenv(D.ENV_ZIP, str(zip_local))
    monkeypatch.setenv(D.ENV_CACHE, str(tmp_path / "c"))
    ds = D.abrir_dataset()
    assert not ds.remoto and len(ds.estaciones()) == 2


def test_lectura_remota_por_rangos_igual_a_local(zip_local, tmp_path, monkeypatch):
    datos = zip_local.read_bytes()
    sesion = _SesionRangos(datos)
    original = D.ArchivoRemoto.__init__
    monkeypatch.setattr(D.ArchivoRemoto, "__init__",
                        lambda self, url, **kw: original(self, url, bloque=64, tramo=256, sesion=sesion))
    monkeypatch.delenv(D.ENV_ZIP, raising=False)
    remoto = D.abrir_dataset(cache=tmp_path / "r")
    local = D.abrir_dataset(zip_local=zip_local, cache=tmp_path / "l")
    assert remoto.remoto
    pd.testing.assert_frame_equal(remoto.series_hidrometricas(), local.series_hidrometricas())
    pd.testing.assert_frame_equal(remoto.tabla_caracteristicas(), local.tabla_caracteristicas())


def test_archivo_remoto_lee_y_se_posiciona():
    datos = bytes(range(256)) * 40
    f = D.ArchivoRemoto("http://x", bloque=100, tramo=300, hilos=3, sesion=_SesionRangos(datos))
    assert f.read(10) == datos[:10]
    f.seek(-50, io.SEEK_END)
    assert f.read() == datos[-50:]
    f.seek(1000)
    assert f.read(2500) == datos[1000:3500]              # lectura grande en tramos paralelos


def test_archivo_remoto_rechaza_servidor_sin_rangos():
    f = D.ArchivoRemoto("http://x", sesion=_SesionRangos(b"abc" * 10, status=200))
    with pytest.raises(OSError, match="rango"):
        f.read(5)


def test_archivo_remoto_detecta_respuesta_incompleta():
    f = D.ArchivoRemoto("http://x", intentos=2, sesion=_SesionRangos(b"abc" * 10, recorte=1))
    with pytest.raises(OSError, match="incompleta"):
        f.read(5)


def test_cita_y_versiones():
    texto = D.como_citar("v2026.11")
    assert "https://doi.org/10.5281/zenodo.24119292" in texto and D.CONCEPTO_DOI in texto
    assert "IND-2026-0335" in texto and "HydroSHEDS" in texto
    assert D.doi("v2026.06") == "10.5281/zenodo.21231601"
    assert D.url_zenodo("v2026.10").startswith("https://zenodo.org/records/23150556/files/")
    with pytest.raises(ValueError, match="desconocida"):
        D.doi("v1999.01")

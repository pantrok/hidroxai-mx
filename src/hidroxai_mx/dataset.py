"""Acceso al dataset Hidro-MX publicado en Zenodo sin descargar el ZIP completo.

Zenodo atiende peticiones HTTP de rango, así que el ZIP se abre como un archivo remoto y
solo se descargan los miembros que se leen (por ejemplo, ~96 MB de la tabla de
características en lugar de ~880 MB del archivo completo). Cada miembro se guarda en una
caché local y ``zipfile`` comprueba su CRC-32 al extraerlo.

Uso::

    from hidroxai_mx.dataset import abrir_dataset
    ds = abrir_dataset()                      # versión vigente, v2026.11
    est = ds.estaciones()                     # estaciones hidrométricas seleccionadas
    q = ds.series_hidrometricas(claves=["SLVGJ"], anios=range(2020, 2026))

Variables de entorno:

- ``HIDROXAI_MX_ZIP``: ruta a una copia local del ZIP (sin red);
- ``HIDROXAI_MX_CACHE``: carpeta de la caché (por omisión ``~/.cache/hidroxai_mx``).
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

CONCEPTO_DOI = "10.5281/zenodo.21231600"
VERSION_ACTUAL = "v2026.11"
VERSIONES = {
    "v2026.11": {"registro": "24119292", "archivo": "HidroXAI-MX-v2026.11.zip", "fecha": "2026-11-10"},
    "v2026.10": {"registro": "23150556", "archivo": "HidroXAI-MX-v2026.10.zip", "fecha": "2026-10-05"},
    "v2026.06": {"registro": "21231601", "archivo": "HidroXAI-MX-v2026.06.zip", "fecha": "2026-07-07"},
}
AUTORES = ("Sánchez-Ruiz, D., Ramos Aguilar, E., Ramos-Aguilar, R., Reyes-Peña, C., "
           "Reyes-Cocoletzi, L., & García-Ramírez, J.")
ENV_ZIP, ENV_CACHE = "HIDROXAI_MX_ZIP", "HIDROXAI_MX_CACHE"
CREDITOS = ("Instituto Politécnico Nacional (IPN) · Convocatoria PICDT2026 · proyecto IND-2026-0335. "
            "Datos: CONAGUA (Sistema de Información Hidrológica), INEGI y HydroSHEDS.")


def _meta(version: str) -> dict:
    if version not in VERSIONES:
        raise ValueError(f"versión desconocida {version!r}; disponibles: {', '.join(VERSIONES)}")
    return VERSIONES[version]


def doi(version: str = VERSION_ACTUAL) -> str:
    """DOI de una versión del dataset."""
    return f"10.5281/zenodo.{_meta(version)['registro']}"


def url_zenodo(version: str = VERSION_ACTUAL) -> str:
    """URL de descarga directa del ZIP de una versión."""
    m = _meta(version)
    return f"https://zenodo.org/records/{m['registro']}/files/{m['archivo']}?download=1"


def como_citar(version: str = VERSION_ACTUAL) -> str:
    """Texto de cita del dataset (metadatos del depósito en Zenodo) y créditos del proyecto."""
    anio = _meta(version)["fecha"][:4]
    return (f"{AUTORES} ({anio}). Hidro-MX {version}: a reproducible hydroclimatic dataset for "
            f"Mexican pilot basins (CONAGUA-SIH and INEGI) [Data set]. Zenodo. "
            f"https://doi.org/{doi(version)}\n"
            f"Todas las versiones (DOI de concepto): https://doi.org/{CONCEPTO_DOI}\n"
            f"Créditos: {CREDITOS}")


class ArchivoRemoto(io.RawIOBase):
    """Archivo de solo lectura sobre HTTP con peticiones de rango.

    Las lecturas pequeñas (directorio central del ZIP, encabezados) pasan por una caché de
    bloques; las grandes se piden en tramos de ``tramo`` bytes, ``hilos`` a la vez, con
    reintentos si una respuesta llega incompleta.
    """

    def __init__(self, url: str, bloque: int = 1 << 20, tramo: int = 8 << 20, hilos: int = 4,
                 intentos: int = 3, sesion=None):
        if sesion is None:
            import requests

            sesion = requests.Session()
        self.url, self.bloque, self.tramo, self._s = url, bloque, tramo, sesion
        self.hilos, self.intentos = hilos, intentos
        r = self._s.head(url, allow_redirects=True, timeout=60,
                         headers={"User-Agent": "hidroxai-mx"})
        r.raise_for_status()
        self.tamano = int(r.headers["Content-Length"])
        self._pos = 0
        self._bloques: OrderedDict[int, bytes] = OrderedDict()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.tamano}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def _rango(self, ini: int, fin: int) -> bytes:
        """Bytes [ini, fin] (inclusivo), con reintentos ante respuestas incompletas."""
        for intento in range(1, self.intentos + 1):
            r = self._s.get(self.url, timeout=300, allow_redirects=True,
                            headers={"Range": f"bytes={ini}-{fin}", "User-Agent": "hidroxai-mx"})
            if r.status_code != 206:
                raise OSError(f"el servidor no aceptó la petición de rango (HTTP {r.status_code})")
            if len(r.content) == fin - ini + 1:
                return r.content
            if intento == self.intentos:
                raise OSError(f"respuesta de rango incompleta tras {self.intentos} intentos")
        raise AssertionError("inalcanzable")

    def _rango_grande(self, ini: int, n: int) -> list[bytes]:
        """Bytes [ini, ini + n) en tramos descargados en paralelo, en orden."""
        tramos = [(a, min(a + self.tramo, ini + n) - 1) for a in range(ini, ini + n, self.tramo)]
        if self.hilos <= 1 or len(tramos) == 1:
            return [self._rango(a, b) for a, b in tramos]
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self.hilos) as ex:
            return list(ex.map(lambda ab: self._rango(*ab), tramos))

    def _bloque(self, i: int) -> bytes:
        if i in self._bloques:
            self._bloques.move_to_end(i)
        else:
            ini = i * self.bloque
            self._bloques[i] = self._rango(ini, min(ini + self.bloque, self.tamano) - 1)
            if len(self._bloques) > 16:
                self._bloques.popitem(last=False)
        return self._bloques[i]

    def readinto(self, b) -> int:
        n = min(len(b), self.tamano - self._pos)
        if n <= 0:
            return 0
        out = memoryview(b).cast("B")
        hecho = 0
        if n > self.bloque:
            for datos in self._rango_grande(self._pos, n):
                out[hecho:hecho + len(datos)] = datos
                hecho += len(datos)
            self._pos += hecho
            return hecho
        while hecho < n:
            i, off = divmod(self._pos, self.bloque)
            datos = self._bloque(i)[off:off + n - hecho]
            out[hecho:hecho + len(datos)] = datos
            hecho += len(datos)
            self._pos += len(datos)
        return hecho


class Dataset:
    """Un ZIP de Hidro-MX (remoto en Zenodo o local) con lectores de sus productos."""

    def __init__(self, version: str = VERSION_ACTUAL, zip_local: str | Path | None = None,
                 cache: str | Path | None = None):
        _meta(version)
        self.version = version
        ruta = zip_local or os.environ.get(ENV_ZIP)
        self.remoto = ruta is None
        fuente = ArchivoRemoto(url_zenodo(version)) if self.remoto else open(ruta, "rb")  # noqa: SIM115
        self.zip = zipfile.ZipFile(fuente)
        base = Path(cache or os.environ.get(ENV_CACHE) or Path.home() / ".cache" / "hidroxai_mx")
        self.cache = base / version

    def __repr__(self) -> str:
        origen = f"Zenodo, DOI {doi(self.version)}" if self.remoto else "copia local del ZIP"
        return f"Dataset Hidro-MX {self.version} ({origen}; {len(self.zip.namelist())} archivos)"

    # ------------------------------------------------------------------ acceso genérico
    def miembros(self, prefijo: str = "") -> pd.DataFrame:
        """Archivos del ZIP con su tamaño (MB) original y comprimido."""
        filas = [{"archivo": i.filename, "mb": i.file_size / 1e6, "mb_comprimido": i.compress_size / 1e6}
                 for i in self.zip.infolist() if i.filename.startswith(prefijo) and not i.is_dir()]
        return pd.DataFrame(filas)

    def leer_bytes(self, nombre: str) -> bytes:
        """Contenido de un archivo del ZIP; se descarga una vez y se guarda en la caché."""
        info = self.zip.getinfo(nombre)
        destino = self.cache / nombre
        if destino.is_file() and destino.stat().st_size == info.file_size:
            return destino.read_bytes()
        datos = self.zip.read(info)            # comprueba el CRC-32 del miembro
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".parcial")
        tmp.write_bytes(datos)
        tmp.replace(destino)
        return datos

    def leer_csv(self, nombre: str, **kwargs) -> pd.DataFrame:
        kwargs.setdefault("dtype", {"clave": str, "clave_estacion": str})
        return pd.read_csv(io.BytesIO(self.leer_bytes(nombre)), **kwargs)

    def leer_texto(self, nombre: str) -> str:
        return self.leer_bytes(nombre).decode("utf-8")

    def particiones(self, carpeta: str) -> list[str]:
        """Archivos Parquet de una carpeta particionada (``…/anio=AAAA/*.parquet``)."""
        pre = carpeta.rstrip("/") + "/"
        return sorted(n for n in self.zip.namelist() if n.startswith(pre) and n.endswith(".parquet"))

    def leer_parquet(self, nombre: str, columnas: list[str] | None = None, filtros=None,
                     anios: Iterable[int] | None = None) -> pd.DataFrame:
        """Lee un Parquet del ZIP, un archivo o una carpeta particionada por año.

        ``filtros`` sigue la sintaxis de pyarrow (p. ej. ``[("clave_estacion", "in", claves)]``)
        y se aplica al leer; ``anios`` elige particiones sin descargar las demás.
        """
        import pyarrow.parquet as pq

        partes = self.particiones(nombre)
        if not partes:
            tabla = pq.read_table(io.BytesIO(self.leer_bytes(nombre)), columns=columnas, filters=filtros)
            return tabla.to_pandas()
        elegidos = set(anios) if anios is not None else None
        marcos = []
        for p in partes:
            m = re.search(r"/anio=(\d{4})/", p)
            anio = int(m.group(1)) if m else None
            if elegidos is not None and anio not in elegidos:
                continue
            cols = [c for c in columnas if c != "anio"] if columnas else None
            df = pq.read_table(io.BytesIO(self.leer_bytes(p)), columns=cols, filters=filtros).to_pandas()
            if anio is not None and (columnas is None or "anio" in columnas):
                df["anio"] = anio
            marcos.append(df)
        return pd.concat(marcos, ignore_index=True) if marcos else pd.DataFrame(columns=columnas)

    # ------------------------------------------------------------------ productos
    def estaciones(self, tipo: str = "hidrometricas", conjunto: str = "seleccionadas") -> pd.DataFrame:
        """Catálogo de estaciones: ``tipo`` hidrometricas/climatologicas; ``conjunto``
        candidatas, seleccionadas o extendidas (solo hidrométricas)."""
        return self.leer_csv(f"processed/estaciones_{conjunto}_{tipo}.csv")

    def vinculo_hidrorivers(self) -> pd.DataFrame:
        """Estación hidrométrica → unidad piloto y tramo de HydroRIVERS v1.0."""
        return self.leer_csv("processed/estaciones_hidrorivers.csv")

    def series_hidrometricas(self, claves: Iterable[str] | None = None,
                             anios: Iterable[int] | None = None,
                             columnas: list[str] | None = None) -> pd.DataFrame:
        filtros = [("clave_estacion", "in", list(claves))] if claves is not None else None
        return self.leer_parquet("processed/series_hidrometricas.parquet", columnas, filtros, anios)

    def series_climatologicas(self, claves: Iterable[str] | None = None,
                              anios: Iterable[int] | None = None,
                              columnas: list[str] | None = None) -> pd.DataFrame:
        filtros = [("clave_estacion", "in", list(claves))] if claves is not None else None
        return self.leer_parquet("processed/series_climatologicas.parquet", columnas, filtros, anios)

    def tabla_caracteristicas(self, claves: Iterable[str] | None = None,
                              columnas: list[str] | None = None) -> pd.DataFrame:
        """Tabla diaria de características (gasto, rezagos, medias móviles, precipitación IDW)."""
        filtros = [("clave_estacion", "in", list(claves))] if claves is not None else None
        return self.leer_parquet("features/feature_table.parquet", columnas, filtros)

    def configuracion(self, nombre: str = "cuencas_piloto") -> dict:
        """Archivo de configuración ``conf/<nombre>.yaml`` con el que se construyó la versión."""
        import yaml

        return yaml.safe_load(self.leer_texto(f"conf/{nombre}.yaml"))


def abrir_dataset(version: str = VERSION_ACTUAL, zip_local: str | Path | None = None,
                  cache: str | Path | None = None) -> Dataset:
    """Abre una versión del dataset: en Zenodo, o local si se da ``zip_local`` o ``HIDROXAI_MX_ZIP``."""
    return Dataset(version, zip_local=zip_local, cache=cache)

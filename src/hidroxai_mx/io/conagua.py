"""Conectores CONAGUA-SIH: catálogos y series diarias (CSV directos) + BANDAS (.mdb).

Verificado 2026-06-18: el portal SIH publica un CSV por estación en URL predecible:
    https://sih.conagua.gob.mx/basedatos/{Hidros|Climas}/<CLAVE>.csv
y un catálogo maestro por tipo. No hay selector JS: la descarga es directa.
"""
from __future__ import annotations

import io
import unicodedata
from pathlib import Path

import pandas as pd

from ..utils import RAW, get_logger, load_sources
from ..utils.download import fetch

log = get_logger("io.conagua")
_SRC = load_sources()["fuentes"]["sih_series"]
ENCODING = _SRC.get("encoding", "latin-1")
NA = _SRC.get("na_values", ["-", ""])


def _norm(s: object) -> str:
    """minúsculas sin acentos ni espacios extremos (para mapear encabezados)."""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.strip().lower()


# --------------------------------------------------------------------------- #
# URLs
# --------------------------------------------------------------------------- #
def catalog_url(tipo: str) -> str:
    c = _SRC[tipo]
    return f"{_SRC['base']}{c['dir']}/{c['catalogo']}"


def series_url(tipo: str, clave: str) -> str:
    c = _SRC[tipo]
    return f"{_SRC['base']}{c['dir']}/{clave}.csv"


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
def download_catalog(tipo: str, overwrite: bool = False) -> Path:
    dest = RAW / "sih" / f"catalogo_{tipo}.csv"
    return fetch(catalog_url(tipo), dest, overwrite=overwrite)


_CAT_MAP = [
    ("clave", lambda n: n.startswith("clave")),
    ("nombre", lambda n: n.startswith("nombre")),
    ("latitud", lambda n: n.startswith("latitud")),
    ("longitud", lambda n: n.startswith("longitud")),
    ("altitud", lambda n: n.startswith("altitud")),
    ("estado", lambda n: n == "estado"),
    ("municipio", lambda n: n.startswith("municipio")),
    ("region_hidrologica", lambda n: n.replace(".", "").replace(" ", "").startswith("rh")
        or ("region" in n and ("numero" in n or "num" in n))),
    ("cuenca", lambda n: n.startswith("cuenca")),
]


def read_catalog(path: Path) -> pd.DataFrame:
    """Lee un catálogo SIH (hidro o clima) y normaliza columnas al esquema."""
    df = pd.read_csv(path, encoding=ENCODING, dtype=str, skipinitialspace=True)
    rename: dict[str, str] = {}
    for col in df.columns:
        n = _norm(col)
        for target, pred in _CAT_MAP:
            if target not in rename.values() and pred(n):
                rename[col] = target
                break
    out = df.rename(columns=rename)
    keep = [c for c in ["clave", "nombre", "latitud", "longitud", "altitud",
                        "estado", "municipio", "region_hidrologica", "cuenca"] if c in out.columns]
    out = out[keep].copy()
    for c in ("latitud", "longitud", "altitud"):
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if "clave" in out:
        out["clave"] = out["clave"].str.strip()
    if "region_hidrologica" in out:
        out["region_hidrologica"] = out["region_hidrologica"].str.strip()
    return out


def claves_from_catalog(path: Path) -> list[str]:
    return read_catalog(path)["clave"].dropna().tolist()


# --------------------------------------------------------------------------- #
# Series
# --------------------------------------------------------------------------- #
_SER_MAP = [
    ("fecha", lambda n: n.startswith("fecha")),
    ("gasto_medio_m3s", lambda n: "gasto" in n),
    ("nivel_m", lambda n: "nivel" in n),
    ("precip_mm", lambda n: "precip" in n),
    ("tmax_c", lambda n: "temperatura" in n and "maxima" in n),
    ("tmin_c", lambda n: "temperatura" in n and "minima" in n),
    ("tmed_c", lambda n: "temperatura" in n and "media" in n),
    ("evap_mm", lambda n: "evap" in n),
]


def read_series_csv(path: Path) -> pd.DataFrame:
    """Lee una serie del SIH saltando el bloque de metadatos y normaliza al esquema.

    Devuelve columnas canónicas presentes + clave_estacion (de nombre de archivo).
    """
    raw = Path(path).read_text(encoding=ENCODING, errors="replace")
    lines = raw.splitlines()
    hdr = next((i for i, ln in enumerate(lines) if _norm(ln).startswith("fecha")), None)
    if hdr is None:
        raise ValueError(f"No se encontró encabezado 'Fecha' en {Path(path).name}")
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), na_values=NA, skipinitialspace=True)
    rename: dict[str, str] = {}
    for col in df.columns:
        n = _norm(col)
        for target, pred in _SER_MAP:
            if target not in rename.values() and pred(n):
                rename[col] = target
                break
    df = df.rename(columns=rename)
    df = df[[c for c in df.columns if c in {t for t, _ in _SER_MAP}]].copy()
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y/%m/%d", errors="coerce")
    for c in df.columns:
        if c != "fecha":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["fecha"])
    df["clave_estacion"] = Path(path).stem.strip()
    return df


def download_series(tipo: str, claves: list[str] | None = None,
                    limit: int | None = None, overwrite: bool = False) -> list[Path]:
    """Descarga las series CSV directas. Si no se pasan claves, usa todo el catálogo."""
    if claves is None:
        cat = download_catalog(tipo, overwrite=overwrite)
        claves = claves_from_catalog(cat)
    if limit:
        claves = claves[:limit]
    out: list[Path] = []
    for clave in claves:
        dest = RAW / "sih_series" / tipo / f"{clave}.csv"
        try:
            out.append(fetch(series_url(tipo, clave), dest, overwrite=overwrite))
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo descargar %s/%s: %s", tipo, clave, exc)
    log.info("Descargadas %d/%d series (%s)", len(out), len(claves), tipo)
    return out


# --------------------------------------------------------------------------- #
# BANDAS (.mdb) — respaldo histórico profundo
# --------------------------------------------------------------------------- #
def mdb_to_csv(mdb_path: Path, table: str) -> pd.DataFrame:
    import shutil
    import subprocess

    if shutil.which("mdb-export"):
        raw = subprocess.check_output(["mdb-export", str(mdb_path), table])
        return pd.read_csv(io.BytesIO(raw))
    try:
        import pandas_access as mdb  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instala mdbtools o el extra 'mdb' (pandas-access).") from exc
    return mdb.read_table(str(mdb_path), table)

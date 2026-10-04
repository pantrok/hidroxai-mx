"""Utilidades transversales: rutas, configuración, logging, descargas con caché."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Rutas del proyecto (resueltas relativas a la raíz del repo)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]
CONF = ROOT / "conf"


def _data_root() -> Path:
    """`data/` en el repositorio; en el archivo de Zenodo (raw/, processed/ y features/ en
    la raíz, junto a src/) la raíz misma. La variable HIDROXAI_DATA lo fija explícitamente."""
    if env := os.environ.get("HIDROXAI_DATA"):
        return Path(env).resolve()
    if not (ROOT / "data").is_dir() and (ROOT / "raw").is_dir() and (ROOT / "processed").is_dir():
        return ROOT
    return ROOT / "data"


DATA = _data_root()
RAW, INTERIM, PROCESSED, FEATURES = (
    DATA / "raw",
    DATA / "interim",
    DATA / "processed",
    DATA / "features",
)

for _p in (RAW, INTERIM, PROCESSED, FEATURES):
    _p.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Logger con formato uniforme para todos los scripts."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def load_sources(path: Path | None = None) -> dict[str, Any]:
    """Carga el registro de fuentes (conf/sources.yaml)."""
    path = path or (CONF / "sources.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_cuencas(path: Path | None = None) -> dict[str, Any]:
    path = path or (CONF / "cuencas_piloto.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    """Hash de un archivo para trazabilidad del snapshot."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()

"""Descarga reproducible con caché y registro de procedencia.

Usa `requests` con reintentos. Registra (url, ruta, sha256, fecha, bytes) en un
manifiesto JSON dentro de data/raw/_manifest.json para trazabilidad del snapshot DVC.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import RAW, get_logger, sha256

log = get_logger("io.download")
_MANIFEST = RAW / "_manifest.json"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (HidroXAI-MX ingest)"}


def _record(url: str, dest: Path) -> None:
    manifest = {}
    if _MANIFEST.exists():
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    manifest[str(dest.relative_to(RAW))] = {
        "url": url,
        "sha256": sha256(dest),
        "bytes": dest.stat().st_size,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch(
    url: str,
    dest: Path,
    *,
    headers: dict[str, str] | None = None,
    overwrite: bool = False,
    retries: int = 3,
    timeout: int = 60,
) -> Path:
    """Descarga `url` a `dest` (idempotente salvo overwrite). Devuelve la ruta."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        log.info("cache-hit %s", dest.name)
        return dest

    hdrs = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=hdrs, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        fh.write(chunk)
                tmp.replace(dest)
            _record(url, dest)
            log.info("downloaded %s (%d bytes)", dest.name, dest.stat().st_size)
            return dest
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("intento %d/%d falló para %s: %s", attempt, retries, url, exc)
            time.sleep(2 * attempt)
    raise RuntimeError(f"No se pudo descargar {url}") from last_exc

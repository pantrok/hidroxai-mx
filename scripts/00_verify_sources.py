#!/usr/bin/env python
"""Etapa 00 — Verificación de disponibilidad de todas las fuentes (HEAD/GET ligero).

Recorre conf/sources.yaml y reporta qué portales/URLs responden. Útil antes de cada
snapshot mensual para detectar cambios de formato en datos abiertos federales.

Uso:
    python scripts/00_verify_sources.py
"""
from __future__ import annotations

import requests

from hidroxai_mx.utils import get_logger, load_sources

log = get_logger("00_verify")
HEADERS = {"User-Agent": "Mozilla/5.0 (HidroXAI-MX verify)"}


def _check(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        return f"{r.status_code} {'OK' if r.ok else 'FALLA'}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR {type(exc).__name__}"


def main() -> None:
    src = load_sources()["fuentes"]
    for fuente, meta in src.items():
        urls: list[str] = []
        for key in ("portal", "api_legacy"):
            if isinstance(meta.get(key), str):
                urls.append(meta[key])
        for sub in ("recursos", "portales", "paginas"):
            if isinstance(meta.get(sub), dict):
                for v in meta[sub].values():
                    if isinstance(v, str):
                        urls.append(v)
                    elif isinstance(v, dict) and "url" in v:
                        urls.append(v["url"])
        for u in dict.fromkeys(urls):
            log.info("%-16s %-7s %s", fuente, _check(u), u)


if __name__ == "__main__":
    main()

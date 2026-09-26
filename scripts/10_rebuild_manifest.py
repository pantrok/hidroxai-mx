#!/usr/bin/env python
"""Etapa 10 — Manifiesto de procedencia de data/raw reconstruido desde disco.

Registra, para cada archivo de data/raw (catálogos SIH, series por estación y CEM por
cuenca): ruta relativa, bytes, SHA-256, URL de origen y fechas. La URL de las series se
reconstruye con el patrón del portal SIH (``conagua.series_url``); la de los catálogos con
``conagua.catalog_url``; los CEM por cuenca no tienen URL propia (son mosaicos de teselas
estatales INEGI, ver scripts/06b_build_cem_per_basin.py).

Fechas: ``descargado_utc`` solo cuando la fecha real de descarga consta en un manifiesto
previo; en todos los casos se da ``modificado_utc`` (mtime del archivo), que no debe
leerse como fecha de descarga.

Salida: data/raw/_manifest.json (el anterior, si existe, se respalda como
_manifest.previo.json).
Uso:  python scripts/10_rebuild_manifest.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from hidroxai_mx.io import conagua
from hidroxai_mx.utils import RAW, get_logger, sha256

log = get_logger("10_manifest")


def main() -> None:
    path = RAW / "_manifest.json"
    previo = {}
    if path.exists():
        previo = {k.replace("\\", "/"): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
        (RAW / "_manifest.previo.json").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    entries = {}
    files = sorted(p for p in RAW.rglob("*") if p.is_file() and not p.name.startswith("_manifest"))
    for p in files:
        rel = p.relative_to(RAW).as_posix()
        parts = rel.split("/")
        if parts[0] == "sih" and p.name.startswith("catalogo_"):
            url = conagua.catalog_url(p.stem.replace("catalogo_", ""))
        elif parts[0] == "sih_series" and len(parts) == 3:
            url = conagua.series_url(parts[1], p.stem)
        else:
            url = None
        e = {"url": url, "bytes": p.stat().st_size, "sha256": sha256(p),
             "modificado_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
             "descargado_utc": previo.get(rel, {}).get("downloaded_at")}
        if parts[0] == "inegi":
            e["nota"] = "mosaico de teselas estatales CEM 3.0 (INEGI) recortado al bbox de la unidad"
        entries[rel] = e
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    con_fecha = sum(1 for e in entries.values() if e["descargado_utc"])
    log.info("Manifiesto: %d archivos (%d con fecha de descarga registrada) → %s",
             len(entries), con_fecha, path)


if __name__ == "__main__":
    main()

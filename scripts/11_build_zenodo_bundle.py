#!/usr/bin/env python
"""Etapa 11 — Paquete Zenodo del snapshot v2026.06.

Empaqueta el dataset HidroXAI-MX en un único ZIP listo para subir a Zenodo,
con un manifiesto SHA-256 y un README autocontenido en español que explica la
estructura, la procedencia y cómo citar. Toda la información se lee del
repositorio (conf/, data/, docs/, LICENSE-DATA.md, CITATION.cff) y del
metrics.json generado por scripts/09_make_report_figures.py.

Contenido del ZIP (definitivo tras las decisiones de sesión):
  raw/                     — CSV originales del SIH + catálogos + CEMs por cuenca
    sih/                     catálogos + _manifest.json (procedencia SHA-256)
    sih_series/hidrometricas/    547 CSVs
    sih_series/climatologicas/   2 659 CSVs
    inegi/                       6 CEMs cem_<cuenca>.tif (30 m / 15 m)
  processed/               — parquets canónicos + estaciones + cuencas + reportes
  features/                — feature_table.parquet
  README.md                — metadata + estructura + citación (autogenerado)
  LICENSE-DATA.md          — CC BY 4.0 (copiado del repo)
  CITATION.cff             — con placeholder de DOI Zenodo (copiado del repo)
  conf/cuencas_piloto.yaml — configuración de cuencas usada en la corrida
  manifest_zenodo.json     — SHA-256, tamaño y ruta relativa de cada archivo

Se excluyen: .npz (regla de oro), data/interim (rasters intermedios de whitebox),
data/scratch, .venv, .env, .dvc/config.local, __pycache__, .git.

Uso:
    python scripts/11_build_zenodo_bundle.py [--version v2026.06] [--out dist/]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Ruta origen -> ruta relativa dentro del ZIP.
INCLUDES: list[tuple[Path, str]] = [
    (REPO / "data" / "raw" / "sih", "raw/sih"),
    (REPO / "data" / "raw" / "sih_series" / "hidrometricas", "raw/sih_series/hidrometricas"),
    (REPO / "data" / "raw" / "sih_series" / "climatologicas", "raw/sih_series/climatologicas"),
    (REPO / "data" / "raw" / "inegi", "raw/inegi"),
    (REPO / "data" / "processed", "processed"),
    (REPO / "data" / "features", "features"),
    (REPO / "conf" / "cuencas_piloto.yaml", "conf/cuencas_piloto.yaml"),
    (REPO / "LICENSE-DATA.md", "LICENSE-DATA.md"),
    (REPO / "CITATION.cff", "CITATION.cff"),
]

# Patrones que NO se suben a Zenodo.
EXCLUDE_SUFFIXES = {".npz"}
EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints"}


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def iter_files(src: Path):
    """Recorre archivos bajo `src` aplicando los filtros de exclusión."""
    if src.is_file():
        if src.suffix in EXCLUDE_SUFFIXES:
            return
        yield src
        return
    if not src.exists():
        return
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIXES:
            continue
        yield p


def load_metrics() -> dict:
    m = REPO / "data" / "processed" / "reportes" / "metrics.json"
    if m.exists():
        return json.loads(m.read_text(encoding="utf-8"))
    return {}


def build_readme(version: str, metrics: dict, files_count: int, total_bytes: int) -> str:
    """Genera el README.md que acompaña al ZIP en Zenodo."""
    ds = metrics.get("dataset", {})
    hid = ds.get("hidrometricas", {})
    cli = ds.get("climatologicas", {})
    fig1 = metrics.get("fig1", {})
    fig8 = metrics.get("fig8", {})
    sub_by = fig8.get("subcuencas_por_cuenca", {})
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def n(x, default="—"):
        try:
            return f"{int(x):,}".replace(",", " ")
        except Exception:
            return default

    def _sub(nombre: str) -> str:
        return str(sub_by.get(nombre, "—"))

    return f"""# HidroXAI-MX — Snapshot {version}

Dataset hidroclimático reproducible para cuatro cuencas piloto de México
(Cutzamala, Lerma–Santiago —dividida en Lerma Alto / Bajío / Santiago—, Pánuco
y Alta del Balsas), construido a partir de las fuentes públicas
CONAGUA-SIH e INEGI CEM 3.0. Este ZIP es el depósito en Zenodo asociado al
artículo *data paper* enviado a **Data in Brief**.

Fecha de empaquetado: {hoy} (UTC).
Repositorio del código y pipeline: https://github.com/pantrok/hidroxai-mx.

---

## Contenido y volumen

* Archivos totales: **{files_count:,}** (aprox. **{total_bytes / 1e9:.2f} GB**).
* Estaciones hidrométricas: **{n(hid.get("n_estaciones"))}** con
  **{n(hid.get("n_filas"))}** observaciones diarias
  ({hid.get("fecha_min", "—")} → {hid.get("fecha_max", "—")}).
* Estaciones climatológicas: **{n(cli.get("n_estaciones"))}** con
  **{n(cli.get("n_filas"))}** observaciones diarias
  ({cli.get("fecha_min", "—")} → {cli.get("fecha_max", "—")}).
* Subcuencas delineadas con WhiteboxTools: **{n(fig8.get("subcuencas_total"))}**
  (Cutzamala {_sub("Cutzamala")}, Lerma Alto {_sub("Lerma Alto")},
  Bajío {_sub("Bajío")}, Santiago {_sub("Santiago")},
  Pánuco {_sub("Pánuco")}, Alta del Balsas {_sub("Alta del Balsas")}).
* Cobertura media del universo hidrométrico (2010–2025):
  **{fig1.get("cobertura_media_pct", 0):.1f} %**;
  estaciones ≥ 60 %: **{fig1.get("estaciones_ge_60pct", 0)}**;
  ≥ 80 %: **{fig1.get("estaciones_ge_80pct", 0)}**.

## Estructura

```
raw/
  sih/
    catalogo_hidrometricas.csv       catálogo oficial (SIH)
    catalogo_climatologicas.csv      catálogo oficial (SIH)
    _manifest.json                   URL + SHA-256 + fecha UTC por archivo
  sih_series/
    hidrometricas/<CLAVE>.csv        series diarias por estación
    climatologicas/<CLAVE>.csv       series diarias por estación
  inegi/
    cem_<cuenca>.tif                 6 modelos digitales de elevación

processed/
  series_hidrometricas.parquet/      canónico particionado por año
  series_climatologicas.parquet/     canónico particionado por año
  estaciones_candidatas_*.csv        universo por región hidrológica
  estaciones_seleccionadas_*.csv     conjunto principal (≥ 60 % / ≥ 80 %)
  estaciones_extendidas_hidrometricas.csv     30 %–59 % (sensibilidad)
  cuencas/                           6 GeoPackages (subcuencas delineadas)
  reportes/                          8 figuras 300 dpi + metrics.json + CSV
                                     cobertura por estación

features/
  feature_table.parquet              rezagos + medias móviles por estación

conf/cuencas_piloto.yaml             bboxes curados por cuenca
LICENSE-DATA.md                      Creative Commons Attribution 4.0 (CC BY 4.0)
CITATION.cff                         cómo citar el dataset
manifest_zenodo.json                 SHA-256 + tamaño + ruta de cada archivo
```

## Fuentes originales

* **CONAGUA — Sistema de Información Hidrológica (SIH):**
  https://sih.conagua.gob.mx (catálogos maestros y series diarias por estación).
* **INEGI — Continuo de Elevaciones Mexicano 3.0 (CEM 3.0):**
  https://www.inegi.org.mx/temas/relieve/continental/ (modelos digitales de
  elevación por entidad federativa, mosaicados y recortados por cuenca).

## Cómo reproducir

```bash
git clone https://github.com/pantrok/hidroxai-mx.git
cd hidroxai-mx
pip install -e ".[dev,geo]"
# opción 1: reconstruir desde este ZIP
unzip HidroXAI-MX-{version}.zip -d data_zenodo/
# opción 2: descargar el mismo snapshot desde el remoto DVC (Cloudflare R2)
dvc pull
python scripts/09_make_report_figures.py   # regenera las 8 figuras a 300 dpi
```

## Cómo citar

Si utilizas este dataset, cítalo como se indica en `CITATION.cff`. Al asignarse
un DOI de Zenodo se debe reemplazar el placeholder correspondiente. También se
solicita la atribución obligatoria a CONAGUA (SIH) e INEGI (CEM 3.0) por ser las
fuentes primarias.

## Licencia

Datos derivados: **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
Código y pipeline (repositorio en GitHub): **MIT**.

## Financiamiento

Proyecto **IND-2026-0335**, Instituto Politécnico Nacional (IPN), Unidad
Profesional Interdisciplinaria de Ingeniería campus Tlaxcala (UPIIT).
Convocatoria de Proyectos de Investigación Científica y Desarrollo Tecnológico
2026 (PICDT 2026), Secretaría de Investigación y Posgrado.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v2026.06", help="Etiqueta de versión del ZIP.")
    ap.add_argument("--out", default="dist", help="Carpeta de salida del ZIP.")
    ap.add_argument("--dry-run", action="store_true", help="Solo listar y calcular tamaño; no crea el ZIP.")
    args = ap.parse_args()

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"HidroXAI-MX-{args.version}.zip"
    zip_path = out_dir / zip_name

    metrics = load_metrics()

    # Inventario previo
    entries: list[tuple[Path, str]] = []
    for src, dest in INCLUDES:
        for f in iter_files(src):
            if src.is_file():
                arcname = dest
            else:
                arcname = f"{dest}/{f.relative_to(src).as_posix()}"
            entries.append((f, arcname))

    total_bytes = sum(f.stat().st_size for f, _ in entries)
    print(f"Archivos a empaquetar: {len(entries):,}  |  Tamaño sin comprimir: {total_bytes / 1e9:.2f} GB")

    if args.dry_run:
        return 0

    manifest = []
    print(f"Creando {zip_path} …")
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        # Documentos generados a partir de las métricas (README) — al final
        # para que el hash del propio README pueda registrarse.
        for i, (src, arcname) in enumerate(entries, 1):
            digest = sha256(src)
            size = src.stat().st_size
            zf.write(src, arcname=arcname)
            manifest.append({"path": arcname, "sha256": digest, "bytes": size})
            if i % 200 == 0 or i == len(entries):
                pct = 100 * i / len(entries)
                print(f"  [{i:>5}/{len(entries)}]  {pct:5.1f} %  {arcname}")

        readme = build_readme(args.version, metrics, files_count=len(entries), total_bytes=total_bytes)
        readme_bytes = readme.encode("utf-8")
        zf.writestr("README.md", readme_bytes)
        manifest.append({"path": "README.md", "sha256": hashlib.sha256(readme_bytes).hexdigest(),
                         "bytes": len(readme_bytes)})

        manifest_json = json.dumps({
            "version": args.version,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_files": len(manifest),
            "total_bytes": sum(m["bytes"] for m in manifest),
            "files": manifest,
        }, indent=2, ensure_ascii=False).encode("utf-8")
        zf.writestr("manifest_zenodo.json", manifest_json)

    zip_size = zip_path.stat().st_size
    print()
    print(f"OK  {zip_path}")
    print(f"    {len(manifest):,} archivos  |  ZIP {zip_size / 1e9:.2f} GB  (comprimido)  |  original {total_bytes / 1e9:.2f} GB")

    # Sanity check: nada .npz coló.
    with zipfile.ZipFile(zip_path) as zf:
        bad = [n for n in zf.namelist() if n.endswith(".npz")]
    if bad:
        print("ERROR: se colaron .npz:", bad[:5])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

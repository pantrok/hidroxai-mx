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
  README.md                — metadata + estructura (autogenerado, en inglés)
  LICENSE-DATA.md          — CC BY 4.0 (autogenerado, en inglés)
  conf/cuencas_piloto.yaml — configuración de cuencas usada en la corrida
  manifest_zenodo.json     — SHA-256, tamaño y ruta relativa de cada archivo

CITATION.cff no se incluye a propósito: la citación oficial la genera Zenodo
al asignar el DOI del depósito.

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
    # LICENSE-DATA.md and README.md are generated in English at packaging time.
    # CITATION.cff is intentionally excluded: Zenodo issues the canonical citation
    # when the DOI is minted.
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
    """Generate the English README.md that ships inside the Zenodo ZIP."""
    ds = metrics.get("dataset", {})
    hid = ds.get("hidrometricas", {})
    cli = ds.get("climatologicas", {})
    fig1 = metrics.get("fig1", {})
    fig8 = metrics.get("fig8", {})
    sub_by = fig8.get("subcuencas_por_cuenca", {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def n(x, default="—"):
        try:
            return f"{int(x):,}"
        except Exception:
            return default

    def _sub(name: str) -> str:
        return str(sub_by.get(name, "—"))

    return f"""# HidroXAI-MX — snapshot {version}

Reproducible hydroclimatic dataset for four pilot basins in Mexico
(Cutzamala, Lerma–Santiago —split into Lerma Alto / Bajío / Santiago—, Pánuco
and Alta del Balsas), built from the open sources CONAGUA-SIH and INEGI
CEM 3.0. This archive is the Zenodo deposit that supports the *Data in Brief*
manuscript associated with the dataset.

Packaging date: {today} (UTC).
Source code and pipeline: https://github.com/pantrok/hidroxai-mx.

---

## Contents and volume

* Total files: **{files_count:,}** (approximately **{total_bytes / 1e9:.2f} GB**
  uncompressed).
* Hydrometric stations: **{n(hid.get("n_estaciones"))}** with
  **{n(hid.get("n_filas"))}** daily observations
  ({hid.get("fecha_min", "—")} → {hid.get("fecha_max", "—")}).
* Climatological stations: **{n(cli.get("n_estaciones"))}** with
  **{n(cli.get("n_filas"))}** daily observations
  ({cli.get("fecha_min", "—")} → {cli.get("fecha_max", "—")}).
* Sub-basins delineated with WhiteboxTools: **{n(fig8.get("subcuencas_total"))}**
  (Cutzamala {_sub("Cutzamala")}, Lerma Alto {_sub("Lerma Alto")},
  Bajío {_sub("Bajío")}, Santiago {_sub("Santiago")},
  Pánuco {_sub("Pánuco")}, Alta del Balsas {_sub("Alta del Balsas")}).
* Mean coverage of the hydrometric universe (2010–2025):
  **{fig1.get("cobertura_media_pct", 0):.1f} %**;
  stations ≥ 60 %: **{fig1.get("estaciones_ge_60pct", 0)}**;
  ≥ 80 %: **{fig1.get("estaciones_ge_80pct", 0)}**.

## Layout

```
raw/
  sih/
    catalogo_hidrometricas.csv        official SIH catalog
    catalogo_climatologicas.csv       official SIH catalog
    _manifest.json                    URL + SHA-256 + UTC timestamp per file
  sih_series/
    hidrometricas/<KEY>.csv           daily series per station
    climatologicas/<KEY>.csv          daily series per station
  inegi/
    cem_<basin>.tif                   6 per-basin digital elevation models

processed/
  series_hidrometricas.parquet/       canonical, partitioned by year
  series_climatologicas.parquet/      canonical, partitioned by year
  estaciones_candidatas_*.csv         universe per hydrological region
  estaciones_seleccionadas_*.csv      primary set (≥ 60 % / ≥ 80 % coverage)
  estaciones_extendidas_hidrometricas.csv     30 %–59 % (sensitivity set)
  cuencas/                            6 GeoPackages (delineated sub-basins)
  reportes/                           8 figures at 300 dpi + metrics.json +
                                      coverage CSV per station

features/
  feature_table.parquet               lags + rolling means per station

conf/cuencas_piloto.yaml              curated per-basin bounding boxes
LICENSE-DATA.md                       Creative Commons Attribution 4.0
manifest_zenodo.json                  SHA-256, size and path for every file
```

## Original data sources

* **CONAGUA — Sistema de Información Hidrológica (SIH):**
  https://sih.conagua.gob.mx (master catalogs and daily series per station).
* **INEGI — Continuo de Elevaciones Mexicano 3.0 (CEM 3.0):**
  https://www.inegi.org.mx/temas/relieve/continental/ (state-level digital
  elevation models, mosaicked and clipped per basin).

## How to reproduce

```bash
git clone https://github.com/pantrok/hidroxai-mx.git
cd hidroxai-mx
pip install -e ".[dev,geo]"
# Option 1: rebuild directly from this archive
unzip HidroXAI-MX-{version}.zip -d data_zenodo/
# Option 2: pull the same snapshot from the DVC remote (Cloudflare R2)
dvc pull
python scripts/09_make_report_figures.py   # regenerates the 8 figures at 300 dpi
```

## How to cite

Please use the citation that Zenodo displays for this deposit once the DOI is
issued; that is the canonical reference for the dataset. Attribution to
CONAGUA (SIH) and INEGI (CEM 3.0) as primary data sources is also required.

## License

Derived data: **Creative Commons Attribution 4.0 International (CC BY 4.0)** —
see `LICENSE-DATA.md` inside this archive. Source code and pipeline
(GitHub repository): **MIT**.

## Funding

Project **IND-2026-0335**, Instituto Politécnico Nacional (IPN), Unidad
Profesional Interdisciplinaria de Ingeniería campus Tlaxcala (UPIIT).
2026 Call for Scientific Research and Technological Development Projects
(PICDT 2026), Secretaría de Investigación y Posgrado.
"""


def build_license_data_en() -> str:
    """English CC BY 4.0 statement bundled with the Zenodo archive."""
    return """# Data license

The dataset distributed in this archive (curated hydroclimatic data for
HidroXAI-MX, versioned via DVC and deposited on Zenodo) is released under
**Creative Commons Attribution 4.0 International (CC BY 4.0)** —
https://creativecommons.org/licenses/by/4.0/.

The **source code** and pipeline that produced these data are published in a
separate repository under the **MIT License**
(https://github.com/pantrok/hidroxai-mx).

## Mandatory attribution to primary sources

The dataset is a derivative work of the following open sources. When you reuse
this dataset you must also credit them, per their own terms of use:

- **CONAGUA — Sistema de Información Hidrológica (SIH) and BANDAS**:
  Términos de Libre Uso MX. Cite as "Comisión Nacional del Agua (CONAGUA),
  Sistema de Información Hidrológica, https://sih.conagua.gob.mx".
- **Servicio Meteorológico Nacional (CONAGUA)**: Términos de Libre Uso MX.
- **INEGI (CEM 3.0, hydrographic network)**: Términos de Libre Uso del INEGI.
  Cite as "Instituto Nacional de Estadística y Geografía (INEGI), Continuo de
  Elevaciones Mexicano 3.0, https://www.inegi.org.mx/temas/relieve/continental/".
- **CICESE-CLICOM** (relevant if you later extend the dataset with CLICOM series):
  academic use with the required citation "Datos climáticos diarios del CLICOM
  del SMN a través de su plataforma web del CICESE
  (http://clicom-mex.cicese.mx)".
- **CONABIO** (hydrographic mirror layers, when applicable): CC BY-NC 2.5 MX.

## Institutional credit

Data and software produced within project **IND-2026-0335**, Instituto
Politécnico Nacional (IPN), Unidad Profesional Interdisciplinaria de
Ingeniería campus Tlaxcala (UPIIT). 2026 Call for Scientific Research and
Technological Development Projects (PICDT 2026), Secretaría de Investigación y
Posgrado.
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

        license_bytes = build_license_data_en().encode("utf-8")
        zf.writestr("LICENSE-DATA.md", license_bytes)
        manifest.append({"path": "LICENSE-DATA.md",
                         "sha256": hashlib.sha256(license_bytes).hexdigest(),
                         "bytes": len(license_bytes)})

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

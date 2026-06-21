# CLAUDE.md — Guía para Claude Code · HidroXAI-MX (OE1: dataset)

Eres un asistente de ingeniería de datos para **HidroXAI-MX** (IPN, PICDT2026). Este repo
construye, valida y versiona un dataset hidroclimático de México a partir de datos abiertos
(CONAGUA-SIH, SMN, INEGI). Tu tarea típica: ejecutar el pipeline por etapas y subir el
snapshot a Cloudflare R2 con DVC, **sin pasarte de 10 GB**.

## Reglas de oro (no negociables)
1. **Presupuesto R2 = 10 GB.** Antes de CUALQUIER `dvc push`, corre `python scripts/08_storage_report.py`.
   Si falla (supera 9.5 GB), NO subas: reduce estaciones.
2. **Nunca versiones los tensores `.npz`** (ventana deslizante ≈ 9 GB con 200 estaciones).
   `07` no los genera por defecto; se regeneran al entrenar. Están en `.gitignore`.
3. **Empieza siempre pequeño:** usa `--limit` antes de bajar todo. No uses `03 --all` salvo
   que el usuario pida explícitamente el catálogo nacional completo (~5 GB sin tensores).
4. **Pide confirmación** antes de `dvc push`, `git commit`, `git push` y `git tag`.
5. **Secretos:** las llaves de R2 viven en `.env` (gitignored). Verifica que `.env` NO entre
   a git. No imprimas ni subas credenciales.

## Setup (una vez)
```bash
python -m venv .venv && source .venv/bin/activate   # o uv venv
pip install -e ".[dev,geo]"
cp .env.example .env            # edita: R2_ENDPOINT_URL, R2_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
bash scripts/setup_dvc_r2.sh    # crea el remoto DVC 'r2' (claves solo en .dvc/config.local)
pytest -q                       # debe pasar (necesita scipy; ya está en deps)
```

## Pipeline (orden) y qué hace cada etapa
- `01_download_sih_catalogs.py` → catálogos hidro/clima (CSV directo del portal SIH) en `data/raw/sih/`.
- `05_select_stations.py` → filtra por regiones piloto (12,18,26) → `estaciones_candidatas_*.csv`.
- `03_download_sih_series.py --tipo {hidrometricas|climatologicas}` → series CSV por estación
  (URL directa `/basedatos/{Hidros|Climas}/<CLAVE>.csv`). Usa las candidatas; `--limit N` para prueba.
- `04_build_canonical.py --tipo ...` → esquema canónico + Parquet particionado por año (`data/processed/`).
- `05_select_stations.py --refine` → filtra por cobertura ≥80% y calcula k vecinos clima.
- `06_delineate_basins.py` → (extra geo) delineación de cuencas con CEM+whitebox → GeoPackage.
  Requiere `data/raw/inegi/cem_<cuenca>.tif` (descárgalo del portal INEGI a la resolución de conf:
  30 m por defecto; 15 m solo Alta del Balsas). Si falta, el script avisa con el bbox.
- `07_build_features.py --no-save-tensors` → `data/features/feature_table.parquet` (compacto).
- `08_storage_report.py` → guardarraíl de tamaño antes de `dvc push`.

## Corrida por etapas
### Etapa 1 — prueba (~13 MB)
```bash
python scripts/01_download_sih_catalogs.py
python scripts/05_select_stations.py
python scripts/03_download_sih_series.py --tipo hidrometricas  --limit 5
python scripts/03_download_sih_series.py --tipo climatologicas --limit 5
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py          # OK esperado
# tras confirmar:
dvc add data/processed data/features && dvc push
```
### Etapa 2 — consolidación 4 cuencas (~0.4 GB)
```bash
python scripts/03_download_sih_series.py --tipo hidrometricas
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/05_select_stations.py --refine
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py          # guardarraíl < 9.5 GB
# tras confirmar:
dvc add data/processed data/features && dvc push && git tag v2026.06
```

## Validación y reporte
- `notebooks/02_reporte_cobertura.ipynb` genera tablas/figuras de validación (data paper) en
  `data/processed/reportes/`. La lógica está en `hidroxai_mx.report` (con pruebas).
- Corre `pytest -q` tras cualquier cambio. Mantén ≥70% de cobertura en módulos de datos.

## Convenciones del dato (no romper)
- Claves SIH como **string** (preservar ceros). Codificación de fuentes **Latin-1**.
  Faltantes `-`/vacío → NaN. Fecha `YYYY/MM/DD`. CRS pipeline **EPSG:6372**.
- Esquema canónico en `src/hidroxai_mx/data/schema.py` (validado con pandera). Banderas
  `calidad`: 0=ok, 1=imputado, 2=outlier (los outliers se marcan, no se eliminan).

## Presupuesto medido (sin tensores) — referencia
piloto ~13 MB · OE1 (200 est.) ~134 MB · 4 cuencas (~600) ~0.4 GB · catálogo (~7400) ~5.0 GB.
Tensores .npz: ~9 GB con 200 est. → NO subir.

## Qué NO hacer
- No subir `.npz`, `.env`, ni `data/raw` pesado fuera de DVC.
- No correr `03 --all` ni delineación nacional sin pedirlo.
- No exceder 9.5 GB en lo versionado (lo verifica `08`).

## Identidad del proyecto (para créditos)
- Proyecto: **IND-2026-0335** (IPN, UPIIT) — Convocatoria de Proyectos de Investigación
  Científica y Desarrollo Tecnológico 2026, Secretaría de Investigación y Posgrado.
- Responsable técnico: Daniel Sánchez Ruiz.
- Crédito obligatorio al IPN en todos los entregables. Código MIT; datos CC BY 4.0.
- Archivos de licencias/créditos: `LICENSE`, `LICENSE-DATA.md`, `CITATION.cff`, `CREDITOS.md`.

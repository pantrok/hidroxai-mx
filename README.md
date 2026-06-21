# hidroxai-mx

Biblioteca y pipeline reproducible para **HidroXAI-MX** (IPN · PICDT2026): pronóstico
explicable de niveles hidrométricos y clima local en México sobre datos abiertos de
CONAGUA, SMN e INEGI.

Este repositorio cubre **OE1 — Integración y curado del dataset nacional** (Mes 2 del
cronograma). Las capas posteriores (modelado, explicabilidad, difuso, dashboard) se
añaden sobre la misma estructura modular.

> Estado de las fuentes verificado el **2026-06-18**. Ver `conf/sources.yaml` y
> `docs/fuentes_verificacion.md` para el detalle de cada endpoint.

## Estructura

```
hidroxai-mx/
├── conf/
│   ├── sources.yaml          # Registro de fuentes (URLs verificadas, formatos, licencias)
│   └── cuencas_piloto.yaml    # Cuencas y regiones hidrológicas objetivo
├── data/                      # NO versionar el contenido (lo gestiona DVC)
│   ├── raw/                   # Tal como se descarga (inmutable)
│   ├── interim/               # Conversiones intermedias (mdb→csv, kmz→parquet)
│   ├── processed/             # Series limpias e imputadas (esquema canónico)
│   └── features/              # Tensores listos para entrenamiento
├── src/hidroxai_mx/
│   ├── io/                    # Conectores de descarga (CONAGUA/SMN/INEGI/DataMéxico)
│   ├── data/                  # Esquemas (pandera), limpieza, imputación, persistencia
│   ├── features/              # Lags, SPI/SPEI, STL, ventanas, tensores
│   └── utils/                 # Logging, caché, geo, fechas
├── scripts/                   # Entrypoints ejecutables por etapa (01..05)
├── notebooks/                 # Exploración y reportes de cobertura
├── tests/                     # Pruebas de esquema y de I/O
├── pyproject.toml
├── dvc.yaml                    # Stages del pipeline de datos
└── Makefile
```

## Quickstart

```bash
# 1. Entorno (uv recomendado; pip funciona igual)
uv venv && source .venv/bin/activate        # o: python -m venv .venv
uv pip install -e ".[dev]"                   # o: pip install -e ".[dev]"

# 2. Descargar catálogos maestros del SIH (rápido, ~1 MB)
python scripts/01_download_sih_catalogs.py

# 3. Descargar catálogos espaciales de redes meteorológicas (KMZ/XLSX)
python scripts/02_download_smn_kmz.py

# 4. Descargar series históricas diarias del SIH (CSV, cobertura reciente 2010–2025)
python scripts/03_download_sih_series.py --tipo hidrometricas

# 5. Construir el esquema canónico y persistir en Parquet particionado
python scripts/04_build_canonical.py

# 6. (Opcional) Versionar el snapshot con DVC
dvc add data/processed && git add data/processed.dvc && git commit -m "dataset v0.1"
```

## Decisión de fuentes (importante)

El inventario original (`datasets_HidroXAI_MX.docx`) apuntaba a los catálogos estáticos
de `datos.gob.mx` y a las series históricas en archivos `.mdb` de **BANDAS**. La
verificación en vivo (2026-06-18) encontró que:

- El **portal SIH** (`https://sih.conagua.gob.mx`) ahora publica las **series históricas
  diarias de estaciones climatológicas e hidrométricas como CSV UTF-8**, con
  actualización semanal. Es la **fuente primaria recomendada** para la cobertura
  2010–2025 (no requiere conversión `.mdb`).
- **BANDAS** (`https://app.conagua.gob.mx/bandas`) sigue activo y se usa como **respaldo
  histórico profundo** (pre-2013) y para el catálogo/series de **presas**.
- **DataMéxico** migró a `https://www.economia.gob.mx/datamexico`; su API Tesseract debe
  reconfirmarse antes de usarse (capa socioeconómica auxiliar, prioridad baja).

Ver `docs/fuentes_verificacion.md`.

## Licencias

Código: **MIT**. Datos derivados redistribuibles: **CC BY 4.0** (compatible con Libre Uso
MX). Atribución obligatoria a CONAGUA, SMN, INEGI y CICESE-CLICOM según corresponda.

---

## Flujo de ingesta actualizado (verificado 2026-06-18)

El SIH publica **CSV directos por estación** (`/basedatos/{Hidros|Climas}/<CLAVE>.csv`),
por lo que la ingesta es dirigida por catálogo (sin parseo de HTML ni selector JS):

```bash
python scripts/01_download_sih_catalogs.py     # catálogos hidro + clima (CSV)
python scripts/05_select_stations.py            # candidatas por región hidrológica (12,18,26)
python scripts/03_download_sih_series.py --tipo hidrometricas    # descarga dirigida por candidatas
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/04_build_canonical.py --tipo hidrometricas        # esquema canónico -> Parquet
python scripts/05_select_stations.py --refine   # filtra por cobertura >=80% + k vecinos clima
```

Notas de formato: codificación **Latin-1**; faltantes `-`/vacío; fecha `YYYY/MM/DD`; el lector
salta el bloque de metadatos y normaliza encabezados automáticamente.

## CEM (INEGI): resolución

`conf/sources.yaml` fija `resolucion_default: 30` m. En `conf/cuencas_piloto.yaml`,
la **Alta del Balsas** usa **15 m** (cuenca pequeña de cabecera); el resto, 30 m.
Descargar recortado al bbox de cada cuenca (no el mosaico nacional).

## Almacenamiento remoto: Cloudflare R2 (DVC)

R2 es S3-compatible y sin costo de egreso (10 GB gratis). Configuración:

```bash
cp .env.example .env          # completa R2_ENDPOINT_URL y las llaves S3 de R2
bash scripts/setup_dvc_r2.sh  # crea el remoto 'r2' (claves solo en .dvc/config.local)
dvc add data/processed && dvc push   # versiona y sube el snapshot
git add data/processed.dvc .dvc/config && git commit -m "dataset v0.1" && git tag v2026.06
```

## Acceso remoto desde un notebook

Ver `notebooks/01_acceso_datos_r2.ipynb` (Colab/Jupyter): instala `dvc[s3]`, fija las
credenciales R2 por variables de entorno y trae los datos con `dvc pull` (todo el dataset)
o `dvc.api.get_url(...)` (un archivo puntual), luego `pd.read_parquet(...)`.

## Subflujo geoespacial (script 06) y features (script 07)

Requiere el extra geo:  `pip install -e ".[geo]"`

```bash
# 06 — delineación de cuencas (necesita el CEM por cuenca en data/raw/inegi/cem_<cuenca>.tif)
python scripts/06_delineate_basins.py --threshold 1000
#   CEM(tif) -> fill_depressions -> d8_pointer + flow_accumulation -> extract_streams
#   -> snap pour points (estaciones) -> watershed -> GeoPackage por cuenca
#   (área_km2, elevación_media, pendiente_media) en data/processed/cuencas/<cuenca>.gpkg

# 07 — features y tensores
python scripts/07_build_features.py --t-in 256 --horizon 7
#   une clima vecino por IDW (pot. 2) a cada estación hidrométrica, genera lags
#   (1/3/7/14/30) y medias móviles, normaliza por estación y arma tensores (B,T,F)
#   -> data/features/feature_table.parquet y data/features/tensors_h7.npz
```

El módulo `hidroxai_mx.geo` (delineación + uniones espaciales) y las funciones de
`hidroxai_mx.features` (lags, SPI/SPEI, STL, IDW, ventanas) importan las dependencias
pesadas (whitebox/rasterio/geopandas) de forma diferida.

## Reporte de cobertura y validación (notebook 02)

`notebooks/02_reporte_cobertura.ipynb` genera las tablas y figuras de validación del
*data paper* (inventario, cobertura, estadística descriptiva, calidad, consistencia entre
fuentes, coherencia espacial, patrones temporales, precip→gasto y procedencia). La lógica
vive en `hidroxai_mx.report` (con pruebas). Si no hay Parquet aún, el notebook simula un
dataset de demostración. Las salidas se guardan en `data/processed/reportes/`.

## Corrida oficial por etapas (presupuesto R2 = 10 GB)

> El `dvc push` se ejecuta en **tu** máquina con **tus** credenciales R2 (el repo no las
> incluye). **Regla de oro: NO versionar los tensores `.npz`** (se generan al entrenar);
> con eso, hasta el catálogo nacional completo (~5 GB) cabe en 10 GB.

Presupuesto **medido** (Parquet, sin tensores):

| Alcance | raw CSV | canónico | features | Total |
|---|---|---|---|---|
| Piloto (~20 est.) | ~1 MB | ~2 MB | ~10 MB | **~13 MB** |
| OE1 (~200 est.) | ~10 MB | ~24 MB | ~100 MB | **~134 MB** |
| 4 cuencas (~600 est.) | ~30 MB | ~71 MB | ~301 MB | **~402 MB** |
| Catálogo (~7400 est.) | ~370 MB | ~878 MB | ~3.7 GB | **~5.0 GB** |

Riesgo: los `.npz` de ventana deslizante (stride 1) pesan ~9 GB con 200 estaciones y ~336 GB
con el catálogo → por eso `07` no los materializa por defecto y `08` falla si se superan 9.5 GB.
Súmale el CEM por cuenca (30 m: ~0.1–0.5 GB c/u); aun así cabe holgado.

### Etapa 1 — Prueba (pocos datos, ~13 MB)
```bash
python scripts/01_download_sih_catalogs.py
python scripts/05_select_stations.py
python scripts/03_download_sih_series.py --tipo hidrometricas  --limit 5
python scripts/03_download_sih_series.py --tipo climatologicas --limit 5
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py        # debe decir OK (dentro del presupuesto)
dvc add data/processed data/features && dvc push
```

### Etapa 2 — Consolidación (4 cuencas piloto, ~0.4 GB)
```bash
python scripts/03_download_sih_series.py --tipo hidrometricas     # todas las candidatas
python scripts/03_download_sih_series.py --tipo climatologicas
python scripts/05_select_stations.py --refine                     # cobertura >=80% + vecinos
python scripts/04_build_canonical.py --tipo hidrometricas
python scripts/04_build_canonical.py --tipo climatologicas
python scripts/07_build_features.py --no-save-tensors
python scripts/08_storage_report.py        # guardarraíl: falla si > 9.5 GB
dvc add data/processed data/features && dvc push && git tag v2026.06
```

`03 --all` descarga el catálogo nacional completo (~5 GB sin tensores): cabe, pero solo úsalo
si de verdad quieres cobertura nacional. Ajusta el tope con `R2_CAP_GB` si cambias de plan.

## Créditos y financiamiento

Proyecto **IND-2026-0335** — "Pronóstico explicable de niveles hidrométricos y clima
local en México mediante aprendizaje profundo temporal y reglas difusas, sobre datos
abiertos de CONAGUA y el Servicio Meteorológico Nacional".

Desarrollado en el **Instituto Politécnico Nacional (IPN)**, Unidad Profesional
Interdisciplinaria de Ingeniería campus Tlaxcala (**UPIIT**), en el marco de la
**Convocatoria de Proyectos de Investigación Científica y Desarrollo Tecnológico 2026**
de la **Secretaría de Investigación y Posgrado**. Responsable técnico: **Daniel Sánchez Ruiz**.

Licencias: código **MIT** (`LICENSE`); datos derivados **CC BY 4.0** (`LICENSE-DATA.md`).
Cómo citar: ver `CITATION.cff`. Créditos completos: `CREDITOS.md`.

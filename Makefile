.PHONY: install verify catalogs smn series canonical all test lint

install:
	uv pip install -e ".[dev]" || pip install -e ".[dev]"

verify:        ## Verificar disponibilidad de todas las fuentes
	python scripts/00_verify_sources.py

catalogs:      ## Descargar catálogos maestros SIH
	python scripts/01_download_sih_catalogs.py

smn:           ## Descargar catálogos espaciales SMN (KMZ/XLSX)
	python scripts/02_download_smn_kmz.py

series:        ## Descargar series históricas SIH (CSV)
	python scripts/03_download_sih_series.py --tipo hidrometricas

canonical:     ## Construir dataset canónico (Parquet)
	python scripts/04_build_canonical.py --tipo hidrometricas

all: catalogs smn series canonical

test:
	pytest

lint:
	ruff check src scripts tests && mypy src

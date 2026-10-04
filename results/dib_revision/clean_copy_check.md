# Prueba desde copia limpia — HidroXAI-MX-v2026.10.zip

- Fecha: 2026-10-04; ZIP SHA-256 `ff8944c00c544f5aee1f794d3a49ac16310d906ec879bf7e3cd34fefbcc8c4f8`.
- Python del entorno nuevo: 3.12.6; sistema: Windows-11-10.0.26200-SP0.
- Tiempo total: 11.4 min (pip install: 5.2 min).
- Resultado: **hay diferencias**; valores (JSON y CSV) idénticos; figuras idénticas por píxel: 6/7.

## Versiones de bibliotecas

| Paquete | entorno_nuevo | repositorio (salidas empaquetadas) |
|---|---|---|
| matplotlib | 3.11.2 | 3.11.0 |
| geopandas | 1.2.0 | 1.1.3 |
| shapely | 2.1.2 | 2.1.2 |
| pyproj | 3.8.0 | 3.7.2 |
| pyogrio | 0.13.0 | 0.12.1 |
| numpy | 2.5.3 | 2.4.6 |
| pandas | 3.0.6 | 3.0.3 |
| pyarrow | 25.0.1 | 24.0.0 |
| pandera | 0.33.1 | 0.32.0 |
| pillow | 12.3.0 | 12.2.0 |

## Comandos

```
C:\Python312\python.exe -m venv <copia_limpia>\venv  # 9.5 s
<copia_limpia>\venv\Scripts\python.exe -m pip install -q --upgrade pip  # 9.4 s
<copia_limpia>\venv\Scripts\python.exe -m pip install -q -e .[dev,geo]  # 309.1 s
descarga https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip  #  s
descarga http://www.conabio.gob.mx/informacion/gis/maps/geo/rh250kgw.zip  #  s
descarga http://www.conabio.gob.mx/informacion/gis/maps/geo/cue250kgw.zip  #  s
<copia_limpia>\venv\Scripts\python.exe -W ignore -m pytest -q -p no:cacheprovider -o addopts=  # 16.1 s
<copia_limpia>\venv\Scripts\python.exe -W ignore scripts/09_make_report_figures.py  # 90.0 s
<copia_limpia>\venv\Scripts\python.exe -W ignore scripts/12_make_workflow_figure.py  # 2.0 s
<copia_limpia>\venv\Scripts\python.exe -W ignore scripts/dib_01_reconcile_counts.py --suffix _v2026_10  # 220.5 s
<copia_limpia>\venv\Scripts\python.exe -W ignore scripts/dib_13_paso2_tables.py  # 1.2 s
<copia_limpia>\venv\Scripts\python.exe -W ignore scripts/dib_14_pilot_basin_outlines.py  # 2.0 s
```

## Comparación (regenerado vs empaquetado)

| Archivo | Resultado | Detalle |
|---|---|---|
| `processed/reportes/metrics.json` | igual | valores (sin fechas de ejecución) |
| `processed/reportes/cobertura_por_estacion.csv` | igual | 547 filas |
| `processed/reportes/precip_streamflow_lagcorr.csv` | igual | 31 filas |
| `processed/reportes/Fig1_workflow.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `processed/reportes/Fig2_station_map.png` | difiere | 4946 píxeles distintos (0.15 %), dentro de x 271–680, y 81–343 de 1994×1701 px |
| `processed/reportes/Fig3_quality_flags.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `processed/reportes/Fig4_inventory_coverage.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `processed/reportes/Fig5_streamflow_by_region.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `processed/reportes/Fig6_climatology_annual.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `processed/reportes/Fig7_precip_streamflow.png` | igual | píxeles idénticos; bytes distintos (metadatos del PNG) |
| `results/dib_revision/counts_reconciliation_v2026_10.csv` | igual | 17 filas |
| `results/dib_revision/observation_counts_v2026_10.csv` | igual | 2 filas |
| `results/dib_revision/calidad_composition_v2026_10.csv` | igual | 15 filas |
| `results/dib_revision/tabla3_v2026_10.csv` | igual | 6 filas |
| `results/dib_revision/hidrorivers_sin_vinculo.csv` | igual | 8 filas |
| `results/dib_revision/e13_paso2_t1.json` | igual | valores (sin fechas de ejecución) |
| `results/dib_revision/pilot_basin_outlines.csv` | igual | 21 filas |

Se ignoran las claves con la fecha de ejecución y el bloque `duplicados_v2026_06`, que se calcula sobre parquets del release v2026.06 que no viajan en el archivo. Una figura con diferencias de píxeles y valores idénticos refleja el dibujo de versiones distintas de las bibliotecas (tabla de versiones), no un cambio del dato.

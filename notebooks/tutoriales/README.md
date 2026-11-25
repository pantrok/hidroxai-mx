# Tutoriales de HidroXAI-MX

Cinco notebooks en español que corren en Google Colab sin credenciales. Instalan la
biblioteca desde GitHub y leen el dataset Hidro-MX v2026.11 directamente de Zenodo
([10.5281/zenodo.24119292](https://doi.org/10.5281/zenodo.24119292)): solo se descargan los
archivos del ZIP que se usan.

| Notebook | Contenido | Colab |
|---|---|---|
| `01_cargar_dataset.ipynb` | Estructura del ZIP, serie de una estación, banderas de calidad 0/1/2 y estaciones por unidad | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/01_cargar_dataset.ipynb) |
| `02_cobertura_seleccion.ipynb` | Cobertura por estación y por unidad; reproduce la selección de las 101 estaciones hidrométricas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/02_cobertura_seleccion.ipynb) |
| `03_entrenar_evaluar.ipynb` | Ventanas de 30 días, partición cronológica, persistencia, XGBoost y una TCN en Alta del Balsas; NSE, KGE y skill score | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/03_entrenar_evaluar.ipynb) |
| `04_explicaciones.ipynb` | TreeSHAP e Integrated Gradients; mapa variable × día; acuerdo entre dos semillas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/04_explicaciones.ipynb) |
| `05_alertas_difusas.ipynb` | Sistema Mamdani (percentil y dispersión) contra un umbral; POD, FAR y CSI; línea de tiempo de alertas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/05_alertas_difusas.ipynb) |

- **Cifras.** Las de los tutoriales 03–05 son ilustrativas: usan una cuenca y pocos modelos. Los
  resultados del benchmark están en [`results/xai_benchmark/`](../../results/xai_benchmark/).
- **Ejecución sin red.** Con `HIDROXAI_MX_ZIP=<ruta del ZIP>` los notebooks leen una copia local
  del archivo de Zenodo.
- **Modo reducido.** Con `HIDROXAI_TUTORIAL_REDUCIDO=1` usan 3 estaciones y 1 época. Así los
  ejecuta la integración continua.

Proyecto IND-2026-0335 · Instituto Politécnico Nacional (IPN) · Convocatoria PICDT2026. Datos:
CONAGUA (Sistema de Información Hidrológica), INEGI y HydroSHEDS.

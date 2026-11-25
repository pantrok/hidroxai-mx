# Tutoriales

Cinco notebooks en español que corren en Google Colab sin credenciales. Cada uno instala la
biblioteca desde GitHub y lee el dataset Hidro-MX v2026.11 directamente de Zenodo; solo se
descargan los archivos del ZIP que se usan. Limitados a 2 hilos de CPU, como en Colab, cada uno
tardó entre 0.5 y 3.3 minutos, sin contar la instalación ni la descarga de datos.

| Tutorial | Contenido | Colab |
|---|---|---|
| [1 · Cargar el dataset](01_cargar_dataset.ipynb) | Estructura del ZIP, serie de una estación, banderas de calidad 0/1/2 y estaciones por unidad | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/01_cargar_dataset.ipynb) |
| [2 · Cobertura y selección](02_cobertura_seleccion.ipynb) | Cobertura por estación y por unidad; reproduce la selección de las 101 estaciones hidrométricas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/02_cobertura_seleccion.ipynb) |
| [3 · Entrenar y evaluar](03_entrenar_evaluar.ipynb) | Ventanas de 30 días, partición cronológica, persistencia, XGBoost y una TCN en Alta del Balsas; NSE, KGE y skill score | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/03_entrenar_evaluar.ipynb) |
| [4 · Explicaciones](04_explicaciones.ipynb) | TreeSHAP e Integrated Gradients; mapa variable × día; acuerdo entre dos semillas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/04_explicaciones.ipynb) |
| [5 · Alertas difusas](05_alertas_difusas.ipynb) | Sistema Mamdani (percentil y dispersión) contra un umbral; POD, FAR y CSI; línea de tiempo de alertas | [Abrir](https://colab.research.google.com/github/pantrok/hidroxai-mx/blob/main/notebooks/tutoriales/05_alertas_difusas.ipynb) |

!!! warning "Cifras ilustrativas"
    Los tutoriales 3 a 5 usan una cuenca, un horizonte y pocos modelos. Sus cifras ilustran el
    procedimiento; los resultados del benchmark están en
    [`results/xai_benchmark/`](https://github.com/pantrok/hidroxai-mx/tree/main/results/xai_benchmark).

- **Sin red.** Con `HIDROXAI_MX_ZIP=<ruta del ZIP>` los notebooks leen una copia local del
  archivo de Zenodo.
- **Modo reducido.** Con `HIDROXAI_TUTORIAL_REDUCIDO=1` usan 3 estaciones y 1 época. Así los
  ejecuta la integración continua en cada cambio del repositorio.

# Instalación

!!! note "Sin paquete en PyPI"
    No hay paquete en PyPI en esta versión. La biblioteca se instala desde GitHub.

Requiere Python 3.10 o posterior.

## Uso

```bash
pip install "git+https://github.com/pantrok/hidroxai-mx@main"
```

Para entrenar modelos y calcular explicaciones (torch, XGBoost y Captum), agrega el extra `ml`:

```bash
pip install "hidroxai-mx[ml] @ git+https://github.com/pantrok/hidroxai-mx@main"
```

| Extra | Para qué |
|---|---|
| `ml` | modelos (torch, XGBoost) e Integrated Gradients (Captum) |
| `geo` | geoprocesamiento del pipeline (delineación, recorte de modelos de elevación) |
| `dev` | pruebas, lint, DVC y Jupyter |
| `docs` | construir este sitio |

## Google Colab

Colab ya trae pandas, pyarrow, matplotlib, torch y XGBoost, así que los tutoriales instalan la
biblioteca sin dependencias y solo agregan Captum:

```bash
pip install --no-deps "git+https://github.com/pantrok/hidroxai-mx@main"
pip install captum
```

## Desarrollo

```bash
git clone https://github.com/pantrok/hidroxai-mx.git
cd hidroxai-mx
python -m venv .venv
# Windows: .venv\Scripts\activate · Linux y macOS: source .venv/bin/activate
pip install -e ".[dev,geo,ml]"
pytest
```

## Datos sin red

`hidroxai_mx.dataset` lee el ZIP del dataset directamente de Zenodo y guarda en caché
(`~/.cache/hidroxai_mx`) cada archivo que lee. Para trabajar sin red, descarga el ZIP de
[Zenodo](https://doi.org/10.5281/zenodo.24119292) y apunta a él:

```bash
export HIDROXAI_MX_ZIP=/ruta/HidroXAI-MX-v2026.11.zip     # Windows: set HIDROXAI_MX_ZIP=...
```

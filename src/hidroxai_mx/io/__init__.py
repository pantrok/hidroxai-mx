"""Conectores de ingesta (Capa 1). Cada submódulo expone funciones `download_*`
que descargan a data/raw/<fuente>/ y devuelven las rutas locales."""
from . import conagua, inegi, smn  # noqa: F401

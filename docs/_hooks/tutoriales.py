"""Hook de mkdocs: copia los notebooks de ``notebooks/tutoriales/`` a ``docs/tutoriales/``.

Los notebooks viven en un solo lugar del repositorio; la copia en ``docs/tutoriales/`` no se
versiona (``.gitignore``). Solo se copia lo que cambió, para no disparar recargas en
``mkdocs serve``.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def on_pre_build(config, **kwargs) -> None:
    raiz = Path(config["config_file_path"]).parent
    origen = raiz / "notebooks" / "tutoriales"
    destino = Path(config["docs_dir"]) / "tutoriales"
    destino.mkdir(exist_ok=True)
    for nb in sorted(origen.glob("*.ipynb")):
        copia = destino / nb.name
        if not copia.exists() or copia.read_bytes() != nb.read_bytes():
            shutil.copy2(nb, copia)

"""Manifiesto de cómputo del benchmark: una fila por corrida, con columnas fijas."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = ["fecha", "tipo", "run", "modelo", "config", "cuenca", "h", "semilla", "dispositivo", "hilos",
           "epocas", "segundos", "pared_s", "mejor_val_mse", "parada_temprana", "parametros"]


def append(path: Path, **row) -> None:
    """Agrega una fila con el esquema fijo (las columnas ausentes quedan vacías)."""
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise ValueError(f"Columnas no previstas en el manifiesto: {sorted(unknown)}")
    df = pd.DataFrame([row]).reindex(columns=COLUMNS)
    df.to_csv(path, mode="a", header=not Path(path).exists(), index=False)

"""Criterios congelados de H1–H3 (protocolo §7) como funciones.

Sirven para aplicar la misma regla en la partición principal y en cada pliegue del
walk-forward. Cada IC es una terna (mediana o punto, límite inferior, límite superior).
"""
from __future__ import annotations

import numpy as np

CI = tuple[float, float, float]


def h1(ci: dict[str, CI]) -> str:
    """ci: {"<modelo>_h<h>": IC de la mediana de SS} para los modelos aprendidos, h ∈ {7, 14}."""
    n_pos = {h: sum(v[1] > 0 for k, v in ci.items() if k.endswith(f"_h{h}")) for h in (7, 14)}
    if all(n_pos[h] >= 3 for h in (7, 14)):
        return "SUPPORTED"
    return "REJECTED" if not any(v[1] > 0 for v in ci.values()) else "OPEN"


def h1b(cis: list[CI]) -> str:
    """IC de la mediana de ΔNSE (profundo − XGBoost) de los modelos profundos, en un horizonte."""
    if any(c[1] > 0 for c in cis):
        return "SUPPORTED"
    return "REJECTED" if cis and all(c[2] < 0 for c in cis) else "OPEN"


def h2a(medians) -> str:
    """Medianas de Spearman por combinación cuenca (≥ 8 estaciones) × horizonte."""
    med = np.asarray(list(medians), dtype=float)
    if (med >= 0.5).mean() >= 2 / 3:
        return "SUPPORTED"
    return "REJECTED" if (med < 0.3).mean() > 0.5 else "OPEN"


def h2b(proportion: float) -> str:
    """Proporción de pares (modelo, cuenca) con el rezago de precipitación más importante en 1–3 días."""
    return "SUPPORTED" if proportion >= 0.75 else ("REJECTED" if proportion < 0.5 else "OPEN")


def h3(p90_h1: CI, p90_h7: CI) -> str:
    """IC de ΔCSI (difuso − umbral) para eventos P90 a h = 1 y h = 7."""
    key = (p90_h1, p90_h7)
    if all(d[1] > 0 for d in key):
        return "SUPPORTED"
    if any(d[2] < 0 for d in key) or all(d[1] <= 0 <= d[2] for d in key):
        return "REJECTED"
    return "OPEN"


def stability(yearly: dict[int, str], main: str) -> dict:
    """Robustez (especificación del walk-forward): coincidencias del veredicto anual con el principal."""
    same = [y for y, v in yearly.items() if v == main]
    other = {y: v for y, v in yearly.items() if v != main}
    n = len(same)
    label = ("estable" if n == len(yearly) else
             "estable con excepciones" if n >= 3 else "inestable")
    return {"veredicto_principal": main, "por_año": {str(y): v for y, v in yearly.items()},
            "coincidencias": n, "años": len(yearly), "excepciones": {str(y): v for y, v in other.items()},
            "robustez": label}

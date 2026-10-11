"""Alertas difusas Mamdani (protocolo, sección 6).

El motor (funciones de pertenencia, variables, reglas, inferencia mín–máx con
defuzzificación por centroide) se copió sin cambios de lógica de
``hidroxmx-forecasting`` (``src/hidroxmx/alert/fuzzy.py``, commit 32690cb, mismo autor).
Aquí se añaden la inferencia vectorizada por bloques y el sistema del protocolo de este
benchmark: entradas *percentil* (del pronóstico de ensamble en la distribución de
entrenamiento de la estación) y *dispersión* (rango intercuartílico de los percentiles de
los miembros), salida *nivel* ∈ [0, 3] (normal, vigilancia, alerta, emergencia).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

LEVELS = ("normal", "vigilancia", "alerta", "emergencia")


# --------------------------------------------------------------------------- funciones de pertenencia
class MembershipFunction:
    def __call__(self, x):  # pragma: no cover
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class TriangularMF(MembershipFunction):
    """Triangular con vértices a < b < c."""
    a: float
    b: float
    c: float

    def __call__(self, x):
        x = np.asarray(x, dtype=float)
        left = (x - self.a) / max(self.b - self.a, 1e-12)
        right = (self.c - x) / max(self.c - self.b, 1e-12)
        return np.clip(np.minimum(left, right), 0.0, 1.0)


@dataclass(slots=True, frozen=True)
class TrapezoidalMF(MembershipFunction):
    """Trapezoidal con vértices a ≤ b ≤ c ≤ d.

    Con hombro vertical (a = b o c = d) la pertenencia en el vértice es 1: trapecio (0, 0, …)
    vale 1 en x = 0 y (…, 1, 1) vale 1 en x = 1. La versión copiada de forecasting daba 0 en
    ese punto (división entre 1e-12 de un numerador nulo); corregido el 2026-10-10.
    """
    a: float
    b: float
    c: float
    d: float

    def __call__(self, x):
        x = np.asarray(x, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            left = np.where(x >= self.b, 1.0, (x - self.a) / (self.b - self.a))
            right = np.where(x <= self.c, 1.0, (self.d - x) / (self.d - self.c))
        return np.clip(np.minimum(left, right), 0.0, 1.0)


# --------------------------------------------------------------------------- variables y reglas
@dataclass(slots=True)
class FuzzyVariable:
    name: str
    universe_min: float
    universe_max: float
    mfs: dict[str, MembershipFunction] = field(default_factory=dict)


@dataclass(slots=True)
class MamdaniRule:
    """Antecedentes unidos con mín (Y); el consecuente es (variable de salida, conjunto)."""
    antecedent: dict[str, str]
    consequent: tuple[str, str]
    weight: float = 1.0

    def activation(self, mu_inputs: dict[str, dict[str, float]]) -> float:
        acts = [mu_inputs[var][mf] for var, mf in self.antecedent.items()]
        return float(self.weight * min(acts)) if acts else 0.0


@dataclass(slots=True)
class MamdaniFIS:
    inputs: dict[str, FuzzyVariable]
    output: FuzzyVariable
    rules: list[MamdaniRule]
    resolution: int = 201

    def _universe(self) -> np.ndarray:
        return np.linspace(self.output.universe_min, self.output.universe_max, self.resolution)

    def infer(self, values: dict[str, float]) -> float:
        """Una observación → centroide (motor original)."""
        mu = {n: {k: float(mf(x)) for k, mf in self.inputs[n].mfs.items()} for n, x in values.items()}
        u = self._universe()
        agg = np.zeros_like(u)
        for rule in self.rules:
            out_mf = self.output.mfs[rule.consequent[1]]
            agg = np.maximum(agg, np.minimum(out_mf(u), rule.activation(mu)))
        total = agg.sum()
        return float((u * agg).sum() / total) if total > 0 else float(self.output.universe_min)

    def infer_array(self, batch: dict[str, np.ndarray], chunk: int = 4096) -> np.ndarray:
        """Inferencia vectorizada; mismo resultado que `infer` punto a punto."""
        n = len(next(iter(batch.values())))
        u = self._universe()
        out_mu = {k: mf(u) for k, mf in self.output.mfs.items()}
        res = np.empty(n)
        for s in range(0, n, chunk):
            sl = slice(s, min(s + chunk, n))
            mu = {v: {k: mf(np.asarray(batch[v][sl], dtype=float)) for k, mf in self.inputs[v].mfs.items()}
                  for v in batch}
            agg = np.zeros((sl.stop - sl.start, len(u)))
            for rule in self.rules:
                act = rule.weight * np.minimum.reduce([mu[v][m] for v, m in rule.antecedent.items()])
                agg = np.maximum(agg, np.minimum(out_mu[rule.consequent[1]][None, :], act[:, None]))
            tot = agg.sum(1)
            with np.errstate(invalid="ignore", divide="ignore"):
                res[sl] = np.where(tot > 0, (agg * u).sum(1) / tot, self.output.universe_min)
        return res

    def rules_table(self) -> pd.DataFrame:
        """Reglas como tabla legible (para el artículo y el dashboard)."""
        return pd.DataFrame([{**{v: m for v, m in r.antecedent.items()}, self.output.name: r.consequent[1]}
                             for r in self.rules])


# --------------------------------------------------------------------------- sistema del protocolo
def build_protocol_fis() -> MamdaniFIS:
    """Funciones de pertenencia y reglas congeladas en `results/xai_benchmark/protocol.md` §6."""
    pct = FuzzyVariable("percentil", 0.0, 1.0, {
        "bajo": TrapezoidalMF(0.0, 0.0, 0.70, 0.80),
        "alto": TriangularMF(0.70, 0.85, 0.92),
        "muy_alto": TriangularMF(0.88, 0.94, 0.985),
        "extremo": TrapezoidalMF(0.97, 0.99, 1.0, 1.0),
    })
    disp = FuzzyVariable("dispersion", 0.0, 1.0, {
        "baja": TrapezoidalMF(0.0, 0.0, 0.05, 0.15),
        "alta": TrapezoidalMF(0.05, 0.15, 1.0, 1.0),
    })
    level = FuzzyVariable("nivel", 0.0, 3.0, {name: TriangularMF(i - 1.0, float(i), i + 1.0)
                                              for i, name in enumerate(LEVELS)})
    table = {("bajo", "baja"): "normal", ("bajo", "alta"): "normal",
             ("alto", "baja"): "vigilancia", ("alto", "alta"): "vigilancia",
             ("muy_alto", "baja"): "alerta", ("muy_alto", "alta"): "vigilancia",
             ("extremo", "baja"): "emergencia", ("extremo", "alta"): "alerta"}
    rules = [MamdaniRule({"percentil": p, "dispersion": d}, ("nivel", out)) for (p, d), out in table.items()]
    return MamdaniFIS({"percentil": pct, "dispersion": disp}, level, rules)


def level_index(score) -> np.ndarray:
    """Nivel = entero más cercano al centroide (0 normal … 3 emergencia)."""
    return np.clip(np.rint(np.asarray(score, dtype=float)), 0, 3).astype(int)


def station_percentile(values, train_obs) -> np.ndarray:
    """Percentil empírico de `values` en la distribución de entrenamiento de la estación."""
    ref = np.sort(np.asarray(train_obs, dtype=float)[np.isfinite(train_obs)])
    return np.searchsorted(ref, np.asarray(values, dtype=float), side="right") / max(len(ref), 1)

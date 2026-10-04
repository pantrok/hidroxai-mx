#!/usr/bin/env python
"""P2-T2 — Valores climatológicos fuera de límites físicos (revisión DIB-D-26-01662).

--antes   : lista los valores fuera de `schema.PHYSICAL_LIMITS` en los CSV crudos leídos con
            el parser vigente, con la bandera que su fila tiene en la serie actual
            -> results/dib_revision/clima_fuera_de_rango.csv
--despues : compara fila por fila las series reconstruidas con las archivadas. Éxito
            (enmienda P2-T2a del proof ledger) si solo pasan a calidad = 2 las filas del CSV,
            ningún valor cambia salvo tmax_c/tmin_c de NaN a valor, y la serie hidrométrica
            queda idéntica. Escribe también la composición de `calidad` por bandera y por
            variable -> results/dib_revision/e12_clima_limites.json

Uso:
    python scripts/dib_12_clima_physical_limits.py --antes
    python scripts/dib_12_clima_physical_limits.py --despues \
        --previa data/interim/dib_revision/v2026.10_pre_p2/series_climatologicas.parquet \
        --previa-hidro data/interim/dib_revision/v2026.10_pre_p2/series_hidrometricas.parquet
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import click
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as ds

from hidroxai_mx.data.schema import PHYSICAL_LIMITS
from hidroxai_mx.io import conagua
from hidroxai_mx.utils import PROCESSED, RAW, ROOT, get_logger

log = get_logger("dib_12")
OUT = ROOT / "results" / "dib_revision"
CSV = OUT / "clima_fuera_de_rango.csv"
SERIE = PROCESSED / "series_climatologicas.parquet"
KEY = ["clave_estacion", "fecha"]


def _dataset(path: Path) -> ds.Dataset:
    return ds.dataset(path, format="parquet", partitioning="hive")


def _value_cols(d: ds.Dataset) -> list[str]:
    skip = set(KEY) | {"fuente", "calidad", "anio"}
    return [c for c in d.schema.names if c not in skip and not c.startswith("__")]


def _limit_tests(lo, hi):
    """Pares (operador, etiqueta) de los lados con límite."""
    out = []
    if lo is not None:
        out.append((lambda x, lo=lo: x < lo, f"< {lo}"))
    if hi is not None:
        out.append((lambda x, hi=hi: x > hi, f"> {hi}"))
    return out


def _out_of_limits_raw(previa: ds.Dataset) -> pd.DataFrame:
    """Valores fuera de límites en los CSV crudos leídos con el parser vigente (enmienda
    P2-T2a); `calidad` es la bandera que la fila tiene en la serie previa."""
    rows = []
    for f in sorted((RAW / "sih_series" / "climatologicas").glob("*.csv")):
        df = conagua.read_series_csv(f)
        for col, (lo, hi) in PHYSICAL_LIMITS.items():
            if col not in df:
                continue
            for test, lim in _limit_tests(lo, hi):
                rows += [{"clave_estacion": r.clave_estacion, "fecha": r.fecha.date().isoformat(),
                          "variable": col, "valor": float(getattr(r, col)), "limite_violado": lim}
                         for r in df[test(df[col])].itertuples()]
    fr = pd.DataFrame(rows)
    prev = previa.to_table(columns=KEY + ["calidad"],
                           filter=ds.field("clave_estacion").isin(sorted(fr["clave_estacion"].unique()))
                           ).to_pandas()
    prev["fecha"] = prev["fecha"].dt.date.astype(str)
    fr = fr.merge(prev, on=KEY, how="left")
    return fr.sort_values(["clave_estacion", "fecha", "variable"])


def _composition(d: ds.Dataset, cols: list[str]) -> dict:
    """n y % por bandera: sobre todas las filas y, por variable, sobre los días con valor."""
    tot = {"filas": {}}
    per = {c: {} for c in cols}
    for frag_year in sorted(pc.unique(d.to_table(columns=["anio"]).column("anio")).to_pylist()):
        t = d.to_table(columns=cols + ["calidad"], filter=ds.field("anio") == frag_year).to_pandas()
        for k, n in t["calidad"].value_counts().items():
            tot["filas"][int(k)] = tot["filas"].get(int(k), 0) + int(n)
        for c in cols:
            for k, n in t.loc[t[c].notna(), "calidad"].value_counts().items():
                per[c][int(k)] = per[c].get(int(k), 0) + int(n)

    def pct(counts):
        s = sum(counts.values())
        return {str(k): {"n": v, "pct": round(100 * v / s, 6)} for k, v in sorted(counts.items())}
    return {"todas_las_filas": pct(tot["filas"]),
            "por_variable_dias_con_valor": {c: pct(per[c]) for c in cols}}


def _compare(nueva: ds.Dataset, vieja: ds.Dataset, fill_ok: tuple[str, ...] = ()) -> tuple[dict, list]:
    """Compara dos series canónicas fila por fila (por año). Las columnas de `fill_ok` solo
    pueden pasar de NaN a valor; cualquier otro cambio de valor se cuenta."""
    cols = _value_cols(nueva)
    anios = sorted(set(pc.unique(nueva.to_table(columns=["anio"]).column("anio")).to_pylist())
                   | set(pc.unique(vieja.to_table(columns=["anio"]).column("anio")).to_pylist()))
    st = {"filas_nueva": 0, "filas_previa": 0, "llaves_distintas": 0,
          "columnas_distintas": sorted(set(cols) ^ set(_value_cols(vieja))),
          "valores_cambiados": dict.fromkeys(cols, 0), "celdas_nan_a_valor": dict.fromkeys(fill_ok, 0)}
    bandera = []
    for a in anios:
        cn = KEY + cols + ["calidad"]
        n = nueva.to_table(columns=cn, filter=ds.field("anio") == a).to_pandas()
        v = vieja.to_table(columns=cn, filter=ds.field("anio") == a).to_pandas()
        st["filas_nueva"] += len(n)
        st["filas_previa"] += len(v)
        m = n.merge(v, on=KEY, how="outer", suffixes=("", "_prev"), indicator=True)
        st["llaves_distintas"] += int((m["_merge"] != "both").sum())
        m = m[m["_merge"] == "both"]
        for c in cols:
            a1, a0 = m[c].to_numpy(dtype=float), m[c + "_prev"].to_numpy(dtype=float)
            changed = ~((a1 == a0) | (np.isnan(a1) & np.isnan(a0)))
            if c in fill_ok:
                filled = np.isnan(a0) & ~np.isnan(a1)
                st["celdas_nan_a_valor"][c] += int(filled.sum())
                changed &= ~filled
            st["valores_cambiados"][c] += int(changed.sum())
        d = m[m["calidad"] != m["calidad_prev"]]
        bandera += [(r.clave_estacion, r.fecha.date().isoformat(), int(r.calidad_prev), int(r.calidad))
                    for r in d.itertuples()]
    st["filas_que_cambian_de_bandera"] = len(bandera)
    return st, bandera


def _identical(st: dict) -> bool:
    return (st["llaves_distintas"] == 0 and st["filas_nueva"] == st["filas_previa"]
            and not st["columnas_distintas"] and not any(st["valores_cambiados"].values()))


@click.command()
@click.option("--antes", "modo", flag_value="antes")
@click.option("--despues", "modo", flag_value="despues")
@click.option("--previa", type=click.Path(path_type=Path), default=None,
              help="Serie climatológica archivada antes de reconstruir (para --despues).")
@click.option("--previa-hidro", type=click.Path(path_type=Path), default=None,
              help="Serie hidrométrica archivada antes de reconstruir (debe quedar idéntica).")
def main(modo: str | None, previa: Path | None, previa_hidro: Path | None) -> None:
    if modo is None:
        raise SystemExit("Indica --antes o --despues.")
    OUT.mkdir(parents=True, exist_ok=True)
    nueva = _dataset(SERIE)

    if modo == "antes":
        fr = _out_of_limits_raw(nueva)
        fr.to_csv(CSV, index=False)
        log.info("%d valores fuera de límites en %d filas -> %s", len(fr),
                 fr[["clave_estacion", "fecha"]].drop_duplicates().shape[0], CSV)
        return

    if previa is None:
        raise SystemExit("--despues necesita --previa.")
    fr = pd.read_csv(CSV, dtype={"clave_estacion": str})
    esperadas = set(zip(fr["clave_estacion"], fr["fecha"], strict=True))
    st, bandera = _compare(nueva, _dataset(previa), fill_ok=("tmax_c", "tmin_c"))

    cambiadas = {(k, f) for k, f, _, _ in bandera}
    # Bandera final de cada fila del CSV: la nueva si cambió; si no, la previa (columna calidad).
    previa_csv = {(r.clave_estacion, r.fecha): int(r.calidad) for r in fr.itertuples()}
    final = dict(previa_csv)
    final.update({(k, f): c for k, f, _, c in bandera if (k, f) in esperadas})
    rep = {t: json.loads((PROCESSED / "reportes" / f"validacion_{t}.json").read_text(encoding="utf-8"))
           for t in ("climatologicas", "hidrometricas")}
    res = {
        "fecha": date.today().isoformat(),
        "fuente": "scripts/dib_12_clima_physical_limits.py --despues; "
                  "results/dib_revision/clima_fuera_de_rango.csv; "
                  "data/processed/series_climatologicas.parquet",
        "limites": {c: list(v) for c, v in PHYSICAL_LIMITS.items()},
        "valores_fuera_de_limites": int(len(fr)),
        "valores_fuera_de_limites_por_variable": fr["variable"].value_counts().to_dict(),
        "filas_fuera_de_limites": len(esperadas),
        "clima": st,
        "cambios_de_bandera_fuera_del_csv": sorted(cambiadas - esperadas),
        "filas_csv_sin_calidad_2": sorted(k for k, c in final.items() if c != 2),
        "filas_csv_que_ya_tenian_calidad_2": sum(c == 2 for c in previa_csv.values()),
        "validacion_esquema_valido": {t: bool(r["valido"]) for t, r in rep.items()},
        "composicion_calidad": _composition(nueva, _value_cols(nueva)),
    }
    ok = (_identical(st) and not res["cambios_de_bandera_fuera_del_csv"]
          and not res["filas_csv_sin_calidad_2"] and all(res["validacion_esquema_valido"].values()))
    if previa_hidro is not None:
        sh, bh = _compare(_dataset(PROCESSED / "series_hidrometricas.parquet"), _dataset(previa_hidro))
        res["hidro"] = sh
        ok = ok and _identical(sh) and not bh
    res["criterio_cumplido"] = ok
    (OUT / "e12_clima_limites.json").write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    log.info("criterio_cumplido=%s | clima: %s", ok, st)


if __name__ == "__main__":
    main()

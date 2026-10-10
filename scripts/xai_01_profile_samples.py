#!/usr/bin/env python
"""Benchmark XAI · paso 1: perfil de muestras válidas (protocolo congelado, secciones 2–3).

Cuenta, por estación, horizonte y partición, las muestras válidas y marca qué estaciones
son evaluables en prueba (≥ 180 muestras y varianza > 0 del gasto observado). No entrena
nada.

Salidas: results/xai_benchmark/sample_profile.csv y sample_profile.json
Uso:  python scripts/xai_01_profile_samples.py
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from hidroxai_mx.models import data as D
from hidroxai_mx.utils import FEATURES, PROCESSED, ROOT, get_logger

log = get_logger("xai_01")
OUT = ROOT / "results" / "xai_benchmark"
MIN_TEST = 180


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    link = pd.read_csv(PROCESSED / "estaciones_hidrorivers.csv", dtype={"clave": str})
    basin = D.station_basins(link)
    ft = pd.read_parquet(FEATURES / "feature_table.parquet",
                         columns=["clave_estacion", "fecha", "calidad", *D.CHANNELS[:4]])
    rows = []
    for clave in link["clave"]:
        p = D.daily_panel(ft, clave)
        for h in D.HORIZONS:
            valid = D.valid_issue_mask(p, h)
            for name, part in D.PARTITIONS.items():
                m = valid & D.partition_mask(p.index, h, part)
                y = p[D.TARGET].to_numpy()[np.nonzero(m)[0] + h]
                rows.append({"clave": clave, "cuenca": basin.get(clave), "h": h, "particion": name,
                             "n": int(m.sum()), "var_objetivo": float(np.var(y)) if y.size else 0.0})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "sample_profile.csv", index=False)

    test = t[t["particion"] == "test"].copy()
    test["evaluable"] = (test["n"] >= MIN_TEST) & (test["var_objetivo"] > 0)
    summary = {"fecha": date.today().isoformat(),
               "fuente": "scripts/xai_01_profile_samples.py; results/xai_benchmark/sample_profile.csv; "
                         "data/features/feature_table.parquet (v2026.10)",
               "estaciones": int(link["clave"].nunique()),
               "fuera_de_unidad": sorted(link.loc[basin.isna().to_numpy(), "clave"]),
               "min_muestras_prueba": MIN_TEST, "por_cuenca": {}}
    for b in D.BASINS:
        sb = t[t["cuenca"] == b]
        d = {"estaciones": int(sb["clave"].nunique())}
        for h in D.HORIZONS:
            sh = sb[sb["h"] == h]
            ev = test[(test["cuenca"] == b) & (test["h"] == h)]
            d[f"h{h}"] = {"muestras": {k: int(sh.loc[sh["particion"] == k, "n"].sum()) for k in D.PARTITIONS},
                          "evaluables_prueba": int(ev["evaluable"].sum()),
                          "no_evaluables": ev.loc[~ev["evaluable"], ["clave", "n"]].to_dict("records")}
        summary["por_cuenca"][b] = d
    summary["evaluables_agregado"] = {f"h{h}": int(test[(test["h"] == h) & test["cuenca"].notna()]["evaluable"].sum())
                                      for h in D.HORIZONS}
    (OUT / "sample_profile.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("perfil listo: %s", summary["evaluables_agregado"])


if __name__ == "__main__":
    main()

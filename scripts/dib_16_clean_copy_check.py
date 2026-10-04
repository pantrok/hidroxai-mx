#!/usr/bin/env python
"""Paso 2, T4 — prueba desde copia limpia del archivo de Zenodo (revisor 3).

1. Descomprime el ZIP en un directorio nuevo.
2. Crea un entorno virtual nuevo e instala el paquete: pip install -e ".[dev,geo]".
3. Descarga las capas externas de Fig. 2 desde las URL de conf/sources.yaml (sección 10).
4. Guarda las salidas empaquetadas y las regenera dentro de la copia: pytest, etapa 09
   (metrics.json, Fig2–Fig7), etapa 12 (Fig1), dib_01 (conteos, Tabla 1), dib_13 (Tablas 2–3),
   dib_14 (contornos de cuencas piloto).
5. Compara lo regenerado contra lo empaquetado: JSON y CSV por valor, figuras por píxel.
Salida: results/dib_revision/clean_copy_check.{json,md} en el repositorio.

Uso:  python scripts/dib_16_clean_copy_check.py --zip dist/HidroXAI-MX-v2026.10.zip --work <dir nuevo>
      (solo biblioteca estándar; las comparaciones corren con el Python del entorno nuevo)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "dib_revision"

# Salidas que se regeneran y comparan (ruta dentro del archivo).
REGEN = [
    "processed/reportes/metrics.json",
    "processed/reportes/cobertura_por_estacion.csv",
    "processed/reportes/precip_streamflow_lagcorr.csv",
    *[f"processed/reportes/{f}.png" for f in (
        "Fig1_workflow", "Fig2_station_map", "Fig3_quality_flags", "Fig4_inventory_coverage",
        "Fig5_streamflow_by_region", "Fig6_climatology_annual", "Fig7_precip_streamflow")],
    "results/dib_revision/counts_reconciliation_v2026_10.csv",
    "results/dib_revision/observation_counts_v2026_10.csv",
    "results/dib_revision/calidad_composition_v2026_10.csv",
    "results/dib_revision/tabla3_v2026_10.csv",
    "results/dib_revision/hidrorivers_sin_vinculo.csv",
    "results/dib_revision/e13_paso2_t1.json",
    "results/dib_revision/pilot_basin_outlines.csv",
]
# Claves que dependen de la fecha de ejecución o de archivos que no viajan en el ZIP.
IGNORE_KEYS = {"fecha", "fecha_conciliacion", "generado", "duplicados_v2026_06"}
CAPAS = {"natural_earth_admin1": "ne_10m_admin_1", "regiones_hidrologicas": "rh250kgw",
         "cuencas_hidrologicas": "cue250kgw"}
PAQUETES = ["matplotlib", "geopandas", "shapely", "pyproj", "pyogrio", "numpy", "pandas",
            "pyarrow", "pandera", "pillow"]
VERSIONS = ("import importlib.metadata as m, json; "
            f"print(json.dumps({{p: m.version(p) for p in {PAQUETES!r}}}))")


def run(cmd: list[str], cwd: Path, log: list) -> float:
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t0
    log.append({"comando": " ".join(cmd), "segundos": round(dt, 1), "codigo": r.returncode,
                "salida_final": (r.stdout + r.stderr)[-1500:]})
    if r.returncode != 0:
        raise SystemExit(f"Falló: {' '.join(cmd)}\n{(r.stdout + r.stderr)[-3000:]}")
    return dt


def compare(base: Path, ref: Path) -> list[dict]:
    """Corre en el Python del entorno nuevo: compara regenerado (base) vs empaquetado (ref)."""
    import numpy as np
    import pandas as pd
    from PIL import Image

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in IGNORE_KEYS}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o

    res = []
    for rel in REGEN:
        a, b = base / rel, ref / rel
        r = {"archivo": rel}
        if not a.exists() or not b.exists():
            r.update(resultado="falta", detalle=f"regenerado={a.exists()} empaquetado={b.exists()}")
        elif rel.endswith(".json"):
            same = strip(json.loads(a.read_text(encoding="utf-8"))) == strip(json.loads(b.read_text(encoding="utf-8")))
            r.update(resultado="igual" if same else "difiere", detalle="valores (sin fechas de ejecución)")
        elif rel.endswith(".csv"):
            da, db = pd.read_csv(a), pd.read_csv(b)
            da = da.drop(columns=[c for c in da.columns if c in IGNORE_KEYS])
            db = db.drop(columns=[c for c in db.columns if c in IGNORE_KEYS])
            try:
                pd.testing.assert_frame_equal(da, db, check_exact=False, rtol=1e-12)
                r.update(resultado="igual", detalle=f"{len(da)} filas")
            except AssertionError as e:
                r.update(resultado="difiere", detalle=str(e)[:300])
        else:
            same_bytes = hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()
            ia, ib = (np.asarray(Image.open(p).convert("RGB")) for p in (a, b))
            if ia.shape != ib.shape:
                r.update(resultado="difiere", detalle=f"tamaño {ia.shape} vs {ib.shape}")
            else:
                mask = (ia != ib).any(axis=2)
                n = int(mask.sum())
                if n == 0:
                    r.update(resultado="igual", detalle="bytes idénticos" if same_bytes else
                             "píxeles idénticos; bytes distintos (metadatos del PNG)")
                else:
                    ys, xs = np.nonzero(mask)
                    r.update(resultado="difiere",
                             detalle=f"{n} píxeles distintos ({100 * n / mask.size:.2f} %), dentro de "
                                     f"x {xs.min()}–{xs.max()}, y {ys.min()}–{ys.max()} de "
                                     f"{ia.shape[1]}×{ia.shape[0]} px")
        res.append(r)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True, help="Directorio nuevo (no debe existir).")
    ap.add_argument("--python", default=sys.executable, help="Intérprete base para el entorno nuevo.")
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("REGENERADO", "EMPAQUETADO"),
                    help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.compare:
        print(json.dumps(compare(*a.compare), ensure_ascii=False))
        return

    if a.work.exists():
        raise SystemExit(f"{a.work} ya existe; usa un directorio nuevo.")
    t_start, log = time.time(), []
    root, ref = a.work / "hidromx", a.work / "empaquetado"
    zip_sha = hashlib.sha256(a.zip.read_bytes()).hexdigest()
    with zipfile.ZipFile(a.zip) as zf:
        zf.extractall(root)
    for rel in REGEN:                                   # copia de lo empaquetado, antes de regenerar
        if (root / rel).exists():
            (ref / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, ref / rel)

    venv = a.work / "venv"
    run([a.python, "-m", "venv", str(venv)], a.work, log)
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], root, log)
    t_pip = run([str(py), "-m", "pip", "install", "-q", "-e", ".[dev,geo]"], root, log)
    py_version = subprocess.run([str(py), "-c", "import sys; print(sys.version.split()[0])"],
                                capture_output=True, text=True).stdout.strip()

    import yaml  # disponible en el Python que corre este script (repositorio)
    src = yaml.safe_load((root / "conf" / "sources.yaml").read_text(encoding="utf-8"))["fuentes"]
    lim = root / "scratch" / "limites"
    for key, folder in CAPAS.items():
        url = src[key]["url"]
        z = a.work / f"{folder}.zip"
        urllib.request.urlretrieve(url, z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(lim / folder)
        log.append({"comando": f"descarga {url}", "bytes": z.stat().st_size})

    for cmd in (["-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts="],
                ["scripts/09_make_report_figures.py"], ["scripts/12_make_workflow_figure.py"],
                ["scripts/dib_01_reconcile_counts.py", "--suffix", "_v2026_10"],
                ["scripts/dib_13_paso2_tables.py"], ["scripts/dib_14_pilot_basin_outlines.py"]):
        run([str(py), "-W", "ignore", *cmd], root, log)

    r = subprocess.run([str(py), str(Path(__file__)), "--zip", str(a.zip), "--work", str(a.work),
                        "--compare", str(root), str(ref)], capture_output=True, text=True, encoding="utf-8")
    cmp_ = json.loads(r.stdout)
    ok = all(c["resultado"] == "igual" for c in cmp_)
    datos = [c for c in cmp_ if not c["archivo"].endswith(".png")]
    figs = [c for c in cmp_ if c["archivo"].endswith(".png")]
    vers = {"entorno_nuevo": json.loads(subprocess.run([str(py), "-c", VERSIONS], capture_output=True,
                                                       text=True).stdout),
            "repositorio (salidas empaquetadas)": json.loads(subprocess.run(
                [sys.executable, "-c", VERSIONS], capture_output=True, text=True).stdout)}
    res = {"ok": ok,
           "valores_identicos": all(c["resultado"] == "igual" for c in datos),
           "figuras_identicas": f"{sum(c['resultado'] == 'igual' for c in figs)}/{len(figs)}",
           "fecha": time.strftime("%Y-%m-%d"), "zip": a.zip.name, "zip_sha256": zip_sha,
           "python_base": platform.python_version(), "python_entorno": py_version,
           "sistema": platform.platform(), "minutos_total": round((time.time() - t_start) / 60, 1),
           "minutos_pip_install": round(t_pip / 60, 1), "versiones": vers,
           "comparaciones": cmp_, "comandos": log}
    (OUT / "clean_copy_check.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [f"# Prueba desde copia limpia — {a.zip.name}", "",
          f"- Fecha: {res['fecha']}; ZIP SHA-256 `{zip_sha}`.",
          f"- Python del entorno nuevo: {py_version}; sistema: {res['sistema']}.",
          f"- Tiempo total: {res['minutos_total']} min (pip install: {res['minutos_pip_install']} min).",
          f"- Resultado: **{'todo coincide' if ok else 'hay diferencias'}**; valores (JSON y CSV) "
          f"{'idénticos' if res['valores_identicos'] else 'con diferencias'}; figuras idénticas "
          f"por píxel: {res['figuras_identicas']}.", "",
          "## Versiones de bibliotecas", "",
          "| Paquete | " + " | ".join(vers) + " |", "|---|" + "---|" * len(vers)]
    md += [f"| {p} | " + " | ".join(v.get(p, "—") for v in vers.values()) + " |" for p in PAQUETES]
    md += ["", "## Comandos", "", "```"]
    md += [f"{c['comando']}  # {c.get('segundos', '')} s" for c in log]
    md += ["```", "", "## Comparación (regenerado vs empaquetado)", "",
           "| Archivo | Resultado | Detalle |", "|---|---|---|"]
    md += [f"| `{c['archivo']}` | {c['resultado']} | {c['detalle']} |" for c in cmp_]
    md += ["", "Se ignoran las claves con la fecha de ejecución y el bloque `duplicados_v2026_06`, "
               "que se calcula sobre parquets del release v2026.06 que no viajan en el archivo. "
               "Una figura con diferencias de píxeles y valores idénticos refleja el dibujo de "
               "versiones distintas de las bibliotecas (tabla de versiones), no un cambio del dato."]
    (OUT / "clean_copy_check.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "minutos": res["minutos_total"]}))


if __name__ == "__main__":
    main()

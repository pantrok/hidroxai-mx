#!/usr/bin/env python
"""Benchmark XAI · MESE: reporte para el autor (results/xai_benchmark/mese/MESE_report.md, local).

Cada cifra sale de un archivo de resultados y se cita con su archivo y campo. Lee:
e_mese_lstm.json, lstm_*.csv, e_mese_imputados.json, imputados_test.csv, rq1_summary.csv,
figures_mese/figures_mese.{csv,json}, los PDF de las figuras (metadatos de autor), git (términos
que identifican al autor, para T5) y mese/hallazgos_colaterales.md (solo títulos).

Uso:  python scripts/xai_19_mese_report.py [--url-anonima URL]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time

import pandas as pd

from hidroxai_mx.utils import ROOT

OUT = ROOT / "results" / "xai_benchmark"
MESE = OUT / "mese"
FIGM = OUT / "figures_mese"
ORDER = ["persistencia", "climatologia", "arima", "xgboost", "tcn", "convnext", "patchtst", "lstm"]
LABEL = {"persistencia": "Persistencia", "climatologia": "Climatología", "arima": "ARIMA", "xgboost": "XGBoost",
         "tcn": "TCN", "convnext": "ConvNeXt-1D", "patchtst": "PatchTST", "lstm": "LSTM (descriptivo)"}
TERMS = ["pantrok", "Daniel", "Sánchez Ruiz", "Sánchez-Ruiz", "UPIIT", "Instituto Politécnico Nacional",
         "IND-2026-0335"]


def f(x, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return f"{x:,}".replace(",", " ")
    return f"{x:.{nd}f}"


def ci(v, nd: int = 3) -> str:
    return f"{f(v[0], nd)} [{f(v[1], nd)}, {f(v[2], nd)}]"


def git_files(term: str) -> list[str]:
    r = subprocess.run(["git", "grep", "-l", "-i", "-F", term, "HEAD", "--", "."], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return sorted({ln.split(":", 1)[1] for ln in r.stdout.splitlines() if ":" in ln})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-anonima", default="")
    a = ap.parse_args()
    js = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    el, ei = js(MESE / "e_mese_lstm.json"), js(MESE / "e_mese_imputados.json")
    v, exp = el["verificacion"], el["explicaciones"]
    sm = pd.read_csv(OUT / "rq1_summary.csv")
    ls = pd.read_csv(MESE / "lstm_skill.csv")
    dx = pd.read_csv(MESE / "lstm_vs_xgboost.csv")
    lw = pd.read_csv(MESE / "lstm_walkforward.csv")
    figs = pd.read_csv(FIGM / "figures_mese.csv")
    fj = js(FIGM / "figures_mese.json")
    L = ["# MESE_report · ajuste del benchmark XAI para *Modeling Earth Systems and Environment*", "",
         f"Generado por `scripts/xai_19_mese_report.py` el {time.strftime('%Y-%m-%d')}. Criterios en "
         "`results/xai_benchmark/proof_ledger.md`, sección \"Enmienda MESE\" (versionada antes de entrenar y de "
         "calcular). Rutas relativas a `results/xai_benchmark/`. Todo lo nuevo es descriptivo: no cambia el "
         "protocolo, sus resultados ni ningún veredicto de §7.", ""]

    # ---------------------------------------------------------------- T1
    core = v.get("computo_slurm", {})
    L += ["## T1 · LSTM descriptivo (LNS-BUAP)", "",
          "### Entorno y cómputo", "",
          "| Cifra | Valor | Archivo: campo |", "|---|---|---|"]
    for i, ln in enumerate(v.get("entorno_lns", [])):
        L.append(f"| Entorno LNS ({i + 1}) | {ln.replace(' | ', ' · ')} | `mese/e_mese_lstm.json:verificacion.entorno_lns` |")
    L += [f"| Ruta del entorno | {'a' if any('ruta a' in x for x in v.get('entorno_lns', [])) else '—'} "
          "(glibc ≥ 2.28: conda del clúster + pip con las versiones del estudio) | ídem |",
          f"| Horas-core asignadas (sacct, CPUTimeRAW; incluye piloto y dos envíos fallidos de 1 s) | "
          f"{f(core.get('horas_core_asignadas'), 2)} | `mese/e_mese_lstm.json:verificacion.computo_slurm.horas_core_asignadas` |",
          f"| Uso real de CPU (sacct, TotalCPU) | {f(core.get('horas_cpu_usadas'), 2)} (el LNS no lo registra) | "
          "`…computo_slurm.horas_cpu_usadas` |",
          f"| Tiempo de entrenamiento sumado (manifiestos) | {f((v.get('entrenamiento_segundos') or 0) / 3600, 2)} h | "
          "`mese/lstm_manifest.csv:segundos` |"]
    for t in core.get("trabajos", []):
        L.append(f"| Trabajo {t['JobID']} ({t['JobName']}) | {t['AllocCPUS']} cores, {t['Elapsed']}, {t['State']} | "
                 "`…computo_slurm.trabajos` |")
    L += ["", "### Verificación de lo bajado del LNS", "", "| Cifra | Valor | Archivo: campo |", "|---|---|---|",
          f"| Partición principal: predicciones / pesos | {v['corridas_principal']['predicciones']} / "
          f"{v['corridas_principal']['pesos']} de {v['corridas_principal']['esperadas']} | `mese/lstm_import.json:corridas_principal` |",
          f"| Walk-forward: predicciones / pesos | {v['corridas_walk_forward']['predicciones']} / "
          f"{v['corridas_walk_forward']['pesos']} de {v['corridas_walk_forward']['esperadas']} | `…corridas_walk_forward` |",
          f"| Muestras distintas de las de CPU; corridas con NaN | {len(v['muestras_distintas'])}; {len(v['corridas_con_nan'])} | "
          "`…muestras_distintas`, `…corridas_con_nan` |",
          f"| Tamaño elegido (validación, regla de §4) | {', '.join(f'{k}: {x}' for k, x in v['seleccion'].items())} | "
          "`mese/lstm_selection.csv` |",
          f"| La selección coincide con la que usó el walk-forward | {'sí' if v['seleccion_coincide_con_walk_forward'] else 'no'} | "
          "`…seleccion_coincide_con_walk_forward` |", ""]
    L += ["### Habilidad en la partición principal (agregado, 91 estaciones)", "",
          "Mediana de NSE y de SS contra persistencia; el LSTM sale de `mese/lstm_skill.csv` y los demás de "
          "`rq1_summary.csv` (columnas `nse_mediana`, `ss_mediana`, `ss_ic_lo`, `ss_ic_hi`).", "",
          "| Modelo | NSE, 1 d | NSE, 7 d | NSE, 14 d | SS, 1 d | SS, 7 d | SS, 14 d |", "|---|---|---|---|---|---|---|"]
    allm = pd.concat([sm, ls], ignore_index=True)
    agg = allm[allm["grupo"] == "agregado"].set_index(["modelo", "h"])
    for m in ORDER:
        nse = [f(agg.loc[(m, h), "nse_mediana"]) for h in (1, 7, 14)]
        ss = [("—" if m == "persistencia" else ci([agg.loc[(m, h), c] for c in ("ss_mediana", "ss_ic_lo", "ss_ic_hi")]))
              for h in (1, 7, 14)]
        L.append(f"| {LABEL[m]} | " + " | ".join(nse + ss) + " |")
    L += ["", "### ΔNSE (LSTM − XGBoost), mediana e IC 95 %", "", "Fuente: `mese/lstm_vs_xgboost.csv`.", "",
          "| Horizonte | Bootstrap de estaciones | Bootstrap de grupos conectados |", "|---|---|---|"]
    for h in (1, 7, 14):
        r = dx[dx["h"] == h].set_index("remuestreo")
        L.append(f"| {h} d | {ci(r.loc['estaciones', ['mediana', 'ic_lo', 'ic_hi']].tolist(), 4)} "
                 f"({int(r.loc['estaciones', 'unidades'])} estaciones) | "
                 f"{ci(r.loc['grupos_conectados', ['mediana', 'ic_lo', 'ic_hi']].tolist(), 4)} "
                 f"({int(r.loc['grupos_conectados', 'unidades'])} grupos) |")
    L += ["", "### Explicaciones y acuerdo (cuencas con ≥ 8 estaciones)", "",
          "| Cifra | Valor | Archivo: campo |", "|---|---|---|",
          f"| Error de completitud de IG, máximo de las medianas de abs(δ) por cuenca, horizonte y semilla | "
          f"{exp['ig_error_completitud']['delta_abs_mediana_max']:.1e} | `mese/lstm_ig_delta.csv:delta_abs_mediana` |",
          f"| Ídem, máximo del P95 de abs(δ) | {exp['ig_error_completitud']['delta_abs_p95_max']:.1e} | "
          "`mese/lstm_ig_delta.csv:delta_abs_p95` |"]
    for m, val in exp["spearman_180_lstm_vs"].items():
        L.append(f"| Spearman (180) LSTM vs {LABEL[m]}, mediana de las 9 combinaciones | {f(val)} | "
                 "`mese/lstm_concordance.csv` (medida spearman_180, tipo entre_modelos) |")
    L += [f"| Spearman (180) del LSTM entre semillas, mediana | {f(exp['spearman_180_lstm_entre_semillas_mediana'])} | "
          "ídem, tipo entre_semillas |",
          f"| Spearman (180) del LSTM entre mitades, mediana | {f(exp['spearman_180_lstm_entre_mitades_mediana'])} | "
          "ídem, tipo entre_mitades |"]
    for meas, txt in exp["pares_con_lstm_bajo_techo"].items():
        L.append(f"| Pares con el LSTM bajo el techo de semillas ({meas}) | {txt} | "
                 "`mese/lstm_concordance.csv:bajo_techo_semillas` |")
    L += ["", "Pares adicionales: la mediana de 6 pares de H2-a no cambia.", "",
          "### Walk-forward 2021–2025 (agregado, una semilla)", "", "Fuente: `mese/lstm_walkforward.csv` "
          "(`nse_mediana`, `delta_nse_xgb_*`).", "",
          "| Año | NSE, 1 d | NSE, 7 d | NSE, 14 d | ΔNSE vs XGBoost, 1 d | ΔNSE, 7 d | ΔNSE, 14 d |",
          "|---|---|---|---|---|---|---|"]
    wfa = lw[lw["grupo"] == "agregado"].set_index(["año", "h"])
    for y in sorted(wfa.index.get_level_values(0).unique()):
        nse = [f(wfa.loc[(y, h), "nse_mediana"]) for h in (1, 7, 14)]
        dd = [ci([wfa.loc[(y, h), c] for c in ("delta_nse_xgb_mediana", "delta_nse_xgb_ic_lo", "delta_nse_xgb_ic_hi")], 4)
              for h in (1, 7, 14)]
        L.append(f"| {y} | " + " | ".join(nse + dd) + " |")

    # ---------------------------------------------------------------- T2
    L += ["", "## T2 · Valores imputados en la ventana (solo evaluación)", "",
          "Fuente: `mese/e_mese_imputados.json` y `mese/imputados_test.csv`. Controles: el NSE recalculado reproduce "
          f"`rq1_station_metrics.csv` (diferencia máxima {ei['control_nse_max_diferencia']:.1e}) y el ΔCSI de la prueba "
          "completa reproduce `e_rq3.json`.", ""]
    names = {"i_sin_qt_imputado": "(i) sin Q(t) imputado", "ii_sin_imputados_en_ventana": "(ii) sin imputados en 30 días"}
    for s, lab in names.items():
        sub = ei["subconjuntos"][s]
        g = sub["fraccion_excluida"]["global"]
        L += [f"### {lab}", "", f"Emisiones excluidas: {f(g['excluidas'])} de {f(g['emisiones'])} "
              f"({100 * g['fraccion']:.1f} %; `subconjuntos.{s}.fraccion_excluida.global`).", "",
              "| Horizonte | Estaciones (mismas / evaluables) | NSE mediana XGBoost: completa → subconjunto | "
              "ΔNSE TCN − XGBoost: completa → subconjunto | ΔCSI P90: completa → subconjunto |",
              "|---|---|---|---|---|"]
        for h in (1, 7, 14):
            p = sub["por_horizonte"][f"h{h}"]
            nx = p["nse_mediana"]["xgboost"]
            dt = p["delta_nse_vs_xgboost"]["tcn"]
            dc = p.get("delta_csi_p90")
            L.append(f"| {h} d | {p['estaciones_mismas']} / {p['estaciones_evaluables']} | {f(nx['principal_mismas'], 4)} → "
                     f"{f(nx['subconjunto'], 4)} | {ci(dt['principal_mismas'], 4)} → {ci(dt['subconjunto'], 4)} | "
                     + (f"{ci(dc['principal_mismas'], 4)} → {ci(dc['subconjunto'], 4)}" if dc else "—") + " |")
        L.append("")
    L += ["Todos los modelos y horizontes: `mese/imputados_test.csv` (bloques `nse_mediana`, `delta_nse_vs_xgboost`, "
          "`delta_csi_p90`, `fraccion_excluida`).", ""]

    # ---------------------------------------------------------------- T3–T4
    L += ["## T3 · Figuras para MESE", "", "Carpeta `figures_mese/` (PDF, EPS, PNG; TIFF fuera de git). Fuente: "
          "`figures_mese/figures_mese.csv`.", "", "| Archivo | Tamaño (mm) | Contenido |", "|---|---|---|"]
    for r in figs.itertuples():
        L.append(f"| `{r.archivo}.pdf` | {r.ancho_mm} × {r.alto_mm:g} | {r.contenido} |")
    lstm_in = fj["lstm_incluido"]
    L += ["", f"LSTM incluido en las figuras: {'sí' if all(lstm_in.values()) else 'parcial: ' + str(lstm_in)} "
          "(`figures_mese/figures_mese.json:lstm_incluido`).", "",
          "## T4 · Mapa propio (Fig. 2)", "", "| Cifra | Valor | Campo |", "|---|---|---|"]
    mp = fj["fig2_mapa"]
    L += [f"| Estaciones modeladas / evaluables | {mp['estaciones_modeladas']} / {mp['estaciones_evaluables']} | "
          "`figures_mese.json:fig2_mapa` |",
          f"| No evaluables (símbolo hueco) | {', '.join(mp['no_evaluables'])} | ídem |",
          f"| Grupos conectados (con más de una estación / aisladas) | {mp['grupos']} ({mp['grupos_con_varias']} / "
          f"{mp['aisladas']}) | ídem |",
          f"| Tamaño de los grupos | {', '.join(f'{k}: {n}' for k, n in mp['tamano_grupos'].items())} | ídem |",
          f"| Régimen | {', '.join(f'{k}: {n}' for k, n in mp['regimen'].items())} | ídem |", ""]

    # ---------------------------------------------------------------- T5
    pdfs = sorted(FIGM.glob("*.pdf"))
    with_author = [p.name for p in pdfs if re.search(rb"/Author\s*\(", p.read_bytes())]
    L += ["## T5 · Versión anónima", "",
          f"- **Metadatos de las figuras:** {len(pdfs)} PDF revisados; con campo de autor: "
          f"{', '.join(with_author) if with_author else 'ninguno'} (solo Creator/Producer de Matplotlib).",
          f"- **URL anónima:** {a.url_anonima or 'pendiente (la crea el autor en anonymous.4open.science con su cuenta de GitHub)'}.",
          "- **Términos que identifican al autor** en el repositorio (para reemplazar en el espejo):", ""]
    for t in TERMS:
        files = git_files(t)
        L.append(f"  - `{t}`: {len(files)} archivos" + (f" ({', '.join(files[:6])}{'…' if len(files) > 6 else ''})" if files else ""))
    L += ["", "- **Riesgo:** el nombre del paquete y del dataset (`hidroxai_mx`, HidroXAI-MX) no se puede reemplazar sin "
          "romper el código, y lleva al registro de Zenodo con autores.", ""]

    # ---------------------------------------------------------------- hallazgos
    hp = MESE / "hallazgos_colaterales.md"
    titles = [ln[3:].strip() for ln in hp.read_text(encoding="utf-8").splitlines() if ln.startswith("## ")] if hp.exists() else []
    L += ["## Hallazgos colaterales (solo títulos)", "", "Detalle en `mese/hallazgos_colaterales.md` (local).", ""]
    L += [f"- {re.sub(r'^[0-9]+[.] *', '', t)}" for t in titles] or ["- Ninguno."]
    (MESE / "MESE_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("MESE_report.md escrito")


if __name__ == "__main__":
    main()

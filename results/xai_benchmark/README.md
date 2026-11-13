# XAI benchmark: how to reproduce the tables and figures

This folder holds the model-comparison, explainability and fuzzy-alert benchmark built on the
Hidro-MX v2026.10 dataset snapshot, and every number reported in the *Modeling Earth Systems and
Environment* (MESE) manuscript.

- `protocol.md`: the pre-specified protocol (frozen on 2026-10-10, before any model was trained).
- `proof_ledger.md`: freeze record, dated amendments and execution notes, including the MESE
  amendment (descriptive LSTM, imputed-input check) written before running it.
- `numbers.json`: the single results file. Every figure quoted in the manuscript comes from it,
  and each block names its source script in `"fuente"`.
- `tables/`, `figures_mese/` and `mese/`: tables, journal figures and MESE-specific outputs.

## Setup

```bash
pip install -e ".[dev,geo,ml]"
```

The scripts read the snapshot from `data/` (repository, `dvc pull`) or from the root of the
unzipped Zenodo archive. Heavy intermediate files (predictions, weights, attributions) are
written to `data/interim/xai_benchmark/` and are not versioned.

## Where each step ran

| Step | Scripts | Hardware |
|---|---|---|
| Sample profile, references, ARIMA, XGBoost | `xai_01`, `xai_04` | local CPU |
| TCN, ConvNeXt-1D, PatchTST, main split (216 runs) | `xai_03` through `notebooks/kaggle_xai_train_nets.ipynb`; imported with `xai_03c` | cloud GPU (Kaggle, Tesla T4) |
| TCN, ConvNeXt-1D, PatchTST, annual walk-forward (180 runs) | `xai_09 --models tcn convnext patchtst` through `notebooks/kaggle_xai_walk_forward.ipynb` | cloud GPU (Kaggle, Tesla T4) |
| Walk-forward references, ARIMA and XGBoost | `xai_09 --models baselines xgboost` | local CPU |
| LSTM (descriptive), main split (72 runs) and walk-forward (60 runs) | `xai_03 --models lstm`, `xai_15`, through `hpc/lns/` | CPU cluster (LNS-BUAP, SLURM partition `normal`) |
| Evaluation, explanations (TreeSHAP, Integrated Gradients), alerts, diagnostics, review analyses, figures | `xai_05`–`xai_08`, `xai_10`–`xai_12`, `xai_14`, `xai_16`–`xai_18` | local CPU |

Run times per run are in `compute_manifest.csv` (protocol models) and `mese/lstm_manifest.csv`
(LSTM).

## Order of execution

```bash
python scripts/xai_01_profile_samples.py
python scripts/xai_04_train_cpu_models.py
# networks on GPU: notebooks/kaggle_xai_train_nets.ipynb, then
python scripts/xai_03c_import_kaggle.py --zip <xai_runs.zip>
python scripts/xai_05_evaluate.py         # RQ1: skill, configuration selection, H1, H1-b
python scripts/xai_06_explain.py          # RQ2: importance maps, agreement, H2-a, H2-b
python scripts/xai_07_alerts.py           # RQ3: fuzzy alerts, H3
python scripts/xai_08_report.py           # rewrites numbers.json, tables/T1–T8
python scripts/xai_09_walk_forward.py --models baselines xgboost
# networks of the walk-forward on GPU: notebooks/kaggle_xai_walk_forward.ipynb
python scripts/xai_10_walk_forward_eval.py
python scripts/xai_11_diagnostics.py
python scripts/xai_12_figures_esi.py      # adds datos.por_cuenca, tables/T9
python scripts/xai_14_review_analyses.py  # RR-1 to RR-6, tables/T10–T13, S1
# LSTM on the cluster: hpc/lns/LEEME_LNS.md, then
python scripts/xai_18_mese_lstm.py --runs <runs folder from the cluster>
python scripts/xai_16_mese_imputados.py
python scripts/xai_17_figures_mese.py     # figures_mese/
python scripts/xai_17_figures_mese.py --review   # Fig1_review (anonymous review)
```

`xai_08` rewrites `numbers.json`, so the scripts that add sections to it (`xai_12`, `xai_14`,
`xai_16`, `xai_18`) run after it.

## Figures of the MESE manuscript

All of them come from `python scripts/xai_17_figures_mese.py`. They are written to
`figures_mese/` as PDF, EPS, PNG and TIFF (TIFF files are not versioned), and listed in
`figures_mese/figures_mese.csv`.

| Figure | Content | Main inputs |
|---|---|---|
| Fig. 1 (`Fig1`, `Fig1_review` with `--review`) | Study workflow | — |
| Fig. 2 | Modeled gauges by connected river group and flow regime | `rev_rr3_grupos.csv`, `tables/S1_descriptores.csv` |
| Fig. 3 | NSE and skill score vs persistence | `rq1_summary.csv`, `mese/lstm_skill.csv` |
| Fig. 4 | Importance maps | `rq2_importance.csv`, `mese/lstm_importance.csv` |
| Fig. 5 | Agreement between explanations and seed noise ceiling | `rq2_concordance.csv`, `rev_rr2_medidas.csv`, `mese/lstm_concordance.csv` |
| Fig. 6 | Alert CSI and decomposition of ΔCSI | `rq3_summary.csv`, `e_rq3.json`, `rev_rr1_contrastes.csv` |
| ESM Fig. S1 | Mamdani decision surface | — |
| ESM Fig. S2 | ΔNSE vs XGBoost | `e_rq1.json`, `mese/lstm_vs_xgboost.csv` |
| ESM Fig. S3 | Precipitation lag profiles | `rq2_importance.csv` |
| ESM Fig. S4 | Annual walk-forward | `wf_summary.csv`, `e_walkforward.json`, `mese/lstm_walkforward.csv` |
| ESM Fig. S5 | 2023 drought | `diag_sequia_2023.csv` |
| ESM Fig. S6 | Median NSE by basin | `rq1_summary.csv`, `mese/lstm_skill.csv` |
| ESM Fig. S7 | Example alert time series | `data/interim/xai_benchmark/alerts/` |
| ESM Fig. S8 | Alert ablations and relative economic value | `rev_rr1_contrastes.csv`, `rev_rr11_valor_relativo.csv` |
| ESM Fig. S9 | Noise ceiling, five agreement measures | `rev_rr2_medidas.csv` |
| ESM Fig. S10 | NSE by flow regime | `tables/S1_descriptores.csv` |

## Tables and numbers

| Content | Command | Output |
|---|---|---|
| Skill by model and lead time; by basin; KGE components | `xai_05`, then `xai_08` | `tables/T1_rq1_agregado.csv`, `T1b_rq1_kge_componentes.csv`, `T2_rq1_por_cuenca.csv` |
| Agreement and precipitation lags | `xai_06`, then `xai_08` | `tables/T3_rq2_concordancia_rezagos.csv` |
| Alerts | `xai_07`, then `xai_08` | `tables/T4_rq3_alertas.csv` |
| Hypotheses (H1–H3) | `xai_08` | `tables/T5_hipotesis.csv`; `numbers.json` → `veredictos` |
| Compute | `xai_08` | `tables/T6_computo.csv` |
| Walk-forward | `xai_10`, then `xai_08` | `tables/T7_walk_forward.csv`, `T7b_walk_forward_metricas.csv` |
| 2023 drought, back-transformation bias | `xai_11`, then `xai_08` | `tables/T8_sequia_2023.csv`, `T1c_kge_log1p.csv` |
| Pilot basins | `xai_12` | `tables/T9_cuencas_piloto.csv` |
| Noise ceiling, sensitivity of verdicts, alert ablations, gauge descriptors | `xai_14` | `tables/T10_techo_ruido.csv`, `T11_veredictos_sensibilidad.csv`, `T13_ablaciones_alertas.csv`, `T13b_contrastes_alertas.csv`, `S1_descriptores.csv` |
| LSTM: skill, ΔNSE vs XGBoost, agreement and noise ceiling, walk-forward | `xai_18` | `mese/lstm_skill.csv`, `lstm_vs_xgboost.csv`, `lstm_concordance.csv`, `lstm_walkforward.csv`; `numbers.json` → `mese_lstm` |
| Imputed inputs in the window (evaluation only) | `xai_16` | `mese/imputados_test.csv`; `numbers.json` → `mese_imputados` |

The LSTM is descriptive: it is not part of H1–H3, of the 12-member alert ensemble or of the
six-pair H2-a median (MESE amendment in `proof_ledger.md`).

## Software environments

- **Local CPU:** `environment_local.txt` (`pip freeze`, Python 3.12.6).
- **CPU cluster (LSTM):** `mese/env_lns.txt` (`pip freeze` with a header: system, glibc, Python,
  PyTorch).
- **Cloud GPU (Kaggle):** the package versions of the Kaggle image used for TCN, ConvNeXt-1D and
  PatchTST were not recorded. The code was fixed by commit in each notebook.

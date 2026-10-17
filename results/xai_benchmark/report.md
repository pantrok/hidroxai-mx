# Reporte técnico · benchmark de arquitecturas, explicabilidad y alertas difusas

Generado por `scripts/xai_08_report.py` el 2026-10-17. Todas las cifras vienen de `numbers.json`; cada bloque indica su fuente. Protocolo: `protocol.md` (SHA-256 coincide con el congelado).

> Pronósticos retrospectivos sobre 2023–2025; no es un sistema operativo.

## 1. Veredictos

| ID | criterio SUPPORTED | veredicto |
|---|---|---|
| H1 | IC 95 % de la mediana de SS > 0 para ≥ 3 de 4 modelos aprendidos a 7 y 14 días (agregado) | SUPPORTED |
| H1-b | IC 95 % de la mediana de ΔNSE (profundo − XGBoost) > 0, por horizonte | h1: SUPPORTED, h7: OPEN, h14: OPEN |
| H2-a | mediana de Spearman ≥ 0.5 en ≥ 2/3 de las combinaciones cuenca (≥ 8 est.) × horizonte | REJECTED |
| H2-b | ≥ 75 % de los pares (modelo, cuenca) con rezago de precipitación más importante en 1–3 días (h = 1) | SUPPORTED |
| H3 | IC 95 % de ΔCSI (difuso − umbral) > 0 para P90 en h = 1 y h = 7 (agregado) | SUPPORTED |

## 2. Datos y diseño

- Snapshot v2026.10 (10.5281/zenodo.23150556). 95 estaciones modeladas en 4 cuencas piloto (Lerma–Santiago: 43, Pánuco: 39, Alta del Balsas: 12, Cutzamala: 1); 6 fuera de toda unidad (CHAMC, CMNMC, LPNMC, LPSMC, LPZMC, TLAMC).
- Estaciones evaluables en prueba: 91 por horizonte (no evaluables: CAPNR, GDLMX, SRSJL, TMTSL).
- Muestras (entrenamiento / validación / prueba): h = 1: 254,481 / 59,073 / 63,478; h = 7: 251,663 / 58,336 / 62,056; h = 14: 248,874 / 57,565 / 60,630.

## 3. RQ1 · desempeño

- Configuración elegida en validación: xgboost_h1 → xgboost-6, xgboost_h7 → xgboost-4, xgboost_h14 → xgboost-6, tcn_h1 → tcn-64, tcn_h7 → tcn-32, tcn_h14 → tcn-32, convnext_h1 → convnext-64, convnext_h7 → convnext-64, convnext_h14 → convnext-32, patchtst_h1 → patchtst-32, patchtst_h7 → patchtst-32, patchtst_h14 → patchtst-64.
- Mejor mediana de NSE por horizonte: h = 1: ARIMA, h = 7: ConvNeXt-1D, h = 14: XGBoost.
- SS mediano contra persistencia a h = 1: ARIMA 0.175, XGBoost 0.149, TCN 0.161, ConvNeXt-1D 0.143, PatchTST 0.159.
- H1: SUPPORTED. Modelos con IC > 0: h = 7 → 4, h = 14 → 4.
- H1-b: h1: SUPPORTED, h7: OPEN, h14: OPEN. ΔNSE (profundo − XGBoost): tcn_h1 0.003 [0.001, 0.006], convnext_h1 0.001 [-0.004, 0.004], patchtst_h1 0.003 [-0.005, 0.006], tcn_h7 -0.001 [-0.010, 0.004], convnext_h7 -0.003 [-0.011, 0.003], patchtst_h7 -0.004 [-0.012, 0.001], tcn_h14 -0.007 [-0.017, 0.006], convnext_h14 -0.028 [-0.038, -0.021], patchtst_h14 -0.021 [-0.035, -0.005].
- Descriptivo (no preregistrado), ΔNSE contra ARIMA: xgboost_h1 -0.004 [-0.019, 0.005], tcn_h1 0.003 [-0.005, 0.007], convnext_h1 -0.005 [-0.020, 0.005], patchtst_h1 -0.005 [-0.014, 0.003], xgboost_h7 0.021 [0.012, 0.037], tcn_h7 0.022 [0.002, 0.033], convnext_h7 0.003 [-0.007, 0.023], patchtst_h7 0.014 [0.003, 0.028], xgboost_h14 0.043 [0.028, 0.065], tcn_h14 0.033 [0.013, 0.062], convnext_h14 0.019 [0.005, 0.043], patchtst_h14 0.023 [0.003, 0.045].
- Descriptivo (no preregistrado), componentes del KGE a h = 1 (α = σ_sim/σ_obs; mediana y fracción de estaciones con α < 1): Persistence α 0.999 (0.659), r 0.779, ARIMA α 0.771 (1.000), r 0.784, XGBoost α 0.715 (0.978), r 0.783, TCN α 0.730 (0.989), r 0.788, ConvNeXt-1D α 0.720 (0.967), r 0.784, PatchTST α 0.771 (0.956), r 0.782.

| h | modelo | NSE mediana [IQR] | KGE mediana | RMSE mediana (m³/s) | SS mediana [IC 95 %] |
|---|---|---|---|---|---|
| 1 | Persistence | 0.558 [0.124, 0.777] | 0.776 | 4.80 | 0 (referencia) |
| 1 | Climatology | 0.035 [-0.202, 0.206] | 0.050 | 7.45 | -1.624 [-2.960, -0.803] |
| 1 | ARIMA | 0.613 [0.316, 0.759] | 0.654 | 4.62 | 0.175 [0.115, 0.201] |
| 1 | XGBoost | 0.599 [0.308, 0.746] | 0.579 | 4.61 | 0.149 [0.060, 0.190] |
| 1 | TCN | 0.606 [0.323, 0.745] | 0.598 | 4.66 | 0.161 [0.082, 0.226] |
| 1 | ConvNeXt-1D | 0.585 [0.285, 0.739] | 0.582 | 4.66 | 0.143 [0.077, 0.176] |
| 1 | PatchTST | 0.607 [0.315, 0.739] | 0.619 | 4.60 | 0.159 [0.084, 0.196] |
| 7 | Persistence | -0.158 [-0.567, 0.203] | 0.375 | 8.78 | 0 (referencia) |
| 7 | Climatology | 0.040 [-0.241, 0.215] | 0.056 | 7.46 | 0.061 [-0.098, 0.219] |
| 7 | ARIMA | 0.140 [0.040, 0.354] | 0.133 | 6.99 | 0.310 [0.264, 0.338] |
| 7 | XGBoost | 0.173 [0.082, 0.388] | 0.167 | 6.92 | 0.314 [0.286, 0.347] |
| 7 | TCN | 0.173 [0.063, 0.382] | 0.164 | 6.91 | 0.323 [0.273, 0.364] |
| 7 | ConvNeXt-1D | 0.179 [0.048, 0.382] | 0.157 | 6.97 | 0.321 [0.285, 0.360] |
| 7 | PatchTST | 0.171 [0.035, 0.387] | 0.161 | 6.86 | 0.306 [0.271, 0.347] |
| 14 | Persistence | -0.390 [-0.656, -0.015] | 0.282 | 8.86 | 0 (referencia) |
| 14 | Climatology | 0.035 [-0.234, 0.211] | 0.065 | 7.48 | 0.221 [0.134, 0.302] |
| 14 | ARIMA | 0.046 [-0.007, 0.209] | -0.052 | 7.34 | 0.320 [0.269, 0.345] |
| 14 | XGBoost | 0.109 [0.014, 0.291] | 0.071 | 7.24 | 0.361 [0.331, 0.385] |
| 14 | TCN | 0.089 [0.011, 0.285] | 0.058 | 7.21 | 0.350 [0.323, 0.370] |
| 14 | ConvNeXt-1D | 0.080 [-0.000, 0.253] | 0.031 | 7.28 | 0.343 [0.298, 0.359] |
| 14 | PatchTST | 0.079 [0.000, 0.255] | 0.016 | 7.20 | 0.328 [0.293, 0.351] |

| h | modelo | KGE mediana | r mediana | α mediana | β mediana | fracción con α < 1 |
|---|---|---|---|---|---|---|
| 1 | Persistence | 0.776 | 0.779 | 0.999 | 0.999 | 0.659 |
| 1 | Climatology | 0.050 | 0.357 | 0.517 | 1.155 | 0.890 |
| 1 | ARIMA | 0.654 | 0.784 | 0.771 | 0.896 | 1.000 |
| 1 | XGBoost | 0.579 | 0.783 | 0.715 | 0.862 | 0.978 |
| 1 | TCN | 0.598 | 0.788 | 0.730 | 0.881 | 0.989 |
| 1 | ConvNeXt-1D | 0.582 | 0.784 | 0.720 | 0.877 | 0.967 |
| 1 | PatchTST | 0.619 | 0.782 | 0.771 | 0.899 | 0.956 |
| 7 | Persistence | 0.375 | 0.386 | 0.996 | 0.992 | 0.648 |
| 7 | Climatology | 0.056 | 0.357 | 0.515 | 1.152 | 0.846 |
| 7 | ARIMA | 0.133 | 0.439 | 0.420 | 0.729 | 0.989 |
| 7 | XGBoost | 0.167 | 0.496 | 0.457 | 0.741 | 0.967 |
| 7 | TCN | 0.164 | 0.481 | 0.459 | 0.710 | 0.967 |
| 7 | ConvNeXt-1D | 0.157 | 0.486 | 0.456 | 0.728 | 0.967 |
| 7 | PatchTST | 0.161 | 0.469 | 0.460 | 0.722 | 0.945 |
| 14 | Persistence | 0.282 | 0.289 | 0.992 | 0.983 | 0.637 |
| 14 | Climatology | 0.065 | 0.360 | 0.515 | 1.149 | 0.868 |
| 14 | ARIMA | -0.052 | 0.317 | 0.303 | 0.673 | 0.978 |
| 14 | XGBoost | 0.071 | 0.437 | 0.392 | 0.708 | 0.956 |
| 14 | TCN | 0.058 | 0.420 | 0.421 | 0.709 | 0.945 |
| 14 | ConvNeXt-1D | 0.031 | 0.404 | 0.405 | 0.658 | 0.945 |
| 14 | PatchTST | 0.016 | 0.388 | 0.370 | 0.689 | 0.934 |

## 4. RQ2 · explicabilidad

- Muestra fija: hasta 2000 ventanas por cuenca y horizonte, semilla 20261010; IG con 64 pasos. Error de completitud de IG (mediana |δ|): ConvNeXt-1D 5.96e-08, PatchTST 1.11e-07, TCN 0.00125.
- H2-a: REJECTED. Fracción de combinaciones con Spearman ≥ 0.5: 0.0; < 0.3: 0.778.
- H2-b: SUPPORTED. Proporción de pares en 1–3 días: 1.0.
- Descriptivo: fracción de pares cuyo rezago más importante es el mínimo posible (= h, precipitación del día de emisión): h1 1.0, h7 0.833, h14 0.583. Con h = 1 el criterio de H2-b no distingue un efecto físico de un efecto de recencia.
- Descriptivo: participación de la precipitación en la importancia total, h = 1: XGBoost 0.093, TCN 0.088, ConvNeXt-1D 0.063, PatchTST 0.107.

| cuenca | h | Spearman mediano | rezago P XGBoost (d) | rezago P TCN (d) | rezago P ConvNeXt-1D (d) | rezago P PatchTST (d) |
|---|---|---|---|---|---|---|
| Lerma–Santiago | 1 | 0.34 | 1 | 1 | 1 | 1 |
| Lerma–Santiago | 7 | 0.24 | 7 | 7 | 7 | 32 |
| Lerma–Santiago | 14 | 0.22 | 14 | 14 | 14 | 18 |
| Pánuco | 1 | 0.31 | 1 | 1 | 1 | 1 |
| Pánuco | 7 | 0.27 | 7 | 7 | 7 | 7 |
| Pánuco | 14 | 0.23 | 14 | 14 | 17 | 14 |
| Alta del Balsas | 1 | 0.27 | 1 | 1 | 1 | 1 |
| Alta del Balsas | 7 | 0.26 | 29 | 7 | 7 | 7 |
| Alta del Balsas | 14 | 0.21 | 15 | 14 | 17 | 24 |
| Cutzamala | 1 | 0.26 | 1 | 1 | 1 | 1 |
| Cutzamala | 7 | 0.09 | 7 | 7 | 8 | 7 |
| Cutzamala | 14 | -0.08 | 43 | 14 | 14 | 31 |

## 5. RQ3 · alertas difusas

- H3: SUPPORTED (variante pre-corrección: SUPPORTED).
- Corrección del 2026-10-10: el `TrapezoidalMF` copiado de forecasting daba pertenencia 0 en los hombros verticales (dispersión = 0, percentil = 1), así que esas muestras quedaban en nivel normal. Se corrigió para que implemente los trapecios del protocolo; ambas variantes se reportan (proof ledger).
- Frontera del sistema congelado: alerta desde el percentil 0.8985 con dispersión 0 y desde 0.975 con dispersión 0.30; emergencia desde 0.9825 con dispersión 0.
- Descriptivo, de dónde sale la diferencia (h = 1): P90: 495 alarmas solo del umbral (479 con dispersión alta, tasa de acierto 0.0303) y 104 solo difusas (tasa de acierto 0.6058); P99: 8 alarmas solo del umbral (6 con dispersión alta, tasa de acierto 0.25) y 270 solo difusas (tasa de acierto 0.4556). En P90 la ganancia viene de suprimir alarmas con miembros en desacuerdo; en P99, de la frontera de emergencia más baja que 0.99.

| evento | h | eventos | POD difuso | FAR difuso | CSI difuso | POD umbral | FAR umbral | CSI umbral | ΔCSI [IC 95 %] | ΔCSI pre-corrección |
|---|---|---|---|---|---|---|---|---|---|---|
| P90 | 1 | 5883 | 0.746 | 0.267 | 0.586 | 0.737 | 0.320 | 0.548 | 0.038 [0.004, 0.069] | 0.092 [0.004, 0.174] |
| P90 | 7 | 5808 | 0.336 | 0.501 | 0.251 | 0.333 | 0.528 | 0.243 | 0.009 [0.001, 0.016] | 0.029 [0.003, 0.060] |
| P90 | 14 | 5738 | 0.175 | 0.603 | 0.139 | 0.172 | 0.681 | 0.126 | 0.013 [0.003, 0.023] | 0.019 [0.003, 0.037] |
| P99 | 1 | 694 | 0.424 | 0.415 | 0.326 | 0.249 | 0.282 | 0.227 | 0.099 [0.057, 0.141] | 0.098 [0.057, 0.141] |
| P99 | 7 | 686 | 0.016 | 0.871 | 0.015 | 0.009 | 0.786 | 0.009 | 0.006 [0.000, 0.013] | 0.006 [0.000, 0.013] |
| P99 | 14 | 682 | 0.004 | 0.955 | 0.004 | 0.004 | 0.939 | 0.004 | -0.000 [-0.001, 0.000] | -0.003 [-0.008, 0.000] |

## 6. Robustez · walk-forward anual

- Pliegues del protocolo §3 (entrenamiento 2010 – Y−2, validación Y−1, prueba Y; Y = 2021–2025), una semilla (20261010); especificación: proof_ledger.md, especificación de ejecución del walk-forward (2026-10-11).
- Comprobaciones: las funciones de criterios reproducen los veredictos oficiales y la evaluación de alertas con 12 miembros reproduce `e_rq3.json`.
- Ranking por NSE mediana (descriptivo): W de Kendall entre años h = 1: 0.52, h = 7: 0.577, h = 14: 0.537.
- Robustez (veredicto anual contra el principal): H1 estable; H1-b h = 1 inestable; H1-b h = 7 estable con excepciones; H1-b h = 14 estable con excepciones; H2-a estable; H2-b estable; H3 (4 miembros) estable con excepciones.
- H3 con 4 miembros en la partición principal (referencia): SUPPORTED.

| año de prueba | estaciones (h = 1) | H1 | H1-b (h1 / h7 / h14) | H2-a | H2-b | H3 (4 miembros) | mejor NSE (h1 / h7 / h14) |
|---|---|---|---|---|---|---|---|
| 2021 | 92 | SUPPORTED | SUPPORTED / OPEN / OPEN | REJECTED | SUPPORTED | SUPPORTED | ARIMA / XGBoost / XGBoost |
| 2022 | 91 | SUPPORTED | OPEN / OPEN / REJECTED | REJECTED | SUPPORTED | REJECTED | TCN / XGBoost / XGBoost |
| 2023 | 58 | SUPPORTED | OPEN / OPEN / OPEN | REJECTED | SUPPORTED | OPEN | XGBoost / XGBoost / XGBoost |
| 2024 | 77 | SUPPORTED | OPEN / REJECTED / REJECTED | REJECTED | SUPPORTED | SUPPORTED | ARIMA / XGBoost / Climatology |
| 2025 | 51 | SUPPORTED | OPEN / OPEN / OPEN | REJECTED | SUPPORTED | SUPPORTED | ARIMA / ConvNeXt-1D / Climatology |
| robustez |  | estable | inestable / estable con excepciones / estable con excepciones | estable | estable | estable con excepciones | W de Kendall 0.52 / 0.577 / 0.537 |

## Diagnósticos post hoc (descriptivos)

Criterios: proof_ledger.md, sección 'Diagnósticos post hoc' (2026-10-11, escritos antes de calcular). No cambian veredictos ni métricas principales.

- D1 (¿2023 seco?): SUPPORTED. Cuencas con inferencia donde 2023 tiene la menor razón de gasto y anomalía de precipitación < 0: 3 de 3. Lerma–Santiago: precipitación -26.9 %, razón de gasto 0.388; Pánuco: precipitación -41.3 %, razón de gasto 0.476; Alta del Balsas: precipitación -39.6 %, razón de gasto 0.370.
- β de la climatología por año del walk-forward (h = 1): 2021 1.0401, 2022 1.6261, 2023 2.7661, 2024 0.9956, 2025 0.7833.
- D2-a (smearing de Duan): SUPPORTED. Acercamiento de la mediana de β a 1 (h = 1): XGBoost 0.0973, TCN 0.0842, ConvNeXt-1D 0.0876, PatchTST 0.0895.
- D2-b (XGBoost sin log1p): SUPPORTED. Mediana de α a h = 1: 0.7989 (log1p: 0.7149); NSE 0.543 (log1p: 0.5994).

| cuenca | año | anomalía de precipitación (%) | estaciones (P) | razón de gasto | estaciones (Q) |
|---|---|---|---|---|---|
| Alta del Balsas | 2021 | -7.3 | 12 | 0.663 | 12 |
| Alta del Balsas | 2022 | -36.4 | 12 | 0.591 | 12 |
| Alta del Balsas | 2023 | -39.6 | 6 | 0.370 | 8 |
| Alta del Balsas | 2024 | -8.4 | 12 | 0.851 | 12 |
| Alta del Balsas | 2025 | -18.2 | 11 | 0.940 | 12 |
| Cutzamala | 2021 | -17.2 | 1 | 0.893 | 1 |
| Cutzamala | 2022 | -12.3 | 1 | 0.792 | 1 |
| Cutzamala | 2023 |  | 0 |  | 0 |
| Cutzamala | 2024 |  | 0 | 1.075 | 1 |
| Cutzamala | 2025 | -5.8 | 1 | 0.674 | 1 |
| Lerma–Santiago | 2021 | 9.3 | 38 | 1.264 | 40 |
| Lerma–Santiago | 2022 | -9.8 | 38 | 0.689 | 40 |
| Lerma–Santiago | 2023 | -26.9 | 23 | 0.388 | 33 |
| Lerma–Santiago | 2024 | 0.9 | 37 | 0.901 | 39 |
| Lerma–Santiago | 2025 | 10.9 | 41 | 1.107 | 39 |
| Pánuco | 2021 | 10.0 | 38 | 0.778 | 38 |
| Pánuco | 2022 | -35.5 | 37 | 0.572 | 37 |
| Pánuco | 2023 | -41.3 | 19 | 0.476 | 32 |
| Pánuco | 2024 | 5.3 | 32 | 1.007 | 34 |
| Pánuco | 2025 | 24.6 | 31 | 1.103 | 34 |

| modelo | h | variante | β | α | r | NSE | KGE |
|---|---|---|---|---|---|---|---|
| ARIMA | 1 | original | 0.896 | 0.771 | 0.784 | 0.613 | 0.654 |
| ARIMA | 1 | smearing | 0.992 | 0.838 | 0.784 | 0.588 | 0.697 |
| ConvNeXt-1D | 1 | original | 0.877 | 0.720 | 0.784 | 0.585 | 0.582 |
| ConvNeXt-1D | 1 | smearing | 0.964 | 0.761 | 0.784 | 0.581 | 0.632 |
| PatchTST | 1 | original | 0.899 | 0.771 | 0.782 | 0.607 | 0.619 |
| PatchTST | 1 | smearing | 0.989 | 0.811 | 0.782 | 0.552 | 0.654 |
| TCN | 1 | original | 0.881 | 0.730 | 0.788 | 0.606 | 0.598 |
| TCN | 1 | smearing | 0.966 | 0.786 | 0.788 | 0.578 | 0.646 |
| XGBoost | 1 | original | 0.862 | 0.715 | 0.783 | 0.599 | 0.579 |
| XGBoost | 1 | smearing | 0.959 | 0.772 | 0.783 | 0.563 | 0.627 |
| XGBoost sin log1p | 1 | espacio_original | 1.065 | 0.799 | 0.772 | 0.543 | 0.588 |
| ARIMA | 7 | original | 0.729 | 0.420 | 0.439 | 0.140 | 0.133 |
| ARIMA | 7 | smearing | 0.986 | 0.530 | 0.439 | 0.158 | 0.253 |
| ConvNeXt-1D | 7 | original | 0.728 | 0.456 | 0.486 | 0.179 | 0.157 |
| ConvNeXt-1D | 7 | smearing | 0.956 | 0.555 | 0.486 | 0.157 | 0.231 |
| PatchTST | 7 | original | 0.722 | 0.460 | 0.469 | 0.171 | 0.161 |
| PatchTST | 7 | smearing | 0.967 | 0.584 | 0.469 | 0.185 | 0.300 |
| TCN | 7 | original | 0.710 | 0.459 | 0.481 | 0.173 | 0.164 |
| TCN | 7 | smearing | 0.947 | 0.562 | 0.481 | 0.183 | 0.255 |
| XGBoost | 7 | original | 0.741 | 0.457 | 0.496 | 0.173 | 0.167 |
| XGBoost | 7 | smearing | 0.943 | 0.565 | 0.496 | 0.195 | 0.279 |
| XGBoost sin log1p | 7 | espacio_original | 1.090 | 0.592 | 0.507 | 0.186 | 0.290 |
| ARIMA | 14 | original | 0.673 | 0.303 | 0.317 | 0.046 | -0.052 |
| ARIMA | 14 | smearing | 0.980 | 0.396 | 0.317 | 0.069 | 0.075 |
| ConvNeXt-1D | 14 | original | 0.658 | 0.405 | 0.404 | 0.080 | 0.031 |
| ConvNeXt-1D | 14 | smearing | 0.893 | 0.480 | 0.404 | 0.094 | 0.102 |
| PatchTST | 14 | original | 0.689 | 0.370 | 0.388 | 0.079 | 0.016 |
| PatchTST | 14 | smearing | 0.948 | 0.490 | 0.388 | 0.098 | 0.113 |
| TCN | 14 | original | 0.709 | 0.421 | 0.420 | 0.089 | 0.058 |
| TCN | 14 | smearing | 0.935 | 0.520 | 0.420 | 0.111 | 0.132 |
| XGBoost | 14 | original | 0.708 | 0.392 | 0.437 | 0.109 | 0.071 |
| XGBoost | 14 | smearing | 0.926 | 0.457 | 0.437 | 0.109 | 0.141 |
| XGBoost sin log1p | 14 | espacio_original | 1.062 | 0.507 | 0.412 | 0.124 | 0.152 |

## 7. Cómputo

- GPU (Tesla T4, Kaggle): 1.625 h en 216 corridas del diseño principal y 1.394 h en 180 del walk-forward. CPU local: 5.408 h en total (presupuesto 40 h).
- Épocas de las redes (mediana; fracción con parada temprana): ConvNeXt-1D 23.0 (0.986), PatchTST 19.5 (1.0), TCN 17.0 (1.0).

| recurso | componente | horas |
|---|---|---|
| GPU Tesla T4 | TCN | 0.412 |
| GPU Tesla T4 | ConvNeXt-1D | 0.433 |
| GPU Tesla T4 | PatchTST | 0.781 |
| CPU | ARIMA | 1.665 |
| CPU | XGBoost | 0.184 |
| CPU | piloto de tiempos | 0.392 |
| CPU | xai_06_explain | 0.553 |
| CPU | xai_07_alerts | 0.002 |
| CPU | xai_05_evaluate | 0.006 |
| CPU | xai_10_walk_forward_eval | 0.654 |
| CPU | xai_11_diagnostics | 0.103 |
| CPU | xai_14_review_analyses | 0.464 |
| CPU | walk-forward ARIMA | 1.136 |
| CPU | walk-forward XGBoost | 0.249 |
| GPU | walk-forward (redes) | 1.394 |
| GPU | total diseño principal | 1.625 |
| GPU | total con walk-forward | 3.019 |
| CPU | total | 5.408 |

## 8. No realizado

- Informer: fuera del diseño principal (protocolo §4)
- Cruce con el Monitor de Sequía municipal (D1, opcional): cruce con el Monitor de Sequía municipal (requiere descargar el archivo oficial)

## 9. Archivos

- Figuras: `results/xai_benchmark/figures/` (PNG a 300 dpi y PDF).
- Tablas: `results/xai_benchmark/tables/` (CSV y `tables.md`).
- Cifras: `results/xai_benchmark/numbers.json`.

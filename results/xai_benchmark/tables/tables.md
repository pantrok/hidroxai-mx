## T1_rq1_agregado

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

## T1b_rq1_kge_componentes

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

## T2_rq1_por_cuenca

| cuenca | estaciones | h | modelo | NSE mediana | SS mediana [IC 95 %] |
|---|---|---|---|---|---|
| Lerma–Santiago | 41 | 1 | Persistence | 0.609 | 0.000 |
| Lerma–Santiago | 41 | 1 | Climatology | 0.176 | -1.745 [-4.058, -0.640] |
| Lerma–Santiago | 41 | 1 | ARIMA | 0.681 | 0.115 [-0.018, 0.194] |
| Lerma–Santiago | 41 | 1 | XGBoost | 0.680 | 0.110 [-0.035, 0.189] |
| Lerma–Santiago | 41 | 1 | TCN | 0.687 | 0.154 [0.023, 0.226] |
| Lerma–Santiago | 41 | 1 | ConvNeXt-1D | 0.696 | 0.140 [0.048, 0.170] |
| Lerma–Santiago | 41 | 1 | PatchTST | 0.677 | 0.159 [0.047, 0.200] |
| Lerma–Santiago | 41 | 7 | Persistence | 0.070 | 0.000 |
| Lerma–Santiago | 41 | 7 | Climatology | 0.187 | 0.043 [-0.198, 0.226] |
| Lerma–Santiago | 41 | 7 | ARIMA | 0.274 | 0.250 [0.158, 0.316] |
| Lerma–Santiago | 41 | 7 | XGBoost | 0.351 | 0.277 [0.185, 0.325] |
| Lerma–Santiago | 41 | 7 | TCN | 0.325 | 0.257 [0.199, 0.326] |
| Lerma–Santiago | 41 | 7 | ConvNeXt-1D | 0.331 | 0.288 [0.211, 0.339] |
| Lerma–Santiago | 41 | 7 | PatchTST | 0.325 | 0.265 [0.206, 0.307] |
| Lerma–Santiago | 41 | 14 | Persistence | -0.108 | 0.000 |
| Lerma–Santiago | 41 | 14 | Climatology | 0.184 | 0.228 [0.078, 0.316] |
| Lerma–Santiago | 41 | 14 | ARIMA | 0.120 | 0.210 [0.145, 0.316] |
| Lerma–Santiago | 41 | 14 | XGBoost | 0.213 | 0.331 [0.220, 0.383] |
| Lerma–Santiago | 41 | 14 | TCN | 0.174 | 0.345 [0.258, 0.376] |
| Lerma–Santiago | 41 | 14 | ConvNeXt-1D | 0.140 | 0.307 [0.216, 0.349] |
| Lerma–Santiago | 41 | 14 | PatchTST | 0.174 | 0.315 [0.175, 0.344] |
| Pánuco | 37 | 1 | Persistence | 0.515 | 0.000 |
| Pánuco | 37 | 1 | Climatology | -0.029 | -1.683 [-3.197, -0.824] |
| Pánuco | 37 | 1 | ARIMA | 0.535 | 0.175 [0.088, 0.215] |
| Pánuco | 37 | 1 | XGBoost | 0.526 | 0.151 [0.012, 0.198] |
| Pánuco | 37 | 1 | TCN | 0.544 | 0.151 [0.039, 0.228] |
| Pánuco | 37 | 1 | ConvNeXt-1D | 0.537 | 0.130 [-0.142, 0.207] |
| Pánuco | 37 | 1 | PatchTST | 0.584 | 0.144 [-0.038, 0.196] |
| Pánuco | 37 | 7 | Persistence | -0.335 | 0.000 |
| Pánuco | 37 | 7 | Climatology | -0.031 | 0.081 [-0.143, 0.284] |
| Pánuco | 37 | 7 | ARIMA | 0.090 | 0.325 [0.294, 0.365] |
| Pánuco | 37 | 7 | XGBoost | 0.127 | 0.305 [0.274, 0.382] |
| Pánuco | 37 | 7 | TCN | 0.093 | 0.346 [0.269, 0.378] |
| Pánuco | 37 | 7 | ConvNeXt-1D | 0.088 | 0.314 [0.274, 0.379] |
| Pánuco | 37 | 7 | PatchTST | 0.065 | 0.301 [0.246, 0.361] |
| Pánuco | 37 | 14 | Persistence | -0.550 | 0.000 |
| Pánuco | 37 | 14 | Climatology | -0.031 | 0.204 [0.065, 0.361] |
| Pánuco | 37 | 14 | ARIMA | -0.003 | 0.348 [0.246, 0.372] |
| Pánuco | 37 | 14 | XGBoost | 0.039 | 0.364 [0.296, 0.389] |
| Pánuco | 37 | 14 | TCN | 0.026 | 0.347 [0.263, 0.388] |
| Pánuco | 37 | 14 | ConvNeXt-1D | 0.004 | 0.355 [0.234, 0.375] |
| Pánuco | 37 | 14 | PatchTST | 0.006 | 0.322 [0.235, 0.371] |
| Alta del Balsas | 12 | 1 | Persistence | 0.187 | 0.000 |
| Alta del Balsas | 12 | 1 | Climatology | -0.047 | -0.444 [-3.193, -0.064] |
| Alta del Balsas | 12 | 1 | ARIMA | 0.354 | 0.266 [0.181, 0.301] |
| Alta del Balsas | 12 | 1 | XGBoost | 0.350 | 0.277 [0.109, 0.328] |
| Alta del Balsas | 12 | 1 | TCN | 0.345 | 0.258 [0.095, 0.317] |
| Alta del Balsas | 12 | 1 | ConvNeXt-1D | 0.348 | 0.255 [0.120, 0.321] |
| Alta del Balsas | 12 | 1 | PatchTST | 0.359 | 0.276 [0.108, 0.333] |
| Alta del Balsas | 12 | 7 | Persistence | -0.352 | 0.000 |
| Alta del Balsas | 12 | 7 | Climatology | -0.044 | 0.040 [-1.159, 0.465] |
| Alta del Balsas | 12 | 7 | ARIMA | 0.084 | 0.369 [0.330, 0.431] |
| Alta del Balsas | 12 | 7 | XGBoost | 0.141 | 0.402 [0.332, 0.432] |
| Alta del Balsas | 12 | 7 | TCN | 0.148 | 0.409 [0.332, 0.429] |
| Alta del Balsas | 12 | 7 | ConvNeXt-1D | 0.141 | 0.407 [0.344, 0.455] |
| Alta del Balsas | 12 | 7 | PatchTST | 0.129 | 0.409 [0.344, 0.433] |
| Alta del Balsas | 12 | 14 | Persistence | -0.472 | 0.000 |
| Alta del Balsas | 12 | 14 | Climatology | -0.045 | 0.214 [-1.092, 0.498] |
| Alta del Balsas | 12 | 14 | ARIMA | 0.038 | 0.365 [0.321, 0.464] |
| Alta del Balsas | 12 | 14 | XGBoost | 0.129 | 0.415 [0.346, 0.502] |
| Alta del Balsas | 12 | 14 | TCN | 0.138 | 0.456 [0.340, 0.508] |
| Alta del Balsas | 12 | 14 | ConvNeXt-1D | 0.152 | 0.450 [0.329, 0.513] |
| Alta del Balsas | 12 | 14 | PatchTST | 0.120 | 0.412 [0.341, 0.500] |
| Cutzamala | 1 | 1 | Persistence | 0.640 | 0.000 |
| Cutzamala | 1 | 1 | Climatology | 0.107 | -1.483 |
| Cutzamala | 1 | 1 | ARIMA | 0.726 | 0.238 |
| Cutzamala | 1 | 1 | XGBoost | 0.717 | 0.213 |
| Cutzamala | 1 | 1 | TCN | 0.728 | 0.245 |
| Cutzamala | 1 | 1 | ConvNeXt-1D | 0.668 | 0.077 |
| Cutzamala | 1 | 1 | PatchTST | 0.718 | 0.216 |
| Cutzamala | 1 | 7 | Persistence | 0.260 | 0.000 |
| Cutzamala | 1 | 7 | Climatology | 0.110 | -0.203 |
| Cutzamala | 1 | 7 | ARIMA | 0.453 | 0.261 |
| Cutzamala | 1 | 7 | XGBoost | 0.496 | 0.319 |
| Cutzamala | 1 | 7 | TCN | 0.501 | 0.326 |
| Cutzamala | 1 | 7 | ConvNeXt-1D | 0.424 | 0.222 |
| Cutzamala | 1 | 7 | PatchTST | 0.489 | 0.310 |
| Cutzamala | 1 | 14 | Persistence | -0.010 | 0.000 |
| Cutzamala | 1 | 14 | Climatology | 0.084 | 0.093 |
| Cutzamala | 1 | 14 | ARIMA | 0.310 | 0.317 |
| Cutzamala | 1 | 14 | XGBoost | 0.427 | 0.432 |
| Cutzamala | 1 | 14 | TCN | 0.314 | 0.321 |
| Cutzamala | 1 | 14 | ConvNeXt-1D | 0.266 | 0.273 |
| Cutzamala | 1 | 14 | PatchTST | 0.232 | 0.239 |

## T3_rq2_concordancia_rezagos

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

## T4_rq3_alertas

| evento | h | eventos | POD difuso | FAR difuso | CSI difuso | POD umbral | FAR umbral | CSI umbral | ΔCSI [IC 95 %] | ΔCSI pre-corrección |
|---|---|---|---|---|---|---|---|---|---|---|
| P90 | 1 | 5883 | 0.746 | 0.267 | 0.586 | 0.737 | 0.320 | 0.548 | 0.038 [0.004, 0.069] | 0.092 [0.004, 0.174] |
| P90 | 7 | 5808 | 0.336 | 0.501 | 0.251 | 0.333 | 0.528 | 0.243 | 0.009 [0.001, 0.016] | 0.029 [0.003, 0.060] |
| P90 | 14 | 5738 | 0.175 | 0.603 | 0.139 | 0.172 | 0.681 | 0.126 | 0.013 [0.003, 0.023] | 0.019 [0.003, 0.037] |
| P99 | 1 | 694 | 0.424 | 0.415 | 0.326 | 0.249 | 0.282 | 0.227 | 0.099 [0.057, 0.141] | 0.098 [0.057, 0.141] |
| P99 | 7 | 686 | 0.016 | 0.871 | 0.015 | 0.009 | 0.786 | 0.009 | 0.006 [0.000, 0.013] | 0.006 [0.000, 0.013] |
| P99 | 14 | 682 | 0.004 | 0.955 | 0.004 | 0.004 | 0.939 | 0.004 | -0.000 [-0.001, 0.000] | -0.003 [-0.008, 0.000] |

## T5_hipotesis

| ID | criterio SUPPORTED | veredicto |
|---|---|---|
| H1 | IC 95 % de la mediana de SS > 0 para ≥ 3 de 4 modelos aprendidos a 7 y 14 días (agregado) | SUPPORTED |
| H1-b | IC 95 % de la mediana de ΔNSE (profundo − XGBoost) > 0, por horizonte | h1: SUPPORTED, h7: OPEN, h14: OPEN |
| H2-a | mediana de Spearman ≥ 0.5 en ≥ 2/3 de las combinaciones cuenca (≥ 8 est.) × horizonte | REJECTED |
| H2-b | ≥ 75 % de los pares (modelo, cuenca) con rezago de precipitación más importante en 1–3 días (h = 1) | SUPPORTED |
| H3 | IC 95 % de ΔCSI (difuso − umbral) > 0 para P90 en h = 1 y h = 7 (agregado) | SUPPORTED |

## T6_computo

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
| CPU | walk-forward ARIMA | 1.136 |
| CPU | walk-forward XGBoost | 0.249 |
| GPU | walk-forward (redes) | 1.394 |
| GPU | total diseño principal | 1.625 |
| GPU | total con walk-forward | 3.019 |
| CPU | total | 4.944 |

## T7_walk_forward

| año de prueba | estaciones (h = 1) | H1 | H1-b (h1 / h7 / h14) | H2-a | H2-b | H3 (4 miembros) | mejor NSE (h1 / h7 / h14) |
|---|---|---|---|---|---|---|---|
| 2021 | 92 | SUPPORTED | SUPPORTED / OPEN / OPEN | REJECTED | SUPPORTED | SUPPORTED | ARIMA / XGBoost / XGBoost |
| 2022 | 91 | SUPPORTED | OPEN / OPEN / REJECTED | REJECTED | SUPPORTED | REJECTED | TCN / XGBoost / XGBoost |
| 2023 | 58 | SUPPORTED | OPEN / OPEN / OPEN | REJECTED | SUPPORTED | OPEN | XGBoost / XGBoost / XGBoost |
| 2024 | 77 | SUPPORTED | OPEN / REJECTED / REJECTED | REJECTED | SUPPORTED | SUPPORTED | ARIMA / XGBoost / Climatology |
| 2025 | 51 | SUPPORTED | OPEN / OPEN / OPEN | REJECTED | SUPPORTED | SUPPORTED | ARIMA / ConvNeXt-1D / Climatology |
| robustez |  | estable | inestable / estable con excepciones / estable con excepciones | estable | estable | estable con excepciones | W de Kendall 0.52 / 0.577 / 0.537 |

## T7b_walk_forward_metricas

| año | h | modelo | estaciones | NSE mediana | SS mediana [IC 95 %] |
|---|---|---|---|---|---|
| 2021 | 1 | ARIMA | 92 | 0.656 | 0.046 [0.006, 0.110] |
| 2021 | 1 | Climatology | 92 | 0.106 | -1.317 [-2.239, -0.865] |
| 2021 | 1 | ConvNeXt-1D | 92 | 0.649 | 0.001 [-0.047, 0.094] |
| 2021 | 1 | PatchTST | 92 | 0.632 | -0.006 [-0.074, 0.057] |
| 2021 | 1 | Persistence | 92 | 0.650 | 0.000 |
| 2021 | 1 | TCN | 92 | 0.638 | 0.052 [0.002, 0.102] |
| 2021 | 1 | XGBoost | 92 | 0.647 | 0.039 [-0.018, 0.089] |
| 2022 | 1 | ARIMA | 91 | 0.570 | 0.145 [0.078, 0.187] |
| 2022 | 1 | Climatology | 91 | -0.585 | -3.495 [-5.856, -1.908] |
| 2022 | 1 | ConvNeXt-1D | 91 | 0.643 | 0.158 [0.088, 0.197] |
| 2022 | 1 | PatchTST | 91 | 0.618 | 0.108 [0.062, 0.172] |
| 2022 | 1 | Persistence | 91 | 0.610 | 0.000 |
| 2022 | 1 | TCN | 91 | 0.648 | 0.132 [0.075, 0.182] |
| 2022 | 1 | XGBoost | 91 | 0.628 | 0.159 [0.087, 0.190] |
| 2023 | 1 | ARIMA | 58 | 0.368 | 0.192 [0.132, 0.240] |
| 2023 | 1 | Climatology | 58 | -2.434 | -5.051 [-11.431, -2.264] |
| 2023 | 1 | ConvNeXt-1D | 58 | 0.335 | 0.188 [0.157, 0.279] |
| 2023 | 1 | PatchTST | 58 | 0.323 | 0.210 [0.150, 0.272] |
| 2023 | 1 | Persistence | 58 | 0.267 | 0.000 |
| 2023 | 1 | TCN | 58 | 0.364 | 0.213 [0.156, 0.263] |
| 2023 | 1 | XGBoost | 58 | 0.378 | 0.215 [0.163, 0.277] |
| 2024 | 1 | ARIMA | 77 | 0.638 | 0.138 [0.080, 0.171] |
| 2024 | 1 | Climatology | 77 | 0.199 | -1.492 [-2.333, -0.771] |
| 2024 | 1 | ConvNeXt-1D | 77 | 0.587 | 0.062 [0.013, 0.113] |
| 2024 | 1 | PatchTST | 77 | 0.608 | 0.060 [-0.044, 0.140] |
| 2024 | 1 | Persistence | 77 | 0.567 | 0.000 |
| 2024 | 1 | TCN | 77 | 0.618 | 0.114 [0.020, 0.173] |
| 2024 | 1 | XGBoost | 77 | 0.597 | 0.095 [0.016, 0.181] |
| 2025 | 1 | ARIMA | 51 | 0.683 | 0.096 [-0.024, 0.136] |
| 2025 | 1 | Climatology | 51 | 0.138 | -1.165 [-2.074, -0.734] |
| 2025 | 1 | ConvNeXt-1D | 51 | 0.608 | -0.015 [-0.221, 0.154] |
| 2025 | 1 | PatchTST | 51 | 0.594 | 0.076 [-0.136, 0.148] |
| 2025 | 1 | Persistence | 51 | 0.672 | 0.000 |
| 2025 | 1 | TCN | 51 | 0.599 | 0.017 [-0.121, 0.122] |
| 2025 | 1 | XGBoost | 51 | 0.602 | 0.104 [-0.083, 0.192] |
| 2021 | 7 | ARIMA | 92 | 0.122 | 0.322 [0.270, 0.353] |
| 2021 | 7 | Climatology | 92 | 0.101 | 0.312 [0.164, 0.381] |
| 2021 | 7 | ConvNeXt-1D | 92 | 0.138 | 0.362 [0.304, 0.408] |
| 2021 | 7 | PatchTST | 92 | 0.167 | 0.354 [0.286, 0.396] |
| 2021 | 7 | Persistence | 92 | -0.248 | 0.000 |
| 2021 | 7 | TCN | 92 | 0.165 | 0.343 [0.292, 0.402] |
| 2021 | 7 | XGBoost | 92 | 0.196 | 0.351 [0.305, 0.407] |
| 2022 | 7 | ARIMA | 91 | 0.162 | 0.317 [0.255, 0.355] |
| 2022 | 7 | Climatology | 91 | -0.585 | -0.429 [-0.810, -0.088] |
| 2022 | 7 | ConvNeXt-1D | 91 | 0.132 | 0.318 [0.248, 0.368] |
| 2022 | 7 | PatchTST | 91 | 0.170 | 0.310 [0.254, 0.363] |
| 2022 | 7 | Persistence | 91 | -0.242 | 0.000 |
| 2022 | 7 | TCN | 91 | 0.131 | 0.297 [0.233, 0.359] |
| 2022 | 7 | XGBoost | 91 | 0.187 | 0.334 [0.287, 0.369] |
| 2023 | 7 | ARIMA | 55 | 0.001 | 0.375 [0.318, 0.450] |
| 2023 | 7 | Climatology | 55 | -2.611 | -1.386 [-5.216, -0.750] |
| 2023 | 7 | ConvNeXt-1D | 55 | 0.001 | 0.345 [0.285, 0.445] |
| 2023 | 7 | PatchTST | 55 | 0.001 | 0.334 [0.269, 0.433] |
| 2023 | 7 | Persistence | 55 | -0.634 | 0.000 |
| 2023 | 7 | TCN | 55 | 0.002 | 0.374 [0.299, 0.445] |
| 2023 | 7 | XGBoost | 55 | 0.008 | 0.340 [0.286, 0.433] |
| 2024 | 7 | ARIMA | 76 | 0.179 | 0.292 [0.237, 0.317] |
| 2024 | 7 | Climatology | 76 | 0.196 | 0.235 [0.085, 0.293] |
| 2024 | 7 | ConvNeXt-1D | 76 | 0.171 | 0.280 [0.209, 0.316] |
| 2024 | 7 | PatchTST | 76 | 0.177 | 0.290 [0.263, 0.324] |
| 2024 | 7 | Persistence | 76 | -0.081 | 0.000 |
| 2024 | 7 | TCN | 76 | 0.168 | 0.279 [0.196, 0.322] |
| 2024 | 7 | XGBoost | 76 | 0.207 | 0.313 [0.261, 0.335] |
| 2025 | 7 | ARIMA | 45 | 0.116 | 0.259 [0.173, 0.327] |
| 2025 | 7 | Climatology | 45 | 0.135 | 0.287 [0.146, 0.372] |
| 2025 | 7 | ConvNeXt-1D | 45 | 0.192 | 0.281 [0.203, 0.347] |
| 2025 | 7 | PatchTST | 45 | 0.182 | 0.299 [0.213, 0.328] |
| 2025 | 7 | Persistence | 45 | -0.129 | 0.000 |
| 2025 | 7 | TCN | 45 | 0.184 | 0.281 [0.246, 0.355] |
| 2025 | 7 | XGBoost | 45 | 0.175 | 0.281 [0.239, 0.338] |
| 2021 | 14 | ARIMA | 91 | 0.056 | 0.286 [0.255, 0.345] |
| 2021 | 14 | Climatology | 91 | 0.096 | 0.351 [0.205, 0.400] |
| 2021 | 14 | ConvNeXt-1D | 91 | 0.074 | 0.370 [0.313, 0.419] |
| 2021 | 14 | PatchTST | 91 | 0.066 | 0.352 [0.289, 0.387] |
| 2021 | 14 | Persistence | 91 | -0.332 | 0.000 |
| 2021 | 14 | TCN | 91 | 0.094 | 0.379 [0.349, 0.407] |
| 2021 | 14 | XGBoost | 91 | 0.108 | 0.388 [0.322, 0.423] |
| 2022 | 14 | ARIMA | 91 | 0.075 | 0.320 [0.251, 0.364] |
| 2022 | 14 | Climatology | 91 | -0.579 | -0.116 [-0.462, 0.083] |
| 2022 | 14 | ConvNeXt-1D | 91 | 0.086 | 0.317 [0.270, 0.381] |
| 2022 | 14 | PatchTST | 91 | 0.108 | 0.314 [0.274, 0.362] |
| 2022 | 14 | Persistence | 91 | -0.391 | 0.000 |
| 2022 | 14 | TCN | 91 | 0.103 | 0.377 [0.315, 0.396] |
| 2022 | 14 | XGBoost | 91 | 0.124 | 0.372 [0.336, 0.394] |
| 2023 | 14 | ARIMA | 47 | -0.004 | 0.382 [0.297, 0.415] |
| 2023 | 14 | Climatology | 47 | -2.722 | -1.153 [-5.213, -0.542] |
| 2023 | 14 | ConvNeXt-1D | 47 | -0.007 | 0.342 [0.271, 0.394] |
| 2023 | 14 | PatchTST | 47 | -0.049 | 0.303 [0.166, 0.360] |
| 2023 | 14 | Persistence | 47 | -0.615 | 0.000 |
| 2023 | 14 | TCN | 47 | -0.013 | 0.336 [0.155, 0.378] |
| 2023 | 14 | XGBoost | 47 | -0.004 | 0.327 [0.190, 0.398] |
| 2024 | 14 | ARIMA | 75 | 0.039 | 0.277 [0.231, 0.322] |
| 2024 | 14 | Climatology | 75 | 0.213 | 0.333 [0.249, 0.380] |
| 2024 | 14 | ConvNeXt-1D | 75 | 0.044 | 0.282 [0.226, 0.319] |
| 2024 | 14 | PatchTST | 75 | 0.081 | 0.281 [0.243, 0.321] |
| 2024 | 14 | Persistence | 75 | -0.355 | 0.000 |
| 2024 | 14 | TCN | 75 | 0.071 | 0.303 [0.254, 0.334] |
| 2024 | 14 | XGBoost | 75 | 0.123 | 0.323 [0.292, 0.356] |
| 2025 | 14 | ARIMA | 44 | -0.030 | 0.232 [0.104, 0.343] |
| 2025 | 14 | Climatology | 44 | 0.134 | 0.393 [0.303, 0.441] |
| 2025 | 14 | ConvNeXt-1D | 44 | 0.031 | 0.330 [0.287, 0.383] |
| 2025 | 14 | PatchTST | 44 | 0.009 | 0.302 [0.241, 0.371] |
| 2025 | 14 | Persistence | 44 | -0.395 | 0.000 |
| 2025 | 14 | TCN | 44 | 0.055 | 0.328 [0.241, 0.367] |
| 2025 | 14 | XGBoost | 44 | 0.059 | 0.306 [0.245, 0.368] |

## T8_sequia_2023

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

## T1c_kge_log1p

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

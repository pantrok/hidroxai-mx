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
| CPU | xai_05_evaluate | 0.004 |
| CPU | xai_06_explain | 0.553 |
| CPU | xai_07_alerts | 0.002 |
| GPU | total | 1.625 |
| CPU | total | 2.8 |

# Reproducibilidad

Cada producto se puede regenerar con el código del repositorio, y cada cifra publicada sale de un
archivo de resultados que nombra el script que la produjo.

## El dataset y su artículo

- **[`REPRODUCE.md`](https://github.com/pantrok/hidroxai-mx/blob/main/REPRODUCE.md)**: para cada
  tabla, figura y cifra del artículo de *Data in Brief*, el comando que la produce, el archivo de
  salida y el tiempo medido en una copia limpia del ZIP. Aplica al archivo
  `HidroXAI-MX-v2026.11.zip` y al tag `v2026.11` del repositorio.
- **Pipeline.** De la descarga a la tabla de características: etapas `scripts/01`–`12`,
  encadenadas en `dvc.yaml`. `dvc.lock` fija las versiones de cada salida y el remoto de DVC está
  en Cloudflare R2.
- **Procedencia.** `raw/_manifest.json` registra la URL de origen, el SHA-256 y el tamaño de cada
  archivo crudo, y `manifest_zenodo.json` los de todo el ZIP.
- **Copia limpia.** `scripts/dib_16_clean_copy_check.py` descomprime el ZIP en una carpeta vacía,
  crea un entorno nuevo, regenera los productos y los compara con los empaquetados. Cada corrida
  deja un registro con fecha en `results/dib_revision/`.

## El benchmark de pronóstico explicable

- **Protocolo congelado.**
  [`results/xai_benchmark/protocol.md`](https://github.com/pantrok/hidroxai-mx/blob/main/results/xai_benchmark/protocol.md)
  se escribió antes de entrenar cualquier modelo. Las enmiendas posteriores están fechadas en
  [`proof_ledger.md`](https://github.com/pantrok/hidroxai-mx/blob/main/results/xai_benchmark/proof_ledger.md),
  junto con las huellas SHA-256 de los archivos que no deben cambiar.
- **Una fuente de cifras.** Toda cifra del benchmark sale de
  [`numbers.json`](https://github.com/pantrok/hidroxai-mx/blob/main/results/xai_benchmark/numbers.json);
  cada bloque nombra su script de origen.
- **Cómo regenerarlo.** El
  [README del benchmark](https://github.com/pantrok/hidroxai-mx/blob/main/results/xai_benchmark/README.md)
  da el comando y el archivo de salida de cada tabla y figura.
- **Versión citable del código.** El tag `xai-benchmark-v1.5`.
- **Dónde corrió cada parte:**

| Parte | Equipo |
|---|---|
| Perfil de muestras, referencias, ARIMA y XGBoost; evaluación, explicaciones, alertas y figuras | CPU local |
| TCN, ConvNeXt-1D y PatchTST (partición principal y walk-forward anual) | GPU en la nube (Kaggle, Tesla T4) |
| LSTM descriptivo (partición principal y walk-forward) | Laboratorio Nacional de Supercómputo del Sureste de México (LNS, BUAP), CPU |

Los tiempos de cada corrida están en `results/xai_benchmark/compute_manifest.csv` y
`results/xai_benchmark/mese/lstm_manifest.csv`. Las versiones de los paquetes del entorno local
están en `results/xai_benchmark/environment_local.txt` y las del LNS en
`results/xai_benchmark/mese/env_lns.txt`. Las del entorno de GPU en la nube no se registraron.

## El clúster LNS-BUAP

[`hpc/lns/`](https://github.com/pantrok/hidroxai-mx/tree/main/hpc/lns) contiene todo lo necesario
para entrenar el LSTM en el clúster:

- el script que arma el entorno (conda y pip);
- el empaquetado del código y los datos;
- los trabajos SLURM (`10_lstm_split.sbatch`, `11_lstm_walkforward.sbatch` y el lanzador por
  lotes `12_lote.sbatch`);
- la recolección de resultados.

La guía de uso es `LEEME_LNS.md`.

## Pruebas e integración continua

Cada cambio en el repositorio dispara la integración continua:

- las pruebas de la biblioteca (`pytest`);
- el lint (`ruff`);
- la ejecución de los cinco tutoriales en modo reducido;
- la construcción de este sitio.

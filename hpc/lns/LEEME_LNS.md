# LSTM en el LNS-BUAP · guía de uso

Entrenamiento del LSTM descriptivo (enmienda MESE en `results/xai_benchmark/proof_ledger.md`)
en la partición `comp` del LNS, en CPU. Sustituye `cuenta` por tu usuario del LNS. Las
contraseñas las escribes tú en tu cliente SSH.

**Regla del LNS:** tu `HOME` (50 GB) es solo para scripts y el entorno de Python. La guía lo
ubica en `/home/cuenta`, pero puede estar en otra ruta (por ejemplo `/zfs-home/cuenta`); los
scripts usan `$HOME`, así que da igual. El paquete, los datos y los resultados van en tu
scratch, que abajo se escribe `<scratch>`: según la guía es `/scratch/cuenta`. Para comprobarlo:
`echo $SCRATCH; ls -ld /scratch/$USER`. En el nodo de login solo se instala el entorno y se
envían trabajos; el entrenamiento va con `sbatch`.

## 0. En tu PC: preparar el paquete

Desde PowerShell, en la carpeta del repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File hpc\lns\02_empaquetar.ps1
```

Deja `dist\lns\hidroxai_lns.tar.gz` (≈ 100 MB) y `hidroxai_lns.tar.gz.sha256`. Si el script
avisa de cambios sin commit, no lo subas: primero hay que hacer el commit.

## 1. Conectarse y subir el paquete

Conéctate al nodo de login con tu cliente SSH, como siempre. Si es la primera vez que usas el
LNS, corre una sola vez:

```bash
/software/LNS/txt/gen_claves_ssh.sh
```

Sube `hidroxai_lns.tar.gz` y `hidroxai_lns.tar.gz.sha256` a `<scratch>/` con la
transferencia de archivos de tu cliente (SFTP).

Alternativa sin el cliente, desde PowerShell (salto por `ui.buap.mx`; cambia la ruta final si tu
scratch es otra):

```powershell
scp -J cuenta@ui.buap.mx dist\lns\hidroxai_lns.tar.gz dist\lns\hidroxai_lns.tar.gz.sha256 cuenta@192.168.170.213:/scratch/cuenta/
```

## 2. En el clúster, en orden

```bash
cd <scratch>
sha256sum -c hidroxai_lns.tar.gz.sha256          # debe decir: hidroxai_lns.tar.gz: OK
tar -xzf hidroxai_lns.tar.gz                      # crea <scratch>/hidroxai
cd hidroxai                                       # todo lo que sigue se corre desde aquí
head -3 PAQUETE.txt                               # commit del código empaquetado
```

**Sondeo** (no instala nada):

```bash
bash hpc/lns/00_sondeo.sh
cat sondeo_lns.txt
```

**Pégame la salida completa de `sondeo_lns.txt`.** Con ella confirmo la ruta del entorno y si hay
GPU.

**Entorno** (una vez, con el conda y el pip del clúster; queda en `$HOME/envs/hidroxai`):

```bash
bash hpc/lns/01_entorno.sh
```

El script usa el conda del PATH o el del primer módulo anaconda/miniconda que encuentre. Elige
solo la versión de PyTorch según la glibc: 2.14.1, la del estudio, si la glibc es ≥ 2.28; 2.5.1 si
es más vieja. Deja las versiones en `<scratch>/hidroxai/env_lns.txt`. **Pégame las 4 líneas
que imprime al terminar.**

Si prefieres crear el entorno a mano con tu cliente, lo necesario es: Python 3.12 en
`$HOME/envs/hidroxai`, `torch==2.14.1` del índice `https://download.pytorch.org/whl/cpu`, y
`numpy==2.4.6 pandas==3.0.3 pyarrow==24.0.0 captum==0.9.0 pyyaml`. Después corre igual
`bash hpc/lns/01_entorno.sh`: no reinstala lo que ya está bien y escribe el registro de versiones.

**Piloto de tiempo** (mide segundos por época y memoria; tarda menos de una hora):

```bash
sbatch hpc/lns/09_piloto_tiempo.sbatch
```

Cuando termine (`squeue -u $USER` ya no lo muestra):

```bash
cat logs/lstm_piloto_<id>.out
sacct -j <id> --format=JobID,Elapsed,MaxRSS,State
```

**Pégame ambas salidas.** Con ellas fijo `-t`, `--mem` y `--cpus-per-task`.

**Partición principal y walk-forward** (con los valores que te dé; aquí van de ejemplo):

```bash
sbatch -t 12:00:00 --mem=16G hpc/lns/10_lstm_split.sbatch
# anota el número de trabajo que imprime, p. ej. 123456, y encadena el walk-forward:
sbatch --dependency=afterok:123456 -t 6:00:00 --mem=16G hpc/lns/11_lstm_walkforward.sbatch
```

Los valores de `-t`, `--mem` y `--cpus-per-task` en la línea de comandos sustituyen a los del
archivo, así que no hay que editarlo.

## 3. Seguimiento

```bash
squeue -u $USER                                    # en cola y corriendo
sacct -j <id> --format=JobID,JobName,State,Elapsed,MaxRSS,ExitCode
scancel <id>                                       # cancela todo el arreglo
scancel <id>_7                                     # cancela solo el elemento 7
tail -f logs/lstm_split_<id>_7.out                 # bitácora de un elemento
```

Si un elemento falla o se queda sin tiempo, se reenvía solo ese elemento; retoma desde su
último checkpoint:

```bash
sbatch -a 7 -t 12:00:00 --mem=16G hpc/lns/10_lstm_split.sbatch
```

## 4. Recoger y bajar los resultados

En el nodo de login, cuando ya no quede nada en la cola:

```bash
bash <scratch>/hidroxai/hpc/lns/20_recoger.sh
```

Deja `<scratch>/lstm_resultados.tar.gz` y su `.sha256` (predicciones, pesos, metadatos,
manifiestos, bitácoras, `env_lns.txt` y el consumo de `sacct`). Bájalos con la transferencia de
archivos de tu cliente, o desde PowerShell (cambia la ruta si tu scratch es otra):

```powershell
scp -J cuenta@ui.buap.mx "cuenta@192.168.170.213:/scratch/cuenta/lstm_resultados.tar.gz*" .
```

Avísame cuando estén bajados y dime en qué carpeta quedaron.

## Rutas de respaldo

- **Contenedor (ruta c):** si el sondeo muestra glibc < 2.17 o no hay internet, pero sí Apptainer
  o Singularity, el contenedor se construye fuera del LNS (Linux o WSL2 con Apptainer):
  `apptainer build hidroxai.sif hpc/lns/hidroxai_lns.def`. Se sube a `$HOME/envs/` y se corre
  `bash hpc/lns/01_entorno.sh c`.
- **Kaggle:** si nada de lo anterior funciona, el LSTM se entrena con los cuadernos
  `notebooks/kaggle_xai_*.ipynb`, como las otras redes del estudio. Antes hay que ajustar el
  commit y los argumentos del LSTM en el cuaderno; te los preparo si llega a hacer falta.

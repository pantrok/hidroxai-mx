#!/bin/bash
# LSTM en la partición principal: un elemento del arreglo por cuenca × horizonte × tamaño
# (4 × 3 × 2 = 24); cada elemento corre sus 3 semillas (20261010–12) con xai_03_train_nets.py.
# Es reanudable: al reenviar, salta las corridas con predicciones y retoma desde el checkpoint.
# %10 elementos a la vez × 24 cores = 240 cores, el máximo por usuario.
# Ajusta -t, --mem y --cpus-per-task con el piloto, desde la línea de comandos:
#   sbatch -t 12:00:00 --mem=16G hpc/lns/10_lstm_split.sbatch
#SBATCH -J lstm_split
#SBATCH -p comp
#SBATCH -n 1
#SBATCH --cpus-per-task=24
#SBATCH --mem=16G
#SBATCH -t 24:00:00
#SBATCH -a 0-23%10
#SBATCH -o logs/%x_%A_%a.out

set -eo pipefail
source hpc/lns/comun.sh

i=${SLURM_ARRAY_TASK_ID:?este script se envía como arreglo}
HS=(1 7 14); SZ=(32 64)
B=$(( i / 6 )); H=${HS[$(( (i / 2) % 3 ))]}; SIZE=${SZ[$(( i % 2 ))]}
OUT="$RUNS/split/$(slug $B)_h${H}_lstm-${SIZE}"

echo "== $(date -Iseconds) elemento $i: $(basin $B), h=$H, lstm-$SIZE, ${SLURM_CPUS_PER_TASK} hilos → $OUT"
$PY scripts/xai_03_train_nets.py --models lstm --sizes "$SIZE" --horizons "$H" --basins "$(basin $B)" \
    --device cpu --threads "$SLURM_CPUS_PER_TASK" --out "$OUT"
echo "== $(date -Iseconds) fin del elemento $i"

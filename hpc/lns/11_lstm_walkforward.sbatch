#!/bin/bash
# Walk-forward anual del LSTM: 5 años × 4 cuencas × 3 horizontes = 60 elementos, una semilla
# (20261010) y el tamaño elegido por horizonte con la regla del protocolo §4 sobre la
# validación de la partición principal (xai_15_lstm_walk_forward.py lo calcula de runs/split).
# Necesita terminada la partición principal:
#   sbatch --dependency=afterok:<id de 10_> -t 6:00:00 --mem=16G hpc/lns/11_lstm_walkforward.sbatch
#SBATCH -J lstm_wf
#SBATCH -p comp
#SBATCH -n 1
#SBATCH --cpus-per-task=24
#SBATCH --mem=16G
#SBATCH -t 12:00:00
#SBATCH -a 0-59%10
#SBATCH -o logs/%x_%A_%a.out

set -eo pipefail
source hpc/lns/comun.sh

i=${SLURM_ARRAY_TASK_ID:?este script se envía como arreglo}
YS=(2021 2022 2023 2024 2025); HS=(1 7 14)
Y=${YS[$(( i / 12 ))]}; B=$(( (i / 3) % 4 )); H=${HS[$(( i % 3 ))]}
OUT="$RUNS/wf/$(slug $B)_h${H}_y${Y}"

echo "== $(date -Iseconds) elemento $i: $(basin $B), h=$H, año $Y, ${SLURM_CPUS_PER_TASK} hilos → $OUT"
$PY scripts/xai_15_lstm_walk_forward.py --split-runs "$RUNS/split" --out "$OUT" --years "$Y" \
    --basins "$(slug $B)" --horizons "$H" --device cpu --threads "$SLURM_CPUS_PER_TASK"
echo "== $(date -Iseconds) fin del elemento $i"

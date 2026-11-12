#!/bin/bash
# Corre varios elementos de 10_ o 11_ dentro de un solo trabajo, PARALELO a la vez en el mismo
# nodo, con HILOS cada uno. Sirve cuando el LNS limita el número de trabajos enviados
# (AssocGrpSubmitJobsLimit): un arreglo cuenta un trabajo por elemento; este lote, uno.
# Llama a 10_lstm_split.sbatch / 11_lstm_walkforward.sbatch sin modificarlos.
# Uso, desde la carpeta del paquete:
#   sbatch -p normal -t 8:00:00 --export=ALL,ETAPA=10,DESDE=0,HASTA=23 hpc/lns/12_lote.sbatch
#   sbatch -p normal -t 8:00:00 --export=ALL,ETAPA=11,DESDE=0,HASTA=59 --dependency=afterok:<id> hpc/lns/12_lote.sbatch
#SBATCH -J lstm_lote
#SBATCH -p normal
#SBATCH -n 1
#SBATCH --cpus-per-task=24
#SBATCH --mem=16G
#SBATCH -t 08:00:00
#SBATCH -o logs/%x_%j.out

set -o pipefail
ETAPA="${ETAPA:?ETAPA=10 (partición principal) u 11 (walk-forward)}"
DESDE="${DESDE:-0}"
HASTA="${HASTA:?HASTA = último elemento (23 para 10, 59 para 11)}"
PARALELO="${PARALELO:-2}"
HILOS="${HILOS:-12}"
case "$ETAPA" in
    10) SCRIPT=hpc/lns/10_lstm_split.sbatch; NOMBRE=split ;;
    11) SCRIPT=hpc/lns/11_lstm_walkforward.sbatch; NOMBRE=wf ;;
    *) echo "ETAPA debe ser 10 u 11" >&2; exit 2 ;;
esac
cd "${SLURM_SUBMIT_DIR:-$PWD}" || exit 1
mkdir -p logs

elemento() {
    SLURM_ARRAY_TASK_ID="$1" SLURM_CPUS_PER_TASK="$HILOS" bash "$SCRIPT" \
        > "logs/lstm_${NOMBRE}_lote${SLURM_JOB_ID}_$1.out" 2>&1
}

echo "== $(date -Iseconds) etapa $ETAPA, elementos $DESDE–$HASTA, $PARALELO a la vez con $HILOS hilos"
fallos=0
for i in $(seq "$DESDE" "$HASTA"); do
    elemento "$i" &
    while [ "$(jobs -rp | wc -l)" -ge "$PARALELO" ]; do
        wait -n || fallos=$((fallos + 1))
    done
done
while [ "$(jobs -rp | wc -l)" -gt 0 ]; do
    wait -n || fallos=$((fallos + 1))
done
wait
echo "== $(date -Iseconds) fin: $fallos elementos con error (ver logs/lstm_${NOMBRE}_lote${SLURM_JOB_ID}_*.out)"
[ "$fallos" -eq 0 ]

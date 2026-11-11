#!/bin/bash
# Piloto de tiempo: una corrida corta del LSTM (cuenca más grande, h = 1, tamaño 64, 3 épocas)
# con 24 y con 12 hilos, para fijar -t, --mem y --cpus-per-task de 10_ y 11_.
# Uso (desde la carpeta del paquete, …/hidroxai):  sbatch hpc/lns/09_piloto_tiempo.sbatch
#SBATCH -J lstm_piloto
#SBATCH -p comp
#SBATCH -n 1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH -t 02:00:00
#SBATCH -o logs/%x_%j.out

set -eo pipefail
source hpc/lns/comun.sh

B=0                                   # Lerma–Santiago: la cuenca con más estaciones
for T in 24 12; do
    OUT="$RUNS/piloto/t$T"
    rm -rf "$OUT"
    echo "== $(date -Iseconds) piloto con $T hilos"
    $PY scripts/xai_03_train_nets.py --models lstm --sizes 64 --seeds 20261010 --horizons 1 \
        --basins "$(basin $B)" --max-epochs 3 --device cpu --threads "$T" --out "$OUT"
done

$PY - "$RUNS/piloto" <<'EOF'
import sys
from pathlib import Path
import pandas as pd
root = Path(sys.argv[1])
rows = []
for t in (24, 12):
    m = pd.read_csv(root / f"t{t}" / "compute_manifest.csv").iloc[-1]
    rows.append({"hilos": t, "s_por_epoca": m["segundos"] / m["epocas"], "pared_s": m["pared_s"]})
df = pd.DataFrame(rows)
print(df.to_string(index=False))
best = df.sort_values("s_por_epoca").iloc[0]
# Peor caso del protocolo: 100 épocas; split = 3 semillas por elemento del arreglo; margen 1.3.
split_h = 3 * 100 * best["s_por_epoca"] * 1.3 / 3600 + 0.25
wf_h = 100 * best["s_por_epoca"] * 1.3 / 3600 + 0.25
print(f"\nSugerencia: --cpus-per-task={int(best['hilos'])}; -t {split_h:.1f} h para 10_ (3 semillas) "
      f"y {wf_h:.1f} h para 11_ (1 semilla, pliegues con menos datos de entrenamiento).")
print("Memoria máxima: sacct -j $SLURM_JOB_ID --format=JobID,MaxRSS,Elapsed (al terminar).")
EOF

#!/usr/bin/env bash
# Empaqueta los resultados del LSTM para bajarlos: runs/ (predicciones, pesos, metadatos,
# manifiestos, selección), logs/, env_lns.txt y el consumo de SLURM (sacct).
# Uso (nodo de login, desde cualquier carpeta):  bash <paquete>/hpc/lns/20_recoger.sh [fecha inicial AAAA-MM-DD]
# Deja: lstm_resultados.tar.gz y su .sha256 junto a la carpeta del paquete (en tu scratch)

set -euo pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"     # carpeta del paquete (…/hidroxai)
SCR="$(dirname "$BASE")"
DESDE="${1:-2026-11-01}"
cd "$BASE"

ckpt=$(find runs -path '*/ckpt/*.pt' | wc -l)
[ "$ckpt" -eq 0 ] || echo "AVISO: $ckpt checkpoints sin terminar (corridas incompletas); se incluyen."

cp -f env_lns.txt runs/ 2>/dev/null || echo "AVISO: no está env_lns.txt (¿se corrió 01_entorno.sh?)"
# Horas-core: CPUTime = cores asignados × tiempo de pared (lo que se cobra); TotalCPU = uso real.
sacct -u "$USER" -S "$DESDE" --name=lstm_piloto,lstm_split,lstm_wf,lstm_lote -X -P \
    --format=JobID,JobName,Partition,AllocCPUS,Elapsed,CPUTimeRAW,TotalCPU,State,ExitCode > runs/sacct_lns.txt
sacct -u "$USER" -S "$DESDE" --name=lstm_piloto,lstm_split,lstm_wf,lstm_lote -P \
    --format=JobID,JobName,MaxRSS,Elapsed,State > runs/sacct_lns_pasos.txt

tar -czf "$SCR/lstm_resultados.tar.gz" runs logs
(cd "$SCR" && sha256sum lstm_resultados.tar.gz > lstm_resultados.tar.gz.sha256)
echo "Listo: $SCR/lstm_resultados.tar.gz ($(du -h "$SCR/lstm_resultados.tar.gz" | cut -f1))"
cat "$SCR/lstm_resultados.tar.gz.sha256"

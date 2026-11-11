# Configuración común de los trabajos del LNS (se carga con `source hpc/lns/comun.sh`).
# El paquete es la carpeta desde la que se envían los trabajos (…/hidroxai, en tu scratch);
# el entorno está en $HOME/envs (01_entorno.sh).

BASE="${HIDROXAI_BASE:-${SLURM_SUBMIT_DIR:-$PWD}}"
if [ ! -f "$BASE/scripts/xai_03_train_nets.py" ]; then
    echo "Envía los trabajos desde la carpeta del paquete (la que tiene scripts/ y hpc/): $BASE" >&2
    exit 1
fi
RUNS="$BASE/runs"

if [ ! -f "$HOME/envs/activar_hidroxai.sh" ]; then
    echo "Falta $HOME/envs/activar_hidroxai.sh: corre antes hpc/lns/01_entorno.sh" >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$HOME/envs/activar_hidroxai.sh"      # define HIDROXAI_PY (python del entorno o del contenedor)
PY="$HIDROXAI_PY"

export PYTHONPATH="$BASE/src"
export HIDROXAI_DATA="$BASE/data"              # features/ y processed/ del paquete
export PYTHONUTF8=1                            # nombres de cuenca con acentos y guion largo
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

# Cuenca por índice (0–3), en el orden de hidroxai_mx.models.data.BASINS.
basin() { $PY -c "import sys; from hidroxai_mx.models import data as D; print(D.BASINS[int(sys.argv[1])])" "$1"; }
slug() { case "$1" in 0) echo lerma_santiago ;; 1) echo panuco ;; 2) echo alta_balsas ;; 3) echo cutzamala ;; esac; }

cd "$BASE" || exit 1
mkdir -p "$RUNS" logs

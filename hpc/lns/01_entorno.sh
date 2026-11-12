#!/usr/bin/env bash
# Entorno de Python para entrenar el LSTM en el LNS, con el conda y el pip del clúster.
# Se corre una vez, en el nodo de login (desde tu cliente SSH). Queda en $HOME/envs/hidroxai.
#
# Ruta que se elige sola, según la glibc del sistema (queda registrada):
#   a) glibc >= 2.28: Python 3.12 de conda y, con pip, las versiones del estudio en CPU:
#      torch 2.14.1 (CPU), numpy 2.4.6, pandas 3.0.3, pyarrow 24.0.0, captum 0.9.0, pyyaml.
#   b) glibc 2.17–2.27: numpy, pandas, pyarrow y pyyaml de conda-forge (compatibles con esa
#      glibc) y torch 2.5.1, la última con ruedas manylinux2014 en CPU. La diferencia de
#      versiones con el estudio queda en env_lns.txt.
#   c) contenedor (solo si se pide): glibc < 2.17 o sin internet; ver LEEME_LNS.md.
#
# conda: el que esté en el PATH; si no, el primer módulo anaconda/miniconda/conda de
# `module avail`; si tampoco, micromamba (binario estático, requiere internet).
#
# Uso:  bash hpc/lns/01_entorno.sh            (rutas a/b, automático)
#       bash hpc/lns/01_entorno.sh c          (contenedor ya subido a $HOME/envs/hidroxai.sif)
# Deja: $HOME/envs/activar_hidroxai.sh (lo cargan los trabajos) y env_lns.txt en la carpeta del paquete

set -euo pipefail
ENVS="$HOME/envs"
PREFIX="$ENVS/hidroxai"
BASE="$(cd "$(dirname "$0")/../.." && pwd)"     # carpeta del paquete (…/hidroxai)
PYTORCH_CPU="https://download.pytorch.org/whl/cpu"
export PIP_NO_CACHE_DIR=1
# logs/ debe existir antes de sbatch: SLURM abre ahí la salida (-o logs/...) antes de correr el trabajo.
mkdir -p "$ENVS" "$BASE/logs"
type module >/dev/null 2>&1 || source /etc/profile >/dev/null 2>&1 || true

glibc=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
mayor=${glibc%%.*}; menor=${glibc#*.}; menor=${menor%%.*}
if [ "${1:-}" = "c" ]; then
    RUTA=c
elif [ "$mayor" -gt 2 ] || { [ "$mayor" -eq 2 ] && [ "$menor" -ge 28 ]; }; then
    RUTA=a
elif [ "$mayor" -eq 2 ] && [ "$menor" -ge 17 ]; then
    RUTA=b
else
    echo "glibc $glibc < 2.17: usa la ruta c (contenedor) o Kaggle; ver LEEME_LNS.md." >&2
    exit 3
fi
echo "glibc $glibc → ruta $RUTA"

buscar_conda() {
    if command -v conda >/dev/null 2>&1; then command -v conda; return; fi
    if type module >/dev/null 2>&1; then
        local mod
        mod=$(module -t avail 2>&1 | grep -iE '^(anaconda|miniconda|miniforge|conda)' | head -1 || true)
        if [ -n "$mod" ]; then
            module load "$mod" >/dev/null 2>&1 && echo "módulo cargado: $mod" >&2
            if command -v conda >/dev/null 2>&1; then command -v conda; return; fi
        fi
    fi
    echo "Sin conda en el PATH ni en módulos: uso micromamba." >&2
    if [ ! -x "$ENVS/bin/micromamba" ]; then
        (cd "$ENVS" && curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba)
    fi
    export MAMBA_ROOT_PREFIX="$ENVS/mamba"
    echo "$ENVS/bin/micromamba"
}

if [ "$RUTA" = c ]; then
    SIF="$ENVS/hidroxai.sif"
    RUNNER=$(command -v apptainer || command -v singularity || true)
    [ -n "$RUNNER" ] || { echo "No hay Apptainer ni Singularity: hay que entrenar en Kaggle (LEEME_LNS.md)." >&2; exit 3; }
    [ -f "$SIF" ] || { echo "Falta $SIF: constrúyelo fuera con hpc/lns/hidroxai_lns.def y súbelo." >&2; exit 4; }
    PYCMD="$RUNNER exec --bind /scratch $SIF python"
    GESTOR="$RUNNER"
else
    CONDA=$(buscar_conda)
    GESTOR="$CONDA"
    # conda-forge sin el canal defaults (evita los términos de uso del canal de Anaconda).
    # Si el entorno ya existe (p. ej. creado a mano), no se recrea: pip solo completa lo que falte.
    if [ "$RUTA" = a ]; then
        [ -x "$PREFIX/bin/python" ] || "$CONDA" create -y -p "$PREFIX" --override-channels -c conda-forge python=3.12 pip
        "$PREFIX/bin/python" -m pip install "torch==2.14.1" --index-url "$PYTORCH_CPU"
        "$PREFIX/bin/python" -m pip install "numpy==2.4.6" "pandas==3.0.3" "pyarrow==24.0.0" "captum==0.9.0" pyyaml
    else
        [ -x "$PREFIX/bin/python" ] || "$CONDA" create -y -p "$PREFIX" --override-channels -c conda-forge python=3.12 pip numpy pandas pyarrow pyyaml
        "$PREFIX/bin/python" -m pip install "torch==2.5.1" --index-url "$PYTORCH_CPU"
        "$PREFIX/bin/python" -m pip install captum || echo "AVISO: captum no se instaló (no se usa para entrenar)."
    fi
    PYCMD="$PREFIX/bin/python"
fi

cat > "$ENVS/activar_hidroxai.sh" <<EOF
# Generado por hpc/lns/01_entorno.sh (ruta $RUTA) el $(date -Iseconds)
export HIDROXAI_RUTA="$RUTA"
export HIDROXAI_PY="$PYCMD"
EOF

# Registro de versiones (en ESI faltó): cabecera comentada + pip freeze.
{
    echo "# ruta $RUTA · $(date -Iseconds) · $(hostname)"
    echo "# sistema: $(cat /etc/redhat-release 2>/dev/null || uname -sr) · glibc $glibc"
    echo "# gestor: $GESTOR"
    $PYCMD -c "import sys, torch, numpy, pandas, pyarrow; print('# python', sys.version.split()[0], '| torch', torch.__version__, '| numpy', numpy.__version__, '| pandas', pandas.__version__, '| pyarrow', pyarrow.__version__, '| hilos por defecto', torch.get_num_threads())"
    $PYCMD -m pip freeze
} > "$BASE/env_lns.txt"

echo "Entorno listo (ruta $RUTA). Versiones en $BASE/env_lns.txt:"
head -4 "$BASE/env_lns.txt"

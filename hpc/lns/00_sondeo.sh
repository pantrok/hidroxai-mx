#!/usr/bin/env bash
# Sondeo del LNS-BUAP, en el nodo de login: sistema, glibc, SLURM, módulos, contenedores,
# salida a internet y cuotas. No instala ni modifica nada.
# Uso:  bash hpc/lns/00_sondeo.sh        → escribe sondeo_lns.txt en la carpeta actual

OUT="${1:-sondeo_lns.txt}"
SCR="${SCRATCH:-/scratch/$USER}"
type module >/dev/null 2>&1 || source /etc/profile >/dev/null 2>&1

seccion() { printf '\n== %s\n' "$1"; }
web() { printf '%-40s ' "$1"; curl -sI --max-time 15 "$1" | head -1 || true; echo; }

{
    seccion "fecha y nodo";      date -Iseconds; echo "$USER@$(hostname)"; uname -srm
    seccion "HOME y scratch";    echo "HOME=$HOME  SCRATCH=${SCRATCH:-<sin definir>}  carpeta actual=$(pwd)"
    for d in "/scratch/$USER" "/zfs-scratch/$USER" "${SCRATCH:-}"; do [ -n "$d" ] && ls -ld "$d" 2>&1; done
    df -h 2>/dev/null | grep -iE "scratch|zfs|home|Filesystem"
    seccion "sistema";           cat /etc/redhat-release 2>/dev/null || cat /etc/os-release
    seccion "glibc";             ldd --version | head -1; getconf GNU_LIBC_VERSION 2>/dev/null
    seccion "SLURM: particiones (sinfo)"; sinfo -o "%P %a %l %D %c %m %G"
    seccion "SLURM: scontrol show partition"; scontrol show partition
    seccion "SLURM: versión";    sbatch --version
    seccion "SLURM: límites de la cuenta"; sacctmgr -n show assoc user="$USER" format=Account,Partition,MaxJobs,MaxSubmit,GrpTRES,MaxTRES,MaxWall 2>&1 | head -20
    seccion "módulos (filtro)";  module avail 2>&1 | grep -iE "python|anaconda|conda|miniconda|cuda|gcc|singularity|apptainer"
    seccion "contenedores";      command -v apptainer singularity || echo "ni apptainer ni singularity en PATH"
    seccion "python del sistema"; command -v python3 && python3 --version
    seccion "herramientas";      for c in curl wget bzip2 tar sha256sum; do printf '%-10s %s\n' "$c" "$(command -v "$c" || echo no)"; done
    seccion "internet"
    web https://pypi.org
    web https://download.pytorch.org/whl/cpu/
    web https://micro.mamba.pm
    web https://conda.anaconda.org/conda-forge/
    seccion "cuotas";            quota -s 2>&1 | head -20; lfs quota -h -u "$USER" /scratch 2>&1 | head -10
    seccion "espacio";           df -h "$HOME" "$SCR" 2>&1
    seccion "uso";               du -sh "$HOME" 2>/dev/null; du -sh "$SCR" 2>/dev/null
    seccion "nodo de login";     nproc; free -g
} > "$OUT" 2>&1

echo "Listo: $(pwd)/$OUT  (pega su contenido para elegir la ruta del entorno)"

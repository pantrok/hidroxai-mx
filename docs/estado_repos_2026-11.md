# Estado del repositorio · noviembre de 2026

Cierre del 2026-11-12 de los trabajos que usan este repositorio: el benchmark XAI (artículo
MESE, parte A) y el dataset Hidro-MX (artículo de *Data in Brief*, parte B). Ninguna cifra
reportada cambió. No se creó ningún *release*; la integración con Zenodo publica una versión con
cada *release*.

## Tags

| Tag | Commit | Qué marca |
|---|---|---|
| `v2026.10` | `4f2b887` | Dataset v2026.10 (primera revisión de *Data in Brief*) |
| `v2026.11` | `f20a9a9` | Dataset v2026.11 (segunda revisión), archivado en Zenodo: DOI [10.5281/zenodo.24119292](https://doi.org/10.5281/zenodo.24119292), `HidroXAI-MX-v2026.11.zip`, MD5 `6ca7ab32be0b3173ddb8ab31ffba5134` |
| `xai-benchmark-v1` | `26c9a1c` | Benchmark XAI con protocolo congelado (partición principal y walk-forward anual) |
| `xai-benchmark-v1.1` | `ec13149` | v1 más diagnósticos post hoc (sequía de 2023, sesgo de la retransformación log1p) |
| `xai-benchmark-v1.2` | `767c969` | v1.1 más figuras para *Earth Science Informatics*, mapa y datos de la Tabla 1 |
| `xai-benchmark-v1.3` | `74d1461` | v1.2 más análisis post hoc de la revisión por pares |
| `xai-benchmark-v1.4` | `4f20de9` | Ajuste MESE: LSTM descriptivo y comprobación de imputados |
| `xai-benchmark-v1.5` | `ada01bb` (objeto del tag `220b6fd`) | Cierre MESE: Fig. 1 para revisión anónima, README del benchmark, entornos y corrección de `tipo`. Es el que cita *Code availability* |

`v1.4` no se movió; `v1.5` es un tag nuevo.

## Parte A · benchmark XAI (MESE)

| Punto | Qué se hizo | Dónde |
|---|---|---|
| A.1 | Trabajo MESE en commits `42977b7`, `08222ba` y `4f20de9` | — |
| A.2 | Opción `--review` del script de figuras: Fig. 1 con "Open hydroclimatic dataset (CONAGUA-SIH)" en lugar del nombre y el depósito del dataset | `scripts/xai_17_figures_mese.py`; `results/xai_benchmark/figures_mese/Fig1_review.{pdf,eps,png}` (el TIFF se regenera, no se versiona) |
| A.3 | Tag nuevo `xai-benchmark-v1.5` | tabla de tags |
| A.4 | Cómo reproducir cada tabla y figura: comando, archivo de salida y dónde corrió cada paso (CPU local, GPU en la nube, LNS-BUAP) | `results/xai_benchmark/README.md` |
| A.5 | Entornos. El README declara que las versiones del entorno de GPU en la nube (Kaggle) no se registraron | `results/xai_benchmark/environment_local.txt` (`pip freeze`, Python 3.12.6); `results/xai_benchmark/mese/env_lns.txt` |
| A.6 | `xai_03_train_nets.py` distingue `principal` y `walk_forward` (`--tipo`, `principal` por defecto), con prueba. Los manifiestos publicados no cambian y no se regeneran. Nota fechada y huella nueva en el `proof_ledger` | commit "fix: run type metadata"; `tests/test_run_type_metadata.py` (4 pruebas pasan) |

## Parte B · dataset (Data in Brief)

**B.1 · Comprobaciones.**

- `git status` estaba limpio antes del cierre.
- `v2026.11` apunta a `f20a9a9`, el commit con el que se construyó el ZIP archivado
  (DOI 10.5281/zenodo.24119292).
- `REPRODUCE.md` está en la raíz.

**B.2 · Mantenimiento** (commit "chore: maintenance after R2", sin *release*):

| Hallazgo | Qué se hizo |
|---|---|
| Comentario de `scipy` en `pyproject.toml` | Ahora describe su uso real: experimento de imputación (PCHIP y spline) y estadística de rangos. La imputación del pipeline es lineal |
| Rutas de `figuras_envio.csv` | `dib_15` escribe la columna `origen` relativa a la raíz del repositorio en las dos estructuras (repositorio y archivo de Zenodo). El CSV regenerado es igual al versionado |
| `dib_16` sobrescribía su registro | Cada corrida escribe `clean_copy_check_<AAAAMMDD-HHMMSS>.{json,md}`. Se conserva el registro de la R1 (`clean_copy_check.{json,md}`, 2026-10-04) |
| Comparación de JSON | `dib_17` compara números de JSON con tolerancia relativa y absoluta de 1e-12, como ya hacía con los CSV. El residuo de control (5.7e-14 en el repositorio, 0 en la copia limpia) deja de contar como diferencia. `r2/reproducibilidad.json` publicado no se regenera |
| `.venv` local apuntaba a la ruta anterior | Reinstalación editable (`pip install -e .`) solo en local; no forma parte del repositorio. `import hidroxai_mx` funciona sin `PYTHONPATH` |
| Ventana de la cobertura | **No se cambia.** Se documenta en `docs/nota_diseno_cobertura.md` (definición publicada 2010–2025 con registro hasta el 2025-09-03) |

**Prueba desde copia limpia del ZIP v2026.11** con los scripts nuevos
(`results/dib_revision/clean_copy_check_20261112-234058.{json,md}`):

- valores de JSON y CSV idénticos;
- 6 de 7 figuras idénticas por píxel;
- la Fig. 2 difiere en 4,946 píxeles (0.15 %), igual que en las pruebas de la R1 y la R2, por
  versiones distintas de las bibliotecas de dibujo.

**B.3 · CHANGELOG.** Sección "Unreleased" con estos cambios y la línea de que no alteran datos ni
resultados.

## Hallazgos colaterales

Los archivos `hallazgos_colaterales.md` se quedan en local. `.gitignore` los excluye en todo el
repositorio.

- **Data in Brief, segunda revisión:** cinco hallazgos, todos atendidos sin cambiar datos ni
  cifras. Cuatro (1, 3, 4 y 5) en el commit de mantenimiento; el 2 (venv) solo en local.
- **MESE:** un hallazgo (`tipo` en `xai_03`), corregido en "fix: run type metadata".
- `MESE_report.md` y `R2_report.md` se quedan en local (`.git/info/exclude`).

## Commits del cierre

| Commit | Mensaje |
|---|---|
| `8a71a40` | fix: run type metadata |
| `ada01bb` | docs(xai): MESE closing: review Fig. 1, benchmark README and environments (tag `xai-benchmark-v1.5`) |
| `e4df87f` | chore: maintenance after R2 |
| el siguiente | docs: repository status, November 2026 (este archivo) |

Confirmados por el autor el 2026-11-13. Se subieron `main` y el tag `xai-benchmark-v1.5` a
`origin`, sin *release*.

## Pendiente para la siguiente ronda

- **MESE T5:** espejo anónimo del código para la revisión doble ciega, creado desde
  `xai-benchmark-v1.5`. Con su URL se corre `xai_19 --url-anonima <URL>`.
- Nada pendiente en el dataset: no hay *release* nuevo, y v2026.11 sigue siendo la versión
  archivada.

## `git status` final

Después del último commit y del push (`git status -sb`), sin cambios pendientes:

```
## main...origin/main
```

Quedan en disco, fuera de git a propósito: los dos `hallazgos_colaterales.md` (`.gitignore`) y
`MESE_report.md` y `R2_report.md` (`.git/info/exclude`).

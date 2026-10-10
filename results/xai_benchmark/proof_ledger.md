# Proof ledger · HidroXAI-MX (modelos, explicabilidad, alertas difusas)

**Estado: protocolo CONGELADO el 2026-10-10.** Ningún modelo se había entrenado ni
evaluado al congelarlo.

## Congelamiento

| Campo | Valor |
|---|---|
| Fecha de aprobación | 2026-10-10 (autor) |
| SHA-256 de `protocol.md` | `8df99290b17bfc8a5a15dd46492772866ace00ec57d9687d0b5e73809db05799` (contenido con fin de línea LF, como queda en git) |
| Commit | el primero que contiene `results/xai_benchmark/protocol.md` |

Para verificarlo: `git show <commit>:results/xai_benchmark/protocol.md | sha256sum`.

## Afirmaciones, verificadores y criterios

Los criterios SUPPORTED/REJECTED son los de `protocol.md`, sección 7. Cada afirmación
queda `OPEN` hasta tener evidencia.

| ID | Verificador | Estado |
|---|---|---|
| H1 | Bootstrap de estaciones (10,000) de la mediana de SS contra persistencia, *h* = 7 y 14, agregado | OPEN |
| H1-b | Bootstrap de la mediana de ΔNSE (profundo − XGBoost), por horizonte | OPEN |
| H2-a | Mediana de Spearman entre pares de modelos sobre importancias 6 × 30 | OPEN |
| H2-b | Proporción de pares (modelo, cuenca) con el rezago de precipitación más importante en 1–3 días respecto al objetivo, *h* = 1 | OPEN |
| H3 | Bootstrap de ΔCSI (difuso − umbral), eventos P90, *h* = 1 y 7, agregado | OPEN |

## Enmiendas

Ninguna.

## Evidencia

Pendiente.

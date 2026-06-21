# Verificación de fuentes — 2026-06-18

Resultado de probar en vivo los portales y endpoints del inventario `datasets_HidroXAI_MX.docx`.

| # | Fuente | Endpoint | Estado | Nota |
|---|--------|----------|--------|------|
| 1 | SIH catálogos | datos.gob.mx (CSV) | ⚠️ Reconfirmar | El portal es una SPA JS; el HTML llega vacío al fetch directo. El recurso probablemente sigue, pero validar la descarga binaria. |
| 2 | **SIH series CSV** | sih.conagua.gob.mx/climas.html, /hidros.html | ✅ OK | **Hallazgo clave**: publica series históricas diarias como CSV UTF-8, actualización semanal. Fuente primaria para 2010–2025. |
| 3 | BANDAS | app.conagua.gob.mx/bandas | ✅ OK | Catálogos y bases hidrométricas + presas (.mdb). Respaldo histórico profundo. |
| 4 | SMN climatológicas | smn.conagua.gob.mx (portal + KMZ) | ✅ OK | ~5,400 estaciones, ~2,800 reportan. Requiere User-Agent. |
| 5 | CICESE-CLICOM | clicom-mex.cicese.mx | ✅ OK | Series diarias 1920–2012, descarga CSV/MAT. Cita obligatoria. |
| 6 | INEGI CEM 3.0 | inegi.org.mx/app/geo2/elevacionesmex | ✅ OK | Versión 202508; resoluciones 15/30/60/90/120 m; descarga por estado/carta/área. |
| 7 | Acuíferos | datos.gob.mx (SHP) | ⚠️ Reconfirmar | Misma SPA JS que (1). |
| 8 | **DataMéxico** | datamexico.org → economia.gob.mx/datamexico | 🔁 Migrado | Sitio migró a economia.gob.mx; API Tesseract (`api.datamexico.org`) debe reconfirmarse. Auxiliar, prioridad baja. |
| 9 | Monitor de Sequía | smn.conagua.gob.mx/monitor-de-sequia | ✅ OK | Categorías D0–D4 quincenales. |

## Recomendaciones derivadas
1. **Reordenar prioridad de fuentes de series**: SIH-CSV como primaria (reciente, sin `.mdb`),
   BANDAS como respaldo histórico pre-2013 y para presas.
2. **datos.gob.mx**: implementar el descargador con reintentos y, si la descarga directa
   falla, resolver el recurso vía la API CKAN del portal o el espejo del SIH.
3. **DataMéxico**: tratar como opcional; aislar tras una bandera de configuración para que
   su indisponibilidad no rompa el pipeline.
4. Registrar el hash y la fecha de cada descarga (pooch) para trazabilidad del snapshot DVC.

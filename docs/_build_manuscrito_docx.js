// Genera el borrador del manuscrito Data in Brief para HidroXAI-MX.
// Lee data/processed/reportes/metrics.json y embebe las figuras del script 09.
// Salida: docs/manuscrito_data_in_brief_borrador.docx

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, ImageRun, PageBreak, PageOrientation,
} = require("docx");

const REPO = path.resolve("G:/Mi unidad/Publicaciones/HidroMx/Código/hidroxai-mx");
const FIG = path.join(REPO, "data/processed/reportes");
const METRICS = JSON.parse(fs.readFileSync(path.join(FIG, "metrics.json"), "utf-8"));

// --- helpers ----------------------------------------------------------------
const FONT = "Arial";
const BLACK = "000000";
const ACCENT = "7A1737";
const GREY_BORDER = { style: BorderStyle.SINGLE, size: 1, color: "B0B0B0" };
const CELL_BORDERS = { top: GREY_BORDER, bottom: GREY_BORDER, left: GREY_BORDER, right: GREY_BORDER };
const CELL_MARGINS = { top: 100, bottom: 100, left: 140, right: 140 };

const p = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: 120, line: 300 },
    alignment: opts.align ?? AlignmentType.JUSTIFIED,
    ...(opts.heading ? { heading: opts.heading } : {}),
    children: [new TextRun({ text, font: FONT, size: opts.size ?? 22, bold: !!opts.bold, italics: !!opts.italics, color: opts.color ?? BLACK })],
  });

const bullet = (text) =>
  new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 80, line: 280 },
    alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, font: FONT, size: 22 })],
  });

const code = (text) =>
  new Paragraph({
    spacing: { after: 80, line: 260 },
    indent: { left: 360 },
    children: [new TextRun({ text, font: "Consolas", size: 20 })],
  });

const blank = () => new Paragraph({ children: [new TextRun({ text: "", font: FONT, size: 22 })] });

const h1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, font: FONT, size: 30, bold: true, color: ACCENT })],
  });

const h2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, font: FONT, size: 26, bold: true, color: BLACK })],
  });

// Image helper. Figures are 300 dpi PNG; show ~6 inches wide (max contenido US Letter ≈ 9360 DXA = 6.5 in)
function figure(filename, caption, widthPx = 540, aspect = 0.55) {
  const file = path.join(FIG, filename);
  if (!fs.existsSync(file)) {
    return [new Paragraph({ children: [new TextRun({ text: `[FALTA ${filename}]`, font: FONT, size: 20, color: "B23A48", italics: true })] })];
  }
  const data = fs.readFileSync(file);
  const heightPx = Math.round(widthPx * aspect);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 60 },
      children: [new ImageRun({
        type: "png",
        data,
        transformation: { width: widthPx, height: heightPx },
        altText: { title: caption, description: caption, name: filename },
      })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
      children: [new TextRun({ text: caption, font: FONT, size: 19, italics: true })],
    }),
  ];
}

function specRow(label, value) {
  return new TableRow({
    children: [
      new TableCell({
        borders: CELL_BORDERS, width: { size: 3000, type: WidthType.DXA }, margins: CELL_MARGINS,
        children: [new Paragraph({ children: [new TextRun({ text: label, font: FONT, size: 21, bold: true })] })],
      }),
      new TableCell({
        borders: CELL_BORDERS, width: { size: 6360, type: WidthType.DXA }, margins: CELL_MARGINS,
        children: [new Paragraph({ children: [new TextRun({ text: value, font: FONT, size: 21 })] })],
      }),
    ],
  });
}

function row3(c1, c2, c3, isHeader = false) {
  const mk = (t) => new TableCell({
    borders: CELL_BORDERS, width: { size: 3120, type: WidthType.DXA }, margins: CELL_MARGINS,
    shading: isHeader ? { fill: "F0F0F0", type: ShadingType.CLEAR } : undefined,
    children: [new Paragraph({ children: [new TextRun({ text: t, font: FONT, size: 21, bold: isHeader })] })],
  });
  return new TableRow({ children: [mk(c1), mk(c2), mk(c3)] });
}

const fmt = (n, decimals = 0) => Number(n).toLocaleString("es-MX", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

// --- content ----------------------------------------------------------------
const TITLE_ES = "HidroXAI-MX: un dataset hidroclimático reproducible para cuencas piloto de México (CONAGUA-SIH e INEGI) con modelos digitales de elevación y delineación de subcuencas";
const TITLE_EN = "HidroXAI-MX: a reproducible hydroclimatic dataset for Mexican pilot basins (CONAGUA-SIH and INEGI) with per-basin digital elevation models and watershed delineations";

const M = METRICS;
const N_HID = M.dataset.hidrometricas.n_estaciones;
const N_CLI = M.dataset.climatologicas.n_estaciones;
const N_HID_60 = M.fig1.estaciones_ge_60pct;
const N_HID_80 = M.fig1.estaciones_ge_80pct;
const N_SUB = M.fig8.subcuencas_total;
const SUB_BY = M.fig8.subcuencas_por_cuenca;
const N_SEL = M.fig8.n_estaciones_seleccionadas;
const ROWS_HID = M.dataset.hidrometricas.n_filas;
const ROWS_CLI = M.dataset.climatologicas.n_filas;
const LAG = M.fig7.lag_max_correlacion_dias;
const CORR = M.fig7.correlacion_max;
const PCT_OK = M.fig3.pct.ok;
const PCT_IMP = M.fig3.pct.imputado;
const PCT_OUT = M.fig3.pct.outlier;
const COV_MEAN = M.fig1.cobertura_media_pct;

const children = [];

// Portada
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [new TextRun({ text: "Data Article — borrador para Data in Brief (Elsevier)", font: FONT, size: 20, italics: true, color: "555555" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
  children: [new TextRun({ text: TITLE_ES, font: FONT, size: 30, bold: true, color: ACCENT })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: [new TextRun({ text: TITLE_EN, font: FONT, size: 22, italics: true })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "Daniel Sánchez Ruiz a,*", font: FONT, size: 22, bold: true })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "a Instituto Politécnico Nacional (IPN), Unidad Profesional Interdisciplinaria de Ingeniería campus Tlaxcala (UPIIT). * Correspondencia: pantrok@gmail.com", font: FONT, size: 20, italics: true })] }));
children.push(new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.JUSTIFIED,
  shading: { fill: "FFF6E6", type: ShadingType.CLEAR },
  children: [new TextRun({ text: "AVISO (no para envío): borrador con figuras y métricas reales generadas a partir del snapshot actual del repositorio hidroxai-mx (commit reciente, dataset descargado manualmente desde sih.conagua.gob.mx). Único pendiente no técnico: depositar el snapshot v2026.06 en Zenodo y reemplazar el placeholder de DOI en la Specifications Table.", font: FONT, size: 20, italics: true })] }));

// Abstract
children.push(h1("Abstract"));
children.push(p(
  `HidroXAI-MX es un dataset hidroclimático reproducible centrado en cuatro cuencas piloto de México: Cutzamala, Lerma–Santiago (subdividida en tres subcuencas operativas: Lerma Alto, Bajío y Santiago), Pánuco y Alta del Balsas. La versión publicada integra ${fmt(N_HID)} estaciones hidrométricas y ${fmt(N_CLI)} estaciones climatológicas del Sistema de Información Hidrológica (SIH) de la Comisión Nacional del Agua (CONAGUA), con ${fmt(ROWS_HID)} y ${fmt(ROWS_CLI)} observaciones diarias respectivamente; de éstas, ${N_HID_60} estaciones hidrométricas superan el 60 % de cobertura observada en el periodo 2010–2025 y ${N_HID_80} superan el 80 %. La cartografía hidrológica acompaña a las series: para cada cuenca se proveen un modelo digital de elevación recortado a partir del CEM 3.0 del Instituto Nacional de Estadística y Geografía (INEGI) y la delineación automática de ${N_SUB} subcuencas usando WhiteboxTools sobre las estaciones aforadas. Todo el ciclo —descarga, validación, esquema canónico, delineación, generación de features— se versiona con DVC sobre un remoto S3-compatible (Cloudflare R2) y se distribuye con licencia MIT (código) y CC BY 4.0 (datos derivados). El dataset es directamente reutilizable para pronóstico explicable de niveles hidrométricos, reglas difusas, análisis de sequía y planeación de recursos hídricos.`
));

// Specifications Table (EN)
children.push(h1("Specifications Table (in English, as required by the journal)"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3000, 6360],
  rows: [
    specRow("Subject", "Earth and Planetary Sciences"),
    specRow("Specific subject area", "Hydrology, hydroclimatic monitoring, watershed delineation, open data curation for explainable forecasting"),
    specRow("Type of data", "Tables (Apache Parquet, partitioned by year), CSV, GeoTIFF raster, GeoPackage, JSON provenance manifest, YAML configuration"),
    specRow("Data collection",
      "Daily streamflow and climate series were downloaded as direct per-station CSV from CONAGUA SIH (https://sih.conagua.gob.mx/basedatos/{Hidros|Climas}/<CLAVE>.csv) following the master catalogs of hydrometric and climatological stations. Digital elevation models were obtained per Mexican state from the INEGI Continuo de Elevaciones Mexicano 3.0 (CEM 3.0; https://www.inegi.org.mx/temas/relieve/continental/), mosaicked and clipped per basin. Watershed polygons were derived from the DEM with WhiteboxTools (fill → d8 pointer → flow accumulation → snap pour points → watershed)."),
    specRow("Data source location",
      "Mexico. Pilot basins: Cutzamala (Edo. de México / Michoacán / Guerrero), Lerma Alto (Toluca / Querétaro sur), Bajío (Guanajuato / Michoacán / Querétaro), Santiago (Jalisco / Nayarit), Pánuco (S. L. P. / Tamaulipas / Hidalgo / Veracruz / Querétaro / Puebla / Tlaxcala), Alta del Balsas (Morelos / Puebla / Tlaxcala / Edo. de México)."),
    specRow("Data accessibility",
      "Repository: GitHub — https://github.com/pantrok/hidroxai-mx (code, dvc.yaml, dvc.lock, configuration). DVC remote: Cloudflare R2 (S3-compatible), pulled with `dvc pull`. Snapshot DOI: TO BE ASSIGNED (Zenodo deposit pending). Licenses: code MIT, derived data CC BY 4.0, attribution to CONAGUA, SMN and INEGI required."),
    specRow("Related research article",
      "Sánchez Ruiz, D. et al. (in preparation). Explainable forecasting of streamflow gauge levels and local climate in Mexico via temporal deep learning and fuzzy rules over CONAGUA and Servicio Meteorológico Nacional open data. IND-2026-0335, IPN — UPIIT, PICDT 2026."),
  ],
}));
children.push(blank());

// Value of the Data
children.push(h1("Value of the Data"));
[
  `Primer dataset hidroclimático nacional reproducible end-to-end para México centrado en cuencas críticas para la política pública del agua: Cutzamala (≈ 30 % del abasto de la ZMVM) y Alta del Balsas (zona de estudio del IPN-UPIIT, históricamente subestudiada).`,
  `Volumen sustantivo: ${fmt(ROWS_HID)} observaciones hidrométricas diarias (${N_HID} estaciones) y ${fmt(ROWS_CLI)} observaciones climatológicas (${N_CLI} estaciones), con ${N_HID_60} estaciones hidro que superan el umbral piloto de 60 % de cobertura en 2010–2025.`,
  `Integra, en un solo flujo versionado, las series temporales del SIH, los modelos digitales de elevación (CEM 3.0 de INEGI) recortados por cuenca y la delineación automática de ${N_SUB} subcuencas con WhiteboxTools, lista para alimentar modelos hidrológicos distribuidos o conceptuales.`,
  `Cada observación trae banderas de calidad (0 = ok, 1 = imputado por interpolación corta en huecos < 7 días, 2 = outlier marcado y conservado) y procedencia (SHA-256, URL, fecha de descarga) para auditoría y reproducibilidad. En el snapshot publicado, ${PCT_OK.toFixed(2)} % de observaciones son originales, ${PCT_IMP.toFixed(2)} % son imputadas y ${PCT_OUT.toFixed(3)} % se marcaron como outliers físicos.`,
  `Es directamente reutilizable para: (a) pronóstico explicable de niveles hidrométricos con deep learning; (b) sistemas de reglas difusas para alerta temprana; (c) análisis de sequía con índices SPI/SPEI; (d) estudios de cambio climático regional; (e) entrenamiento de líneas base reproducibles en hidroinformática.`,
  `Pipeline ampliable: el esquema canónico (pandera), la limpieza, el guardarraíl de almacenamiento (≤ 9.5 GB) y la convención DVC permiten a terceros añadir más cuencas o fuentes (BANDAS, CLICOM, SMN) sin romper la trazabilidad.`,
].forEach((t) => children.push(bullet(t)));

// Background
children.push(h1("Background"));
children.push(p(
  "México es uno de los países con mayor estrés hídrico estructural del continente. El sistema Cutzamala —que aporta aproximadamente 30 % del agua potable de la Zona Metropolitana del Valle de México (ZMVM)— ha operado de forma recurrente por debajo del 40 % de su capacidad útil en los últimos años, y eventos de sequía severa (2011, 2021, 2023–2024) han disparado restricciones de abasto, conflictos sociales y costos de bombeo. A pesar de ello, los datos hidroclimáticos abiertos del país siguen siendo fragmentarios: la Comisión Nacional del Agua (CONAGUA) publica catálogos y series del Sistema de Información Hidrológica (SIH) y archivos históricos en BANDAS; el Instituto Nacional de Estadística y Geografía (INEGI) distribuye modelos digitales de elevación; el Servicio Meteorológico Nacional (SMN) y el archivo CLICOM (CICESE) ofrecen series climatológicas; pero ninguno publica un dataset curado, validado y versionado, listo para análisis o aprendizaje automático."
));
children.push(p(
  "HidroXAI-MX se desarrolla en el marco del proyecto IND-2026-0335 (Convocatoria PICDT 2026 del IPN), cuyo Objetivo Específico 1 (OE1) es justamente construir, validar y publicar el dataset que aquí se describe. Los objetivos subsecuentes (OE2 a OE6) abordan modelado profundo, explicabilidad (XAI), reglas difusas y un panel operativo; el dataset publicado en este artículo es la base reproducible sobre la que se construyen esos productos. La pertenencia institucional al IPN-UPIIT, situada en Tlaxcala dentro de la cuenca Alta del Balsas, justifica además el énfasis en esta cuenca de cabecera, históricamente subestudiada respecto a Cutzamala y Lerma-Santiago."
));

// Data Description
children.push(h1("Data Description"));
children.push(p("El dataset se distribuye en cuatro zonas dentro del repositorio:"));
[
  "data/raw/sih/: catálogos maestros del SIH para estaciones hidrométricas y climatológicas (CSV originales).",
  "data/raw/sih_series/{hidrometricas|climatologicas}/<CLAVE>.csv: series temporales diarias por estación, tal como fueron descargadas (codificación Latin-1).",
  "data/raw/inegi/cem_<cuenca>.tif: modelos digitales de elevación recortados por cuenca (30 m por defecto, 15 m para Alta del Balsas).",
  "data/processed/: tablas canónicas en Parquet particionado por año, listas de estaciones seleccionadas y extendidas, y la cartografía de subcuencas (GeoPackage por cuenca).",
  "data/features/feature_table.parquet: tabla compacta lista para modelado (rezagos, medias móviles, normalización por estación), sin tensores deslizantes.",
  "data/raw/_manifest.json: procedencia de cada archivo descargado (URL, SHA-256, bytes, marca de tiempo UTC).",
].forEach((t) => children.push(bullet(t)));

children.push(h2("Inventario por cuenca piloto"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3120, 3120, 3120],
  rows: [
    row3("Cuenca", "Estaciones hidro en el bbox (sel ≥60%)", "Subcuencas delineadas", true),
    row3("Cutzamala", "8", String(SUB_BY["Cutzamala"])),
    row3("Lerma Alto", "9", String(SUB_BY["Lerma Alto"])),
    row3("Bajío", "26", String(SUB_BY["Bajío"])),
    row3("Santiago", "13", String(SUB_BY["Santiago"])),
    row3("Pánuco", "52", String(SUB_BY["Pánuco"])),
    row3("Alta del Balsas", "17", String(SUB_BY["Alta del Balsas"])),
    row3("Total (a)", `${N_SEL} únicas`, String(N_SUB)),
  ],
}));
children.push(p("(a) La suma por cuenca excede las estaciones únicas porque algunas caen en bboxes contiguos (overlap geográfico, sobre todo entre Bajío y Pánuco). La asignación final se hace por proximidad al pour point durante la delineación.", { italics: true, size: 20 }));

children.push(h2("Esquema canónico de las series"));
children.push(p("Cada fila de las tablas Parquet representa una observación diaria con las siguientes columnas (validadas con pandera):"));
[
  "clave_estacion (string): clave SIH alfanumérica (1–8 caracteres, ceros preservados).",
  "fecha (datetime64[ns]): fecha local sin componente horaria.",
  "gasto_medio_m3s (float, ≥ 0): caudal medio diario para series hidrométricas.",
  "nivel_m (float, opcional): nivel del agua sobre referencia local.",
  "precip_mm (float, ≥ 0): precipitación acumulada del día (series climatológicas).",
  "tmax_c, tmin_c, tmed_c (float): temperaturas extremas y media diaria.",
  "evap_mm (float, ≥ 0): evaporación diaria reportada por la estación.",
  "fuente (categoría: SIH, BANDAS, CLICOM, EMAS): origen de la observación; en este snapshot todas son SIH.",
  "calidad (entero {0,1,2}): 0 = original, 1 = imputado por interpolación corta (huecos < 7 días, cúbica con fallback a lineal), 2 = outlier físico marcado y conservado.",
].forEach((t) => children.push(bullet(t)));

// ==== FIGURAS REALES EMBEBIDAS ====
children.push(h2("Figuras de validación (generadas a 300 DPI desde el snapshot publicado)"));

children.push(...figure(
  "fig1_inventario_cobertura.png",
  `Fig. 1. (Izq.) Inventario de las ${N_HID} estaciones hidrométricas por región hidrológica: RH 12 = ${M.fig1.inventario_por_rh["12"]}, RH 18 = ${M.fig1.inventario_por_rh["18"]}, RH 26 = ${M.fig1.inventario_por_rh["26"]}. (Der.) Distribución de cobertura observada 2010–2025; las líneas marcan los umbrales operativos (60 % hidro, 80 % clima). La cobertura media nacional es ${COV_MEAN.toFixed(1)} %; ${N_HID_60} estaciones superan el 60 % y ${N_HID_80} el 80 %.`,
));

children.push(...figure(
  "fig2_descriptiva.png",
  `Fig. 2. Distribución del gasto medio diario por región hidrológica (escala logarítmica). Estadísticos globales: mediana ${M.fig2.describe_global["50%"].toFixed(2)} m³/s, p75 ${M.fig2.describe_global["75%"].toFixed(2)} m³/s, máximo ${fmt(M.fig2.describe_global.max, 0)} m³/s. Temporada lluviosa (mayo–octubre) mediana ${M.fig2.por_temporada.median.lluviosa.toFixed(2)} m³/s vs. seca ${M.fig2.por_temporada.median.seca.toFixed(2)} m³/s.`,
));

children.push(...figure(
  "fig3_calidad.png",
  `Fig. 3. Distribución de banderas de calidad sobre las ${fmt(M.fig3.n.ok + M.fig3.n.imputado + M.fig3.n.outlier)} observaciones hidrométricas: ${PCT_OK.toFixed(2)} % originales, ${PCT_IMP.toFixed(2)} % imputadas por interpolación corta y ${PCT_OUT.toFixed(3)} % marcadas como outliers físicos (conservadas para análisis XAI).`,
));

children.push(...figure(
  "fig5_mapa.png",
  "Fig. 5. Coherencia espacial: ubicación de las estaciones hidrométricas geolocalizadas por región hidrológica. La separación geográfica entre RH 12 (Lerma-Santiago, occidente), RH 18 (Balsas, centro-sur) y RH 26 (Pánuco, oriente) es consistente con el catálogo oficial.",
));

children.push(...figure(
  "fig6_temporal.png",
  "Fig. 6. (Izq.) Climatología mensual del gasto medio (media ± 1σ): pico en septiembre, mínimos en abril–mayo, consistente con el régimen de monzón mexicano. (Der.) Serie de medias anuales 1922–2025 con líneas punteadas marcando las sequías severas conocidas (2011, 2021, 2023); los mínimos del dataset son temporalmente coherentes con esos eventos.",
));

children.push(...figure(
  "fig7_precip_gasto.png",
  `Fig. 7. Correlación rezagada entre precipitación (promedio nacional diario, ${N_CLI} estaciones) y gasto medio (promedio nacional diario, ${N_HID} estaciones). La correlación máxima ocurre a un rezago de ${LAG} días con r = ${CORR.toFixed(3)} (n = ${fmt(M.fig7.n_fechas_comunes)} fechas comunes), físicamente compatible con el tiempo de tránsito agregado precipitación → escorrentía en cuencas medianas mexicanas.`,
  540, 0.45,
));

children.push(...figure(
  "fig8_cuencas_subcuencas.png",
  `Fig. 8. Cuencas piloto y subcuencas delineadas con WhiteboxTools (${N_SUB} subcuencas en total): Cutzamala (${SUB_BY.Cutzamala}), Lerma Alto (${SUB_BY["Lerma Alto"]}), Bajío (${SUB_BY["Bajío"]}), Santiago (${SUB_BY.Santiago}), Pánuco (${SUB_BY["Pánuco"]}) y Alta del Balsas (${SUB_BY["Alta del Balsas"]}). Las líneas continuas son los contornos de subcuenca derivados del CEM; las líneas punteadas los bboxes curados en conf/cuencas_piloto.yaml; los puntos negros las ${N_SEL} estaciones hidrométricas con cobertura ≥ 60 % usadas como pour points.`,
  580, 0.85,
));

// Methods
children.push(h1("Experimental Design, Materials and Methods"));
children.push(p(
  "El pipeline se ejecuta como una secuencia de scripts numerados, cada uno con responsabilidad única y reproducible mediante DVC. Las dos etapas oficiales son: Etapa 1 (prueba, ≈ 13 MB versionados, 5 estaciones por tipo) y Etapa 2 (consolidación, ≈ 2.4 GB versionados, las 4 cuencas piloto con la subdivisión de Lerma-Santiago). El dataset distribuido corresponde al cierre de Etapa 2."
));

children.push(h2("Paso 01 — Descarga de catálogos maestros del SIH"));
children.push(p(
  "Se descargan los catálogos públicos de estaciones hidrométricas (n = 1 189) y climatológicas (n = 7 499) directamente desde el SIH como CSV, sin scrapeo HTML. Se normalizan los encabezados (RH, número de región hidrológica, latitud, longitud, altitud, estado, municipio, cuenca) y se conserva el archivo crudo bajo data/raw/sih/."
));

children.push(h2("Paso 05 — Selección de estaciones candidatas y refinamiento"));
children.push(p(
  `Primer pase (sin --refine): el script filtra el catálogo por las regiones hidrológicas piloto (12 Lerma-Santiago, 18 Balsas, 26 Pánuco), generando 550 candidatas hidrométricas y 2 731 climatológicas. Segundo pase (--refine, tras descargar las series): se calcula la cobertura observada por estación dentro del periodo 2010–2025 y se aplica un umbral diferenciado: 60 % para hidrométricas y 80 % para climatológicas. Las estaciones hidrométricas con cobertura intermedia (30 %–60 %) se conservan en un archivo extendido para estudios de sensibilidad y reconstrucción con vecinos. Para cada estación hidrométrica seleccionada se calculan los k = 3 vecinos climatológicos más cercanos por distancia haversine. Resultado del snapshot publicado: ${N_HID_60} estaciones hidrométricas en el conjunto principal (≥ 60 %), ${N_HID_80} en el conjunto estricto (≥ 80 %).`
));

children.push(h2("Paso 03 — Descarga de series temporales por estación"));
children.push(p(
  "Las series se descargan desde los endpoints directos del SIH (`/basedatos/{Hidros|Climas}/<CLAVE>.csv`). El descargador implementa un ThreadPoolExecutor configurable (variable HIDROXAI_DL_WORKERS) y un retardo opcional entre descargas (HIDROXAI_DL_DELAY_S) para no activar el firewall de aplicación (Imperva Incapsula) que protege al portal del SIH. Cada descarga registra en `_manifest.json` el hash SHA-256, los bytes y la fecha UTC, garantizando trazabilidad."
));

children.push(h2("Paso 04 — Esquema canónico y persistencia Parquet"));
children.push(p(
  "Las series crudas se leen con un parser flexible que reconoce dos variantes de encabezado (`Fecha,…` y `Estacion,Fecha,…`) y dos formatos de fecha (YYYY/MM/DD y YYYY-MM-DD). Se aplica un control de calidad por estación: reemplazo de centinelas (-9999) por NaN, marcado de outliers físicos (calidad = 2, conservados), e imputación de huecos cortos (< 7 días) mediante interpolación cúbica con fallback automático a lineal cuando la serie tiene menos de cuatro puntos válidos consecutivos. El resultado se valida con pandera y se persiste como Parquet particionado por año."
));

children.push(h2("Paso 06b — Construcción del CEM por cuenca"));
children.push(p(
  "El portal CEM 3.0 de INEGI no permite descargas por bounding box arbitrario sin selección manual; entrega los modelos por entidad federativa. El script `06b_build_cem_per_basin.py` (a) lista los TIFFs disponibles en `data/scratch/<resolución>m/`, (b) selecciona los que intersectan el bbox curado de cada cuenca en `cuencas_piloto.yaml`, (c) hace mosaico con `rasterio.merge`, (d) recorta al bbox con `rasterio.mask` usando un `MemoryFile` intermedio (evita bloqueos de archivo bajo Windows + Google Drive), y (e) cuando la resolución de los tiles supera la solicitada (caso típico del snapshot: el portal sólo entregó 15 m mientras las cuencas grandes piden 30 m), aplica un remuestreo con `rasterio.warp.reproject` y `Resampling.average`."
));

children.push(h2("Paso 06 — Delineación automática de subcuencas"));
children.push(p(
  `Para cada cuenca, las estaciones hidrométricas seleccionadas dentro del bbox se usan como puntos de aforo, se ejecuta la cadena WhiteboxTools fill_depressions → d8_pointer → flow_accumulation → extract_streams → snap_pour_points → watershed y se exporta el resultado como GeoPackage con atributos de área (km²), elevación media y pendiente media. Para evitar agotar la RAM (referencia: 16 GB), la cuenca Lerma–Santiago se subdividió en tres sub-cuencas piloto cuyos bboxes individuales caben en memoria a 30 m. La corrida produjo ${N_SUB} subcuencas (ver Fig. 8 y Tabla de inventario).`
));

children.push(h2("Paso 07 — Tabla de features"));
children.push(p(
  "Une cada estación hidrométrica con la precipitación de sus k vecinos climatológicos mediante inverse distance weighting (IDW, potencia 2), genera rezagos a 1, 3, 7, 14 y 30 días, medias móviles y normaliza por estación, produciendo `data/features/feature_table.parquet`. Los tensores deslizantes en `.npz` —que con 200 estaciones rondan los 9 GB— no se materializan por defecto: se regeneran on-the-fly al entrenar, evitando inflar el remoto DVC."
));

children.push(h2("Paso 08 — Guardarraíl de almacenamiento"));
children.push(p(
  "Antes de cada `dvc push`, este script suma el tamaño de `data/{raw,processed,features}` excluyendo cualquier `.npz`. Si supera el tope configurable (R2_CAP_GB, por defecto 9.5 GB), aborta con código de salida 1, protegiendo la cuota gratuita del bucket R2."
));

children.push(h2("Versionado y reproducibilidad"));
children.push(p("Pipeline declarado en `dvc.yaml` (8 stages) y `dvc.lock` con hashes md5 por output. Distribución física con DVC sobre Cloudflare R2 (S3-compatible). Para reproducir el snapshot publicado en una máquina nueva:"));
code("git clone https://github.com/pantrok/hidroxai-mx.git");
code("cd hidroxai-mx && pip install -e \".[dev,geo]\"");
code("dvc pull   # descarga ~2.4 GB desde R2 (requiere credenciales)");

// Limitations
children.push(h1("Limitations"));
[
  "Fuente única. Este snapshot integra únicamente el SIH de CONAGUA. La validación cruzada con BANDAS (archivos .mdb históricos), CLICOM (CICESE) y SMN (EMAS) se declara como trabajo futuro (ver §Future Work).",
  `Cobertura hidrométrica heterogénea. La cobertura media de las ${N_HID} estaciones hidrométricas es ${COV_MEAN.toFixed(1)} % en el periodo 2010–2025: muchas series terminan en 2021 o presentan grandes huecos. Para no excluir cuencas críticas, se publicó un conjunto extendido (30 %–60 %) para análisis de sensibilidad y los modelos deben entrenarse sólo sobre ventanas válidas.`,
  "Resolución efectiva del CEM. El portal INEGI sólo permitió descargar los tiles a 15 m; para cuencas grandes (Lerma medio, Pánuco, Santiago) el procesamiento de delineación se hizo tras un remuestreo a 30 m por restricción de memoria. Esto reduce el detalle hidrológico fino en zonas de cabecera.",
  "Errores del catálogo SIH. Cuatro estaciones hidrométricas (entre ellas B18558 ABASOLO, listada en Morelos con coordenadas correspondientes a Tijuana) presentan inconsistencias entre estado, región hidrológica y latitud/longitud reportadas. Se documentan en este artículo y se descartan automáticamente al filtrar por el bbox geográfico curado de cada cuenca.",
  "Restricciones del proveedor. El portal SIH usa el WAF Imperva Incapsula con un JavaScript challenge: descargas concurrentes > 4 hilos disparan bloqueos por IP. El descargador documenta esto y permite ajustar paralelismo y delay; usuarios masivos pueden necesitar mirror local o sesión de navegador.",
  "Sin DOI todavía. El snapshot v2026.06 está pendiente de depósito en Zenodo al cierre de este borrador.",
].forEach((t) => children.push(bullet(t)));

// Future Work
children.push(h1("Future Work"));
children.push(p(
  "El proyecto IND-2026-0335 incluye, además del dataset descrito en este artículo, los siguientes objetivos específicos (OE2–OE6) que se publicarán de forma separada y que extenderán o consumirán este snapshot:"
));
[
  "Validación cruzada multi-fuente. Integración programática de BANDAS (CONAGUA, archivos .mdb), CLICOM (CICESE) y la red EMAS del SMN para validar correlación y sesgo en estaciones comunes. Esto convertirá la actual §4 «Consistencia entre fuentes» (hoy vacía por diseño) en una sección con métricas concretas y reforzará la confiabilidad declarada del snapshot.",
  "OE2 — Modelado profundo. Líneas base y modelos temporales (LSTM, Temporal Fusion Transformer) entrenados sobre la tabla de features, con la subdivisión Lerma Alto / Bajío / Santiago como caso multi-cuenca.",
  "OE3 — Explicabilidad (XAI). Atribución por SHAP, integrated gradients y mecanismos de atención sobre los pronósticos de nivel hidrométrico y precipitación a corto plazo.",
  "OE4 — Reglas difusas. Sistema híbrido neuro-difuso para alerta temprana ante eventos extremos, calibrado sobre las sequías históricas verificadas (2011, 2021, 2023) ya visibles en la Fig. 6.",
  "OE5–OE6 — Panel operativo y evaluación. Dashboard reproducible y evaluación en operación piloto en colaboración con autoridades del agua y CONAGUA-OCAVM.",
  "Ampliación de cobertura geográfica. Aplicar el mismo pipeline a las cuencas restantes (RH no piloto), una vez consolidada la metodología; el guardarraíl de 9.5 GB del paso 08 deja margen para ese crecimiento.",
].forEach((t) => children.push(bullet(t)));

// Ethics
children.push(h1("Ethics Statement"));
children.push(p(
  "Este estudio no involucra sujetos humanos, animales ni datos provenientes de redes sociales. Todas las fuentes utilizadas son datos públicos abiertos publicados por dependencias del Gobierno de México (CONAGUA e INEGI) bajo sus respectivos términos de uso, los cuales se honran mediante atribución obligatoria en la licencia derivada (CC BY 4.0)."
));

// CRediT
children.push(h1("CRediT Author Statement"));
children.push(p("Daniel Sánchez Ruiz: Conceptualización, Metodología, Software, Curación de datos, Redacción — borrador original, Redacción — revisión y edición, Visualización, Administración del proyecto, Obtención de financiamiento.", { italics: true }));
children.push(p("PENDIENTE: completar coautorías y roles del equipo IPN/UPIIT que hayan participado en validación, ingeniería de datos o curación.", { italics: true, size: 20, color: "555555" }));

// Data Availability
children.push(h1("Data Availability"));
children.push(p("Código: https://github.com/pantrok/hidroxai-mx (MIT). Snapshot de datos: a depositar en Zenodo (CC BY 4.0); en tanto se asigna el DOI, los datos están disponibles para revisores mediante el remoto DVC (Cloudflare R2) bajo solicitud al autor de correspondencia."));

// Acknowledgements
children.push(h1("Acknowledgements"));
children.push(p(
  "Este trabajo forma parte del proyecto IND-2026-0335 financiado por la Secretaría de Investigación y Posgrado del Instituto Politécnico Nacional, dentro de la Convocatoria de Proyectos de Investigación Científica y Desarrollo Tecnológico 2026 (PICDT 2026). Se agradece a la Comisión Nacional del Agua (CONAGUA), al Servicio Meteorológico Nacional (SMN) y al Instituto Nacional de Estadística y Geografía (INEGI) por mantener los datos públicos sobre los que se construye este dataset, así como al equipo de la Unidad Profesional Interdisciplinaria de Ingeniería campus Tlaxcala (UPIIT) por el espacio académico para este desarrollo."
));

// References placeholder
children.push(h1("Referencias (placeholder)"));
children.push(p(
  "Mínimos sugeridos antes de envío: (i) documentación oficial del SIH y BANDAS; (ii) manual del CEM 3.0 de INEGI; (iii) WhiteboxTools (Lindsay 2016); (iv) pandera para validación de esquemas; (v) DVC + Cloudflare R2; (vi) antecedentes recientes de deep learning en hidrología latinoamericana; (vii) literatura sobre el Sistema Cutzamala y su crisis hídrica.",
  { italics: true, color: "555555" }
));

// Análisis de suficiencia interno
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1("Análisis de suficiencia (uso interno IPN — no enviar a la revista)"));
children.push(p("Esta sección no forma parte del manuscrito a enviar; sirve de control de calidad interno tras incorporar las figuras y métricas reales del snapshot."));

children.push(h2("Cubierto"));
[
  `Volumen y diversidad. ${fmt(ROWS_HID)} observaciones hidrométricas (${N_HID} estaciones) + ${fmt(ROWS_CLI)} climatológicas (${N_CLI} estaciones) son comparables o superiores a varios datasets publicados recientemente en Data in Brief.`,
  "Trazabilidad reproducible. Manifest JSON con SHA-256 por archivo + DVC + dvc.lock + repo git público cumplen el criterio de “datos accesibles y reproducibles” de la revista.",
  "Metodología documentada. Las etapas 01–08 más 06b cubren descripción de fuentes, descarga, validación, limpieza, derivación de productos y guardarraíl de almacenamiento.",
  `Figuras a 300 DPI. Las ${Object.keys(M).filter(k => k.startsWith("fig")).length} figuras del data paper se generaron desde el snapshot real con scripts/09_make_report_figures.py y están embebidas en este borrador.`,
  `Mapa de cuencas y subcuencas (Fig. 8). Se añadió como figura nueva: muestra las 6 cuencas operativas con sus ${N_SUB} subcuencas delineadas y los ${N_SEL} pour points hidrométricos.`,
  `Validación física inicial. La correlación rezagada precipitación → gasto alcanza r = ${CORR.toFixed(3)} a ${LAG} días (Fig. 7), un comportamiento físicamente esperable.`,
].forEach((t) => children.push(bullet(t)));

children.push(h2("Pendientes no negociables (3) — solo bloquea el envío el #1"));
[
  "Zenodo. Depositar el snapshot v2026.06 y reemplazar el placeholder de DOI en la Specifications Table y en Data Availability.",
  "Completar coautores y roles CRediT (¿alguien del equipo UPIIT participa en validación, supervisión o curación?).",
  "Redactar la lista de referencias bibliográficas a partir del placeholder al final del manuscrito.",
].forEach((t) => children.push(bullet(t)));

children.push(h2("Mejoras deseables (no bloquean)"));
[
  "Validación cruzada con BANDAS/CLICOM/SMN — declarada como trabajo futuro pero quedaría más fuerte ejecutarla en al menos un subconjunto antes de envío.",
  `La cobertura media de ${COV_MEAN.toFixed(1)} % en el universo hidrométrico (${N_HID} estaciones) es baja porque incluye estaciones discontinuadas; podría reportarse también la cobertura restringida al conjunto seleccionado ≥ 60 % para complementar la Fig. 1.`,
  "Un notebook acompañante mínimo (al estilo del paper Urdu OCR) con un caso de uso reproducible (cargar parquet, filtrar una cuenca, graficar respuesta precip → gasto en una estación específica).",
].forEach((t) => children.push(bullet(t)));

children.push(h2("Recomendación"));
children.push(p(
  "El borrador con figuras reales está listo para revisión interna y, una vez cerrados los tres pendientes no negociables (especialmente el depósito en Zenodo con DOI), puede enviarse a Data in Brief sin trabajo metodológico adicional."
));

// --- Build doc --------------------------------------------------------------
const doc = new Document({
  creator: "HidroXAI-MX",
  title: TITLE_ES,
  description: "Borrador con figuras reales para Data in Brief",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: ACCENT },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: BLACK },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
    },
    children,
  }],
});

const out = path.join(REPO, "docs/manuscrito_data_in_brief_borrador.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("OK:", out, "(" + buf.length + " bytes)"); });

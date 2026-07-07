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
const TITLE_ES = "Hidro-MX: un dataset hidroclimático reproducible para cuencas piloto de México (CONAGUA-SIH e INEGI) con modelos digitales de elevación y delineación de subcuencas";
const TITLE_EN = "Hidro-MX: a reproducible hydroclimatic dataset for pilot basins in Mexico (CONAGUA-SIH and INEGI) with digital elevation models and sub-basin delineation";

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
  children: [new TextRun({ text: "Daniel Sánchez-Ruiz a,*, Cecilia Reyes-Peña a, Lauro Reyes-Cocoletzi a, Jesús García-Ramírez a, Eric Ramos-Aguilar a, Ricardo Ramos-Aguilar a", font: FONT, size: 22, bold: true })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "a Instituto Politécnico Nacional, Unidad Profesional Interdisciplinaria de Ingeniería Campus Tlaxcala (UPIIT), Tlaxcala, Tlax., México. * Corresponding author: dsanchezro@ipn.mx", font: FONT, size: 20, italics: true })] }));
children.push(new Paragraph({ spacing: { after: 200 }, alignment: AlignmentType.JUSTIFIED,
  shading: { fill: "FFF6E6", type: ShadingType.CLEAR },
  children: [new TextRun({ text: "AVISO (no para envío): esta versión del borrador incorpora las secciones DATA DESCRIPTION y EXPERIMENTAL DESIGN, MATERIALS AND METHODS reescritas siguiendo las instrucciones del template Data in Brief v.19 (no ofrecer background, interpretaciones o conclusiones en esas secciones) y completa el campo \"Instructions for accessing these data\" en la Specifications Table. Snapshot v2026.06 depositado en Zenodo con DOI 10.5281/zenodo.21231601 (público, sin registro). Pendientes no técnicos: cerrar el CRediT Author Statement y completar la lista final de referencias.", font: FONT, size: 20, italics: true })] }));

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
      "Repository name: HidroXAI-MX v2026.06 — a reproducible hydroclimatic dataset for Mexican pilot basins (CONAGUA-SIH and INEGI). Data identification number: 10.5281/zenodo.21231601. Direct URL to data: https://doi.org/10.5281/zenodo.21231601. Instructions for accessing these data: the deposit is publicly downloadable under CC BY 4.0 without registration. From the Zenodo record page, download HidroXAI-MX-v2026.06.zip (about 0.9 GB compressed, 3.2 GB uncompressed) and extract it; the archive expands into the folders raw/, processed/, features/, conf/ and ships with an English README.md, an English LICENSE-DATA.md, and manifest_zenodo.json with the SHA-256 hash and size of every archived file for integrity checks. Alternatively, clone the source-code repository https://github.com/pantrok/hidroxai-mx (MIT-licensed pipeline; `pip install -e \".[dev,geo]\"`) and run `dvc pull` to fetch the same snapshot from the Cloudflare R2 remote (S3-compatible; anonymous read requires no credentials for this deposit). Attribution to CONAGUA-SIH and INEGI-CEM 3.0 as primary sources is mandatory under the reused terms of use."),
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
children.push(p(
  "The dataset is distributed as a single Zenodo archive (HidroXAI-MX-v2026.06.zip) whose top-level layout mirrors the working repository. When uncompressed, it expands into four content folders (raw/, processed/, features/, conf/) plus three self-contained documentation files (README.md, LICENSE-DATA.md, manifest_zenodo.json). Table 1 summarises the folders and Table 2 summarises the columns of every tabular file. All CSV files are UTF-8 (the raw SIH files retain the provider's Latin-1 encoding); all Parquet directories are Apache Parquet (Snappy-compressed) partitioned by year using Hive-style keys (anio=YYYY/*.parquet); rasters are GeoTIFF (LZW-compressed); vector layers are OGC GeoPackage; configuration is YAML; provenance is JSON."
));
children.push(blank());

children.push(h2("Table 1. Folder layout of the archive"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2600, 6760],
  rows: [
    row3("Folder / file", "Content", "", true),
    row3("raw/sih/", `Master catalogs downloaded from the CONAGUA Hydrological Information System (SIH): catalogo_hidrometricas.csv (1,189 rows) and catalogo_climatologicas.csv (7,499 rows), plus _manifest.json listing the source URL, SHA-256 hash, size in bytes and UTC download timestamp for every raw file.`, ""),
    row3("raw/sih_series/hidrometricas/", `547 per-station daily CSVs named <KEY>.csv (Latin-1). Columns: Fecha (YYYY/MM/DD or YYYY-MM-DD), Gasto medio (m³/s), Nivel (m). Missing values encoded as "-" or empty.`, ""),
    row3("raw/sih_series/climatologicas/", `2,659 per-station daily CSVs named <KEY>.csv (Latin-1). Columns: Fecha, Precipitación (mm), Temperatura máxima/mínima/media (°C), Evaporación (mm).`, ""),
    row3("raw/inegi/", `Six per-basin digital elevation models (GeoTIFF, int16, EPSG:6362, LZW compression): cem_cutzamala.tif, cem_lerma_alto.tif, cem_bajio.tif, cem_santiago.tif, cem_panuco.tif at 30 m spatial resolution, and cem_alta_del_balsas.tif at 15 m.`, ""),
    row3("processed/", `Curated datasets ready for analysis (see Table 2): series_hidrometricas.parquet/, series_climatologicas.parquet/, estaciones_candidatas_*.csv, estaciones_seleccionadas_*.csv, estaciones_extendidas_hidrometricas.csv, cuencas/*.gpkg, reportes/*.png + metrics.json + cobertura_por_estacion.csv.`, ""),
    row3("features/", `feature_table.parquet — model-ready table with lags and rolling means per station (see Table 2).`, ""),
    row3("conf/cuencas_piloto.yaml", `Basin configuration: for each of the six operational basins (Cutzamala, Lerma Alto, Bajío, Santiago, Pánuco, Alta del Balsas), it stores the curated bounding box [min_lon, min_lat, max_lon, max_lat] in EPSG:4326, the reference hydrological region code, the target CEM resolution in metres and an optional priority label.`, ""),
    row3("README.md, LICENSE-DATA.md", `Auto-generated English README with the archive's layout, provenance and reuse instructions; CC BY 4.0 licence text with mandatory attribution to CONAGUA and INEGI.`, ""),
    row3("manifest_zenodo.json", `Machine-readable index listing every archived file with its relative path, byte size and SHA-256 hash for integrity verification.`, ""),
  ],
}));
children.push(blank());

children.push(h2("Table 2. Columns and units of the tabular files"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2800, 6560],
  rows: [
    row3("File", "Columns (name — type — units / valid range)", "", true),
    row3("series_hidrometricas.parquet",
      "clave_estacion — string (1–8 alphanumeric, leading zeros preserved). fecha — datetime64[ns] (local, no time-of-day). gasto_medio_m3s — float64 ≥ 0. nivel_m — float64 (station-referenced datum, may be missing). fuente — categorical {SIH, BANDAS, CLICOM, EMAS}; SIH in this deposit. calidad — int8 in {0, 1, 2} (0 = original observation; 1 = imputed by short-gap interpolation, gap < 7 days; 2 = physical outlier retained for auditability). anio — int32 (Hive partition key; not stored inside the row-group).", ""),
    row3("series_climatologicas.parquet",
      "clave_estacion — string. fecha — datetime64[ns]. precip_mm — float64 ≥ 0. tmax_c, tmin_c, tmed_c — float64 (°C). evap_mm — float64 ≥ 0. fuente, calidad, anio as above.", ""),
    row3("estaciones_candidatas_hidrometricas.csv (550 rows) / _climatologicas.csv (2,731 rows)",
      "clave — string. nombre — string. estado — string. municipio — string. region_hidrologica — string (SIH code). cuenca — string. latitud, longitud — float64 (WGS 84 decimal degrees). altitud — float64 (m a.s.l.).", ""),
    row3("estaciones_seleccionadas_hidrometricas.csv (108 rows) / _climatologicas.csv (415 rows)",
      "All columns from the candidate file plus: cobertura — float64 in [0, 1] (fraction of non-missing daily observations of the target variable within 2010-01-01…2025-12-31). vecinos_clima (hydrometric file only) — string, comma-separated list of the three closest climate station keys by haversine distance.", ""),
    row3("estaciones_extendidas_hidrometricas.csv (107 rows)",
      "Same schema as estaciones_seleccionadas_hidrometricas.csv, restricted to stations with 0.30 ≤ cobertura < 0.60. Column uso_recomendado = \"sensibilidad_reconstruccion\".", ""),
    row3("cuencas/<basin>.gpkg",
      "OGC GeoPackage; layer cuenca; polygon geometries (EPSG:6362). Attributes: area_km2 — float64; elevacion_media_m — float64; pendiente_media — float64 (dimensionless slope, tan θ); clave_estacion — string (pour-point station key).", ""),
    row3("feature_table.parquet (6,028,437 rows × 8 columns; 478 stations)",
      "clave_estacion, fecha, gasto_medio_m3s, calidad as in series_hidrometricas.parquet, plus per-station lagged and rolling-mean features: gasto_medio_m3s_lag1, _lag3, _lag7, _lag14, _lag30 (float64, m³/s at t − k days); gasto_medio_m3s_ma7, _ma30 (float64, m³/s moving averages).", ""),
    row3("reportes/cobertura_por_estacion.csv",
      "clave_estacion — string. n_obs — int64 (non-missing days). dias_periodo — int64 (target-window length, days). cobertura — float64 in [0, 1]. inicio, fin — datetime64[ns] (first/last observation).", ""),
    row3("reportes/metrics.json",
      "JSON document with sub-objects fig1…fig8 mirroring the numerical summaries used to caption Figs. 1–8 (station counts, coverage percentiles, quality-flag counts, monthly climatology, annual means, lag/correlation of the precipitation–discharge relationship, sub-basin counts per basin).", ""),
    row3("cuencas_piloto.yaml",
      "Fields per basin: nombre — string. region_hidrologica — int. bbox — [min_lon, min_lat, max_lon, max_lat] (EPSG:4326). cem_resolucion_m — int (m). prioridad — int. Optional nota — string (short annotation).", ""),
  ],
}));
children.push(blank());

children.push(h2("Table 3. Station counts per basin bounding box"));
children.push(p("Stations are assigned to a basin by geometric containment in the curated bbox (conf/cuencas_piloto.yaml). Sub-basin polygons per basin are the outputs of the WhiteboxTools delineation described in §4.7."));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3120, 3120, 3120],
  rows: [
    row3("Basin", "Hydrometric stations ≥60% inside bbox", "Sub-basin polygons", true),
    row3("Cutzamala", "8", String(SUB_BY["Cutzamala"])),
    row3("Lerma Alto", "9", String(SUB_BY["Lerma Alto"])),
    row3("Bajío", "26", String(SUB_BY["Bajío"])),
    row3("Santiago", "13", String(SUB_BY["Santiago"])),
    row3("Pánuco", "52", String(SUB_BY["Pánuco"])),
    row3("Alta del Balsas", "17", String(SUB_BY["Alta del Balsas"])),
    row3("Total (unique)", `${N_SEL}`, String(N_SUB)),
  ],
}));
children.push(p("The sum by basin exceeds the number of unique selected stations because a small number of stations lie in the overlap between contiguous bboxes (Bajío/Pánuco); each station is then assigned to a single sub-basin by proximity to the snapped pour point during delineation.", { italics: true, size: 20 }));
children.push(blank());

// ==== FIGURAS REALES EMBEBIDAS ====
children.push(h2("Figures included in reportes/"));

children.push(...figure(
  "fig1_inventario_cobertura.png",
  `Fig. 1. Left: number of hydrometric stations per hydrological region among the ${N_HID} stations in series_hidrometricas.parquet (RH 12 = ${M.fig1.inventario_por_rh["12"]}, RH 18 = ${M.fig1.inventario_por_rh["18"]}, RH 26 = ${M.fig1.inventario_por_rh["26"]}). Right: histogram of the coverage of gasto_medio_m3s per station over 2010-01-01…2025-12-31. Vertical dashed lines mark the operational thresholds (60% for hydrometric selection, 80% for climatological selection). Mean coverage across all stations = ${COV_MEAN.toFixed(1)}%; ${N_HID_60} stations meet the 60% cut-off; ${N_HID_80} meet 80%.`,
));

children.push(...figure(
  "fig2_descriptiva.png",
  `Fig. 2. Boxplot of the daily gasto_medio_m3s values in series_hidrometricas.parquet grouped by hydrological region (RH 12, 18, 26); y-axis is on a base-10 log scale. Sample statistics of the pooled series: median = ${M.fig2.describe_global["50%"].toFixed(2)} m³/s, third quartile = ${M.fig2.describe_global["75%"].toFixed(2)} m³/s, maximum = ${fmt(M.fig2.describe_global.max, 0)} m³/s. Median value in the wet season (May–October) = ${M.fig2.por_temporada.median.lluviosa.toFixed(2)} m³/s; dry season = ${M.fig2.por_temporada.median.seca.toFixed(2)} m³/s.`,
));

children.push(...figure(
  "fig3_calidad.png",
  `Fig. 3. Counts and percentages of the calidad flag over ${fmt(M.fig3.n.ok + M.fig3.n.imputado + M.fig3.n.outlier)} hydrometric daily observations: ${PCT_OK.toFixed(2)}% flagged 0 (original), ${PCT_IMP.toFixed(2)}% flagged 1 (imputed by short-gap interpolation, gap < 7 days), and ${PCT_OUT.toFixed(3)}% flagged 2 (physical outliers retained in the archive).`,
));

children.push(...figure(
  "fig5_mapa.png",
  "Fig. 5. Latitude–longitude scatter of the geolocated hydrometric stations recorded in estaciones_seleccionadas_hidrometricas.csv, coloured by the reported hydrological region (RH 12, 18, 26). Point counts per region are given in the legend.",
));

children.push(...figure(
  "fig6_temporal.png",
  "Fig. 6. Left: monthly climatology of gasto_medio_m3s aggregated over all hydrometric stations (mean ± 1σ); x-axis month 1–12. Right: annual mean of gasto_medio_m3s from 1922 to 2025; vertical dotted lines mark the years 2011, 2021 and 2023 for reference. Numerical values are stored in reportes/metrics.json under fig6.climatologia_mensual and fig6.media_anual.",
));

children.push(...figure(
  "fig7_precip_gasto.png",
  `Fig. 7. Lagged Pearson correlation between the daily national mean of precip_mm (averaged over the ${N_CLI} climatological stations) shifted back by lag L days and the daily national mean of gasto_medio_m3s (averaged over the ${N_HID} hydrometric stations). Lags 0–15 days are shown; number of matched dates n = ${fmt(M.fig7.n_fechas_comunes)}. The maximum correlation is r = ${CORR.toFixed(3)} at lag = ${LAG} days.`,
  540, 0.45,
));

children.push(...figure(
  "fig8_cuencas_subcuencas.png",
  `Fig. 8. Map of the six operational basins and their delineated sub-basins (${N_SUB} in total): Cutzamala (${SUB_BY.Cutzamala}), Lerma Alto (${SUB_BY["Lerma Alto"]}), Bajío (${SUB_BY["Bajío"]}), Santiago (${SUB_BY.Santiago}), Pánuco (${SUB_BY["Pánuco"]}) and Alta del Balsas (${SUB_BY["Alta del Balsas"]}). Solid lines: sub-basin boundaries stored in processed/cuencas/<basin>.gpkg. Dotted rectangles: curated bboxes from conf/cuencas_piloto.yaml. Black dots: the ${N_SEL} hydrometric stations with ≥60% coverage used as pour points.`,
  580, 0.85,
));

// Methods
children.push(h1("Experimental Design, Materials and Methods"));
children.push(p(
  "The dataset was assembled by a scripted pipeline of ten Python entry points (scripts/01…scripts/11) run against Python 3.10+ with the following libraries pinned in pyproject.toml: pandas 2.2, numpy 1.26, scipy 1.13, pyarrow 16, geopandas 1.0, shapely 2, rasterio 1.3, rioxarray 0.15, whitebox 2.3, pandera 0.20, requests 2.32, PyYAML 6, click 8.1, python-dotenv 1.0, dvc[s3] 3.50. Version control uses Git; data versioning uses DVC 3.50 with a Cloudflare R2 (S3-compatible) backend. All step numbers below refer to script filenames in the source repository."
));

children.push(h2("4.1. Master-catalog acquisition (scripts/01_download_sih_catalogs.py)"));
children.push(p(
  "The hydrometric and climatological master catalogs were retrieved from the CONAGUA SIH portal (https://sih.conagua.gob.mx) as UTF-8 CSV files without HTML scraping. Requests were issued through requests.Session with User-Agent \"Mozilla/5.0 (HidroXAI-MX ingest)\" and a 60-second timeout. Each response was streamed to disk under data/raw/sih/, its SHA-256 digest computed with hashlib, and an entry was appended to data/raw/_manifest.json recording the URL, byte size, digest and UTC download timestamp. Header names were normalised (NFKD, lowercased, diacritic-stripped) and mapped to a canonical column set {clave, nombre, latitud, longitud, altitud, estado, municipio, region_hidrologica, cuenca}; numeric coordinates were coerced with pandas.to_numeric(errors=\"coerce\")."
));

children.push(h2("4.2. Basin configuration and per-basin bounding boxes (conf/cuencas_piloto.yaml)"));
children.push(p(
  "Each pilot basin is declared as a YAML entry with its name, its reference SIH hydrological region (12, 18 or 26), a curated bbox [min_lon, min_lat, max_lon, max_lat] in EPSG:4326, and the requested DEM resolution in metres. Lerma–Santiago is represented as three operational sub-entries (Lerma Alto, Bajío, Santiago) because the full bbox of the historical Lerma–Santiago region exceeds the memory budget of the WhiteboxTools chain used in §4.7 on a 16 GB reference workstation. The YAML file is the single source of truth for §4.6 (DEM assembly), §4.7 (delineation) and downstream station-to-basin assignment."
));

children.push(h2("4.3. Candidate-station filter (scripts/05_select_stations.py, default mode)"));
children.push(p(
  "The two master catalogs were filtered to the hydrological regions listed in conf/cuencas_piloto.yaml (regiones_hidrologicas = [12, 18, 26]) using pandas boolean indexing on the region_hidrologica column. The result was written to data/processed/estaciones_candidatas_hidrometricas.csv (550 rows) and data/processed/estaciones_candidatas_climatologicas.csv (2,731 rows) and used as input for the following download step."
));

children.push(h2("4.4. Per-station time-series download (scripts/03_download_sih_series.py)"));
children.push(p(
  "For every candidate key, the file at https://sih.conagua.gob.mx/basedatos/{Hidros|Climas}/<KEY>.csv was fetched. Concurrency is controlled by two environment variables: HIDROXAI_DL_WORKERS (default 16; a ThreadPoolExecutor with N workers) and HIDROXAI_DL_DELAY_S (default 0; per-request sleep applied only after real downloads, not on cache hits). The SIH portal is fronted by the Imperva Incapsula WAF; sustained concurrency above ~4 workers triggered per-IP challenges (302 loops or 403 responses) during our runs. The snapshot published in this article was completed at HIDROXAI_DL_WORKERS=1 and HIDROXAI_DL_DELAY_S=5 from a mobile-tethered IPv4. Each retrieved file was recorded in _manifest.json exactly as in §4.1. Failures were retried three times with exponential back-off (2s, 4s, 6s); series that ultimately failed were logged and excluded from downstream stages."
));

children.push(h2("4.5. Canonical schema, quality control and Parquet persistence (scripts/04_build_canonical.py)"));
children.push(p(
  "The raw CSVs were parsed with a permissive reader that accepts two header variants used by SIH (\"Fecha,…\" and \"Estacion,Fecha,…\") and two date formats (\"YYYY/MM/DD\" and \"YYYY-MM-DD\"). Header lines were located as the first row containing \"fecha\" as a comma-separated field; parsing uses pandas.read_csv with encoding=\"latin-1\", na_values=[\"-\", \"\"] and pandas.to_datetime(format=\"mixed\", errors=\"coerce\"). For every station the following transformations are applied, in order: (i) rebuild a continuous daily index via to_daily(); (ii) mark physical outliers with calidad = 2 using per-station thresholds v < 0 or v > 3·q99.9, where v is the target variable (gasto_medio_m3s for hydro, precip_mm for climate); (iii) impute internal gaps < 7 days with pandas.Series.interpolate(method=\"cubic\", limit=7, limit_area=\"inside\"), falling back to method=\"linear\" when scipy's cubic spline rejects the input for lack of boundary points; each imputed cell receives calidad = 1. The resulting DataFrame is validated against a pandera DataFrameSchema (src/hidroxai_mx/data/schema.py) that enforces column dtypes, ranges (e.g. gasto_medio_m3s ≥ 0, tmax_c ∈ [−30, 60]) and the allowed set of calidad and fuente labels. Validation errors are logged as warnings and do not abort the run. Outputs are written with pyarrow as a Hive-partitioned Parquet directory (partition_cols=[\"anio\"]) under data/processed/."
));

children.push(h2("4.6. Per-basin digital elevation model (scripts/06b_build_cem_per_basin.py)"));
children.push(p(
  "State-level tiles of the INEGI CEM 3.0 were downloaded manually from https://www.inegi.org.mx/temas/relieve/continental/ (the portal does not offer bbox-based downloads) and placed under data/scratch/<resolution>m/. For every basin declared in cuencas_piloto.yaml the following pipeline runs: (i) select the tiles whose extents intersect the basin bbox using rasterio.warp.transform_bounds to reproject tile extents to EPSG:4326; (ii) mosaic the selected tiles with rasterio.merge.merge; (iii) copy the mosaic into a rasterio.io.MemoryFile buffer to avoid file locks on Windows / Google Drive; (iv) clip the mosaic to the basin bbox with rasterio.mask.mask(shapes=[shapely.geometry.box(*bbox)], crop=True); (v) if the tile resolution differs from the resolution requested in the YAML (typical case: portal-supplied 15 m vs. requested 30 m), reproject with rasterio.warp.reproject using an affine scaled by the resolution ratio and Resampling.average when downsampling or Resampling.bilinear when upsampling; (vi) write the output as LZW-compressed, tiled GeoTIFF (predictor=2 for int16 rasters, 3 for floating-point) to data/raw/inegi/cem_<basin>.tif."
));

children.push(h2("4.7. Watershed delineation (scripts/06_delineate_basins.py)"));
children.push(p(
  "For every basin, the selected hydrometric stations that fall inside its bbox were exported as an ESRI Shapefile of pour points (data/interim/delineacion/<basin>/pour_points.shp) in EPSG:6362. The delineation runs the following WhiteboxTools chain on data/raw/inegi/cem_<basin>.tif: fill_depressions_wang_and_liu → d8_pointer → d8_flow_accumulation → extract_streams (threshold in cells, default 1000) → snap_pour_points (snap distance in map units, default 0.01) → watershed. The resulting raster was polygonised, and per-polygon attributes (area_km²; mean elevation and mean slope computed from the DEM with rasterstats-style zonal statistics) were written to data/processed/cuencas/<basin>.gpkg (layer cuenca). Because the historical Lerma–Santiago bbox exceeded the resident memory budget of d8_pointer / d8_flow_accumulation at 30 m on a 16 GB reference workstation, it was split into the three operational sub-entries described in §4.2."
));

children.push(h2("4.8. Refined station selection with coverage thresholds (scripts/05_select_stations.py --refine)"));
children.push(p(
  "After §4.4 and §4.5, per-station coverage was computed as cov = valid_days / expected_days, where expected_days = 5844 (2010-01-01 through 2025-12-31 inclusive) and valid_days is the count of non-missing observations of the target variable within that window. Threshold values are read from conf/cuencas_piloto.yaml (cobertura_minima: hidrometricas = 0.60, climatologicas = 0.80). Stations at or above the threshold are written to estaciones_seleccionadas_<type>.csv; hydrometric stations with 0.30 ≤ cov < 0.60 are additionally written to estaciones_extendidas_hidrometricas.csv with an extra column uso_recomendado = \"sensibilidad_reconstruccion\". For every selected hydrometric station, the k = 3 nearest climatological stations are computed with a spherical-earth haversine distance (R = 6371.0 km) and their comma-separated keys are stored in the column vecinos_clima."
));

children.push(h2("4.9. Feature engineering (scripts/07_build_features.py --no-save-tensors)"));
children.push(p(
  "For every hydrometric station, the daily precipitation value at time t was computed as the inverse-distance-weighted mean of the precip_mm series of the k = 3 climatological neighbours (weights w_i ∝ 1/d_i², with d_i = haversine distance station↔neighbour). Per-station lags at 1, 3, 7, 14 and 30 days and rolling means over 7 and 30 days were then generated for gasto_medio_m3s using pandas groupby(\"clave_estacion\").shift and rolling(window).mean. Numeric columns were left in their native units (m³/s, °C, mm). The resulting flat table is written to data/features/feature_table.parquet. Sliding-window tensor stacks (.npz) are not materialised by default because their size scales roughly as n_stations × window_length × n_features; they are re-generated on demand at training time."
));

children.push(h2("4.10. Storage guardrail and versioning (scripts/08_storage_report.py; DVC)"));
children.push(p(
  "Before every dvc push, scripts/08_storage_report.py walks data/{raw,processed,features}, excludes any file with the .npz suffix, and sums the remaining byte counts. If the total exceeds the ceiling read from the environment variable R2_CAP_GB (default 9.5 GB, chosen to stay below the 10 GB free tier of the Cloudflare R2 bucket used as remote), the script exits with status 1 and aborts the push. Reproducibility is enforced through DVC: dvc.yaml declares one stage per pipeline step with explicit deps and outs; dvc.lock stores an MD5 digest per stage output. On a clean checkout, `dvc pull` restores the exact byte contents of the archive from the R2 remote."
));

children.push(h2("4.11. Figure and metrics generation (scripts/09_make_report_figures.py)"));
children.push(p(
  "Figures 1–8 embedded in this article and the file processed/reportes/metrics.json were produced by scripts/09_make_report_figures.py using matplotlib (matplotlib.use(\"Agg\"); rcParams[\"savefig.dpi\"] = 300; rcParams[\"savefig.bbox\"] = \"tight\"). The script reads the Parquet directories as pyarrow.dataset objects (partitioning=\"hive\") and augments the hydrometric dataframe with the catalog columns via a left join on clave_estacion. Sub-basin polygons for Fig. 8 are loaded from processed/cuencas/*.gpkg with geopandas.read_file, reprojected to EPSG:4326, and rendered with GeoDataFrame.boundary.plot; overlaid rectangles are the bboxes from conf/cuencas_piloto.yaml, and overlaid points are the ${N_SEL} pour points from estaciones_seleccionadas_hidrometricas.csv."
));

children.push(h2("4.12. Deposit packaging (scripts/11_build_zenodo_bundle.py)"));
children.push(p(
  "The Zenodo archive was produced with zipfile.ZipFile(..., compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) over data/{raw/sih, raw/sih_series/hidrometricas, raw/sih_series/climatologicas, raw/inegi, processed, features} and conf/cuencas_piloto.yaml, and augmented with an autogenerated English README.md and LICENSE-DATA.md and a machine-readable manifest_zenodo.json listing the SHA-256 hash and byte size of every archived file. Files ending in .npz and the folders data/scratch/ and data/interim/ were excluded from the deposit. The resulting archive HidroXAI-MX-v2026.06.zip totals about 895 MB compressed (3,588 archived files, 3.2 GB uncompressed) and was uploaded to Zenodo, producing the DOI 10.5281/zenodo.21231601 referenced in the Specifications Table."
));

// Limitations
children.push(h1("Limitations"));
[
  "Fuente única. Este snapshot integra únicamente el SIH de CONAGUA. La validación cruzada con BANDAS (archivos .mdb históricos), CLICOM (CICESE) y SMN (EMAS) se declara como trabajo futuro (ver §Future Work).",
  `Cobertura hidrométrica heterogénea. La cobertura media de las ${N_HID} estaciones hidrométricas es ${COV_MEAN.toFixed(1)} % en el periodo 2010–2025: muchas series terminan en 2021 o presentan grandes huecos. Para no excluir cuencas críticas, se publicó un conjunto extendido (30 %–60 %) para análisis de sensibilidad y los modelos deben entrenarse sólo sobre ventanas válidas.`,
  "Resolución efectiva del CEM. El portal INEGI sólo permitió descargar los tiles a 15 m; para cuencas grandes (Lerma medio, Pánuco, Santiago) el procesamiento de delineación se hizo tras un remuestreo a 30 m por restricción de memoria. Esto reduce el detalle hidrológico fino en zonas de cabecera.",
  "Errores del catálogo SIH. Cuatro estaciones hidrométricas (entre ellas B18558 ABASOLO, listada en Morelos con coordenadas correspondientes a Tijuana) presentan inconsistencias entre estado, región hidrológica y latitud/longitud reportadas. Se documentan en este artículo y se descartan automáticamente al filtrar por el bbox geográfico curado de cada cuenca.",
  "Restricciones del proveedor SIH. El portal usa el WAF Imperva Incapsula con un JavaScript challenge: descargas concurrentes > 4 hilos disparan bloqueos por IP; el descargador documenta esto y permite ajustar paralelismo y delay, pero usuarios masivos pueden necesitar mirror local o sesión de navegador. Esta limitación es del proveedor primario, no del snapshot ya publicado en Zenodo (DOI 10.5281/zenodo.21231601).",
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
children.push(p("Código: https://github.com/pantrok/hidroxai-mx (MIT). Snapshot de datos v2026.06 depositado en Zenodo: DOI 10.5281/zenodo.21231601 (https://doi.org/10.5281/zenodo.21231601), licencia CC BY 4.0. La misma versión del dataset también está disponible en el remoto DVC (Cloudflare R2) mediante `dvc pull` sobre el repositorio."));

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

children.push(h2("Pendientes no negociables (2)"));
[
  "Completar coautores y roles CRediT (¿alguien del equipo UPIIT participa en validación, supervisión o curación?).",
  "Redactar la lista de referencias bibliográficas a partir del placeholder al final del manuscrito.",
].forEach((t) => children.push(bullet(t)));
children.push(h2("Cerrado"));
[
  "Zenodo. Snapshot v2026.06 depositado con DOI 10.5281/zenodo.21231601, ya referenciado en Specifications Table y Data Availability.",
].forEach((t) => children.push(bullet(t)));

children.push(h2("Mejoras deseables (no bloquean)"));
[
  "Validación cruzada con BANDAS/CLICOM/SMN — declarada como trabajo futuro pero quedaría más fuerte ejecutarla en al menos un subconjunto antes de envío.",
  `La cobertura media de ${COV_MEAN.toFixed(1)} % en el universo hidrométrico (${N_HID} estaciones) es baja porque incluye estaciones discontinuadas; podría reportarse también la cobertura restringida al conjunto seleccionado ≥ 60 % para complementar la Fig. 1.`,
  "Un notebook acompañante mínimo (al estilo del paper Urdu OCR) con un caso de uso reproducible (cargar parquet, filtrar una cuenca, graficar respuesta precip → gasto en una estación específica).",
].forEach((t) => children.push(bullet(t)));

children.push(h2("Recomendación"));
children.push(p(
  "El borrador con figuras reales, DOI de Zenodo (10.5281/zenodo.21231601) y coherencia entre snapshot y manuscrito está listo para revisión interna. Una vez cerrados los dos pendientes restantes (autores/CRediT y lista de referencias), puede enviarse a Data in Brief sin trabajo metodológico adicional."
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

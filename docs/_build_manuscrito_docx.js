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
  `Hidro-MX is organised as five interlinked groups of files that together cover the raw daily records of the primary sources, the canonical time-series tables in a columnar format optimised for out-of-memory reads, the manifests of the stations selected for downstream modelling, the geospatial resources used to describe each pilot basin, and a compact model-ready feature table. The dataset covers four pilot basins in Mexico (Cutzamala; the historical Lerma–Santiago region, operationally split into Lerma Alto, Bajío and Santiago; Pánuco; and Alta del Balsas), spans the reference window 2010-01-01–2025-12-31, and totals ${fmt(N_HID)} hydrometric stations with ${fmt(ROWS_HID)} daily observations of streamflow and ${fmt(N_CLI)} climatological stations with ${fmt(ROWS_CLI)} daily observations of precipitation, temperature and evaporation.`
));
children.push(p(
  "Table 1 gives the top-level structure of the dataset. Table 2 lists, for every tabular file, the columns delivered to the reader together with their data type, physical units and valid range. Table 3 summarises the number of stations selected per pilot basin together with the number of sub-basin polygons delivered with the geospatial resources."
));
children.push(blank());

children.push(h2("Table 1. Directory structure and content"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3000, 6360],
  rows: [
    row3("Directory / group", "Content", "", true),
    row3("Raw daily records", "Two master catalogs (hydrometric and climatological) that list every station published by the primary provider with its identifier, name, coordinates, altitude, state, municipality, hydrological region and basin. One CSV file per station with the full historical daily record delivered by the provider (streamflow and stage for hydrometric stations; precipitation, minimum, maximum and mean temperature and evaporation for climatological stations). A provenance manifest lists the source URL, SHA-256 hash, byte size and UTC timestamp for every raw file.", ""),
    row3("Canonical time-series tables", "Two columnar tables (hydrometric and climatological), partitioned by year, produced from the raw records by parsing, quality control and short-gap imputation. Every row is a station–day pair augmented with a quality flag and a source label. Column set and units are given in Table 2.", ""),
    row3("Station manifests", "Three tabular products describing which stations are used downstream and how: (i) the candidate universe, obtained by filtering the master catalogs by hydrological region; (ii) the main set of stations meeting the per-type coverage threshold over the reference window; (iii) an extended set of hydrometric stations with intermediate coverage, released for sensitivity and reconstruction studies. Each selected hydrometric station carries the identifiers of its three closest climatological neighbours.", ""),
    row3("Geospatial resources", "One digital elevation model per pilot basin (six rasters, five at 30 m and one at 15 m resolution) covering the full curated bounding box of the corresponding basin. One vector layer per basin with the polygons of the delineated sub-basins together with their area, mean elevation and mean slope.", ""),
    row3("Feature table", "A single flat model-ready table pairing every hydrometric station-day with its own lagged streamflow at 1, 3, 7, 14 and 30 days and with rolling means over 7 and 30 days. It preserves the quality flag inherited from the canonical hydrometric table so downstream users can restrict training to valid windows.", ""),
    row3("Basin configuration", "A configuration file that declares, for each pilot basin, its name, its reference hydrological region code, its curated bounding box and its target elevation-model resolution. This file defines the geographic scope shared by the time-series manifests, the digital elevation models and the delineated sub-basins.", ""),
  ],
}));
children.push(blank());

children.push(h2("Table 2. Columns, data types and units of the tabular files"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2800, 6560],
  rows: [
    row3("File group", "Columns — data type — units / valid range", "", true),
    row3("Canonical hydrometric time series",
      `Station identifier — string, alphanumeric (1–8 characters, leading zeros preserved). Date — day-precision timestamp (no time-of-day). Mean daily streamflow — float, m³/s, ≥ 0. Water stage — float, m, referenced to a station datum, allowed to be missing. Source label — categorical, one of {SIH, BANDAS, CLICOM, EMAS}; equal to SIH throughout this release. Quality flag — integer in {0, 1, 2}: 0 for an original observation, 1 for a value imputed by short-gap interpolation (gap length < 7 days), 2 for a physical outlier retained for auditability. Year — integer partition key.`, ""),
    row3("Canonical climatological time series",
      "Station identifier, date, source label, quality flag and year partition key as above. Daily precipitation — float, mm, ≥ 0. Daily maximum, minimum and mean temperature — float, °C, within physical bounds. Daily evaporation — float, mm, ≥ 0.", ""),
    row3("Candidate stations (hydrometric / climatological)",
      "Station identifier, name, state, municipality, hydrological region code and basin — strings. Latitude and longitude — float, WGS 84 decimal degrees. Altitude — float, metres above sea level.", ""),
    row3("Selected stations (main set)",
      "All columns from the candidate file, plus a coverage column in [0, 1] representing the fraction of non-missing daily observations of the target variable inside the reference window 2010-01-01–2025-12-31. Selected hydrometric stations additionally carry a comma-separated list of the three closest climatological stations by great-circle distance.", ""),
    row3("Extended hydrometric stations",
      "Same columns as the main hydrometric selection, restricted to stations whose coverage lies in [0.30, 0.60), plus a categorical column marking the intended use (sensitivity analysis and gap reconstruction).", ""),
    row3("Sub-basin polygons",
      "Polygon geometries in a metric coordinate reference system. Attributes: area in km², mean elevation in metres above sea level, mean slope as a dimensionless gradient, and the identifier of the pour-point hydrometric station used during delineation.", ""),
    row3("Feature table",
      "Station identifier, date, mean daily streamflow and quality flag as in the canonical hydrometric table. Lagged features L1, L3, L7, L14 and L30 — float, m³/s — corresponding to the streamflow observed at the same station k days before the current row. Rolling-mean features M7 and M30 — float, m³/s — corresponding to the trailing 7-day and 30-day mean of the streamflow at the same station.", ""),
    row3("Basin configuration",
      "Per basin: name — string. Hydrological region code — integer. Bounding box — four floats in decimal degrees, ordered as minimum longitude, minimum latitude, maximum longitude, maximum latitude. Target elevation-model resolution — integer, metres.", ""),
  ],
}));
children.push(blank());

children.push(h2("Table 3. Stations and sub-basins delivered per pilot basin"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3120, 3120, 3120],
  rows: [
    row3("Basin", "Selected hydrometric stations inside bbox", "Delineated sub-basin polygons", true),
    row3("Cutzamala", "8", String(SUB_BY["Cutzamala"])),
    row3("Lerma Alto", "9", String(SUB_BY["Lerma Alto"])),
    row3("Bajío", "26", String(SUB_BY["Bajío"])),
    row3("Santiago", "13", String(SUB_BY["Santiago"])),
    row3("Pánuco", "52", String(SUB_BY["Pánuco"])),
    row3("Alta del Balsas", "17", String(SUB_BY["Alta del Balsas"])),
    row3("Total (unique)", `${N_SEL}`, String(N_SUB)),
  ],
}));
children.push(p("The per-basin sum in Table 3 exceeds the count of unique selected stations because a small number of stations lie inside the overlap between two contiguous bounding boxes; each station is then assigned to a single sub-basin by proximity to its snapped pour point during delineation.", { italics: true, size: 20 }));

// Methods
children.push(h1("Experimental Design, Materials and Methods"));
children.push(p(
  "The dataset was constructed through a seven-stage systematic pipeline that ingests two publicly available primary sources (a national hydrological information system and a national digital elevation model), harmonises them into a station–day columnar schema and a per-basin geospatial layer, and derives from them a compact model-ready feature table. Fig. 1 summarises the overall workflow and the input and output of every stage. Algorithm 1 gives the corresponding pseudocode. The following subsections detail each stage. All time series were reduced to the reference window 2010-01-01 through 2025-12-31 (5,844 days) for coverage assessment and downstream feature engineering."
));

children.push(...figure(
  "fig0_workflow.png",
  "Fig. 1. Overall workflow of the Hidro-MX construction pipeline. Blue boxes: primary data sources. Red-edged boxes: processing stages. Green-edged boxes: quality-control and feature-engineering stages. Orange boxes: distributed outputs. Arrows follow the direction of data flow.",
  580, 0.75,
));

// Pseudocode Algorithm 1
children.push(h2("Algorithm 1 — Hidro-MX dataset construction pipeline"));
const algoLines = [
  "Input:  H = hydrological information system endpoint",
  "        E = state-level digital elevation model tiles",
  "        B = pilot-basin configuration (name, region code, bounding box, target resolution)",
  "        [t_start, t_end] = reference reporting window",
  "Output: T_H, T_C = canonical hydrometric and climatological time-series tables",
  "        S_H, S_C = selected station manifests with climate neighbours",
  "        D_b = per-basin digital elevation model",
  "        W_b = per-basin sub-basin polygon layer",
  "        F   = model-ready feature table",
  "",
  "Step 1 — Catalog acquisition:",
  "  For type in {hydrometric, climatological}:",
  "     Download master catalog from H; normalise headers; record provenance manifest",
  "",
  "Step 2 — Candidate-station selection:",
  "  For each catalog: retain stations whose hydrological region is listed in B",
  "  Result: candidate universes U_H, U_C",
  "",
  "Step 3 — Time-series retrieval:",
  "  For every station k in U_H \\cup U_C:",
  "     Download the full historical daily record from H",
  "     Register the file in the provenance manifest",
  "",
  "Step 4 — Canonical schema and quality control:",
  "  For every retrieved series s_k:",
  "     Parse permissively (header and date-format variants); replace sentinels by NaN",
  "     Rebuild a continuous daily index over the observed range",
  "     Mark physical outliers (quality flag = 2, retained for auditability)",
  "     Impute internal gaps < 7 days by cubic spline; fall back to linear",
  "       on numerically ill-posed segments (quality flag = 1)",
  "     Validate against the canonical schema (types, physical bounds, allowed labels)",
  "  Persist T_H, T_C as year-partitioned columnar tables",
  "",
  "Step 5 — Digital elevation model preparation per basin:",
  "  For every basin b in B:",
  "     Select the state tiles whose extents intersect the bounding box of b",
  "     Mosaic the selected tiles; clip to the bounding box",
  "     If tile resolution differs from the target: resample (average for downsampling,",
  "       bilinear for upsampling)",
  "     Store the result as a compressed raster D_b",
  "",
  "Step 6 — Watershed delineation per basin:",
  "  For every basin b:",
  "     Take the hydrometric stations of the main set that fall inside its bounding box",
  "     Chain over D_b: fill depressions → flow direction → flow accumulation →",
  "                     snap pour points → watershed",
  "     Vectorise; attach per-polygon area, mean elevation and mean slope",
  "     Store the result as a per-basin polygon layer W_b",
  "",
  "Step 7 — Coverage refinement and feature engineering:",
  "  For every station k: cov_k = valid_days_k / (t_end − t_start + 1)",
  "  Main sets:    S_H = { k in U_H : cov_k ≥ 0.60 };  S_C = { k in U_C : cov_k ≥ 0.80 }",
  "  Extended set: E_H = { k in U_H : 0.30 ≤ cov_k < 0.60 }  (sensitivity / reconstruction)",
  "  For every k in S_H:",
  "     N_k = 3 nearest climatological stations by great-circle distance",
  "  For every k in S_H:",
  "     Compute per-station lags L1, L3, L7, L14, L30 of streamflow",
  "     Compute per-station rolling means M7 and M30 of streamflow",
  "     Inherit the quality flag from T_H",
  "  Persist F as a flat columnar table",
];
algoLines.forEach((line) => children.push(code(line)));
children.push(blank());

// ---- Stages ----
children.push(h2("Stage 1 — Catalog acquisition"));
children.push(p(
  "The pipeline is initialised by retrieving the two master catalogs published by the primary hydrological information system, one describing the population of hydrometric stations and the other describing the population of climatological stations. Both catalogs are streamed over HTTPS with a persistent session and a bounded read timeout; each retrieved file is streamed to disk and its cryptographic hash is computed on-the-fly. A provenance manifest is written next to the catalogs and records, for every retrieved file, the source URL, the byte size, the hash and the timestamp of retrieval. Header names are normalised (case-folding and diacritic stripping) and mapped to a canonical column set covering the station identifier, name, latitude, longitude, altitude, state, municipality, hydrological region code and basin. Numeric fields are coerced to floating-point with an explicit NaN policy so that malformed rows never propagate silently."
));

children.push(h2("Stage 2 — Candidate-station selection"));
children.push(p(
  "The two master catalogs are filtered by hydrological region using the reference list declared in the pilot-basin configuration, retaining every station whose region code matches one of the pilot regions. The resulting candidate universes act as the driver of the retrieval stage: every station downloaded downstream is a member of these universes. Producing the candidate manifests as an explicit deliverable (rather than as an intermediate variable held only in memory) allows later work to compare the population reduction implied by the coverage thresholds with the underlying regional population."
));

children.push(h2("Stage 3 — Time-series retrieval"));
children.push(p(
  "The full historical daily record of every candidate station is retrieved from the primary hydrological information system, one file per station. Because the provider protects its portal with a web-application firewall that reacts to sustained parallelism by challenging or blocking client IPs, the retrieval respects two configurable knobs: a bounded thread pool (default 16 workers) and a per-request idle interval (default 0 seconds) applied only after a real network fetch, not after a cache hit. For the release described in this article the retrieval was completed at one worker with a five-second interval between fetches from a mobile-tethered network so that the WAF did not challenge the client during the operation. Every retrieved file is registered in the provenance manifest introduced in Stage 1 with the same fields (URL, byte size, cryptographic hash, timestamp). Individual retrieval failures are retried three times with exponential back-off and, if unrecoverable, are logged and excluded from later stages."
));

children.push(h2("Stage 4 — Canonical schema and quality control"));
children.push(p(
  "The raw records ingested in Stage 3 are heterogeneous: the provider distributes at least two header variants and two date formats across its station families, and represents missing values as either an explicit dash character or as an empty field. A permissive parser locates the header line by searching for the presence of the field \"Fecha\" as a comma-separated token, normalises column labels to the same canonical schema used by the catalogs in Stage 1 and coerces dates in mixed format. For every station the following transformations are applied in order: the daily index is rebuilt as a continuous calendar so that structural absences are not confused with observational absences; sentinel encodings of missing values are replaced by NaN; a physical range check flags negative flows and outliers above three times the 99.9-th percentile of the local distribution (quality flag = 2, retained); internal gaps shorter than seven days are imputed by cubic-spline interpolation, falling back to linear interpolation on segments where the spline is not numerically well-posed (quality flag = 1). The output is validated against a strict schema that enforces the column set, dtypes, physical bounds (for example non-negative streamflow, temperature within a physical range) and the finite set of allowed labels for the source and quality columns. Two canonical tables are persisted as year-partitioned columnar files, one hydrometric and one climatological."
));

children.push(h2("Stage 5 — Digital elevation model preparation per basin"));
children.push(p(
  "The primary provider distributes the national digital elevation model as state-level tiles. For every pilot basin the pipeline selects the tiles whose extents intersect its curated bounding box, mosaics them into a single raster and clips the mosaic to the bounding box, so that the delivered raster contains no data outside the basin envelope. When the resolution of the source tiles differs from the resolution requested for the basin, the raster is resampled with an area-preserving average when it is coarsened and with bilinear interpolation when it is refined. The result is stored as a single compressed elevation raster per basin. In the release described in this article, five basins are delivered at 30-metre resolution and one basin (Alta del Balsas) at 15-metre resolution, matching the target declared in the pilot-basin configuration."
));

children.push(h2("Stage 6 — Watershed delineation"));
children.push(p(
  "For every pilot basin, the hydrometric stations of the main selection that lie inside its bounding box are used as the pour points of a standard raster-based delineation over the basin elevation model. The chain consists of depression filling, single-flow-direction encoding, flow accumulation, snapping of the pour points to the streams derived from a fixed accumulation threshold and watershed extraction. The output is vectorised and per-polygon attributes are computed by zonal statistics on the elevation model (area, mean elevation and mean slope). The result is written to a per-basin vector layer. To keep the memory budget of the delineation chain compatible with a workstation-class machine, the historical Lerma–Santiago region is delivered as three operational sub-basins (Lerma Alto, Bajío and Santiago), each with its own bounding box, elevation model and vector layer, rather than as a single basin."
));

children.push(h2("Stage 7 — Coverage refinement and feature engineering"));
children.push(p(
  "The last stage applies to the canonical time-series tables the coverage criterion used downstream. Per-station coverage is computed as the fraction of non-missing daily observations of the target variable inside the reference window; the target variable is streamflow for hydrometric stations and precipitation for climatological stations. Two per-type thresholds define the main sets (0.60 for hydrometric stations, 0.80 for climatological stations); a lower threshold (0.30) defines an additional extended set of hydrometric stations released for sensitivity and reconstruction studies. Every selected hydrometric station is paired with the three closest climatological stations by great-circle distance, so that end users can build multi-station inputs directly. Finally, per-station lagged streamflow features at 1, 3, 7, 14 and 30 days and rolling means over 7 and 30 days are computed and delivered together as a flat feature table that preserves the quality flag inherited from the canonical hydrometric table."
));

// --- Descriptive figures of the delivered dataset ---
children.push(h2("Descriptive figures of the delivered dataset"));
children.push(p(
  "The following figures summarise the delivered dataset in terms of station inventory (Fig. 2), streamflow distribution by region (Fig. 3), quality-flag composition (Fig. 4), spatial distribution of the selected stations (Fig. 5), monthly and annual dynamics of streamflow (Fig. 6), lagged agreement between the aggregate national precipitation and streamflow series (Fig. 7) and the delineated sub-basins together with the pour points (Fig. 8)."
));

children.push(...figure(
  "fig1_inventario_cobertura.png",
  `Fig. 2. Left: number of hydrometric stations per hydrological region in the delivered canonical hydrometric table (RH 12 = ${M.fig1.inventario_por_rh["12"]}, RH 18 = ${M.fig1.inventario_por_rh["18"]}, RH 26 = ${M.fig1.inventario_por_rh["26"]}). Right: histogram of the per-station coverage of streamflow over the reference window 2010-01-01 through 2025-12-31. Vertical dashed lines mark the operational thresholds used in Stage 7 (0.60 for hydrometric selection, 0.80 for climatological selection). Mean coverage across all stations = ${COV_MEAN.toFixed(1)}%; ${N_HID_60} stations meet the 0.60 cut-off; ${N_HID_80} stations meet the 0.80 cut-off.`,
));

children.push(...figure(
  "fig2_descriptiva.png",
  `Fig. 3. Boxplot of the daily mean streamflow grouped by hydrological region (RH 12, 18 and 26); the y-axis is on a base-10 logarithmic scale. Sample statistics of the pooled series: median = ${M.fig2.describe_global["50%"].toFixed(2)} m³/s, third quartile = ${M.fig2.describe_global["75%"].toFixed(2)} m³/s, maximum = ${fmt(M.fig2.describe_global.max, 0)} m³/s. Median value in the wet season (May–October) = ${M.fig2.por_temporada.median.lluviosa.toFixed(2)} m³/s; dry season = ${M.fig2.por_temporada.median.seca.toFixed(2)} m³/s.`,
));

children.push(...figure(
  "fig3_calidad.png",
  `Fig. 4. Counts and percentages of the three-valued quality flag over ${fmt(M.fig3.n.ok + M.fig3.n.imputado + M.fig3.n.outlier)} hydrometric daily observations: ${PCT_OK.toFixed(2)}% flagged 0 (original observation), ${PCT_IMP.toFixed(2)}% flagged 1 (imputed by short-gap interpolation, gap length < 7 days) and ${PCT_OUT.toFixed(3)}% flagged 2 (physical outliers retained in the archive).`,
));

children.push(...figure(
  "fig5_mapa.png",
  "Fig. 5. Latitude–longitude scatter of the geolocated hydrometric stations of the main selection, coloured by their reported hydrological region (RH 12, 18 and 26). The legend reports the count of points per region.",
));

children.push(...figure(
  "fig6_temporal.png",
  "Fig. 6. Left: monthly climatology of mean daily streamflow aggregated over all hydrometric stations (mean ± 1σ) as a function of the calendar month. Right: annual mean of mean daily streamflow from 1922 to 2025; vertical dotted lines mark the years 2011, 2021 and 2023 for reference.",
));

children.push(...figure(
  "fig7_precip_gasto.png",
  `Fig. 7. Lagged Pearson correlation between the daily national mean of precipitation (averaged over the ${N_CLI} climatological stations) shifted back by lag L days and the daily national mean of streamflow (averaged over the ${N_HID} hydrometric stations); lags from 0 to 15 days are shown. Number of matched dates n = ${fmt(M.fig7.n_fechas_comunes)}. The maximum correlation is r = ${CORR.toFixed(3)} at lag = ${LAG} days.`,
  540, 0.45,
));

children.push(...figure(
  "fig8_cuencas_subcuencas.png",
  `Fig. 8. Map of the six pilot basins and their delineated sub-basins (${N_SUB} sub-basins in total): Cutzamala (${SUB_BY.Cutzamala}), Lerma Alto (${SUB_BY["Lerma Alto"]}), Bajío (${SUB_BY["Bajío"]}), Santiago (${SUB_BY.Santiago}), Pánuco (${SUB_BY["Pánuco"]}) and Alta del Balsas (${SUB_BY["Alta del Balsas"]}). Solid lines: sub-basin boundaries. Dotted rectangles: curated bounding boxes declared in the pilot-basin configuration. Black dots: the ${N_SEL} hydrometric stations of the main selection used as pour points.`,
  580, 0.85,
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

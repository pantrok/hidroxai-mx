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
  children: [new TextRun({ text: "AVISO (no para envío): esta versión del borrador incorpora las secciones DATA DESCRIPTION y EXPERIMENTAL DESIGN, MATERIALS AND METHODS reescritas siguiendo las instrucciones del template Data in Brief v.19 (no ofrecer background, interpretaciones o conclusiones en esas secciones); completa el campo \"Instructions for accessing these data\" en la Specifications Table; y cierra el CRediT Author Statement con la lista de coautores del artículo. Snapshot v2026.06 depositado en Zenodo con DOI 10.5281/zenodo.21231601 (público, sin registro). Único pendiente no técnico: completar la lista final de referencias bibliográficas. Los roles CRediT asignados son sugerencias razonables sobre la base habitual para un data paper; se solicita a cada coautor confirmar / ajustar sus roles.", font: FONT, size: 20, italics: true })] }));

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
  `The dataset is distributed as a single deposit hosted on Zenodo. When uncompressed, the archive expands into four content directories (raw/, processed/, features/, conf/) that follow the same logical layout used to construct the dataset, plus three top-level files that document the deposit (README.md, LICENSE-DATA.md and manifest_zenodo.json). The dataset covers four pilot basins in Mexico (Cutzamala; the historical Lerma–Santiago region, operationally split into Lerma Alto, Bajío and Santiago; Pánuco; and Alta del Balsas), uses the reference window 2010-01-01 through 2025-12-31 for coverage assessment, and totals ${fmt(N_HID)} hydrometric stations with ${fmt(ROWS_HID)} daily observations of streamflow, and ${fmt(N_CLI)} climatological stations with ${fmt(ROWS_CLI)} daily observations of precipitation, temperature and evaporation.`
));
children.push(p(
  "Table 1 lists the top-level directories, the file formats they use and the type of data delivered inside each of them. Table 2 lists, for every tabular file, its columns together with data type, physical units and valid range. Table 3 summarises the number of stations delivered per pilot basin and the number of sub-basin polygons produced by the delineation."
));
children.push(blank());

children.push(h2("Table 1. Directory structure, file formats and content"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2000, 2400, 4960],
  rows: [
    row3("Directory / file", "File formats", "Content", true),
    row3("raw/sih/",
      "CSV (UTF-8, comma-separated); JSON",
      "Two master catalogs distributed by the primary hydrological information system: catalogo_hidrometricas.csv (1,189 rows) and catalogo_climatologicas.csv (7,499 rows), each row describing one publicly listed station with its identifier, name, coordinates, altitude, state, municipality, hydrological region code and basin. The file _manifest.json records, for every raw file retrieved during the construction pipeline, the source URL, byte size, SHA-256 hash and UTC timestamp of retrieval."),
    row3("raw/sih_series/hidrometricas/",
      "CSV (Latin-1, comma-separated)",
      "547 per-station files named <STATION_KEY>.csv holding the full historical daily record delivered by the primary provider: date, mean daily streamflow (m³/s) and water stage (m). Missing values are encoded as an explicit dash or as an empty field."),
    row3("raw/sih_series/climatologicas/",
      "CSV (Latin-1, comma-separated)",
      "2,659 per-station files named <STATION_KEY>.csv with date, daily precipitation (mm), daily maximum, minimum and mean temperature (°C) and daily evaporation (mm)."),
    row3("raw/inegi/",
      "GeoTIFF (int16, LZW-compressed, tiled)",
      "Six per-basin digital elevation models named cem_<basin>.tif: cem_cutzamala.tif, cem_lerma_alto.tif, cem_bajio.tif, cem_santiago.tif and cem_panuco.tif at 30 m spatial resolution, and cem_alta_del_balsas.tif at 15 m. Each raster covers the curated bounding box of its basin and stores the elevation above mean sea level."),
    row3("processed/",
      "Apache Parquet (Snappy-compressed, year-partitioned Hive layout); CSV; OGC GeoPackage",
      "Curated tables delivered as the main analytical entry point: series_hidrometricas.parquet and series_climatologicas.parquet (canonical station–day tables described in Table 2); estaciones_candidatas_<type>.csv (candidate universes: 550 hydro / 2,731 climate rows); estaciones_seleccionadas_<type>.csv (main sets: 108 hydro / 415 climate rows); estaciones_extendidas_hidrometricas.csv (107 hydrometric stations of the extended set); and the sub-directory cuencas/ with one GeoPackage per basin holding the polygons of the delineated sub-basins."),
    row3("features/",
      "Apache Parquet (Snappy-compressed, single file)",
      "feature_table.parquet: model-ready flat table pairing every hydrometric station–day with its own lagged streamflow at 1, 3, 7, 14 and 30 days and with rolling means over 7 and 30 days; the quality flag is preserved so downstream users can restrict training to valid windows."),
    row3("conf/",
      "YAML (UTF-8)",
      "cuencas_piloto.yaml: configuration file that declares, for every pilot basin, its name, its reference hydrological region code, its curated bounding box (four floats in EPSG:4326) and its target elevation-model resolution."),
    row3("README.md · LICENSE-DATA.md · manifest_zenodo.json",
      "Markdown (English); JSON",
      "Deposit-level documentation. README.md describes the archive layout and reuse instructions. LICENSE-DATA.md contains the Creative Commons Attribution 4.0 International text and the mandatory attribution to the primary providers. manifest_zenodo.json lists every archived file with its relative path, byte size and SHA-256 hash for integrity verification."),
  ],
}));
children.push(blank());

children.push(h2("Table 2. Columns, data types and units of the tabular files"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2800, 6560],
  rows: [
    row3("File", "Columns — data type — units / valid range", "", true),
    row3("series_hidrometricas.parquet",
      "clave_estacion — string, alphanumeric (1–8 characters, leading zeros preserved). fecha — datetime64[ns] at day precision. gasto_medio_m3s — float, m³/s, ≥ 0. nivel_m — float, m, station-referenced datum, may be missing. fuente — categorical in {SIH, BANDAS, CLICOM, EMAS}; equal to SIH throughout this release. calidad — int in {0, 1, 2}: 0 = original observation, 1 = imputed by short-gap interpolation (gap length < 7 days), 2 = physical outlier retained. anio — int (Hive partition key).", ""),
    row3("series_climatologicas.parquet",
      "clave_estacion, fecha, fuente, calidad and anio as above. precip_mm — float, mm, ≥ 0. tmax_c, tmin_c, tmed_c — float, °C, within physical bounds. evap_mm — float, mm, ≥ 0.", ""),
    row3("estaciones_candidatas_<type>.csv",
      "clave, nombre, estado, municipio, region_hidrologica, cuenca — strings. latitud, longitud — float, WGS 84 decimal degrees. altitud — float, m above mean sea level.", ""),
    row3("estaciones_seleccionadas_<type>.csv",
      "All columns from the candidate file, plus cobertura — float in [0, 1] (fraction of non-missing daily observations of the target variable inside the reference window). The hydrometric file additionally carries vecinos_clima — string, a comma-separated list of the three closest climatological stations by great-circle distance.", ""),
    row3("estaciones_extendidas_hidrometricas.csv",
      "Same schema as estaciones_seleccionadas_hidrometricas.csv, restricted to stations with 0.30 ≤ cobertura < 0.60. Additional column uso_recomendado — string, categorical label marking the intended use (sensitivity analysis and gap reconstruction).", ""),
    row3("cuencas/<basin>.gpkg",
      "Polygon geometries in a metric coordinate reference system (EPSG:6362). Attributes: area_km2 — float, km². elevacion_media_m — float, m above mean sea level. pendiente_media — float, dimensionless gradient. clave_estacion — string, identifier of the pour-point station used during delineation.", ""),
    row3("feature_table.parquet",
      "clave_estacion, fecha, gasto_medio_m3s and calidad as in the canonical hydrometric table. gasto_medio_m3s_lag1, _lag3, _lag7, _lag14, _lag30 — float, m³/s at t − k days for the same station. gasto_medio_m3s_ma7, _ma30 — float, m³/s trailing 7-day and 30-day mean at the same station.", ""),
    row3("cuencas_piloto.yaml",
      "Per basin: nombre — string. region_hidrologica — int. bbox — sequence of four floats [min_lon, min_lat, max_lon, max_lat] in EPSG:4326. cem_resolucion_m — int, m.", ""),
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
  "The dataset was constructed with a Python 3.10 pipeline that ingests two publicly available primary sources — a national hydrological information system (streamflow and climate) and a national digital elevation model — harmonises them into a station–day columnar schema together with a per-basin geospatial layer, and derives from them a compact model-ready feature table. Data manipulation relies on pandas and numpy; scientific interpolation on scipy; retrieval on the requests library; columnar persistence on Apache Arrow through pyarrow; schema validation on pandera; raster processing on rasterio and rioxarray; vector processing on geopandas and shapely; hydrological delineation on WhiteboxTools through the whitebox binding; configuration on PyYAML; and the diagnostic figures on matplotlib. The processing is organised in seven stages summarised in the workflow of Fig. 1 and detailed in Algorithm 1. All time series are reduced to the reference window 2010-01-01 through 2025-12-31 (5,844 days) for coverage assessment and feature engineering."
));

children.push(...figure("fig0_workflow.png",
  "Fig. 1. Overall workflow of the dataset construction pipeline (four processing phases and four distributed outputs).",
  540, 0.55));

// Pseudocode Algorithm 1 (compact)
children.push(h2("Algorithm 1 — Dataset construction pipeline (compact form)"));
[
  "Input:  H = hydrological information system endpoint",
  "        E = state-level DEM tiles",
  "        B = pilot-basin configuration (name, region code, bbox, target grid)",
  "        [t0, t1] = reference reporting window",
  "Output: T_H, T_C = canonical time-series tables (hydrometric, climatological)",
  "        S_H, S_C, X_H = station manifests (main, main, extended hydrometric)",
  "        D_b, W_b = per-basin DEM and sub-basin polygon layer",
  "        F = model-ready feature table",
  "",
  "1. Catalog acquisition: fetch master catalogs from H; normalise headers; record provenance.",
  "2. Candidate selection: retain stations whose region code is in B  →  U_H, U_C.",
  "3. Time-series retrieval: for every k in U_H ∪ U_C fetch the daily record; register in manifest.",
  "4. Canonical schema and QC: for every series",
  "     parse (header/date variants) → rebuild daily index → replace sentinels →",
  "     flag physical outliers (calidad=2) → cubic-spline / linear gap imputation < 7 d (calidad=1) →",
  "     validate schema → persist T_H, T_C as year-partitioned Parquet.",
  "5. Per-basin DEM: for every b in B, mosaic state tiles ∩ bbox, clip, resample if needed  →  D_b.",
  "6. Delineation: for every b, run fill → flow direction → flow accumulation →",
  "     snap pour points → watershed on D_b, using the main hydrometric stations inside bbox;",
  "     vectorise, attach area / mean elevation / mean slope  →  W_b.",
  "7. Coverage refinement and features: cov_k = valid_days_k / (t1 − t0 + 1).",
  "     S_H = {cov ≥ 0.60}, S_C = {cov ≥ 0.80}, X_H = {0.30 ≤ cov < 0.60}.",
  "     For every k in S_H pick the 3 nearest neighbours in S_C by great-circle distance.",
  "     Compute per-station lags L1, L3, L7, L14, L30 and rolling means M7, M30 on streamflow  →  F.",
].forEach((line) => children.push(code(line)));
children.push(blank());

// Optional external map suggestion
children.push(p(
  "As an optional visual aid before the delineation figures, an official map of the Mexican hydrological regions published by the national provider could be reproduced (with attribution) at the beginning of this section: it makes the geographic scope of regions 12, 18 and 26 immediately readable, and provides context for the delineated sub-basins delivered by the pipeline.",
  { italics: true, size: 20 }
));

// ---- Stages ----
children.push(h2("Stage 1 — Catalog acquisition"));
children.push(p(
  "The pipeline is initialised by retrieving the two master catalogs published by the primary hydrological information system, one for the population of hydrometric stations and one for the population of climatological stations. Both catalogs are streamed over HTTPS with a persistent requests session and a bounded read timeout; each retrieved file is written to disk and its SHA-256 hash is computed on the fly. A JSON provenance manifest is written next to the catalogs and records, for every retrieved file, the source URL, byte size, hash and UTC timestamp of retrieval. Header names are normalised (case-folding and diacritic stripping with unicodedata) and mapped to a canonical column set covering the station identifier, name, latitude, longitude, altitude, state, municipality, hydrological region code and basin. Numeric fields are coerced with pandas.to_numeric under an explicit NaN policy."
));

children.push(h2("Stage 2 — Candidate-station selection"));
children.push(p(
  "The two master catalogs are filtered with pandas boolean indexing by hydrological region, using the reference list declared in the pilot-basin configuration and retaining every station whose region code matches. The resulting candidate universes are persisted as CSV files and act as the driver of the retrieval stage: every station downloaded downstream is a member of these universes."
));

children.push(h2("Stage 3 — Time-series retrieval"));
children.push(p(
  `The full historical daily record of every candidate station is retrieved from the primary hydrological information system, one file per station. Because the provider protects its portal with a web-application firewall that reacts to sustained parallelism by challenging or blocking client IPs, the retrieval respects two configurable knobs: a bounded ThreadPoolExecutor (default 16 workers) and a per-request idle interval (default 0 seconds) applied only after a real network fetch. For the release described in this article the retrieval was completed at one worker with a five-second interval between fetches from a mobile-tethered network. Every retrieved file is registered in the provenance manifest introduced in Stage 1 with the same four fields. Individual retrieval failures are retried three times with exponential back-off and, if unrecoverable, are logged and excluded from later stages. Fig. 2 shows the spatial distribution of the ${N_SEL} selected hydrometric stations that ultimately reached the coverage threshold applied in Stage 7.`
));
children.push(...figure("fig5_mapa.png",
  "Fig. 2. Spatial distribution of the selected hydrometric stations by hydrological region.",
  380, 0.85));

children.push(h2("Stage 4 — Canonical schema and quality control"));
children.push(p(
  "The raw records ingested in Stage 3 are heterogeneous: the provider distributes at least two header variants (\"Fecha,…\" and \"Estacion,Fecha,…\") and two date formats (\"YYYY/MM/DD\" and \"YYYY-MM-DD\") across its station families, and represents missing values as either an explicit dash character or as an empty field. A permissive parser (pandas.read_csv with na_values, followed by pandas.to_datetime in mixed-format mode) locates the header line by searching for \"Fecha\" as a comma-separated token and normalises column labels to the canonical schema. For every station the following transformations are applied in order: the daily index is rebuilt as a continuous calendar so that structural absences are not confused with observational absences; sentinel encodings of missing values are replaced by NaN; a physical range check flags negative flows and outliers above three times the 99.9-th percentile of the local distribution as quality = 2 (retained); internal gaps shorter than seven days are imputed by cubic-spline interpolation, falling back to linear interpolation on segments where the spline is not numerically well-posed, and marked as quality = 1. The output is validated with pandera against a strict schema (column set, dtypes, physical bounds, allowed labels) and persisted with pyarrow as a year-partitioned Parquet directory (Snappy compression). Fig. 3 gives the resulting composition of the quality flag over the delivered hydrometric records."
));
children.push(...figure("fig3_calidad.png",
  "Fig. 3. Composition of the three-valued quality flag over the delivered hydrometric records.",
  360, 0.72));

children.push(h2("Stage 5 — Digital elevation model preparation per basin"));
children.push(p(
  "The primary provider distributes the national digital elevation model as state-level tiles. For every pilot basin the pipeline selects the tiles whose extents intersect its curated bounding box (extents reprojected to EPSG:4326 with rasterio.warp.transform_bounds), mosaics them with rasterio.merge, and clips the mosaic to the basin bounding box with rasterio.mask against a shapely.geometry.box; the intermediate is held in a rasterio MemoryFile to avoid file locks. When the resolution of the source tiles differs from the resolution requested for the basin, the raster is resampled with rasterio.warp.reproject using an affine scaled by the resolution ratio and the Resampling.average kernel when it is coarsened, or Resampling.bilinear when it is refined. The result is stored as a LZW-compressed, tiled GeoTIFF. In the release described in this article, five basins are delivered at 30-metre resolution and one basin (Alta del Balsas) at 15-metre resolution."
));

children.push(h2("Stage 6 — Watershed delineation"));
children.push(p(
  `For every pilot basin, the hydrometric stations of the main selection that lie inside its bounding box are used as the pour points of a raster-based delineation over the basin elevation model. The chain consists of fill_depressions → d8_pointer → d8_flow_accumulation → extract_streams (accumulation threshold in cells) → snap_pour_points (snap distance in map units) → watershed, executed through the whitebox binding of WhiteboxTools. The output is vectorised with geopandas and per-polygon attributes are computed by zonal statistics on the elevation model (area in km², mean elevation, mean slope) and written to a per-basin GeoPackage. To keep the memory budget of the delineation compatible with a workstation-class machine, the historical Lerma–Santiago region is delivered as three operational sub-basins (Lerma Alto, Bajío and Santiago). Fig. 4 shows the resulting layer with all ${N_SUB} delineated sub-basins and the ${N_SEL} pour points.`
));
children.push(...figure("fig8_cuencas_subcuencas.png",
  "Fig. 4. Delineated sub-basins across the six pilot basins with the hydrometric pour points.",
  460, 0.85));

children.push(h2("Stage 7 — Coverage refinement and feature engineering"));
children.push(p(
  "The last stage applies to the canonical time-series tables the coverage criterion used downstream. Per-station coverage is computed as the fraction of non-missing daily observations of the target variable inside the reference window (streamflow for hydrometric stations, precipitation for climatological stations). Two per-type thresholds define the main sets (0.60 for hydrometric stations, 0.80 for climatological stations); a lower threshold (0.30) defines an extended set of hydrometric stations released for sensitivity and reconstruction studies. Every selected hydrometric station is paired with the three closest climatological stations by great-circle distance (haversine formula with R = 6371 km). Finally, per-station lagged streamflow features L1, L3, L7, L14, L30 and rolling means M7 and M30 are computed with pandas groupby / shift / rolling and persisted as a flat Parquet table that preserves the quality flag inherited from the canonical hydrometric table."
));

// --- Descriptive analysis of the delivered dataset ---
children.push(h2("Descriptive analysis of the delivered dataset"));
children.push(p(
  "Figs. 5 to 8 report descriptive summaries of the delivered dataset. Fig. 5 shows the inventory and coverage distribution of the hydrometric stations. Fig. 6 shows the distribution of streamflow by hydrological region. Fig. 7 shows the aggregate monthly climatology and the annual mean streamflow across all hydrometric stations. Fig. 8 shows the lagged correlation between the aggregate national precipitation and streamflow series."
));

children.push(...figure("fig1_inventario_cobertura.png",
  "Fig. 5. Inventory of hydrometric stations per hydrological region (left) and coverage distribution over the reference window (right).",
  540, 0.33));

children.push(...figure("fig2_descriptiva.png",
  "Fig. 6. Daily mean streamflow by hydrological region, log-scaled y-axis.",
  460, 0.47));

children.push(...figure("fig6_temporal.png",
  "Fig. 7. Monthly climatology (left) and annual mean (right) of the daily mean streamflow.",
  540, 0.33));

children.push(...figure("fig7_precip_gasto.png",
  "Fig. 8. Lagged Pearson correlation between the daily national means of precipitation and streamflow.",
  460, 0.48));

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
[
  "Daniel Sánchez-Ruiz: Conceptualization, Methodology, Software, Data curation, Formal analysis, Visualization, Writing – Original draft, Project administration, Funding acquisition.",
  "Cecilia Reyes-Peña: Methodology, Validation, Writing – Review & Editing.",
  "Lauro Reyes-Cocoletzi: Software, Validation, Writing – Review & Editing.",
  "Jesús García-Ramírez: Methodology, Formal analysis, Writing – Review & Editing.",
  "Eric Ramos-Aguilar: Investigation, Resources, Writing – Review & Editing.",
  "Ricardo Ramos-Aguilar: Supervision, Resources, Writing – Review & Editing.",
].forEach((t) => children.push(bullet(t)));

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
  "Confirmar con cada coautor la asignación específica de roles CRediT propuesta en el manuscrito.",
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
  "El borrador con figuras reales, DOI de Zenodo (10.5281/zenodo.21231601), CRediT completo y coherencia entre snapshot y manuscrito está listo para revisión interna. El único pendiente restante es completar la lista final de referencias bibliográficas."
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

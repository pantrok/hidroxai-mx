"""Pruebas offline de los parsers del SIH (formato real reproducido en miniatura)."""

import pandas as pd

from hidroxai_mx.io import conagua

HID = """Comisión Nacional del Agua
Subdirección General Técnica
Estación: Abasolo
Clave: ABSTP
Estado: Tamaulipas
Municipio: Abasolo

Fecha, Nivel(m), Gasto(m³/s)
2010/01/01,23.00,-
2010/01/02,-,1.50
"""

CLI = (
    "Comisión Nacional del Agua\n"
    "Subdirección General Técnica\n"
    "Estación: Abasolo\n"
    "Clave: ABASOLO\n"
    "Estado: Tamaulipas\n"
    "Municipio: Abasolo\n\n"
    "Fecha,Precipitación(mm),Temperatura Media(ºC),Temperatura Máxima(ºC),"
    "Temperatura Mínima(ºC),Evaporación(mm)\n"
    "2010/01/01,0.00,19.7,26.3,15.7,\n"
    "2010/01/02,3.40,-,-,-,\n"
)

CLI_ESTACION_FECHA = """Comision Nacional del Agua
Subdireccion General Tecnica
Estacion: Aguascalientes, Ags.
Clave: AGSAG

Estacion,Fecha,TempMax(C),Precipitacion(mm),TempMin(C),Evaporacion(mm),TempAmb(C)
AGSAG,2010-01-01,26.3,0.0,15.7,4.2,19.7
AGSAG,2010-01-02,-,3.4,-,-,-
"""

CAT_HID = (
    "Clave,Nombre de la estaci\xf3n,Latitud,Longitud,Altitud,Estado,Municipio,R.H.,Cuenca\n"
    'ABSTP,"Abasolo",24.05,-98.37,100,Tamaulipas,Abasolo,26,Panuco\n'
)
CAT_CLI = (
    "N\xfamero,Clave ,Nombre,Latitud,Longitud,Altitud,Estado,Municipio,Id,Cuenca de disponibilidad,"
    "N\xfamero de la regi\xf3n hidrol\xf3gica,Regi\xf3n hidrol\xf3gica\n"
    "1,C01001,Aguascalientes,21.85,-102.29,1891,Ags,Ags,191,Presa,12,Lerma Santiago\n"
)


def test_series_hidro(tmp_path):
    p = tmp_path / "ABSTP.csv"
    p.write_text(HID, encoding="latin-1")
    df = conagua.read_series_csv(p)
    assert {"fecha", "nivel_m", "gasto_medio_m3s", "clave_estacion"} <= set(df.columns)
    assert df["clave_estacion"].iloc[0] == "ABSTP"
    assert pd.isna(df["gasto_medio_m3s"].iloc[0])  # "-" -> NaN
    assert abs(df["gasto_medio_m3s"].iloc[1] - 1.5) < 1e-9


def test_series_clima(tmp_path):
    p = tmp_path / "ABASOLO.csv"
    p.write_text(CLI, encoding="latin-1")
    df = conagua.read_series_csv(p)
    assert {"precip_mm", "tmax_c", "tmin_c", "tmed_c"} <= set(df.columns)
    assert abs(df["tmax_c"].iloc[0] - 26.3) < 1e-9


def test_series_clima_estacion_fecha_and_hyphen_dates(tmp_path):
    p = tmp_path / "AGSAG.csv"
    p.write_text(CLI_ESTACION_FECHA, encoding="latin-1")
    df = conagua.read_series_csv(p)
    assert {"fecha", "precip_mm", "tmax_c", "tmin_c", "tmed_c", "evap_mm"} <= set(df.columns)
    assert len(df) == 2
    assert df["fecha"].iloc[0] == pd.Timestamp("2010-01-01")
    assert abs(df["precip_mm"].iloc[1] - 3.4) < 1e-9
    assert abs(df["tmed_c"].iloc[0] - 19.7) < 1e-9


def test_catalog_region(tmp_path):
    ph = tmp_path / "h.csv"
    ph.write_text(CAT_HID, encoding="latin-1")
    dh = conagua.read_catalog(ph)
    assert dh["region_hidrologica"].iloc[0] == "26"
    assert abs(dh["latitud"].iloc[0] - 24.05) < 1e-9
    pc = tmp_path / "c.csv"
    pc.write_text(CAT_CLI, encoding="latin-1")
    dc = conagua.read_catalog(pc)
    assert dc["region_hidrologica"].iloc[0] == "12"
    assert dc["clave"].iloc[0] == "C01001"


def test_series_url():
    assert conagua.series_url("hidrometricas", "ABSTP").endswith("/Hidros/ABSTP.csv")
    assert conagua.series_url("climatologicas", "C01001").endswith("/Climas/C01001.csv")

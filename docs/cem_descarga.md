# CEM por cuenca — flujo de descarga y recorte

El portal CEM 3.0 de INEGI (`https://www.inegi.org.mx/temas/relieve/continental/`)
sirve descargas **por entidad federativa**, con archivos GeoTIFF fijos. Esta es la
ruta práctica para HidroXAI-MX: descargas una vez los estados que cubren las
cuencas piloto y un script Python hace el mosaico y el recorte al bbox de cada
cuenca (los bboxes están en `conf/cuencas_piloto.yaml`).

> No usamos la opción "Por área geográfica" del portal porque obliga a dibujar la
> selección a mano y produce recortes irreproducibles.

## 1. Qué estados descargar

Corre:

```bash
python scripts/06b_build_cem_per_basin.py --list-states
```

Imprime, por cuenca y resolución, los estados que debes descargar. A junio 2026:

| Cuenca | Resolución | Estados sugeridos |
|---|---|---|
| Cutzamala | 30 m | México, Michoacán, Guerrero |
| Lerma-Santiago | 30 m | Jalisco, Guanajuato, Michoacán, Querétaro, México, Aguascalientes, Zacatecas, San Luis Potosí, Nayarit |
| Pánuco | 30 m | San Luis Potosí, Tamaulipas, Hidalgo, Veracruz, Querétaro, México, Puebla, Tlaxcala |
| Alta del Balsas | 15 m | Morelos, Puebla, Tlaxcala, México, Guerrero, Oaxaca |

## 2. Dónde dejar los TIFFs

Guarda los archivos así (el nombre del `.tif` es libre — el portal INEGI los nombra
por código de entidad federativa, p.ej. `15_México_r15m_v4.tif`):

```
data/scratch/
├── 30m/
│   ├── 15_México_r30m_v4.tif
│   ├── 16_Michoacán_r30m_v4.tif
│   └── ...
└── 15m/
    ├── 17_Morelos_r15m_v4.tif
    ├── 21_Puebla_r15m_v4.tif
    └── ...
```

Solo necesitas la subcarpeta de la resolución que descargaste. Si el portal solo te
permitió descargar 15m, deja todo en `data/scratch/15m/` y el script hará fallback
automático (usará los 15m incluso para cuencas que pidan 30m, con un warning).

`data/scratch/` está fuera de DVC y fuera del guardarraíl de `08_storage_report`,
así que los TIFFs estatales (200–400 MB c/u a 30m; ~4x más a 15m) **no se suben a
R2**.

## 3. Mosaico + recorte por cuenca

```bash
python scripts/06b_build_cem_per_basin.py
```

Para cada cuenca el script:
1. Lista los TIFFs en `data/scratch/cem_estados/<resolución>m/`.
2. Filtra los que intersectan el `bbox` curado de la cuenca.
3. Hace `rasterio.merge` + `rasterio.mask` con ese bbox.
4. Escribe `data/raw/inegi/cem_<slug>.tif` (comprimido LZW, tiled).

Tras esto, `scripts/06_delineate_basins.py` puede correr la delineación normal.

## 4. Re-generar o forzar

```bash
python scripts/06b_build_cem_per_basin.py --overwrite     # regenera todos
```

Si cambias el `bbox` en `conf/cuencas_piloto.yaml`, vuelve a correr el script
con `--overwrite` para que el CEM por cuenca se ajuste al bbox nuevo.

## 5. Impacto en R2

- `data/scratch/cem_estados/*.tif` → **no versionados** (gitignore + fuera de DVC + ignorados por 08).
- `data/raw/inegi/cem_<cuenca>.tif` → versionables manualmente con `dvc add` si quieres
  congelarlos al snapshot. Tamaño esperado: 50–400 MB por cuenca, < 1 GB total.

Mantén siempre el chequeo previo:

```bash
python scripts/08_storage_report.py   # debe quedar < 9.5 GB
```

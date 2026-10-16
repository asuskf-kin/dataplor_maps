# Mapas y presentación de prospección

Pipeline de Kin Analytics para los resultados de prospección digital (Dataplor) de los bottlers de Coca-Cola.
Con un mercado (`<pais>/<region>`, por ejemplo `mx/Golfo`) genera:

1. **QA** del algoritmo de match: falsos negativos, categorías y comparación con el benchmark del mercado.
2. **Mapas interactivos** en HTML (versión completa para el bottler y versión anonimizada para KO).
3. **Deck de Prospección Digital** en Claude Design (22 diapositivas, según la plantilla oficial).
4. **Entregables CSV** con prioridad 1–6 para el bottler y para KO.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.14 solo, según `.python-version`)
- Google Chrome (solo para `deck_preview.py --png`)

```bash
uv sync
```

Después, cada script se corre con `uv run`, por ejemplo `uv run python src/qa.py mx/Golfo`. En los ejemplos de
abajo `python` equivale a `uv run python`. Sin uv: `pip install -r requirements.txt`.

En Windows conviene definir `PYTHONIOENCODING=utf-8` para que los acentos salgan bien en la consola.

## Estructura

```
.
├── src/                    # Scripts del pipeline
│   ├── common.py           # Utilidades compartidas (lectura, columnas, prioridad, paleta Kin)
│   ├── qa.py               # Paso 1: QA
│   ├── mapa.py             # Paso 2: mapas interactivos (BOTTLER / KO)
│   ├── mapa_template.html  # Plantilla HTML del mapa
│   ├── mapa_png.py         # Imagen estática del mapa (diapositiva 14)
│   ├── deck_data.py        # Paso 3: cifras del deck → deck_data.json
│   ├── deck_slides.py      # Paso 3: genera las 22 diapositivas (formato Claude Design)
│   ├── deck_preview.py     # Paso 3: vista previa local (PNG por diapositiva)
│   └── entregables.py      # Paso 4: CSV de entregables
├── .claude/skills/         # Skills de Claude Code (QA, mapa, deck, marca Kin)
├── data/                   # Entradas (no se versionan, salvo data/templates/assets/)
│   └── <pais>/<region>/
│       ├── clientes/       # Maestra de clientes (alias: Clients/, Maestra/)
│       ├── datamatch/      # Salida del algoritmo de match
│       ├── priority/       # Base Priority de Dataplor
│       ├── geo_alias.json  # Opcional: une ciudades equivalentes
│       └── exclusiones.csv # Opcional: falsos negativos a quitar
├── output/<pais>/<region>/ # Salidas (no se versionan)
└── CLAUDE.md               # Instrucciones del pipeline para Claude Code
```

## Uso

Todos los comandos se corren desde la raíz del repositorio. `<mercado>` es `<pais>/<region>`, entre comillas
si tiene espacios (`"mx/Centro Pacifico"`).

### 1. QA

```bash
python src/qa.py mx/Golfo
```

Genera `qa_report.html` y los mapas de QA en `output/<mercado>/qa/`. Si no existe un benchmark de penetración
del mercado, guárdalo en `output/<mercado>/qa/benchmark.json` y vuelve a correr con `--benchmark <ruta>`.
Opciones: `--clientes`, `--datamatch`, `--threshold` (por defecto 0.65).

Revisa el reporte antes de seguir. Los falsos negativos confirmados van a `data/<mercado>/exclusiones.csv`
(`dataplor_id,nombre,motivo`) y se quitan del mapa, del deck y de los entregables.

### 2. Mapas

```bash
python src/mapa.py mx/Golfo --cliente-nombre "Bepensa"
python src/mapa_png.py mx/Golfo
```

- `*_BOTTLER.html`: completo.
- `*_KO.html`: nombres anonimizados ("POI n", el mismo `poi_ref` del CSV de KO, y "Cliente n") y sin direcciones.
  Si se cuela algún nombre real, la corrida aborta.

El script imprime los breaks de la escala; para cambiarlos usa `--breaks`. Otras opciones: `--res` (resolución H3,
por defecto 8), `--fit`, `--version {both,bottler,ko}`.

### 3. Deck

```bash
python src/deck_data.py mx/Golfo --portafolio <total_maestra>
```

Requiere que la base Priority tenga `probability_existence_cat`, `channel_cat`, `business_category` y `city`.
Revisa las cifras de `output/<mercado>/deck/deck_data.json` antes de armar el deck.

1. Escribe `output/<mercado>/deck/meta.json` con textos, insights y glosario (copia el de un mercado parecido).
2. Crea el artifact Slides en Claude Design, súbele los assets de `data/templates/assets/` más el mapa del mercado,
   y guarda las URLs en `assets.json`.
3. Genera las diapositivas:
   ```bash
   python src/deck_slides.py --data output/mx/Golfo/deck/deck_data.json --meta output/mx/Golfo/deck/meta.json --assets output/mx/Golfo/deck/assets.json --out output/mx/Golfo/deck/slides
   ```
4. Revísalas en local (un PNG por diapositiva y `contact.png`):
   ```bash
   python src/deck_preview.py --root output/mx/Golfo/deck/slides --assets output/mx/Golfo/deck/assets.json --local output/mx/Golfo/deck/assets_local.json --png output/mx/Golfo/deck/png
   ```
5. Publica `project/deck.json` y la portada, y luego el resto de las diapositivas.

El deck sigue siempre la plantilla `Plantilla_Prospeccion_Digital_v2.pptx`. Las reglas aprendidas de las ediciones
están en [.claude/skills/prospeccion-digital/references/aprendizajes.md](.claude/skills/prospeccion-digital/references/aprendizajes.md).

### 4. Entregables CSV

```bash
python src/entregables.py mx/Golfo --sufijo 202610
```

- Prioridad 1–6: primero el área (dentro → fuera), luego la existencia (High → Moderate → Low).
- Los archivos empiezan por `Dataplor_on_premise_priority`.
- `_BOTTLER.csv`: todas las columnas, con coordenadas.
- `_KO.csv`: sin coordenadas, nombre, contacto ni columnas `ref_`.

## Notas

- Las carpetas de datos se reconocen sin distinguir mayúsculas, y las columnas de coordenadas (`Coord_Y`/`Coord_X`,
  `lat`/`lon`…) se detectan solas.
- Si la base Priority no trae `match_no_match` (solo no-match), el total de match se toma del datamatch.
- Los mapas usan los tiles de Esri Canvas (los de CARTO piden API key).

## Datos y confidencialidad

`data/` y `output/` contienen información de clientes y no se suben al repositorio (ver `.gitignore`).
Solo se versionan los assets gráficos de `data/templates/assets/`. Para trabajar un mercado, copia sus datos
a `data/<pais>/<region>/` en tu equipo.

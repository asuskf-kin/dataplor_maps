---
name: prospeccion-digital
description: >
  Skill para generar presentaciones de Prospección Digital de KinAnalytics como deck de
  Claude Design (artifact Slides con el Kin Design System). Úsalo SIEMPRE que el usuario
  quiera crear, generar o actualizar una presentación de prospección digital, análisis de Priority,
  resultados de Dataplor, o cualquier entregable de presentación para embotelladores
  (Femsa, Arca, OXXO, etc.). También activa cuando el usuario mencione "base de Priority",
  "maestra de clientes", "prospección", "no match", "match", "probability_existence_cat",
  "channel_cat", "business_category" en el contexto de una presentación. Este skill guía todo
  el proceso interactivo: hace preguntas al usuario, procesa la base de datos, arma tablas y
  gráficos y publica el deck como artifact de Claude Design (descargable como .pptx o PDF).
---

# Skill: Prospección Digital — Deck en Claude Design

Este skill genera la presentación de resultados de Prospección Digital a partir de una base de datos
de Priority. El entregable es un **artifact Slides de Claude Design** construido sobre el **Kin Design
System**: se presenta en el navegador y se descarga como .pptx o PDF desde el propio artifact.

| Recurso | Dónde |
|---|---|
| Tipo de artifact | **Slides**. Se obtiene con `Artifact` `action:"quickstart"`, `intent:"slides"` |
| Design system | **Kin Design System - Kin Official** (default de la organización): `https://claude.ai/artifact/Kyrvxqzwp78R1ZzWhrgBHK` |
| Reglas de marca | skill `brand-guidelines-kin` (`.claude/skills/brand-guidelines-kin/`) |
| Textos fijos del deck | `references/contenido-fijo.md` |
| Plantilla .pptx original | `assets/Plantilla_Prospección_Digital.pptx`: solo para consultar estructura, imágenes y el plan B |

---

## PASO 1 — Preguntas iniciales (OBLIGATORIO al arrancar)

Antes de hacer cualquier otra cosa, pregunta al usuario estas 5 cosas:

1. **¿En qué país se realiza el ejercicio?**  
   (Ejemplo: Nicaragua, Guatemala, México, Honduras…)

2. **¿Cuál es la embotelladora?**  
   (Ejemplo: Femsa, Arca, OXXO, Coca-Cola FEMSA…)

3. **¿Cuándo fue entregada la base de clientes (maestra de clientes)?**  
   (Ejemplo: "Abril 2026", "Marzo 2026"…)

4. **¿Quién hizo la entrega de la base de clientes?**  
   Opciones: `"por embotelladora"` o `"por NSR"`

5. **¿Cuántos clientes tiene la maestra del embotellador (total de registros en la base de clientes)?**  
   (Ejemplo: 45.164 — este número NO se puede calcular desde la base de Priority, debe ser confirmado por el usuario)

Una vez respondidas, pide la **base de datos de Priority** (archivo CSV o Excel).

> ⚠️ **IMPORTANTE**: El total de clientes del embotellador (pregunta 5) es un dato externo que **no coincide necesariamente** con el conteo de `match` en la base de Priority. Siempre usar el número confirmado por el usuario para la diapositiva 9 y para los % de la diapositiva 15.

---

## PASO 2 — Cargar y analizar la base de Priority

La base de Priority debe contener al menos estas columnas clave:

| Columna | Descripción |
|---|---|
| `match_no_match` | Valores: `match` o `no_match` |
| `probability_existence_cat` | Valores: `High`, `Moderate`, `Low` |
| `channel_cat` | Valores: `On Premise`, `Off Premise` |
| `business_category` | Categoría del negocio |
| `city` | Ciudad del punto |

Si falta alguna, preguntar al usuario cuál columna equivalente usar.

```python
import pandas as pd

df = pd.read_csv("base_priority.csv")  # o read_excel según el formato

# Diapositiva 9 — totales
total_dataplor     = len(df)
total_embotellador = TOTAL_CONFIRMADO_POR_USUARIO   # pregunta 5
no_match = df[df['match_no_match'] == 'no_match']
high_count     = (no_match['probability_existence_cat'] == 'High').sum()
moderate_count = (no_match['probability_existence_cat'] == 'Moderate').sum()
low_count      = (no_match['probability_existence_cat'] == 'Low').sum()
total_no_match = len(no_match)
total_match    = (df['match_no_match'] == 'match').sum()

# Segmento analizado en 10–15: no_match con High o Moderate
hm_nomatch = no_match[no_match['probability_existence_cat'].isin(['High', 'Moderate'])]

slide10 = hm_nomatch.groupby(['city', 'channel_cat']).size().unstack(fill_value=0)
slide11 = hm_nomatch.groupby(['business_category', 'channel_cat']).size().unstack(fill_value=0)
on_prem  = hm_nomatch[hm_nomatch['channel_cat'] == 'On Premise']
off_prem = hm_nomatch[hm_nomatch['channel_cat'] == 'Off Premise']

# Diapositiva 15 — etapas acumulativas (top 3, 5, 8, resto)
top_cities = hm_nomatch.groupby('city').size().sort_values(ascending=False)
top_cats   = hm_nomatch.groupby('business_category').size().sort_values(ascending=False)
def etapa(n):
    return hm_nomatch[hm_nomatch['city'].isin(top_cities.head(n).index) &
                      hm_nomatch['business_category'].isin(top_cats.head(n).index)]
e1, e3_5, e3_8 = len(etapa(3)), len(etapa(5)), len(etapa(8))
etapas = [e1, e3_5 - e1, e3_8 - e3_5, len(hm_nomatch) - e3_8]   # incrementales
# % de cada etapa y acumulado sobre total_embotellador
```

### Formato de números
Todos los números ≥ 1.000 usan **punto** como separador de miles (tablas, cifras y textos):
```python
def fmt(n):
    return f"{int(n):,}".replace(",", ".")
# 1129 → 1.129 | 3387 → 3.387
```

Muestra al usuario un resumen de las cifras clave (diap 9 y 15) y confirma antes de construir el deck.

> **Atajo / QA obligatorio:** si el repo tiene `src/deck_data.py`, córrelo en lugar de este código:
> `python src/deck_data.py <pais>/<region> --portafolio <total maestra>`. Es el port del notebook
> `ABI_Guatemala_Charts.ipynb` e imprime los chequeos de las diapositivas 9–15. Escribe
> `output/<pais>/<region>/deck/deck_data.json`, que es la única fuente de cifras para el deck.
> Sus definiciones replican la plantilla de referencia (ver abajo):
> - diap 7: umbrales reales de la base;
> - diap 10: ciudad × canal;
> - diap 11: top categorías High + Moderate por canal;
> - diap 12 y 13: `High | Moderate | Total` y top 2 ciudades;
> - diap 15: etapas top 3/5/8 ciudades × categorías.

> ⛔ **Antes de empezar, lee `references/aprendizajes.md`.** Recoge lo que el usuario corrigió a mano:
> - la plantilla manda sobre la skill de marca ("Let knowledge in" sí va);
> - sin datos Off Premise no hay diapositiva Off Premise;
> - impacto con dentro/fuera y captura neta al 50–70 %;
> - mapa estilo Kepler;
> - contactos vigentes.
> Donde contradiga algo de este archivo, manda `aprendizajes.md`.
>
> ⛔ **Diseño:** la plantilla vigente es `data/templates/Plantilla_Prospeccion_Digital_v2.pptx`, publicada en Claude
> Design como https://claude.ai/artifact/Eagmk8BE2pDi61CWFeVf4R.
> - Las diapositivas se generan con `src/deck_slides.py`, a partir de `deck_data.json`, `meta.json` y `assets.json`.
> - La revisión visual se hace con `src/deck_preview.py --png`. Los pasos completos están en CLAUDE.md.
> - No escribir diapositivas a mano.
>
> ⛔ **Plantilla de referencia obligatoria:** `data/templates/Prospeccion_Digital_Republica_Dominicana_Bepensa_Junio_2026.pptx`
> (22 diapositivas). El deck sigue su orden, sus títulos, sus textos y sus tablas, y reutiliza sus fotos.
> - **Nunca reorganizar** las diapositivas por otro eje (por ejemplo, área dentro/fuera). Ese dato va solo en un insight.
> - Si un bloque no tiene datos (por ejemplo, Off Premise = 0), su diapositiva y su panel se eliminan (aprendizajes.md).
> - Diapositiva 14: la imagen sale de `python src/mapa_png.py <mercado>`.

---

## PASO 3 — Crear el deck en Claude Design

Sigue **las instrucciones del tipo Slides** que llegan al crear el artifact; esas mandan sobre el
formato de los archivos. Este paso solo fija las decisiones de este skill.

1. **Quickstart:** `Artifact` `action:"quickstart"`, `intent:"slides"`. Devuelve el `type_url` del
   tipo Slides y el design system por defecto.
2. **Crear el artifact:** publica con ese `type_url`, sin archivos, con
   `title: "Prospección Digital — {PAIS} {EMBOTELLADORA} — {MES_ANO}"` y
   `auto_open: "after_first_write"`. Desde ahí, usa siempre el `url` que devuelve. Nunca crees un segundo deck.
3. **Design system:** el **Kin Design System - Kin Official**
   (`https://claude.ai/artifact/Kyrvxqzwp78R1ZzWhrgBHK`). **Instálalo** en el deck como indica el tipo
   (registro en `designSystems` y `project/ds/<folder>/tokens.json` copiado del sistema). Copia también
   sus fuentes (Space Grotesk y Albert Sans) y sus archivos de logo con entradas
   `{"artifact": …, "path": …}`. Así los logos se colocan desde archivo y nunca se dibujan.
4. **Lee `references/contenido-fijo.md`** para los textos que no cambian.
5. Escribe `project/deck.json` (con el `order` completo y las secciones), luego la portada, y después
   las demás diapositivas de tres en tres, como indica el tipo.
6. Al terminar, comparte el link del artifact. **No verifiques el deck** (no lo releas ni lo
   renderices) salvo que el usuario lo pida.

### Reglas Kin para todas las diapositivas
Las da el design system y la skill `brand-guidelines-kin`. Las críticas para este deck:

- **Colores solo de los tokens del sistema.** Black `#141417`, Gray 4 `#222326`, Gray 3 `#999EA6`,
  Gray 2 `#D4D5D6`, Gray 1 `#EFEFEE`, White y Kin Yellow `#E5FF01`. El Yellow se usa como acento
  (≈3 %) y **nunca como texto sobre fondo claro**. Nada de gradientes, azules, naranjas ni lima.
- **Tipografía:** Space Grotesk en títulos, números y cifras; Albert Sans en el cuerpo, las tablas y
  los labels.
- **Ritmo claro/oscuro:**
  - fondo oscuro: portada, divisores y cierre;
  - fondo claro: contenido, tablas y gráficos.
- **Footer en las diapositivas de contenido:** wordmark formal "Kin Analytics" desde archivo abajo a
  la izquierda y `kinanalytics.com` en minúsculas abajo a la derecha. No va en la portada, en los
  divisores ni en el cierre.
- **Portada:** marca `Kin Analytics© {AÑO}` + `CONFIDENTIAL` abajo a la derecha, solo ahí. El bloque
  de título (eyebrow, título, subtítulo y metadatos) es un solo contenedor.
- **Divisores:** número `01`, `02`… con el título en Space Grotesk y el acento amarillo en forma de
  punta de hexágono, nunca una franja. El logo va desde archivo.
- **Tagline:** en este deck **sí** va "Let knowledge in", como en la plantilla: pie, portada y cierre (aprendizajes.md).
- **Hexágonos:** solo desde los archivos del sistema, uno o dos por diapositiva como acento, nunca
  como patrón de fondo.
- **Cajas:** esquinas de 12px, padding generoso y altura automática.

---

## PASO 4 — Contenido por diapositiva

Orden del deck (22 diapositivas, ids sugeridos entre paréntesis). Las marcadas **FIJA** copian el
texto de `references/contenido-fijo.md`.

| # | id | Diapositiva | Tipo |
|---|---|---|---|
| 1 | `cover` | Portada | Variable |
| 2 | `agenda` | Contenido | FIJA |
| 3 | `objetivo` | Objetivo del proyecto + cifras | FIJA |
| 4 | `ciclo` | Ciclo de vida del proyecto | FIJA |
| 5 | `proceso` | Detalles del proceso | Variable (1 texto) |
| 6 | `algoritmo` | Lógica del algoritmo | FIJA |
| 7 | `priorizacion` | Sistema de priorización | FIJA |
| 8 | `div-resultados` | Divisor "Resultados" | FIJA |
| 9 | `resumen` | Resumen por potencial de existencia | Variable |
| 10 | `ciudad-canal` | Resumen por ciudad y canal | Variable |
| 11 | `categoria-canal` | Por categoría y canal | Variable |
| 12 | `on-premise` | Detalle On Premise | Variable |
| 13 | `off-premise` | Detalle Off Premise | Variable |
| 14 | `mapa` | Mapa de concentración | Variable + imagen manual |
| 15 | `impacto` | Impacto del proyecto por etapas | Variable |
| 16 | `div-pasos` | Divisor "Siguientes pasos" | FIJA |
| 17 | `pasos` | Próximos pasos | FIJA |
| 18 | `div-datos` | Divisor "Vista previa a los datos" | FIJA |
| 19–21 | `glosario-1..3` | Glosario | FIJA + captura manual |
| 22 | `cierre` | Contactos | FIJA |

Secciones (`sections`): Introducción (1–7) · Resultados (8–15) · Siguientes pasos (16–17) · Datos (18–22).

### 1 — Portada
Eyebrow `PROSPECCIÓN DIGITAL`, título `Prospección Digital` y subtítulo `{PAIS} - {EMBOTELLADORA}`.
La fecha es el mes actual en español (`datetime.now()`, p. ej. "Mayo 2026").

### 5 — Detalles del proceso
El paso 2 del flujo dice:
`Maestra de clientes - {EMBOTELLADORA} {PAIS} ({MES_ENTREGA} compartida por {QUIEN_ENTREGO})`.
`{QUIEN_ENTREGO}` vale `embotelladora` o `NSR`.

### 9 — Resumen de resultados
- Eyebrow `PROSPECCIÓN DIGITAL` y título "Resumen de resultados por potencial existencia".
- Texto de "Punto de partida" (de la plantilla):
  > El análisis presentado tuvo en cuenta los departamentos clave de operación de la embotelladora,
  > así como los canales de distribución identificados Tradicional y Otros, y las categorías de
  > negocio que se exponen más adelante.
- Dos cifras grandes: **Dataplor** `{total_dataplor}` y **Embotellador** `{total_embotellador}`.
- Tabla No Match: High `{high}`, Moderate `{moderate}`, Low `{low}`, Total `{total_no_match}`.
- Banda de tres bloques de izquierda a derecha:
  - `{high} high & {moderate} moderate no-match` (High Confidence);
  - `{low} no-match` (Grey Area);
  - `{total_match} Match` (Match POS).
  El bloque High Confidence es el único con Yellow.

### 10 — Resumen por ciudad y canal
**Tabla** (no gráfico): `Ciudad | Off Premise | On Premise | Total`. Lleva el top 5 de ciudades, la
fila `Otros` y la fila **Total**. Texto:
> A continuación se presenta el potencial total identificado en la prospección digital, desglosado por
> ciudad y canal…

Cierra con: "Las 5 principales ciudades abarcan el {X}% del potencial total de High y Moderate
({total_HM_top5} potenciales nuevos POS)". Nota al pie: `* Total de High y Moderate No-Match points`.

### 11 — Por categoría y canal
**Dos gráficos de barras horizontales** lado a lado: On Premise (izquierda) y Off Premise (derecha),
cada uno con el top de `business_category` del segmento High+Moderate no_match. Texto:
"Para On Premise, {cat1} y {cat2} representan el {X}% del total de oportunidad del canal. En Off
Premise, {cat1} y {cat2} abarcan el {X}%."

### 12 y 13 — Detalle On Premise / Off Premise
**Dos tablas** por diapositiva, sin gráficos:
- Izquierda: `Business Category | High | Moderate | Total`, con el top 5, la fila `Others` y la fila Total.
  Subtítulo: "No Match - probabilidad de existencia".
- Derecha: `Business Category | Ciudad1 | Ciudad2 | Others | Total`, con las 2 ciudades principales
  **de ese canal** (pueden ser distintas en On y Off). Subtítulo: "Oportunidad por ciudad y potencial High/Moderate*".
- Texto con las 5 categorías y su % del canal, y con las 2 ciudades y su %.
- Nota: `*Para esta tabla se ha seleccionado las 5 categorías con mayor oportunidad con alta probabilidad de existencia (high y moderate no-match)`.

### 14 — Mapa
Título: "{CIUDAD_TOP} concentra la mayor cantidad de puntos con alta probabilidad de existencia", donde
`{CIUDAD_TOP}` es la ciudad con más puntos High+Moderate. El texto descriptivo usa esa misma ciudad.
La imagen del mapa **es manual**:
- Si el usuario tiene un mapa (por ejemplo de la skill `prospection-map` o de Kepler.gl), súbelo como
  asset y colócalo con `object-fit:contain`.
- Si no, deja un `<img>` sin `src`, con tamaño y un `alt` descriptivo, y avísalo.

### 15 — Impacto del proyecto
"De acuerdo a los datos y análisis mostrados, consideramos que se puede capturar valor para
{EMBOTELLADORA} de la siguiente manera:". Siguen 4 etapas, cada una con +POS incrementales, su % y el
% acumulado sobre `total_embotellador`:
1. Top 3 ciudades × top 3 categorías
2. Top 5 × top 5
3. Top 8 × top 8
4. El resto

Total: "+{total} nuevos puntos, equivalente a +{%} sobre el portafolio actual ({total_embotellador} POS)".
Nota al pie: `* Tomar en cuenta que, en las primeras iteraciones, los resultados pueden variar dependiendo del % de precisión del modelo, donde se estima que se consiga un 50%-70% de exactitud donde los POS no-match en cada etapa son encontrados y validados`.
Úsalo como roadmap con la etapa 1 resaltada en Yellow. El texto va alineado a la izquierda, nunca justificado.

---

## PASO 5 — Tablas y gráficos en formato Slides

El formato de las diapositivas acepta `<table>` y `<svg>` en línea (≤ 52 KB). Todos los estilos van
en línea, con colores hex o rgb y tamaños en px; el tipo no admite `var()`. Por eso los hex de abajo
salen de los tokens del Kin Design System instalado.

### Tablas (diap 9, 10, 12, 13)
- Encabezado (`<th>`): fondo Kin Yellow `#E5FF01`, texto Black `#141417`, Albert Sans 600.
- Fila Total: fondo Black `#141417`, texto White, números en Space Grotesk 700.
- Filas alternas: Gray 1 `#EFEFEE` / White; bordes de 1px Gray 2 `#D4D5D6`.
- Primera columna alineada a la izquierda; las demás centradas. Números en Space Grotesk.
- Tamaño de letra ≥ 24px (mínimo del formato). Si no entra, divide la diapositiva; no achiques la letra.

### Gráficos de barras (diap 11) — SVG generado en Python
```python
def svg_barras(datos, titulo, w=760, h=560):
    """datos: lista [(categoria, valor)] ya ordenada desc. Devuelve <svg> en línea."""
    YEL, BLK, G4, G3, G2 = '#E5FF01', '#141417', '#222326', '#999EA6', '#D4D5D6'
    n, top, left, bar_h, gap = len(datos), 72, 260, 40, 16
    vmax = max(v for _, v in datos) or 1
    out = [f'<svg aria-label="{titulo}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
           f'<text x="0" y="32" font-family="Space Grotesk" font-size="32" font-weight="500" fill="{BLK}">{titulo}</text>']
    for i, (cat, v) in enumerate(datos):
        y = top + i * (bar_h + gap); bw = (w - left - 120) * v / vmax
        out += [f'<text x="{left-16}" y="{y+bar_h*0.68}" text-anchor="end" font-family="Albert Sans" font-size="24" fill="{G4}">{cat}</text>',
                f'<rect x="{left}" y="{y}" width="{bw:.0f}" height="{bar_h}" rx="6" fill="{YEL}"/>',
                f'<text x="{left+bw+12:.0f}" y="{y+bar_h*0.68}" font-family="Space Grotesk" font-size="24" font-weight="700" fill="{G4}">{fmt(v)}</text>']
    out.append(f'<line x1="{left}" y1="{top-8}" x2="{left}" y2="{top+n*(bar_h+gap)}" stroke="{G2}" stroke-width="2"/></svg>')
    return ''.join(out)
```
- Serie única = Kin Yellow. Si dos series van juntas: On Premise Yellow y Off Premise Black.
  High / Moderate / Low = Yellow / Black / Gray 3.
- Las etiquetas de valor van en Gray 4, nunca en amarillo sobre fondo claro.
- Usa como máximo el top 8 por gráfico para que quepa con letra ≥ 24px.

---

## PASO 6 — Insights (agregar, no reemplazar)

El texto descriptivo de cada diapositiva se mantiene y el insight se **agrega** como un callout Kin:
una caja Gray 1 `#EFEFEE`, una barra de acento Kin Yellow de 6px a la izquierda, texto Gray 4 en
Albert Sans, 12px de radio y altura automática. Va en las diapositivas 9, 10, 11, 12, 13, 14 y 15. Si
no cabe, divide la diapositiva antes que achicar el texto.

El insight debe: (1) señalar algo no obvio, (2) tener implicación comercial clara, (3) NO ser una explicación de la tabla.

| ❌ Descripción | ✅ Insight |
|---|---|
| "Restaurant y hotel representan el 42%" | "Solo 2 categorías capturan >40% en ambos canales — estrategia focalizada captura mitad del potencial con esfuerzo mínimo" |
| "Caracas tiene el 17% del potencial" | "55% del potencial está fuera del top 5 — mercados secundarios desatendidos de alta densidad comercial" |
| "Valencia supera a Caracas Off Premise" | "Valencia supera a Caracas Off Premise — hallazgo contraintuitivo que señala mayor densidad de puntos alternativos en secundarios" |

---

## PASO 7 — Entrega

1. Comparte el **link del artifact**. El deck se presenta en el navegador y se descarga como
   **.pptx o PDF** desde el propio artifact (Share › Export).
2. Avisa de las **acciones manuales pendientes**:
   - **Diapositiva 14 (mapa):** subir la imagen del mapa si no se colocó.
   - **Diapositivas 19–21 (glosario):** reemplazar los espacios de captura con imágenes de la base real que se va a entregar.
   - **Diapositiva 22 (contactos):** revisar los correos (`paula.lara@`, `david.farinango@`, `nicolas.ayala@kinanalytics.com`).
3. Lista los valores entre corchetes `[ ]` que hayan quedado sin dato.

---

## Notas importantes

- **Siempre usar "ciudad"** en lugar de "departamento" en los textos de las diapositivas 10, 12, 13 y 14.
- **El segmento analizado siempre es**: `no_match` con `probability_existence_cat` en `High` o `Moderate`.
- Nunca inventar una cifra ni una cita. Si falta un dato, usa un placeholder entre corchetes y menciónalo.
- **Plan B (.pptx directo):** si el usuario pide expresamente editar la plantilla .pptx en vez del
  artifact, usa `assets/Plantilla_Prospección_Digital.pptx` con la skill `pptx`.
  - Las reglas Kin de este skill aplican igual.
  - Nota: la plantilla vieja (`assets/Plantilla_Prospección_Digital.pptx`) quedó sin "Let knowledge in". La vigente (v2) sí lo lleva y así debe quedar.
  - Su diapositiva 9 trae los valores de Guatemala (34.626, 229.077, 896, 2.636, 5.952, 9.484, 25.142):
    parchear siempre desde esos valores.

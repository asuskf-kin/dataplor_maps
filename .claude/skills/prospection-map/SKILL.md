---
name: prospection-map
description: >
  Usar este skill cuando el usuario suba resultados de prospección (CSV, Excel o
  Kepler JSON) y quiera un mapa interactivo HTML. Frases de activación: "hazme un mapa
  interactivo", "make this interactable", "crea un mapa de esto", "turn this into a map",
  "map these results", "mismo mapa pero con nuevos datos", o cualquier variante donde
  el usuario comparta un archivo con coordenadas de POIs y quiera visualizarlo.
  También activar si el usuario sube un segundo archivo de clientes actuales para
  agregar como capa adicional.
---

# Skill: Mapa Interactivo de Prospección

Genera un HTML completamente autónomo (sin servidor, sin API keys) con mapa
interactivo de resultados de prospección. Funciona con CSV, XLSX o Kepler GL JSON.

Se adapta automáticamente según las columnas presentes:
- Si existe `predicted_grade` / `grade` → agrega filtro multi-select de grade
- Si existe `Exclusión_KIN` (o similar) → agrega filtro de exclusión con 3 opciones
- Si existe `state` / `departamento` → agrega dropdown de estado/departamento
- Si se sube un segundo archivo de clientes → agrega capa de clientes con su toggle
- Si no existe alguna columna → omite ese filtro silenciosamente

---

## PASO 0 — Leer skills relevantes

```
view /mnt/skills/public/file-reading/SKILL.md
```

**Identidad visual Kin (obligatorio).** El mapa es un entregable Kin: sigue la skill
`brand-guidelines-kin` (instalada en `.claude/skills/brand-guidelines-kin/`, abajo `BRAND`).
Léela, junto con `BRAND/references/web-html.md`, antes de escribir el HTML. Resumen de lo que
aplica aquí:

- **Tema oscuro.** Superficie Black `#141417`, paneles Gray 4 `#222326`, texto White y Gray 3 `#999EA6`.
  Kin Yellow `#E5FF01` solo como acento (≈3 %): toggles activos, chips activos, número clave y
  serie primaria. Nada de gradientes.
- **Tipografía.** Space Grotesk para títulos, números y stats; Albert Sans para labels y texto.
  Se embeben en base64 desde `BRAND/assets/fonts/*.woff2`. **Nunca** Google Fonts ni IBM Plex.
- **Logo desde archivo.** `BRAND/assets/logos/informal/Kin_Logo_IV_19.svg` (fondo oscuro) como
  `<img>` data-URI en el header del sidebar. Nunca dibujarlo ni escribir "Kin" en texto.
- **Colores desde tokens.** Copia el bloque `:root` de `BRAND/assets/tokens/colors_and_type.css` al
  `<style>` y usa `var(--ka-…)` en el CSS. En JS (Leaflet necesita valores literales) lee los tokens
  con `getComputedStyle(document.documentElement).getPropertyValue('--ka-color-yellow')`.
- **Esquinas** de 12px en paneles y cards; píldora (`999px`) solo en chips y toggles.
- No usar el tagline "Let knowledge in". La URL, si aparece, va como `kinanalytics.com`.

---

## Atajo — pipeline en código (ahorra tokens)

Si el repo tiene `src/mapa.py`, úsalo en vez de escribir el HTML a mano:
`python src/mapa.py <pais>/<region> [--breaks 1,3,6,10,15] [--cliente-nombre "…"]`. Implementa
todos los pasos de abajo con `src/mapa_template.html`. Muestra los breaks al usuario y regenera con
`--breaks` si pide otros.

## PASO 1 — Inspeccionar el archivo

```python
import pandas as pd
df = pd.read_csv(path)  # o read_excel
print(df.shape)
print(df.columns.tolist())
print(df.head(2).to_string())
# Revisar última columna — puede ser exclusión
# Revisar distribución de columnas clave
```

Detectar columnas automáticamente:

```python
def find_col(fields, candidates):
    fl = [f.lower() for f in fields]
    for c in candidates:
        if c.lower() in fl:
            return fields[fl.index(c.lower())]
    return None

lat_col    = find_col(cols, ['dataplor_latitude','latitude','lat','y'])
lng_col    = find_col(cols, ['dataplor_longitude','longitude','lng','lon','x'])
name_col   = find_col(cols, ['dataplor_name','name','nombre','outlet_name'])
addr_col   = find_col(cols, ['dataplor_address','address','direccion'])
cat_col    = find_col(cols, ['business_category','category','categoria','tipo'])
city_col   = find_col(cols, ['city','ciudad'])
state_col  = find_col(cols, ['state','departamento','estado','region'])
channel_col= find_col(cols, ['channel_cat','channel','canal'])
exist_col  = find_col(cols, ['probability_existence_cat','existence_prob','existence'])
score_col  = find_col(cols, ['weighted_combined_score','score','combined_score'])
grade_col  = find_col(cols, ['predicted_grade','grade','grado','tier'])
excl_col   = find_col(cols, ['exclusión_kin','exclusion_kin','excluido','excluded','removed'])

HAS_GRADE  = grade_col is not None
HAS_STATE  = state_col is not None
HAS_EXCL   = excl_col is not None
# Exclusión: valor 'x' (o 'X') = excluido, NaN/vacío = activo
```

---

## PASO 2 — Preparar datos compactos

Con 3k–80k filas usar arrays paralelos con deduplicación de strings.
Objetivo: HTML < 10MB.

```python
import h3, json, pandas as pd
from collections import Counter

# String deduplication
uniq_cats   = sorted(df[cat_col].fillna('').unique())   if cat_col   else []
uniq_cities = sorted(df[city_col].fillna('').unique())  if city_col  else []
uniq_states = sorted(df[state_col].fillna('').unique()) if HAS_STATE else []
cat_idx     = {c:i for i,c in enumerate(uniq_cats)}
city_idx    = {c:i for i,c in enumerate(uniq_cities)}
state_idx   = {c:i for i,c in enumerate(uniq_states)}

# Encodings categóricos — construir desde valores del dataset
exist_order   = ['high','moderate','low']
uniq_exist    = sorted(df[exist_col].dropna().unique(),
                       key=lambda x: exist_order.index(x) if x in exist_order else 99) if exist_col else []
exist_enc     = {v:i for i,v in enumerate(uniq_exist)}

channel_enc   = {}
if channel_col:
    for i,v in enumerate(sorted(df[channel_col].dropna().unique())):
        channel_enc[v] = i

grade_enc     = {}
if HAS_GRADE:
    for i,g in enumerate([g for g in ['Gold','Silver','Bronze','Iron']
                          if g in df[grade_col].values]):
        grade_enc[g] = i

# Arrays paralelos
lats,lngs,names,addrs = [],[],[],[]
cats,cities,states,channels,exists,grades,scores,excls,h3cells = [],[],[],[],[],[],[],[],[]

for _,row in df.iterrows():
    lat,lng = float(row[lat_col]), float(row[lng_col])
    lats.append(round(lat,5)); lngs.append(round(lng,5))
    names.append(str(row[name_col]) if name_col and pd.notna(row[name_col]) else '')
    addrs.append(str(row[addr_col]) if addr_col and pd.notna(row[addr_col]) else '')
    cats.append(cat_idx.get(str(row[cat_col]).strip()   if cat_col   else '', 0))
    cities.append(city_idx.get(str(row[city_col]).strip() if city_col else '', 0))
    states.append(state_idx.get(str(row[state_col]).strip() if HAS_STATE else '', 0))
    channels.append(channel_enc.get(str(row[channel_col]).strip(), 0) if channel_col else 0)
    exists.append(exist_enc.get(str(row[exist_col]).strip().lower(), len(uniq_exist)-1) if exist_col else 0)
    grades.append(grade_enc.get(str(row[grade_col]).strip(), -1) if HAS_GRADE else -1)
    scores.append(round(float(row[score_col]),4) if score_col and pd.notna(row[score_col]) else 0.0)
    excls.append(1 if HAS_EXCL and str(row[excl_col]).strip().lower()=='x' else 0)
    h3cells.append(h3.latlng_to_cell(lat, lng, 8))

# VERIFICAR siempre antes de continuar
print('exists:', Counter(exists))    # debe tener múltiples valores distintos
print('excls:', Counter(excls))      # 0=activo, 1=excluido

# H3 boundaries pre-computadas
uniq_cells  = list(set(h3cells))
cell_idx    = {c:i for i,c in enumerate(uniq_cells)}
cell_ids    = [cell_idx[c] for c in h3cells]
# h3 v4 devuelve (lat, lng) y L.polygon espera [lat, lng]: NO invertir (invertido = hexágonos fuera del mapa)
cell_bounds = [[[round(lat2,6),round(lng2,6)] for lat2,lng2 in h3.cell_to_boundary(c)]
               for c in uniq_cells]

data = {
    'lats':lats,'lngs':lngs,'names':names,'addrs':addrs,
    'cats':cats,'cities':cities,'states':states,
    'chs':channels,'exists':exists,'grades':grades,'scores':scores,'excls':excls,
    'h3':cell_ids,'uCats':uniq_cats,'uCities':uniq_cities,'uStates':uniq_states,
    'cells':cell_bounds,
}
```

### Si hay archivo de clientes (segunda capa)

```python
df_clients = pd.read_csv(client_path)
# Detectar lat/lng igual que arriba
client_lats  = [round(float(r[lat_col]),5) for _,r in df_clients.iterrows()]
client_lngs  = [round(float(r[lng_col]),5) for _,r in df_clients.iterrows()]
client_names = [str(r[name_col]) if pd.notna(r[name_col]) else '' for _,r in df_clients.iterrows()]
# Agregar al data dict:
data['clientLats']  = client_lats
data['clientLngs']  = client_lngs
data['clientNames'] = client_names
HAS_CLIENTS = True
```

---

## PASO 3 — Breaks dinámicos para hexágonos

**Mostrar al usuario y pedir confirmación antes de generar el HTML.**

```python
cell_counts   = Counter(h3cells)
counts_sorted = sorted(cell_counts.values())
total, max_count = len(counts_sorted), counts_sorted[-1]

def pct(q): return counts_sorted[min(int(q*total), total-1)]
def r5(x):  return max(1, round(x/5)*5)

b1 = r5(pct(0.70))
b2 = r5(pct(0.85))
b3 = r5(pct(0.90))
b4 = b3 + 10
b5 = b4 + 10
DEFAULT_BREAKS = [b1, b2, b3, b4, b5]

# Si max_count es pequeño (< 30), usar breaks más finos:
# DEFAULT_BREAKS = [1, 3, 6, 10, 15]  (como en Guatemala con max=21)

print(f'Total celdas: {total}, Max: {max_count}')
prev = 0
for br in DEFAULT_BREAKS + [max_count]:
    n = sum(1 for c in counts_sorted if prev < c <= br)
    print(f'  {prev+1}–{br}: {n} celdas ({n/total*100:.0f}%)')
    prev = br
```

---

## PASO 4 — Centroid y zoom inicial

```python
center_lat = sum(lats) / len(lats)
center_lng = sum(lngs) / len(lngs)
zoom = 7 if len(lats) > 10000 else 8   # país = 7-8, ciudad = 11-12
```

---

## PASO 5 — Construir el HTML

Escribir a `/mnt/user-data/outputs/prospection_map_[cliente].html`.

### `<head>` — Leaflet por CDN; fuentes y logo embebidos
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```
> Leaflet es la **única** dependencia externa permitida, porque los tiles del mapa base
> necesitan internet de todas formas. Las fuentes y el logo **siempre** van embebidos.

```python
import base64, pathlib
BRAND = pathlib.Path('.claude/skills/brand-guidelines-kin')   # ajustar si se ejecuta desde otra carpeta
b64 = lambda p: base64.b64encode((BRAND / p).read_bytes()).decode()
FONT_CSS = f"""
@font-face{{font-family:'Space Grotesk';src:url('data:font/woff2;base64,{b64('assets/fonts/space-grotesk.woff2')}') format('woff2');font-weight:300 700;}}
@font-face{{font-family:'Albert Sans';src:url('data:font/woff2;base64,{b64('assets/fonts/albert-sans.woff2')}') format('woff2');font-weight:100 900;}}
"""
TOKENS_CSS = (BRAND / 'assets/tokens/colors_and_type.css').read_text(encoding='utf-8')
LOGO_URI   = 'data:image/svg+xml;base64,' + b64('assets/logos/informal/Kin_Logo_IV_19.svg')
# <html data-theme="dark"> + <style>{FONT_CSS}{TOKENS_CSS} …</style>
# Header del sidebar: <img src="{LOGO_URI}" alt="Kin" style="height:var(--…)">
```

### Variables CSS — tokens Kin, tema oscuro
```css
/* <html data-theme="dark">: los tokens --ka-* ya resuelven los valores oscuros */
#sidebar { background: var(--ka-color-gray-4); color: var(--ka-color-white); }
#map     { background: var(--ka-color-black); }
.section-title { font-family:'Albert Sans'; font-weight:600; text-transform:uppercase;
                 letter-spacing:.08em; color: var(--ka-color-gray-3); }   /* eyebrow */
h1, .stat-num  { font-family:'Space Grotesk'; font-weight:700; }
.stat-num.key  { color: var(--ka-color-yellow); }      /* solo el número clave */
.chip.active, .toggle.on { background: var(--ka-color-yellow); color: var(--ka-color-black); }
/* Body y labels: Albert Sans. Números, contadores y breaks: Space Grotesk (tabular-nums). */
```

### Layout
```
#sidebar → position:absolute; top:0; left:0; bottom:0; width:320px; z-index:400
#map     → position:absolute; top:0; left:320px; right:0; bottom:0
```

### Capas del mapa — ORDEN CRÍTICO
```javascript
// 1. Fondo sin labels — basemap oscuro Esri Canvas (CARTO ya exige API key: devuelve 'API KEY REQUIRED')
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:16, attribution:'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap'}).addTo(map);

// 2. Panes — zIndex explícito
map.createPane('hexPane');      map.getPane('hexPane').style.zIndex    = 300;
map.createPane('pointPane');    map.getPane('pointPane').style.zIndex  = 350;
map.createPane('clientPane');   map.getPane('clientPane').style.zIndex = 340; // entre hex y puntos
map.createPane('labelsPane');   map.getPane('labelsPane').style.zIndex = 450;
map.getPane('labelsPane').style.pointerEvents = 'none';

// 3. Labels encima de todo — siempre último
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:16, pane:'labelsPane'}).addTo(map);

// IMPORTANTE: L.layerGroup() NO acepta opción pane — va en cada marker individual
let hexGroup    = L.layerGroup().addTo(map);
let pointGroup  = L.layerGroup().addTo(map);
let clientGroup = L.layerGroup().addTo(map); // solo si HAS_CLIENTS
```

### Paleta Kin en JS — leída de los tokens
```javascript
const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const K = {
  yellow: tok('--ka-color-yellow'), black: tok('--ka-color-black'), white: tok('--ka-color-white'),
  g2: tok('--ka-color-gray-2'), g3: tok('--ka-color-gray-3'), g4: tok('--ka-color-gray-4'),
};
```

### Colores de existencia — orden de series Kin (Yellow → White → Gray 3)
```javascript
const EXIST_COLORS = [K.yellow, K.white, K.g3]; // índice 0=high, 1=moderate, 2=low
```

### Puntos de prospección — diferenciados por exclusión
```javascript
// Activos: relleno por existencia + borde Black fino (los separa de los hexágonos amarillos)
// Excluidos: anillo hueco Gray 2 (sin relleno). No se usa rojo: no está en la paleta Kin
const isExcl = D.excls[i] === 1;
L.circleMarker([lat, lng], {
  pane:        'pointPane',
  radius:      5,
  fillColor:   isExcl ? K.black : EXIST_COLORS[D.exists[i]],
  color:       isExcl ? K.g2    : K.black,
  weight:      isExcl ? 1.5     : 1,
  fillOpacity: isExcl ? 0       : 0.9,
});
```

### Capa de clientes (solo si HAS_CLIENTS)
```javascript
// Relleno Gray 4 con anillo Yellow: se distingue de la prospección sin salir de la paleta
L.circleMarker([lat, lng], {
  pane: 'clientPane',
  radius: 5,
  fillColor: K.g4,
  color: K.yellow,
  weight: 2,
  fillOpacity: 1,
});
// Toggle independiente en el sidebar
```

### Puntos — solo renderizar con zoom ≥ 10
```javascript
const POINT_ZOOM_THRESHOLD = 10;
// Mostrar hint "Haz zoom para ver puntos" cuando zoom < threshold
// En zoomend: reconstruir puntos si layerVis.points === true
```

### Hexágonos — breaks dinámicos + sliders
```javascript
// Rampa Kin: una sola tinta (Kin Yellow) con opacidad creciente sobre el basemap oscuro.
// Plana, sin gradientes ni colores fuera de la paleta. Más densidad = más amarillo
const HEX_OPACITY    = [0.12, 0.25, 0.40, 0.55, 0.75, 0.95];
const DEFAULT_BREAKS = [B1, B2, B3, B4, B5]; // inyectados desde Python
const MAX_VAL        = MAX_COUNT;             // inyectado desde Python
let breaks           = [...DEFAULT_BREAKS];
let hexPolys         = []; // [{poly, count}] — para repintado instantáneo

function getHexClass(n) {
  for (let i=0; i<breaks.length; i++) if (n<=breaks[i]) return i;
  return 5;
}
// estilo: {fillColor:K.yellow, fillOpacity:HEX_OPACITY[cls], color:K.yellow, weight:0.5, opacity:0.35}
// La leyenda de breaks muestra los mismos 6 pasos de opacidad (cuadrados, como en Kin_Graphs_Style)

// buildHex() guarda refs en hexPolys
// repaintHex() recorre hexPolys con setStyle() — sin reconstruir la capa
// renderSliders() genera 5 sliders + 1 label estático
// onSlider(idx, val, input) — clampea entre breaks vecinos
// resetBreaks() — vuelve a DEFAULT_BREAKS
```

### Tooltip hexágono — fondo White, texto Black (legible sobre cualquier celda)
```javascript
// Usar una clase CSS (.kin-tip) con tokens, no estilos inline con hex literales
`<div class="kin-tip"><span class="kin-tip-swatch" style="opacity:${HEX_OPACITY[cls]}"></span>
  <b class="num">${count}</b>&nbsp;POIs</div>`
```
```css
.kin-tip { font-family:'Albert Sans'; background:var(--ka-color-white); color:var(--ka-color-black);
           border-left:3px solid var(--ka-color-yellow); border-radius:12px; display:flex;
           align-items:center; gap:.5em; white-space:nowrap; }
.kin-tip .num { font-family:'Space Grotesk'; font-weight:700; }
.kin-tip-swatch { background:var(--ka-color-yellow); width:.75em; height:.75em; }
/* Badge EXCLUIDO en el tooltip de punto: fondo Black, texto White, sin rojo */
```

---

## PASO 6 — Sidebar: orden y componentes

1. **Header**: logo Kin desde archivo (`Kin_Logo_IV_19.svg` como data-URI), un eyebrow
   en mayúsculas Gray 3, el título en Space Grotesk White y el subtítulo (cliente · fuente · tipo)
2. **Stats bar** — Total POIs | Visible (se actualiza con filtros)
3. **Sección Layers** — un toggle por capa activa:
   - Hexagonos (siempre)
   - Puntos (siempre)
   - Clientes (solo si HAS_CLIENTS)
4. **Sección Filtros** — solo mostrar si la columna existe:

| Filtro | Tipo | Cuándo mostrarlo |
|--------|------|-----------------|
| Exclusión KIN | chips 3 opciones: Todos / Sin exclusión / Solo excluidos | Solo si HAS_EXCL |
| Canal | chips single-select | Solo si HAS_CHANNEL |
| Existencia | chips multi-select con color hint | Solo si HAS_EXISTENCE |
| Grade | chips multi-select | Solo si HAS_GRADE |
| Categoría | dropdown con búsqueda | Solo si HAS_CAT |
| Ciudad | dropdown con búsqueda | Solo si HAS_CITY |
| Departamento/Estado | dropdown con búsqueda | Solo si HAS_STATE |
| Nombre | input texto libre | Siempre |

5. **Sección Hexagonos — Breaks** — sliders + botón ↺ Reset
6. **Sección Leyenda** — puntos por existencia + indicador de excluidos si aplica

### Filtro de exclusión — 3 chips (activo = Yellow con texto Black; inactivo = Gray 4 con borde Gray 3)
```html
<div class="chip active"        onclick="setExcl('all')"  id="fex-all">Todos</div>
<div class="chip"               onclick="setExcl('kept')" id="fex-kept">✓ Sin exclusión</div>
<div class="chip"               onclick="setExcl('excl')" id="fex-excl">✕ Solo excluidos</div>
```
```javascript
// 'all'  → mostrar todos (2785 activos + 747 excluidos)
// 'kept' → solo activos (excls[i] === 0)
// 'excl' → solo excluidos (excls[i] === 1)
function setExcl(val) {
  fExcl = val;
  // Actualizar clases de chips según estado
  buildLayers();
}
```

### Toggle de capa — crítico: re-agregar al mapa al activar
```javascript
function toggleLayer(id) {
  layerVis[id] = !layerVis[id];
  document.getElementById('toggle-'+id).classList.toggle('on', layerVis[id]);
  const grp = {hex:hexGroup, points:pointGroup, clients:clientGroup}[id];
  if (!layerVis[id]) {
    map.removeLayer(grp);
  } else {
    grp.addTo(map);        // SIEMPRE re-agregar antes de buildX()
    if (id === 'hex') { const v=getVisible(); buildHex(v); }
    else if (id === 'points') { const v=getVisible(); buildPoints(v); }
    else if (id === 'clients') buildClients();
  }
}
```

---

## PASO 7 — Filtrado JS

```javascript
function isVisible(i) {
  if (HAS_EXCL    && fExcl==='kept' && D.excls[i]===1) return false;
  if (HAS_EXCL    && fExcl==='excl' && D.excls[i]===0) return false;
  if (HAS_CHANNEL && fChannel!=='all' && D.chs[i]!==fChannel) return false;
  if (HAS_EXIST   && !fExists.has('all') && !fExists.has(D.exists[i])) return false;
  if (HAS_GRADE   && !fGrades.has('all') && !fGrades.has(D.grades[i])) return false;
  if (fCat  !== null && D.cats[i]   !== fCat)   return false;
  if (fCity !== null && D.cities[i] !== fCity)  return false;
  if (fState!== null && D.states[i] !== fState) return false;
  if (fSearch) {
    const s = fSearch.toLowerCase();
    if (!(D.names[i]||'').toLowerCase().includes(s) &&
        !(D.uCats[D.cats[i]]||'').toLowerCase().includes(s) &&
        !(D.uCities[D.cities[i]]||'').toLowerCase().includes(s)) return false;
  }
  return true;
}
```

---

## PASO 8 — Checklist antes de entregar

- [ ] HTML abre sin errores (sin servidor; internet solo para Leaflet y los tiles)
- [ ] **Marca Kin:** Space Grotesk y Albert Sans embebidas (ninguna petición a fonts.googleapis),
      logo `Kin_Logo_IV_19.svg` desde archivo, tokens `--ka-*`, Yellow solo como acento, sin
      "Let knowledge in", sin gradientes y sin colores fuera de la paleta (ni rojo, ni naranja, ni azul)
- [ ] Mapa centrado correctamente sobre los datos
- [ ] Hexágonos con pasos de opacidad distinguibles (no toda una región con el mismo tono)
- [ ] Labels y bordes del mapa ENCIMA de hexágonos y puntos
- [ ] Puntos visibles con zoom ≥ 10; hint visible en zoom < 10
- [ ] Puntos activos: color por existencia (Yellow/White/Gray 3). Excluidos: anillo hueco Gray 2
- [ ] Toggle puntos funciona ON → OFF → ON sin desaparecer al re-activar
- [ ] Toggle clientes funciona (si aplica)
- [ ] Filtro Exclusión KIN presente solo si la columna existe
- [ ] Filtro Grade presente solo si la columna existe
- [ ] Sliders repintan hexágonos en tiempo real
- [ ] Botón ↺ Reset vuelve a DEFAULT_BREAKS
- [ ] Tooltip hexágono: fondo White y texto Black (legible sobre cualquier celda)
- [ ] Tooltip punto: muestra badge EXCLUIDO si aplica
- [ ] Archivo < 10MB y completamente autónomo
- [ ] Nombre del archivo: `prospection_map_[cliente].html`

---

## BUGS CONOCIDOS — EVITAR SIEMPRE

### BUG 1: L.layerGroup con opción pane
```javascript
// ❌ layerGroup ignora el pane — puntos no aparecen
let pointGroup = L.layerGroup({pane:'pointPane'}).addTo(map);

// ✅ pane va en cada marker individual
let pointGroup = L.layerGroup().addTo(map);
L.circleMarker([lat, lng], { pane: 'pointPane', ... });
```

### BUG 2: Encoding categórico todo en ceros
```python
# SIEMPRE verificar después de encodear
print(Counter(exists))   # si todos son 0, el encoding falló
# Forma segura:
exists = [exist_enc.get(str(v).strip().lower(), fallback) for v in df[col].fillna('')]
```

### BUG 4: un lienzo (canvas) por capa
```javascript
// ❌ L.canvas({pane:'pointPane'}) + L.canvas({pane:'hexPane'}): el lienzo de arriba tapa el mouse
//    y los hexágonos no muestran tooltip ni responden al clic
// ✅ un solo L.canvas() para todas las capas; hexágonos con bringToBack()
```

### BUG 3: Toggle no re-agrega el grupo al mapa
```javascript
// ❌ markers se agregan al grupo pero el grupo no está en el mapa
else { buildPoints(vis); }

// ✅ siempre addTo(map) primero
else { pointGroup.addTo(map); buildPoints(vis); }
```

---

## NOTAS FINALES

- **Nunca usar breaks fijos** — siempre calcular desde la distribución real y confirmar con el usuario antes de generar
- **Columnas opcionales** — detectar dinámicamente, no asumir que existen
- **Nombre del archivo**: `prospection_map_[cliente].html`
- **>20k filas**: usar arrays paralelos + deduplicación (no GeoJSON objects)
- **Breaks para datasets pequeños** (max < 30): usar `[1, 3, 6, 10, 15]` en lugar del cálculo percentil

# Pipeline de prospección (QA → mapa → deck)

Entrada: un mercado `<pais>/<region>` (ej. `mx/Golfo`) con los datos en
`data/<pais>/<region>/{clientes,datamatch,priority}/`. Las salidas van a `output/<pais>/<region>/`.
Correr los scripts en vez de rehacer la lógica de las skills: así se ahorran tokens.

1. **QA** (skill `prospection-qa`): `python src/qa.py <mercado>`
   - Si falta el benchmark de mercado, búscalo en la web, guárdalo en `output/<mercado>/qa/benchmark.json`
     y vuelve a correr con `--benchmark <ruta>`.
   - Envía `qa_report.html` y los dos mapas, y **espera el OK del usuario** antes de seguir.
2. **Mapa** (skill `prospection-map`): `python src/mapa.py <mercado> [--breaks …] [--cliente-nombre …]`
   - Genera dos versiones:
     - `_BOTTLER.html`: completo.
     - `_KO.html`: nombres anonimizados ("POI n", el mismo `poi_ref` del CSV de KO, y "Cliente n"), sin
       direcciones. Una verificación aborta la corrida si se cuela algún nombre real.
   - Muestra los breaks que imprime; si el usuario pide otros, regenera con `--breaks`.
   - Imagen estática para la diapositiva 14 del deck: `python src/mapa_png.py <mercado>`.
3. **Deck** (skill `prospeccion-digital`):
   - Primero el QA de cifras (port de `ABI_Guatemala_Charts.ipynb`):
     `python src/deck_data.py <mercado> --portafolio <total maestra>`. Requiere la base Priority con
     `probability_existence_cat`, `channel_cat`, `business_category` y `city`.
   - Revisa las cifras con el usuario y luego arma el deck en Claude Design con `output/<mercado>/deck/deck_data.json`.
   - El deck sigue SIEMPRE la plantilla `data/templates/Plantilla_Prospeccion_Digital_v2.pptx`, que está en Claude Design
     como https://claude.ai/artifact/Eagmk8BE2pDi61CWFeVf4R (22 diapositivas). No inventar otra estructura.
   - Las diapositivas se generan con código, nunca a mano:
     1. Escribir `output/<mercado>/deck/meta.json` con textos, insights y glosario (copiar el de Golfo y adaptarlo).
     2. Crear el artifact Slides y subirle los assets: logos, `cover_hex`, `ciclo`, `proceso`, `divider_bg`,
        `collage` y las fotos de `data/templates/assets/`, más el mapa y las vistas previas del mercado.
        Guardar las URLs en `assets.json`.
     3. `python src/deck_slides.py --data …/deck_data.json --meta …/meta.json --assets …/assets.json --out <root>`.
     4. Revisión visual: `python src/deck_preview.py --root <root> --assets … --local …/assets_local.json --png <dir>`
        (un PNG por diapositiva y `contact.png`).
     5. Publicar `project/deck.json` y la portada, y luego el resto de las diapositivas.
   - Formato Slides: el padding máximo es 256 px. Para dejar libre una columna de foto se usa una grilla, no padding.
   - **Leer `.claude/skills/prospeccion-digital/references/aprendizajes.md` antes de armar un deck.** Resume lo aprendido
     de las ediciones del usuario:
     - la plantilla manda, con "Let knowledge in" y los logos de la plantilla;
     - un canal sin datos no lleva diapositiva;
     - el texto del algoritmo va completo;
     - impacto con dentro/fuera y captura neta al 50–70 %;
     - mapa estilo Kepler;
     - contactos vigentes.
   - El deck terminado de referencia (editado por el usuario) está en `data/templates/golfo_editado/project/`.

4. **Entregables CSV**: `python src/entregables.py <mercado> --sufijo AAAAMM`.
   - Prioridad 1–6: primero el área (dentro → fuera) y luego la existencia (High → Moderate → Low).
   - Los nombres empiezan siempre por `Dataplor_on_premise_priority` (se reusa el nombre de la base Priority).
   - El CSV `_BOTTLER` lleva todo, con coordenadas. El CSV `_KO` va sin coordenadas, nombre, contacto ni `ref_`.

Notas:
- Las carpetas de datos admiten alias sin distinguir mayúsculas: `clientes` también puede llamarse `Clients/` o `Maestra/`.
  Las coordenadas `Coord_Y`/`Coord_X` se detectan solas.
- `data/<mercado>/geo_alias.json` une ciudades que son la misma, por ejemplo `{"Oaxaca de Juárez": "Oaxaca"}`.
- Mercados hechos: `mx/Golfo` y `mx/Centro Pacifico`. Para un mercado nuevo, copiar el `meta.json` del más parecido y reescribir los insights.
- `data/<mercado>/exclusiones.csv` (`dataplor_id,nombre,motivo`): falsos negativos del QA que se quitan
  del mapa, del deck y de los entregables.
- La base Priority puede venir sin `match_no_match` (solo trae no-match). En ese caso, el total de match sale del datamatch.
- En Windows usar `python` (3.14, tiene pandas) y `PYTHONIOENCODING=utf-8` para los acentos.
- Los tiles de CARTO exigen API key; los mapas usan Esri Canvas.

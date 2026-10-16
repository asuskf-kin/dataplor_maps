# Aprendizajes del deck de Prospección Digital

Se aprendieron al revisar las ediciones del usuario sobre el deck de México Golfo · Coca-Cola FEMSA (oct-2026).
La versión editada por el usuario está en `data/templates/golfo_editado/project/`. Es la referencia de cómo
debe quedar un deck terminado.

`src/deck_slides.py` ya aplica todo esto. Las reglas sirven para cuando haya que tocar algo a mano.

## Plantilla y marca
- **La plantilla manda sobre la skill de marca.** Los decks de prospección llevan el tagline **"Let knowledge in."**
  como en la plantilla:
  - en el pie de página, con la imagen `logo_footer_light.png` o `logo_footer_dark.png`;
  - en la portada, con `cover_logo.png` y `cover_tagline.png`;
  - en el cierre amarillo, con el título "Let Knowledge in".
  La prohibición de `brand-guidelines-kin` no aplica a este entregable.
- Los logos son las imágenes de la plantilla (`data/templates/assets/logo_footer_*.png`, `cover_*.png`), no los SVG de la marca.
- Las posiciones salen de la plantilla:
  - pie claro: logo en left 104, top 994, 438×42;
  - pie oscuro: left 66, top 994, 517×57;
  - portada: logo en left 96, top 902, 640×116, y franja en left 1214, top 984, 640×73.

## Contenido
- **Sin datos en un canal, la diapositiva no va.** Si Off Premise = 0:
  - se elimina la diapositiva de detalle Off Premise;
  - en "Top categorías" se muestra solo la gráfica On Premise, centrada;
  - no se dejan paneles vacíos ni diapositivas que expliquen el vacío.
- **Si la base no trae Off Premise, no se nombra en ninguna parte del deck** (pedido del usuario, oct-2026):
  - no hay columna Off Premise en la tabla por ciudad;
  - no hay viñeta Off Premise en "Segmentación por canal";
  - el texto no dice "tanto en Off como en On";
  - el glosario no dice "On/Off Premise";
  - las notas no explican que Off Premise vale 0.
  `deck_slides.py` lo resuelve con `has_off`.
- **Un deck de cliente no cita otras regiones o clientes.** No escribir "a diferencia de Golfo". Al copiar el `meta.json`
  de otro mercado, revisar los textos `alt` del glosario y los insights.
- **Lógica del algoritmo:** va el texto COMPLETO de la plantilla (proceso iterativo y las 4 razones del No Match en
  viñetas), con **match** en verde `#9CCFB1` y **No Match** en rojo `#E5A39B`.
- **Impacto del proyecto:**
  - Con una sola ciudad dominante, las etapas se nombran por categorías ("Etapa 1 | Categorías prioritarias:
    Restaurantes, Taquerías y Bares…"), no por "top 3 ciudades".
  - El total desglosa el potencial bruto en **dentro / fuera** del radio actual de las rutas (≤300 m de un cliente).
  - La nota al pie da la **captura neta al 50–70 %** en POS y en % del portafolio. Ejemplo:
    534 → 267–374 POS = 15,11 %–21,17 % sobre 1.767.
- **Insight de la diapositiva 10:** destacar "ampliar la cobertura" sin descartar las zonas con presencia.
- **Próximos pasos:** con aire entre las viñetas.
- **Contactos vigentes:** paula.lara@, david.farinango@ y nicolas.ayala@kinanalytics.com. **miguel.mena@ ya no va.**
- **Canal:** el usuario describe el canal de Golfo como "On Premise nocturno" (en el punto de partida y en el impacto).

## Mapa (diapositiva 14)
- El usuario prefiere el **estilo Kepler** al hexbin amarillo de marca:
  - basemap claro;
  - hexágonos de todos los no-match en rampa amarillo → naranja → rojo → granate;
  - puntos por existencia (high azul oscuro, moderate verde claro, low turquesa);
  - **recuadro verde** sobre la zona más densa;
  - panel de leyenda oscuro.
- Se genera con `python src/mapa_png.py <mercado>` (estilo `kepler` por defecto).

## Formato Slides (técnico)
- El padding máximo es 256 px. Para dejar libre una columna de foto se usa una grilla `640px 1fr` o posiciones absolutas.
- Los blobs (`/_blob/…`) son por artifact: hay que subir los assets a cada deck y guardar las URLs en `assets.json`.
- Antes de republicar sobre un deck editado por el usuario, leer su versión: no pisar sus cambios.

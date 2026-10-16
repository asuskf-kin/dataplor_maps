# Contenido fijo del deck de Prospección Digital

Textos de las diapositivas que **no cambian** entre ejercicios. Se extrajeron de
`assets/Plantilla_Prospección_Digital.pptx`. Se copian tal cual al deck, con el diseño
del Kin Design System. Las imágenes originales (fotos, diagramas, capturas) están en
`ppt/media/` dentro de la plantilla; súbelas como assets solo si la diapositiva las necesita.

Leyenda: «Eyebrow» = etiqueta en mayúsculas sobre el título.

---

## 1 · Portada (variable — ver SKILL.md)
Eyebrow `PROSPECCIÓN DIGITAL` · título `Prospección Digital` · subtítulo `{PAIS} - {EMBOTELLADORA}` ·
fecha `{MES_ACTUAL} {AÑO}` · marca `Kin Analytics© {AÑO}` + `CONFIDENTIAL` abajo a la derecha (solo en la portada).

## 2 · Contenido (agenda)
1. Introducción y generalidades
2. El algoritmo
3. Análisis y resultados
4. Siguientes pasos
5. Glosario

## 3 · Objetivo del proyecto
- **Objetivo del proyecto:** Identificar y priorizar las oportunidades de expansión de mercado para el
  embotellador en sus distintos canales y categorías a nivel de punto de venta.
- **Impacto esperado:** Este análisis permitirá al embotellador entender mejor las áreas clave de
  crecimiento y tomar decisiones informadas sobre dónde concentrar sus esfuerzos de expansión,
  optimizando así la distribución y los recursos de manera estratégica.
- **El proyecto en cifras** (3 cifras grandes):
  - Implementado con éxito en más de **17 países** y **25 embotelladores** alrededor del mundo.
  - En promedio, **1 de cada 5** prospectos contactados se transforma en cliente, lo que refleja la
    efectividad del análisis en la conversión de oportunidades.
  - En los casos más exitosos, se ha mejorado el ratio a **1 de cada 3** prospectos convertidos en
    clientes, optimizando el proceso de captación y expansión.

## 4 · El ciclo de vida del proyecto (3 pasos)
1. **Modelado:** En esta etapa nos encargamos de validar la calidad de los datos compartidos, de
   ejecutar el algoritmo y de generar una versión de resultado.
2. **Pruebas de campo:** Una vez se han recibido los resultados es importante validar su veracidad en
   campo; para esto, se crean diferentes rutas a conveniencia del bottler para evaluar la calidad de los resultados.
3. **Ajustes en base a las pruebas de campo:** Se analizan los resultados de las pruebas de campo y se
   crean acciones para el ajuste del modelo en caso de ser necesarias.

## 5 · Detalles del proceso (variable en un texto — ver SKILL.md)
Flujo de 7 pasos numerados:
1. Datos de PDI en zonas de operación.
2. Maestra de clientes - {EMBOTELLADORA} {PAIS} ({MES_ENTREGA} compartida por {QUIEN_ENTREGO})
3. Algoritmo de Datamatch
4. C. Match
5. C. No Match
6. Algoritmo de estimación de prioridad por existencia
7. Base de datos final

## 6 · Lógica del algoritmo
El algoritmo asigna un score de similitud (de 0% a 100%) para comparar puntos de venta con clientes
existentes. Esto permite identificar qué clientes ya están en la base de datos (match) y cuáles son
nuevos posibles clientes (No Match). Utiliza inteligencia artificial para analizar textos y datos de
ubicación geográfica.

El proceso compara características como:
- **Nombre y fonética:** similitud en los nombres.
- **Ubicación geográfica:** distancia entre los puntos.
- **Dirección:** concordancia en la ubicación, si está disponible.

Es un proceso iterativo que ajusta el peso de cada característica para calcular un score final. Luego,
se establece un umbral para clasificar los puntos como match o No Match.

Los puntos No Match son comercios que se encuentran fuera del maestro de clientes por alguna de las
siguientes razones:
- Compra productos de la marca por medio de un tercero (Distribuidor)
- Es un comercio no atendido por la embotelladora
- Los comercios no son manejantes de bebidas NARTD
- El comercio ha cerrado o se ha trasladado

## 7 · Sistema de Priorización de Prospección
El objetivo de este proceso es brindar una métrica que representa la probabilidad de existencia de un
POS de acuerdo con la información disponible.
- **Variables clave:** Popularidad histórica (últimos 6 meses): recuento ponderado de impresiones ·
  Número de reseñas: cantidad de reseñas normalizadas · Validity Score: índice/puntaje de confianza de
  los datos medido por Dataplor.
- **Segmentación por canal:** On Premise (restaurantes, bares, hoteles, gym, etc.) · Off Premise
  (supermercados, farmacias, tiendas, gasolineras, etc.)
- **Score Combinado:** normalización por canal · pesos para cada una de las variables clave.
- **Clasificación final** (umbrales sobre el score combinado): Low 0.00 – 0.30 · Moderate 0.30 – 0.50 · High 0.50 – 1.00

## 8 · Divisor de sección: `Resultados`

## 16 · Divisor de sección: `Siguientes pasos`

## 17 · Próximos pasos (3 puntos)
1. Proporcionar la base de datos de prospección (puntos de alta y moderada probabilidad de no match)
   para que los equipos de campo puedan priorizar y planificar las visitas de forma eficiente.
2. Validar los puntos de alta y moderada probabilidad no-match en el campo, centrándose en las áreas
   con mayor potencial comercial para acelerar la captación de nuevos clientes.
3. Compartir los resultados y la retroalimentación con los equipos comerciales para orientar las
   siguientes fases de activación y perfeccionar la precisión del ejercicio.

## 18 · Divisor de sección: `Vista previa a los datos`

## 19 · Glosario (1/3)
**Identificación del punto:** dataplor_id: ID único del punto en Dataplor · name: nombre comercial del
establecimiento · address: dirección registrada · latitude / longitude: ubicación geográfica · phone:
información de contacto telefónico (si aplica) · business_category: categoría del negocio ·
Características geográficas: columnas como barrio, ciudad, estado, código postal y código de país ·
channel: categorización On/Off Premise con base en la categoría de negocio · pos_id: ID en base de
clientes (cuando el punto es match) · match_nomatch: indica si coincide o no con clientes existentes.

## 20 · Glosario (2/3)
**Características del local:** price_level = rango de precios estimado del local · number_of_reviews =
cantidad total de reseñas registradas · average_stars = calificación promedio del local · website = URL
oficial del establecimiento (si existe) · place_attributes = etiquetas descriptivas (por ejemplo,
"children-friendly", "wifi", etc.).
**Horarios de atención:** monday_hours – sunday_hours = franja de apertura y cierre por día (formato HH:MM–HH:MM).

## 21 · Glosario (3/3)
**Servicios disponibles (TRUE / FALSE):** service_curbside_pickup = retiro en auto (curbside) ·
service_no_contact_delivery = entrega sin contacto físico · service_delivery = servicio de delivery
convencional · service_takeout = pedido para llevar · service_dine_in = consumo en el lugar.
**Características:** feature_seating = indica si el local cuenta con asientos ·
Potential_qualitative_final = nivel estimado de presencia real del punto (Low, Moderate, High).

> En las diapositivas 19–21 la plantilla también trae una captura de la base. Deja un espacio de
> imagen con `alt` descriptivo y avisa al usuario que debe subir la captura de la base real.

## 22 · Cierre
Título `Let Knowledge in` · `Contacts:` paula.lara@kinanalytics.com · david.farinango@kinanalytics.com ·
nicolas.ayala@kinanalytics.com. **No** usar "Let knowledge in". "Leave it to Kin" solo si el usuario lo pide.

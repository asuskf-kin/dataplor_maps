"""Genera las 22 diapositivas del deck de Prospección Digital en formato Claude Design (Slides).

Replica el diseño de data/templates/Plantilla_Prospeccion_Digital_v2.pptx (RD Bepensa, junio 2026).

Uso:
    # Plantilla (datos de ejemplo de RD, tal como vienen en el .pptx)
    python src/deck_slides.py --data data/templates/plantilla_rd_ejemplo.json --assets <assets.json> --out <root>
    # Mercado
    python src/deck_slides.py --data output/mx/Golfo/deck/deck_data.json --meta output/mx/Golfo/deck/meta.json \
                              --assets output/mx/Golfo/deck/assets.json --out <root>

<root>/project/deck.json y <root>/project/slides/*.html quedan listos para publicar con el Artifact
tool (url del deck, root=<root>). assets.json mapea nombre → url /_blob/<id> del artifact destino
(los blobs son por artifact: hay que subirlos a cada deck).
"""
import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

DARK, BLACK, WHITE, Y, Y2 = '#222326', '#141417', '#FFFFFF', '#E5FF01', '#F2FF84'
G1, G2, G3, G4, G5 = '#EFEFEE', '#D4D5D6', '#999EA6', '#222326', '#D8D8D5'
POS, ATT, NEG = '#9CCFB1', '#E8C68A', '#E5A39B'          # tokens ne-positive / ne-attention / ne-negative
SG, AS = "'Space Grotesk', Arial, sans-serif", "'Albert Sans', Arial, sans-serif"
e = html.escape


def fmt(n):
    return f'{int(round(n)):,}'.replace(',', '.')


def pc(x, d=1):
    return f'{x:.{d}f}'.replace('.', ',') + '%'


# ── piezas comunes ────────────────────────────────────────────────────────────────────────────
def section(sid, bg, body, color=BLACK, layout='display:flex;flex-direction:column;gap:28px', pad='88px 128px 170px',
            notes='', trans='fade'):
    aside = f'<aside>{e(notes)}</aside>' if notes else ''
    return (f'<section id="{sid}" data-transition="{trans}" style="background:{bg};color:{color};font-family:{AS};'
            f'padding:{pad};{layout}">\n{body}\n{aside}</section>\n')


def footer(A, dark=False):
    # Aprendido (edición del usuario, oct-2026): el pie usa la imagen de la plantilla con logo + "Let knowledge in."
    if dark and 'logo_footer_dark' in A:
        return (f'<img src="{A["logo_footer_dark"]}" alt="Kin Analytics. Let knowledge in." style="position:absolute;left:66px;top:994px;width:517px;height:57px;object-fit:contain">'
                f'<p style="position:absolute;right:96px;bottom:52px;width:400px;text-align:right;font-size:24px;font-weight:500;color:{G3}">kinanalytics.com</p>')
    if not dark and 'logo_footer_light' in A:
        return (f'<div style="position:absolute;left:0px;bottom:0px;width:1920px;height:120px;background:{G1}"></div>'
                f'<img src="{A["logo_footer_light"]}" alt="Kin Analytics. Let knowledge in." style="position:absolute;left:104px;top:994px;width:438px;height:42px;object-fit:contain">'
                f'<p style="position:absolute;right:96px;bottom:44px;width:400px;text-align:right;font-size:24px;font-weight:500;color:{G3}">kinanalytics.com</p>')
    if dark:
        return (f'<img src="{A["logo_dark"]}" alt="Kin Analytics" style="position:absolute;left:96px;bottom:40px;width:240px;height:60px;object-fit:contain">'
                f'<p style="position:absolute;right:96px;bottom:52px;width:400px;text-align:right;font-size:24px;font-weight:500;color:{G3}">kinanalytics.com</p>')
    return (f'<div style="position:absolute;left:0px;bottom:0px;width:1920px;height:120px;background:{G1}"></div>'
            f'<img src="{A["logo_light"]}" alt="Kin Analytics" style="position:absolute;left:96px;bottom:32px;width:240px;height:60px;object-fit:contain">'
            f'<p style="position:absolute;right:96px;bottom:44px;width:400px;text-align:right;font-size:24px;font-weight:500;color:{G3}">kinanalytics.com</p>')


def head(title, eyebrow='Prospección digital', size=52, color=BLACK):
    eb = (f'<p style="font-size:24px;font-weight:500;letter-spacing:3px;text-transform:uppercase;color:{G3}">{e(eyebrow)}</p>'
          if eyebrow else '')
    return (f'<div style="display:flex;flex-direction:column;gap:10px">{eb}'
            f'<h2 style="font-family:{SG};font-size:{size}px;font-weight:500;line-height:1.15;color:{color}">{title}</h2></div>')


def para(text, size=26, color=G4, extra=''):
    return f'<p style="font-size:{size}px;line-height:1.45;color:{color};{extra}">{text}</p>'


def insight(text):
    return (f'<div style="display:flex;flex-direction:column;gap:6px;background:#FAFFD6;border-radius:12px;padding:20px 28px;border-left:8px solid {Y}">'
            f'<p style="font-size:24px;line-height:1.45;color:{G4}"><b>Insight:</b> {text}</p></div>')


def table(header, rows, widths, size=24, first_left=True, total_last=True, width=None):
    th = ''.join(f'<th style="width:{w}%;text-align:{"left" if i == 0 and first_left else "center"}">{e(str(h))}</th>'
                 for i, (h, w) in enumerate(zip(header, widths)))
    wd = f';width:{width}px' if width else ''
    out = [f'<table style="font-family:{AS};font-size:{size}px;color:{BLACK};border:1px solid {G2}{wd}">',
           f'<tr style="background:{Y}">{th}</tr>']
    for k, r in enumerate(rows):
        last = total_last and k == len(rows) - 1
        bg = BLACK if last else (G1 if k % 2 else WHITE)
        col = f';color:{WHITE}' if last else ''
        tds = ''.join(f'<td style="text-align:{"left" if i == 0 and first_left else "center"}{col}">'
                      f'{e(fmt(v) if isinstance(v, (int, float)) else str(v))}</td>' for i, v in enumerate(r))
        out.append(f'<tr style="background:{bg}">{tds}</tr>')
    return ''.join(out) + '</table>'


def bars(items, maxw=420, label_w=300, hi=2):
    if not items:
        return para('Sin puntos en este canal.', 24, G3)
    mx = max(v for _, v in items) or 1
    rows = []
    for i, (c, v) in enumerate(items):
        w = max(6, round(v / mx * maxw))
        rows.append(f'<div style="display:flex;align-items:center;gap:12px"><p style="font-size:24px;width:{label_w}px;text-align:right;color:{G4}">{e(c)}</p>'
                    f'<div style="width:{w}px;height:30px;background:{Y if i < hi else "#C8D400"};border-radius:3px"></div>'
                    f'<p style="font-family:{SG};font-size:24px;font-weight:700;color:{G4}">{fmt(v)}</p></div>')
    return ''.join(rows)


def divider(sid, text, A):
    body = (f'<img src="{A["divider_bg"]}" alt="" style="position:absolute;left:0px;top:0px;width:1920px;height:1080px;object-fit:cover">'
            f'<p style="position:absolute;left:1290px;top:500px;width:420px;text-align:center;font-family:{SG};font-size:56px;line-height:1.15;color:{Y}">{e(text)}</p>')
    return section(sid, DARK, body, layout='display:flex', pad='0px', trans='push')


def photo_split(sid, photo, alt, right_body, A, photo_w=640):
    body = (f'<img src="{photo}" alt="{e(alt)}" style="width:{photo_w}px;height:960px;object-fit:cover">'
            f'<div style="display:flex;flex-direction:column;gap:22px;padding:72px 112px 40px 88px">{right_body}</div>'
            + footer(A))
    return section(sid, WHITE, body, layout=f'display:grid;grid-template-columns:{photo_w}px 1fr', pad='0px 0px 120px 0px')


# ── diapositivas ──────────────────────────────────────────────────────────────────────────────
def build(D, M, A):
    s9, s10, s11, s12, s13, s14, s15 = (D[k] for k in ('slide9', 'slide10', 'slide11', 'slide12', 'slide13', 'slide14', 'slide15'))
    pais, bott, fecha, geo = M['pais'], M['embotelladora'], M['fecha'], M.get('geo_label', 'ciudad')
    Geo, geos = geo.capitalize(), M.get('geo_plural', geo + 'es' if geo.endswith('d') else geo + 's')
    thr = D.get('thresholds') or {'low': [0, .4], 'moderate': [.4, .6], 'high': [.6, 1]}
    t = lambda k: f'{thr[k][0]:.2f} – {thr[k][1]:.2f}'.replace('.', ',')
    S = {}
    # Aprendido: si la base no trae Off Premise, el deck no lo nombra en ningún lado (ni columna, ni viñeta, ni glosario)
    off_ix = s10['header'].index('Off Premise') if 'Off Premise' in s10['header'] else None
    has_off = bool(s13) or bool(s11.get('Off Premise', {}).get('bars')) or (
        off_ix is not None and any(r[off_ix] for r in s10['rows']))

    S['cover'] = section('cover', DARK, (
        f'<img src="{A["cover_hex"]}" alt="Equipo en oficina dentro de un hexágono" style="position:absolute;left:760px;top:140px;width:1160px;height:750px;object-fit:cover">'
        f'<p style="position:absolute;left:96px;top:56px;width:500px;font-size:24px;line-height:1.35;color:{G3}">Kin Analytics<br>©{datetime.now().year}<br>CONFIDENTIAL</p>'
        f'<div style="display:flex;flex-direction:column;gap:36px;width:620px">'
        f'<h1 style="font-family:{SG};font-size:104px;font-weight:400;line-height:1.1;color:{WHITE}">Prospección Digital</h1>'
        f'<p style="font-family:{SG};font-size:44px;line-height:1.25;color:{Y}">{e(pais)} - {e(bott)}</p>'
        f'<p style="font-family:{SG};font-size:40px;color:{WHITE}">{e(fecha)}</p></div>'
        + (f'<img src="{A["cover_logo"]}" alt="Kin Analytics" style="position:absolute;left:96px;top:902px;width:640px;height:116px;object-fit:contain">'
           f'<img src="{A["cover_tagline"]}" alt="Let knowledge in. KinAnalytics.com" style="position:absolute;left:1214px;top:984px;width:640px;height:73px;object-fit:contain">'
           if 'cover_logo' in A else
           f'<img src="{A["logo_dark"]}" alt="Kin Analytics" style="position:absolute;left:96px;bottom:56px;width:560px;height:120px;object-fit:contain">')),
        color=WHITE, layout='display:flex;flex-direction:column;justify-content:center', pad='128px 96px 220px 120px',
        notes=M.get('notes_cover', ''))

    items = [('1. Introducción y generalidades', Y2, BLACK), ('2. El algoritmo', Y, BLACK), ('3. Análisis y resultados', G5, BLACK),
             ('4. Siguientes pasos', G3, BLACK), ('5. Glosario', DARK, WHITE)]
    S['agenda'] = section('agenda', G1, (
        f'<h2 style="font-family:{SG};font-size:56px;font-weight:500;color:{BLACK};text-align:center">Contenido</h2>'
        + ''.join(f'<p style="width:620px;font-size:32px;background:{bg};color:{c};padding:30px 28px">{x}</p>' for x, bg, c in items)
        + footer(A)), layout='display:flex;flex-direction:column;align-items:center;gap:18px', pad='72px 128px 150px')

    S['objetivo'] = photo_split('objetivo', A['photo_objetivo'], 'Persona revisando datos en una laptop', (
        f'<p style="font-size:24px;font-weight:500;letter-spacing:3px;color:{G3}">PROSPECCIÓN DIGITAL</p>'
        f'<h2 style="font-family:{SG};font-size:44px;font-weight:500;color:{BLACK}">Objetivo del proyecto</h2>'
        + para('Identificar y priorizar las oportunidades de expansión de mercado para el embotellador en sus distintos canales y categorías a nivel de punto de venta.', 24)
        + f'<h2 style="font-family:{SG};font-size:44px;font-weight:500;color:{BLACK}">Impacto esperado</h2>'
        + para('Este análisis permitirá al embotellador <b>entender mejor las áreas clave</b> de crecimiento y <b>tomar decisiones informadas</b> sobre dónde <b>concentrar sus esfuerzos de expansión</b>, optimizando así la distribución y los recursos de manera estratégica.', 24)
        + f'<h2 style="font-family:{SG};font-size:44px;font-weight:500;color:{BLACK}">El proyecto en cifras</h2>'
        + f'<ul style="font-size:24px;line-height:1.45;color:{G4}"><li>Implementado con éxito en más de <b>17 países y 25 embotelladores</b> alrededor del mundo.</li>'
        f'<li>En promedio, <b>1 de cada 5 prospectos</b> contactados se transforma en cliente.</li>'
        f'<li>En los casos más exitosos, <b>se ha mejorado el ratio a 1 de cada 3 prospectos</b> convertidos en clientes.</li></ul>'), A)

    S['ciclo'] = section('ciclo', DARK, (
        head('El ciclo de vida del proyecto', size=48, color=WHITE)
        + f'<img src="{A["ciclo"]}" alt="Ciclo circular: modelado, pruebas de campo y ajustes alrededor de Prospección digital" style="position:absolute;left:660px;top:200px;width:600px;height:610px;object-fit:contain">'
        f'<div style="position:absolute;left:150px;top:380px;width:470px;display:flex;flex-direction:column;gap:10px">'
        f'<p style="font-family:{SG};font-size:32px;color:{WHITE}">Modelado</p>{para("Validamos la calidad de los datos compartidos, ejecutamos el algoritmo y generamos una versión de resultado.", 24, G2)}</div>'
        f'<div style="position:absolute;left:1300px;top:380px;width:500px;display:flex;flex-direction:column;gap:10px">'
        f'<p style="font-family:{SG};font-size:32px;color:{WHITE};text-align:right">Pruebas de campo</p>{para("Validamos la veracidad de los resultados en campo con rutas creadas a conveniencia del bottler.", 24, G2, "text-align:right")}</div>'
        f'<div style="position:absolute;left:560px;top:830px;width:800px;display:flex;flex-direction:column;gap:6px">'
        f'<p style="font-family:{SG};font-size:32px;color:{WHITE};text-align:center">Ajustes en base a las pruebas de campo</p>{para("Analizamos los resultados de campo y definimos ajustes al modelo cuando hagan falta.", 24, G2, "text-align:center")}</div>'
        + footer(A, dark=True)), color=WHITE, pad='72px 96px 150px')

    S['proceso'] = section('proceso', DARK, (
        f'<h2 style="font-family:{SG};font-size:56px;font-weight:500;color:{Y}">Detalles del proceso</h2>'
        f'<img src="{A["proceso"]}" alt="Flujo de 7 pasos: datos Dataplor y maestra de clientes entran al algoritmo de Datamatch, se separan en match y no match, pasan por el algoritmo de prioridad por existencia y forman la base final" style="position:absolute;left:40px;top:180px;width:1780px;height:620px;object-fit:contain">'
        f'<p style="position:absolute;left:96px;top:800px;width:560px;text-align:center;font-size:26px;line-height:1.4;color:{Y}">'
        f'Maestra de clientes - {e(bott)} {e(pais)}<br>({e(M["entrega"])})</p>'
        + footer(A, dark=True)), color=WHITE, pad='64px 96px 150px')

    S['algoritmo'] = photo_split('algoritmo', A['photo_algoritmo'], 'Centro de distribución con personal', (
        f'<p style="font-size:24px;font-weight:500;letter-spacing:3px;color:{G3}">PROSPECCIÓN DIGITAL</p>'
        f'<h2 style="font-family:{SG};font-size:44px;font-weight:500;color:{BLACK}">Lógica del algoritmo</h2>'
        + para(f'El algoritmo asigna un <b>score de similitud</b> (de 0% a 100%) para comparar puntos de venta con clientes existentes. Así identifica qué clientes ya están en la base de datos (<span style="color:{POS}"><b>match</b></span>) y cuáles son nuevos posibles clientes (<span style="color:{NEG}"><b>No Match</b></span>). Utiliza <b>inteligencia artificial</b> para analizar textos y datos de ubicación geográfica.', 24)
        + para('El proceso compara características como:', 24)
        + f'<ul style="font-size:24px;line-height:1.4;color:{G4}"><li><b>Nombre y fonética:</b> similitud en los nombres.</li><li><b>Ubicación geográfica:</b> distancia entre los puntos.</li><li><b>Dirección:</b> concordancia en la ubicación, si está disponible.</li></ul>'
        + para(f'Es un proceso iterativo que ajusta el peso de cada característica para calcular un score final. Luego, se establece un umbral para clasificar los puntos como match o <span style="color:{NEG}">No Match</span>.', 24)
        + para(f'Los puntos <span style="color:{NEG}"><b>No Match</b></span> son comercios que se encuentran fuera del maestro de clientes por alguna de las siguientes razones:', 24)
        + f'<ul style="font-size:24px;line-height:1.4;color:{G4}"><li>Compra productos de la marca por medio de un tercero (Distribuidor)</li><li>Es un comercio no atendido por la embotelladora</li>'
          f'<li>Los comercios no son manejantes de bebidas NARTD</li><li>El comercio ha cerrado o se ha trasladado</li></ul>'), A)

    chip = lambda txt, bg: f'<p style="font-size:26px;background:{bg};color:{BLACK};padding:6px 16px;border-radius:999px">{txt}</p>'
    S['priorizacion'] = section('priorizacion', WHITE, (
        head('Sistema de Priorización de Prospección', eyebrow='')
        + para('El objetivo de este proceso es brindar una métrica que representa la probabilidad de existencia de un <b>POS</b> de acuerdo con la información disponible.')
        + f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:28px">'
        f'<div style="display:flex;flex-direction:column;gap:8px"><p style="font-size:26px;font-weight:600">Variables clave</p>'
        f'<ul style="font-size:24px;line-height:1.4;color:{G4}"><li>Popularidad histórica (últimos 6 meses): recuento ponderado de impresiones.</li><li>Número de reseñas: cantidad de reseñas normalizadas.</li><li>Validity Score: confianza de los datos medida por <b>Dataplor</b>.</li></ul></div>'
        f'<div style="display:flex;flex-direction:column;gap:8px"><p style="font-size:26px;font-weight:600">Segmentación por canal</p>'
        f'<ul style="font-size:24px;line-height:1.4;color:{G4}"><li>On Premise (restaurantes, bares, hoteles, gym, etc.)</li>'
        + ('<li>Off Premise (supermercados, farmacias, tiendas, gasolineras, etc.)</li>' if has_off else '') + '</ul></div>'
        f'<div style="display:flex;flex-direction:column;gap:8px"><p style="font-size:26px;font-weight:600">Score combinado</p>'
        f'<ul style="font-size:24px;line-height:1.4;color:{G4}"><li>Normalización por canal.</li><li>Pesos para cada una de las variables clave.</li></ul></div>'
        f'<div style="display:flex;flex-direction:column;gap:10px"><p style="font-size:26px;font-weight:600">Clasificación final: umbrales sobre el score combinado</p>'
        f'<div style="display:flex;gap:12px;flex-wrap:wrap">{chip("Low: " + t("low"), NEG)}{chip("Moderate: " + t("moderate"), Y)}{chip("High: " + t("high"), POS)}</div></div>'
        f'</div>' + footer(A)))

    S['div-resultados'] = divider('div-resultados', 'Resultados', A)

    S['resumen'] = section('resumen', WHITE, (
        head('Punto de partida')
        + para(M['texto_punto_partida'])
        + f'<div style="display:flex;justify-content:center">{table(["Dataplor", "Embotellador"], [[s9["total_dataplor"], s9["total_embotellador"]]], [50, 50], 26, False, False, 520)}</div>'
        f'<div style="display:flex;gap:20px">'
        f'<div style="flex:3;display:flex;flex-direction:column;gap:6px;border-top:6px solid {POS};padding:16px 8px"><p style="font-size:24px;color:{G3}">No Match · High Confidence</p><p style="font-family:{SG};font-size:32px;font-weight:600">{fmt(s9["high"])} high &amp; {fmt(s9["moderate"])} moderate no-match</p></div>'
        f'<div style="flex:2;display:flex;flex-direction:column;gap:6px;border-top:6px solid {NEG};padding:16px 8px"><p style="font-size:24px;color:{G3}">Low Confidence · Grey Area</p><p style="font-family:{SG};font-size:32px;font-weight:600">{fmt(s9["low"])} no-match</p></div>'
        f'<div style="flex:2;display:flex;flex-direction:column;gap:6px;border-top:6px solid {G4};padding:16px 8px"><p style="font-size:24px;color:{G3}">Possible Match · High Confidence</p><p style="font-family:{SG};font-size:32px;font-weight:600">{fmt(s9["total_match"])} Match</p></div></div>'
        f'<div style="display:flex;justify-content:space-between"><p style="font-size:24px;color:{G3}">0% · No match threshold</p><p style="font-size:24px;color:{G3}">Match threshold · 100%</p></div>'
        f'<div style="display:flex;gap:48px;align-items:center;justify-content:center">'
        f'<h3 style="font-family:{SG};font-size:30px;font-weight:500;width:420px;text-align:right">Resumen de resultados por potencial existencia</h3>'
        + table(['No match', 'POS'], [['High', s9['high']], ['Moderate', s9['moderate']], ['Low', s9['low']], ['Total', s9['total_no_match']]], [60, 40], 24, width=480)
        + '</div>' + footer(A)), notes=M.get('notes_resumen', ''), layout='display:flex;flex-direction:column;gap:20px')

    S['ciudad-canal'] = section('ciudad-canal', WHITE, (
        head('Resumen de resultados')
        + para(f'A continuación se presenta el potencial total identificado en la prospección digital, desglosado por {geo} y canal. Esta vista permite priorizar mercados con mayor concentración de puntos <b>High</b> y <b>Moderate</b>, tanto en <b>Off Premise</b> como en <b>On Premise</b>, para enfocar los esfuerzos comerciales donde el impacto puede ser más alto.'
               if has_off else
               f'A continuación se presenta el potencial total identificado en la prospección digital del canal <b>On Premise</b>, desglosado por {geo}. Esta vista permite priorizar mercados con mayor concentración de puntos <b>High</b> y <b>Moderate</b> para enfocar los esfuerzos comerciales donde el impacto puede ser más alto.')
        + f'<div style="display:flex;gap:56px;align-items:center"><div style="display:flex;flex-direction:column;gap:10px;width:900px">'
        f'<h3 style="font-family:{SG};font-size:30px;font-weight:500;text-align:center">Resumen de resultados*</h3>'
        + (table([Geo] + s10['header'][1:], s10['rows'], [43, 19, 19, 19], 24) if has_off else
           table([Geo, 'On Premise · High + Moderate'], [[r[0], r[-1]] for r in s10['rows']], [55, 45], 24))
        + para('* Total de High y Moderate No-Match points', 24, G3) + '</div>'
        f'<div style="flex:1;display:flex;flex-direction:column;gap:28px">'
        f'<p style="font-family:{SG};font-size:32px;line-height:1.3;text-align:center">{M["callout_10"]}</p>'
        + insight(M['insight_10']) + '</div></div>' + footer(A)), notes=M.get('notes_10', ''))

    on, off = s11.get('On Premise', {}), s11.get('Off Premise', {})
    S['categoria-canal'] = section('categoria-canal', WHITE, (
        head('Resumen de resultados') + para(M['texto_11'])
        + (f'<div style="display:flex;gap:48px">'
           f'<div style="flex:1;display:flex;flex-direction:column;gap:10px"><h3 style="font-family:{SG};font-size:30px;font-weight:600;text-align:center">On Premise</h3>{bars(on.get("bars", []))}</div>'
           f'<div style="flex:1;display:flex;flex-direction:column;gap:10px"><h3 style="font-family:{SG};font-size:30px;font-weight:600;text-align:center">Off Premise</h3>{bars(off.get("bars", []))}</div></div>'
           if off.get('bars') else
           # Aprendido: si un canal no tiene puntos no se muestra su panel vacío
           f'<div style="display:flex;flex-direction:column;gap:10px;align-items:center"><h3 style="font-family:{SG};font-size:30px;font-weight:600;text-align:center">On Premise</h3>{bars(on.get("bars", []), maxw=560)}</div>')
        + insight(M['insight_11']) + footer(A)), notes=M.get('notes_11', ''))

    def detail(sid, ch, d, txt, ins):
        if not d:
            body = (head(f'Detalle de oportunidad canal {ch}')
                    + f'<div style="display:flex;gap:48px;align-items:center"><div style="display:flex;flex-direction:column;gap:6px;background:{DARK};border-radius:12px;padding:40px;width:520px">'
                    f'<p style="font-family:{SG};font-size:96px;font-weight:700;color:{Y}">0</p><p style="font-size:26px;color:{WHITE}">puntos {ch} en esta base</p></div>'
                    f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">{para(txt, 28)}{insight(ins)}</div></div>')
            return section(sid, WHITE, body + footer(A))
        rh = d['right_header']
        rh = rh[:1] + [M.get('geo_abbr', {}).get(x, x) for x in rh[1:]]
        body = (head(f'Detalle de oportunidad canal {ch}') + para(txt, 24)
                + f'<div style="display:flex;gap:40px">'
                f'<div style="flex:1;display:flex;flex-direction:column;gap:10px"><p style="font-size:26px;text-align:center">No Match - probabilidad de existencia</p>'
                + table(d['left_header'], d['left'], [46, 18, 18, 18], 24) + '</div>'
                f'<div style="flex:1;display:flex;flex-direction:column;gap:10px"><p style="font-size:26px;text-align:center">Oportunidad por {geo} y potencial High/Moderate*</p>'
                + table(rh, d['right'], [36] + [64 // (len(rh) - 1)] * (len(rh) - 1), 24) + '</div></div>'
                + f'<div style="display:flex;gap:40px;align-items:start"><div style="flex:1">{insight(ins) if ins else ""}</div>'
                f'<p style="flex:1;font-size:24px;line-height:1.35;color:{G3};text-align:center">*Para esta tabla se ha seleccionado las 5 categorías con mayor oportunidad con alta probabilidad de existencia (high y moderate no-match)</p></div>')
        return section(sid, WHITE, body + footer(A), layout='display:flex;flex-direction:column;gap:22px')

    S['on-premise'] = detail('on-premise', 'On Premise', s12, M['texto_12'], M.get('insight_12', ''))
    if s13:  # Aprendido: sin puntos Off Premise la diapositiva se elimina (no se deja una vacía)
        S['off-premise'] = detail('off-premise', 'Off Premise', s13, M['texto_13'], M.get('insight_13', ''))

    S['mapa'] = section('mapa', WHITE, (
        head(M['titulo_14'], size=44)
        + f'<img src="{A["mapa"]}" alt="{e(M.get("alt_mapa", "Mapa de hexágonos con la densidad de puntos High y Moderate"))}" style="width:1180px;height:540px;object-fit:cover;align-self:center;border-radius:12px">'
        + para(M['texto_14'], 24) + footer(A)), notes=M.get('notes_14', ''), layout='display:flex;flex-direction:column;gap:20px')

    et = s15['etapas']
    desc = [f'Activación de puntos high y moderate en el top 3 {geos} y top 3 categorías de negocio',
            f'Expansión de la activación high y moderate hacia el top 5 {geos} y top 5 categorías, complementando la cobertura inicial',
            f'Activación de puntos high y moderate en el siguiente bloque ampliado, cubriendo el top 8 {geos} y top 8 categorías',
            f'Activación de puntos high y moderate en el resto de {geos} y categorías fuera del top 8']
    desc = M.get('etapas_desc', desc)   # Aprendido: con una sola ciudad, las etapas se nombran por categorías
    lis = ''.join(f'<li><b>Etapa {x["etapa"]}:</b> {dsc} (+{fmt(x["pos"])} POS, +{pc(x["pct"], 2)}'
                  + (f', +{pc(x["pct_acum"], 2)} acumulado)' if x['etapa'] > 1 else ' del portafolio actual)') + '</li>'
                  for x, dsc in zip(et, desc))
    tot, port = s15['total'], D['portafolio']
    lo, hi = round(tot * .5), round(tot * .7)
    dentro = s10.get('total_hm', 0) - s10['area_fuera_hm'] if 'area_fuera_hm' in s10 else None
    total_15 = (f'Las cuatro etapas identifican un potencial bruto de <b>{fmt(tot)} nuevos POS</b>: {fmt(dentro)} dentro del radio actual de las rutas y '
                f'{fmt(s10["area_fuera_hm"])} fuera de este. Esto representa un crecimiento potencial del <b>{pc(s15["total_pct"], 2)}</b> sobre los {fmt(port)} POS actuales.'
                if dentro is not None else
                f'En total, la activación por etapas representa un potencial de <b>+{fmt(tot)}</b> nuevos puntos, equivalente a un crecimiento de <b>+{pc(s15["total_pct"], 2)}</b> sobre el portafolio actual ({fmt(port)} POS).')
    nota_15 = (f'* Considerando una tasa estimada de validación en campo del 50 %–70 %, se proyecta una captura neta de <b>{fmt(lo)}–{fmt(hi)} POS</b>, '
               f'equivalente a un crecimiento del <b>{pc(lo / port * 100, 2)}–{pc(hi / port * 100, 2)}</b>. Estos resultados están sujetos a validación.')
    S['impacto'] = section('impacto', WHITE, (
        head('Impacto del proyecto')
        + para(M.get('texto_15', f'De acuerdo a los datos y análisis mostrados, consideramos que se puede capturar valor para {e(bott)} de la siguiente manera:'))
        + f'<p style="font-family:{SG};font-size:32px;font-weight:500">Resultados esperados por etapas*</p>'
        + f'<ul style="font-size:26px;line-height:1.5;color:{G4}">{lis}</ul>'
        + para(total_15, 28, BLACK, 'text-align:center') + para(nota_15, 24, G3)
        + footer(A)), notes=M.get('notes_15', ''), layout='display:flex;flex-direction:column;gap:20px')

    S['div-pasos'] = divider('div-pasos', 'Siguientes pasos', A)
    S['pasos'] = section('pasos', DARK, (
        f'<img src="{A["collage"]}" alt="Collage de hexágonos con fotos de equipos de trabajo" style="position:absolute;left:1338px;top:0px;width:582px;height:937px;object-fit:cover">'
        f'<h2 style="font-family:{SG};font-size:56px;font-weight:500;color:{WHITE}">Próximos Pasos</h2>'
        f'<ul style="font-size:30px;line-height:1.7;color:{WHITE};width:1100px;display:flex;flex-direction:column;gap:28px">'
        f'<li>Proporcionar la base de datos de prospección (puntos de alta y moderada probabilidad de no match) para que los equipos de campo puedan priorizar y planificar las visitas de forma eficiente.</li>'
        f'<li>Validar los puntos de alta y moderada probabilidad no-match en el campo, centrándose en las áreas con mayor potencial comercial para acelerar la captación de nuevos clientes.</li>'
        f'<li>Compartir los resultados y la retroalimentación con los equipos comerciales para orientar las siguientes fases de activación y perfeccionar la precisión del ejercicio.</li></ul>'
        + footer(A, dark=True)), color=WHITE, pad='96px 96px 150px', notes=M.get('notes_pasos', ''))
    S['div-datos'] = divider('div-datos', 'Vista previa a los datos', A)

    for i, g in enumerate(M['glosario'], 1):
        cols = ''.join(f'<div style="flex:1;display:flex;flex-direction:column;gap:12px">'
                       + ''.join(f'<p style="font-size:24px;line-height:1.4;color:{G4}">{x}</p>' for x in col) + '</div>'
                       for col in g['cols'])
        img = (f'<img src="{A[g["img"]]}" alt="{e(g["alt"])}" style="width:1600px;height:280px;object-fit:contain;align-self:center;border:1px solid {G2}">'
               if g.get('img') and g['img'] in A else '')
        S[f'glosario-{i}'] = section(f'glosario-{i}', WHITE, (
            head('Glosario', eyebrow='') + f'<div style="display:flex;gap:56px">{cols}</div>' + img + footer(A)),
            layout='display:flex;flex-direction:column;gap:24px')

    contacts = ''.join(f'<p style="font-size:30px;color:{BLACK}">{e(c)}</p>' for c in M['contactos'])
    S['cierre'] = section('cierre', Y, (
        f'<h1 style="font-family:{SG};font-size:180px;font-weight:700;line-height:1;color:{BLACK}">{M.get("cierre", "Let<br>Knowledge in")}</h1>'
        f'<div style="display:flex;flex-direction:column;gap:6px"><p style="font-size:30px;color:{BLACK}">Contactos:</p>{contacts}</div>'
        f'<img src="{A["logo_light"]}" alt="Kin Analytics" style="position:absolute;right:96px;bottom:64px;width:460px;height:110px;object-fit:contain">'),
        layout='display:flex;flex-direction:column;justify-content:center;gap:120px', pad='96px 120px 150px')
    return S


ORDER = ['cover', 'agenda', 'objetivo', 'ciclo', 'proceso', 'algoritmo', 'priorizacion', 'div-resultados', 'resumen',
         'ciudad-canal', 'categoria-canal', 'on-premise', 'off-premise', 'mapa', 'impacto', 'div-pasos', 'pasos',
         'div-datos', 'glosario-1', 'glosario-2', 'glosario-3', 'cierre']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='deck_data.json (o plantilla_rd_ejemplo.json, que trae meta incluida)')
    ap.add_argument('--meta', help='meta.json con textos, insights y datos del cliente')
    ap.add_argument('--assets', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title')
    a = ap.parse_args()
    D = json.loads(Path(a.data).read_text(encoding='utf-8'))
    M = json.loads(Path(a.meta).read_text(encoding='utf-8')) if a.meta else D['meta']
    A = json.loads(Path(a.assets).read_text(encoding='utf-8'))
    S = build(D, M, A)
    root = Path(a.out)
    (root / 'project' / 'slides').mkdir(parents=True, exist_ok=True)
    for sid, htm in S.items():
        (root / 'project' / 'slides' / f'{sid}.html').write_text(htm, encoding='utf-8')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    deck = {'v': 4, 'createdOnFiles': {'v': 1, 'at': now}, 'lists': 'css',
            'title': a.title or f"Prospección Digital — {M['pais']} · {M['embotelladora']} — {M['fecha']}",
            'cover': 'cover', 'order': [x for x in ORDER if x in S],
            'sections': {'s1': {'description': 'Introducción y generalidades del proyecto y del algoritmo', 'start': 'cover'},
                         's2': {'description': 'Análisis y resultados de la prospección', 'start': 'div-resultados'},
                         's3': {'description': 'Siguientes pasos', 'start': 'div-pasos'},
                         's4': {'description': 'Vista previa y glosario de la base', 'start': 'div-datos'}},
            'faces': {'space-grotesk': {'family': 'Space Grotesk', 'src': 'project/ds/kin/fonts/SpaceGrotesk-VariableFont_wght.ttf'},
                      'albert-sans': {'family': 'Albert Sans', 'src': 'project/ds/kin/fonts/AlbertSans-VariableFont_wght.ttf'}},
            'designSystems': [{'title': 'Kin Design System - Kin Official', 'namespace': 'kin',
                               'artifact': 'https://claude.ai/artifact/Kyrvxqzwp78R1ZzWhrgBHK', 'version': '1792096519-1a0c',
                               'copiedAt': now}]}
    (root / 'project' / 'deck.json').write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'OK → {root} ({len(S)} diapositivas)')


if __name__ == '__main__':
    main()

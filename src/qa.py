"""Paso 1 — QA de prospección (skill prospection-qa) en un solo comando.

Uso:
    python src/qa.py mx/Golfo [--benchmark output/mx/Golfo/qa/benchmark.json]
                              [--clientes RUTA] [--datamatch RUTA] [--threshold 0.65]

Lee data/<pais>/<region>/{clientes,datamatch}/ (el archivo más reciente de cada carpeta) y escribe
en output/<pais>/<region>/qa/:
    map_overview.html, map_mistakes.html, mistakes_report.csv, category_mapping.xlsx,
    category_issues.xlsx, no_match_enriched.xlsx, qa_report.html, qa_summary.json

El benchmark de mercado (Paso 6 de la skill) requiere búsqueda web: Claude lo investiga y lo pasa
como JSON {"market","penetration","sources":[{"title","url"}],"assessment","verdict"}; luego se
vuelve a correr el script solo con --benchmark para regenerar el reporte.
"""
import argparse
import html
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import unicodedata

from rapidfuzz import fuzz, process, utils
from sklearn.neighbors import BallTree

from common import (latest_file, market_dirs, normalize_match, read_table, save_json, schema)

EARTH_M = 6_371_000
GEO_MAX_M = 300

# Categorías claramente no-bebida (heurística; ante la duda se conservan)
NON_BEV = re.compile(r'hardware|ferreter|clothing|ropa|apparel|auto[ _]?parts|refaccion|car[ _]?(repair|dealer|wash)|'
                     r'taller|mechanic|bank|banco|atm|insurance|seguro|real[ _]?estate|inmobili|dentist|dental|'
                     r'doctor|hospital|clinic|veterin|lawyer|abogad|accountant|church|iglesia|school|escuela|'
                     r'university|universidad|furniture|mueble|electronics|electr[oó]nica|phone|celular|'
                     r'jewel|joyer|optic|[oó]ptica|laundry|lavander|hair|salon|barber|est[eé]tica|beauty|'
                     r'shoe|zapater|tailor|plumb|electrician|government|gobierno|police|parking|estacionamiento|'
                     r'storage|bodega de almacenamiento|funeral|cemetery|library|biblioteca|museum', re.I)


def norm(s):
    """Minúsculas y sin acentos: 'ANTOJÍTOS' == 'antojitos'."""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return utils.default_process(s)


def tokenize(s):
    return re.findall(r'[a-z0-9]+', norm(s))


def build_idf(names):
    df_count = Counter()
    for n in names:
        df_count.update(set(tokenize(n)))
    N = len(names)
    return {t: math.log(N / (1 + c)) for t, c in df_count.items()}


def tfidf_cosine(a, b, idf):
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    ca, cb = Counter(ta), Counter(tb)
    dot = na = nb = 0.0
    for t in set(ta) | set(tb):
        w = idf.get(t, 1.0)
        va, vb = ca.get(t, 0) * w, cb.get(t, 0) * w
        dot += va * vb
        na += va * va
        nb += vb * vb
    return dot / (math.sqrt(na) * math.sqrt(nb)) if na > 0 and nb > 0 else 0.0


def detect_mistakes(nm, cl, s_p, s_c, idf, threshold):
    """Mejor candidato de la base de clientes para cada no_match. Solo los que están a <300 m
    pueden pasar el umbral (con geo_score=0 el combinado máximo es 0.6 < 0.65)."""
    tree = BallTree(np.radians(cl[[s_c['lat'], s_c['lng']]].to_numpy(float)), metric='haversine')
    pts = np.radians(nm[[s_p['lat'], s_p['lng']]].to_numpy(float))
    idxs, dists = tree.query_radius(pts, r=GEO_MAX_M / EARTH_M, return_distance=True)
    rows = []
    for i, (cand, dist) in enumerate(zip(idxs, dists)):
        if len(cand) == 0:
            continue
        p = nm.iloc[i]
        best = None
        for j, d in zip(cand, dist * EARTH_M):
            c = cl.iloc[j]
            fz = fuzz.token_sort_ratio(norm(p[s_p['name']]), norm(c[s_c['name']])) / 100
            tf = tfidf_cosine(p[s_p['name']], c[s_c['name']], idf)
            name_score = 0.5 * fz + 0.5 * tf
            geo = max(0.0, 1 - d / GEO_MAX_M)
            comb = 0.4 * geo + 0.6 * name_score
            if best is None or comb > best['combined_score']:
                best = dict(j=j, distance_meters=round(d, 1), name_similarity_pct=round(fz * 100, 1),
                            tfidf_cosine=round(tf, 3), hybrid_name_score=round(name_score, 3),
                            geo_score=round(geo, 3), name_score=round(name_score, 3),
                            combined_score=round(comb, 3))
        if best['combined_score'] < threshold:
            continue
        c = cl.iloc[best.pop('j')]
        g, n = best['geo_score'], best['name_score']
        reason = 'both_strong' if g >= 0.6 and n >= 0.6 else ('proximity_dominant' if g > n else 'name_dominant')
        rows.append(dict(
            prospection_outlet_name=p[s_p['name']], prospection_outlet_id=p[s_p['id']],
            prospection_lat=p[s_p['lat']], prospection_lon=p[s_p['lng']],
            prospection_category=p[s_p['cat']] if s_p['cat'] else '',
            client_base_outlet_name=c[s_c['name']], client_base_outlet_id=c[s_c['id']],
            client_base_lat=c[s_c['lat']], client_base_lon=c[s_c['lng']],
            client_base_category=c[s_c['cat']] if s_c['cat'] else '',
            **best, match_reason=reason))
    cols = ['prospection_outlet_name', 'prospection_outlet_id', 'prospection_lat', 'prospection_lon',
            'prospection_category', 'client_base_outlet_name', 'client_base_outlet_id', 'client_base_lat',
            'client_base_lon', 'client_base_category', 'distance_meters', 'name_similarity_pct', 'tfidf_cosine',
            'hybrid_name_score', 'geo_score', 'name_score', 'combined_score', 'match_reason']
    return pd.DataFrame(rows, columns=cols).sort_values('combined_score', ascending=False)


def client_coverage(pr, cl, s_p, s_c, radius_m=50):
    """% de clientes con algún POI de Dataplor a <= radius_m (señal de completitud de la base)."""
    tree = BallTree(np.radians(pr[[s_p['lat'], s_p['lng']]].to_numpy(float)), metric='haversine')
    cnt = tree.query_radius(np.radians(cl[[s_c['lat'], s_c['lng']]].to_numpy(float)),
                            r=radius_m / EARTH_M, count_only=True)
    return float((cnt > 0).mean())


def category_outputs(pr, cl, s_p, s_c, out):
    """Pasos 5a–5c. Devuelve (tabla 5a, mapping dict, set no-bebida) o Nones si no hay categorías."""
    if not s_p['cat'] and not s_c['cat']:
        pd.DataFrame([{'note': 'Ninguna base tiene columna de categoría'}]).to_excel(out / 'category_mapping.xlsx', index=False)
        pd.DataFrame([{'note': 'Ninguna base tiene columna de categoría'}]).to_excel(out / 'category_issues.xlsx', index=False)
        return None, {}, set()
    cat_tab = None
    if s_p['cat']:
        g = pr.groupby(pr[s_p['cat']].fillna('(vacío)'))['_m']
        cat_tab = pd.DataFrame({'total': g.size(), 'match': g.apply(lambda s: (s == 'match').sum()),
                                'no_match': g.apply(lambda s: (s == 'no_match').sum())})
        cat_tab['no_match_share'] = (cat_tab['no_match'] / cat_tab['total'] * 100).round(1)
        cat_tab = cat_tab.sort_values('no_match_share', ascending=False).reset_index(names='category')
    mapping = {}
    p_cats = sorted(pr[s_p['cat']].dropna().astype(str).unique()) if s_p['cat'] else []
    c_cats = sorted(cl[s_c['cat']].dropna().astype(str).unique()) if s_c['cat'] else []
    rows = []
    for pc in p_cats:
        best = process.extractOne(pc, c_cats, scorer=fuzz.token_sort_ratio, processor=norm) if c_cats else None
        if best and best[1] >= 60:
            conf = 'High' if best[1] >= 85 else ('Medium' if best[1] >= 70 else 'Low')
            mapping[pc] = (best[0], conf)
            rows.append(dict(prospection_category=pc, client_base_category=best[0], confidence=conf,
                             notes=f'fuzzy {best[1]:.0f} — revisar semánticamente'))
        else:
            rows.append(dict(prospection_category=pc, client_base_category='', confidence='',
                             notes='sin equivalente (revisar semánticamente)'))
    for cc in c_cats:
        if cc not in {m[0] for m in mapping.values()}:
            rows.append(dict(prospection_category='', client_base_category=cc, confidence='',
                             notes='solo en base de clientes'))
    pd.DataFrame(rows).to_excel(out / 'category_mapping.xlsx', index=False)
    non_bev = {c for c in p_cats if NON_BEV.search(c)}
    if non_bev:
        iss = cat_tab[cat_tab['category'].isin(non_bev)][['category', 'total', 'no_match']]
        iss = iss.rename(columns={'total': 'outlet_count', 'no_match': 'no_match_count'})
        iss['reason'] = 'Categoría que normalmente no comercializa bebidas (heurística)'
        iss.to_excel(out / 'category_issues.xlsx', index=False)
    else:
        pd.DataFrame([{'category': 'No non-beverage categories detected.'}]).to_excel(out / 'category_issues.xlsx', index=False)
    return cat_tab, mapping, non_bev


def enriched_no_match(nm, s_p, mistakes, mapping, non_bev, c_cats, out):
    reason_by_id = dict(zip(mistakes['prospection_outlet_id'], mistakes['match_reason']))
    pri = {'both_strong': 'false_negative_both_strong', 'proximity_dominant': 'false_negative_proximity',
           'name_dominant': 'false_negative_name_similarity'}
    e = nm.drop(columns=['_m']).copy()
    sug, mc, conf = [], [], []
    for _, r in e.iterrows():
        cat = str(r[s_p['cat']]) if s_p['cat'] and pd.notna(r[s_p['cat']]) else ''
        m = mapping.get(cat)
        mc.append(m[0] if m else '')
        conf.append(m[1] if m else '')
        rid = r[s_p['id']]
        if rid in reason_by_id:
            sug.append(pri[reason_by_id[rid]])
        elif m and m[1] in ('High', 'Medium') and m[0] in c_cats:
            sug.append('false_negative_category')
        elif cat in non_bev:
            sug.append('no_beverage_category')
        else:
            sug.append('')
    e['excluding_suggestion'], e['mapped_category'], e['mapped_category_confidence'] = sug, mc, conf
    e['_blank'] = e['excluding_suggestion'].eq('')
    e = e.sort_values(['_blank', 'excluding_suggestion', s_p['name']]).drop(columns='_blank')
    e.to_excel(out / 'no_match_enriched.xlsx', index=False)
    return e


# ── HTML ──────────────────────────────────────────────────────────────────────────────────────
LEAFLET = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
           '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')


def leaflet_page(title, layers_js, center, legend_html):
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">{LEAFLET}
<style>html,body,#map{{height:100%;margin:0}}.legend{{background:#fff;padding:8px 10px;border-radius:6px;
font:13px system-ui;box-shadow:0 1px 4px rgba(0,0,0,.3)}}.legend i{{display:inline-block;width:11px;height:11px;
border-radius:50%;margin-right:6px}}</style></head><body><div id="map"></div><script>
const map=L.map('map',{{preferCanvas:true}}).setView([{center[0]},{center[1]}],12);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}',
 {{maxZoom:16,attribution:'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap'}}).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:16}}).addTo(map);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const overlays={{}};
{layers_js}
L.control.layers(null,overlays,{{collapsed:false}}).addTo(map);
const lg=L.control({{position:'bottomright'}});lg.onAdd=()=>{{const d=L.DomUtil.create('div','legend');d.innerHTML=`{legend_html}`;return d}};lg.addTo(map);
</script></body></html>"""


def points_js(var, label, recs, color, radius, popup_fields):
    data = json.dumps(recs, ensure_ascii=False, default=str)
    pop = '+'.join(f"'<b>{k}:</b> '+esc(p[{json.dumps(f)}])+'<br>'" for k, f in popup_fields)
    return (f"const {var}=L.layerGroup();{data}.forEach(p=>L.circleMarker([p.lat,p.lng],{{radius:{radius},"
            f"color:'{color}',fillColor:'{color}',fillOpacity:.75,weight:1}}).bindPopup({pop}).addTo({var}));"
            f"{var}.addTo(map);overlays[{json.dumps(label)}]={var};\n")


def recs(df, s, extra):
    cols = {'lat': s['lat'], 'lng': s['lng'], 'name': s['name'], 'id': s['id'], **extra}
    cols = {k: v for k, v in cols.items() if v}
    return df[list(cols.values())].rename(columns={v: k for k, v in cols.items()}).to_dict('records')


def donut_svg(match, no_match):
    tot = match + no_match or 1
    frac = match / tot
    r, C = 60, 2 * math.pi * 60
    return (f'<svg width="170" height="170" viewBox="0 0 170 170"><circle cx="85" cy="85" r="{r}" fill="none" '
            f'stroke="#cfd6e4" stroke-width="26"/><circle cx="85" cy="85" r="{r}" fill="none" stroke="#1a2b4a" '
            f'stroke-width="26" stroke-dasharray="{frac * C:.1f} {C:.1f}" transform="rotate(-90 85 85)"/>'
            f'<text x="85" y="91" text-anchor="middle" font-size="20" font-weight="700" fill="#1a2b4a">'
            f'{frac * 100:.1f}%</text></svg>')


def table_html(df, cls_fn=None):
    head = ''.join(f'<th>{html.escape(str(c))}</th>' for c in df.columns)
    body = ''
    for _, r in df.iterrows():
        cls = cls_fn(r) if cls_fn else ''
        body += f'<tr class="{cls}">' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in r.values) + '</tr>'
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def report_html(S, cat_tab, mistakes, bench, files):
    pct = lambda x: f'{x * 100:.1f}%'
    reasons = S['mistakes_by_reason']
    sec3 = '<p>No hay columna de categoría en las bases: análisis por categoría omitido.</p>'
    if cat_tab is not None:
        sec3 = table_html(cat_tab, lambda r: 'red' if r['no_match_share'] > 75 else ('amber' if r['no_match_share'] > 50 else ''))
        sec3 += f"<p>Categorías no-bebida marcadas: {', '.join(S['non_beverage_categories']) or 'ninguna'}.</p>"
    top10 = mistakes.head(10)[['prospection_outlet_name', 'prospection_outlet_id', 'client_base_outlet_name',
                               'client_base_outlet_id', 'distance_meters', 'name_similarity_pct',
                               'combined_score', 'match_reason']]
    if bench:
        src = ''.join(f'<li><a href="{html.escape(s["url"])}">{html.escape(s["title"])}</a></li>' for s in bench.get('sources', []))
        sec5 = (f"<p><b>Mercado:</b> {html.escape(bench.get('market', S['market']))}</p>"
                f"<p><b>Penetración Coca-Cola:</b> {html.escape(bench.get('penetration', ''))}</p><ul>{src}</ul>"
                f"<p>{html.escape(bench.get('assessment', ''))}</p><p><b>Veredicto:</b> {html.escape(bench.get('verdict', ''))}</p>")
    else:
        sec5 = '<p><i>Pendiente: benchmark de mercado (requiere búsqueda web).</i></p>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>QA Prospección — {html.escape(S['market'])}</title>
<style>body{{font-family:system-ui,Inter,sans-serif;background:#f8f9fa;color:#222;margin:0;padding:32px}}
.wrap{{max-width:1100px;margin:auto}}h1,h2{{color:#1a2b4a}}.card{{background:#fff;border-radius:10px;
box-shadow:0 1px 4px rgba(0,0,0,.08);padding:20px 24px;margin:18px 0}}.kpis{{display:flex;gap:16px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:150px;background:#f1f4f9;border-radius:8px;padding:12px}}.kpi b{{font-size:24px;display:block;color:#1a2b4a}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid #e3e6ea;padding:6px 8px;text-align:left}}
th{{background:#1a2b4a;color:#fff}}tr.amber td{{background:#fff4d6}}tr.red td{{background:#fde0de}}
.flex{{display:flex;gap:24px;align-items:center}}footer{{color:#888;font-size:12px;margin-top:24px}}
@media print{{body{{padding:0}}.card{{box-shadow:none;border:1px solid #ddd}}}}</style></head><body><div class="wrap">
<h1>QA de prospección — {html.escape(S['market'])}</h1>
<div class="card"><h2>1. Resumen ejecutivo</h2><div class="flex">{donut_svg(S['match'], S['no_match'])}
<div class="kpis"><div class="kpi"><b>{S['client_base']:,}</b>clientes (maestra)</div>
<div class="kpi"><b>{S['prospection_total']:,}</b>POIs prospección</div>
<div class="kpi"><b>{pct(S['match_rate'])}</b>match ({S['match']:,})</div>
<div class="kpi"><b>{S['mistakes']:,}</b>posibles falsos negativos ({pct(S['mistakes_share_of_no_match'])} del no_match)</div>
<div class="kpi"><b>{pct(S['client_coverage_50m'])}</b>clientes con un POI a ≤50 m</div></div></div></div>
<div class="card"><h2>2. Comparación de bases</h2>{table_html(pd.DataFrame(S['base_comparison']))}</div>
<div class="card"><h2>3. Categorías</h2>{sec3}</div>
<div class="card"><h2>4. Errores (falsos negativos)</h2>
<p>Total: <b>{S['mistakes']}</b> — both_strong {reasons.get('both_strong', 0)}, proximity_dominant
{reasons.get('proximity_dominant', 0)}, name_dominant {reasons.get('name_dominant', 0)}. Lista completa en
<code>mistakes_report.csv</code>; mapa en <code>map_mistakes.html</code>.</p>{table_html(top10)}</div>
<div class="card"><h2>5. Contexto de penetración de mercado</h2>{sec5}</div>
<footer>Generado {datetime.now():%Y-%m-%d %H:%M} · clientes: {html.escape(files[0])} · prospección: {html.escape(files[1])}</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('market')
    ap.add_argument('--clientes')
    ap.add_argument('--datamatch')
    ap.add_argument('--threshold', type=float, default=0.65)
    ap.add_argument('--benchmark')
    a = ap.parse_args()

    data, outroot = market_dirs(a.market)
    out = outroot / 'qa'
    out.mkdir(parents=True, exist_ok=True)
    f_cl = Path(a.clientes) if a.clientes else latest_file(data / 'clientes')
    f_pr = Path(a.datamatch) if a.datamatch else latest_file(data / 'datamatch')
    cl, pr = read_table(f_cl), read_table(f_pr)
    s_c, s_p = schema(cl), schema(pr)
    for k in ('lat', 'lng', 'name', 'id'):
        if not s_c[k] or not s_p[k]:
            raise SystemExit(f'Falta columna {k}: clientes={s_c[k]} prospección={s_p[k]}')
    if not s_p['match']:
        raise SystemExit('No hay columna match_no_match: definir umbral sobre total_score y reintentar.')
    cl = cl.dropna(subset=[s_c['lat'], s_c['lng']]).reset_index(drop=True)
    pr = pr.dropna(subset=[s_p['lat'], s_p['lng']]).reset_index(drop=True)
    pr['_m'] = normalize_match(pr[s_p['match']])
    nm = pr[pr['_m'] == 'no_match'].reset_index(drop=True)

    idf = build_idf(pd.concat([pr[s_p['name']], cl[s_c['name']]]).dropna().astype(str).tolist())
    mistakes = detect_mistakes(nm, cl, s_p, s_c, idf, a.threshold)
    mistakes.drop(columns=['prospection_lat', 'prospection_lon', 'client_base_lat', 'client_base_lon',
                           'tfidf_cosine', 'hybrid_name_score']).to_csv(out / 'mistakes_report.csv', index=False, encoding='utf-8-sig')

    cat_tab, mapping, non_bev = category_outputs(pr, cl, s_p, s_c, out)
    c_cats = set(cl[s_c['cat']].dropna().astype(str)) if s_c['cat'] else set()
    enriched_no_match(nm, s_p, mistakes, mapping, non_bev, c_cats, out)

    # Mapas
    center = (pr[s_p['lat']].mean(), pr[s_p['lng']].mean())
    extra_p = {'addr': s_p['addr'], 'cat': s_p['cat']}
    pf = [('Nombre', 'name'), ('ID', 'id'), ('Dirección', 'addr'), ('Categoría', 'cat'), ('Estado', 'status')]
    rc = recs(cl, s_c, {'cat': s_c['cat']})
    for r in rc:
        r['status'] = 'client_base'
    rm = recs(pr[pr['_m'] == 'match'], s_p, extra_p)
    rn = recs(nm, s_p, extra_p)
    for r in rm:
        r['status'] = 'match'
    for r in rn:
        r['status'] = 'no_match'
    js = (points_js('lc', 'Clientes (maestra)', rc, '#d62728', 7, pf) +
          points_js('lm', 'Prospección — match', rm, '#1f77b4', 7, pf) +
          points_js('ln', 'Prospección — no_match', rn, '#2ca02c', 7, pf))
    leg = "<i style='background:#d62728'></i>Clientes<br><i style='background:#1f77b4'></i>Match<br><i style='background:#2ca02c'></i>No match"
    (out / 'map_overview.html').write_text(leaflet_page(f'QA {a.market} — overview', js, center, leg), encoding='utf-8')

    pairs = mistakes.to_dict('records')
    js2 = (f"const mk=L.layerGroup();{json.dumps(pairs, ensure_ascii=False, default=str)}.forEach(p=>{{"
           "const info='<br><b>Distancia:</b> '+p.distance_meters+' m<br><b>Similitud nombre:</b> '+p.name_similarity_pct+"
           "'%<br><b>Combined:</b> '+p.combined_score+'<br><b>Motivo:</b> '+p.match_reason;"
           "L.polyline([[p.prospection_lat,p.prospection_lon],[p.client_base_lat,p.client_base_lon]],{color:'#999',weight:2,dashArray:'5,5'}).addTo(mk);"
           "L.circleMarker([p.prospection_lat,p.prospection_lon],{radius:9,color:'#ff7f0e',fillColor:'#ff7f0e',fillOpacity:.8,weight:1})"
           ".bindPopup('<b>No_match:</b> '+esc(p.prospection_outlet_name)+'<br><b>ID:</b> '+esc(p.prospection_outlet_id)+'<br><b>Categoría:</b> '+esc(p.prospection_category)+info).addTo(mk);"
           "L.circleMarker([p.client_base_lat,p.client_base_lon],{radius:9,color:'#9467bd',fillColor:'#9467bd',fillOpacity:.8,weight:1})"
           ".bindPopup('<b>Cliente:</b> '+esc(p.client_base_outlet_name)+'<br><b>ID:</b> '+esc(p.client_base_outlet_id)+'<br><b>Categoría:</b> '+esc(p.client_base_category)+info).addTo(mk);"
           "});mk.addTo(map);overlays['Pares de error']=mk;\n")
    leg2 = "<i style='background:#ff7f0e'></i>No_match (posible error)<br><i style='background:#9467bd'></i>Cliente en maestra"
    (out / 'map_mistakes.html').write_text(leaflet_page(f'QA {a.market} — errores', js2, center, leg2), encoding='utf-8')

    # Resumen
    n_match, n_nm = int((pr['_m'] == 'match').sum()), len(nm)
    bbox = lambda d, s: f"{d[s['lat']].min():.3f}…{d[s['lat']].max():.3f}, {d[s['lng']].min():.3f}…{d[s['lng']].max():.3f}"
    S = dict(
        market=a.market, files=[f_cl.name, f_pr.name], client_base=len(cl), prospection_total=len(pr),
        match=n_match, no_match=n_nm, match_rate=n_match / len(pr) if len(pr) else 0,
        mistakes=len(mistakes), mistakes_share_of_no_match=len(mistakes) / n_nm if n_nm else 0,
        mistakes_by_reason=mistakes['match_reason'].value_counts().to_dict(),
        client_coverage_50m=client_coverage(pr, cl, s_p, s_c, 50),
        matched_share_of_client_base=pr.loc[pr['_m'] == 'match', 'pos_id'].nunique() / len(cl) if 'pos_id' in pr else None,
        categories_prospection=int(pr[s_p['cat']].nunique()) if s_p['cat'] else 0,
        non_beverage_categories=sorted(non_bev),
        columns_prospection=s_p, columns_clientes=s_c,
        priority_columns_present={k: bool(s_p[k]) for k in ('exist', 'channel', 'cat', 'city')},
        base_comparison=[
            {'métrica': 'Total de outlets', 'clientes': f'{len(cl):,}', 'prospección': f'{len(pr):,}'},
            {'métrica': 'Bounding box (lat, lng)', 'clientes': bbox(cl, s_c), 'prospección': bbox(pr, s_p)},
            {'métrica': 'Categorías únicas', 'clientes': cl[s_c['cat']].nunique() if s_c['cat'] else 'n/d',
             'prospección': pr[s_p['cat']].nunique() if s_p['cat'] else 'n/d'},
            {'métrica': 'Match (% de clientes)', 'clientes': '—',
             'prospección': f"{n_match:,} ({n_match / len(cl) * 100:.2f}% de la maestra)"},
        ])
    bench = json.loads(Path(a.benchmark).read_text(encoding='utf-8')) if a.benchmark else None
    S['benchmark'] = bench
    (out / 'qa_report.html').write_text(report_html(S, cat_tab, mistakes, bench, S['files']), encoding='utf-8')
    save_json(S, out / 'qa_summary.json')

    print(f"""=== Prospection QA Summary — {a.market} ===
client_base outlets:           {len(cl):,}
prospection_output (match):    {n_match:,}
prospection_output (no_match): {n_nm:,}
Match rate:                    {S['match_rate'] * 100:.2f}%
Clientes con POI a <=50 m:     {S['client_coverage_50m'] * 100:.1f}%

Mistakes detected:             {len(mistakes):,}  ({S['mistakes_share_of_no_match'] * 100:.1f}% of no_match points)
  -> Proximity dominant:  {S['mistakes_by_reason'].get('proximity_dominant', 0)}
  -> Name dominant:       {S['mistakes_by_reason'].get('name_dominant', 0)}
  -> Both strong:         {S['mistakes_by_reason'].get('both_strong', 0)}

Category analysis:             {'n/d (sin columna de categoría)' if cat_tab is None else f"{S['categories_prospection']} categorías, {len(non_bev)} no-bebida"}
Columnas Priority presentes:   {S['priority_columns_present']}
Benchmark de mercado:          {'incluido' if bench else 'PENDIENTE (correr con --benchmark)'}

Outputs: {out}""")


if __name__ == '__main__':
    main()

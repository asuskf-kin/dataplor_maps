"""Paso 3 — Cifras del deck según la plantilla oficial (Prospeccion_Digital_<Pais>_<Bottler>.pptx) → deck_data.json.

Uso:
    python src/deck_data.py mx/Golfo --portafolio 1767 [--priority RUTA] [--geo city|state]

Plantilla de referencia: data/templates/Prospeccion_Digital_Republica_Dominicana_Bepensa_Junio_2026.pptx
(22 diapositivas). Cada bloque de abajo reproduce una diapositiva de esa plantilla:
  9  Punto de partida: Dataplor / Embotellador + High/Moderate/Low/Total no-match + Match
  10 Resumen: geo × canal (Off / On / Total) de High+Moderate no-match, top 5 + Otros + Total
  11 Top categorías High+Moderate por canal (barras On / Off)
  12 / 13 Detalle On / Off: Business Category | High | Moderate | Total (top 5 + Otros + Total)
          y Business Category | Geo1 | Geo2 | Otros | Total
  14 Geo con más High+Moderate (mapa)
  15 Etapas: top 3 / 5 / 8 geo × top 3 / 5 / 8 categorías (incrementales) + resto
  7  Umbrales del score (min/max reales de cada categoría de existencia)

Si la base no trae match_no_match, cada fila es no-match y el match sale del datamatch. Se aplican
las exclusiones de data/<pais>/<region>/exclusiones.csv. --portafolio = total de la maestra.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

from common import (resolve_dir, apply_exclusions, find_col, fmt, latest_file, market_dirs, normalize_match,
                    read_table, save_json, schema)

HM = ('high', 'moderate')
CHANNELS = ['Off Premise', 'On Premise']


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def title(s):
    return str(s).replace('_', ' ').strip().title()


def norm_geo(c):
    """'Municipio de Veracruz' / 'Heroica Veracruz' → 'Veracruz'."""
    t = re.sub(r'^(municipio de|heroica|h\.)\s+', '', str(c).strip(), flags=re.I).strip().title()
    return re.sub(r'(?<=\s)(De|Del|La|Las|Los|Y)(?=\s)', lambda m: m.group(1).lower(), t)  # 'Santa Lucía del Camino'


def channel_detail(hm_ch, geo_top2):
    """Diapositivas 12/13: (izq) categoría × High | Moderate | Total; (der) categoría × Geo1 | Geo2 | Otros | Total."""
    if hm_ch.empty:
        return None
    top = hm_ch['business_category'].value_counts().head(5).index.tolist()
    k = hm_ch['business_category'].where(hm_ch['business_category'].isin(top), '__otros__')
    order = top + ['__otros__']
    left_t = hm_ch.groupby([k, 'exist']).size().unstack(fill_value=0).reindex(index=order, columns=list(HM), fill_value=0)
    left = [['Otros' if i == '__otros__' else title(i), int(r['high']), int(r['moderate']), int(r.sum())] for i, r in left_t.iterrows()]
    left.append(['Total', int(left_t['high'].sum()), int(left_t['moderate'].sum()), len(hm_ch)])
    g = hm_ch['geo'].where(hm_ch['geo'].isin(geo_top2), 'Otros')
    cols = geo_top2 + ['Otros']
    right_t = hm_ch.groupby([k, g]).size().unstack(fill_value=0).reindex(index=order, columns=cols, fill_value=0)
    right = [['Otros' if i == '__otros__' else title(i)] + [int(x) for x in r] + [int(r.sum())] for i, r in right_t.iterrows()]
    right.append(['Total'] + [int(x) for x in right_t.sum()] + [len(hm_ch)])
    n = len(hm_ch)
    top_n = int(hm_ch['business_category'].isin(top).sum())
    top2_geo_n = int(hm_ch['geo'].isin(geo_top2).sum())
    return dict(left_header=['Business Category', 'High', 'Moderate', 'Total'], left=left,
                right_header=['Business Category'] + geo_top2 + ['Otros', 'Total'], right=right,
                total_hm=n, top_cats=[title(c) for c in top], top_cats_pct=pct(top_n, n),
                geo_top2=geo_top2, geo_top2_pct=pct(top2_geo_n, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('market')
    ap.add_argument('--portafolio', type=int, required=True, help='Total de clientes de la maestra')
    ap.add_argument('--priority')
    ap.add_argument('--geo', choices=['city', 'state'], default='city', help='Unidad geográfica (provincia/ciudad)')
    a = ap.parse_args()

    data, outroot = market_dirs(a.market)
    f = Path(a.priority) if a.priority else (latest_file(data / 'priority') if resolve_dir(data / 'priority').is_dir() else None) \
        or latest_file(data / 'datamatch')
    raw = read_table(f)
    s = schema(raw)
    missing = [k for k in ('exist', 'channel', 'cat', 'city') if not s[k]]
    if missing:
        raise SystemExit(f'{f.name} no tiene las columnas Priority: {missing}.')
    raw = apply_exclusions(raw, data, s['id'])
    df = pd.DataFrame({'exist': raw[s['exist']].astype(str).str.strip().str.lower(),
                       'channel_cat': raw[s['channel']].astype(str).str.strip(),
                       'business_category': raw[s['cat']].fillna('(sin categoría)').astype(str).str.strip(),
                       'geo': raw[s[a.geo]].fillna('(sin dato)').map(norm_geo)})
    # Alias de ciudades por mercado: data/<pais>/<region>/geo_alias.json  {"Oaxaca De Juárez": "Oaxaca"}
    fa = data / 'geo_alias.json'
    if fa.exists():
        alias = {norm_geo(k): v for k, v in json.loads(fa.read_text(encoding='utf-8')).items()}
        df['geo'] = df['geo'].replace(alias)
    score = s['score']
    if s['area']:
        df['area'] = raw[s['area']].astype(str).str.strip().str.lower()

    if s['match']:
        df['match'] = normalize_match(raw[s['match']])
        total_match = int((df['match'] == 'match').sum())
    else:
        df['match'] = 'no_match'
        dm = read_table(latest_file(data / 'datamatch'))
        total_match = int((normalize_match(dm[schema(dm)['match']]) == 'match').sum())
    nm = df[df['match'] == 'no_match']
    hm = nm[nm['exist'].isin(HM)]

    # 7 — umbrales reales
    thr = {}
    if score:
        sc = pd.to_numeric(raw.loc[nm.index, score], errors='coerce')
        for e in ('low', 'moderate', 'high'):
            v = sc[nm['exist'] == e]
            if len(v):
                thr[e] = [round(float(v.min()) * 20) / 20, round(float(v.max()) * 20) / 20]  # umbrales a múltiplos de 0,05 (0,41 → 0,40)

    # 9
    s9 = dict(total_dataplor=len(nm) + total_match, total_embotellador=a.portafolio,
              high=int((nm['exist'] == 'high').sum()), moderate=int((nm['exist'] == 'moderate').sum()),
              low=int((nm['exist'] == 'low').sum()), total_no_match=len(nm), total_match=total_match)

    # 10 — geo × canal (H+M)
    geo_rank = hm['geo'].value_counts()
    top5 = geo_rank.head(5).index.tolist()
    t = hm.assign(g=hm['geo'].where(hm['geo'].isin(top5), 'Otros')).groupby(['g', 'channel_cat']).size() \
          .unstack(fill_value=0).reindex(index=top5 + ['Otros'], columns=CHANNELS, fill_value=0)
    t['Total'] = t.sum(axis=1)
    t.loc['Total'] = t.sum()
    top5_sum = int(hm['geo'].isin(top5).sum())
    s10 = dict(header=['Ciudad' if a.geo == 'city' else 'Estado'] + CHANNELS + ['Total'],
               rows=[[i] + [int(x) for x in r] for i, r in t.iterrows()],
               top5=top5, n_geo=int(hm['geo'].nunique()), top5_sum=top5_sum, top5_pct=pct(top5_sum, len(hm)),
               total_hm=len(hm))
    if 'area' in hm:
        s10['area_fuera_hm'] = int(hm['area'].eq('fuera').sum())
        s10['area_fuera_pct'] = pct(hm['area'].eq('fuera').sum(), len(hm))

    # 11 — top categorías H+M por canal
    s11 = {}
    for ch in CHANNELS:
        sub = hm[hm['channel_cat'] == ch]
        vc = sub['business_category'].value_counts().head(8)
        s11[ch] = dict(total=len(sub), bars=[[title(c), int(v)] for c, v in vc.items()],
                       top2=[title(c) for c in vc.index[:2]], top2_pct=pct(vc.head(2).sum(), len(sub)))
    s11['on_share_pct'] = pct((hm['channel_cat'] == 'On Premise').sum(), len(hm))

    # 12 / 13
    det = {}
    for ch in ('On Premise', 'Off Premise'):
        sub = hm[hm['channel_cat'] == ch]
        det[ch] = channel_detail(sub, sub['geo'].value_counts().head(2).index.tolist())

    # 14
    s14 = dict(top_geo=geo_rank.index[0] if len(geo_rank) else '', top_geo_hm=int(geo_rank.iloc[0]) if len(geo_rank) else 0,
               top_geo_pct=pct(geo_rank.iloc[0], len(hm)) if len(geo_rank) else 0)

    # 15 — etapas (plantilla / notebook)
    cat_rank = hm['business_category'].value_counts()
    scope = lambda n: hm[hm['geo'].isin(geo_rank.head(n).index) & hm['business_category'].isin(cat_rank.head(n).index)].index
    i1 = scope(3)
    i2 = scope(5).difference(i1)
    i3 = scope(8).difference(i1.union(i2))
    i4 = hm.index.difference(i1.union(i2).union(i3))
    etapas, acum = [], 0
    for k, idx in enumerate([i1, i2, i3, i4], 1):
        acum += len(idx)
        etapas.append(dict(etapa=k, pos=len(idx), pct=round(len(idx) / a.portafolio * 100, 2),
                           pct_acum=round(acum / a.portafolio * 100, 2)))
    s15 = dict(etapas=etapas, total=acum, total_pct=round(acum / a.portafolio * 100, 2),
               top_geo=geo_rank.head(8).index.tolist(), top_cats=[title(c) for c in cat_rank.head(8).index])

    out = dict(source=f.name, portafolio=a.portafolio, geo=a.geo, thresholds=thr, slide9=s9, slide10=s10,
               slide11=s11, slide12=det['On Premise'], slide13=det['Off Premise'], slide14=s14, slide15=s15)
    dest = outroot / 'deck' / 'deck_data.json'
    save_json(out, dest)

    L = '─' * 72
    print(f"{L}\nBase: {f.name} · geo={a.geo}\nDiap 7 umbrales: {thr}")
    print(f"Diap 9: Dataplor {fmt(s9['total_dataplor'])} · Embotellador {fmt(a.portafolio)} · High {fmt(s9['high'])} · "
          f"Moderate {fmt(s9['moderate'])} · Low {fmt(s9['low'])} · Total {fmt(len(nm))} · Match {fmt(total_match)}")
    print(f"Diap 10: {s10['header']}")
    for r in s10['rows']:
        print(f"         {r}")
    print(f"         top 5 = {fmt(top5_sum)} ({s10['top5_pct']}% del H+M) de {s10['n_geo']} {a.geo}")
    for ch in CHANNELS:
        print(f"Diap 11 {ch}: {s11[ch]['total']} H+M · {', '.join(s11[ch]['top2'])} = {s11[ch]['top2_pct']}%")
    for n_, ch in ((12, 'On Premise'), (13, 'Off Premise')):
        d = det[ch]
        print(f"Diap {n_} {ch}: " + ('sin puntos' if not d else
              f"top 5 = {d['top_cats_pct']}% · {', '.join(d['geo_top2'])} = {d['geo_top2_pct']}%"))
    print(f"Diap 14: {s14['top_geo']} ({fmt(s14['top_geo_hm'])} H+M, {s14['top_geo_pct']}%)")
    for e in etapas:
        print(f"Diap 15 Etapa {e['etapa']}: +{fmt(e['pos'])} POS · +{e['pct']}% · acum +{e['pct_acum']}%")
    print(f"Total +{fmt(acum)} = +{s15['total_pct']}% sobre {fmt(a.portafolio)}\n{L}\nOK → {dest}")


if __name__ == '__main__':
    main()

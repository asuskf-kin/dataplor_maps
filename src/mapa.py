"""Paso 2 — Mapa interactivo de prospección (skill prospection-map), con identidad Kin.

Uso:
    python src/mapa.py mx/Golfo [--puntos RUTA] [--clientes RUTA] [--breaks 1,3,6,10,15]
                                [--cliente-nombre "FEMSA Golfo"] [--res 8]

Por defecto toma el Priority (data/.../priority/) si existe y, si no, el datamatch. La capa de
clientes sale de data/.../clientes/. Escribe output/<pais>/<region>/mapa/prospection_map_<region>_{BOTTLER,KO}.html.
KO: nombres -> 'POI n' (mismo poi_ref que el CSV KO), clientes -> 'Cliente n', sin direcciones.
Imprime la distribución de los breaks: si no se pasan con --breaks, se calculan con percentiles.
"""
import argparse
import base64
import json
from collections import Counter
from pathlib import Path

import h3
import pandas as pd

from common import resolve_dir, BRAND, add_prioridad, apply_exclusions, find_col, latest_file, market_dirs, normalize_match, read_table, schema

EXIST_ORDER = ['high', 'moderate', 'low']
# Filtros extra (si la columna existe): categóricos como chips, numéricos como 'distancia máxima'
EXTRA_CAT = [('region', 'Región', None), ('prioridad', 'Prioridad (área · existencia)', None), ('area', 'Área', ['dentro', 'fuera']), ('pop_density', 'Densidad de población', EXIST_ORDER),
             ('car_mobility', 'Movilidad en auto', EXIST_ORDER), ('walk_mobility', 'Movilidad a pie', EXIST_ORDER)]
EXTRA_NUM = [('dist_to_main_road', 'Distancia a vía principal'), ('dist_to_bus_stop', 'Distancia a parada de bus')]
GRADE_ORDER = ['Gold', 'Silver', 'Bronze', 'Iron']


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def default_breaks(counts):
    s = sorted(counts)
    if s[-1] < 30:
        return [1, 3, 6, 10, 15]
    pct = lambda q: s[min(int(q * len(s)), len(s) - 1)]
    r5 = lambda x: max(1, round(x / 5) * 5)
    b1, b2, b3 = r5(pct(.70)), r5(pct(.85)), r5(pct(.90))
    return [b1, max(b2, b1 + 1), max(b3, b2 + 2), b3 + 10, b3 + 20]


def enc(series, order=None):
    vals = series.fillna('').astype(str).str.strip()
    uniq = sorted(vals.unique(), key=lambda v: (order.index(v.lower()) if order and v.lower() in order else 99, v))
    idx = {v: i for i, v in enumerate(uniq)}
    return [idx[v] for v in vals], uniq


def build_data(df, s, res):
    lat, lng = df[s['lat']].astype(float).round(5), df[s['lng']].astype(float).round(5)
    D = {'lats': lat.tolist(), 'lngs': lng.tolist(),
         'names': df[s['name']].fillna('').astype(str).tolist(),
         'addrs': df[s['addr']].fillna('').astype(str).tolist() if s['addr'] else []}
    flags = {}
    for key, col, order in [('cats', 'cat', None), ('cities', 'city', None), ('states', 'state', None),
                            ('chs', 'channel', None), ('exists', 'exist', EXIST_ORDER), ('grades', 'grade', None)]:
        if s[col] and df[s[col]].notna().any():
            if col == 'grade':
                order = [g.lower() for g in GRADE_ORDER]
            D[key], D['u_' + key] = enc(df[s[col]], order)
            flags[col] = True
        else:
            flags[col] = False
    if s['match']:
        m = normalize_match(df[s['match']])
        D['match'] = (m == 'match').astype(int).tolist()
        flags['match'] = True
    else:
        flags['match'] = False
    if s['excl']:
        D['excls'] = df[s['excl']].astype(str).str.strip().str.lower().eq('x').astype(int).tolist()
        flags['excl'] = True
    else:
        flags['excl'] = False
    D['xcat'], D['xnum'] = [], []
    for key, label, order in EXTRA_CAT:
        col = find_col(df, [key])
        if col and df[col].notna().any():
            codes, uniq = enc(df[col], order)
            D['xcat'].append({'key': key, 'label': label, 'codes': codes, 'uniq': uniq})
    for key, label in EXTRA_NUM:
        col = find_col(df, [key])
        if col and df[col].notna().any():
            v = pd.to_numeric(df[col], errors='coerce')
            D['xnum'].append({'key': key, 'label': label, 'vals': v.round(0).fillna(-1).astype(int).tolist(),
                              'max': int(v.max()) + 1})
    D['scores'] = df[s['score']].fillna(0).astype(float).round(3).tolist() if s['score'] else []
    cells = [h3.latlng_to_cell(a, b, res) for a, b in zip(lat, lng)]
    uniq = list(dict.fromkeys(cells))
    ci = {c: i for i, c in enumerate(uniq)}
    D['h3'] = [ci[c] for c in cells]
    # h3 v4 devuelve (lat, lng); Leaflet también espera [lat, lng]
    D['cells'] = [[[round(la, 6), round(lo, 6)] for la, lo in h3.cell_to_boundary(c)] for c in uniq]
    if flags['exist']:
        print('exists:', Counter(D['exists']), D['u_exists'])
    return D, flags, Counter(cells)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('market')
    ap.add_argument('--puntos')
    ap.add_argument('--clientes')
    ap.add_argument('--breaks')
    ap.add_argument('--cliente-nombre', default='')
    ap.add_argument('--res', type=int, default=8)
    ap.add_argument('--fit', action='store_true', help='encuadrar todos los puntos al abrir (mercados combinados)')
    ap.add_argument('--version', choices=['both', 'bottler', 'ko'], default='both',
                    help='bottler = completo; ko = nombres anonimizados (POI n / Cliente n), sin direcciones')
    a = ap.parse_args()

    data, outroot = market_dirs(a.market)
    f_pts = Path(a.puntos) if a.puntos else (latest_file(data / 'priority') if resolve_dir(data / 'priority').is_dir() else None) \
        or latest_file(data / 'datamatch')
    f_cl = Path(a.clientes) if a.clientes else latest_file(data / 'clientes')
    df = read_table(f_pts)
    s = schema(df)
    df = df.dropna(subset=[s['lat'], s['lng']]).reset_index(drop=True)
    df = apply_exclusions(df, data, s['id'])
    if s['exist']:
        df = add_prioridad(df, s)          # misma numeración poi_ref que el CSV KO
    cl = sc = None
    if f_cl:
        cl = read_table(f_cl)
        sc = schema(cl)
        cl = cl.dropna(subset=[sc['lat'], sc['lng']]).reset_index(drop=True)

    versions = ['bottler', 'ko'] if a.version == 'both' else [a.version]
    for ver in versions:
        d, sv = df, s
        if ver == 'ko':
            # KO: se sabe que el punto existe y dónde, pero no quién es
            d = df.copy()
            ref = d['poi_ref'] if 'poi_ref' in d else pd.Series(range(1, len(d) + 1))
            d[s['name']] = 'POI ' + ref.astype(str)
            sv = dict(s, addr=None)
        D, flags, cell_counts = build_data(d, sv, a.res)
        if cl is not None:
            D['cLats'] = cl[sc['lat']].astype(float).round(5).tolist()
            D['cLngs'] = cl[sc['lng']].astype(float).round(5).tolist()
            D['cNames'] = ([f'Cliente {i}' for i in range(1, len(cl) + 1)] if ver == 'ko'
                           else cl[sc['name']].fillna('').astype(str).tolist())
        flags['clients'] = cl is not None
        flags['ko'] = ver == 'ko'

        counts = list(cell_counts.values())
        breaks = [int(x) for x in a.breaks.split(',')] if a.breaks else default_breaks(counts)
        if ver == versions[0]:
            print(f'Celdas H3 res {a.res}: {len(counts)}, máximo {max(counts)} POIs por celda')
            prev = 0
            for br in breaks + [max(counts)]:
                n = sum(1 for c in counts if prev < c <= br)
                if br > prev:
                    print(f'  {prev + 1}–{br}: {n} celdas ({n / len(counts) * 100:.0f}%)')
                prev = br
            print('DEFAULT_BREAKS =', breaks)

        region = Path(*data.parts[-2:]).as_posix()
        title = f"Prospección digital — {a.cliente_nombre or region}"
        label = 'KO · nombres anonimizados' if ver == 'ko' else 'Bottler'
        subtitle = f"Versión {label} · {len(d):,} POIs".replace(',', '.')
        fonts = BRAND / 'assets' / 'fonts'
        page = (Path(__file__).with_name('mapa_template.html').read_text(encoding='utf-8')
                .replace('/*FONTS*/', f"@font-face{{font-family:'Space Grotesk';src:url('data:font/woff2;base64,{b64(fonts / 'space-grotesk.woff2')}') format('woff2');font-weight:300 700}}"
                                      f"@font-face{{font-family:'Albert Sans';src:url('data:font/woff2;base64,{b64(fonts / 'albert-sans.woff2')}') format('woff2');font-weight:100 900}}")
                .replace('/*TOKENS*/', (BRAND / 'assets/tokens/colors_and_type.css').read_text(encoding='utf-8'))
                .replace('__LOGO__', 'data:image/svg+xml;base64,' + b64(BRAND / 'assets/logos/informal/Kin_Logo_IV_19.svg'))
                .replace('__TITLE__', title).replace('__SUBTITLE__', subtitle)
                .replace('/*DATA*/', 'const D=' + json.dumps(D, ensure_ascii=False, separators=(',', ':')) + ';'
                         + 'const F=' + json.dumps(flags) + ';'
                         + f'const DEFAULT_BREAKS={json.dumps(breaks)};const MAX_VAL={max(counts)};'
                         + f'const CENTER=[{sum(D["lats"]) / len(D["lats"]):.5f},{sum(D["lngs"]) / len(D["lngs"]):.5f}];'
                         + f'const ZOOM={7 if len(d) > 10000 else (12 if len(counts) < 400 else 9)};'
                         + f'const FIT={json.dumps(a.fit)};'))
        out = outroot / 'mapa'
        out.mkdir(parents=True, exist_ok=True)
        fn = out / f"prospection_map_{data.name}_{ver.upper()}.html"
        fn.write_text(page, encoding='utf-8')
        if ver == 'ko':  # garantía: ningún nombre real en el HTML de KO
            names = list(df[s['name']].dropna().astype(str))
            if cl is not None:
                names += list(cl[sc['name']].dropna().astype(str))
            # nombres iguales a una ciudad/estado/categoría aparecen por esos filtros, no por el nombre
            shared = {str(v) for k in ('city', 'state', 'cat') if s[k] for v in df[s[k]].dropna().unique()}
            leak = [n for n in names if len(n) > 5 and n not in shared
                    and json.dumps(n, ensure_ascii=False)[1:-1] in page]
            assert not leak, f'El mapa KO contiene nombres reales: {leak[:5]}'
        print(f'{ver.upper()}: filtros {[k for k, v in flags.items() if v] + [x["key"] for x in D["xcat"] + D["xnum"]]}')
        print(f'OK → {fn} ({fn.stat().st_size / 1e6:.2f} MB)')

if __name__ == '__main__':
    main()

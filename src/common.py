"""Shared helpers for the prospection pipeline (QA -> map -> deck).

Layout convention:
    data/<pais>/<region>/clientes/*.csv|xlsx    client base (maestra)
    data/<pais>/<region>/datamatch/*.csv|xlsx   prospection output (match / no_match)
    data/<pais>/<region>/priority/*.csv|xlsx    Priority base (optional, needed for the deck)
    output/<pais>/<region>/{qa,mapa,deck}/      generated files
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / '.claude' / 'skills' / 'brand-guidelines-kin'

# Kin palette (brand-guidelines-kin tokens)
KIN = dict(yellow='#E5FF01', black='#141417', g4='#222326', g3='#999EA6',
           g2='#D4D5D6', g1='#EFEFEE', white='#FFFFFF', layout='#F2F2F2')


def market_dirs(market):
    """'mx/Golfo' -> (data dir, output dir)."""
    parts = [p for p in re.split(r'[\\/]', market) if p]
    data = ROOT / 'data' / Path(*parts)
    if not data.is_dir():
        raise SystemExit(f'No existe {data}')
    return data, ROOT / 'output' / Path(*parts)


ALIASES = {'clientes': ['clientes', 'clients', 'cliente', 'maestra'], 'datamatch': ['datamatch', 'match'],
           'priority': ['priority', 'prioridad', 'priorities']}


def resolve_dir(folder):
    """data/<mercado>/clientes también acepta Clients/, Maestra/… (sin distinguir mayúsculas)."""
    folder = Path(folder)
    if folder.is_dir() or not folder.parent.is_dir():
        return folder
    names = ALIASES.get(folder.name.lower(), [folder.name.lower()])
    for d in folder.parent.iterdir():
        if d.is_dir() and d.name.lower() in names:
            return d
    return folder


def latest_file(folder):
    folder = resolve_dir(folder)
    if not folder.is_dir():
        return None
    files = sorted([p for p in Path(folder).glob('*') if p.suffix.lower() in ('.csv', '.xlsx', '.xls')],
                   key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def read_table(path):
    path = Path(path)
    if path.suffix.lower() in ('.xlsx', '.xls'):
        return pd.read_excel(path)
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f'No pude leer {path}')


def find_col(df, candidates):
    cols = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    return None


LAT = ['dataplor_latitude', 'latitude', 'lat', 'pos_latitude', 'coord_y', 'y', 'lat_wgs84']
LNG = ['dataplor_longitude', 'longitude', 'lng', 'lon', 'pos_longitude', 'coord_x', 'x', 'lon_wgs84']
NAME = ['dataplor_name', 'name', 'nombre', 'nombrecliente', 'outlet_name', 'store_name', 'pos_name']
ID = ['dataplor_id', 'outlet_id', 'id', 'pos_id', 'code', 'codigo', 'key']
ADDR = ['dataplor_address', 'address', 'direccion', 'dirección']
CAT = ['business_category', 'category', 'categoria', 'categoría', 'business_type', 'segment', 'giro']
CITY = ['city', 'ciudad', 'municipio']
STATE = ['state', 'departamento', 'estado', 'region', 'descripción estado', 'descripcion estado']
CHANNEL = ['channel_cat', 'channel', 'canal']
EXIST = ['probability_existence_cat', 'existence_prob', 'existence']
SCORE = ['weighted_combined_score', 'total_score', 'score', 'combined_score']
GRADE = ['predicted_grade', 'grade', 'grado', 'tier']
EXCL = ['exclusión_kin', 'exclusion_kin', 'excluido', 'excluded', 'removed']
MATCH = ['match_no_match', 'match', 'status', 'verdict', 'result']
AREA = ['area', 'zona_area', 'dentro_fuera']


def schema(df):
    keys = dict(lat=LAT, lng=LNG, name=NAME, id=ID, addr=ADDR, cat=CAT, city=CITY, state=STATE,
                channel=CHANNEL, exist=EXIST, score=SCORE, grade=GRADE, excl=EXCL, match=MATCH, area=AREA)
    return {k: find_col(df, v) for k, v in keys.items()}


def normalize_match(s):
    m = s.astype(str).str.strip().str.lower()
    return m.replace({'1': 'match', 'true': 'match', 'yes': 'match', 'si': 'match',
                      '0': 'no_match', 'false': 'no_match', 'no': 'no_match', 'no match': 'no_match',
                      'nomatch': 'no_match', 'no-match': 'no_match'})


def fmt(n):
    """Spanish thousands separator: 1129 -> 1.129."""
    return f'{int(round(n)):,}'.replace(',', '.')


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def apply_exclusions(df, data_dir, id_col):
    """Quita los IDs de data/<pais>/<region>/exclusiones.csv (columna dataplor_id + motivo)."""
    f = Path(data_dir) / 'exclusiones.csv'
    if not f.exists() or not id_col:
        return df
    ids = set(read_table(f)['dataplor_id'].astype(str).str.strip())
    hit = df[id_col].astype(str).str.strip().isin(ids)
    print(f'Exclusiones ({f.name}): {hit.sum()} de {len(ids)} IDs presentes en la base, eliminados')
    return df[~hit].reset_index(drop=True)


EX_ORDER = ['high', 'moderate', 'low']
AREA_ORDER = ['dentro', 'fuera']


def add_prioridad(df, s):
    """Prioridad 1–6 = área (dentro → fuera) y luego existencia (high → moderate → low), y poi_ref 1..N
    en ese orden (desempate: score desc, dataplor_id). Es la MISMA numeración en el mapa KO y el CSV KO."""
    ex = df[s['exist']].astype(str).str.strip().str.lower()
    ar = df[s['area']].astype(str).str.strip().str.lower() if s['area'] else pd.Series('dentro', index=df.index)
    orden = {(a, e): i + 1 for i, (a, e) in enumerate((a, e) for a in AREA_ORDER for e in EX_ORDER)}
    df = df.copy()
    df['prioridad_orden'] = [orden.get((a, e), 7) for a, e in zip(ar, ex)]
    df['prioridad'] = [f'{orden.get((a, e), "-")}. {a.title()} · {e.title()}' for a, e in zip(ar, ex)]
    score = pd.to_numeric(df[s['score']], errors='coerce').fillna(0) if s['score'] else 0
    df = df.assign(_sc=score).sort_values(['prioridad_orden', '_sc', s['id']], ascending=[True, False, True])
    df['poi_ref'] = range(1, len(df) + 1)
    return df.drop(columns='_sc').reset_index(drop=True)

"""Entregables CSV para KO y para el bottler.

Uso:
    python src/entregables.py mx/Golfo [--priority RUTA] [--sufijo 202610]

Prioridad = área primero (dentro → fuera) y, dentro de cada área, la existencia (high → moderate → low).
- BOTTLER: base completa con coordenadas + prioridad + hex H3 7/8/9.
- KO: sin coordenadas, sin nombre ni datos de contacto: ID, prioridad, atributos de segmentación y hex.
Se aplican las exclusiones de data/<pais>/<region>/exclusiones.csv.
Salida: output/<pais>/<region>/entregables/Dataplor_on_premise_priority_..._{BOTTLER,KO}.csv
"""
import argparse
import re
from datetime import datetime
from pathlib import Path

import h3
import pandas as pd

from common import add_prioridad, apply_exclusions, find_col, latest_file, market_dirs, read_table, schema

KO_COLS = ['poi_ref', 'dataplor_id', 'prioridad', 'prioridad_orden', 'area', 'probability_existence_cat', 'business_category',
           'channel_cat', 'city', 'state', 'country', 'pop_density', 'car_mobility', 'walk_mobility',
           'dist_to_main_road', 'dist_to_bus_stop', 'weighted_combined_score', 'hex_7', 'hex_8', 'hex_9']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('market')
    ap.add_argument('--priority')
    ap.add_argument('--sufijo', default=datetime.now().strftime('%Y%m'))
    a = ap.parse_args()

    data, outroot = market_dirs(a.market)
    f = Path(a.priority) if a.priority else latest_file(data / 'priority')
    df = read_table(f)
    s = schema(df)
    df = apply_exclusions(df, data, s['id'])

    df = add_prioridad(df, s)
    for r in (7, 8, 9):
        df[f'hex_{r}'] = [h3.latlng_to_cell(la, lo, r) for la, lo in zip(df[s['lat']], df[s['lng']])]

    out = outroot / 'entregables'
    out.mkdir(parents=True, exist_ok=True)
    # Nombre: siempre empieza por Dataplor_on_premise_priority (se reusa el nombre de la base Priority si ya lo trae)
    stem = re.sub(r'\s*\(\d+\)$', '', f.stem)
    base = stem if stem.lower().startswith('dataplor_on_premise_priority') \
        else f"Dataplor_on_premise_priority_{data.name.lower()}_{data.parent.name.lower()}_{a.sufijo}"
    first = ['poi_ref', 'dataplor_id', 'prioridad', 'prioridad_orden']
    bottler = df[first + [c for c in df.columns if c not in first]]
    bottler.to_csv(out / f'{base}_BOTTLER.csv', index=False, encoding='utf-8-sig')
    ko = df[[c for c in KO_COLS if c in df.columns or find_col(df, [c])]]
    ko.to_csv(out / f'{base}_KO.csv', index=False, encoding='utf-8-sig')

    print(df['prioridad'].value_counts().sort_index().to_string())
    print(f'BOTTLER: {len(bottler):,} filas × {bottler.shape[1]} columnas → {out / (base + "_BOTTLER.csv")}')
    print(f'KO:      {len(ko):,} filas × {ko.shape[1]} columnas → {out / (base + "_KO.csv")}')
    leak = [c for c in ko.columns if c in (s['lat'], s['lng'], s['name'], 'website') or 'hours' in c or c.startswith('ref_')]
    assert not leak, f'KO tiene columnas sensibles: {leak}'


if __name__ == '__main__':
    main()

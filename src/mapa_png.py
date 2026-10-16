"""Imagen estática del mapa para la diapositiva 14 del deck.

Uso:
    python src/mapa_png.py mx/Golfo [--estilo kepler|kin] [--res 8] [--zoom 13]

--estilo kepler (por defecto; es el que eligió el usuario al editar el deck de Golfo, oct-2026):
    basemap claro, hexágonos H3 con TODOS los no-match en rampa amarillo → naranja → rojo → granate,
    puntos por probability_existence_cat (high azul oscuro, moderate verde claro, low turquesa),
    recuadro verde sobre la zona más densa y panel de leyenda estilo Kepler.
--estilo kin: basemap oscuro y hexágonos solo High+Moderate en Kin Yellow con opacidad creciente.

Tiles Esri Canvas (CARTO exige API key). Escribe output/<pais>/<region>/deck/mapa_hm.png.
"""
import argparse
import io
import math
import urllib.request
from collections import Counter

import h3
from PIL import Image, ImageDraw, ImageFont

from common import BRAND, KIN, apply_exclusions, latest_file, market_dirs, read_table, schema

ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/{layer}/MapServer/tile/{z}/{y}/{x}'
TILE = 256
KIN_OPACITY = [0.30, 0.45, 0.58, 0.72, 0.86, 1.0]
KEPLER_RAMP = ['#FFC300', '#F1920E', '#E3611C', '#C70039', '#900C3F', '#5A1846']
EXIST_COLORS = {'high': '#1F3A93', 'moderate': '#D7F28A', 'low': '#00A9B5'}


def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (a,)


def lonlat_px(lon, lat, z):
    n = 2 ** z * TILE
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def fetch(layer, z, x, y):
    req = urllib.request.Request(ESRI.format(layer=layer, z=z, x=x, y=y), headers={'User-Agent': 'kin-prospection/1.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return Image.open(io.BytesIO(r.read())).convert('RGBA')


def quantile_breaks(counts):
    s = sorted(counts)
    q = lambda p: s[min(int(p * len(s)), len(s) - 1)]
    b = sorted(set([max(1, q(.5)), q(.7), q(.85), q(.93), q(.98)]))
    while len(b) < 5:
        b.append(b[-1] + 1)
    return b


def labels_for(breaks, mx):
    out, prev = [], 0
    for b in breaks:
        out.append(f'{prev + 1} to {b}' if b > prev + 1 else f'{b}')
        prev = b
    out.append(f'{breaks[-1] + 1} to {mx}')
    return out


def densest_zone(cells, pct=0.8):
    """Componente conexa más grande entre las celdas del top 20 % de densidad (para el recuadro)."""
    s = sorted(cells.values())
    thr = s[min(int(pct * len(s)), len(s) - 1)]
    hot = {c for c, n in cells.items() if n >= thr}
    best, seen = set(), set()
    for c in hot:
        if c in seen:
            continue
        comp, stack = set(), [c]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.add(x)
            stack += [y for y in h3.grid_disk(x, 1) if y in hot and y not in seen]
        if sum(cells[x] for x in comp) > sum(cells[x] for x in best):
            best = comp
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('market')
    ap.add_argument('--estilo', choices=['kepler', 'kin'], default='kepler')
    ap.add_argument('--res', type=int, default=8)
    ap.add_argument('--zoom', type=int, default=13)
    a = ap.parse_args()

    data, outroot = market_dirs(a.market)
    df = read_table(latest_file(data / 'priority'))
    s = schema(df)
    df = apply_exclusions(df, data, s['id'])
    ex = df[s['exist']].astype(str).str.lower()
    pts = df if a.estilo == 'kepler' else df[ex.isin(['high', 'moderate'])]
    pex = ex.loc[pts.index]
    cells = Counter(h3.latlng_to_cell(la, lo, a.res) for la, lo in zip(pts[s['lat']], pts[s['lng']]))
    breaks = quantile_breaks(list(cells.values()))
    print('Celdas:', len(cells), 'máx', max(cells.values()), 'breaks', breaks)

    z, pad = a.zoom, 60
    xs, ys = zip(*(lonlat_px(lo, la, z) for la, lo in zip(pts[s['lat']], pts[s['lng']])))
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    if a.estilo == 'kepler':
        x1 += 300  # espacio para el panel de leyenda
    w, h = x1 - x0, y1 - y0
    if w / h < 1.6:
        d = (h * 1.6 - w) / 2; x0 -= d; x1 += d
    else:
        d = (w / 1.6 - h) / 2; y0 -= d; y1 += d
    tx0, ty0, tx1, ty1 = int(x0 // TILE), int(y0 // TILE), int(x1 // TILE), int(y1 // TILE)
    base = Image.new('RGBA', ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE))
    labels = base.copy()
    lay = ('World_Light_Gray_Base', 'World_Light_Gray_Reference') if a.estilo == 'kepler' else ('World_Dark_Gray_Base', 'World_Dark_Gray_Reference')
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            pos = ((tx - tx0) * TILE, (ty - ty0) * TILE)
            base.paste(fetch(lay[0], z, tx, ty), pos)
            labels.alpha_composite(fetch(lay[1], z, tx, ty), pos)
    ox, oy = tx0 * TILE, ty0 * TILE
    P = lambda la, lo: (lambda p: (p[0] - ox, p[1] - oy))(lonlat_px(lo, la, z))

    over = Image.new('RGBA', base.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(over)
    for c, n in cells.items():
        k = next((i for i, b in enumerate(breaks) if n <= b), 5)
        poly = [P(la, lo) for la, lo in h3.cell_to_boundary(c)]
        if a.estilo == 'kepler':
            dr.polygon(poly, fill=rgb(KEPLER_RAMP[k], 215), outline=(255, 255, 255, 200))
        else:
            dr.polygon(poly, fill=rgb(KIN['yellow'], int(255 * KIN_OPACITY[k])), outline=rgb(KIN['black'], 160))
    img = Image.alpha_composite(base, over)
    if a.estilo == 'kepler':
        img = Image.alpha_composite(img, labels)
        dp = ImageDraw.Draw(img)
        for (la, lo), e in zip(zip(pts[s['lat']], pts[s['lng']]), pex):
            x, y = P(la, lo)
            dp.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=rgb(EXIST_COLORS.get(e, '#999EA6')))
        zone = densest_zone(cells)
        zx, zy = zip(*(P(la, lo) for c in zone for la, lo in h3.cell_to_boundary(c)))
        dp.rectangle((min(zx), min(zy), max(zx), max(zy)), outline=(34, 227, 107, 255), width=5)
    else:
        img = Image.alpha_composite(img, labels)
    img = img.crop((int(x0 - ox), int(y0 - oy), int(x1 - ox), int(y1 - oy)))

    if a.estilo == 'kepler':  # panel de leyenda tipo Kepler
        fnt = lambda sz: ImageFont.truetype(str(BRAND / 'assets/fonts/albert-sans.ttf'), sz)
        W, H = img.size
        lx, ly, lw = W - 290, 40, 260
        dl = ImageDraw.Draw(img)
        dl.rectangle((lx, ly, lx + lw, ly + 400), fill=(36, 39, 48, 245))
        dl.text((lx + 14, ly + 12), 'Legend', font=fnt(18), fill=(255, 255, 255))
        dl.text((lx + 14, ly + 50), 'probability_existence_cat', font=fnt(15), fill=(220, 220, 220))
        yy = ly + 80
        for k_, col in EXIST_COLORS.items():
            dl.rectangle((lx + 14, yy, lx + 30, yy + 16), fill=rgb(col))
            dl.text((lx + 40, yy - 1), k_, font=fnt(15), fill=(200, 200, 200))
            yy += 26
        dl.text((lx + 14, yy + 14), 'Densidad · POIs por hexágono', font=fnt(15), fill=(220, 220, 220))
        yy += 44
        for col, lab in zip(KEPLER_RAMP, labels_for(breaks, max(cells.values()))):
            dl.rectangle((lx + 14, yy, lx + 30, yy + 16), fill=rgb(col))
            dl.text((lx + 40, yy - 1), lab, font=fnt(15), fill=(200, 200, 200))
            yy += 26

    if img.width < 1600:
        img = img.resize((1600, int(img.height * 1600 / img.width)), Image.LANCZOS)
    dest = outroot / 'deck' / 'mapa_hm.png'
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(dest, optimize=True)
    print('Leyenda:', labels_for(breaks, max(cells.values())))
    print(f'OK → {dest} ({img.width}×{img.height}, estilo {a.estilo})')


if __name__ == '__main__':
    main()

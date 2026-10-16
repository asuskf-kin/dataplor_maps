"""Vista previa local de las diapositivas generadas por deck_slides.py (sin login en claude.ai).

Uso:
    python src/deck_preview.py --root <root> --assets <assets.json> --local <local_assets.json> [--out preview.html]

local_assets.json mapea el mismo nombre de assets.json → ruta local del archivo. Cada <section> se
muestra a 1920×1080 (escalada) con las fuentes Kin locales. Es una aproximación del renderer de
Slides: sirve para detectar textos encimados, desbordes y huecos antes de publicar.
"""
import argparse
import json
from pathlib import Path

from common import BRAND


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--local', required=True)
    ap.add_argument('--out')
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--png', help='carpeta donde guardar un PNG por diapositiva (Chrome headless)')
    ap.add_argument('--chrome', default=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    a = ap.parse_args()
    A = json.loads(Path(a.assets).read_text(encoding='utf-8'))
    L = json.loads(Path(a.local).read_text(encoding='utf-8'))
    deck = json.loads((Path(a.root) / 'project' / 'deck.json').read_text(encoding='utf-8'))
    fonts = (BRAND / 'assets' / 'fonts').as_uri()
    parts = []
    for i, sid in enumerate(deck['order'], 1):
        h = (Path(a.root) / 'project' / 'slides' / f'{sid}.html').read_text(encoding='utf-8')
        for k, url in A.items():
            if k in L and isinstance(url, str) and url.startswith('/_blob/'):
                h = h.replace(url, Path(L[k]).resolve().as_uri())
        parts.append(f'<div class="wrap"><div class="lbl">{i:02d} · {sid}</div><div class="box">{h}</div></div>')
    s = a.scale
    page = f"""<!doctype html><meta charset="utf-8"><title>Preview</title><style>
@font-face{{font-family:'Space Grotesk';src:url('{fonts}/space-grotesk.ttf');font-weight:300 700}}
@font-face{{font-family:'Albert Sans';src:url('{fonts}/albert-sans.ttf');font-weight:100 900}}
body{{background:#555;margin:0;padding:12px;font-family:sans-serif}} *{{box-sizing:border-box;margin:0}}
.wrap{{display:inline-block;margin:6px;vertical-align:top}} .lbl{{color:#fff;font:12px sans-serif}}
.box{{width:{1920 * s}px;height:{1080 * s}px;overflow:hidden}}
section{{width:1920px;height:1080px;position:relative;overflow:hidden;transform:scale({s});transform-origin:0 0}}
aside{{display:none}} h1,h2,h3,p,ul{{margin:0}} ul{{padding-left:1.2em}} table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #D4D5D6;padding:.35em .6em}}
</style>{''.join(parts)}"""
    out = Path(a.out or Path(a.root) / 'preview.html')
    out.write_text(page, encoding='utf-8')
    print(f'OK → {out}')
    if a.png:
        # Una página por diapositiva a escala 1 y captura con Chrome headless → PNG + hoja de contacto
        import subprocess
        from PIL import Image
        pdir = Path(a.png)
        pdir.mkdir(parents=True, exist_ok=True)
        css = page[page.index('<style>'):page.index('</style>') + 8].replace(f'scale({s})', 'scale(1)')
        css = css.replace(f'width:{1920 * s}px;height:{1080 * s}px', 'width:1920px;height:1080px')
        shots = []
        for i, part in enumerate(parts, 1):
            f = pdir / f'{i:02d}.html'
            f.write_text(f'<!doctype html><meta charset="utf-8">{css.replace("padding:12px", "padding:0")}'
                         + part.replace('<div class="lbl">', '<div class="lbl" style="display:none">'), encoding='utf-8')
            png = pdir / f'{i:02d}.png'
            subprocess.run([a.chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                            '--window-size=1932,1092', f'--screenshot={png}', f.resolve().as_uri()],
                           capture_output=True, timeout=60)
            shots.append(png)
        ims = [Image.open(p).crop((6, 6, 1926, 1086)).resize((640, 360)) for p in shots if p.exists()]
        cols = 4
        sheet = Image.new('RGB', (cols * 650 + 10, ((len(ims) + cols - 1) // cols) * 370 + 10), (90, 90, 90))
        for k, im in enumerate(ims):
            sheet.paste(im, (10 + (k % cols) * 650, 10 + (k // cols) * 370))
        sheet.save(pdir / 'contact.png')
        print(f'PNG → {pdir} ({len(ims)} diapositivas) + contact.png')


if __name__ == '__main__':
    main()

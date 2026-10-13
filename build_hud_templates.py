"""
build_hud_templates.py - Genera las plantillas de digitos de la cabecera (hud_digits/)
a partir de capturas etiquetadas. Uso (desde la carpeta del repo):

    python build_hud_templates.py                 # entrena con screenshots/ y escribe hud_digits/
    python build_hud_templates.py --loo           # solo valida dejando una captura fuera cada vez
    python build_hud_templates.py --extra captura_juego.png 1 1 12   # añade una captura propia
                                                  # (nivel, recogidos, necesarios segun la cabecera)
"""
import argparse
import io
import os
import sys
import types
import contextlib

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import pyautogui  # noqa: F401
except Exception:  # entorno sin pantalla
    sys.modules["pyautogui"] = types.SimpleNamespace(sleep=lambda x: None, screenshot=None)
from diamond_rush_vision import DiamondRushVision  # noqa: E402
import hud_reader  # noqa: E402

# captura del repo -> (nivel, recogidos, necesarios) segun la cabecera del juego
LABELS = {
    1: (2, 0, 14), 2: (5, 0, 8), 3: (4, 0, 6), 4: (8, 0, 11), 5: (1, 12, 12), 6: (1, 12, 12),
    7: (15, 0, 7), 8: (15, 0, 7), 10: (15, 0, 7), 11: (13, 4, 11), 12: (9, 0, 12),
    13: (13, 4, 11), 14: (1, 0, 12), 15: (2, 0, 14), 16: (3, 0, 11), 17: (4, 0, 6), 18: (5, 0, 8),
}


def game_rect(img):
    v = DiamondRushVision()
    with contextlib.redirect_stdout(io.StringIO()):
        return v.get_game_area(img)


def collect(items):
    """items: lista de (nombre, ruta, (nivel, rec, nec)) -> {nombre: [(etiqueta, mascara)]}"""
    out, problemas = {}, []
    for name, path, (lvl, c, n) in items:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        rect = game_rect(img) if img is not None else None
        seg = hud_reader.segment(img, rect) if rect else None
        if not seg:
            problemas.append("%s: no se pudo segmentar" % name)
            continue
        lg, cg = seg
        want_l = list(str(lvl))
        want_c = list("%d/%d" % (c, n))
        if len(lg) != len(want_l) or len(cg) != len(want_c):
            problemas.append("%s: glifos %d/%d (esperados %d/%d)" % (name, len(lg), len(cg), len(want_l), len(want_c)))
            continue
        out[name] = list(zip(want_l, lg)) + list(zip(want_c, cg))
    return out, problemas


def classify_with(samples, mask):
    v = hud_reader._glyph_vec(mask)
    best, bd = None, 1e9
    for lbl, m in samples:
        d = float(np.sum((v - hud_reader._glyph_vec(m)) ** 2))
        if d < bd:
            best, bd = lbl, d
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loo", action="store_true")
    ap.add_argument("--extra", nargs=4, metavar=("PNG", "NIVEL", "RECOGIDOS", "NECESARIOS"), action="append", default=[])
    ap.add_argument("--screens", default=os.path.join(HERE, "screenshots"))
    ap.add_argument("--out", default=hud_reader.DEFAULT_DIR)
    a = ap.parse_args()

    items = [("screenshot%d" % i, os.path.join(a.screens, "screenshot%d.png" % i), lab) for i, lab in sorted(LABELS.items())]
    for png, lvl, c, n in a.extra:
        items.append((os.path.basename(png), png, (int(lvl), int(c), int(n))))
    data, problemas = collect(items)
    for p in problemas:
        print("AVISO:", p)
    print("capturas usables: %d de %d" % (len(data), len(items)))

    if a.loo:
        bien = total = 0
        fallos = []
        for name, glyphs in data.items():
            pool = [g for k, gl in data.items() if k != name for g in gl]
            for lbl, m in glyphs:
                total += 1
                pred = classify_with(pool, m)
                if pred == lbl:
                    bien += 1
                else:
                    fallos.append((name, lbl, pred))
        print("LOO: %d/%d glifos bien clasificados" % (bien, total))
        for f in fallos:
            print("  fallo:", f)
        return

    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.endswith(".png"):
            os.remove(os.path.join(a.out, f))
    n = 0
    for name, glyphs in data.items():
        for j, (lbl, m) in enumerate(glyphs):
            fname = "%s_%s_%d.png" % (hud_reader.NAME_FROM_LABEL.get(lbl, lbl), name, j)
            cv2.imwrite(os.path.join(a.out, fname), (hud_reader._glyph_vec(m) * 255).astype(np.uint8))
            n += 1
    print("escritas %d plantillas en %s" % (n, a.out))


if __name__ == "__main__":
    main()

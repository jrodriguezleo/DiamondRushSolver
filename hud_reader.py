"""
hud_reader.py - Lee la cabecera del juego ("Level N  <diamante>  c/N") sin OCR.

Segmenta los glifos blancos de la cabecera (el diamante celeste sirve de ancla
entre el numero de nivel y el contador) y clasifica cada digito por el vecino
mas cercano contra plantillas guardadas en la carpeta `hud_digits/`.
Devuelve nivel, diamantes recogidos y diamantes necesarios.

    reader = HudReader()                       # carga hud_digits/
    info = reader.read(img_bgr, game_rect)     # game_rect = (x1, y1, x2, y2) de la vision
    info -> {"level": 3, "collected": 0, "total": 11, "texto": "3 | 0/11", "ok": True}
"""
import os
import re

import cv2
import numpy as np

GLYPH_W, GLYPH_H = 20, 24
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "hud_digits")
LABEL_FROM_NAME = {"slash": "/"}
NAME_FROM_LABEL = {"/": "slash"}


def _glyph_vec(mask):
    """mask: recorte binario (0/255) de UN glifo -> vector normalizado en altura."""
    h, w = mask.shape
    nh = GLYPH_H
    nw = max(1, min(GLYPH_W, int(round(w * nh / float(h)))))
    small = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    canvas = np.zeros((GLYPH_H, GLYPH_W), np.float32)
    x0 = (GLYPH_W - nw) // 2
    canvas[:, x0:x0 + nw] = small
    return canvas


def segment(img, rect):
    """Devuelve (grupo_nivel, grupo_contador): listas de recortes binarios de glifos
    ordenados de izquierda a derecha, o None si no se encuentra la cabecera."""
    x1, y1, x2, y2 = rect
    ch = (y2 - y1) / 15.0
    ya, yb = int(y1 + 0.10 * ch), int(y1 + 1.05 * ch)
    xa, xb = int(x1 + 0.15 * (x2 - x1)), int(x1 + 0.85 * (x2 - x1))
    crop = img[ya:yb, xa:xb]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white = (((gray > 190) & (hsv[:, :, 1] < 60)).astype(np.uint8)) * 255

    # ancla: el diamante celeste
    cyan = cv2.inRange(hsv, (78, 90, 140), (105, 255, 255))
    n, lab, st, _ = cv2.connectedComponentsWithStats(cyan, 8)
    best = None
    for k in range(1, n):
        if st[k][4] > 0.05 * ch * ch and (best is None or st[k][4] > st[best][4]):
            best = k
    # glifos altos (digitos y las letras L y l; las e y v son mas bajas)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(white, 8)
    comps = []
    for k in range(1, n2):
        x, y, w, h, a = st2[k]
        if 0.32 * ch <= h <= 0.52 * ch and w <= 0.35 * ch:
            comps.append((x, y, w, h, k))
    comps.sort()
    if len(comps) < 3:
        return None
    if best is not None:
        dl, dr = st[best][0], st[best][0] + st[best][2]
    else:  # sin diamante: se parte por el hueco mas grande
        gaps = [(comps[i + 1][0] - (comps[i][0] + comps[i][2]), i) for i in range(len(comps) - 1)]
        g, i = max(gaps)
        dl, dr = comps[i][0] + comps[i][2] + 1, comps[i + 1][0] - 1
    left = [c for c in comps if c[0] + c[2] <= dl + 2]
    right = [c for c in comps if c[0] >= dr - 2]
    # numero de nivel: de derecha a izquierda mientras el hueco sea de digitos (no de palabra)
    grp, prev = [], None
    for c in reversed(left):
        if prev is not None and (prev[0] - (c[0] + c[2])) > 0.13 * ch:
            break
        if prev is None and (dl - (c[0] + c[2])) > 0.6 * ch:
            break
        grp.append(c)
        prev = c
    grp.reverse()

    def crop_of(c):
        x, y, w, h, k = c
        return (lab2[y:y + h, x:x + w] == k).astype(np.uint8) * 255

    return [crop_of(c) for c in grp], [crop_of(c) for c in right]


class HudReader:
    def __init__(self, template_dir=DEFAULT_DIR):
        self.labels, self.vecs = [], []
        if os.path.isdir(template_dir):
            for f in sorted(os.listdir(template_dir)):
                if not f.lower().endswith(".png"):
                    continue
                name = f.split("_")[0]
                lbl = LABEL_FROM_NAME.get(name, name)
                m = cv2.imread(os.path.join(template_dir, f), cv2.IMREAD_GRAYSCALE)
                if m is not None:
                    self.labels.append(lbl)
                    self.vecs.append(m.astype(np.float32) / 255.0)

    def available(self):
        return len(self.vecs) > 0

    def classify(self, mask, exclude=None):
        v = _glyph_vec(mask)
        best, bd = None, 1e9
        for lbl, t, tag in zip(self.labels, self.vecs, getattr(self, "tags", [None] * len(self.vecs))):
            d = float(np.sum((v - t) ** 2))
            if d < bd:
                best, bd = lbl, d
        return best, bd

    def read(self, img, rect):
        res = {"level": None, "collected": None, "total": None, "texto": "", "ok": False}
        if not self.available():
            return res
        seg = segment(img, rect)
        if seg is None:
            return res
        lvl_glyphs, cnt_glyphs = seg
        lvl = "".join(self.classify(g)[0] or "?" for g in lvl_glyphs)
        cnt = "".join(self.classify(g)[0] or "?" for g in cnt_glyphs)
        res["texto"] = "%s | %s" % (lvl, cnt)
        if re.fullmatch(r"\d{1,2}", lvl):
            res["level"] = int(lvl)
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", cnt)
        if m:
            res["collected"], res["total"] = int(m.group(1)), int(m.group(2))
        res["ok"] = res["level"] is not None and res["total"] is not None
        return res

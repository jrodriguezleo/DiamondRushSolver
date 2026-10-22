"""
captura.py - Captura de pantalla rapida para macOS, con respaldo en pyautogui.

pyautogui.screenshot() en macOS llama al comando `screencapture`, que escribe un PNG en disco
y lo vuelve a leer: en una pantalla Retina tarda del orden de medio segundo. Aqui se captura
directamente con Quartz (pyobjc ya esta en requirements.txt), que es mucho mas rapido.

Para no arriesgar la vision, la primera vez se capturan las dos versiones y se comparan: si
Quartz no da la misma imagen (tamano o colores distintos) se usa pyautogui para el resto de la
ejecucion. Siempre devuelve BGR en pixeles fisicos, igual que antes.

    from captura import capturar
    img = capturar()           # np.ndarray BGR (alto, ancho, 3)
"""
import sys
import time

import cv2
import numpy as np

_modo = None          # None = sin decidir, "quartz", "quartz_rgb" (canales al reves) o "pyautogui"
_aviso = None


def _pyautogui():
    import pyautogui
    return cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)


def _quartz_raw():
    """Pantalla principal en pixeles fisicos, 4 canales en el orden de memoria (normalmente BGRA)."""
    import Quartz
    rect = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    img = Quartz.CGWindowListCreateImage(rect, Quartz.kCGWindowListOptionOnScreenOnly,
                                         Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
    if img is None:
        raise RuntimeError("CGWindowListCreateImage devolvio None (permiso de Grabacion de pantalla?)")
    if Quartz.CGImageGetBitsPerPixel(img) != 32:
        raise RuntimeError("formato de imagen inesperado")
    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
    bpr = Quartz.CGImageGetBytesPerRow(img)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    arr = np.frombuffer(data, np.uint8).reshape(h, bpr // 4, 4)[:, :w, :]
    return arr


def _quartz(rgb=False):
    a = _quartz_raw()
    return np.ascontiguousarray(a[:, :, 2::-1] if rgb else a[:, :, :3])


def _diferencia(a, b):
    if a.shape != b.shape:
        return 255.0
    return float(np.mean(cv2.absdiff(a, b)))


def _decidir():
    """Compara Quartz con pyautogui una vez y fija el metodo de captura."""
    global _modo, _aviso
    if sys.platform != "darwin":
        _modo = "pyautogui"
        return _pyautogui()
    try:
        t0 = time.perf_counter()
        raw = _quartz_raw()
        t_q = time.perf_counter() - t0
        t0 = time.perf_counter()
        ref = _pyautogui()
        t_p = time.perf_counter() - t0
        bgr = np.ascontiguousarray(raw[:, :, :3])
        rgb = np.ascontiguousarray(raw[:, :, 2::-1])
        d_bgr, d_rgb = _diferencia(bgr, ref), _diferencia(rgb, ref)
        if d_bgr < 4.0:
            _modo = "quartz"
        elif d_rgb < 4.0:
            _modo = "quartz_rgb"
        else:
            _modo = "pyautogui"
            _aviso = "captura rapida descartada: no coincide con pyautogui (dif %.1f / %.1f)" % (d_bgr, d_rgb)
        if _modo != "pyautogui":
            _aviso = "captura rapida activada (Quartz %.2f s frente a pyautogui %.2f s)" % (t_q, t_p)
        return ref
    except Exception as e:
        _modo = "pyautogui"
        _aviso = "captura rapida no disponible (%s): se usa pyautogui" % e
        return _pyautogui()


def capturar():
    """Captura la pantalla principal en BGR (pixeles fisicos)."""
    global _modo, _aviso
    if _modo is None:
        img = _decidir()
        if _aviso:
            print("(%s)" % _aviso)
        return img
    if _modo == "pyautogui":
        return _pyautogui()
    try:
        return _quartz(rgb=(_modo == "quartz_rgb"))
    except Exception as e:
        _modo = "pyautogui"
        print("(fallo la captura rapida (%s): se vuelve a pyautogui)" % e)
        return _pyautogui()


def metodo():
    return _modo


_escala = None  # pixeles fisicos por punto (2.0 en Retina)


def _quartz_region(x1, y1, x2, y2, rgb=False):
    """Recorte de la pantalla principal; coordenadas en pixeles FISICOS (como las de la vision)."""
    global _escala
    import Quartz
    if _escala is None:
        b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        _escala = Quartz.CGDisplayPixelsWide(Quartz.CGMainDisplayID()) / float(b.size.width)
        if _escala <= 0:
            _escala = 1.0
        # CGDisplayPixelsWide puede dar puntos en vez de pixeles: se corrige con la captura completa
        try:
            _escala = _quartz_raw().shape[1] / float(b.size.width)
        except Exception:
            pass
    e = _escala
    rect = Quartz.CGRectMake(x1 / e, y1 / e, (x2 - x1) / e, (y2 - y1) / e)
    img = Quartz.CGWindowListCreateImage(rect, Quartz.kCGWindowListOptionOnScreenOnly,
                                         Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
    if img is None:
        raise RuntimeError("CGWindowListCreateImage devolvio None")
    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
    bpr = Quartz.CGImageGetBytesPerRow(img)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    a = np.frombuffer(data, np.uint8).reshape(h, bpr // 4, 4)[:, :w, :]
    return a[:, :, 2::-1] if rgb else a[:, :, :3]


def region_rapida():
    """True si se puede capturar solo una region con Quartz (decide el metodo si hace falta)."""
    if _modo is None:
        capturar()
    return _modo in ("quartz", "quartz_rgb")


def capturar_region(rect):
    """Captura solo rect=(x1, y1, x2, y2) en pixeles fisicos. Con Quartz es barato; sin el, recorta
    una captura completa (lento: el modo --safe lo avisa)."""
    global _modo
    x1, y1, x2, y2 = rect
    if region_rapida():
        try:
            return _quartz_region(x1, y1, x2, y2, rgb=(_modo == "quartz_rgb"))
        except Exception as e:
            _modo = "pyautogui"
            print("(fallo la captura rapida de region (%s): se vuelve a pyautogui)" % e)
    return capturar()[y1:y2, x1:x2]

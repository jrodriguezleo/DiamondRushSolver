"""
enfoque.py - Arranque sin tocar el raton: pone el juego delante y le da el foco del teclado.

1. activar_navegador(): por AppleScript busca, entre los navegadores abiertos, la pestana cuya URL
   o titulo contiene `patron` (por defecto "diamond"), la selecciona y trae su ventana al frente.
   Sirve para Chrome, Brave, Edge, Chromium, Arc y Safari. Firefox no deja leer sus pestanas:
   con --navegador Firefox solo se trae al frente. La primera vez macOS pedira permiso para que
   la terminal controle el navegador (Ajustes > Privacidad y seguridad > Automatizacion).
2. esperar_juego(): captura cada ~0,15 s hasta que la vision encuentra el area del juego y sale
   igual en dos capturas seguidas (la ventana ya termino de aparecer). Sustituye a la cuenta atras.
3. clic_foco(): un clic en la franja oscura que rodea el juego (fuera del tablero y de los botones
   de la cabecera) para que las flechas lleguen al juego; luego devuelve el raton a donde estaba.
"""
import contextlib
import io
import subprocess
import sys
import time

import numpy as np

NAVEGADORES = ["Google Chrome", "Brave Browser", "Microsoft Edge", "Chromium", "Arc", "Safari", "Firefox"]
# color de las franjas oscuras a los lados del juego (BGR), el mismo rango que usa get_game_area
BORDE_LO = np.array((24, 21, 13))
BORDE_HI = np.array((32, 27, 22))

_SCRIPT_CHROME = '''
tell application "%(app)s"
  repeat with w in windows
    set i to 0
    repeat with t in tabs of w
      set i to i + 1
      set u to ""
      set n to ""
      try
        set u to (URL of t) as text
      end try
      try
        set n to (title of t) as text
      end try
      if u contains "%(patron)s" or n contains "%(patron)s" then
        set active tab index of w to i
        set index of w to 1
        activate
        return "ok"
      end if
    end repeat
  end repeat
  return "no"
end tell
'''

_SCRIPT_SAFARI = '''
tell application "Safari"
  repeat with w in windows
    repeat with t in tabs of w
      set u to ""
      set n to ""
      try
        set u to (URL of t) as text
      end try
      try
        set n to (name of t) as text
      end try
      if u contains "%(patron)s" or n contains "%(patron)s" then
        set current tab of w to t
        set index of w to 1
        activate
        return "ok"
      end if
    end repeat
  end repeat
  return "no"
end tell
'''


def _osascript(script, timeout=6):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _apps_abiertas():
    """Nombres de las apps abiertas (AppKit, sin pedir permisos). None si no se puede saber."""
    try:
        from AppKit import NSWorkspace
        return {str(a.localizedName()) for a in NSWorkspace.sharedWorkspace().runningApplications()
                if a.localizedName()}
    except Exception:
        return None


def _abierto(app, abiertas=None):
    if abiertas is not None:
        return app in abiertas
    return _osascript('application "%s" is running' % app) == "true"


def activar_navegador(nombre=None, patron="diamond"):
    """Trae al frente la pestana del juego. Devuelve (app | None, texto explicativo)."""
    if sys.platform != "darwin":
        return None, "activar el navegador solo esta programado para macOS"
    patron = patron.replace('"', "").replace("\\", "")
    candidatos = [nombre] if nombre else NAVEGADORES
    apps = _apps_abiertas()
    abiertos = [a for a in candidatos if _abierto(a, apps)]
    if not abiertos:
        return None, ("%s no esta abierto" % nombre) if nombre else "no hay ningun navegador conocido abierto"
    for app in abiertos:
        if app == "Firefox":
            continue
        plantilla = _SCRIPT_SAFARI if app == "Safari" else _SCRIPT_CHROME
        if _osascript(plantilla % {"app": app, "patron": patron}) == "ok":
            return app, "pestana del juego encontrada en %s" % app
    # sin pestana reconocible: traer al frente el navegador indicado (o el primero abierto)
    app = abiertos[0]
    if _osascript('tell application "%s" to activate' % app) is not None:
        return app, ("no encontre una pestana con '%s': traigo %s al frente tal cual" % (patron, app))
    return None, "no se pudo activar %s (permiso de Automatizacion?)" % app


def esperar_juego(vision, timeout=10.0, intervalo=0.15):
    """Captura hasta ver el area del juego estable en dos capturas seguidas.
    Devuelve (img, rect) o (None, None) si se agota el tiempo."""
    t0 = time.time()
    previo = None
    while time.time() - t0 < timeout:
        img = vision.read_screen_realtime()
        with contextlib.redirect_stdout(io.StringIO()):
            rect = vision.get_game_area(img)
        if rect and previo == rect:
            return img, rect
        previo = rect
        time.sleep(intervalo)
    return None, None


def _franja(img, x, y, paso):
    """Recorre desde x en la direccion `paso` mientras el pixel tenga el color del borde.
    Devuelve el x central de la franja y su ancho."""
    h, w = img.shape[:2]
    inicio = x
    while 0 <= x < w and np.all(img[y, x] >= BORDE_LO) and np.all(img[y, x] <= BORDE_HI):
        x += paso
    ancho = abs(x - inicio)
    return inicio + paso * (ancho // 2), ancho


def punto_foco(img, rect, modo="borde"):
    """Punto (en pixeles fisicos de la captura) donde hacer clic para dar foco al juego."""
    x1, y1, x2, y2 = rect
    ym = (y1 + y2) // 2
    if modo == "borde":
        for x, paso in ((x1 - 1, -1), (x2, 1)):
            xc, ancho = _franja(img, x, ym, paso)
            if ancho >= 6:
                return xc, ym
    # tablero: centro de la ultima fila (casi siempre pared)
    return (x1 + x2) // 2, int(y1 + (y2 - y1) * 14.5 / 15)


def clic_foco(img, rect, modo="borde"):
    """Hace clic en el juego y devuelve el raton a su sitio. Devuelve el punto en coordenadas de pantalla."""
    import pyautogui
    px, py = punto_foco(img, rect, modo)
    escala = img.shape[1] / float(pyautogui.size()[0])  # Retina: la captura va en pixeles fisicos
    sx, sy = px / escala, py / escala
    antes = pyautogui.position()
    pyautogui.click(sx, sy)
    if antes[0] > 5 and antes[1] > 5:  # no devolver el raton a la esquina (activaria el FAILSAFE)
        pyautogui.moveTo(antes[0], antes[1])
    time.sleep(0.1)
    return sx, sy


def preparar(vision, navegador=None, patron="diamond", clic="borde", hacer_clic=True, timeout=10.0):
    """Activa el navegador, espera el juego y le da el foco. Devuelve (img, rect) de la ultima
    captura (para reutilizarla) o (None, None) si no aparece el juego."""
    t0 = time.perf_counter()
    app, texto = activar_navegador(navegador, patron)
    print("Navegador: %s" % texto, flush=True)
    img, rect = esperar_juego(vision, timeout)
    if img is None:
        print("No veo el juego en pantalla tras %.0f s. Comprueba que este visible y entero." % timeout)
        return None, None
    if hacer_clic and clic != "no":
        sx, sy = clic_foco(img, rect, clic)
        print("Clic de foco en (%d, %d)." % (sx, sy))
    print("Juego listo en %.2f s." % (time.perf_counter() - t0), flush=True)
    return img, rect

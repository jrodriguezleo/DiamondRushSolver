"""
bot_solver.py - Puente entre la vision del bot y el solucionador optimo.

  grid (15x10 de Cell|None, de DiamondRushVision)  ->  layout de texto 13x10
  layout -> movimientos U/D/L/R optimos  ->  teclas 'up'/'down'/'left'/'right'

La cabecera del juego (contador, botones) ocupa las 2 primeras filas de la
cuadricula del bot; el tablero real son las filas 2..14 (13 filas x 10 columnas).
"""
from diamond_solver import Level, simulate

try:  # cache con soluciones ya calculadas (el nivel 11 tarda mucho en resolverse)
    from known_levels import KNOWN
except ImportError:  # pragma: no cover
    KNOWN = {}

FIRST_BOARD_ROW = 2

# tipo de celda de la vision -> simbolo del layout
SYMBOL = {
    "terrain": ".",
    "player": "P",
    "player-with-key": "P",
    "diamond": "D",
    "ladder": "E",
    "totem": "E",           # totem dorado (nivel 20): tambien es la salida
    "ladder-open": "E",
    "rock": "R",
    "fall": "O",            # hoyo
    "rock-in-fall": ".",    # hoyo ya rellenado: se camina encima
    "key": "K",
    "door": "G",            # puerta verde
    "metal-door": "|",      # valla de metal
    "push_button": "_",     # placa de presion
    "push-button": "_",
    # Pinchos: no existen en los niveles 1-19 y la vision los detecta mal (falsos
    # positivos sobre suelo normal), por eso se tratan como suelo salvo que se pida
    # lo contrario con grid_to_layout(..., spikes="wall").
    "spike": ".",
    "spike-up": ".",
}


def grid_to_layout(grid, first_row=FIRST_BOARD_ROW, spikes="once"):
    """Devuelve (layout, hand0, avisos). `hand0`=1 si el jugador ya lleva llave.
    spikes: "once" (por defecto: se pisa una vez y luego es pared), "floor" o "wall"."""
    rows, warns, hand0 = [], [], 0
    n_spikes = unknown = 0
    donde = []
    for r in range(first_row, len(grid)):
        line = []
        for cell in grid[r]:
            if cell is None:
                line.append("#")
                continue
            t = cell.cell_type
            if t in ("spike", "spike-up"):
                n_spikes += 1
                donde.append("(fila %d, col %d)" % (r - first_row, len(line)))
            if t == "player-with-key":
                hand0 = 1
            if t in ("spike", "spike-up"):
                sym = {"floor": ".", "wall": "#", "once": "^"}[spikes]
            else:
                sym = SYMBOL.get(t)
            if sym is None:
                unknown += 1
                sym = "#"
            line.append(sym)
        rows.append("".join(line))
    if n_spikes:
        warns.append("%d casilla(s) de pinchos %s: %s" % (
            n_spikes,
            {"once": "(se pisan una sola vez, luego son pared)", "floor": "tratadas como suelo",
             "wall": "tratadas como pared"}[spikes], " ".join(donde)))
    if unknown:
        warns.append("%d casilla(s) de tipo desconocido tratadas como pared" % unknown)
    layout = "\n".join(rows)
    if layout.count("P") != 1:
        warns.append("se esperaba 1 jugador y hay %d" % layout.count("P"))
    if layout.count("E") != 1:
        warns.append("se esperaba 1 salida y hay %d" % layout.count("E"))
    return layout, hand0, warns


def _norm(layout):
    """Normaliza el layout y se queda con las 13 filas del tablero (algunos
    niveles transcritos traen una fila extra de pared al final)."""
    lines = [l.rstrip().replace("S", ".").replace("^", ".") for l in layout.strip("\n").split("\n")]
    return "\n".join(lines[:13])  # S (marca de inicio) y ^ (pincho, anotado o no) cuentan como suelo al comparar


def find_known(layout):
    """Si el layout coincide con un nivel conocido devuelve (nivel, entrada)."""
    key = _norm(layout)
    for n, k in KNOWN.items():
        if _norm(k["grid"]) == key:
            return n, k
    return None, None


def solve_layout_text(layout, needed=None, hand0=0, use_cache=True, links=None, rock_over_fence=True, rock_on_spike=True, **kw):
    """-> (movimientos, origen). origen: 'cache nivel N' o 'A*'."""
    if use_cache and not hand0:
        n, k = find_known(layout)
        if k is not None and needed in (None, k["needed"]):
            # se valida sobre el layout DETECTADO (con sus pinchos reales), no sobre el guardado
            ok, _, _ = simulate(layout, k["solution"], k["needed"], True, 0, links or k.get("links"), rock_over_fence or k.get("rock_over_fence", True), rock_on_spike)
            if ok:
                return k["solution"], "cache (nivel %d)" % n
    moves = Level(layout, needed, True, hand0, links, rock_over_fence, rock_on_spike).solve(**kw)
    return moves, "A*"


KEYS = {"U": "up", "D": "down", "L": "left", "R": "right"}


def moves_to_keys(moves):
    return [KEYS[m] for m in moves]

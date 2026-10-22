"""
nivel.py - Identifica en que nivel esta el juego.

Dos fuentes que se combinan:
  1. La cabecera ("Level N  c/N") leida con hud_reader: es la fuente principal; da el
     numero de nivel del juego, los diamantes recogidos y los necesarios.
  2. El parecido del mapa detectado con los niveles conocidos (known_levels.py),
     tolerando lo que cambia al jugar (diamantes recogidos, llave cogida, puerta
     abierta, hoyo relleno, jugador y rocas movidos). Sirve de respaldo y de
     confirmacion cruzada.

    info = identificar(layout, hud)      # hud = dict de HudReader.read (o None)
"""
try:
    from known_levels import KNOWN
except ImportError:  # pragma: no cover
    KNOWN = {}

N_FILAS = 13


def _filas(texto):
    return [l.rstrip() for l in texto.strip("\n").split("\n")][:N_FILAS]


def distancia(layout, grid):
    """Numero (ponderado) de casillas que no se explican por jugar el nivel."""
    return _dist_filas(_filas(layout), _filas(grid))


def _dist_filas(a, b):
    if len(a) != len(b):
        return 10 ** 6
    score = 0.0
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return 10 ** 6
        for x, k in zip(ra, rb):          # x = detectado ahora, k = nivel conocido
            if x == k:
                continue
            if {x, k} <= set(".^"):         # pincho anotado en un lado y no en el otro
                continue
            if k == "^" and x in "#P":     # pincho ya pisado (levantado) o jugador encima
                continue
            if k in "DKGO" and x in ".P":  # recogido / abierta / hoyo relleno (o el jugador encima)
                continue
            if k == "P" and x in ".DK_":   # el jugador ya no esta en la casilla inicial
                continue
            if x == "P" and k in ".DK_":   # el jugador esta ahora aqui
                continue
            if {x, k} == {"R", "."}:       # una roca se movio (2 casillas implicadas)
                score += 0.5
                continue
            score += 1
    return score


def por_mapa(layout, umbral=8.0, margen=2.0):
    """-> (nivel, distancia) del nivel conocido mas parecido, o (None, mejor) si no es fiable."""
    ranking = sorted((distancia(layout, k["grid"]), n) for n, k in KNOWN.items())
    if not ranking:
        return None, None
    d1, n1 = ranking[0]
    d2 = ranking[1][0] if len(ranking) > 1 else 10 ** 6
    if d1 <= umbral and (d2 - d1) >= margen:
        return n1, d1
    return None, d1


def identificar(layout, hud=None, n_diamantes_visibles=None):
    """Combina cabecera y mapa. Devuelve un dict:
       nivel, fuente ('cabecera' | 'mapa' | None), recogidos, total, faltan (diamantes que
       aun hacen falta para abrir la salida o None), mapa_nivel, mapa_distancia, avisos."""
    avisos = []
    info = {"nivel": None, "fuente": None, "recogidos": None, "total": None, "faltan": None,
            "mapa_nivel": None, "mapa_distancia": None, "avisos": avisos}
    mapa_n, mapa_d = por_mapa(layout)
    info["mapa_nivel"], info["mapa_distancia"] = mapa_n, mapa_d

    if hud and hud.get("ok"):
        info["nivel"], info["fuente"] = hud["level"], "cabecera"
        c, t = hud.get("collected"), hud.get("total")
        if c is not None and t is not None and 0 <= c <= t <= 30:
            info["recogidos"], info["total"] = c, t
            faltan = t - c
            if n_diamantes_visibles is not None and faltan > n_diamantes_visibles:
                avisos.append("la cabecera pide %d diamantes pero solo se ven %d: se ignora el contador"
                              % (faltan, n_diamantes_visibles))
            else:
                info["faltan"] = faltan
        else:
            avisos.append("contador de la cabecera incoherente (%s/%s): se ignora" % (c, t))
        if mapa_n is not None and mapa_n != hud["level"]:
            avisos.append("la cabecera dice nivel %d pero el mapa se parece al nivel %d (distancia %.1f)"
                          % (hud["level"], mapa_n, mapa_d))
    elif mapa_n is not None:
        info["nivel"], info["fuente"] = mapa_n, "mapa"
        avisos.append("no se pudo leer la cabecera: nivel deducido del parecido del mapa")
    else:
        avisos.append("no se pudo identificar el nivel (ni cabecera ni mapa conocido)")
    return info


def layout_guardado(nivel):
    """Mapa guardado del nivel (13 filas) o None."""
    k = KNOWN.get(nivel)
    return None if k is None else "\n".join(_filas(k["grid"]))


def pos_jugador(layout):
    """(fila, columna) del jugador 'P' o None."""
    for r, fila in enumerate(_filas(layout)):
        c = fila.find("P")
        if c >= 0:
            return (r, c)
    return None


def desfase(layout, grid):
    """Alinea el mapa detectado con uno guardado: a veces el detectado empieza una o dos filas mas
    abajo (la fila superior del nivel queda bajo la cabecera). Devuelve (desfase, distancia)."""
    a = _filas(layout)
    todas = [l.rstrip() for l in grid.strip("\n").split("\n")]
    mejor = (None, 10 ** 6)
    for d in (0, 1, 2):
        b = todas[d:d + N_FILAS]
        b += ["#" * len(a[0])] * (N_FILAS - len(b))
        sc = _dist_filas(a, b)
        if sc < mejor[1]:
            mejor = (d, sc)
    return mejor


def pos_jugador(layout):
    """(fila, col) de la 'P' del layout, o None."""
    for r, f in enumerate(layout.strip("\n").split("\n")):
        if "P" in f:
            return r, f.index("P")
    return None


def corregir_casillas(layout, nivel):
    """Para niveles con `casillas_guardadas` en KNOWN: copia del mapa guardado SOLO esas casillas
    (las que la vision lee mal) y deja el resto como se ve en pantalla (jugador, rocas...).
    Devuelve (layout, lista de cambios (fila, col, visto, guardado))."""
    k = KNOWN.get(nivel) or {}
    fijas = k.get("casillas_guardadas")
    if not fijas:
        return layout, []
    filas = [list(f) for f in layout.strip("\n").split("\n")]
    guard = k["grid"].strip("\n").split("\n")
    cambios = []
    for r, c in fijas:
        if r < len(filas) and c < len(filas[r]) and filas[r][c] != guard[r][c]:
            cambios.append((r, c, filas[r][c], guard[r][c]))
            filas[r][c] = guard[r][c]
    return "\n".join("".join(f) for f in filas), cambios


def completar_con_guardado(layout, info, hud, umbral=10.0):
    """Si la cabecera dice que no se ha recogido ningun diamante pero el mapa detectado tiene menos
    de los necesarios (parte del tablero tapada por la cabecera o por el cuadro WALKTHROUGH) y se
    parece al nivel conocido (tras alinear filas), devuelve (layout_guardado, needed) de ese nivel.
    En cualquier otro caso devuelve (None, None)."""
    n = info.get("nivel")
    if not (hud and hud.get("ok") and n in KNOWN and hud.get("collected") == 0):
        return None, None
    if hud["total"] <= layout.count("D"):
        return None, None  # el mapa detectado esta completo: no hace falta
    k = KNOWN[n]
    guardado = k["grid"].strip("\n")
    if guardado.count("D") < hud["total"]:
        return None, None
    d, sc = desfase(layout, guardado)
    if d is None or sc > umbral:
        return None, None
    return guardado, k["needed"]


def links_para(layout, nivel):
    """Emparejamiento placa->valla del nivel conocido, llevado a las coordenadas del layout
    detectado (por el desfase de filas). Devuelve (links | None, avisos)."""
    k = KNOWN.get(nivel)
    if not k or not k.get("links"):
        return None, []
    d, sc = desfase(layout, k["grid"])
    if d is None or sc > 12:
        return None, ["el mapa no encaja con el nivel %s guardado: no se aplica el emparejamiento placa-valla" % nivel]
    out = {}
    for (pr, pc), (fr, fc) in k["links"].items():
        out[(pr - d, pc)] = (fr - d, fc)
    return out, []

"""
main.py - Bot de Diamond Rush con solucionador optimo (A*).

Flujo: captura la pantalla -> la vision detecta la cuadricula -> se identifica el nivel
(cabecera "Level N" + parecido con los niveles conocidos) -> A* calcula la ruta con el
MENOR numero de pasos -> se envian las flechas al juego -> al final pregunta si salio
bien y lo guarda en historial_intentos.jsonl.

Uso (desde la carpeta del repo, con el venv activo):
    python main.py --dry          # solo calcula y muestra la solucion, no pulsa teclas
    python main.py                # juega un nivel y pregunta el resultado
    python main.py --loop         # encadena niveles sin pedir nada por la terminal (ver abajo)
    python main.py --historial    # muestra el resumen de intentos guardados

Opciones utiles:
    --needed N       diamantes que FALTAN por recoger para abrir la salida (por defecto se
                     lee de la cabecera; si no se puede, todos los visibles).
    --delay S        segundos por paso (por defecto 0.25). Subelo si el juego pierde pasos.
    --countdown S    segundos para cambiar al navegador antes de capturar (por defecto 3).
    --spikes MODO    pinchos: once (por defecto: se pisan UNA vez y luego son pared), floor o wall.
    --level N        NO usa la vision: juega la solucion optima guardada del nivel N, con el
                     numero que muestra el juego en la cabecera. El nivel debe estar recien
                     empezado.
    --candidata      con --level: probar la ruta candidata del A* (mas corta, sin verificar).
    --loop           NO pregunta nada: tras cada nivel mira la cabecera; si cambia de nivel lo da por
                     bueno (guarda 'ok' en el historial) y sigue; si sigue igual, lo guarda como
                     'fallo' y se detiene. --max-niveles N, --timeout-siguiente S, --wait S.
    --verificar RUTA con --level N: simula una ruta escrita a mano (U/D/L/R) y la juega pulsando las teclas (--dry: solo simula);
                     dice si gana o en que paso falla. --traza muestra todos los pasos.
    --no-historial   no preguntar ni guardar el resultado.
Para cortar: Ctrl+C, o lleva el raton a la esquina superior izquierda.
"""
import argparse
import time

import pyautogui

from diamond_rush_vision import DiamondRushVision
from bot_solver import grid_to_layout, solve_layout_text, moves_to_keys
from known_levels import KNOWN
import historial
import nivel as nivel_mod
from hud_reader import HudReader

DELAY_DEFECTO = 0.25
LEYENDA = ("# pared  . suelo  P jugador  D diamante  E salida  R roca  "
           "O hoyo  K llave  G puerta  _ placa  | valla")


def cuenta_atras(segundos, texto):
    for s in range(int(segundos), 0, -1):
        print("%s %d..." % (texto, s), flush=True)
        time.sleep(1)


def eventos(layout, moves):
    """{n_paso: texto} con lo que pasa al pisar diamantes, llaves, puertas y la salida
    (siguiendo la ruta sobre el layout; solo informativo)."""
    g = [list(r) for r in layout.strip("\n").split("\n")]
    pos = next(((r, f.index("P")) for r, f in enumerate(g) if "P" in f), None)
    if pos is None:
        return {}
    d = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
    out, dia = {}, 0
    r, c = pos
    out["pos0"] = pos
    g[r][c] = "."
    for i, m in enumerate(moves, 1):
        r, c = r + d[m][0], c + d[m][1]
        out[("pos", i)] = (r, c)
        if not (0 <= r < len(g) and 0 <= c < len(g[r])):
            break
        x = g[r][c]
        if x == "D":
            dia += 1
            out[i] = "diamante %d" % dia
        elif x == "K":
            out[i] = "LLAVE"
        elif x == "G":
            out[i] = "PUERTA (debe abrirse)"
        elif x == "E":
            out[i] = "SALIDA"
        if x in "DKG":
            g[r][c] = "."
    return out


def jugar(keys, delay, moves=None, layout=None, verbose=False):
    """Envia las flechas una a una. Cada paso dura `delay` segundos en total.
    Con verbose imprime 'paso i/N' y marca diamantes, llaves, puertas y salida."""
    pyautogui.PAUSE = 0
    hold = min(0.06, delay / 2.0)
    ev = eventos(layout, moves) if (verbose and layout and moves) else {}
    t0 = None
    for i, k in enumerate(keys, 1):
        if verbose:
            extra = ev.get(i)
            fc = ev.get(("pos", i))
            print("paso %d/%d  %-5s -> (fila %d, col %d)%s" % (
                i, len(keys), k, fc[0], fc[1], ("  <- " + extra) if extra else "") if fc else
                "paso %d/%d  %s" % (i, len(keys), k), flush=True)
        if t0 is None:
            t0 = time.perf_counter()  # el cronometro arranca con el primer movimiento
        pyautogui.keyDown(k)
        time.sleep(hold)
        pyautogui.keyUp(k)
        if i < len(keys):
            time.sleep(max(0.0, delay - hold))
    # termina al soltar la ultima tecla (la que entra por la salida)
    return (time.perf_counter() - t0) if t0 is not None else 0.0


def texto_tiempo(segundos, n_pasos):
    m, sec = divmod(segundos, 60)
    t = ("%d min %05.2f s" % (m, sec)) if m else ("%.2f s" % sec)
    return "Tiempo del nivel: %s (%d pasos, %.2f s por paso)" % (t, n_pasos, segundos / max(1, n_pasos))


def mostrar_pasos(args):
    return True  # siempre listar los pasos (casilla y eventos) mientras se juega


def registrar(args, datos, n_pasos):
    """Pregunta si la ejecucion fue correcta y la guarda en el historial."""
    if args.dry or args.no_historial:
        return
    if args.loop:  # sin preguntas: el bucle verifica solo si el juego paso de nivel
        args._pendiente = datos
        return
    if datos.get("nivel") is None:
        datos["nivel"] = historial.preguntar_nivel()
        if datos["nivel"] is not None:
            datos["nivel_fuente"] = "manual"
    seg = datos.get("segundos")
    datos["segundos_por_paso"] = round(seg / max(1, n_pasos), 3) if seg else None
    datos["config"] = {"delay": args.delay, "tecla_pulsada_s": min(0.06, args.delay / 2.0),
                       "spikes": args.spikes, "needed_forzado": args.needed,
                       "max_seconds": args.max_seconds, "candidata": bool(getattr(args, "candidata", False))}
    resp = historial.preguntar_resultado(n_pasos)
    if resp is None:
        print("Intento no guardado.")
        return
    reg = historial.guardar(dict(datos, **resp))
    print("Guardado en %s (nivel %s: %s)." % (historial.ARCHIVO, reg.get("nivel"), reg["resultado"]))


def verificar_ruta(args):
    """--level N --verificar RUTA: simula una lista de pasos sobre el mapa guardado del nivel N.
    No pulsa teclas ni captura la pantalla."""
    from diamond_solver import simulate
    if not args.level:
        print("Indica el nivel con --level N (el mapa guardado sobre el que se comprueba la ruta).")
        return False
    k = KNOWN.get(args.level)
    if not k:
        print("No hay mapa guardado del nivel %d (hay 1-19)." % args.level)
        return False
    texto = args.verificar
    raros = sorted({c for c in texto.upper() if c not in "UDLR" and not c.isspace() and c not in ",;.-_'\"[]()"})
    if raros:
        print("AVISO: se ignoran caracteres que no son U/D/L/R: %s" % " ".join(raros))
    ruta = "".join(c for c in texto.upper() if c in "UDLR")
    if not ruta:
        print("La ruta esta vacia: escribe pasos con U (arriba), D (abajo), L (izquierda), R (derecha).")
        return False
    grid = k["grid"].strip("\n")
    links = k.get("links")
    rof = bool(k.get("rock_over_fence", True))
    ros_k = bool(k.get("rock_on_spike", True))
    ok, msg, i = simulate(grid, ruta, k["needed"], True, 0, links, rof, ros_k)
    print("Nivel %d: mapa guardado, %d diamantes necesarios, %d pasos en tu ruta." % (args.level, k["needed"], len(ruta)))
    print(grid)
    if args.traza or not ok:
        ev = eventos(grid, ruta)
        lo, hi = (1, len(ruta)) if args.traza else (max(1, i - 4), min(len(ruta), i + 2))
        print("\nPasos %d-%d:" % (lo, hi))
        for n in range(lo, hi + 1):
            fc = ev.get(("pos", n))
            print("  paso %2d  %s -> %s%s%s" % (n, ruta[n - 1], ("(fila %d, col %d)" % fc) if fc else "?",
                                              ("  <- " + ev[n]) if ev.get(n) else "",
                                              "   <== AQUI FALLA" if (not ok and n == i + 1) else ""))
    print()
    if ok:
        print("CORRECTA: gana en %d pasos (la solucion guardada tiene %d)." % (msg and i, len(k["solution"])))
    else:
        print("INCORRECTA en el paso %d (%s): %s" % (i + 1, ruta[i] if i < len(ruta) else "-", msg))
    # que hipotesis de reglas necesita la ruta
    var = []
    for vr in ((False, False), (False, True), (True, False), (True, True)):
        r = simulate(grid, ruta, k["needed"], True, 0, links, vr[0], vr[1])
        var.append((vr, r[0]))
    if any(o for _, o in var) and not all(o for _, o in var):
        print("Segun las reglas supuestas:")
        for (a, b), o in var:
            print("  roca sobre valla abierta=%-5s roca sobre pincho (lo desactiva)=%-5s -> %s" % (a, b, "gana" if o else "falla"))
    if args.dry:
        print("\n(--dry: solo simulacion, no se pulsa ninguna tecla)")
        return ok
    if not ok:
        print("\nLa simulacion no la da por buena, pero se prueba igual en el juego (el modelo puede estar mal).")
    if args.countdown:
        cuenta_atras(args.countdown, "Cambia al navegador (nivel %d recien empezado). Empiezo a pulsar en" % args.level)
    segundos = jugar(moves_to_keys(ruta), args.delay, ruta, k["grid"], mostrar_pasos(args))
    print("Listo.")
    print(texto_tiempo(segundos, len(ruta)))
    registrar(args, dict(nivel=args.level, nivel_fuente="manual", recogidos_antes=0,
                         total_diamantes=k["needed"], layout=k["grid"].strip("\n").split("\n"),
                         pasos=len(ruta), segundos=round(segundos, 2), movimientos=ruta, origen="manual",
                         delay=args.delay, spikes=args.spikes, avisos=[]), len(ruta))
    return ok


def nivel_conocido(args):
    k = KNOWN.get(args.level)
    if not k:
        print("No hay solucion guardada para el nivel %d (hay %s)." % (args.level, "1-19"))
        return False
    moves = k["solution"]
    if args.candidata and k.get("solution_a_star"):
        moves = k["solution_a_star"]
        print("(usando la ruta CANDIDATA del A*, aun sin probar en el juego)")
    print("Nivel %d (solucion guardada): %d pasos" % (args.level, len(moves)))
    print(moves)
    if args.dry:
        print("(--dry: no se pulsa ninguna tecla)")
        return True
    if args.countdown:
        cuenta_atras(args.countdown, "Cambia al navegador (nivel recien empezado). Empiezo en")
    segundos = jugar(moves_to_keys(moves), args.delay, moves, k["grid"], mostrar_pasos(args))
    print("Listo.")
    print(texto_tiempo(segundos, len(moves)))
    registrar(args, dict(nivel=args.level, nivel_fuente="manual", recogidos_antes=0,
                         total_diamantes=k["needed"], layout=k["grid"].strip("\n").split("\n"),
                         pasos=len(moves), segundos=round(segundos, 2), movimientos=moves, origen="candidata" if args.candidata else "guardada",
                         delay=args.delay, spikes=args.spikes, avisos=[]), len(moves))
    return True


def leer_cabecera(vision):
    """Lee 'Level N  c/N' de la pantalla. Devuelve el dict de HudReader o None."""
    try:
        lector = HudReader()
        if not lector.available():
            print("(sin plantillas hud_digits/: no se lee la cabecera; ver CLAUDE.md)")
            return None
        img = vision.read_screen_realtime()
        return lector.read(img, vision.game_rectangle)
    except Exception as e:  # la cabecera es un extra: nunca debe tumbar el bot
        print("(no se pudo leer la cabecera: %s)" % e)
        return None


def guardar_intento_auto(args, datos, resultado, nota):
    """Guarda en el historial un intento verificado por el propio bot (sin preguntar)."""
    if not datos or args.no_historial:
        return
    n = len(datos.get("movimientos") or "")
    seg = datos.get("segundos")
    datos["segundos_por_paso"] = round(seg / max(1, n), 3) if seg else None
    datos["config"] = {"delay": args.delay, "tecla_pulsada_s": min(0.06, args.delay / 2.0),
                       "spikes": args.spikes, "needed_forzado": args.needed,
                       "max_seconds": args.max_seconds, "candidata": False}
    datos.update(resultado=resultado, paso_fallo=None, nota=nota, verificacion="automatica")
    historial.guardar(datos)
    print("Guardado en el historial (nivel %s: %s, verificacion automatica)." % (datos.get("nivel"), resultado))


def nivel_en_pantalla():
    """Nivel que muestra la cabecera ahora mismo, o None si no se puede leer."""
    import contextlib
    import io
    try:
        v = DiamondRushVision()
        img = v.read_screen_realtime()
        with contextlib.redirect_stdout(io.StringIO()):
            rect = v.get_game_area(img)
        if not rect:
            return None
        hud = HudReader().read(img, rect)
        return hud["level"] if hud.get("ok") else None
    except Exception:
        return None


def esperar_cambio_de_nivel(nivel, timeout):
    """Mira la cabecera cada segundo hasta que cambie el numero de nivel.
    Devuelve (nuevo_nivel, 'cambio') | (nivel, 'igual') | (None, 'ilegible')."""
    t0 = time.time()
    visto = None
    while time.time() - t0 < timeout:
        n = nivel_en_pantalla()
        if n is not None:
            visto = n
            if n != nivel:
                return n, "cambio"
        time.sleep(1)
    return (visto, "igual") if visto is not None else (None, "ilegible")


def un_nivel(args):
    if args.level:
        return nivel_conocido(args)
    if args.countdown:
        cuenta_atras(args.countdown, "Cambia al navegador con el juego completo visible. Capturo en")
    vision = DiamondRushVision()
    grid = vision.realtime_mode(show_image=False)
    hud = leer_cabecera(vision)

    layout, hand0, avisos = grid_to_layout(grid, spikes=args.spikes)
    info = nivel_mod.identificar(layout, hud, layout.count("D"))
    avisos = list(avisos) + list(info["avisos"])

    # La cabecera puede tapar la fila superior: si faltan diamantes, usar el mapa guardado.
    guardado, needed_guardado = nivel_mod.completar_con_guardado(layout, info, hud)
    origen_mapa = "detectado"
    if guardado is not None:
        avisos.append("el mapa detectado esta incompleto (la cabecera tapa parte del tablero): "
                      "se usa el mapa guardado del nivel %d" % info["nivel"])
        layout, origen_mapa = guardado, "guardado"
        needed = args.needed if args.needed is not None else needed_guardado
    else:
        # La cabecera manda: faltan = total - recogidos (puede ser menos que los diamantes visibles,
        # p. ej. nivel 6: hay 10 y la salida se abre con 8). --needed lo fuerza.
        needed = args.needed if args.needed is not None else info["faltan"]

    # Niveles donde la vision falla en casillas concretas (nivel 20: hoyos vistos como suelo/pincho): si el mapa
    # detectado encaja con el guardado, se usa el guardado (marcado con usar_guardado en known_levels.py).
    kg = KNOWN.get(info["nivel"]) if info["nivel"] is not None else None
    if origen_mapa == "detectado" and kg and kg.get("usar_guardado"):
        d, sc = nivel_mod.desfase(layout, kg["grid"])
        if d == 0 and sc <= 8:
            avisos.append("se usa el mapa guardado del nivel %d (la vision no lee bien algunas casillas de este nivel)" % info["nivel"])
            layout, origen_mapa = kg["grid"].strip("\n"), "guardado"
            needed = args.needed if args.needed is not None else kg["needed"]
    # Niveles de totem (sin diamantes): la cabecera puede marcar 0/14 pero no hay nada que recoger.
    if layout.count("D") == 0 and needed and args.needed is None:
        avisos.append("no hay diamantes en el mapa: el objetivo es solo llegar a la salida/totem (needed=0)")
        needed = 0

    links = None
    if "|" in layout:
        if origen_mapa == "guardado":
            links = KNOWN[info["nivel"]].get("links")
        else:
            links, av = nivel_mod.links_para(layout, info["nivel"])
            avisos += av
        if not links:
            avisos.append("hay vallas pero no se conoce que placa abre cada una: se asume que cualquier placa abre cualquier valla")

    if links:  # la vision a veces ve una roca sobre una placa vacia (nivel 17, placa (7,8)): una placa de `links` se toma vacia
        filas = layout.split("\n")
        for (pr, pc) in links:
            if 0 <= pr < len(filas) and 0 <= pc < len(filas[pr]) and filas[pr][pc] == "R":
                filas[pr] = filas[pr][:pc] + "_" + filas[pr][pc + 1:]
                avisos.append("la vision vio una roca sobre la placa (fila %d, col %d): se toma como placa vacia" % (pr, pc))
        layout = "\n".join(filas)

    print("\nLayout (%s) - compáralo con la pantalla:" % origen_mapa)
    print(LEYENDA)
    print(layout)
    if info["nivel"] is not None:
        print("Nivel detectado: %d (fuente: %s)%s" % (
            info["nivel"], info["fuente"],
            "  diamantes %s/%s" % (info["recogidos"], info["total"]) if info["total"] else ""))
    else:
        print("Nivel detectado: desconocido")
    for a in avisos:
        print("AVISO:", a)

    print("\nBuscando la ruta mas corta (los niveles con muchos pinchos o llaves pueden tardar hasta ~1-2 min)...", flush=True)
    try:
        moves, origen = solve_layout_text(layout, needed=needed, hand0=hand0, links=links,
                                          rock_over_fence=bool(KNOWN.get(info["nivel"], {}).get("rock_over_fence", True)),
                                          rock_on_spike=bool(KNOWN.get(info["nivel"], {}).get("rock_on_spike", True)),
                                          time_limit=args.max_seconds, max_expansions=6_000_000)
    except ValueError as e:
        print("\nNo se pudo interpretar el nivel:", e)
        print("Revisa que el juego este completo y visible, sin nada encima.")
        return False
    if not moves:
        for peso, limite in ((2.0, 40), (5.0, 40), (10.0, 60)):
            print("\nSin ruta optima en el tiempo dado: reintento con busqueda rapida (peso %g, puede no ser la mas corta)..." % peso, flush=True)
            moves, origen = solve_layout_text(layout, needed=needed, hand0=hand0, links=links,
                                              rock_over_fence=bool(KNOWN.get(info["nivel"], {}).get("rock_over_fence", True)),
                                              rock_on_spike=bool(KNOWN.get(info["nivel"], {}).get("rock_on_spike", True)),
                                              time_limit=limite, max_expansions=6_000_000, weight=peso, use_cache=False)
            if moves:
                origen = "A* rapido peso %g (no garantiza la ruta mas corta)" % peso
                break
    if not moves:
        print("\nNo se encontro solucion (o se agoto el limite de busqueda: %d s / 6 millones de estados)." % args.max_seconds)
        print("Posibles causas: la vision detecto mal alguna casilla, o el nivel necesita reglas no modeladas.")
        return False

    print("\nSolucion (%s): %d pasos" % (origen, len(moves)))
    print(moves)
    if args.dry:
        print("(--dry: no se pulsa ninguna tecla)")
        return True
    print("Jugando...")
    segundos = jugar(moves_to_keys(moves), args.delay, moves, layout, mostrar_pasos(args))
    print("Listo.")
    print(texto_tiempo(segundos, len(moves)))
    registrar(args, dict(nivel=info["nivel"], nivel_fuente=info["fuente"],
                         recogidos_antes=info["recogidos"], total_diamantes=info["total"],
                         layout=layout.split("\n"), mapa_origen=origen_mapa,
                         pasos=len(moves), segundos=round(segundos, 2), movimientos=moves, origen=origen,
                         delay=args.delay, spikes=args.spikes, avisos=avisos), len(moves))
    return True


def main():
    ap = argparse.ArgumentParser(description="Bot de Diamond Rush con solucionador optimo")
    ap.add_argument("--dry", action="store_true", help="solo calcular y mostrar, sin pulsar teclas")
    ap.add_argument("--loop", action="store_true", help="encadenar niveles sin preguntar nada: verifica solo si el juego paso de nivel y lo guarda en el historial")
    ap.add_argument("--needed", type=int, default=None, help="diamantes que faltan por recoger")
    ap.add_argument("--level", type=int, default=None,
                    help="jugar la solucion guardada del nivel N (numero de la cabecera del juego), sin vision")
    ap.add_argument("--delay", type=float, default=DELAY_DEFECTO, help="segundos por paso")
    ap.add_argument("--countdown", type=int, default=3, help="segundos antes de capturar")
    ap.add_argument("--wait", type=int, default=3, help="con --loop: segundos de pausa tras detectar el nivel nuevo, antes de capturarlo")
    ap.add_argument("--timeout-siguiente", type=int, default=25, help="con --loop: segundos maximos esperando que la cabecera cambie de nivel")
    ap.add_argument("--max-niveles", type=int, default=0, help="con --loop: parar tras N niveles completados (0 = sin limite)")
    ap.add_argument("--max-seconds", type=int, default=120, help="tiempo maximo de busqueda de A*")
    ap.add_argument("--spikes", choices=["once", "floor", "wall"], default="once",
                    help="pinchos: once = se pisan una vez y luego son pared (por defecto), floor = suelo, wall = pared")
    ap.add_argument("--candidata", action="store_true", help="con --level: probar la ruta candidata del A* (si el nivel la tiene)")
    ap.add_argument("--pasos", action="store_true", help="mostrar el paso actual (se activa solo si --delay no es el predeterminado)")
    ap.add_argument("--verificar", metavar="RUTA", default=None, help="con --level N: simula una lista de pasos (U/D/L/R) y la PRUEBA en el juego pulsando las teclas (con --dry solo simula)")
    ap.add_argument("--traza", action="store_true", help="con --verificar: mostrar todos los pasos con su casilla")
    ap.add_argument("--historial", action="store_true", help="mostrar el resumen de intentos y salir")
    ap.add_argument("--no-historial", action="store_true", help="no preguntar ni guardar el resultado")
    args = ap.parse_args()

    if args.historial:
        historial.resumen()
        return
    if args.verificar:
        verificar_ruta(args)
        return

    if args.loop and args.level:
        print("--loop no se combina con --level: usa --loop solo (el bot lee el nivel de la pantalla).")
        return

    args._pendiente = None
    ok = un_nivel(args)
    completados, t_total = 0, 0.0
    while args.loop and ok and not args.dry:
        datos = args._pendiente
        args._pendiente = None
        nivel = datos.get("nivel") if datos else None
        print("\nComprobando que el juego pasa de nivel (hasta %d s)..." % args.timeout_siguiente, flush=True)
        if nivel is None:
            print("No se conoce el nivel actual: no se puede verificar; espero %d s y sigo." % args.wait)
            guardar_intento_auto(args, datos, "no_se", "nivel desconocido: sin verificar")
            time.sleep(args.wait)
        else:
            nuevo, estado = esperar_cambio_de_nivel(nivel, args.timeout_siguiente)
            if estado == "cambio":
                completados += 1
                t_total += (datos.get("segundos") or 0)
                print("Nivel %d completado. La cabecera ahora muestra el nivel %d." % (nivel, nuevo))
                guardar_intento_auto(args, datos, "ok", "paso al nivel %d" % nuevo)
                if args.max_niveles and completados >= args.max_niveles:
                    print("Alcanzado --max-niveles (%d)." % args.max_niveles)
                    break
                print("Espero %d s a que cargue el nivel %d..." % (args.wait, nuevo))
                time.sleep(args.wait)
            elif estado == "igual":
                print("La cabecera sigue en el nivel %d: el intento fallo. Me detengo." % nivel)
                guardar_intento_auto(args, datos, "fallo", "la cabecera siguio en el nivel %d" % nivel)
                break
            else:
                print("No pude leer la cabecera tras jugar: no se puede verificar. Me detengo.")
                guardar_intento_auto(args, datos, "no_se", "cabecera ilegible tras jugar")
                break
        args.countdown = 0
        ok = un_nivel(args)
    if args.loop and not args.dry:
        print("\nResumen del bucle: %d nivel(es) completado(s) y verificado(s), %.1f s de juego en total." % (completados, t_total))


if __name__ == "__main__":
    main()

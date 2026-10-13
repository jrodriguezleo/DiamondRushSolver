"""
Niveles 1-19 de Diamond Rush (Minijuegos) transcritos de pantallazos, con el
numero de diamantes necesarios y la solucion optima (en pasos) calculada
previamente (claude/soluciones.md). Sirven de cache y de prueba de regresion.

Leyenda del layout:
    #  pared            .  suelo             P  jugador (inicio)
    D  diamante         E  salida (reja)     R  roca
    O  hoyo             L  lava              K  llave verde
    G  puerta verde     _  placa de presion  |  valla (reja arqueada)
    S  losa lisa (se trata como suelo)
    |  valla; cada placa _ abre UNA sola valla (campo `links` {placa: valla}, coords de este layout)
    ^  pincho: se puede pisar UNA vez; al salir se levanta y queda como pared
       (confirmado en el nivel 3; en los demas niveles aun no estan anotados)
Secuencia: U=arriba D=abajo L=izquierda R=derecha.

NUMERACION: las claves de KNOWN son el numero que el juego muestra en la cabecera
("Level N"). Los documentos del proyecto (levels.py, soluciones.md) numeran segun el
orden de los pantallazos y difieren en los tres primeros niveles; el numero antiguo se
conserva en el campo `doc_level`.
"""

_KNOWN_DOC = {
    1: dict(needed=11, moves=65, grid="""
##########
#...#.#.D#
#P.##.G.E#
#..^..#.D#
##^#G#####
#..#..#DD#
#.D#..GKD#
##.#..#DD#
#K.#D.####
#.##..#..#
#D^^..GKD#
#.###K#..#
##########""", solution="DRDDDDDLDDRRRRRRRLLLUUUURRURDDLULLULUDDDDDDRDULUUUUUUURURRURLDDRU",
        # VERIFICADA en el juego real (65 pasos). La ruta A* antigua de 63 pasos fallaba porque volvia a
        # pisar pinchos ya levantados; con esa regla el A* da la candidata de 63 pasos (sin probar aun).
        solution_a_star="DRDDDDDLDDRRRUUUUUUDDDDDDRDURRRLLLUUUURRURDDLULLULUURURRURLDDRU"),
    2: dict(needed=12, moves=22, grid="""
##########
#..#######
#..#######
#.PDDD...#
#######D.#
#######D.#
#.D.DD...#
#.D.######
#.D.######
###.DD...#
###..#.E.#
#....#...#
##########""", solution="RRRRRDDDLLLLLDDRDRRRDR"),
    3: dict(needed=14, moves=34, grid="""
##########
#..D..#LL#
#.D.D.#LL#
#.###.##.#
#DLL#D.D.#
#DLL#D.D.#
#.###.#LL#
#.#.D.#LL#
#.#E#.####
#.###....#
#DD...SP.#
#DD##....#
##########""", solution="LLLLLDLUUUUUUUUURURDRRDDRRDLLDDLLD"),
    4: dict(needed=6, moves=47, grid="""
##########
#.P......#
######R###
#..DD.O..#
#R########
#O...R.D.#
######D###
#.....S..#
#.R......#
##..R#O#.#
###OD#E#.#
####D###.#
##########""", solution="RRRRDDLLLLLDDRRRRRRLDDLLLLLDRURDDDRDUULURRURDDD"),
    5: dict(needed=8, moves=53, grid="""
##########
#E#####DD#
#P...K#DD#
#.##R###G#
#D#...##O#
#D#......#
#O#.S....#
#.....#..#
#....###.#
#LLL.###R#
#LLL.....#
#####DD###
##########""", solution="RRRRLDDLDDDDRDDRDRURRUUUUUUUUULDRDDDLLLULUULLLDDDUUUU"),
    6: dict(needed=8, moves=77, grid="""
##########
#....P...#
#.R.DD.RK#
#O#.##.#O#
#........#
#........#
#..##G#..#
#.D#ED#.D#
##G####^##
#O.DDD...#
#.######^#
#^.DKD...#
##########""", solution="RRRDLLLLULDDDRDLULDLDDRDULUURDDDUUURRRRRDDDDLLLLLLDDRRRRRRRUULLLLLLUUUURRRDDL"),
    7: dict(needed=8, moves=42, grid="""
##########
##R.R.##.#
#RPR.R.#.#
#.R#D#R#D#
#R.R.R##R#
##R.O.#KD#
#.D.#R#.R#
#R##R.#.D#
#OR..D.O##
#..##G##R#
#D.#.D.#.#
#.##.E.#R#
##########""", solution="RURDDDDLDLLDDDDUURRRRRRUUURUUDDLDDRLDLLDDD"),
    8: dict(needed=11, moves=49, grid="""
##########
##D.D.D.##
##.####D##
##D#.E#.##
##.D.D#.##
#######G##
##_.RP.D##
#######|##
##ORD^|.##
##K#^^#.##
##R#^^#^##
##OR.D_D##
##########
##########""", solution="LLRRRRDDDDDLLLUUULLDDDRRRUUURRUUUUUUULLLLLDDDRRRU",
        links={(6, 2): (7, 7), (11, 6): (8, 6)}),  # placa -> valla que abre (confirmado por el usuario)
    9: dict(needed=12, moves=71, grid="""
##########
#....P...#
#.RDD....#
#_##|#####
#D..RDD.##
##......_#
##|#######
#..#..D..#
#......D.#
#.#.#.#|##
#.R.#_#D.#
#DDD#D#.E#
##########""", solution="DLLLULDRRRDDLDRRRRULLLLLLRDDDDLDDDURDRUUDLLUURRRRDDDUUUURRDLULDDURRDDDR",
        links={(3, 1): (3, 4), (5, 8): (6, 2), (10, 5): (9, 7)}),  # placa -> valla (confirmado por el usuario),
    10: dict(needed=10, moves=68, grid="""
##########
#..^..^..#
#D##..##D#
#DD#E.#DD#
#.D##P#D.#
##.#..#.##
#DO.^^.OD#
##^#RR#^##
#........#
#.R....R.#
#.#.RR.#.#
#....S...#
##########""", solution="DDDDLDRDRURLLURDRUUURLUUURUULLLDDDDLDDDRDLDLULRRULDLUUULRUUULUURRRDD",
        # la ruta de 58 pasos del A* ponderado FALLO en el juego: no usar
        ),  # regla rock_on_spike confirmada: ahora es global
    11: dict(needed=11, moves=72, grid="""
##########
#K..###_.#
#.P.ED|..#
#^#####O##
#..#DD#D.#
#.D...#D.#
#^###...##
#.^.#OR.K#
#R#.#...##
#.DD.R..##
#O###R#^##
#.^DG.GDD#
##########""", solution="ULDDDDRLDDDDRRRRLLLLDDRRRRUUUURDRURLUUUDDLLULURDDDDDRLDDRRRLUUUUUUUUULLL",
        links={(1, 7): (2, 6)}),  # unica placa -> unica valla,
    12: dict(needed=9, moves=60, grid="""
##########
#.DP.^#D##
#####.^.^#
##.G.^##R#
#D.#...^D#
##.#####.#
##|#L#L#.#
#DD..#...#
#^##R#.#D#
#^#..#.RO#
#KDD._..E#
##########
##########""", solution="LRRRDRRUDRDDDDDDDLDLLLLLLUUURRRDDLDRUUULLUUULRDDDRRDDDRRURRD"),
    13: dict(needed=11, moves=60, grid="""
##########
#DD.^.D.K#
#D#^##G###
###..D...#
#D#.#R##^#
#.^K|_..D#
#.#.##.###
#D#^#..#^#
#.#.#D.^E#
#G#^##^###
#..DP..D.#
##########
##########""", solution="LUUUUUUUUULLDURRRRRDURRLLDDLRRRDDLLLLLLLUDDDDDDRRRRRRLUULRRR"),
    14: dict(needed=9, moves=85, grid="""
##########
#..D..#DD#
##|#E##DD#
#...#.#|##
#D..D#...#
#.#|#.#O_#
##.R_#D..#
#...#D...#
##G#.##R##
#_.._.|..#
##..R.##K#
####P#####
##########""", solution="URURRRDULLLDLLULUUURDLDDDRRRURRUURUUULUUURDLDDRDDDLLLRURDRUDLDDLLLLLUUURUURLLLURUURRD",
        links={(9, 4): (9, 6), (9, 1): (5, 3), (5, 8): (2, 2), (6, 4): (3, 7)}),  # placa -> valla (confirmado por el usuario),
    15: dict(needed=7, moves=65, grid="""
##########
#E.#.^.D.#
##G#.#.R.#
#..#.#...#
#P.D.#D_.#
#^##.#.R.#
#D##.^...#
#..#^###R#
##^#DRO..#
#..###R###
#K.|.D.D.#
##########
##########""", solution="RRRDDDDRRDURRUULULUUUURLLLDDDLLLDDDRDDDLRRRRRRLUURRUULLLLUULLUUUL"),
    16: dict(needed=5, moves=98, grid="""
##########
#LLLLLLLL#
#LL#LL#LL#
#LLLLLLLL#
#P..#..#D#
#.#....R.#
#.#R##R#.#
#.#..D.#.#
#D...#.#.#
#.##...D.#
#.#D.#####
#....OOOE#
##########""", solution="RRDDDRRRDDRRUUUUUDLLLLRRDDDUUURRDDDDLLLRUULLDDDLDRLLLUUURRLLUUUURRDDDRDDDLDRRLLLLUUURRURDDDLDRRRRR"),
    # Nivel 17: la placa (7,8) empieza VACIA (la vision a veces ve una roca ahi: error). Se pulsa empujando la roca (8,5).
    # Empujar una roca sobre una valla ABIERTA sigue sin probar (el fallo del 78-pasos fue porque (3,5) estaba cerrada).
    17: dict(needed=8, moves=90, grid="""
##########
#..D.^.#K#
#D####.#|#
#.|K_|._.#
#P##D###D#
#.^.R....#
#.^.R.####
#.##.###_#
###..R...#
#D#^^##.D#
#DG..D#G##
#######.E#
##########""", solution="DDRRRDDRRRDRULLLLUUUUDLLLUUUURRLLDDRRRRRLLDDDDDLDDLLUDRRRRLUUUUURRRRUUUUDDDDLLLLDDDRRRDDDR",
        links={(3, 4): (3, 2), (7, 8): (3, 5), (3, 7): (2, 8)},  # placa -> valla (confirmado por el usuario)
        rock_over_fence=True),  # CONFIRMADO: roca sobre valla abierta (ahora global)
    18: dict(needed=14, moves=63, grid="""
##########
#.D.D.D.D#
#D######|#
#.#..D...#
#D#_##.#.#
#.#.|EDR.#
#D#P##.#D#
#.#....#.#
#D#R##_#D#
#.#....#.#
#DR_.#D|.#
##########
##########""", solution="UUURRRRRDDDDDUUULRUULLDDDDUUUURRUULLLLLLLDDDDDDDDDRRURRRDUUUUUL",
        links={(4, 3): (10, 7), (8, 6): (2, 8), (10, 3): (5, 4)}),  # placa -> valla (confirmado por el usuario)
    19: dict(needed=7, moves=50, grid="""
##########
#E##K#.D.#
#D#..#.#.#
#|_..|...#
#.##P##..#
#...D##RD#
#.#.....##
#.##R##..#
#D.D.#.._#
#.####.###
#.G...D.##
##########
##########""", solution="DLLLDDDRRRUURRRDDLDDUURUUURUUUULRDDDDLDLLLUUULLLUU",
        links={(3, 2): (3, 1), (8, 8): (3, 5)}),  # placa -> valla (confirmado por el usuario),
    # Nivel 20: TOTEM dorado en vez de escalera (casilla 'E' = (8,1) abajo a la izquierda); no hay diamantes (la cabecera dice 0/14: se ignora).
    # Mapa transcrito de la captura (la vision no ve el totem ni el hoyo (0,1)); la ruta se calculo con A* ponderado (no garantiza la mas corta).
    20: dict(needed=0, moves=81, grid="""#O..R..R.#
##R##....#
##...R.P.#
#..R.OO###
#R..R#RR##
####O#.R.#
#OOORRO..#
#E##OR##.#
###..R#..#
#....ORRR#
#.ORR#...#
#R...#.R.#
##########""", solution="LLLDDDDUULLUURRRURDDDDDRRULDLLLUULLURURDDUURRDDDRDLLLLRRRUUUULLDDDUUURRDDDDLLLLLD",
        usar_guardado=True),
}

# Numeracion: las claves de KNOWN son el numero que muestra la cabecera del juego (HUD). En el documento original
# los tres primeros niveles estaban en otro orden: nivel del documento -> nivel del juego.
_DOC_A_JUEGO = {1: 3, 2: 1, 3: 2}

KNOWN = {_DOC_A_JUEGO.get(doc_level, doc_level): k for doc_level, k in _KNOWN_DOC.items()}

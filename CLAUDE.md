# Diamond Rush Bot — contexto del proyecto

Responde siempre en español. Antes de ejecutar cualquier cosa que pulse teclas o
tome la pantalla, avisa; para pruebas usa `python main.py --dry`.

## Estado actual (2026-10-18)
Proyecto funcional: el bot lee la pantalla, calcula la ruta con MENOS pasos y la juega.
Los niveles 1 a 20 se completaron correctamente en el juego real con `python main.py --loop --delay 0.3`
(verificado el 2026-10-13). Repositorio propio, una sola rama (`main`), historial limpio.

## Objetivo
Bot que juega Diamond Rush (Minijuegos.com, en el navegador) con reconocimiento de imagen y la
ruta con MENOS pasos. Parte del repo SebMatDo/Diamond-Rush-Bot (agente codicioso + visión); su
código se auditó: sin red, subprocess, eval ni ofuscación. El solver óptimo, la lectura de
cabecera y el historial son aportes de este repo.

## Repositorio y Git
- Remoto `origin`: https://github.com/jrodriguezleo/DiamondRushSolver (repo PROPIO; el push es
  válido). El repo original de SebMatDo NO es nuestro: no se hace push allí.
- Una sola rama: `main`. Tag `v0.1-estable` = bot funcionando con el algoritmo codicioso original.
  Las ramas `estable`, `solver-astar` y `help` se eliminaron (estaban contenidas en `main`).
- Historial reescrito con `git filter-repo` el 2026-10-18 para quitar `.venv/` (se había
  commiteado por error) y las capturas antiguas `screenshots/screenshotN.png`. Los hashes
  cambiaron y se subió con `--force`; `.git` pasó de ~757 MB a ~36 MB. Cualquier clon anterior
  a esa fecha debe descartarse y volver a clonarse.
- `.gitignore`: venv/, .venv/, __pycache__/, *.pyc, .DS_Store, mi_captura.png, captura_juego.png,
  main_anterior.py, historial_intentos.jsonl (el historial de intentos es local).
- `deprecated/` (plantillas viejas) se eliminó.

## Entorno (MacBook, macOS, pantalla Retina)
- Python 3.12 en `./venv` (`source venv/bin/activate`). Se necesita Python >= 3.10
  (el repo usa `match` y `X | None`; el README original decía 3.8 y era falso).
  Si se mueve o renombra la carpeta, recrear: `rm -rf venv && python3.12 -m venv venv &&
  source venv/bin/activate && pip install -r requirements.txt`.
- Dependencias: `opencv-python pyautogui scikit-image` (`requirements.txt` generado con
  `pip freeze`, incluye pyobjc para macOS). NO usar `pyKey` (solo Windows) ni `pytautogui` (typo).
- Permisos de macOS para la app de terminal: Accesibilidad (enviar teclas) y Grabación de
  pantalla (capturas). Tras darlos hay que cerrar la app con ⌘+Q.

## Estructura del código
Flujo actual (lo que usa `main.py`):
- `diamond_rush_vision.py`: captura y visión por plantillas (`objects_in_game/`).
- `hud_reader.py` + `nivel.py`: identifican el nivel y los diamantes que faltan desde la cabecera.
- `bot_solver.py`: puente visión -> layout y caché de niveles conocidos.
- `diamond_solver.py`: A* óptimo (`solve_layout`, `simulate`).
- `known_levels.py`: niveles 1-20 (layout, `needed`, `links`, solución óptima).
- `historial.py`: registro de intentos en `historial_intentos.jsonl`.
- `main.py`: CLI y bucle de juego.
Código heredado del agente codicioso original (NO lo usa `main.py`, se conserva por referencia
y para `v0.1-estable`): `smart_agent.py`, `game_state.py`, `a_star.py`, `rock_simulation.py`
(con simulación de rocas defectuosa), `keyboard_simulator.py`, `cell.py`, `game_action.py`.

## Hallazgos de la visión (diamond_rush_vision.py)
- Cuadrícula del bot: 15 filas x 10 columnas. La cabecera (contador, botones) ocupa
  las 2 primeras filas; el tablero real son las filas 2..14 (13x10).
- `pyautogui.screenshot()` en Retina devuelve píxeles físicos (p. ej. 2816x1762).
- Con `show_image=True` la ventana de depuración se cuela en la siguiente captura y
  confunde la detección: en tiempo real usar `show_image=False`.
- Las etiquetas del modo depuración se dibujan ENCIMA de la celda que describen.
- Falsos positivos de `spike` sobre suelo normal (ver reglas de pinchos más abajo).
- La cabecera tapa parcialmente la fila superior en algunos niveles (nivel 8).
- Tipos de celda: terrain, player, player-with-key, diamond, ladder, ladder-open,
  rock, rock-in-fall (hoyo relleno), fall (hoyo), key, door (puerta verde),
  metal-door (valla), push_button (placa), spike, spike-up, totem (nivel 20). La lava no se
  detecta (queda como None = pared, equivalente).

## Solucionador óptimo
- `diamond_solver.py`: A* por macro-movimientos, heurística MST (admisible y consistente).
  Costo = pasos. API: `solve_layout(layout, needed=None)` -> "UDLR..." o None.
  `simulate(layout, moves, needed)` verifica una ruta paso a paso.
- `bot_solver.py`: puente visión -> layout (`grid_to_layout`) y caché (`solve_layout_text`).
- `known_levels.py`: niveles 1-20. Sirve de caché y de prueba de regresión.
- `main.py`: `--dry`, `--loop`, `--needed N`, `--delay S` (defecto 0.25; usar 0.3 si se pierden
  teclas), `--countdown S`, `--wait S`, `--timeout-siguiente S`, `--max-niveles N`,
  `--max-seconds S`, `--spikes once|floor|wall`, `--level N` (juega la solución guardada sin
  visión), `--candidata`, `--verificar RUTA`, `--traza`, `--pasos`, `--historial`, `--no-historial`.
- Si A* óptimo agota el tiempo, `main.py` reintenta con A* ponderado (pesos 2, 5 y 10): ruta
  válida pero no necesariamente la más corta.
- Validación: las soluciones conocidas son válidas en el simulador y el A* reproduce la longitud
  óptima (nivel 11: 72 pasos, ~224 s, ~2,9 M expansiones; el resto de décimas de segundo a ~7 s).
  Con las capturas de `screenshots/Levels/`, la visión + solver resuelve 14 de 18; los fallos son
  de detección.
- Numeración: las claves de `known_levels.KNOWN` son el número que muestra el juego en la
  cabecera ("Level N"). Los docs antiguos del proyecto (levels.py, soluciones.md) difieren solo
  en los 3 primeros: juego1=doc2, juego2=doc3, juego3=doc1 (campo `doc_level`). `--level N` usa
  la numeración del juego.

## Reglas del juego (confirmadas jugando)
- Pared/lava bloquean. Roca: se empuja si la casilla siguiente está libre; puede quedar sobre
  diamante/llave; una roca en un hoyo lo rellena. Llave: máx. 1 en mano. Puerta: se abre gastando
  la llave. Salida: bloqueada hasta tener `needed` diamantes.
- Diamantes: la cabecera manda (`needed = total - recogidos`). Nivel 6: hay 10 diamantes pero la
  salida se abre con 8. `--needed N` lo fuerza.
- Pinchos `^`: se pisan UNA vez y al salir se levantan (quedan como pared). Por defecto
  `--spikes once`. Una roca empujada sobre un pincho lo desactiva y la casilla pasa a suelo
  (`rock_on_spike=True` por defecto en `Level`, `simulate`, `solve_layout_text`).
- Placas `_` y vallas `|`: cada placa abre UNA sola valla. `known_levels` guarda
  `links={(fila,col) placa: (fila,col) valla}`; sin `links` el solver asume que cualquier placa
  abre cualquier valla (aproximación antigua). `nivel.links_para` los traslada al layout
  detectado. La valla está abierta si alguna roca está sobre una placa O el jugador está parado
  en una placa (el nivel 19 lo necesita). Las placas NO son permanentes: una roca sobre una placa
  la mantiene pulsada.
- Una roca SÍ se puede empujar sobre una valla abierta (nivel 17, `rock_over_fence=True`); una
  valla cerrada la bloquea. La visión a veces ve una roca sobre una placa vacía (nivel 17, placa
  (7,8)): `main.py` la toma como placa vacía si está en `links`.

## Identificación de nivel e historial
- `hud_reader.py`: lee "Level N  c/N" de la cabecera sin OCR (glifos blancos + diamante celeste
  como ancla + plantillas en `hud_digits/`, generadas con `build_hud_templates.py` a partir de
  `screenshots/Levels/`; `--extra PNG NIVEL RECOGIDOS NECESARIOS` añade capturas propias, útil
  sobre todo para los dígitos 6 y 9). Si no hay plantillas, no falla: usa el mapa. Validado 20/20
  sobre `screenshots/Levels` y en vivo en el Mac.
- `nivel.py`: `identificar` combina cabecera (principal) y parecido del mapa con KNOWN
  (respaldo/contraste). `faltan` = total - recogidos se usa como `needed` automático.
  `completar_con_guardado`: si la cabecera tapa la fila superior (nivel 8) y el nivel acaba de
  empezar, usa el mapa guardado (`desfase` alinea el mapa detectado, que va una fila desplazado).
- `historial.py` + `main.py`: tras jugar pregunta "¿La ejecución fue correcta? s/n/?/x" (si n:
  paso donde se desvió y nota) y añade una línea a `historial_intentos.jsonl` (nivel, fuente,
  layout, pasos, movimientos, delay, resultado, versión git...). `--historial` muestra el
  resumen por nivel; `--no-historial` lo omite; con `--dry` nunca se guarda.
- Limitación: con el juego muy pequeño en pantalla los dígitos no se leen (cae al mapa).

## Modo --loop (sin input)
`python main.py --loop`: no pregunta nada. Tras cada nivel mira la cabecera (`nivel_en_pantalla`,
lee "Level N" cada segundo hasta `--timeout-siguiente`, 25 s): si cambia -> historial `ok`
(verificación automática), pausa `--wait` (3 s) y sigue; si sigue igual -> `fallo` y se detiene;
si no se lee -> `no_se` y se detiene. `--max-niveles N` limita la tanda. No se combina con
`--level`. Probado en vivo: niveles 1 a 20 seguidos sin fallos.

## Notas por nivel (numeración de la cabecera)
- Niveles 1 a 20: completados en el juego real (2026-10-13). Rutas de referencia: nivel 3 en
  65 pasos (existe una candidata A* de 63 sin probar, `--level 3 --candidata`); nivel 6 en 77
  pasos con 8 de 10 diamantes; nivel 10 en 68 pasos (la candidata de 58, `solution_a_star`, sin
  probar); nivel 11 en 72; nivel 12 en 60; nivel 13 en 60 (la antigua repetía un pincho); nivel 14
  en 85; nivel 17 en 78 si la visión ve la roca inicial sobre la placa (90 sin ella); nivel 20 en
  81 (A* ponderado, no necesariamente óptima).
- Nivel 8: placa (6,2)->valla (7,7) y placa (11,6)->valla (8,6); ruta de 49 pasos (con placas
  emparejadas; sin emparejar salía 45). El cuadro WALKTHROUGH tapa 3 diamantes de la fila
  superior.
- Nivel 9: sin pinchos; placas->vallas (3,1)->(3,4), (5,8)->(6,2), (10,5)->(9,7); 71 pasos.
- Nivel 11: pinchos (3,1),(6,1),(7,2),(10,7),(11,2); una placa (1,7)->valla (2,6).
- Nivel 14: (9,4)->(9,6), (9,1)->(5,3), (5,8)->(2,2), (6,4)->(3,7).
- Nivel 17: placas A(3,4)->valla(3,2), I(7,8)->valla(3,5), E(3,7)->valla(2,8); pinchos
  (1,5),(5,2),(6,2),(9,3),(9,4).
- Nivel 20 (tótem): la salida es un TÓTEM dorado (plantilla `objects_in_game/totem.png`,
  símbolo 'E'); no hay diamantes (la cabecera dice 0/14: se ignora, `needed=0`). Está en (8,1),
  solo se llega por el hoyo (7,1), que hay que rellenar con una roca. La visión lee mal dos hoyos
  ((0,1) como suelo y (7,1) como pincho), por eso el nivel lleva `usar_guardado=True`.
- Pinchos de los niveles 2, 5, 10, 15, 17, 18, 19 detectados en capturas pero sin confirmar uno
  a uno (las rutas funcionaron igualmente). Nivel 3: (3,3),(4,2),(10,2),(10,3). Nivel 8: 6
  pinchos confirmados con captura. Niveles 12 y 13 anotados.
- Reescaneo de `screenshots/Levels` vs `known_levels`: solo difieren lava (L->#), salidas
  cerradas, vallas y losas lisas (límites de la detección).

## Verificar rutas a mano
`python main.py --level N --verificar "DDLR..."` simula la ruta sobre el mapa guardado y la juega
pulsando las teclas (`--dry`: solo simula; `--traza`: todos los pasos). Muestra qué reglas
dudosas necesita la ruta.

## Pendiente
1. Tests automáticos (regresión de las soluciones conocidas y de la lectura de cabecera).
2. Mejorar la visión: falsos pinchos, fila tapada por la cabecera, lava, losas lisas, rocas
   sobre placas.
3. Optimizar el nivel 11 (podas de estados muertos, C++/Rust) si hace falta.
4. Probar las rutas candidatas más cortas (nivel 3: 63; nivel 10: 58) y confirmar pinchos
   pendientes.
5. Revisar si el repo original tiene licencia: no hay archivo `LICENSE` en este repo.
6. Decidir si se eliminan los módulos heredados del agente codicioso.

# Diamond Rush Bot — contexto del proyecto

Responde siempre en español. Antes de ejecutar cualquier cosa que pulse teclas o
tome la pantalla, avisa; para pruebas usa `python main.py --dry`.

## Objetivo
Bot que juega Diamond Rush (Minijuegos.com, en el navegador) con reconocimiento
de imagen y la ruta con MENOS pasos. Base: repo SebMatDo/Diamond-Rush-Bot
(origin; NO hacer push ahí, no es nuestro). Su código se auditó: sin red,
subprocess, eval ni ofuscación.

## Entorno (MacBook, macOS, pantalla Retina)
- Python 3.12 en `./venv` (`source venv/bin/activate`). Se necesita Python >= 3.10
  (el repo usa `match` y `X | None`; su README dice 3.8 y es falso).
- Dependencias: `opencv-python pyautogui scikit-image` (`requirements.txt` regenerado
  con `pip freeze`). NO usar `pyKey` (solo Windows) ni `pytautogui` (typo de pyautogui).
- Permisos de macOS para la app de terminal: Accesibilidad (enviar teclas) y
  Grabación de pantalla (capturas). Tras darlos hay que cerrar la app con ⌘+Q.
- Git (convención): rama `estable` con tag `v0.1-estable` = bot funcionando con el
  algoritmo codicioso original; los cambios del solver van en la rama `solver-astar`.
  `.gitignore`: venv/, __pycache__/, *.pyc, capturas .png sueltas.

## Hallazgos de la visión (diamond_rush_vision.py)
- Cuadrícula del bot: 15 filas x 10 columnas. La cabecera (contador, botones) ocupa
  las 2 primeras filas; el tablero real son las filas 2..14 (13x10).
- `pyautogui.screenshot()` en Retina devuelve píxeles físicos (p. ej. 2816x1762).
- Con `show_image=True` la ventana de depuración se cuela en la siguiente captura y
  confunde la detección: en tiempo real usar `show_image=False`.
- Las etiquetas del modo depuración se dibujan ENCIMA de la celda que describen.
- Falsos positivos de `spike` sobre suelo normal; en niveles 1-19 no hay pinchos,
  así que se tratan como suelo.
- La cabecera tapa parcialmente la fila superior en algunos niveles (nivel 8).
- Tipos de celda: terrain, player, player-with-key, diamond, ladder, ladder-open,
  rock, rock-in-fall (hoyo relleno), fall (hoyo), key, door (puerta verde),
  metal-door (valla), push_button (placa), spike, spike-up. La lava no se detecta
  (queda como None = pared, equivalente).

## Solucionador óptimo (archivos en la raíz del repo)
- `diamond_solver.py`: A* por macro-movimientos, heurística MST (admisible y
  consistente). Costo = pasos. API: `solve_layout(layout, needed=None)` -> "UDLR..." o None.
  `simulate(layout, moves, needed)` verifica una ruta paso a paso.
- `bot_solver.py`: puente visión -> layout (`grid_to_layout`) y caché de niveles
  conocidos (`solve_layout_text`).
- `known_levels.py`: niveles 1-19 (layout, `needed`, solución óptima). Sirve de caché y
  de prueba de regresión.
- `main.py` (nuevo): `--dry`, `--loop`, `--needed N`, `--delay S`, `--countdown S`,
  `--spikes wall`, `--level N` (juega la solución guardada sin visión), `--historial`, `--no-historial`.
- Pinchos `^` (CONFIRMADO por el usuario): se pisan UNA vez y al salir se levantan (quedan como pared). Antes se trataban como suelo/falso positivo: error. Por defecto `--spikes once`. Solo el nivel 3 tiene sus pinchos anotados en known_levels (3,3),(4,2),(10,2),(10,3); los demás niveles hay que revisarlos.
- Nivel 3 verificado en el juego: 65 pasos (`solution`); candidata A* de 63 en `solution_a_star` (`--level 3 --candidata`).
- Diamantes: la cabecera manda (`needed = total - recogidos`). Nivel 6 (confirmado): hay 10 diamantes pero la salida se abre con 8; la ruta de 77 pasos (con pinchos de un paso) es la idónea. `--needed N` lo fuerza.
- Placas y vallas (CONFIRMADO): cada placa `_` abre UNA sola valla `|`. `known_levels` guarda `links={(fila,col) placa: (fila,col) valla}` por nivel; sin `links` el solver asume que cualquier placa abre cualquier valla (aproximación antigua). `nivel.links_para` los traslada al layout detectado. Nivel 8: placa (6,2)->valla (7,7) y placa (11,6)->valla (8,6); con esto la ruta óptima pasó de 45 a 49 pasos.
- Reglas modeladas: pared/lava bloquean; roca se empuja si la casilla siguiente está
  libre y puede quedar sobre diamante/llave; roca en hoyo lo rellena; llave máx. 1 en
  mano; puerta se abre gastando la llave; valla abierta si alguna roca está sobre una
  placa O el jugador está parado en una placa (el nivel 19 lo necesita); salida
  bloqueada hasta tener `needed` diamantes.
- Validación hecha: las 19 soluciones conocidas son válidas en el simulador y el A*
  reproduce la longitud óptima en los 19 (nivel 11: 72 pasos, ~224 s, ~2,9 M
  expansiones; el resto de décimas de segundo a ~7 s). Con las capturas del repo
  (`screenshots/`), la visión + solver resuelve 14 de 18; los fallos son de detección.
- Numeración: las claves de `known_levels.KNOWN` son el número que muestra el juego en
  la cabecera ("Level N"). Los docs del proyecto (levels.py, soluciones.md) difieren solo
  en los 3 primeros: juego1=doc2, juego2=doc3, juego3=doc1 (campo `doc_level`). Verificado
  con capturas en 1,2,3,4,5,8,9,13,15; el resto se asume igual. `--level N` usa la del juego.

## Identificación de nivel e historial
- `hud_reader.py`: lee "Level N  c/N" de la cabecera sin OCR (glifos blancos + diamante
  celeste como ancla + plantillas en `hud_digits/`, generadas con `build_hud_templates.py`
  a partir de `screenshots/`; `--extra PNG NIVEL RECOGIDOS NECESARIOS` añade capturas
  propias, útil sobre todo para los dígitos 6 y 9). Si no hay plantillas, no falla: usa el mapa.
- `nivel.py`: `identificar` combina cabecera (principal) y parecido del mapa con KNOWN
  (respaldo/contraste). `faltan` = total - recogidos se usa como `needed` automático.
  `completar_con_guardado`: si la cabecera tapa la fila superior (nivel 8) y el nivel
  acaba de empezar, usa el mapa guardado.
- `historial.py` + `main.py`: tras jugar pregunta "¿La ejecución fue correcta? s/n/?/x"
  (si n: paso donde se desvió y nota) y añade una línea a `historial_intentos.jsonl`
  (nivel, fuente, layout, pasos, movimientos, delay, resultado, versión git...).
  `python main.py --historial` muestra el resumen por nivel; `--no-historial` lo omite;
  con `--dry` nunca se guarda.
- Limitaciones: con el juego muy pequeño en pantalla los dígitos no se leen (cae al mapa);
  nunca probado aún con la pantalla real del Mac.

## Modo --loop (sin input)
`python main.py --loop`: no pregunta nada. Tras cada nivel mira la cabecera (`nivel_en_pantalla`, lee "Level N"
cada segundo hasta `--timeout-siguiente`, 25 s): si cambia -> historial `ok` (verificacion automatica), pausa
`--wait` (3 s) y sigue; si sigue igual -> `fallo` y se detiene; si no se lee -> `no_se` y se detiene.
`--max-niveles N` limita la tanda. No se combina con `--level`. Lectura de cabecera validada 20/20 sobre
screenshots/Levels. No probado aun en vivo (se desconoce si el juego muestra pantallas intermedias).

## Niveles verificados en el juego real (numeración de la cabecera)
- Niveles 1 a 7: ejecución perfecta (confirmado por el usuario el 2026-10-13). Nivel 3: 65 pasos
  (candidata A* de 63 sin probar). Nivel 6: 77 pasos con pinchos de un paso y 8 de 10 diamantes.
- Nivel 8: pinchos anotados (6, confirmados con captura). El cuadro WALKTHROUGH tapa 3 diamantes de la fila superior y el mapa detectado va desplazado una fila: `nivel.completar_con_guardado` alinea (`desfase`) y usa el mapa guardado. Ruta 49 pasos (con placas emparejadas), sin probar aún en el juego.
- Nivel 9: sin pinchos (confirmado); placas->vallas: (3,1)->(3,4), (5,8)->(6,2), (10,5)->(9,7). Ruta 71 pasos (la antigua de 49 era inválida), sin probar aún en el juego.
- Nivel 11: pinchos anotados ((3,1),(6,1),(7,2),(10,7),(11,2)); sigue en 72 pasos. Una placa (1,7)->valla (2,6). Nivel 14: (9,4)->(9,6), (9,1)->(5,3), (5,8)->(2,2), (6,4)->(3,7); ruta 85 pasos (la antigua de 53 era inválida), sin probar; pinchos de los niveles 11 y 14 sin revisar.
- Niveles 14, 15 y 16: ejecución perfecta (confirmado por el usuario). Niveles 12 y 13: pinchos anotados (detectados por la visión sobre screenshots/Levels, confirmados bien ubicados); 12 sigue en 60 pasos, 13 pasó a una ruta nueva de 60 (la antigua repetía un pincho).
- Pinchos detectados en capturas pero SIN confirmar: niveles 2, 5, 10, 15, 17, 18, 19 (script de apoyo: detectar con la visión sobre `screenshots/Levels/Level N.png`).
- Nivel 17: placas A(3,4)->valla(3,2), I(7,8)->valla(3,5), E(3,7)->valla(2,8). Con esos pares NO hay solución a menos que una roca pueda empujarse sobre una valla abierta (HIPÓTESIS, flag `rock_over_fence`, solo activa en el nivel 17). Ruta 90 pasos con los 5 pinchos detectados ((1,5),(5,2),(6,2),(9,3),(9,4); sin confirmar, la ruta es válida aunque no lo fueran). Sin probar en el juego.
- Nivel 17 (EN VIVO): la visión ve una roca ENCIMA de la placa (7,8) al empezar; `Level` acepta una roca sobre una placa si `links` indica ahí una placa (símbolo R en el layout). Con ese estado la ruta es de 78 pasos (con `rock_over_fence`); sin roca inicial, 90. El bot resuelve siempre sobre lo que ve en vivo. Reescaneo de screenshots/Levels vs known_levels: solo difieren lava (L→#), salidas cerradas, vallas y losas lisas (límites de la detección).
- Niveles 10 a 19: soluciones calculadas, sin verificar; sus pinchos (`^`) aún no están anotados.

## Pendiente
1. Probar `python main.py --dry` y luego jugar en el Mac; comparar el layout impreso
   con la pantalla. (El flujo completo solo se ha probado con visión y teclado
   simulados, no en el juego real con el código nuevo.)
2. Confirmar reglas dudosas: roca sobre diamante, placas<->vallas (cualquier placa o
   pares), losa lisa, lava, jugador sobre placa.
3. Capturas completas del nivel 20 (es más alto que la pantalla).
4. Validar en el Mac la lectura de la cabecera (`--dry` imprime "Nivel detectado").
5. Mejorar la visión: falsos pinchos, fila tapada por la cabecera, validar rocas,
   llaves, puertas, placas y vallas con capturas reales de tu pantalla.
6. Optimizar el nivel 11 (podas de estados muertos, C++/Rust) si hace falta.
7. Añadir tests automáticos (regresión de las 19 soluciones).

## Regla confirmada: roca sobre pincho (nivel 10)
Una roca empujada sobre un pincho (`^`) lo desactiva y la casilla pasa a ser suelo normal. Confirmada
jugando la ruta manual de 68 pasos del nivel 10. Es global (`rock_on_spike=True` por defecto en
`Level`, `simulate`, `solve_layout_text`). Nivel 10: 6 pinchos, 68 pasos verificados en el juego; la ruta
de 58 pasos (`solution_a_star`, `--candidata`) esta sin probar.
Si A* optimo agota el tiempo, `main.py` reintenta con A* ponderado (weight=2.0): ruta valida pero no
necesariamente la mas corta.

## Verificar rutas a mano
`python main.py --level N --verificar "DDLR..."` simula la ruta sobre el mapa guardado y la juega pulsando
las teclas (`--dry`: solo simula; `--traza`: todos los pasos). Muestra que reglas dudosas necesita la ruta.

## Roca sobre valla ABIERTA (nivel 17): CONFIRMADA
Una roca SI se puede empujar sobre una valla abierta (confirmado: nivel 17, ruta de 90 pasos perfecta). Una valla cerrada la bloquea.
La visión a veces ve una roca sobre una placa vacía (nivel 17, placa (7,8)): `main.py` la toma como placa vacía si está en `links`.
Las placas NO son permanentes; una roca sobre una placa la mantiene pulsada. El nivel 17 usa `rock_over_fence=True`.


## Nivel 20 (totem)
La salida es un TOTEM dorado (plantilla `objects_in_game/totem.png`, simbolo 'E'); no hay diamantes (la cabecera dice 0/14: se ignora,
`needed=0`). El totem esta en (8,1), solo se llega por el hoyo (7,1), que hay que rellenar con una roca. La vision lee mal dos hoyos
(el (0,1) como suelo y el (7,1) como pincho), por eso el nivel lleva `usar_guardado=True`: si el mapa detectado encaja con el guardado
se usa el guardado. Ruta de 81 pasos calculada con A* ponderado (peso 8-10; el optimo no termina): valida en el simulador, SIN PROBAR en el juego.
`main.py` ahora reintenta con pesos 2, 5 y 10 si A* optimo agota el tiempo.

## Estado verificado (2026-10-13)
Ejecución en bucle (`python main.py --loop`) de los niveles 1 al 20 completada correctamente con `--delay 0.3`
(el delay por defecto del código es 0.25: si se pierden teclas, usar 0.3). Reglas confirmadas: pincho de un solo paso,
roca sobre pincho lo desactiva, roca sobre valla abierta permitida, placas no permanentes (una roca las mantiene pulsadas),
una placa abre una sola valla. Nivel 20 (totem, sin diamantes): ver sección propia.

"""
seguro.py - Modo --safe: confirma en pantalla cada paso antes de enviar el siguiente.

No identifica al jugador (seria caro): tras pulsar una flecha compara, en miniaturas grises de
16x16, la casilla de origen y la de destino con como estaban antes de pulsar.
  * Si cambian -> el juego recibio la tecla. Se espera a que la casilla de destino deje de
    cambiar durante `quieto` s (el jugador termino de moverse) y se envia la siguiente tecla.
    No hay retardo fijo: si el juego va rapido, el bot va rapido.
  * Si en `espera_max` s no cambio nada -> la tecla se perdio: se reenvia (hasta `reintentos`).
    Si sigue sin cambiar, se detiene en vez de seguir a ciegas.
Se captura solo el rectangulo del juego (Quartz), cada ~5 ms mientras se espera.
"""
import time

import cv2
import numpy as np

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
UMBRAL_CAMBIO = 10.0   # diferencia media (0-255) para dar por recibida la tecla
UMBRAL_QUIETO = 3.0    # cambio de origen+destino en la ventana `quieto`: por debajo, nada se mueve


class Vigia:
    """Recorta casillas del mapa (coordenadas del layout) en capturas del area del juego."""

    def __init__(self, rect, fila0=2, filas=15, cols=10, capturar=None):
        self.rect = tuple(int(v) for v in rect)
        self.fila0, self.filas, self.cols = fila0, filas, cols
        if capturar is None:
            from captura import capturar_region
            capturar = lambda: capturar_region(self.rect)
        self.capturar = capturar

    def celda(self, img, pos):
        h, w = img.shape[:2]
        ch, cw = h / float(self.filas), w / float(self.cols)
        r, c = pos[0] + self.fila0, pos[1]
        y1, x1 = int(r * ch), int(c * cw)
        roi = img[max(0, y1):int(y1 + ch), max(0, x1):int(x1 + cw)]
        if roi.size == 0:
            return np.zeros((16, 16), np.float32)
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return cv2.resize(g, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)


def _dif(a, b):
    return float(np.mean(np.abs(a - b)))


def jugar_seguro(moves, pos0, vigia, pulsar, hold=0.05, espera_max=0.6, reintentos=2, quieto=0.05,
                 sondeo=0.005, verbose=False, eventos=None):
    """Juega `moves` desde pos0 confirmando cada paso. pulsar(tecla, hold) envia una flecha.
    Devuelve dict(ok, pasos, segundos, reenvios, paso_fallo)."""
    from bot_solver import moves_to_keys
    keys = moves_to_keys(moves)
    eventos = eventos or {}
    pos = pos0
    img = vigia.capturar()
    t0 = time.perf_counter()
    reenvios = 0
    for i, (m, k) in enumerate(zip(moves, keys), 1):
        dr, dc = DIRS[m]
        dst = (pos[0] + dr, pos[1] + dc)
        if verbose:
            extra = eventos.get(i)
            print("paso %d/%d  %-5s -> (fila %d, col %d)%s" % (i, len(keys), k, dst[0], dst[1],
                  ("  <- " + extra) if extra else ""), flush=True)
        ref_o, ref_d = vigia.celda(img, pos), vigia.celda(img, dst)
        pulsar(k, hold)
        t_tecla = time.perf_counter()
        intentos = 0
        while True:
            img = vigia.capturar()
            d_o = _dif(vigia.celda(img, pos), ref_o)
            d_d = _dif(vigia.celda(img, dst), ref_d)
            if max(d_o, d_d) > UMBRAL_CAMBIO:
                break
            if time.perf_counter() - t_tecla > espera_max:
                if intentos >= reintentos:
                    print("PASO %d SIN CONFIRMAR: tras %d reenvios la pantalla no cambia. Me detengo." % (i, intentos))
                    return dict(ok=False, pasos=i - 1, segundos=time.perf_counter() - t0,
                                reenvios=reenvios, paso_fallo=i)
                intentos += 1
                reenvios += 1
                print("  (paso %d: el juego no reacciono en %.1f s, reenvio la tecla %s)" % (i, espera_max, k), flush=True)
                pulsar(k, hold)
                t_tecla = time.perf_counter()
            time.sleep(sondeo)
        if i == len(keys):  # ultimo paso (entra en la salida): basta con saber que llego
            pos = dst
            break
        # la tecla llego: esperar a que el jugador haya entrado en el destino y que origen y destino
        # no cambien durante `quieto` s (se vigilan los dos: al empezar a moverse el destino apenas cambia)
        prev = (vigia.celda(img, pos), vigia.celda(img, dst))
        t_quieto = time.perf_counter()
        while True:
            llego = _dif(prev[1], ref_d) > UMBRAL_CAMBIO
            if llego and time.perf_counter() - t_quieto >= quieto:
                break
            if time.perf_counter() - t_tecla > 3.0:
                break  # algo raro (animacion continua): no bloquear
            time.sleep(sondeo)
            img = vigia.capturar()
            cur = (vigia.celda(img, pos), vigia.celda(img, dst))
            if _dif(cur[0], prev[0]) + _dif(cur[1], prev[1]) > UMBRAL_QUIETO or not llego:
                prev, t_quieto = cur, time.perf_counter()
        pos = dst
    return dict(ok=True, pasos=len(keys), segundos=time.perf_counter() - t0, reenvios=reenvios, paso_fallo=None)

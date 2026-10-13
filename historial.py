"""
historial.py - Historial de intentos del bot (un registro JSON por linea).

Archivo: historial_intentos.jsonl, junto a este modulo. Cada intento guarda el nivel, el
mapa detectado, la solucion usada y si salio bien, para poder ver despues que niveles
funcionan, cuales fallan y en que paso.

    guardar(registro)                    # añade una linea
    preguntar_resultado(n_pasos)         # pregunta en la terminal: -> dict | None
    resumen()                            # imprime una tabla por nivel
"""
import json
import os
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(HERE, "historial_intentos.jsonl")


def version_git():
    """Version del codigo (tag/commit, con -dirty si hay cambios sin guardar) o None."""
    try:
        r = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"], cwd=HERE,
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or None
    except Exception:
        return None


def guardar(registro, archivo=ARCHIVO):
    registro = dict(registro)
    registro.setdefault("fecha", datetime.now().astimezone().isoformat(timespec="seconds"))
    registro.setdefault("version", version_git())
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


def leer(archivo=ARCHIVO):
    out = []
    if not os.path.exists(archivo):
        return out
    with open(archivo, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                out.append(json.loads(linea))
            except ValueError:
                pass  # linea danada: se ignora
    return out


_SI = {"s", "si", "sí", "y", "yes", "1"}
_NO = {"n", "no", "0"}
_NS = {"?", "ns", "no se", "no sé", "nose"}
_SALIR = {"x", "salir", "q"}


def preguntar_resultado(n_pasos, entrada=input):
    """Pregunta si la ejecucion fue correcta.
    Devuelve {"resultado": "ok"|"fallo"|"no_se", "paso_fallo": int|None, "nota": str}
    o None si el usuario elige no guardar (o interrumpe con Ctrl+C / Ctrl+D)."""
    print("\a", end="")
    print("\nHaz clic en esta terminal para responder.")
    try:
        while True:
            r = entrada("¿La ejecución fue correcta?  [s] sí  [n] no  [?] no estoy seguro  [x] no guardar: ").strip().lower()
            if r in _SI:
                resultado = "ok"
                break
            if r in _NO:
                resultado = "fallo"
                break
            if r in _NS:
                resultado = "no_se"
                break
            if r in _SALIR:
                return None
            print("Responde s, n, ? o x.")
        paso = None
        if resultado == "fallo":
            while True:
                p = entrada("¿En qué paso se desvió? (1-%d, ENTER si no lo sabes): " % n_pasos).strip()
                if not p:
                    break
                if p.isdigit() and 1 <= int(p) <= n_pasos:
                    paso = int(p)
                    break
                print("Escribe un número entre 1 y %d, o ENTER." % n_pasos)
        nota = entrada("Nota (opcional, ENTER para omitir): ").strip()
        return {"resultado": resultado, "paso_fallo": paso, "nota": nota}
    except (EOFError, KeyboardInterrupt):
        print("\n(sin respuesta: no se guarda el intento)")
        return None


def preguntar_nivel(entrada=input):
    """Para cuando no se pudo detectar el nivel: devuelve un int o None."""
    try:
        r = entrada("No pude detectar el nivel. ¿Cuál era? (número, ENTER si no lo sabes): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return int(r) if r.isdigit() else None


def resumen(archivo=ARCHIVO):
    datos = leer(archivo)
    if not datos:
        print("Todavía no hay intentos guardados (%s)." % archivo)
        return
    por_nivel = {}
    for d in datos:
        por_nivel.setdefault(d.get("nivel"), []).append(d)
    print("%d intentos en %s\n" % (len(datos), os.path.basename(archivo)))
    print("%-7s %9s %5s %7s %9s  %s" % ("nivel", "intentos", "ok", "fallos", "no sé", "mejor ok (pasos, segundos)"))
    clave = lambda n: (n is None, n if n is not None else 0)
    for n in sorted(por_nivel, key=clave):
        rs = por_nivel[n]
        ok = [r for r in rs if r.get("resultado") == "ok"]
        mejor = min((r.get("pasos") for r in ok if r.get("pasos")), default=None)
        tiempos = [r.get("segundos") for r in ok if r.get("segundos")]
        if mejor is not None and tiempos:
            mejor_t = min((r for r in ok if r.get("segundos")), key=lambda r: r["segundos"])
            mejor = "%s pasos, %.1f s (%.2f s/paso, delay %s)" % (
                mejor, mejor_t["segundos"], mejor_t.get("segundos_por_paso") or 0,
                (mejor_t.get("config") or {}).get("delay", mejor_t.get("delay")))
        print("%-7s %9d %5d %7d %9d  %s" % (
            "?" if n is None else n, len(rs), len(ok),
            sum(r.get("resultado") == "fallo" for r in rs),
            sum(r.get("resultado") == "no_se" for r in rs),
            "-" if mejor is None else mejor))
    fallos = [d for d in datos if d.get("resultado") == "fallo"]
    if fallos:
        print("\nÚltimos fallos:")
        for d in fallos[-5:]:
            print("  %s  nivel %s  paso %s  %s" % (d.get("fecha", "")[:16].replace("T", " "), d.get("nivel"),
                                                  d.get("paso_fallo") or "?", d.get("nota") or ""))

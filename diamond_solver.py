"""
diamond_solver.py - Solucionador optimo de Diamond Rush (Minijuegos).

A* sobre macro-movimientos: caminar sin eventos + UN paso que recoge un
diamante/llave, abre una puerta o empuja una roca. El costo es el numero de
pasos, asi que la solucion es optima en pasos. Heuristica admisible y
consistente: arbol de expansion minima (MST) entre el jugador, los diamantes
pendientes y la salida, midiendo distancias en el mapa relajado (solo paredes).
Si hacen falta solo k diamantes (p. ej. nivel 6: 8 de 10) se usa la distancia
k-esima al jugador como cota.

Reglas (ver plan-solver-diamond-rush.md):
  * Diamante: se recoge al pisarlo.  Salida E: bloqueada hasta tener `needed`.
  * Roca: se empuja si la casilla siguiente esta libre; puede quedar encima de
    un diamante o llave (el objeto sigue debajo). Una roca en un hoyo lo rellena.
  * Llave: maximo 1 en mano. Puerta: se abre gastando la llave y queda abierta.
  * Valla '|': abierta mientras alguna roca este sobre SU placa '_' (o el jugador parado en ella).
    `links` = {(fila,col) de la placa: (fila,col) de la valla}; una placa abre una unica valla.
    Sin `links` (comportamiento antiguo) cualquier placa abre cualquier valla.
  * Pared '#' y lava 'L' bloquean (la roca no rellena la lava).
  * Pincho '^': se puede pisar UNA vez; al salir se levanta y queda como pared.
    (una roca no se puede empujar sobre un pincho)

Uso:
    from diamond_solver import solve_layout
    moves = solve_layout(layout_text, needed=None)   # "RRDDL..." o None
"""
import heapq
import time
from collections import deque

DIRS = (("U", -1, 0), ("D", 1, 0), ("L", 0, -1), ("R", 0, 1))
INF = 10 ** 6
WIN = "WIN"


def _popcount(x):
    return bin(x).count("1")


class Level:
    def __init__(self, grid, needed=None, player_on_plate_opens=True, hand0=0, links=None,
                 rock_over_fence=True, rock_on_spike=True):
        # player_on_plate_opens: el jugador parado sobre una placa tambien abre
        # las vallas (regla asumida por soluciones.md; el nivel 19 la necesita).
        self.pp = player_on_plate_opens
        # rock_over_fence: una roca se puede empujar sobre una valla que esta abierta (hipotesis; nivel 17)
        self.rof = rock_over_fence
        # rock_on_spike (CONFIRMADA en el nivel 10): una roca empujada sobre un pincho lo DESACTIVA y la casilla
        # queda como suelo. smask guarda 2 bits por pincho: 2i = activo y sin pisar, 2i+1 = ya es suelo.
        self.ros = rock_on_spike
        self.hand0 = hand0  # 1 si el jugador ya lleva una llave al empezar
        rows = [r for r in grid.strip("\n").split("\n")]
        self.H = len(rows)
        self.W = len(rows[0])
        if any(len(r) != self.W for r in rows):
            raise ValueError("Todas las filas deben tener el mismo ancho")
        W = self.W
        # una roca puede empezar encima de una placa (la vision solo ve la roca): `links` dice donde
        # hay placa debajo
        rock_plates = {r * W + c for (r, c) in (links or {}) if 0 <= r < self.H and 0 <= c < W and rows[r][c] == "R"}
        self.kind = []
        self.start = None
        rocks0 = []
        self.diamonds, keys, doors, holes, spikes = [], [], [], [], []
        self.exit = None
        plates = []
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                t = r * W + c
                if ch not in "#.PDERO LKG_|S^".replace(" ", ""):
                    raise ValueError("Simbolo desconocido %r en (%d,%d)" % (ch, r, c))
                if ch in "#L":
                    k = "#"
                elif ch in ".SPR":
                    k = "."
                else:
                    k = ch
                if ch == "R" and t in rock_plates:
                    k = "_"
                self.kind.append(k)
                if ch == "P":
                    self.start = t
                elif ch == "R":
                    rocks0.append(t)
                if k == "D":
                    self.diamonds.append(t)
                elif k == "K":
                    keys.append(t)
                elif k == "G":
                    doors.append(t)
                elif k == "O":
                    holes.append(t)
                elif k == "^":
                    spikes.append(t)
                elif k == "E":
                    self.exit = t
                elif k == "_":
                    plates.append(t)
        if self.start is None:
            raise ValueError("El layout no tiene jugador (P)")
        if self.exit is None:
            raise ValueError("El layout no tiene salida (E)")
        self.N = self.H * W
        self.plateset = frozenset(plates)
        self.didx = {t: i for i, t in enumerate(self.diamonds)}
        self.kidx = {t: i for i, t in enumerate(keys)}
        self.gidx = {t: i for i, t in enumerate(doors)}
        self.oidx = {t: i for i, t in enumerate(holes)}
        self.sidx = {t: i for i, t in enumerate(spikes)}
        self.nd = len(self.diamonds)
        self.needed = self.nd if needed is None else min(needed, self.nd)
        self.rocks0 = tuple(sorted(rocks0))
        # vecinos
        fences = [t for t in range(self.N) if self.kind[t] == "|"]
        self.fence_plates = {f: self.plateset for f in fences}
        if links:
            lp = {}
            for (pr, pc), (fr, fc) in links.items():
                pt, ft = pr * W + pc, fr * W + fc
                if self.kind[pt] != "_" or self.kind[ft] != "|":
                    raise ValueError("links: %r no es placa o %r no es valla" % ((pr, pc), (fr, fc)))
                lp.setdefault(ft, set()).add(pt)
            for f in fences:
                self.fence_plates[f] = frozenset(lp.get(f, ()))
        self.nb = []
        self.nbd = []
        for t in range(self.N):
            r, c = divmod(t, W)
            lst, dct = [], {}
            for ch, dr, dc in DIRS:
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.H and 0 <= cc < W:
                    lst.append((ch, rr * W + cc))
                    dct[ch] = rr * W + cc
            self.nb.append(lst)
            self.nbd.append(dct)
        self._build_relaxed()
        self._hc = {}

    # ---------- estado ----------
    def initial(self):
        return (self.start, (1 << self.nd) - 1, self.rocks0,
                (1 << len(self.kidx)) - 1, (1 << len(self.gidx)) - 1, self.hand0, 0,
                sum(1 << (2 * i) for i in range(len(self.sidx))))

    # ---------- mapa relajado y heuristica ----------
    def _build_relaxed(self):
        kind, nb = self.kind, self.nb
        self.DM = [None] * self.N
        for s in range(self.N):
            if kind[s] == "#":
                continue
            d = [INF] * self.N
            d[s] = 0
            q = deque([s])
            while q:
                u = q.popleft()
                for _, v in nb[u]:
                    if kind[v] != "#" and d[v] == INF:
                        d[v] = d[u] + 1
                        q.append(v)
            self.DM[s] = d

    def _mst(self, nodes):
        n = len(nodes)
        if n <= 1:
            return 0
        DM = self.DM
        in_tree = [False] * n
        best = [INF] * n
        best[0] = 0
        total = 0
        for _ in range(n):
            u, bu = -1, INF + 1
            for i in range(n):
                if not in_tree[i] and best[i] < bu:
                    bu, u = best[i], i
            in_tree[u] = True
            total += bu
            du = DM[nodes[u]]
            for i in range(n):
                if not in_tree[i]:
                    d = du[nodes[i]]
                    if d < best[i]:
                        best[i] = d
        return total

    def h(self, st):
        pos, dmask = st[0], st[1]
        key = (pos, dmask)
        v = self._hc.get(key)
        if v is not None:
            return v
        rem = [t for t, i in self.didx.items() if dmask >> i & 1]
        k_rem = self.needed - (self.nd - len(rem))
        DMp = self.DM[pos]
        if k_rem <= 0:
            v = DMp[self.exit]
        elif k_rem == len(rem):
            v = self._mst([pos] + rem + [self.exit])
        else:
            v = sorted(DMp[t] for t in rem)[k_rem - 1]
        self._hc[key] = v
        return v

    # ---------- sucesores (macro-movimientos) ----------
    def successors(self, st):
        pos, dmask, rocks, kmask, gmask, hand, fmask, smask = st
        kind, nb, nbd = self.kind, self.nb, self.nbd
        didx, kidx, gidx, oidx = self.didx, self.kidx, self.gidx, self.oidx
        sidx = self.sidx
        rockset = set(rocks)
        plateset = self.plateset
        fp = self.fence_plates
        open_f = {f for f, ps in fp.items() if any(r in ps for r in rocks)}
        exit_open = (self.nd - _popcount(dmask)) >= self.needed
        dist = {pos: 0}
        par = {pos: None}
        q = deque([pos])
        out = []
        while q:
            u = q.popleft()
            du = dist[u]
            for ch, v in nb[u]:
                if v in dist:
                    continue
                if v in rockset:
                    # empujar la roca de v en la direccion ch
                    t2 = nbd[v].get(ch)
                    if t2 is None or t2 in rockset:
                        continue
                    k2 = kind[t2]
                    nf = fmask
                    fill = False
                    if k2 == "#" or k2 == "E" or (k2 == "^" and not (self.ros and (smask >> (2 * sidx[t2])) & 3)) or (k2 == "|" and not (self.rof and t2 in open_f)):
                        continue
                    if k2 == "G":
                        if gmask >> gidx[t2] & 1:
                            continue
                    elif k2 == "O":
                        if not (fmask >> oidx[t2] & 1):
                            fill = True
                            nf = fmask | (1 << oidx[t2])
                    nsm = smask
                    if k2 == "^" and (smask >> (2 * sidx[t2]) & 1):
                        nsm = (smask & ~(1 << (2 * sidx[t2]))) | (1 << (2 * sidx[t2] + 1))
                    nr = [x for x in rocks if x != v]
                    if not fill:
                        nr.append(t2)
                    nr.sort()
                    nd_, nk, nh = dmask, kmask, hand
                    if kind[v] == "D" and (dmask >> didx[v] & 1):
                        nd_ = dmask & ~(1 << didx[v])
                    elif kind[v] == "K" and (kmask >> kidx[v] & 1) and hand == 0:
                        nk = kmask & ~(1 << kidx[v])
                        nh = 1
                    out.append(((v, nd_, tuple(nr), nk, gmask, nh, nf, nsm), du + 1, u, ch))
                    continue
                k = kind[v]
                if k == "#":
                    continue
                if k == ".":
                    pass
                elif k == "D":
                    if dmask >> didx[v] & 1:
                        out.append(((v, dmask & ~(1 << didx[v]), rocks, kmask, gmask, hand, fmask, smask), du + 1, u, ch))
                        continue
                elif k == "K":
                    if (kmask >> kidx[v] & 1) and hand == 0:
                        out.append(((v, dmask, rocks, kmask & ~(1 << kidx[v]), gmask, 1, fmask, smask), du + 1, u, ch))
                        continue
                elif k == "G":
                    if gmask >> gidx[v] & 1:
                        if hand:
                            out.append(((v, dmask, rocks, kmask, gmask & ~(1 << gidx[v]), 0, fmask, smask), du + 1, u, ch))
                        continue
                elif k == "^":
                    if smask >> (2 * sidx[v] + 1) & 1:
                        pass  # pincho desactivado por una roca: suelo
                    else:
                        if smask >> (2 * sidx[v]) & 1:
                            out.append(((v, dmask, rocks, kmask, gmask, hand, fmask,
                                         smask & ~(1 << (2 * sidx[v]))), du + 1, u, ch))
                        continue
                elif k == "O":
                    if not (fmask >> oidx[v] & 1):
                        continue
                elif k == "|":
                    if v not in open_f and not (self.pp and u in fp[v]):
                        continue
                elif k == "E":
                    if exit_open:
                        out.append((WIN, du + 1, u, ch))
                    continue
                # '_' (placa), 'S' y demas: suelo
                dist[v] = du + 1
                par[v] = (u, ch)
                q.append(v)
        return par, out

    @staticmethod
    def _path(par, u):
        s = []
        while par[u] is not None:
            u, ch = par[u]
            s.append(ch)
        s.reverse()
        return "".join(s)

    # ---------- A* ----------
    def solve(self, max_expansions=4_000_000, time_limit=None, stats=None, weight=1.0):
        # weight > 1: A* ponderado (mas rapido, ruta no necesariamente optima)
        start = self.initial()
        g = {start: 0}
        parent = {start: None}
        heap = [(weight * self.h(start), 0, 0, start)]
        cnt = 0
        expansions = 0
        t0 = time.time()
        while heap:
            f, ng, _, st = heapq.heappop(heap)
            gs = -ng
            if g.get(st, INF) < gs:
                continue
            if st == WIN:
                moves = []
                cur = st
                while parent[cur] is not None:
                    prev, mv = parent[cur]
                    moves.append(mv)
                    cur = prev
                moves.reverse()
                if stats is not None:
                    stats.update(expansions=expansions, states=len(g), seconds=time.time() - t0)
                return "".join(moves)
            expansions += 1
            if expansions > max_expansions:
                break
            if time_limit and (expansions & 1023) == 0 and time.time() - t0 > time_limit:
                break
            par, items = self.successors(st)
            for new, cost, u, ch in items:
                g2 = gs + cost
                if g2 < g.get(new, INF):
                    if new == WIN:
                        hv = 0
                    else:
                        hv = self.h(new)
                        if hv >= INF:
                            continue
                    g[new] = g2
                    parent[new] = (st, self._path(par, u) + ch)
                    cnt += 1
                    heapq.heappush(heap, (g2 + weight * hv, -g2, cnt, new))
        if stats is not None:
            stats.update(expansions=expansions, states=len(g), seconds=time.time() - t0)
        return None


def solve_layout(layout, needed=None, player_on_plate_opens=True, hand0=0, links=None,
                 rock_over_fence=True, rock_on_spike=True, **kw):
    """Devuelve la cadena de movimientos optima (U/D/L/R) o None."""
    return Level(layout, needed, player_on_plate_opens, hand0, links, rock_over_fence, rock_on_spike).solve(**kw)


# ---------------------------------------------------------------------------
# Simulador paso a paso (independiente del A*): sirve para verificar rutas.
# ---------------------------------------------------------------------------
def simulate(layout, moves, needed=None, player_on_plate_opens=True, hand0=0, links=None,
             rock_over_fence=True, rock_on_spike=True):
    """Aplica `moves` y devuelve (gano, mensaje, pasos_usados)."""
    L = Level(layout, needed, player_on_plate_opens, hand0, links, rock_over_fence, rock_on_spike)
    pos, dmask, rocks, kmask, gmask, hand, fmask, smask = L.initial()
    rocks = set(rocks)
    for i, m in enumerate(moves):
        t = L.nbd[pos].get(m)
        if t is None:
            return False, "paso %d: fuera del mapa" % i, i
        if t in rocks:
            t2 = L.nbd[t].get(m)
            if t2 is None or t2 in rocks:
                return False, "paso %d: roca atascada" % i, i
            k2 = L.kind[t2]
            if k2 == "|" and L.rof and any(q in rocks for q in L.fence_plates[t2]):
                pass  # roca sobre valla abierta (hipotesis)
            elif k2 == "^" and L.ros and (smask >> (2 * L.sidx[t2])) & 3:
                if smask >> (2 * L.sidx[t2]) & 1:
                    smask = (smask & ~(1 << (2 * L.sidx[t2]))) | (1 << (2 * L.sidx[t2] + 1))
            elif k2 in "#E|^":
                return False, "paso %d: roca bloqueada por %s" % (i, k2), i
            rocks.discard(t)
            if k2 == "G":
                if gmask >> L.gidx[t2] & 1:
                    rocks.add(t)
                    return False, "paso %d: roca contra puerta cerrada" % i, i
                rocks.add(t2)
            elif k2 == "O":
                if fmask >> L.oidx[t2] & 1:
                    rocks.add(t2)
                else:
                    fmask |= 1 << L.oidx[t2]
            else:
                rocks.add(t2)
            pos = t
            if L.kind[t] == "D" and (dmask >> L.didx[t] & 1):
                dmask &= ~(1 << L.didx[t])
            elif L.kind[t] == "K" and (kmask >> L.kidx[t] & 1) and hand == 0:
                kmask &= ~(1 << L.kidx[t])
                hand = 1
            continue
        k = L.kind[t]
        if k == "#":
            return False, "paso %d: pared" % i, i
        if k == "D" and (dmask >> L.didx[t] & 1):
            dmask &= ~(1 << L.didx[t])
        elif k == "K" and (kmask >> L.kidx[t] & 1) and hand == 0:
            kmask &= ~(1 << L.kidx[t])
            hand = 1
        elif k == "G" and (gmask >> L.gidx[t] & 1):
            if not hand:
                return False, "paso %d: puerta sin llave" % i, i
            gmask &= ~(1 << L.gidx[t])
            hand = 0
        elif k == "^":
            if smask >> (2 * L.sidx[t] + 1) & 1:
                pass  # pincho desactivado por una roca
            elif not (smask >> (2 * L.sidx[t]) & 1):
                return False, "paso %d: pincho ya levantado" % i, i
            else:
                smask &= ~(1 << (2 * L.sidx[t]))
        elif k == "O" and not (fmask >> L.oidx[t] & 1):
            return False, "paso %d: hoyo" % i, i
        elif k == "|" and not (any(p in rocks for p in L.fence_plates[t])
                               or (L.pp and pos in L.fence_plates[t])):
            return False, "paso %d: valla cerrada" % i, i
        elif k == "E":
            if L.nd - _popcount(dmask) >= L.needed:
                return True, "gana", i + 1
            return False, "paso %d: salida bloqueada" % i, i
        pos = t
    return False, "termino sin llegar a la salida", len(moves)

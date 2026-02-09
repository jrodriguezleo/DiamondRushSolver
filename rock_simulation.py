
import copy
from game_action import GameAction
from a_star import AStar
from collections import deque

#TODO fix this rock simulation.
# Está devolviendo un path incorrecto
# Es posible que la logica esté bien pero esté mal el como devuelve el camino correcto

class RockSimulation:
    def __init__(self, grid, player_pos, rock_pos, target_pos):
        self.grid = copy.deepcopy(grid)  # Esta grilla estara actualizada al finalizar la simulacion
        self.player_pos = player_pos
        self.path = []                # Path completo seguido por el jugador
        self.directions = []          # Direcciones seguidas por el jugador
        self.rock_start = rock_pos
        self.target_pos = target_pos
        self.action_history = []  # Acciones tomadas durante la simulacion
        self.action = "push_rock"

    def is_in_bounds(self, pos):
        r, c = pos
        return 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0])
    
    def is_walkable(self, pos):
        r, c = pos
        if not self.is_in_bounds(pos):
            return False
        cell = self.grid[r][c]
        return cell is not None and cell.walkable
    
    def is_empty(self, pos):
        r, c = pos
        if not self.is_in_bounds(pos):
            return False
        cell = self.grid[r][c]
        return cell is not None and cell.cell_type in ["terrain", "fall", "push-button"]
    
    def update_grid(self, rock_pos):
        r, c = rock_pos
        # Actualizamos la celda de la roca a "rock-in-fall" si es que esta en una posicion de caida
        if self.grid[r][c].cell_type == "fall":
            self.grid[r][c].cell_type = "rock-in-fall"
            self.grid[r][c].weight = 1
            self.grid[r][c].walkable = True
        # Si la roca esta en un boton, se cambia el tipo de celda a "rock-in-button"
        elif self.grid[r][c].cell_type == "button":
            self.grid[r][c].cell_type = "rock-in-button"
            self.grid[r][c].weight = 200
        # Si la roca esta en una posicion de terreno, se cambia el tipo de celda a "rock"
        elif self.grid[r][c].cell_type == "terrain":
            self.grid[r][c].cell_type = "rock"
            self.grid[r][c].weight = 100000 - 100
        
        # Actualizamos la celda inicial de la roca volviendola a terreno
        start_r, start_c = self.rock_start
        if self.grid[start_r][start_c].cell_type == "rock":
            self.grid[start_r][start_c].cell_type = "terrain"
            self.grid[start_r][start_c].weight = 1

    def simulate(self):
        visited : list = []
        queue = deque()
        
        # Iniciamos desde la posición actual de la roca
        queue.append((self.rock_start, self.player_pos, []))
        while queue:
            rock_pos, player_pos, path = queue.popleft()
            
            if [rock_pos[0],rock_pos[1]] == self.target_pos:
                self.player_pos = player_pos
                self.path = path
                self.action_history.append(GameAction("push_rock", coordinates=rock_pos, path=self.directions))
                self.rock_final = rock_pos
                self.update_grid(rock_pos)
                return True

            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                push_from = (rock_pos[0] - dx, rock_pos[1] - dy)
                new_rock_pos = (rock_pos[0] + dx, rock_pos[1] + dy)

                # Si ya visitamos ese estado, ignoramos
                state_key = (rock_pos, push_from, player_pos)
                if state_key in visited:
                    continue
                visited.append(state_key)

                if not self.is_in_bounds(new_rock_pos):
                    continue

                if self.is_walkable(push_from) and self.is_empty(new_rock_pos):
                    # Intentamos encontrar path del jugador hasta push_from
                    astar = AStar(start=player_pos, goal=push_from, grid=self.grid)
                    astar.search()
                    if astar.total_weight == float('inf'):
                        continue
                    # Si el A* encontró un camino, lo usamos
                    push_path = astar.path
                    push_directions = astar.directions
                    if push_path:
                        new_path = path + push_path + [rock_pos]
                        self.directions += push_directions
                        queue.append((new_rock_pos, rock_pos, new_path))  # Ahora el jugador está donde estaba la roca
                    # Revisamos si el push from es un spike, en caso de ser cierto se actualiza la grilla con el spike up
                    if self.grid[push_from[0]][push_from[1]].cell_type == "spike":
                        self.grid[push_from[0]][push_from[1]].cell_type = "spike-up"
                        self.grid[push_from[0]][push_from[1]].weight = 100000

        return False
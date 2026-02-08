
from collections import deque
import copy
from typing import List, Tuple
from cell import Cell
from game_action import GameAction
from a_star import AStar
from rock_simulation import RockSimulation


class GameState:
    # Esta clase se encarga de guardar el estado del juego junto ccon la lista de acciones que lo llevaron a ese estado
    # Se considera un estado ganador si el jugador llega a la escalera abierta. (el agente revisa esta condicion para romper la simulacion)
    # con player pos y ladder pos
    # Las acciones son ir a x,y o empujar a alguna direccion
    def __init__(self, grid: List[List[Cell | None]], player_pos: tuple[int, int], game_state: int, action_history: list[GameAction] = [], player_has_key: bool = False):
        self.grid = grid
        self.player_pos = player_pos
        self.player_has_key = player_has_key
        self.game_state = game_state
        self.action_history = action_history
        self.check_objects_in_grid()
        # Las acciones van en orden de peso
        self.actions = ["go_ladder", "get_diamond" ,"get_key", "open_door" , "push_rock","go_spike" ]
        self.alternative_stack: list[tuple[str, tuple[int, int], list]] = []  # Lista de tuplas (action_type, coordinates, path)
    
    def check_objects_in_grid(self):
        doorExists, keyExists, diamondExists, rockExists = False, False, False, False
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "door":
                        doorExists = True
                    elif cell.cell_type == "key":
                        keyExists = True
                    elif cell.cell_type == "diamond":
                        diamondExists = True
                    elif cell.cell_type == "rock":
                        rockExists = True
        self.doorExist, self.keyExist, self.diamondExist, self.rockExist = doorExists, keyExists, diamondExists, rockExists

    def find_nearest_diamond(self):
        # Esta funcion se encarga de encontrar el diamante mas cercano al jugador, si el peso excede un umbral
        # o no hay diamantes o vecinos caminables, entonces no se realiza esta accion
        # Se usa el algoritmo A* para encontrar el camino mas corto entre el jugador y el diamante
        # Debe decir si se pasa encima de un spike (o tomar el spike como otra accion)
        best = None
        best_score = 100000
        path = None
        player_position = self.player_pos
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "diamond":
                        Astar = AStar(start = player_position, 
                                    goal = cell.coordinates,
                                    grid = self.grid)
                        Astar.search() 
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if Astar.total_weight < best_score:
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def go_ladder(self):
        best = None
        best_score = 100000
        path = None
        player_position = self.player_pos
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "ladder" or cell.cell_type == "ladder-open":
                        Astar = AStar(start = player_position, 
                                    goal = cell.coordinates,
                                    grid = self.grid)
                        Astar.search() 
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if Astar.total_weight < best_score:
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def find_nearest_key(self):
        best = None
        best_score = 100000
        path = None
        player_position = self.player_pos
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "key":
                        Astar = AStar(start = player_position, 
                                    goal = cell.coordinates,
                                    grid = self.grid)
                        Astar.search() 
                        # Si el peso es el minimo, actualizar mejor, si es inwalkeable, none
                        if Astar.total_weight < best_score:
                            best_score = Astar.total_weight
                            best = cell
                            path = Astar.directions
        return best, path

    def get_possible_spikes(self) -> List[Tuple[int, int]]:
        possible_spikes = []
        visited : list = []
        queue = deque()
        queue.append((self.player_pos, []))  # (posición actual, lista de spikes vistos)

        while queue:
            current_pos, spikes_seen = queue.popleft()
            r, c = current_pos
            current_cell = self.grid[r][c]

            if current_pos in visited:
                continue
            visited.append(current_pos)

            # Si llegamos a un spike y no hemos visto otros antes, es válido
            if current_cell.cell_type == "spike":
                if len(spikes_seen) <= 1:
                    possible_spikes.append(current_pos)
                continue  # no seguimos más allá del spike

            for neighbor in [current_cell.neighbor_up, current_cell.neighbor_down,
                            current_cell.neighbor_left, current_cell.neighbor_right]:
                if neighbor and neighbor.walkable:
                    new_pos = neighbor.coordinates
                    new_spikes = spikes_seen[:]
                    if neighbor.cell_type == "spike":
                        new_spikes.append(new_pos)
                    queue.append((new_pos, new_spikes))

        return possible_spikes
    
    def get_possible_doors(self) -> List[Tuple[int, int]]:
        possible_spikes = []
        visited : list = []
        queue = deque()
        queue.append((self.player_pos, []))  # (posición actual, lista de spikes vistos)

        while queue:
            current_pos, spikes_seen = queue.popleft()
            r, c = current_pos
            current_cell = self.grid[r][c]

            if current_pos in visited:
                continue
            visited.append(current_pos)

            # Si llegamos a un spike y no hemos visto otros antes, es válido
            if current_cell.cell_type == "door":
                if len(spikes_seen) <= 1:
                    possible_spikes.append(current_pos)
                continue  # no seguimos más allá del spike

            for neighbor in [current_cell.neighbor_up, current_cell.neighbor_down,
                            current_cell.neighbor_left, current_cell.neighbor_right]:
                if neighbor and neighbor.walkable:
                    new_pos = neighbor.coordinates
                    new_spikes = spikes_seen[:]
                    if neighbor.cell_type == "door":
                        new_spikes.append(new_pos)
                    queue.append((new_pos, new_spikes))

        return possible_spikes
    
    def get_rock_simulations(self) -> List[RockSimulation]:
        targets = []
        # Encontrar falls o buttons
        for row in self.grid:
            for cell in row:
                if cell is not None and (cell.cell_type == "fall" or cell.cell_type == "button"):
                    targets.append(cell.coordinates)
        simulations = []

        rocks = []
        # Encontrar rocas
        for row in self.grid:
            for cell in row:
                if cell is not None and cell.cell_type == "rock":
                    rocks.append(cell.coordinates)

        for rock in rocks:
            # Para cada objetivo se hace una simulacion y se poda si es imposible
            for t in targets:
                rock_simulation : RockSimulation = RockSimulation(grid=self.grid, player_pos=self.player_pos, 
                                                rock_pos=rock, target_pos=t)
                
                if rock_simulation.simulate():
                    # Si la simulacion es valida se agrega a la lista de simulaciones
                    simulations.append(rock_simulation)
        
        return simulations        

    def get_next_action(self):
        # Primero intentamos las alternativas guardadas (backtracking)
        if self.alternative_stack:
            alt_action, coords, path = self.alternative_stack.pop()
            return GameAction(alt_action, coordinates=coords, path=path)

        # Si no hay alternativas, seguimos con las acciones normales
        while len(self.actions) > 0:
            next_action = self.actions.pop(0)
            match next_action:
                case "get_key":
                    if self.keyExist and not self.player_has_key:
                        nearest, path = self.find_nearest_key()
                        if nearest is not None:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)
                
                case "push_rock":
                    if self.rockExist:
                        simulations = self.get_rock_simulations()
                        if simulations:
                            best : RockSimulation = simulations.pop(0)
                            for alt in simulations:
                                self.alternative_stack.append(("push_rock", alt))
                            return best

                case "open_door":
                    if self.doorExist and self.player_has_key:
                        spike_coords = self.get_possible_doors()
                        best = None
                        best_score = 100000
                        best_path = None
                        alternatives = []
                        for coord in spike_coords:
                            Astar = AStar(start=self.player_pos, goal=coord, grid=self.grid)
                            Astar.search()
                            if Astar.total_weight < best_score:
                                if best != None:
                                    alternatives.append((best, best_path))  # Guardar la anterior mejor como alternativa
                                best_score = Astar.total_weight
                                best = coord
                                best_path = Astar.directions
                            else:
                                if Astar.total_weight < 100000:
                                    alternatives.append((coord, Astar.directions))
                        for alt in alternatives:
                            self.alternative_stack.append(("open_door", alt[0], alt[1]))
                        if best is not None:
                            return GameAction("open_door", coordinates=best, path=best_path)

                case "get_diamond":
                    if self.diamondExist:
                        nearest, path = self.find_nearest_diamond()
                        if nearest is not None:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)
                case "go_ladder":
                    if not self.diamondExist:
                        nearest, path = self.go_ladder()
                        if nearest is not None:
                            return GameAction(next_action, coordinates=nearest.coordinates, path=path)
                case "go_spike":
                    spike_coords = self.get_possible_spikes()
                    best = None
                    best_score = 100000
                    best_path = None
                    alternatives = []
                    for coord in spike_coords:
                        Astar = AStar(start=self.player_pos, goal=coord, grid=self.grid)
                        Astar.search()
                        if Astar.total_weight < best_score:
                            if best != None:
                                alternatives.append((best, best_path))  # Guardar la anterior mejor como alternativa
                            best_score = Astar.total_weight
                            best = coord
                            best_path = Astar.directions
                        else:
                            if Astar.total_weight < 100000:
                                alternatives.append((coord, Astar.directions))
                    for alt in alternatives:
                        self.alternative_stack.append(("go_spike", alt[0], alt[1]))
                    if best is not None:
                        return GameAction("go_spike", coordinates=best, path=best_path)

            # Si esta acción no produjo una acción válida, sigue con la siguiente
        return GameAction("None", [0, 0], path=[])




    def clone(self):
        grid_clone = copy.deepcopy(self.grid)
        player_pos_clone = copy.deepcopy(self.player_pos)
        game_state_clone = self.game_state  # int, no necesita deepcopy
        actions_clone = copy.deepcopy(self.action_history)
        player_key = self.player_has_key

        return GameState(grid_clone, player_pos_clone, game_state_clone, actions_clone, player_has_key = player_key)


    def __repr__(self):
        return f"GameState({self.grid}, {self.player_pos}, {self.game_state})"

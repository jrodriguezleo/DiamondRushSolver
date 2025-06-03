# COMMANDS TO INSTALL DEPENDENCIES
# pip install opencv-python
# pip install pytautogui
# pip install scikit-image  -> usado en skimage.metrics
# pip3 install pyKey

from contextlib import nullcontext
from itertools import count
import re
import cv2
import numpy as np
import copy
from collections import deque
import pyautogui
from typing import Optional, Tuple, Dict, List


from skimage.metrics import structural_similarity as ssim
from pyKey import pressKey, releaseKey, press, sendSequence, showKeys

# TODO crear acciones posibles en game state y ponerles peso
# TODO poder simular acciones del juego de forma eficiente (no simular cada paso del pj, solo acciones en el mundo relevantes)
# TODO crear la funcion que permita simular el juego
# TODO recortar assets en resolucion de portatil 1366x768

ROW = 0 
COL = 1

# TODO mirar los pesos de cada celda para ver si funciona bien el A*
class Cell:
    def __init__(self, coordinates: Tuple[int,int], cell_type):
        self.coordinates = coordinates
        self.cell_type = cell_type
        self.neighbor_up = None
        self.neighbor_down = None
        self.neighbor_left = None
        self.neighbor_right = None
        self.weight = 1
        self.walkable = True

        # De acuerdo al tipo de celda ya se pone un primer peso y si se puede caminar encima de el
        match cell_type:
            case "terrain":
                self.walkable = True
                self.weight = 2
            case "spike":
                self.walkable = True
                self.weight = 10
            case "diamond":
                self.walkable = True
                self.weight = 3
            case "key":
                self.walkable = True
                self.weight = 4
            case "ladder-open":
                self.walkable = True
                self.weight = 1
            case "rock-in-fall":
                self.walkable = True
                self.weight = 2
            case "push-button":
                self.walkable = True
                self.weight = 2
            case "door":
                self.walkable = False
                self.weight = 100000
            case "rock":
                self.walkable = False
                self.weight = 100000
            case "fall":
                self.walkable = False
                self.weight = 100000
            case "metal-door":
                self.walkable = False
                self.weight = 100000
            case "ladder":
                self.walkable = False
                self.weight = 100000
            case "spike-up":
                self.walkable = False
                self.weight = 100000

    def set_neighbors(self, neighbors):
        self.neighbor_up = None
        self.neighbor_down = None
        self.neighbor_left = None
        self.neighbor_right = None

        r, c = self.coordinates
        for neighbor in neighbors:
            if neighbor != None:
                nr, nc = neighbor.coordinates
                if nr == r - 1 and nc == c:
                    self.neighbor_up = neighbor
                elif nr == r + 1 and nc == c:
                    self.neighbor_down = neighbor
                elif nr == r and nc == c - 1:
                    self.neighbor_left = neighbor
                elif nr == r and nc == c + 1:
                    self.neighbor_right = neighbor

    def __repr__(self):
        return f"Cell({self.coordinates[ROW]}, {self.coordinates[COL]}, {self.cell_type})"

class AStar:
    def __init__(self, start: tuple[int, int], goal: tuple[int, int], grid: list[list['Cell']]):
        self.start = start
        self.goal = goal
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.open_set = [start]
        self.closed_set = []
        self.g_score = [[float('inf') for _ in range(self.cols)] for _ in range(self.rows)]
        self.f_score = [[float('inf') for _ in range(self.cols)] for _ in range(self.rows)]
        self.came_from = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.total_weight = float('inf')
        self.directions = []
        self.path = []

    def heuristic(self, a, b) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def reconstruct_path(self, current):
        total_path = [current]
        while self.came_from[current[0]][current[1]] is not None:
            current = self.came_from[current[0]][current[1]]
            total_path.append(current)
        return total_path[::-1]

    def path_to_directions(self, path: list[tuple[int, int]]) -> list[str]:
        directions = []
        for i in range(1, len(path)):
            r1, c1 = path[i - 1]
            r2, c2 = path[i]
            if r2 < r1: directions.append("up")
            elif r2 > r1: directions.append("down")
            elif c2 < c1: directions.append("left")
            elif c2 > c1: directions.append("right")
        return directions

    def get_neighbors(self, node):
        row, col = node
        neighbors = []
        cell : Cell = self.grid[row][col]
        up : Cell = cell.neighbor_up
        down : Cell = cell.neighbor_down
        left : Cell = cell.neighbor_left
        right : Cell = cell.neighbor_right
        
        if up is not None and cell.walkable:
            neighbors.append(up.coordinates)
        if down is not None and cell.walkable:
            neighbors.append(down.coordinates)
        if left is not None and cell.walkable:
            neighbors.append(left.coordinates)
        if right is not None and cell.walkable:
            neighbors.append(right.coordinates)
        
        return neighbors

    def search(self):
        self.g_score[self.start[0]][self.start[1]] = 0
        self.f_score[self.start[0]][self.start[1]] = self.heuristic(self.start, self.goal)

        while self.open_set:
            current = min(self.open_set, key=lambda x: self.f_score[x[0]][x[1]])

            if current[0] == self.goal[0] and current[1] == self.goal[1]:
                self.path = self.reconstruct_path(current)
                self.total_weight = self.g_score[current[0]][current[1]]
                self.directions = self.path_to_directions(self.path)
                return {
                    "path": self.path,
                    "total_weight": self.total_weight,
                    "directions": self.directions
                }

            self.open_set.remove(current)
            self.closed_set.append(current)

            for neighbor in self.get_neighbors(current):
                if neighbor in self.closed_set:
                    continue

                tentative_g = self.g_score[current[0]][current[1]] + self.grid[neighbor[0]][neighbor[1]].weight

                if neighbor not in self.open_set:
                    self.open_set.append(neighbor)
                elif tentative_g >= self.g_score[neighbor[0]][neighbor[1]]:
                    continue
                
                self.came_from[neighbor[0]][neighbor[1]] = current
                self.g_score[neighbor[0]][neighbor[1]] = tentative_g
                self.f_score[neighbor[0]][neighbor[1]] = tentative_g + self.heuristic(neighbor, self.goal)

        return None


class GameAction:
    # Esta clase se encarga de guardar las posibles acciones del juego. Basicamente es para que se pueda
    # leer humanamente esto, ya que al final se traduce como moverse a x,y o empujar a alguna direccion
    def __init__(self, action: str, coordinates: tuple[int, int] = None, path : list = []):
        self.action = action
        self.coordinates = coordinates
        # El path es el camino hallado por A* para llegar a la celda
        self.path = path
    
    def get_readable(self):
        return self.action + " en " + str(self.coordinates) + " camino "  + str(self.path)

class GameState:
    # Esta clase se encarga de guardar el estado del juego junto ccon la lista de acciones que lo llevaron a ese estado
    # Se considera un estado ganador si el jugador llega a la escalera abierta. (el agente revisa esta condicion para romper la simulacion)
    # con player pos y ladder pos
    # Las acciones son ir a x,y o empujar a alguna direccion
    def __init__(self, grid: List[List[Cell | None]], player_pos: tuple[int, int], game_state: int, action_history: list[GameAction] = []):
        self.grid = grid
        self.player_pos = player_pos
        self.game_state = game_state
        self.action_history = action_history
        self.check_objects_in_grid()
        # Las acciones van en orden de peso
        self.actions = ["go_ladder","get_diamond", "get_key" ]

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
        best_score = float('inf')
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
        best_score = float('inf')
        path = None
        player_position = self.player_pos
        for row in self.grid:
            for cell in row:
                if cell != None:
                    if cell.cell_type == "ladder":
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

    def find_nearest_key():
        #TODO
        # Esta funcion se encarga de encontrar la llave mas cercana al jugador, si el peso excede un umbral
        # o no hay llaves o vecinos caminables, entonces no se realiza esta accion
        # Se usa el algoritmo A* para encontrar el camino mas corto entre el jugador y la llave
        pass

    def find_nearest_door():
        #TODO
        # la accion de ir a una puerta deberia tener mas peso si se tiene una llave y menos peso en caso de que no.
        # Esta funcion se encarga de encontrar la puerta mas cercana al jugador, si el peso excede un umbral
        # o no hay puertas o vecinos caminables, entonces no se realiza esta accion
        # Se usa el algoritmo A* para encontrar el camino mas corto entre el jugador y la puerta
        pass

    def get_next_action(self):
        if len(self.actions) > 0:
            next_action = self.actions.pop(0)
        else:
            return GameAction("None",[0,0], path=[])
        while next_action != None:
            match next_action:
                case "get_diamond":
                    if self.diamondExist:
                        nearest, path = self.find_nearest_diamond()
                        if nearest != None:
                            # Devuelve la accion mas coordenada donde acaba el player
                            return GameAction(next_action, coordinates = nearest.coordinates,
                                              path = path)
                case "go_ladder":
                    if not self.diamondExist:
                        nearest, path = self.go_ladder()
                        if nearest != None:
                            # Devuelve la accion mas coordenada donde acaba el player
                            return GameAction(next_action, coordinates = nearest.coordinates,
                                              path = path)
            # Si la accion anterior se intento pero no hubo posibilidad, busca la siguiente
            if len(self.actions)>0:
                next_action = self.actions.pop(0)
            else:
                return GameAction("None",[0,0], path=[])



    def clone(self):
        grid_clone = copy.deepcopy(self.grid)
        player_pos_clone = copy.deepcopy(self.player_pos)
        game_state_clone = self.game_state  # int, no necesita deepcopy
        actions_clone = copy.deepcopy(self.action_history)

        return GameState(grid_clone, player_pos_clone, game_state_clone, actions_clone)


    def __repr__(self):
        return f"GameState({self.grid}, {self.player_pos}, {self.game_state})"

class KeyboardSimulator:
    # Esta clase se encarga de simular el teclado para enviar acciones al juego
    def __init__(self, game_state: GameState):
        self.actions = game_state.action_history
    
    def execute_actions(self):
        total_path = []
        # Ejecutar las acciones en la lista de acciones
        for action in self.actions:
            for th in action.path:
                total_path.append(th)
        # Limpiar la lista de acciones
        self.actions = []
        print("Lista completa de pasos a seguir")
        print(total_path)
        for step in total_path:
            # Simular el movimiento en el juego
            self.simulate_move(step)
            # Esperar un tiempo para que el juego procese el movimiento
            pyautogui.sleep(0.5)
    
    # Dado que cada accion es un ir a x,y o empujar a alguna direccion, se debe hacer un A* para encontrar el camino
    # luego simular cada movimiento del A * en el juego
    def execute_action(self, action: GameAction):
        path = action.path
        # Simular el movimiento en el juego
        for step in path:
            # Simular el movimiento en el juego
            self.simulate_move(step)
            # Esperar un tiempo para que el juego procese el movimiento
            pyautogui.sleep(1.5)

    def simulate_move(self, step: str):
        # Simular el movimiento en el juego
        # Esto se hace enviando las teclas de movimiento al juego
        # Se puede usar pyautogui o pynput para simular el teclado
        if step == "up":
            press("UP",0.2)
        elif step == "down":
            press("DOWN",0.2)
        elif step == "left":
            press("LEFT",0.2)
        elif step == "right":
            press("RIGHT",0.2)

class SmartAgent:
    # El agente define la estrategia a seguir para resolver el juego
    def __init__(self, first_grid : List[List[Cell | None]]):
        for row in range(0,len(first_grid)):
            for col in range(0,len(first_grid[row])):
                if first_grid[row][col] != None and first_grid[row][col].cell_type=="player":
                    player_pos = [row, col]
        game_state = GameState(first_grid, player_pos, 0, [])
        self.game_state = game_state
        

    def simulate(self):
        # Esta funcion se encarga de simular el juego con un loop
        # Se devuelve el estado del juego al lograr la meta
        # En cada paso se guarda la accion tomaada por cada estado de juego
        # Se tiene una pila de acciones en orden para ir de forma greedy a la solucion pero si no se puede hacer la accion
        # se hace la siguiente y asi, si no hay ninguna accion se considera unn camino bloqueado y se devuelve hasta el ultimo estado viable
        # Retorna el game state donde se gana junto con sus acciones

        state_stack : deque = []
        simulated_game_state : GameState = self.game_state
        simulated_action : GameAction = simulated_game_state.get_next_action()
        while True:
            match simulated_action.action:
                case "get_diamond":
                    # Mover pj al diamante, quitar diamante de la grilla.
                    # Solo si no pasó por spikes
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    # TODO  # Puede que haga falta crear uno de personaje in spike.. o manejar el player pos, sin ponerll como cell.
                    # Se borra el diamante y se cambia a terrain
                    new_terrain = Cell(
                        coordinates=simulated_action.coordinates, 
                        cell_type="terrain"
                    )

                    # Se colocan sus vecinos de nuevo manualmente
                    r, c = simulated_action.coordinates
                    neighbors = []
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                            neighbors.append(next_state.grid[nr][nc])
                    new_terrain.set_neighbors(neighbors)

                    # Se coloca la nueva celda en la grilla
                    next_state.grid[r][c] = new_terrain

                    # Se borra el personaje y se cambia a terrain
                    pr, pc = simulated_game_state.player_pos
                    player_replaced = Cell(
                        coordinates=simulated_game_state.player_pos, 
                        cell_type="terrain"
                    )

                    # Se colocan denuevo sus vecinos
                    player_neighbors = []
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = pr + dr, pc + dc
                        if 0 <= nr < len(next_state.grid) and 0 <= nc < len(next_state.grid[0]):
                            player_neighbors.append(next_state.grid[nr][nc])
                    player_replaced.set_neighbors(player_neighbors)

                    # Se actualiza en la grilla
                    next_state.grid[pr][pc] = player_replaced

                    # Se actualiza player pos
                    next_state.player_pos = simulated_action.coordinates

                    simulated_game_state = next_state
                    
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    # Actualizar lo que hay en exists
                    simulated_game_state.check_objects_in_grid()

                    state_stack.append(next_state)
                    print("Llego a nuevo estado get diamond")
                case "go_ladder":
                    next_state : GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    simulated_game_state = next_state
                    # Añadir accion anterior
                    simulated_game_state.action_history.append(simulated_action)
                    state_stack.append(next_state)
                    break
                case "None":
                    if len(state_stack) > 0:
                        simulated_game_state = state_stack.pop()
                        print("Me devolvi un estado")
                    else:
                        print("No hay mas game state, no encontre la solucion")
                        break
            simulated_action : GameAction = simulated_game_state.get_next_action()
        print("Se encontró simulacion hasta go ladder")
        return simulated_game_state

class DiamondRushVision:
    def __init__(self):
        self.templates_raw = self.load_templates()
        self.contours_spike = None
        self.contours_diamond = None
        self.contours_rock = None
        self.contours_key = None
        self.contours_door = None
        self.contours_fall = None
        self.game_rectangle = None
        self.cell_width = None
        self.cell_height = None
        
    def read_screen_debug(self, path: str) -> np.ndarray:
        """Read an image from file for debugging purposes."""
        return cv2.imread(path, cv2.IMREAD_COLOR)
    
    def read_screen_realtime(self) -> np.ndarray:
        """Capture the current screen in real-time."""
        img = pyautogui.screenshot()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    def get_game_area(self, img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect the game area by finding two large contours with specific colors.
        Returns the rectangle coordinates (x1, y1, x2, y2) of the game area.
        """
        # Target color range for game borders (BGR format)
        target_color = (24, 21, 13)  # Lower bound
        target_color2 = (32, 27, 22)  # Upper bound
        
        # Create color range mask
        lower_bound = np.array(target_color)
        upper_bound = np.array(target_color2)
        mask = cv2.inRange(img, lower_bound, upper_bound)
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Keep only the two largest contours
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]
        
        if len(contours) >= 2:
            # Determine left and right contours
            x1 = cv2.boundingRect(contours[0])
            x2 = cv2.boundingRect(contours[1])
            left_contour = contours[0] if x1 < x2 else contours[1]
            right_contour = contours[1] if x1 < x2 else contours[0]
            
            # Get bounding rectangles
            x1, y1, w1, h1 = cv2.boundingRect(left_contour)
            x2, y2, w2, h2 = cv2.boundingRect(right_contour)
            
            # Calculate area dimensions
            area = (x2 - x1 - w1, h1)
            
            if area[0] < 100 or area[1] < 100:
                print("Game area is too small to process.")
                return None
            
            # Return game rectangle coordinates
            game_rectangle = (x1 + w1, y1, x2, y2 + h2)
            print("Game area detected:", game_rectangle)
            return game_rectangle
        
        print("Not enough contours found to determine game area.")
        return None
    
    def create_grid(self, img_res: np.ndarray, game_rectangle: Tuple[int, int, int, int], 
                   rows: int, cols: int) -> Tuple[float, float]:
        """
        Draw a grid on the image and calculate cell dimensions.
        Returns the width and height of each cell.
        """
        area_width = game_rectangle[2] - game_rectangle[0]
        area_height = game_rectangle[3] - game_rectangle[1]
        cell_width = area_width / cols
        cell_height = area_height / rows
        first_x, first_y = game_rectangle[0], game_rectangle[1]
        
        print(f"Game area: {area_width}x{area_height}")
        print(f"Cell size: {cell_width}x{cell_height}")
        
        # Draw vertical grid lines
        for i in range(cols + 1):
            x = round(first_x + i * cell_width)
            pt1 = (x, round(first_y))
            pt2 = (x, round(first_y + rows * cell_height))
            cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)
        
        # Draw horizontal grid lines
        for j in range(rows + 1):
            y = round(first_y + j * cell_height)
            pt1 = (round(first_x), y)
            pt2 = (round(first_x + cols * cell_width), y)
            cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)
        
        return cell_width, cell_height
    
    def resize_templates(self, cell_width: float, cell_height: float) -> None:
        """Resize all templates to match the cell dimensions."""
        for name, template in self.templates_raw.items():
            self.templates_raw[name] = cv2.resize(
                template, 
                (int(cell_width), int(cell_height)), 
                interpolation=cv2.INTER_NEAREST
            )
    
    def _find_spike_contours(self) -> List:
        """Find and return contours for spike objects."""
        template = self.templates_raw["spike"]
        lower_bound = np.array([0, 0, 0])
        upper_bound = np.array([20, 20, 20])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    def _find_diamond_contours(self) -> List:
        """Find and return contours for diamond objects."""
        template = self.templates_raw["diamond"]
        lower_bound = np.array([90, 70, 20])
        upper_bound = np.array([235, 235, 235])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def _find_rock_contours(self) -> List:
        """Find and return contours for rock objects."""
        template = self.templates_raw["rock"]
        lower_bound = np.array([100, 100, 100])
        upper_bound = np.array([255, 255, 255])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sorted(contours, key=cv2.contourArea, reverse=True)[0] if contours else None
    
    def _find_fall_contours(self) -> List:
        """Find and return contours for fall objects."""
        template = self.templates_raw["fall"]
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        _, template_gray = cv2.threshold(template_gray, 40, 50, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(template_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sorted(contours, key=cv2.contourArea, reverse=True)[0] if contours else None
    
    def _find_key_contours(self) -> List:
        """Find and return contours for key objects."""
        template = self.templates_raw["key"]
        lower_bound = np.array([50, 50, 10])
        upper_bound = np.array([200, 200, 40])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def _find_door_contours(self) -> List:
        """Find and return contours for door objects."""
        template = self.templates_raw["door"]
        lower_bound = np.array([50, 80, 5])
        upper_bound = np.array([109, 133, 25])
        mask = cv2.inRange(template, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours[0] if contours else None
    
    def detect_spike(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains spikes."""
        lower_bound = np.array([0, 0, 0])
        upper_bound = np.array([20, 20, 20])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == len(self.contours_spike):
            contours_spike = sorted(self.contours_spike, key=cv2.contourArea, reverse=True)[:1]
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            sum_score = sum(cv2.matchShapes(contours_spike[i], contours[i], cv2.CONTOURS_MATCH_I1, 0.0) 
                           for i in range(len(contours_spike)))
            return sum_score < 3
        return False
    
    def detect_diamond(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a diamond."""
        lower_bound = np.array([90, 70, 20])
        upper_bound = np.array([235, 235, 235])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 1:
            match_score = cv2.matchShapes(self.contours_diamond, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.5
        return False
    
    def detect_rock(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a rock."""
        lower_bound = np.array([100, 100, 100])
        upper_bound = np.array([255, 255, 255])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 5:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            match_score = cv2.matchShapes(self.contours_rock, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.5
        return False
    
    def detect_fall(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a fall trap."""
        cell_roi_gray = cv2.cvtColor(cell_roi, cv2.COLOR_BGR2GRAY)
        _, cell_roi_gray = cv2.threshold(cell_roi_gray, 40, 50, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(cell_roi_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 1:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            match_score = cv2.matchShapes(self.contours_fall, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.08
        return False
    
    def detect_key(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a key."""
        lower_bound = np.array([50, 50, 10])
        upper_bound = np.array([200, 200, 40])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 1:
            match_score = cv2.matchShapes(self.contours_key, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.5
        return False
    
    def detect_door(self, cell_roi: np.ndarray) -> bool:
        """Check if a cell contains a door."""
        lower_bound = np.array([50, 80, 5])
        upper_bound = np.array([109, 133, 25])
        mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 1:
            match_score = cv2.matchShapes(self.contours_door, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
            return match_score < 0.5
        return False
    
    def tag_cells(self, img_res: np.ndarray, img: np.ndarray, rows: int, cols: int) -> List[List[Optional[Cell]]]:
        """
        Analyze each cell in the grid and identify its content.
        Returns a 2D grid of Cell objects.
        """
        grid = [[None for _ in range(cols)] for _ in range(rows)]
        
        for i in range(rows):
            for j in range(cols):
                # Calculate cell position and extract ROI
                cell_x = int(self.game_rectangle[0] + j * self.cell_width)
                cell_y = int(self.game_rectangle[1] + i * self.cell_height)
                cell_w = int(self.cell_width)
                cell_h = int(self.cell_height)
                cell_roi = img[cell_y:cell_y + cell_h, cell_x:cell_x + cell_w]
                
                # Check for template matches first
                match_found = False
                for name, template in self.templates_raw.items():
                    result = cv2.matchTemplate(cell_roi, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    
                    if max_val >= 0.75:
                        # Draw rectangle and label for detected object
                        cv2.rectangle(img_res, (cell_x, cell_y), 
                                     (cell_x + cell_w, cell_y + cell_h), 
                                     (0, 255, 0), 2)
                        cv2.putText(img_res, name.capitalize(), 
                                   (cell_x, cell_y - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                                   (0, 255, 0), 1)
                        
                        # Remove any numbers from the end of the name
                        clean_name = re.sub(r'\d+$', '', name)
                        grid[i][j] = Cell(cell_type=clean_name, coordinates=[i,j])
                        match_found = True
                        break
                
                if match_found:
                    continue
                
                # Check for specific objects if no template match was found
                if self.detect_spike(cell_roi):
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (0, 0, 255), 1)
                    cv2.putText(img_res, "Spike", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (0, 0, 255), 1)
                    grid[i][j] = Cell(cell_type="spike", row=i, col=j)
                    continue
                
                if self.detect_fall(cell_roi):
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (60, 60, 255), 1)
                    cv2.putText(img_res, "Fall", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (60, 60, 255), 1)
                    grid[i][j] = Cell(cell_type="fall", row=i, col=j)
                    continue
                
                # Check for terrain if nothing else was detected
                roi_mean_color = cv2.mean(cell_roi)[:3]
                terrain_mean_color = cv2.mean(self.templates_raw["terrain"])[:3]
                color_diff = np.linalg.norm(np.array(roi_mean_color) - np.array(terrain_mean_color))
                
                if color_diff < 15:  # Color threshold for terrain
                    cv2.rectangle(img_res, (cell_x, cell_y), 
                                 (cell_x + cell_w, cell_y + cell_h), 
                                 (0, 120, 120), 2)
                    cv2.putText(img_res, "Terrain", (cell_x, cell_y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.35, 
                               (0, 255, 0), 1)
                    grid[i][j] = Cell(cell_type="terrain", coordinates = [i,j])
        
        # Update neighbors for each cell
        for i in range(rows):
            for j in range(cols):
                cell = grid[i][j]
                if cell:
                    if i > 0:
                        cell.neighbor_up = grid[i-1][j]
                    if i < rows - 1:
                        cell.neighbor_down = grid[i+1][j]
                    if j > 0:
                        cell.neighbor_left = grid[i][j-1]
                    if j < cols - 1:
                        cell.neighbor_right = grid[i][j+1]
        
        return grid
    
    def load_templates(self) -> Dict[str, np.ndarray]:
        """Load all template images for object detection."""
        return {
            "diamond": cv2.imread("objects_in_game/diamond.png", cv2.IMREAD_COLOR),
            "door": cv2.imread("objects_in_game/door.png", cv2.IMREAD_COLOR),
            "fall": cv2.imread("objects_in_game/fall.png", cv2.IMREAD_COLOR),
            "key": cv2.imread("objects_in_game/key.png", cv2.IMREAD_COLOR),
            "ladder1": cv2.imread("objects_in_game/ladder.png", cv2.IMREAD_COLOR),
            "ladder2": cv2.imread("objects_in_game/ladder-fs.png", cv2.IMREAD_COLOR),
            "ladder3": cv2.imread("objects_in_game/ladder-pj.png", cv2.IMREAD_COLOR),
            "ladder4": cv2.imread("objects_in_game/ladder-no-walls.png", cv2.IMREAD_COLOR),
            "ladder-open1": cv2.imread("objects_in_game/ladder-open.png", cv2.IMREAD_COLOR),
            "ladder-open2": cv2.imread("objects_in_game/ladder-open-pj.png", cv2.IMREAD_COLOR),
            "ladder-open3": cv2.imread("objects_in_game/ladder-no-walls-open.png", cv2.IMREAD_COLOR),
            "player1": cv2.imread("objects_in_game/player-izq.png", cv2.IMREAD_COLOR),
            "player2": cv2.imread("objects_in_game/player-izq2.png", cv2.IMREAD_COLOR),
            "player3": cv2.imread("objects_in_game/player-der.png", cv2.IMREAD_COLOR),
            "player-with-key1": cv2.imread("objects_in_game/player-key-der.png", cv2.IMREAD_COLOR),
            "player-with-key2": cv2.imread("objects_in_game/player-key-izq.png", cv2.IMREAD_COLOR),
            "rock": cv2.imread("objects_in_game/rock.png", cv2.IMREAD_COLOR),
            "rock-in-fall": cv2.imread("objects_in_game/rock-in-fall.png", cv2.IMREAD_COLOR),
            "terrain": cv2.imread("objects_in_game/terrain.png", cv2.IMREAD_COLOR),
            "spike": cv2.imread("objects_in_game/spikes.png", cv2.IMREAD_COLOR),
            "metal-door": cv2.imread("objects_in_game/metal-door.png", cv2.IMREAD_COLOR),
            "push_button": cv2.imread("objects_in_game/push_button.png", cv2.IMREAD_COLOR),
            "spike-up1": cv2.imread("objects_in_game/spikes-up1.png", cv2.IMREAD_COLOR),
            "spike-up2": cv2.imread("objects_in_game/spikes-up2.png", cv2.IMREAD_COLOR),
        }
    
    def debug_mode(self, screenshot_path: str) -> List[List[Optional[Cell]]]:
        """Run the vision pipeline in debug mode with a saved screenshot."""
        img = self.read_screen_debug(screenshot_path)
        img_res = img.copy()
        
        # Detect game area
        self.game_rectangle = self.get_game_area(img)
        if not self.game_rectangle:
            print("Failed to detect game area.")
            return None
        
        # Create grid and resize templates
        self.cell_width, self.cell_height = self.create_grid(
            img_res, self.game_rectangle, rows=15, cols=10
        )
        self.resize_templates(self.cell_width, self.cell_height)
        
        # Find contours for all object types
        self.contours_spike = self._find_spike_contours()
        self.contours_diamond = self._find_diamond_contours()
        self.contours_rock = self._find_rock_contours()
        self.contours_key = self._find_key_contours()
        self.contours_door = self._find_door_contours()
        self.contours_fall = self._find_fall_contours()
        
        # Tag all cells in the grid
        grid = self.tag_cells(img_res, img, rows=15, cols=10)
        
        # Display results
        cv2.imshow("Resultado", img_res)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return grid
    
    def realtime_mode(self, show_image = False) -> None:
        """Run the vision pipeline in real-time mode."""
        grid = []
        while True:
            img = self.read_screen_realtime()
            img_res = img.copy()
            
            # Detect game area
            self.game_rectangle = self.get_game_area(img)
            if not self.game_rectangle:
                print("Failed to detect game area.")
                pyautogui.sleep(1)
                #if show_image:
                #    cv2.imshow("Resultado", img_res)
                #    if cv2.waitKey(1) == ord('q'):
                #        break
                continue
            pyautogui.sleep(1)
            # Create grid and resize templates
            self.cell_width, self.cell_height = self.create_grid(
                img_res, self.game_rectangle, rows=15, cols=10
            )
            self.resize_templates(self.cell_width, self.cell_height)
            
            # Find contours for all object types
            self.contours_spike = self._find_spike_contours()
            self.contours_diamond = self._find_diamond_contours()
            self.contours_rock = self._find_rock_contours()
            self.contours_key = self._find_key_contours()
            self.contours_door = self._find_door_contours()
            self.contours_fall = self._find_fall_contours()
            
            # Tag all cells in the grid
            grid = self.tag_cells(img_res, img, rows=15, cols=10)
            
            # Display results
            if show_image:
                cv2.imshow("Resultado", img_res)
                break
            else:
                return grid
        
        if cv2.waitKey():
            cv2.destroyAllWindows()
            pyautogui.sleep(2)
            return grid

def main():   
    vision = DiamondRushVision()
    # first_grid = vision.debug_mode("screenshots/screenshot14.png")
    first_grid = vision.realtime_mode(True)
    # print(first_grid)

    # Simular desde la primera grilla hasta el final
    agent = SmartAgent(first_grid)
    winner_state : GameState = agent.simulate()
    for i in winner_state.action_history:
        print(i.get_readable())
    key_simulator = KeyboardSimulator(winner_state)
    key_simulator.execute_actions()
    # TODO verificar si gana el nivel para hacer esto de nuevo

if __name__ == "__main__":
    main()

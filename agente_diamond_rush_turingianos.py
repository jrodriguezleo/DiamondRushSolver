# COMMANDS TO INSTALL DEPENDENCIES
# pip install opencv-python
# pip install pytautogui
# pip install scikit-image  -> usado en skimage.metrics
from contextlib import nullcontext
from itertools import count
import re
import cv2
import numpy as np
from collections import deque
import pyautogui

from skimage.metrics import structural_similarity as ssim


# TODO crear acciones posibles en game state y ponerles peso
# TODO poder simular acciones del juego de forma eficiente (no simular cada paso del pj, solo acciones en el mundo relevantes)
# TODO crear la funcion que permita simular el juego
# TODO recortar assets en resolucion de portatil 1366x768

# TODO mirar los pesos de cada celda para ver si funciona bien el A*
class Cell:
    def __init__(self, row, col, cell_type):
        self.row = row
        self.col = col
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
        

    def __repr__(self):
        return f"Cell({self.row}, {self.col}, {self.cell_type})"

class AStar:
    # Algoritmo A* para encontrar el camino mas corto entre dos puntos usando las celdas Cell
    def __init__(self, start: tuple[int, int], goal: tuple[int, int], grid: list[list[Cell]]):
        self.start = start
        self.goal = goal
        self.grid = grid
        self.open_set = set()
        self.closed_set = set()
        self.came_from = {}
        self.g_score = {}
        self.f_score = {}
        self.path = []
    
    def heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        # Heuristica de manhattan
        # Util cuando solo hay 4 direcciones de movimiento
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    def reconstruct_path(self, current):
        total_path = [current]
        while current in self.came_from:
            current = self.came_from[current]
            total_path.append(current)
        return total_path[::-1]

    # Esta funcion devuelve los vecinos de una celda que son caminables
    def get_neighbors(self, node):
        row, col = node
        neighbors = []
        # Direcciones posibles: arriba, abajo, izquierda, derecha
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        # Para cada cambio en la direccion de fila y columna
        for delta_row, delta_column in directions:
            # Calcular la nueva fila y columna en base a mi delta (osea direcciones arriba, abajo, izquierda, derecha)
            new_row, new_column = row + delta_row, col + delta_column
            # Verificar que la nueva fila y columna esten dentro de los limites de la rejilla
            if 0 <= new_row < len(self.grid) and 0 <= new_column < len(self.grid[0]):
                neighbor_cell = self.grid[new_row][new_column]
                # Agregar celda solo si es caminable y no es None
                if neighbor_cell is not None and neighbor_cell.walkable:
                    neighbors.append((new_row, new_column))
        return neighbors

    # Esta funcion se encarga de buscar el camino mas corto entre el punto de inicio y el punto de fin
    def search(self):
        self.open_set = {self.start}
        self.g_score = {self.start: 0}
        self.f_score = {self.start: self.heuristic(self.start, self.goal)}
        self.came_from = {}

        # Mientras haya nodos en la lista abierta
        while self.open_set:
            # Obtener el nodo con el menor f_score 
            current = min(self.open_set, key=lambda x: self.f_score.get(x, float('inf')))
            if current == self.goal:
                self.path = self.reconstruct_path(current)
                return self.path

            # Mover el nodo actual de la lista abierta a la lista cerrada
            self.open_set.remove(current)
            self.closed_set.add(current)

            neighbors = self.get_neighbors(current)
            if not neighbors:
                continue  # No walkable neighbors, path may be blocked

            # Para cada vecino del nodo actual y que no esté en la lista cerrada
            for neighbor in neighbors:
                if neighbor in self.closed_set:
                    continue
                # Calcular el costo g del vecino  y sumarle el peso de la celda
                tentative_g_score = self.g_score[current] + self.grid[neighbor[0]][neighbor[1]].weight
                # Si el vecino no está en la lista abierta, agregarlo
                if neighbor not in self.open_set:
                    self.open_set.add(neighbor)
                # Si el costo g es mayor que el costo g actual, continuar
                elif tentative_g_score >= self.g_score.get(neighbor, float('inf')):
                    continue
                
                # Actualizar el camino más corto
                self.came_from[neighbor] = current
                self.g_score[neighbor] = tentative_g_score
                self.f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, self.goal)

        # No path found
        self.path = []
        return None

class GameAction:
    # Esta clase se encarga de guardar las posibles acciones del juego. Basicamente es para que se pueda
    # leer humanamente esto, ya que al final se traduce como moverse a x,y o empujar a alguna direccion
    def __init__(self, action: str, coordinates: tuple[int, int] = None, path : list = []):
        self.action = action
        self.coordinates = coordinates
        # El path es el camino hallado por A* para llegar a la celda
        self.path = path

class GameState:
    # Esta clase se encarga de guardar el estado del juego junto ccon la lista de acciones que lo llevaron a ese estado
    # Se considera un estado ganador si el jugador llega a la escalera abierta. (el agente revisa esta condicion para romper la simulacion)
    # con player pos y ladder pos
    # Las acciones son ir a x,y o empujar a alguna direccion
    def __init__(self, grid: list[list[Cell]], player_pos: tuple[int, int], game_state: int, actions: list[GameAction] = []):
        self.grid = grid
        self.player_pos = player_pos
        self.game_state = game_state
        self.actions = actions

    def __repr__(self):
        return f"GameState({self.grid}, {self.player_pos}, {self.game_state})"

class KeyboardSimulator:
    # Esta clase se encarga de simular el teclado para enviar acciones al juego
    def __init__(self, game_state: GameState):
        self.actions = game_state.actions
    
    def execute_actions(self):
        # Ejecutar las acciones en la lista de acciones
        for action in self.actions:
            # Simular la accion en el juego
            self.execute_action(action)
        # Limpiar la lista de acciones
        self.actions = []
    
    # Dado que cada accion es un ir a x,y o empujar a alguna direccion, se debe hacer un A* para encontrar el camino
    # luego simular cada movimiento del A * en el juego
    def execute_action(self, action: GameAction):
        path = action.path
        if action.action == "move":
            # Simular el movimiento en el juego
            for step in path:
                # Simular el movimiento en el juego
                self.simulate_move(step)
                # Esperar un tiempo para que el juego procese el movimiento
                pyautogui.sleep(1)

    def simulate_move(self, step: str):
        # Simular el movimiento en el juego
        # Esto se hace enviando las teclas de movimiento al juego
        # Se puede usar pyautogui o pynput para simular el teclado
        if step == "up":
            pyautogui.press("up")
        elif step == "down":
            pyautogui.press("down")
        elif step == "left":
            pyautogui.press("left")
        elif step == "right":
            pyautogui.press("right")

class SmartAgent:
    # El agente define la estrategia a seguir para resolver el juego
    def __init__(self, game_state: GameState):
        self.game_state = game_state
    
    # IDEALMENTE ESTAS FUNCIONES DE FIND NEAREST PRIMERO DEBEN MIRAR SI EN LA GRILLA EXISTE DICHA COSA PARA AHORRAR COMPUTO.
    # Podria ser un solo for que recorra la grilla y busque todas las cosas al mismo tiempo diciendo si existen.
    def check_objects_in_grid(self):
        doorExists = False
        keyExists = False
        diamondExists = False
        rockExists = False
        for row in self.grid:
            for cell in row:
                if cell.cell_type == "door":
                    doorExists = True
                elif cell.cell_type == "key":
                    keyExists = True
                elif cell.cell_type == "diamond":
                    diamondExists = True
                elif cell.cell_type == "rock":
                    rockExists = True
        return doorExists, keyExists, diamondExists, rockExists

    def find_nearest_diamond():
        #TODO
        # Esta funcion se encarga de encontrar el diamante mas cercano al jugador, si el peso excede un umbral
        # o no hay diamantes o vecinos caminables, entonces no se realiza esta accion
        # Se usa el algoritmo A* para encontrar el camino mas corto entre el jugador y el diamante
        pass

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
        #TODO
        # Esta funcion se encarga de devolver la siguiente accion a realizar
        # Se elige la accion con menor peso
        # Si el peso es mayor a un umbral, entonces no se realiza la accion
        # si no se realiza la accion, se elige la siguiente accion con menor peso en la lista de acciones
        pass

    def simulate(self):
        # Esta funcion se encarga de simular el juego con un loop
        # Se devuelve el estado del juego al lograr la meta
        # En cada paso se guarda la accion tomaada por cada estado de juego
        # Se tiene una pila de acciones en orden para ir de forma greedy a la solucion pero si no se puede hacer la accion
        # se hace la siguiente y asi, si no hay ninguna accion se considera unn camino bloqueado y se devuelve hasta el ultimo estado viable
        # Retorna el game state donde se gana junto con sus acciones
        pass


import cv2
import numpy as np
import pyautogui
import re
from typing import Optional, Tuple, Dict, List

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
                        grid[i][j] = Cell(cell_type=clean_name, row=i, col=j)
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
                    grid[i][j] = Cell(cell_type="terrain", row=i, col=j)
        
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
    
    def realtime_mode(self) -> None:
        """Run the vision pipeline in real-time mode."""
        while True:
            img = self.read_screen_realtime()
            img_res = img.copy()
            
            # Detect game area
            self.game_rectangle = self.get_game_area(img)
            if not self.game_rectangle:
                print("Failed to detect game area.")
                cv2.imshow("Resultado", img_res)
                if cv2.waitKey(1) == ord('q'):
                    break
                continue
            
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
            _ = self.tag_cells(img_res, img, rows=15, cols=10)
            
            # Display results
            cv2.imshow("Resultado", img_res)
            if cv2.waitKey(1) == ord('q'):
                break

def main():   
    vision = DiamondRushVision()
    first_grid = vision.debug_mode("screenshots/screenshot3.png")
    # first_grid = vision.realtime_mode()
    print(first_grid)

    # Simular desde la primera grilla hasta el final
    agent = SmartAgent(first_grid)
    winner_state = agent.simulate()
    key_simulator = KeyboardSimulator(winner_state)
    key_simulator.execute_actions()
    # TODO verificar si gana el nivel para hacer esto de nuevo


if __name__ == "__main__":
    main()



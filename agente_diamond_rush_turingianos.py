from contextlib import nullcontext
from itertools import count
import re
import cv2
import numpy as np
from collections import deque
import pyautogui

from skimage.metrics import structural_similarity as ssim


# TODO crear un nodo game state para ir guardanndo los estados del juego simulados
# TODO crear algoritmo A star
# TODO crear acciones posibles en game state y ponerles peso
# TODO crear heuristicac para el algoritmo A star
# TODO poder enviar acciones al juego por medio de simulacion de teclado
# TODO preocuparse de paralelizar la simulacion de juego
# TODO poder simular acciones del juego de forma eficiente (no simular cada paso del pj, solo acciones en el mundo relevantes)
# TODO crear la funcion que permita simular el juego
# TODO recortar assets en resolucion de portatil 1366x768

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

def read_screen_debug(path : str) -> tuple[str, str]:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    return img

def read_screen_realtime() -> tuple[str, str]:
    img = pyautogui.screenshot()
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return img

def get_game_area(img) -> None | tuple[int, int, int, int]:
    # ------- HALLAR AREA ENTRE CONTORNOS ------- #
    # color hexadecimal #10191c
    # RGB ES 17 25 28
    target_color = (24, 21, 13)  # Color en formato BGR DEL COLOR -1 PARA RANGO
    target_color2 = (32, 27, 22)  # Color en formato BGR + 1 para rango

    # Crear un rango de color
    lower_bound = np.array(target_color)  # Límite inferior del color
    upper_bound = np.array(target_color2)  # Límite superior del color

    # Esta mascara filtra segun el rango de color
    mask = cv2.inRange(img, lower_bound, upper_bound)
    # Hallar contornos del filtro (mascara)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Dejar solo los 2 contornos mas grandes
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]

    # Hallar el area entre los dos contornos y dibujarla en rojo
    # Verificar que hay al menos dos contornos
    if len(contours) >= 2:
        x1 = cv2.boundingRect(contours[0])
        x2 = cv2.boundingRect(contours[1])
        # Reconocer que contorno esta a la izquierda y cual a la derecha
        if x1 < x2:
            left_contour = contours[0]
            right_contour = contours[1]
        else:
            left_contour = contours[1]
            right_contour = contours[0]

        x1, y1, w1, h1 = cv2.boundingRect(left_contour)
        x2, y2, w2, h2 = cv2.boundingRect(right_contour)
        # Solo el area sin posicionamiento
        area = (x2 - x1 - w1, h1)
        
        if area[0] < 100 or area[1] < 100:
            print("El área es demasiado pequeña para procesar.")
            return None
        else:
            # Rectángulo delimitador del área entre los dos contornos con posicion inicial y tamaño
            game_rectangle = (x1 + w1, y1, x2, y2+h2)
            print("El área es lo suficientemente grande para procesar. ", game_rectangle)
            # Debug dibujar el rectángulo en la imagen original y mostrarlo
            #img_debug = img.copy()
            #cv2.rectangle(img_debug, (w1, y1), (x2, y2+h2), (0, 0, 255), 1)
            #cv2.imshow("Area del juego", img_debug)
            #cv2.waitKey(0)
            return game_rectangle
    else:
        print("No se encontraron suficientes contornos para calcular el área.")
        return None
    # ---- FIN HALLAR AREA ENTRE CONTORNOS ---- #

# Esta funcion se encarga de crear la rejilla en la imagen editada y devuelve el tamaño de las celdas
def create_grid(img_res: np.ndarray, game_rectangle: tuple[int, int, int, int], rows: int, cols: int) -> tuple[float, float]:
    area = (game_rectangle[2] - game_rectangle[0], game_rectangle[3] - game_rectangle[1])
    cell_width = area[0] / cols
    cell_height = area[1] / rows
    first_x, first_y = (game_rectangle[0], game_rectangle[1])
    print("Area: ", area)
    print("Tamaño de celda: ", cell_width, cell_height)
    # Dibujar rejilla
    for i in range(cols + 1):
        x = round(first_x + i * cell_width)  # Redondear posición x
        pt1 = (x, round(first_y))  # Redondear posición y
        pt2 = (x, round(first_y + rows * cell_height))  # Redondear posición y
        cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)

    for j in range(rows + 1):
        y = round(first_y + j * cell_height)  # Redondear posición y
        pt1 = (round(first_x), y)  # Redondear posición x
        pt2 = (round(first_x + cols * cell_width), y)  # Redondear posición x
        cv2.line(img_res, pt1, pt2, (255, 0, 0), 1)


    return cell_width, cell_height

def resize_templates(templates_raw, cell_width, cell_height):
    # Usar el tamaño de celda calculado para redimensionar los templates
    for name, template in templates_raw.items():
        templates_raw[name] = cv2.resize(template, (int(cell_width), int(cell_height)), interpolation=cv2.INTER_NEAREST)



def find_spike_contours(template: list) -> list:
    # ----- Hallar ----- #
    lower_bound = np.array([0, 0, 0])  # Límite inferior del color
    upper_bound = np.array([20, 20, 20])  # Límite superior del color
    # Verificar si el template se cargó correctamente
    if template is None:
        print("El template 'spike' no se cargó correctamente.")
    else:
        # Crear una máscara binaria para el rango de color
        mask = cv2.inRange(template, lower_bound, upper_bound)
        # Encontrar los contornos en la máscara
        contoursSpike, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Mostrar la máscara y el template con contornos
        # template_with_contours = template.copy()
        # cv2.drawContours(template_with_contours, contoursSpike, -1, (0, 255, 0), 2)  # Color verde para los contornos
        # cv2.imshow("Máscara binaria", mask)
        # cv2.imshow("Contornos en el template spike", template_with_contours)
        # cv2.waitKey(0)
        return contoursSpike
    # ----- FIN Hallar numero de contornos de spikes ----- #

def find_diamond_contours(template: list) -> list:
    # ----- Hallar ----- #
    lower_bound = np.array([90, 70, 20])  # Límite inferior del color del diamante
    upper_bound = np.array([235, 235, 235])  # Límite superior del color del diamante
    # Verificar si el template se cargó correctamente
    if template is None:
        print("El template 'diamond' no se cargó correctamente.")
    else:
        # Crear una máscara binaria para el rango de color
        mask = cv2.inRange(template, lower_bound, upper_bound)
        # Encontrar los contornos en la máscara
        contoursDiamond, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # result = cv2.bitwise_and(template, template, mask=mask)
        # # Mostrar la imagen resultante
        # cv2.imshow("Resultado", result)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()

        # # Mostrar la máscara y el template con contornos
        # template_with_contours = template.copy()
        # cv2.drawContours(template_with_contours, contoursDiamond, -1, (0, 255, 0), 2)  # Color verde para los contornos
        # cv2.imshow("Máscara binaria", mask)
        # cv2.imshow("Contornos en el template", template_with_contours)
        # cv2.waitKey(0)
        # Devuelve el uinico contorno encontrado
        return contoursDiamond[0]
    # ----- FIN Hallar numero de contornos de spikes ----- #

def find_rock_contours(template: list) -> list:
    # ----- Hallar ----- #
    # Color principal roca en rgb 236, 151, 91
    # el color secundario tira hacia al blanco
    lower_bound = np.array([100, 100, 100])  # Límite inferior del color 
    upper_bound = np.array([255, 255, 255])  # Límite superior del color 
    # Verificar si el template se cargó correctamente
    if template is None:
        print("El template 'rock' no se cargó correctamente.")
    else:
        # Crear una máscara binaria para el rango de color
        mask = cv2.inRange(template, lower_bound, upper_bound)
        # Encontrar los contornos en la máscara
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # result = cv2.bitwise_and(template, template, mask=mask)
        # # Mostrar la imagen resultante
        # cv2.imshow("Resultado", result)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        # print("Contornos encontrados: ", len(contours))
        # # Mostrar la máscara y el template con contornos
        # template_with_contours = template.copy()
        # cv2.drawContours(template_with_contours, contours, -1, (0, 255, 0), 2)  # Color verde para los contornos
        # cv2.imshow("Máscara binaria", mask)
        # cv2.imshow("Contornos en el template", template_with_contours)
        # cv2.waitKey(0)
        # Devuelve el contorno mayor
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        return contours[0]
    # ----- FIN Hallar numero de contornos de spikes ----- #



def find_fall_contours(template: list) -> list:
    # template to gray scale
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    # umbral para binarizar la imagen
    _, template_gray = cv2.threshold(template_gray, 40, 50, cv2.THRESH_BINARY_INV)
    # encontrar contornos
    contours, _ = cv2.findContours(template_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
    return contours[0]
    # cv2.imshow("Resultado", template_gray)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    # # dibujar contornos
    # cv2.drawContours(template, contours, -1, (0, 255, 0), 2)  # Color verde para los contornos
    # # # Mostrar la imagen resultante
    # cv2.imshow("Resultado", template)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


def find_key_contours(template: list) -> list:
    # ----- Hallar ----- #
    # Color principal key en rgb 23, 166, 123
    # Casi notiene red y debe predominar azul y verde
    lower_bound = np.array([50, 50, 10])  # Límite inferior del color 
    upper_bound = np.array([200, 200, 40])  # Límite superior del color 
    # Verificar si el template se cargó correctamente
    if template is None:
        print("El template 'key' no se cargó correctamente.")
    else:
        # Crear una máscara binaria para el rango de color
        mask = cv2.inRange(template, lower_bound, upper_bound)
        # Encontrar los contornos en la máscara
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # result = cv2.bitwise_and(template, template, mask=mask)
        # # Mostrar la imagen resultante
        # cv2.imshow("Resultado", result)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        # print("Contornos encontrados: ", len(contours))
        # # Mostrar la máscara y el template con contornos
        # template_with_contours = template.copy()
        # cv2.drawContours(template_with_contours, contours, -1, (0, 255, 0), 2)  # Color verde para los contornos
        # cv2.imshow("Máscara binaria", mask)
        # cv2.imshow("Contornos en el template", template_with_contours)
        # cv2.waitKey(0)
        # Devuelve el contorno mayor
        # contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        return contours[0]
    # ----- FIN Hallar numero de contornos de spikes ----- #


def find_door_contours(template: list) -> list:
    # ----- Hallar ----- #
    # Color principal key en rgb 17, 121, 87
    # Casi notiene red y debe predominar azul y verde
    lower_bound = np.array([50, 80, 5])  # Límite inferior del color 
    upper_bound = np.array([109, 133, 25])  # Límite superior del color 
    # Verificar si el template se cargó correctamente
    if template is None:
        print("El template 'door' no se cargó correctamente.")
    else:
        # Crear una máscara binaria para el rango de color
        mask = cv2.inRange(template, lower_bound, upper_bound)
        # Encontrar los contornos en la máscara
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # result = cv2.bitwise_and(template, template, mask=mask)
        # # Mostrar la imagen resultante
        # cv2.imshow("Resultado", result)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        # print("Contornos encontrados: ", len(contours))
        # # Mostrar la máscara y el template con contornos
        # template_with_contours = template.copy()
        # cv2.drawContours(template_with_contours, contours, -1, (0, 255, 0), 2)  # Color verde para los contornos
        # cv2.imshow("Máscara binaria", mask)
        # cv2.imshow("Contornos en el template", template_with_contours)
        # cv2.waitKey(0)
        # Devuelve el contorno mayor

        return contours[0]
    # ----- FIN Hallar numero de contornos de spikes ----- #

def detect_spike(cell_roi: np.ndarray, contours_spike: list) -> bool:
    lower_bound = np.array([0, 0, 0])
    upper_bound = np.array([20, 20, 20])
    mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == len(contours_spike):
        contours_spike = sorted(contours_spike, key=cv2.contourArea, reverse=True)[:1]
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        sum_score = 0
        for i in range(len(contours_spike)):
            match_score = cv2.matchShapes(contours_spike[i], contours[i], cv2.CONTOURS_MATCH_I1, 0.0)
            sum_score += match_score
        if sum_score < 3:
            return True
    return False


def detect_diamond(cell_roi: np.ndarray, diamond_contour: list) -> bool:
    # Color principal del diamante: en RGB 58,162, 182
    # Color secundario mas blanco: 183,222,222
    # Crear rango para los colores del diamante desde 58,162,182 a 183,222,222
    lower_bound = np.array([90, 70, 20])  # Límite inferior del color del diamante
    upper_bound = np.array([235, 235, 235])  # Límite superior del color del diamante
    mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Si exactamente un contorno, entonces es un posible diamante
    if len(contours) == 1:
        match_score = cv2.matchShapes(diamond_contour, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
        # Si el match es menor a 0.1, entonces es un diamante
        if match_score < 0.5:
            return True
    return False


def detect_fall(cell_roi: np.ndarray, contour: list) -> bool:
    # template to gray scale
    cell_roi_gray = cv2.cvtColor(cell_roi, cv2.COLOR_BGR2GRAY)
    # umbral para binarizar la imagen
    _, cell_roi_gray = cv2.threshold(cell_roi_gray, 40, 50, cv2.THRESH_BINARY_INV)
    # encontrar contornos
    contours, _ = cv2.findContours(cell_roi_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    

    if len(contours) > 1:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
            
        match_score = cv2.matchShapes(contour, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
        # Si el match es menor a 0.1, entonces es un fall
        if match_score < 0.08:
            return True
    return False



def detect_key(cell_roi: np.ndarray, contour: list) -> bool:
    # Color principal del diamante: en RGB 58,162, 182
    # Color secundario mas blanco: 183,222,222
    # Crear rango para los colores del diamante desde 58,162,182 a 183,222,222
    lower_bound = np.array([50, 50, 10])  # Límite inferior del color 
    upper_bound = np.array([200, 200, 40])  # Límite superior del color 
    mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Si exactamente un contorno, entonces es un posible diamante
    if len(contours) == 1:
        match_score = cv2.matchShapes(contour, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
        # Si el match es menor a 0.1, entonces es un diamante
        if match_score < 0.5:
            return True
    return False
    #return len(contours) == len(contours_spike)

def detect_door(cell_roi: np.ndarray, contour: list) -> bool:
    # Crear rango para los colores del diamante desde 58,162,182 a 183,222,222
    lower_bound = np.array([50, 80, 5])  # Límite inferior del color 
    upper_bound = np.array([109, 133, 25])  # Límite superior del color 
    mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Si exactamente un contorno, entonces es un posible diamante
    if len(contours) == 1:
        match_score = cv2.matchShapes(contour, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
        # Si el match es menor a 0.1, entonces es un diamante
        if match_score < 0.5:
            return True
    return False

def detect_rock(cell_roi: np.ndarray, rock_contour: list) -> bool:
    # Color principal del diamante: en RGB 58,162, 182
    # Color secundario mas blanco: 183,222,222
    # Crear rango para los colores del diamante desde 58,162,182 a 183,222,222
    lower_bound = np.array([100, 100, 100])  # Límite inferior del color 
    upper_bound = np.array([255, 255, 255])  # Límite superior del color 
    mask = cv2.inRange(cell_roi, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Si exactamente 5 contorno, entonces es un posible roca
    if len(contours) == 5:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        match_score = cv2.matchShapes(rock_contour, contours[0], cv2.CONTOURS_MATCH_I1, 0.0)
        # Si el match es menor a 0.1, entonces es
        if match_score < 0.5:
            return True
    return False
    #return len(contours) == len(contours_spike)


def tag_cells(img_res, img, templates_raw, contours_spike, contours_diamond, contours_rock, contours_key, contours_door, contours_fall, firstGrid, cell_width, cell_height, rows, cols):
    grid = [[None for _ in range(cols)] for _ in range(rows)]  # Inicializar la rejilla
    # Traverse the grid and check for matches with templates
    for i in range(rows):
        for j in range(cols):
            # Calcular la posición de la celda actual
            cell_x = int(firstGrid[0] + j * cell_width)
            cell_y = int(firstGrid[1] + i * cell_height)
            cell_w = int(cell_width)
            cell_h = int(cell_height)
            # Recortar solo la celda actual de la imagen original
            cell_roi = img[cell_y:cell_y + cell_h, cell_x:cell_x + cell_w]

            match_found_by_template = False
            for name, template in templates_raw.items():
                # Realizar el match template
                result = cv2.matchTemplate(cell_roi, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                # Si el resultado supera el umbral y es el mejor hasta ahora, registrar el match
                # TODO AJUSTAR MEJOR EL UMBRAL Y A VECES AJUSTAR EL DE LA ROCA Y EL BOTON
                if max_val >= 0.75:
                    print(f"{name.capitalize()} encontrado en celda ({i}, {j}) con confianza {max_val:.2f}")
                    # Dibujar un rectángulo alrededor del match en la imagen editada
                    bottom_right = (cell_x + cell_w, cell_y + cell_h)
                    cv2.rectangle(img_res, (cell_x, cell_y), bottom_right, (0, 255, 0), 2)
                    cv2.putText(img_res, name.capitalize(), (cell_x, cell_y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
                    match_found_by_template = True

                    # Si el nombre termina con un numero, cortar ese numero antes de guardar el nombre enn el nodo
                    name = re.sub(r'\d+$', '', name)
                    grid[i][j] = Cell(cell_type = name, row = i, col = j)
                    break

            if match_found_by_template: continue

            # --- Verificar si la celda tiene spikes --- #
            if detect_spike(cell_roi, contours_spike):
                # Si se detectan spikes, dibujar un rectángulo alrededor de la celda
                cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (0, 0, 255), 1)
                # Poner el texto "Spike" en la celda
                cv2.putText(img_res, "Spike", (cell_x, cell_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
                name = "spike"
                grid[i][j] = Cell(cell_type = name, row = i, col = j)
                continue
            
            if detect_fall(cell_roi, contours_fall):
                # Si se detecta un fall, dibujar un rectángulo alrededor de la celda
                cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (60, 60, 255), 1)
                # Poner el texto "Fall" en la celda
                cv2.putText(img_res, "Fall", (cell_x, cell_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (60, 60, 255), 1)
                name = "fall"
                grid[i][j] = Cell(cell_type = name, row = i, col = j)
                continue

            # if detect_diamond(cell_roi, contours_diamond):
            #     # Si se detecta un diamante, dibujar un rectángulo alrededor de la celda
            #     cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (0, 255, 0), 1)
            #     # Poner el texto "Diamond" en la celda
            #     cv2.putText(img_res, "Diamond", (cell_x, cell_y - 10),
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
            #     continue

            # if detect_rock(cell_roi, contours_rock):
            #     # Si se detecta una roca, dibujar un rectángulo alrededor de la celda
            #     cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (100, 100, 255), 1)
            #     # Poner el texto "Rock" en la celda
            #     cv2.putText(img_res, "Rock", (cell_x, cell_y - 10),
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 255), 1)
            #     continue
            
            # if detect_key(cell_roi, contours_key):
            #     # Si se detecta una llave, dibujar un rectángulo alrededor de la celda
            #     cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (240, 240, 240), 1)
            #     # Poner el texto "Key" en la celda
            #     cv2.putText(img_res, "Key", (cell_x, cell_y - 10),
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            #     continue
            
            # if detect_door(cell_roi, contours_door):
            #     # Si se detecta una llave, dibujar un rectángulo alrededor de la celda
            #     cv2.rectangle(img_res, (cell_x, cell_y), (cell_x + cell_w, cell_y + cell_h), (20, 240, 240), 1)
            #     # Poner el texto "Door" en la celda
            #     cv2.putText(img_res, "Door", (cell_x, cell_y - 10),
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.35, (20, 255, 255), 1)
            #     continue
            
            

            # Verificar si es terreno luego de que el resto falló
            roi_mean_color = cv2.mean(cell_roi)[:3]
            # Verificar si el ROI coincide con el terreno basado en el color promedio
            terrain_mean_color = cv2.mean(templates_raw["terrain"])[:3]
            color_diff = np.linalg.norm(np.array(roi_mean_color) - np.array(terrain_mean_color))
            color_threshold = 15  # Ajusta este valor según sea necesario

            if color_diff < color_threshold:
                print(f"terreno encontrado en celda ({i}, {j}) con confianza {color_diff:.2f}")

                #  Dibujar un rectángulo alrededor del match en la imagen editada
                bottom_right = (cell_x + cell_w, cell_y + cell_h)
                cv2.rectangle(img_res, (cell_x, cell_y), bottom_right, (0, 120, 120), 2)
                cv2.putText(img_res, "Terreno", (cell_x, cell_y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
                name = "terrain"
                grid[i][j] = Cell(cell_type = name, row = i, col = j)
            
            #cv2.imshow("cell", cell_roi)
            #cv2.waitKey(0)
    
    # Actualizar los vecinos de cada celda
    for i in range(rows):
        for j in range(cols):
            cell = grid[i][j]
            if cell is not None:
                if i > 0:
                    cell.neighbor_up = grid[i-1][j]
                if i < rows - 1:
                    cell.neighbor_down = grid[i+1][j]
                if j > 0:
                    cell.neighbor_left = grid[i][j-1]
                if j < cols - 1:
                    cell.neighbor_right = grid[i][j+1]
    
    return grid


def load_templates() -> tuple[dict, dict]:
    # ASSETS en tamaño full screen 1920x1080
    # TODO hacer assets en 1366x768 y probar si esas estan mejor para pantallas mas chicas... probar
    templates_raw = {
        "diamond": cv2.imread("Diamond-Rush-Bot/diamond.png", cv2.IMREAD_COLOR),
        "door": cv2.imread("Diamond-Rush-Bot/door.png", cv2.IMREAD_COLOR),
        "fall": cv2.imread("Diamond-Rush-Bot/fall.png", cv2.IMREAD_COLOR),
        "key": cv2.imread("Diamond-Rush-Bot/key.png", cv2.IMREAD_COLOR),
        "ladder1": cv2.imread("Diamond-Rush-Bot/ladder.png", cv2.IMREAD_COLOR),
        "ladder2": cv2.imread("Diamond-Rush-Bot/ladder-fs.png", cv2.IMREAD_COLOR),
        "ladder3": cv2.imread("Diamond-Rush-Bot/ladder-pj.png", cv2.IMREAD_COLOR),
        "ladder4": cv2.imread("Diamond-Rush-Bot/ladder-no-walls.png", cv2.IMREAD_COLOR),
        "ladder-open1": cv2.imread("Diamond-Rush-Bot/ladder-open.png", cv2.IMREAD_COLOR),
        "ladder-open2": cv2.imread("Diamond-Rush-Bot/ladder-open-pj.png", cv2.IMREAD_COLOR),
        "ladder-open3": cv2.imread("Diamond-Rush-Bot/ladder-no-walls-open.png", cv2.IMREAD_COLOR),
        "player1": cv2.imread("Diamond-Rush-Bot/player-izq.png", cv2.IMREAD_COLOR),
        "player2": cv2.imread("Diamond-Rush-Bot/player-izq2.png", cv2.IMREAD_COLOR),
        "player3": cv2.imread("Diamond-Rush-Bot/player-der.png", cv2.IMREAD_COLOR),
        "player-with-key1": cv2.imread("Diamond-Rush-Bot/player-key-der.png", cv2.IMREAD_COLOR),
        "player-with-key2": cv2.imread("Diamond-Rush-Bot/player-key-izq.png", cv2.IMREAD_COLOR),
        "rock": cv2.imread("Diamond-Rush-Bot/rock.png", cv2.IMREAD_COLOR),
        "rock-in-fall": cv2.imread("Diamond-Rush-Bot/rock-in-fall.png", cv2.IMREAD_COLOR),
        "terrain": cv2.imread("Diamond-Rush-Bot/terrain.png", cv2.IMREAD_COLOR),
        "spike": cv2.imread("Diamond-Rush-Bot/spikes.png", cv2.IMREAD_COLOR),
        "metal-door": cv2.imread("Diamond-Rush-Bot/metal-door.png", cv2.IMREAD_COLOR),
        "push_button": cv2.imread("Diamond-Rush-Bot/push_button.png", cv2.IMREAD_COLOR),
        "spike-up1": cv2.imread("Diamond-Rush-Bot/spikes-up1.png", cv2.IMREAD_COLOR),
        "spike-up2": cv2.imread("Diamond-Rush-Bot/spikes-up2.png", cv2.IMREAD_COLOR),
        
    }
    return templates_raw

def debug_mode():
    # --- CONFIG ---
    # Diccionario con objetos y su imagen base
    templates_raw = load_templates()
    # Modo debug
    img = read_screen_debug("Diamond-Rush-Bot/screenshots/screenshot3.png")
    img_res = img.copy()
    # Obtener área del juego
    game_rectangle = get_game_area(img)
    if game_rectangle is None:
        print("No se pudo encontrar el área del juego.")
        return

    # Crear rejilla
    cell_width, cell_height = create_grid(img_res, game_rectangle, rows=15, cols=10)

    # Redimensionar templates
    resize_templates(templates_raw, cell_width, cell_height)

    # Hallar una sola vez los contornos de los templates
    contours_spike = find_spike_contours(templates_raw["spike"])
    contours_diamond = find_diamond_contours(templates_raw["diamond"])
    contours_rock = find_rock_contours(templates_raw["rock"])
    contours_key = find_key_contours(templates_raw["key"])
    contours_door = find_door_contours(templates_raw["door"])
    contours_fall = find_fall_contours(templates_raw["fall"])
    # ponerle nombre a las celdas
    nodes_in_game = tag_cells(img_res, img, templates_raw, contours_spike, contours_diamond, contours_rock, contours_key, contours_door, contours_fall, game_rectangle, cell_width, cell_height, rows=15, cols=10)
    
    # Imprimir en consola los nodos encontrados de manera legible para un humano
    for i in range(len(nodes_in_game)):
        for j in range(len(nodes_in_game[i])):
            if nodes_in_game[i][j] is not None:
                print(f"Celda ({i}, {j}): {nodes_in_game[i][j].cell_type}")
            else:
                print(f"Celda ({i}, {j}): None")
    
    # Mostrar resultados
    cv2.imshow("Resultado", img_res)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def realtime_mode():
    # --- CONFIG ---
    while True:
        # Diccionario con objetos y su imagen base
        templates_raw = load_templates()
        # Modo debug
        img = read_screen_realtime()
        img_res = img.copy()
        # Obtener área del juego
        game_rectangle = get_game_area(img)
        if game_rectangle is None:
            print("No se pudo encontrar el área del juego.")
            cv2.imshow("Resultado", img_res)
            if cv2.waitKey(1) == ord('q'):
                break
            continue

        # Crear rejilla
        cell_width, cell_height = create_grid(img_res, game_rectangle, rows=15, cols=10)

        # Redimensionar templates
        resize_templates(templates_raw, cell_width, cell_height)

        # Hallar una sola vez los contornos de los templates
        contours_spike = find_spike_contours(templates_raw["spike"])
        contours_diamond = find_diamond_contours(templates_raw["diamond"])
        contours_rock = find_rock_contours(templates_raw["rock"])
        contours_key = find_key_contours(templates_raw["key"])
        contours_door = find_door_contours(templates_raw["door"])
        contours_fall = find_fall_contours(templates_raw["fall"])
        # ponerle nombre a las celdas
        nodes_in_game = tag_cells(img_res, img, templates_raw, contours_spike, contours_diamond, contours_rock, contours_key, contours_door, contours_fall, game_rectangle, cell_width, cell_height, rows=15, cols=10)

        # Mostrar resultados
        cv2.imshow("Resultado", img_res)
        if cv2.waitKey(1) == ord('q'):
                break

def main():   
    # realtime_mode()
    debug_mode()


if __name__ == "__main__":
    main()



from game_action import GameAction
from game_state import GameState
import pyautogui
from pyKey import pressKey, releaseKey, press, sendSequence, showKeys

class KeyboardSimulator:
    # Esta clase se encarga de simular el teclado para enviar acciones al juego
    def __init__(self, game_state: GameState):
        self.actions = game_state.action_history
    
    async def execute_actions(self):
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
            pyautogui.sleep(0.15)
    
    # Dado que cada accion es un ir a x,y o empujar a alguna direccion, se debe hacer un A* para encontrar el camino
    # luego simular cada movimiento del A * en el juego
    def execute_action(self, action: GameAction):
        path = action.path
        # Simular el movimiento en el juego
        for step in path:
            # Simular el movimiento en el juego
            self.simulate_move(step)
            # Esperar un tiempo para que el juego procese el movimiento
            pyautogui.sleep(0.15)

    def simulate_move(self, step: str):
        # Simular el movimiento en el juego
        # Esto se hace enviando las teclas de movimiento al juego
        # Se puede usar pyautogui o pynput para simular el teclado
        if step == "up":
            press("UP",0.15)
        elif step == "down":
            press("DOWN",0.15)
        elif step == "left":
            press("LEFT",0.15)
        elif step == "right":
            press("RIGHT",0.15)
from game_action import GameAction
from game_state import GameState
import pyautogui

class KeyboardSimulator:
    # Esta clase se encarga de simular el teclado para enviar acciones al juego
    def __init__(self, game_state: GameState):
        self.actions = game_state.action_history

    async def execute_actions(self):
        total_path = []
        for action in self.actions:
            for th in action.path:
                total_path.append(th)
        self.actions = []
        print("Lista completa de pasos a seguir")
        print(total_path)
        for step in total_path:
            self.simulate_move(step)
            pyautogui.sleep(0.15)

    def execute_action(self, action: GameAction):
        for step in action.path:
            self.simulate_move(step)
            pyautogui.sleep(0.15)

    def simulate_move(self, step: str):
        if step in ("up", "down", "left", "right"):
            pyautogui.keyDown(step)
            pyautogui.sleep(0.05)
            pyautogui.keyUp(step)

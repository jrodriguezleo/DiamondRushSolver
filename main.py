from diamond_rush_vision import DiamondRushVision
from smart_agent import SmartAgent
from keyboard_simulator import KeyboardSimulator
from game_state import GameState
import asyncio

# TODO crear acciones posibles en game state y ponerles peso
# TODO poder simular acciones del juego de forma eficiente (no simular cada paso del pj, solo acciones en el mundo relevantes)
# TODO crear la funcion que permita simular el juego
# TODO recortar assets en resolucion de portatil 1366x768

def main():
    while True:
        vision = DiamondRushVision()

        # first_grid = vision.debug_mode("screenshots/screenshot18.png")
        
        first_grid = vision.realtime_mode(True)
        # Simular desde la primera grilla hasta el final
        agent = SmartAgent(first_grid)
        if agent.game_state is None:
            continue
        else:
            winner_state : GameState = agent.simulate()
            #for i in winner_state.action_history:
            #    print(i.get_readable())
            key_simulator = KeyboardSimulator(winner_state)
            
            asyncio.run(key_simulator.execute_actions())
        


if __name__ == "__main__":
    main()

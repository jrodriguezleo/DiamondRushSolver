from diamond_rush_vision import DiamondRushVision
from smart_agent import SmartAgent
from keyboard_simulator import KeyboardSimulator
from game_state import GameState
import asyncio

# TODO recortar assets en resolucion de portatil 1366x768

def main():
    while True:
        vision = DiamondRushVision()

        # first_grid = vision.debug_mode("screenshots/screenshot18.png")
        
        first_grid = vision.realtime_mode(show_image=True)
        # Simular desde la primera grilla hasta el final
        agent = SmartAgent(first_grid)
        # Debug
        print("Grid inicial capturado, iniciando simulacion del agente...")
        print(first_grid)
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

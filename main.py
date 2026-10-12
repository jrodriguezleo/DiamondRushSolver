import time
import asyncio
from diamond_rush_vision import DiamondRushVision
from smart_agent import SmartAgent
from keyboard_simulator import KeyboardSimulator

def main():
    print("Cambia al navegador con el juego completo visible. Empiezo en 8 segundos...")
    time.sleep(8)
    vision = DiamondRushVision()
    first_grid = vision.realtime_mode(show_image=False)
    print("Grid inicial capturado, iniciando simulacion del agente...")
    agent = SmartAgent(first_grid)
    if agent.game_state is None:
        print("No se encontro al jugador en la captura. Revisa que el juego este completo y visible.")
        return
    winner_state = agent.simulate()
    if winner_state is None:
        print("El agente no encontro solucion.")
        return
    KeyboardSimulator(winner_state)
    asyncio.run(KeyboardSimulator(winner_state).execute_actions())

if __name__ == "__main__":
    main()

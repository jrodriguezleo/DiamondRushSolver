

from typing import List
from cell import Cell
from rock_simulation import RockSimulation
from game_state import GameState
from game_action import GameAction
from collections import deque

class SmartAgent:
    # El agente define la estrategia a seguir para resolver el juego
    def __init__(self, first_grid : List[List[Cell | None]]):
        player_pos = None
        for row in range(0,len(first_grid)):
            for col in range(0,len(first_grid[row])):
                if first_grid[row][col] != None and first_grid[row][col].cell_type=="player":
                    player_pos = [row, col]
        if player_pos is None:
            game_state = None
            self.game_state = None
        else:
            game_state = GameState(first_grid, player_pos, 0, [])
            self.game_state = game_state
        

    def simulate(self):
        # Esta funcion se encarga de simular el juego con un loop
        # Se devuelve el estado del juego al lograr la meta
        # En cada paso se guarda la accion tomaada por cada estado de juego
        # Se tiene una pila de acciones en orden para ir de forma greedy a la solucion pero si no se puede hacer la accion
        # se hace la siguiente y asi, si no hay ninguna accion se considera unn camino bloqueado y se devuelve hasta el ultimo estado viable
        # Retorna el game state donde se gana junto con sus acciones
        if self.game_state is None:
            print("No se pudo encontrar la posicion del jugador en el grid inicial")
            return None
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

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
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
                case "get_key":
                    # Mover pj al key, quitar key de la grilla.
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    next_state.player_has_key = True  # El jugador ahora tiene la llave
                    # Se borra el key y se cambia a terrain
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

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
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
                    print("Llego a nuevo estado get key")
                case "open_door":
                    # Mover pj al key, quitar key de la grilla.
                    next_state : GameState = simulated_game_state.clone()
                    
                    next_state.game_state += 1
                    next_state.player_has_key = False  # El jugador ahora no tiene la llave
                    # Se borra el key y se cambia a terrain
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

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = simulated_game_state.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
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
                    print("Llego a nuevo estado open door")
                case "push_rock":
                    # Actualizar el estado del juego con la simulacion de la roca
                    rock_simulation : RockSimulation = simulated_action
                    next_state : GameState = simulated_game_state.clone()
                    next_state.game_state += 1
                    # Actualizar la grilla con el estado de la roca
                    next_state.grid = rock_simulation.grid

                    # Se borra el personaje y se cambia a terrain, debe hacerse solo si es la primera vez
                    pr, pc = rock_simulation.player_pos
                    if next_state.grid[pr][pc].cell_type == "player":
                        player_replaced = Cell(
                            coordinates=rock_simulation.player_pos, 
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
                    
                    next_state.player_pos = rock_simulation.player_pos
                    # Actualizar el estado del juego
                    next_state.check_objects_in_grid()
                    # Añadir acciones anteriores
                    for ac in simulated_action.action_history:
                        next_state.action_history.append(ac)
                    # Guardar nuevo estado en la pila
                    state_stack.append(next_state)

                    simulated_game_state = next_state
                    print("Llego a nuevo estado rock push")
            
                case "go_spike":
                    next_state: GameState = simulated_game_state.clone()
                    next_state.game_state += 1

                    r, c = simulated_action.coordinates
                    cell = next_state.grid[r][c]

                    # Activar spike: cambiar tipo y propiedades
                    if cell and cell.cell_type == "spike":
                        cell.cell_type = "spike-up"
                        cell.weight = 100000

                    # Actualizar posición del jugador
                    next_state.player_pos = simulated_action.coordinates

                    # Añadir acción al historial
                    next_state.action_history.append(simulated_action)

                    # Actualizar objetos en el grid, si tienes esta función para actualizar estados
                    next_state.check_objects_in_grid()

                    # Guardar nuevo estado en la pila
                    state_stack.append(next_state)

                    simulated_game_state = next_state
                    print("Llego a nuevo estado go spike")
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
            simulated_action : GameAction | RockSimulation = simulated_game_state.get_next_action()
        print("Se encontró simulacion hasta go ladder")
        return simulated_game_state
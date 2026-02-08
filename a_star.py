

from cell import Cell


class AStar:
    def __init__(self, start: tuple[int, int], goal: tuple[int, int], grid: list[list['Cell']]):
        self.start = start
        self.goal = goal
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.open_set = [(start[0], start[1])]  # Usamos tuplas para evitar problemas de mutabilidad
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
        
        if up is not None and up.walkable:
            neighbors.append(up.coordinates)
        if down is not None and down.walkable:
            neighbors.append(down.coordinates)
        if left is not None and left.walkable:
            neighbors.append(left.coordinates)
        if right is not None and right.walkable:
            neighbors.append(right.coordinates)
        
        return neighbors

    def search(self):
        self.g_score[self.start[0]][self.start[1]] = 0
        self.f_score[self.start[0]][self.start[1]] = self.heuristic(self.start, self.goal)

        while self.open_set:
            current = min(self.open_set, key=lambda x: self.f_score[x[0]][x[1]])
            current = (current[0], current[1])  # Aseguramos que sea un tuple
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
                neighbor = (neighbor[0], neighbor[1])  # Aseguramos que sea un tuple
                if neighbor in self.closed_set:
                    continue

                tentative_g = self.g_score[current[0]][current[1]] + self.grid[neighbor[0]][neighbor[1]].weight

                if neighbor not in self.open_set:
                    self.open_set.append(neighbor)
                elif tentative_g >= self.g_score[neighbor[0]][neighbor[1]]:
                    continue
                
                self.came_from[neighbor[0]][neighbor[1]] = [current[0],current[1]]
                self.g_score[neighbor[0]][neighbor[1]] = tentative_g
                self.f_score[neighbor[0]][neighbor[1]] = tentative_g + self.heuristic(neighbor, self.goal)

        return None
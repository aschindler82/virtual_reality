#see http://www.redblobgames.com/pathfinding/a-star/implementation.html
from __future__ import print_function
import heapq
import time
import math

from distutils.dist import warnings

class PriorityQueue:
    def __init__(self):
        self.elements = []
    
    def empty(self):
        return len(self.elements) == 0
    
    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))
    
    def get(self):
        return heapq.heappop(self.elements)[1]


class SquareGrid:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.walls = []
    
    def in_bounds(self, nId):
        (x, y) = nId
        return 0 <= x < self.width and 0 <= y < self.height
    
    def passable(self, nId):
        return nId not in self.walls
    
    def neighbors(self, nId):
        (x, y) = nId
        # get neighbors, including diagonals
        results = [(x+1, y), (x, y-1), (x-1, y), (x, y+1),  (x+1, y+1), (x-1, y-1), (x+1, y-1), (x-1, y+1)]
        #results = [(x+1, y), (x, y-1), (x-1, y), (x, y+1)]
        if (x + y) % 2 == 0: results.reverse() # aesthetics
        results = filter(self.in_bounds, results)
        results = filter(self.passable, results)
        return results

class GridWithWeights(SquareGrid):
    def __init__(self, width, height):
        #super().__init__(width, height)
        SquareGrid.__init__(self, width, height)
        self.weights = {}
    
#    def cost(self, from_node, to_node):
#        return self.weights.get(to_node, 1)
    
    def cost(self, from_node, to_node):
        xF, yF = from_node
        xT, yT = to_node
        # cost for diagonal
        if abs(xF-xT) == 1 and abs(yF-yT) == 1:
            return math.sqrt(2)
        # cost for neighboring node
        else:
            return 1

def draw_tile(graph, nId, style, width):
    r = "."
    if 'number' in style and nId in style['number']: r = "%d" % style['number'][nId]
    if 'point_to' in style and style['point_to'].get(nId, None) is not None:
        (x1, y1) = nId
        (x2, y2) = style['point_to'][nId]
        if x2 == x1 + 1: r = "\u2192"
        if x2 == x1 - 1: r = "\u2190"
        if y2 == y1 + 1: r = "\u2193"
        if y2 == y1 - 1: r = "\u2191"
    if 'start' in style and nId == style['start']: r = "A"
    if  'goal' in style and nId == style['goal']:  r = "Z"
    if  'path' in style and nId in style['path']:  r = "@"
    if nId in graph.walls: r = "#" * width
    return r

def draw_grid(graph, width=2, **style):
    for y in range(graph.height):
        for x in range(graph.width):
            print("%%-%ds" % width % draw_tile(graph, (x, y), style, width), end="")
        print ()


def reconstruct_path(came_from, start, goal):
    current = goal
    path = [current]
    while current != start:
        try:
            current = came_from[current]
            path.append(current)
        except:
            warnings.warn("Skipped this path node!" )
            
    path.append(start) # optional
    path.reverse() # optional
    return path

#def heuristic(a, b):
# Manhatten distance
#    (x1, y1) = a
#    (x2, y2) = b
#    return abs(x1 - x2) + abs(y1 - y2)

def heuristic(a, b):
    # Euclidean distance
    (x1, y1) = a
    (x2, y2) = b
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    return math.sqrt(dx*dx+dy*dy)

def a_star_search(graph, start, goal):
    frontier = PriorityQueue()
    frontier.put(start, 0)
    came_from = {}
    cost_so_far = {}
    came_from[start] = None
    cost_so_far[start] = 0
    
    # get t0 to stop after n seconds if search takes too long
    #t0 = time.time()
    while not frontier.empty():
                        
        current = frontier.get()
        
        if current == goal:
            break
        
        for nnext in graph.neighbors(current):            
            new_cost = cost_so_far[current] + graph.cost(current, nnext)
            if nnext not in cost_so_far or new_cost < cost_so_far[nnext]:
                
                # check whether we reached time limit
                #if time.time() - t0 > 60:           
                #    return -1
                
                cost_so_far[nnext] = new_cost
                priority = new_cost + heuristic(goal, nnext)
                frontier.put(nnext, priority)
                came_from[nnext] = current
    
    return came_from, cost_so_far
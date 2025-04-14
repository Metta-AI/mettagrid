from mettagrid.config.room.cognitive_evals.terraingen import TerrainGen, Layer
import math

w = 40
h = 95
sym = {
    "agent.agent": "\033[92m@\033[0m", # draws in green
    "agent.prey": "\033[0;33mp\033[0m", # draws in brown
    "agent.predator": "\033[0;31mP\033[0m", # draws in red
    "altar": "\033[1;33ma\033[0m", # draws in yellow
    "converter": "\033[0;34mc\033[0m", # draws in blue
    "generator": "\033[1;32mg\033[0m", # draws in light green
    "mine": "\033[0;35mm\033[0m", # draws in purple
    "wall": "W",
    "empty": " ",
    "block": "b\033[0m",
    "lasery": "L\033[0m",
}

def fn1(x,y, **args):
    octave = [4,4]
    xi = abs(x-0.5*y)*(x-0.5)*(y-0.5) * octave[0]
    yi = abs(x-0.5*y)*(x-0.5)*(y-0.5) * octave[1]

    return (xi, yi)

def fn2(x,y, P, **args):
    octave = [4,4]
    xi = (x-0.5) * octave[0]
    yi = (y-0.5) * octave[1]

    a = (math.pi / 4 * (math.sqrt(xi ** 2 + yi ** 2) * (2+P)))
    xi, yi = xi * math.cos(a) - yi * math.sin(a), yi * math.cos(a) + xi * math.sin(a)

    return (xi, yi)

def fn3(x,y, **args):
    octave = [4,4]
    if x%7 == 0 or y%3 == 0:
        xi, yi = 1*x, 4*y
    else:
        xi, yi = -2*x, -5*y

    return (xi*octave[0], yi*octave[1])

layers = [Layer(fn1,0.3),Layer(fn2, 1.5),Layer(fn3, 3)]

world_map = TerrainGen(w,h, layers, sampling_params={'P':1}, scenario='haul')._build()

for y in range(w):
    print(" ".join([sym[s] for s in world_map[y]]))


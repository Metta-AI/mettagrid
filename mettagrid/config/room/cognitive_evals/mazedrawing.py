from mettagrid.config.room.cognitive_evals.terraingen import TerrainGen, Layer
import math
import numpy as np

from PIL import Image
import glob
import os

w = 100
h = 100
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

def fn4(x, y, P, **args):
    octave = [4,6]
    xi = (x-0.5) * octave[0]
    yi = (y-0.5) * octave[1]
    a = P
    xi, yi = np.sinc((xi**2+yi**2)*math.sin(math.atan(float(x/(y+0.01)))*2*math.pi/a)),np.sinc(xi**2+yi**2)*math.sin(math.atan(float(x/(y+0.01)))*2*math.pi/a)
    return (xi, yi)

def fn5(x,y, M, **args):
    octave = [20,20]
    xi = (x-M)**2 * octave[0]
    yi = (y-0.5)**2 * octave[1]

    return (xi, yi)

def fn6(x,y, O, **args):
    octave = [30,30]
    alpha = 2*math.pi*O
    cs = math.cos(alpha)
    sn = math.sin(alpha)

    xi = (cs*(x-0.5) + sn*(y-0.5))
    yi = (-sn*(x-0.5) + cs*(y-0.5))

    xi, yi = xi**2 * 2, yi**2 * 2

    xi, yi = (cs*(xi-0.5) - sn*(yi-0.5)) * octave[0], (sn*(xi-0.5) + cs*(yi-0.5)) * octave[1]
 
    return (xi, yi)

def fn7(x,y, O, **args):
    octave = [10,5]
    alpha = 2*math.pi*O
    cs = math.cos(alpha)
    sn = math.sin(alpha)
    xc, yc = 0.1, 0.3
    xi, yi = (cs*(x-0.5+xc) + sn*(y-0.5+yc)), (-sn*(x-0.5+xc) + cs*(y-0.5+yc))
    a = 0
    b = 0
    beta = 2*math.atan2((yi+b), (xi+a))
    csb = math.cos(beta)
    snb = math.sin(beta)
    xi, yi = (csb*(xi+a) - snb*(yi+b)), (snb*(xi+a) + csb*(yi+b))

    xi, yi = (cs*(xi-0.5+xc) - sn*(yi-0.5+yc)) * octave[0], (sn*(xi-0.5+xc) + cs*(yi-0.5+yc)) * octave[1]
 
    return (xi, yi)
    

layers = [Layer(fn1,0.3),Layer(fn2, 1.5),Layer(fn3, 6)]
layers = [Layer(fn4, 2),Layer(fn5, 2)]
layers = [Layer(fn5, 0),Layer(fn7, 2)]

# world_map = TerrainGen(w,h, layers, sampling_params={'P':1}, scenario='maze', seed=11)._build()

# for y in range(w):
#     print(" ".join([sym[s] for s in world_map[y]]))

'''
This code generates a gif from the set of generated maps
additional requirements: pip install pillow
'''

def make_gif():
    frames = [Image.open(image) for image in sorted(glob.glob('/home/catnee/mettagrid/giffactory/*.png'), key=os.path.getmtime)]
    frame_one = frames[0]
    frame_one.save("my_awesome.gif", format="GIF", append_images=frames,
               save_all=True, duration=100, loop=0)

N = 100
for i in range(N):
    print(f'{i} step out of {N}')
    t = 0.01*(1.08**i)
    m = 0.01*i
    room = TerrainGen(w,h, layers, sampling_params={'M':t, 'O':m}, scenario='maze', seed=11)._build()
    room = (room != 'wall')
    Image.fromarray(room).resize((400, 400)).save(f'giffactory/{i}.png')

make_gif()
print(f'{N} step out of {N}')
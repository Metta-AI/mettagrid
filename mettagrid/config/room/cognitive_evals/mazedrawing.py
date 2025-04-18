from mettagrid.config.room.cognitive_evals.terraingen import TerrainGen, Layer
from mettagrid.map.mapgen import MapGen
from omegaconf import DictConfig, OmegaConf
import math
import numpy as np
import hydra
from mettagrid.resolvers import register_resolvers

from PIL import Image
import glob
import os

w = 180
h = 90
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
register_resolvers()
config = OmegaConf.load('/home/catnee/mettagrid/configs/game/map_builder/mapgen_terrain_symmetry.yaml')

if OmegaConf.select(config, "root") is not None:
    root = config.root
else:
    print("No root config found, using default maze")
    
world_map = MapGen(w,h,root = root).build()

# for y in range(world_map.shape[0]):
#     print(" ".join([sym[s] for s in world_map[y]]))

Image.fromarray((world_map == 'empty')).resize((400, 400*h//w)).save('maze.png')
'''
This code generates a gif from the set of generated maps
additional requirements: pip install pillow
'''

# def make_gif():
#     frames = [Image.open(image) for image in sorted(glob.glob('/home/catnee/mettagrid/giffactory/*.png'), key=os.path.getmtime)]
#     frame_one = frames[0]
#     frame_one.save("my_awesome.gif", format="GIF", append_images=frames,
#                save_all=True, duration=100, loop=0)

# N = 100
# for i in range(N):
#     print(f'{i} step out of {N}')
#     t = 0.01*(1.08**i)
#     m = 0.01*i
#     room = TerrainGen(w,h, layers, sampling_params={'M':t, 'O':m}, scenario='maze', seed=11)._build()
#     room = (room != 'wall')
#     Image.fromarray(room).resize((400, 400)).save(f'giffactory/{i}.png')

# make_gif()
# print(f'{N} step out of {N}')
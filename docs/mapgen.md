# Map generation

## S3 maps

To produce maps in bulk and store them in S3, use the following commands:

### Creating maps

```bash
python -m tools.mapgen game/map_builder=mapgen_auto mapgen=s3 mapgen.s3_dir=s3://BUCKET/DIR
```

`mapgen_auto` builder is an example. You can use any config from `configs/game/map_builder/`, or write your own.

**Replace `s3://BUCKET/DIR` with the S3 directory to store the maps.**

To create maps in bulk, you can run this in a loop, or use the Hydra's `-m` flag with a range parameter (`x='range(1,100)'`) to [run multiple instances](https://hydra.cc/docs/tutorials/basic/running_your_app/multi-run/).

### Loading maps

You can load a random map from an S3 directory by using `mettagrid.map.load_random.LoadRandom` as a map builder.

Check out `configs/game/map_builder/load_random.yaml` for an example config and for how to tune the number of agents in the map.

Preview a random map:

```bash
python -m tools.mapgen game/map_builder=load_random game.map_builder.dir=...
```

### Indexing maps

Optionally, you can index your maps to make loading them faster.

Index is a plain text file that lists URIs of all the maps. You can assemble it manually, or use the following script:

```bash
python -m tools.index_s3_maps index_s3_maps.dir=s3://BUCKET/DIR index_s3_maps.target=s3://BUCKET/DIR/index.txt
```

`index_s3_maps.target` is optional. If not provided, the index will be saved to `{index_s3_maps.dir}/index.txt`.

You can then use `mettagrid.map.load_random_from_index.LoadRandomFromIndex` to load a random map from the index.

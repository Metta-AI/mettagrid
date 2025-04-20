# Map generation

## S3 maps

To produce maps in bulk and store them in S3, use the following commands:

### Creating maps

```bash
python -m tools.mapgen game/map_builder=mapgen_auto mapgen=s3 mapgen.s3_dir=MY_DIR
```

`mapgen_auto` builder is an example. You can use any config from `configs/game/map_builder/`, or write your own.

**Replace `MY_DIR` with the S3 directory to store the maps.**

The directory will be created under `s3://softmax-public/maps/` by default; see `configs/mapgen/s3.yaml` for details.

To create maps in bulk, you can run this in a loop, or use the Hydra's `-m` flag with a range parameter (`x='range(1,100)'`) to [run multiple instances](https://hydra.cc/docs/tutorials/basic/running_your_app/multi-run/).

### Indexing maps

The common scenario is to load a random map from the set of pre-generated maps.

To do this, you need to create an index file.

Index is a plain text file that lists all the maps. You can assemble it manually, or use the following script:

```bash
python -m tools.index_s3_maps index_s3_maps.dir=... index_s3_maps.target=...
```

`index_s3_maps.target` is optional. If not provided, the index will be saved to `{index_s3_maps.dir}/index.txt`.

### Loading maps

By now, all your maps are stored in S3. You can load a random map by using `mettagrid.map.load_random.LoadRandom` as a map builder.

Check out `configs/game/map_builder/load_random.yaml` for an example config.

Preview a random map:

```bash
python -m tests.mapgen game/map_builder=load_random game.map_builder.index_uri=...
```

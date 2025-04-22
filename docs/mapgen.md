# Map generation

## S3 maps

To produce maps in bulk and store them in S3, use the following commands:

### Creating maps

```bash
python -m tools.mapgen --output-dir=s3://BUCKET/DIR ./configs/game/map_builder/mapgen_auto.yaml
```

`mapgen_auto` builder is an example. You can use any YAML config that can be parsed by OmegaConf.

**Replace `s3://BUCKET/DIR` with the S3 directory to store the maps.**

To create maps in bulk, you can run this in a loop, or use `--count` option to generate multiple maps at once.

### Loading maps

You can load a random map from an S3 directory by using `mettagrid.map.load_random.LoadRandom` as a map builder.

Check out `configs/game/map_builder/load_random.yaml` for an example config and for how to tune the number of agents in the map.

Preview a random map:

```bash
python -m tools.mapgen ./configs/game/map_builder/load_random.yaml --overrides='dir=s3://BUCKET/DIR'
```

### Indexing maps

Optionally, you can index your maps to make loading them faster.

Index is a plain text file that lists URIs of all the maps. You can assemble it manually, or use the following script:

```bash
python -m tools.index_s3_maps --dir=s3://BUCKET/DIR --target=s3://BUCKET/DIR/index.txt
```

`--target` is optional. If not provided, the index will be saved to `{--dir}/index.txt`.

You can then use `mettagrid.map.load_random_from_index.LoadRandomFromIndex` to load a random map from the index.

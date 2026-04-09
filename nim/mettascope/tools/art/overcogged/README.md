## Overcogged ArtGen

This folder contains the Overcogged ArtGen specs that replace the older
hand-authored station/resource image set with renders from the full ArtGen pipeline:

1. prompt + reference image
2. concept image generation
3. Tripo 3D model generation
4. final sprite render

Overcogged now uses the shared mainline terrain and wall rendering, so this
ArtGen tree only owns the station sprites and resource icons.

Render the source set:

```bash
cd packages/mettagrid/nim/mettascope
nim r -d:release tools/art/artgen.nim \
  --input=tools/art/overcogged/artin \
  --output=tools/art/overcogged/artout \
  --keepConcept \
  --keep3d \
  --verbose
```

Promote the rendered outputs into the canonical game asset directories and
regenerate the score-panel/minimap derivatives:

```bash
cd ../../../../..
python3 scripts/assetgen/sync_overcogged_artgen_assets.py
```

Then rebuild the atlas metadata:

```bash
cd packages/mettagrid/nim/mettascope
nim r -d:release tools/gen_atlas.nim
```

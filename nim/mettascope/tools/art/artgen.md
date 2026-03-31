# ArtGen

ArtGen is a folder-driven art pipeline for game assets.

It reads markdown specs from `artin/`, generates or reuses intermediate assets
in `arttmp/`, and writes final sprite outputs to `artout/`.

The current pipeline is:

1. Build a prompt from inherited folder context and the asset markdown body.
2. Generate a concept image with an image provider.
3. Turn that concept image into a 3D model with Tripo.
4. Render that 3D model into one or more final sprite views with the GLTF
   renderer.

ArtGen preserves the folder structure from `artin` when writing to `artout`.
It skips outputs that already exist unless `--force` is used.

## Goal

ArtGen is meant to make a large body of art editable as normal text files.

Each asset spec should answer:

- What should be generated.
- What shared style rules apply.
- What size and format should be written.
- What provider or model should be used.
- What render settings should be used for the 3D sprite pass.
- Whether multiple directional variants should be produced.

## Folder Layout

The tool expects these working folders next to `artgen.nim`:

```text
artin/
artout/
arttmp/
```

Typical layout:

```text
artin/
  _.md
  cogs/
    _.md
    default.md
    aligner.md
    scrambler.md
    miner.md
    scout.md
    herbivore.md
    carnivore.md
  buildings/
    _.md
    aligner_station.md
    carnivore_station.md
    carbon_extractor.md
    chest.md
    dome.md
    germanium_extractor.md
    herbivore_station.md
    hub.md
    junction.md
    landing_pad.md
    miner_station.md
    oil_depot.md
    oxygen_extractor.md
    pyramid.md
    scrambler_station.md
    silicon_extractor.md
  resources/
    _.md
    carbon.md
    energy.md
    germanium.md
    heart.md
    oxygen.md
    silicon.md
```

Outputs are written to matching relative paths:

```text
artout/
  cogs/
  buildings/
  resources/
```

Intermediate files are written under `arttmp/`:

- concept images as `*.concept.png`
- generated 3D models
- an `index.html` preview for scanning outputs quickly

## File Types

### Asset Specs

Normal `.md` files describe one asset.

Examples:

- `scout.md`
- `heart.md`
- `hub.md`

Each one contains plain English prompt text plus optional `@key value` command
lines.

### Folder Context

Each folder may also contain:

- `_.md`

This file is not rendered directly. It provides shared prompt text and shared
arguments for that folder and all child folders.

## Prompt Assembly

For each asset, ArtGen assembles the final prompt from:

1. inherited `_.md` prefix sections
2. the asset markdown body
3. inherited `_.md` postfix sections

Folder context files support:

```md
# Prefix
Isometric RTS style asset.

# Postfix
One object only.
No text.
```

The same `_.md` files can also carry shared render arguments, for example:

```md
@window 128x128
@multisample 4
@quit true
@transparent true
@projection ortho

@rotx -35
@roty 45
@rotz 0
@zoom 0.75

@ambient_light_color FF6A6A
@ambient_light_strength 0.1

@lightx 1
@lighty -1
@lightz -1
@light_color F2F3FF
@light_strength 1.5

@rim_light_color FF6A6A
@rim_light_strength 2.0
```

## Markdown Style

Most of the markdown should stay plain English:

```md
A small glowing blue orb pickup.
Readable silhouette.
Soft stylized shading.
Centered composition.
```

Keep prompts short, concrete, and visually specific.

## Supported Commands

ArtGen reads `@key value` lines from both asset files and inherited `_.md`
files. Asset-local values override inherited ones.

`@provider` must be defined in the asset file or an inherited `_.md` file.

### Output and Generation

- `@size 256x256`
- `@format png`
- `@provider gemini|openai|xai|stability|claude`
- `@model ...`
- `@generationsize ...`
- `@directions 1|4|8`
- `@inspiration path/to/file.png`
- `@reference path/to/file.png`

`@directions` produces multiple output views from one generated model. The
variants are:

- `1`: one default view
- `4`: `n`, `e`, `s`, `w`
- `8`: `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw`

### Render Settings

These values are passed into the GLTF sprite renderer:

- `@window WxH`
- `@multisample N`
- `@quit true|false`
- `@transparent true|false`
- `@projection perspective|ortho`
- `@rotx DEGREES`
- `@roty DEGREES`
- `@rotz DEGREES`
- `@zoom NUMBER`
- `@lightx NUMBER`
- `@lighty NUMBER`
- `@lightz NUMBER`
- `@light_color HEX`
- `@light_strength NUMBER`
- `@ambient_light_color HEX`
- `@ambient_light_strength NUMBER`
- `@rim_light_color HEX`
- `@rim_light_strength NUMBER`

Per-asset rotation is especially useful for buildings, where each file can set
a slightly different `@rotY`.

## Caching and Reuse

ArtGen supports reuse of intermediate outputs:

- `--keepConcept` reuses existing concept images in `arttmp/`
- `--keep3d` reuses existing generated 3D models in `arttmp/`
- existing final outputs in `artout/` are skipped unless `--force` is used

This makes it possible to iterate on rendering without regenerating the concept
or the 3d model.

## CLI

Run the tool with:

```shell
nim r tools/art/artgen.nim \
  --input=tools/art/artin \
  --output=tools/art/artout \
  --verbose
```

Supported CLI flags:

- `--input=DIR`
- `--output=DIR`
- `--force`
- `--keep3d`
- `--keepConcept`
- `--verbose`

Per-asset settings such as `@provider`, `@model`, `@directions`, and all GLTF
render controls are intentionally file-driven and should be set in the
markdown specs or inherited `_.md` files, not on the CLI.

## Example Asset

```md
A chest building.
Storage structure for gathered materials.
Reinforced container body with heavy latches, side ribs, and access hatch.
Industrial orange accents and secure lock details.
Feels solid, useful, and easy to read as storage.

@provider gemini
@zoom 0.50
@rotY 18
```

## Notes

- Final outputs are always PNG right now.
- ArtGen writes an `arttmp/index.html` preview to help review generated output
  sets quickly.

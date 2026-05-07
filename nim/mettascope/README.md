# Mettascope

## Building

Install Nim `2.2.6` if you haven't already.

- [Mac] `brew install nim`
- [Linux] `sudo apt install nim`
- [Windows] [Downloads](https://nim-lang.org/install.html)

Make sure you are using Nim `2.2.6`.

```
nim --version
```

Build the dynamic link library:

```
cd mettascope
./build.sh
```

Build the browser bundle:

```
cd packages/mettagrid/nim/mettascope
nimble wasm
```

The browser bundle is written to `dist/`. It is generated from the checked-in
Nim sources and assets, and should not be committed.

## Running

```
./tools/run.py arena.play mettascope=true
```

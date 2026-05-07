version     = "0.0.3"
author      = "Softmax"
description = "Visualization of the MettaGrid environment."
license     = "MIT"

srcDir = "src"

requires "nim >= 2.2.4"
requires "cligen >= 1.9.0"
requires "fidget2 >= 0.1.2"
requires "genny >= 0.1.1"
requires "fluffy >= 0.1.0"

task bindings, "Generate bindings":

  proc compile(libName: string) =
    exec "nim c -d:release -d:ssl --app:lib --tlsEmulation:off --out:" & libName & " --outdir:bindings/generated bindings/bindings.nim"
    # Post-process generated Python file: fix cstring -> c_char_p for Python ctypes compatibility
    let pyFile = "bindings/generated/mettascope.py"
    var content = readFile(pyFile)
    content = content.replace("cstring)", "c_char_p)")
    writeFile(pyFile, content)

  when defined(windows):
    compile "mettascope.dll"
  elif defined(macosx):
    compile "libmettascope.dylib"
  else:
    compile "libmettascope.so"

task wasm, "Build browser bundle":
  exec "nimby sync -g nimby.lock"
  exec "nim c -d:emscripten -d:release src/mettascope.nim"
  for path in [
    "dist/mettascope.html",
    "dist/mettascope.js",
    "dist/mettascope.wasm",
    "dist/mettascope.data",
  ]:
    if not fileExists(path):
      quit("Missing " & path)
  exec "ls -lh dist/"

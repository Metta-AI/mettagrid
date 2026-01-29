version     = "0.0.3"
author      = "Softmax"
description = "Visualization of the MettaGrid environment."
license     = "MIT"

srcDir = "src"

requires "nim >= 2.2.4"
requires "cligen >= 1.9.0"
requires "fidget2 >= 0.1.2"
requires "genny >= 0.1.1"

task bindings, "Generate bindings":

  proc compile(libName: string) =
    exec "nim c -d:release --app:lib --tlsEmulation:off --out:" & libName & " --outdir:bindings/generated bindings/bindings.nim"
    # Post-process generated Python file: fix cstring -> c_char_p for Python ctypes compatibility
    let pyFile = "bindings/generated/vibescope.py"
    var content = readFile(pyFile)
    content = content.replace("cstring)", "c_char_p)")
    writeFile(pyFile, content)

  when defined(windows):
    compile "vibescope.dll"
  elif defined(macosx):
    compile "libvibescope.dylib"
  else:
    compile "libvibescope.so"

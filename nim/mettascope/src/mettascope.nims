import os

if defined(emscripten):
  --nimcache:tmp
  --os:linux
  --cpu:wasm32
  --cc:clang
  when defined(windows):
    --clang.exe:emcc.bat
    --clang.linkerexe:emcc.bat
    --clang.cpp.exe:emcc.bat
    --clang.cpp.linkerexe:emcc.bat
  else:
    --clang.exe:emcc
    --clang.linkerexe:emcc
    --clang.cpp.exe:emcc
    --clang.cpp.linkerexe:emcc
  --listCmd

  --gc:orc
  --exceptions:goto
  --define:noSignalHandler
  --debugger:native

  let msRoot = currentSourcePath().parentDir().parentDir()
  let distDir = msRoot / "dist"
  let dataDir = msRoot / "data"
  let shellFile = msRoot / "src" / "mettascope" / "shell.html"

  if dirExists(distDir):
    rmDir(distDir)
  mkDir(distDir)

  switch(
    "passL",
    (
      " -o " & distDir / "mettascope.html" &
      " --preload-file " & dataDir & "@packages/mettagrid/nim/mettascope/data" &
      " --shell-file " & shellFile &
      " -s ASYNCIFY" &
      " -s FETCH" &
      " -s USE_WEBGL2=1" &
      " -s MAX_WEBGL_VERSION=2" &
      " -s MIN_WEBGL_VERSION=1" &
      " -s FULL_ES3=1" &
      " -s GL_ENABLE_GET_PROC_ADDRESS=1" &
      " -s ALLOW_MEMORY_GROWTH" &
      " --profiling"
    )
  )

when not defined(debug):
  --define:noAutoGLerrorCheck
  --define:release

--define:ssl
--define:profile
--define:nimTypeNames

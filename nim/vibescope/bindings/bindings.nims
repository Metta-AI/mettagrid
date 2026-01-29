--define:gennyPython

switch("app", "lib")
switch("tlsEmulation", "off")
when defined(windows):
  switch("out", "vibescope.dll")
elif defined(macosx):
  switch("out", "libvibescope.dylib")
else:
  switch("out", "libvibescope.so")
switch("outdir", "bindings/generated")

when not defined(release):
  --define:noAutoGLerrorCheck
  --define:release

import
  slappy

proc playSound*(filePath: string) =
  ## Minimalist sound playing function.
  ## Used only for temporary testing, until a proper sound architecture is defined for the project.
  let s = newSound(filePath)
  discard s.play()


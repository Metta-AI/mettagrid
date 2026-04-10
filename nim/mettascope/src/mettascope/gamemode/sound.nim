import
  std/[os, math],
  slappy,
  ../[common, replays],
  ./team

template soundPath*(fileName: string): string =
  dataDir / "sounds" / fileName

proc playSound*(fileName: string, gain: float32 = 1.0) =
  ## Minimalist sound playing function.
  ## Used only for temporary testing, until a proper sound architecture is defined for the project.
  if soundMuted: return
  let filepath = soundPath(fileName)
  if not filePath.fileExists(): return
  let s = newSound(filePath)
  var source = s.play()
  source.gain = gain

proc playEntitySound*(obj: Entity) =
  if obj.isNil: return
  if soundMuted: return
  playSound(obj.typeName.addFileExt("wav"))

proc playScrubberStepSound*(t :SomeFloat) =
  if soundMuted: return
  let step = floor(t * replay.maxSteps.float).uint32
  if step == soundScrubberPos: return
  # Make sure only one soundScrubber Sound is ever created, and only one sound is ever playing at once.
  if soundScrubber.isNil: soundScrubber = newSound(soundPath("UIscrub1.wav"))
  if not soundScrubberSource.isNil and soundScrubberSource.playing(): return
  # Play the click once and update scrubberPos.
  soundScrubberPos = step
  soundScrubberSource = soundScrubber.play()

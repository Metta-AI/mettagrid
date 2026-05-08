import
  std/[os, math, strutils],
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
  try:
    let s = newSound(filePath)
    var source = s.play()
    source.gain = gain
  except Exception as e:
    echo "Error playing sound: ", fileName, " ", e.getStackTrace()
    return

proc playEntitySound*(obj: Entity) =
  if obj.isNil: return
  if soundMuted: return
  let fileName = obj.typeName.addFileExt("wav")
  if fileName.fileExists():
    playSound(fileName)
  else:
    playSound("entity_selection".addFileExt("wav"))

proc playAgentSounds*(prevStep, newStep: int) =
  ## Play sounds for the selected agent when the replay steps forward.
  if soundMuted: return
  if selected.isNil: return
  if replay.isNil: return
  if newStep <= prevStep: return
  if not selected.isAgent: return
  if not selected.alive.at(newStep): return

  let
    prevRig = getAgentRigName(selected, prevStep)
    newRig = getAgentRigName(selected, newStep)
  if prevRig != newRig:
    playSound(addFileExt("cogchange_" & newRig, "wav"), gain = 0.2)

  let
    prevTeam = getEntityTeamIndexAtStep(selected, prevStep)
    newTeam = getEntityTeamIndexAtStep(selected, newStep)
  if prevTeam != newTeam and newTeam >= 0:
    playSound(addFileExt("alignment_" & getTeamName(newTeam), "wav"))

  let energyId = replay.itemNames.find("energy")
  if energyId >= 0:
    var prevEnergy, newEnergy: int
    for item in selected.inventory.at(prevStep):
      if item.itemId == energyId:
        prevEnergy = item.count
    for item in selected.inventory.at(newStep):
      if item.itemId == energyId:
        newEnergy = item.count
    if newEnergy < prevEnergy:
      playSound("cogLoseEnergy.wav")

  # Detect inventory gains/losses (excluding energy) for mine/pickup/drop sounds.
  const ExtractorResources = ["oxygen", "carbon", "germanium", "silicon"]
  var delta, extractorDelta: int
  for item in selected.inventory.at(newStep):
    if item.itemId == energyId: continue
    var prev = 0
    for p in selected.inventory.at(prevStep):
      if p.itemId == item.itemId:
        prev = p.count
        break
    let diff = item.count - prev
    delta += diff
    if diff > 0 and replay.itemNames[item.itemId] in ExtractorResources:
      extractorDelta += diff
  if delta > 0:
    if extractorDelta > 0:
      playSound("mine" & $(newStep mod 3) & ".wav")
    else:
      playSound("pickup" & $(newStep mod 3) & ".wav")
  elif delta < 0:
    playSound("drop" & $(newStep mod 2) & ".wav")

  let actionId = selected.actionId.at(newStep)
  if actionId >= 0 and actionId < replay.actionNames.len:
    let actionName = replay.actionNames[actionId]
    if actionName.startsWith("change_vibe_"):
      playSound("vibechange.wav")
    elif actionId == replay.attackActionId or
        actionName == "attack_nearest":
      playSound("attack" & $(newStep mod 4) & ".wav")
    elif actionId == replay.swapActionId:
      playSound("swap" & $(newStep mod 2) & ".wav")

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

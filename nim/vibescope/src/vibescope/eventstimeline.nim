import
  std/[json, algorithm, strutils],
  chroma, vmath, windy, silky, bumpy,
  common

const
  EventsTimelineHeight* = 24f
  TickWidth = 3f
  PositionLineColor = rgbx(255, 255, 255, 200)
  EventsPalette = [
    parseHtmlColor("#FF6B6B").rgbx,  # Red
    parseHtmlColor("#4ECDC4").rgbx,  # Teal
    parseHtmlColor("#FFE66D").rgbx,  # Yellow
    parseHtmlColor("#95E1D3").rgbx,  # Mint
    parseHtmlColor("#F38181").rgbx,  # Salmon
    parseHtmlColor("#AA96DA").rgbx,  # Lavender
    parseHtmlColor("#FCB69F").rgbx,  # Peach
    parseHtmlColor("#A8E6CF").rgbx,  # Light green
    parseHtmlColor("#FF8B94").rgbx,  # Pink
    parseHtmlColor("#6EB5FF").rgbx,  # Blue
  ]
  BackgroundColor = parseHtmlColor("#1A2A3A").rgbx

type
  PlannedEvent = object
    name: string
    timesteps: seq[int]
    color: ColorRGBX

var
  parsedEvents: seq[PlannedEvent]
  eventsParsed = false
  lastReplayPtr: pointer = nil

proc parseEvents() =
  ## Parse events from replay config. Called once per replay load.
  parsedEvents = @[]

  if replay.isNil or replay.mgConfig.isNil:
    return
  if "game" notin replay.mgConfig:
    return
  let game = replay.mgConfig["game"]
  if "events" notin game or game["events"].kind != JObject:
    return

  # Collect event names and sort for consistent color assignment.
  var names: seq[string] = @[]
  for name in game["events"].keys:
    names.add(name)
  names.sort()

  for i, name in names:
    let eventNode = game["events"][name]
    var timesteps: seq[int] = @[]
    if "timesteps" in eventNode and eventNode["timesteps"].kind == JArray:
      for ts in eventNode["timesteps"]:
        if ts.kind == JInt:
          timesteps.add(ts.getInt)
    if timesteps.len > 0:
      parsedEvents.add(PlannedEvent(
        name: name,
        timesteps: timesteps,
        color: EventsPalette[i mod EventsPalette.len],
      ))

proc hasEvents*(): bool =
  ## Returns true if there are events to display.
  if not eventsParsed or cast[pointer](replay) != lastReplayPtr:
    parseEvents()
    eventsParsed = true
    lastReplayPtr = cast[pointer](replay)
  return parsedEvents.len > 0

proc drawEventsTimeline*(pos, size: Vec2) =
  ## Draw the events timeline bar.
  if not hasEvents():
    return

  let maxSteps = configMaxSteps().float32
  if maxSteps <= 0:
    return

  ribbon(pos, size, BackgroundColor):
    let barPos = sk.pos
    let barSize = sk.size

    # Draw event tick marks.
    for event in parsedEvents:
      for ts in event.timesteps:
        let x = (ts.float32 / maxSteps) * barSize.x
        if x >= 0 and x <= barSize.x:
          sk.drawRect(
            vec2(barPos.x + x - TickWidth / 2, barPos.y),
            vec2(TickWidth, barSize.y),
            event.color,
          )

    # Draw current position indicator.
    let posX = (step.float32 / maxSteps) * barSize.x
    sk.drawRect(
      vec2(barPos.x + posX - 0.5, barPos.y),
      vec2(1, barSize.y),
      PositionLineColor,
    )

    # Tooltip on mouseover - find closest event tick.
    let mousePos = window.mousePos.vec2
    if mouseInsideClip(rect(barPos, barSize)):
      var tooltipNames: seq[string] = @[]
      let mouseXRatio = (mousePos.x - barPos.x) / barSize.x
      let mouseStep = mouseXRatio * maxSteps
      let hitRadius = (4.0 / barSize.x) * maxSteps  # 4px in step-space

      for event in parsedEvents:
        for ts in event.timesteps:
          if abs(ts.float32 - mouseStep) < hitRadius:
            if event.name notin tooltipNames:
              tooltipNames.add(event.name)
            break

      if tooltipNames.len > 0:
        let label = tooltipNames.join(", ")
        sk.at = vec2(mousePos.x + 8, barPos.y - 20)
        text(label)

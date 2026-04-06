import
  std/[tables],
  windy, vmath,
  common, replays, talk, gamemode/pathfinding

type
  Orientation* = enum
    Invalid = 'x'
    N = 'n'
    S = 's'
    W = 'w'
    E = 'e'

proc sendAction*(agentId: int, actionName: string) =
  ## Send an action to the Python from the user.
  requestActions.add(ActionRequest(
    agentId: agentId,
    actionName: actionName
  ))
  requestPython = true

proc getOrientationFromDelta(dx, dy: int): Orientation =
  ## Get the orientation from a movement delta.
  if dx == 0 and dy == -1:
    return N
  elif dx == 0 and dy == 1:
    return S
  elif dx == -1 and dy == 0:
    return W
  elif dx == 1 and dy == 0:
    return E
  else:
    return Invalid

proc agentHasEnergy(agent: Entity): bool =
  let energyId = replay.itemNames.find("energy")
  if energyId == -1:
    echo "Energy item not found in replay"
    return true
  let inv = agent.inventory.at(replay.maxSteps - 1)
  for item in inv:
    if item.itemId == energyId and item.count > 1:
      return true
  return false

proc getMoveActionName(orientation: Orientation): string =
  ## Get the move action name from an orientation.
  case orientation
  of Invalid:
    raise newException(ValueError, "Invalid move orientation.")
  of N: return "move_north"
  of S: return "move_south"
  of E: return "move_east"
  of W: return "move_west"

proc isCardinalStep(fromPos, toPos: IVec2): bool =
  ## Return true when two positions are a single cardinal move apart.
  let
    dx = abs(toPos.x - fromPos.x)
    dy = abs(toPos.y - fromPos.y)
  (dx == 1 and dy == 0) or (dx == 0 and dy == 1)

proc processActions*() =
  ## Process path actions and send actions for the current step while in play mode.
  ## Uses a while loop per agent so that reached waypoints and stale-path recomputes
  ## are consumed immediately rather than wasting a tick.
  if not (play or requestPython):
    return
  var agentIds: seq[int] = @[]
  for agentId in agentPaths.keys:
    agentIds.add(agentId)

  for agentId in agentIds:
    if not agentPaths.hasKey(agentId):
      continue

    let agent = getAgentById(agentId)
    let
      currentPos = agent.location.at(replay.maxSteps - 1).xy

    if agentPaths[agentId].len == 0:
      agentPaths.del(agentId)
      continue

    # If the agent has no energy, wait and do not issue new path actions this step.
    if not agentHasEnergy(agent):
      continue

    # Loop to skip past reached waypoints and stale-path recomputes within a single tick.
    while agentPaths.hasKey(agentId) and agentPaths[agentId].len > 0:
      let nextAction = agentPaths[agentId][0]

      case nextAction.kind
      of Move:
        # If play position already reached this queued step, pop it and try the next.
        if currentPos == nextAction.pos:
          agentPaths[agentId].delete(0)
          if agentObjectives.hasKey(agentId) and agentObjectives[agentId].len > 0:
            let objective = agentObjectives[agentId][0]
            if objective.kind == Move and currentPos == objective.pos:
              agentObjectives[agentId].delete(0)
              if objective.repeat:
                agentObjectives[agentId].add(objective)
                recomputePath(agentId, currentPos)
              elif agentObjectives[agentId].len == 0:
                agentPaths.del(agentId)
          continue

        # Execute movement action.
        if not isCardinalStep(currentPos, nextAction.pos):
          echo "Stale/non-cardinal move in queue for agent ", agentId, ": ",
            currentPos, " -> ", nextAction.pos, ". Recomputing."
          recomputePath(agentId, currentPos)
          continue
        let
          dx = nextAction.pos.x - currentPos.x
          dy = nextAction.pos.y - currentPos.y
        let orientation = getOrientationFromDelta(dx.int, dy.int)
        sendAction(agentId, getMoveActionName(orientation))
        break
      of Bump:
        # Execute bump action.
        let targetOrientation = getOrientationFromDelta(nextAction.bumpDir.x.int,
            nextAction.bumpDir.y.int)
        sendAction(agentId, getMoveActionName(targetOrientation))
        # Remove this action from the queue.
        agentPaths[agentId].delete(0)
        # Remove the corresponding objective.
        let objective = agentObjectives[agentId][0]
        agentObjectives[agentId].delete(0)
        if objective.repeat:
          # Re-queue this objective at the end.
          agentObjectives[agentId].add(objective)
          recomputePath(agentId, currentPos)
        elif agentObjectives[agentId].len == 0:
          # No more objectives, clear the path.
          agentPaths.del(agentId)
        break
      of Vibe:
        # Execute vibe.
        sendAction(agentId, replay.actionNames[nextAction.vibeActionId])
        # Remove this action from the queue.
        agentPaths[agentId].delete(0)
        # Remove the corresponding objective.
        let objective = agentObjectives[agentId][0]
        if objective.kind == Vibe:
          agentObjectives[agentId].delete(0)
          if objective.repeat:
            # Re-queue this objective at the end.
            agentObjectives[agentId].add(objective)
            recomputePath(agentId, currentPos)
          elif agentObjectives[agentId].len == 0:
            # No more objectives, clear the path.
            agentPaths.del(agentId)
        break

proc queueWasdMove(agent: Entity, direction: IVec2) =
  ## Queue a single-step WASD move through the pathfinding action queue.
  ## When play=true, this lets processActions() drain it on the next auto-advance
  ## step boundary, avoiding race conditions with the smooth transition system.
  ## When play=false, falls back to direct sendAction() for immediate stepping.
  let
    currentPos = agent.location.at(replay.maxSteps - 1).xy
    targetPos = ivec2(currentPos.x + direction.x, currentPos.y + direction.y)
  let actionName = getMoveActionName(getOrientationFromDelta(direction.x.int, direction.y.int))
  agentObjectives.del(agent.agentId)
  if play:
    # Always queue for smooth interpolation. Replaces any existing path so the
    # agent changes direction immediately on the next step boundary.
    agentPaths[agent.agentId] = @[PathAction(kind: Move, pos: targetPos)]
  else:
    # play=false — user controls stepping. Direct send.
    agentPaths.del(agent.agentId)
    sendAction(agent.agentId, actionName)

proc agentControls*() =
  ## Manual controls with WASD for selected agent.
  ensureTalkComposeSelection()
  if talkComposeActive:
    return
  if selected != nil and selected.isAgent:
    let agent = selected

    # Move
    if window.buttonPressed[KeyW] or window.buttonPressed[KeyUp]:
      queueWasdMove(agent, ivec2(0, -1))

    elif window.buttonPressed[KeyS] or window.buttonPressed[KeyDown]:
      queueWasdMove(agent, ivec2(0, 1))

    elif window.buttonPressed[KeyD] or window.buttonPressed[KeyRight]:
      queueWasdMove(agent, ivec2(1, 0))

    elif window.buttonPressed[KeyA] or window.buttonPressed[KeyLeft]:
      queueWasdMove(agent, ivec2(-1, 0))

    # Noop
    elif window.buttonPressed[KeyX]:
      sendAction(agent.agentId, "noop")

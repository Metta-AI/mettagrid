## Vibe panel allows you to set vibe frequency for the agent.
## Vibe are emoji like symbols that the agent can use to communicate with
## the world and other agents.

import
  std/[tables, strutils],
  silky, windy,
  ../common, ../replays, ../actions

proc getVibes(): seq[string] =
  for vibe in replay.config.game.vibeNames:
    result.add("vibe/" & vibe)

proc drawVibes*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  let m = 12.0f
  frame(frameId, contentPos, contentSize):
    let buttonWidth = 32.0f + sk.padding
    let startX = sk.at.x
    for i, vibe in getVibes():
      # Check if we need to wrap to the next line.
      if sk.at.x + buttonWidth > sk.pos.x + sk.size.x - m:
        sk.at.x = startX
        sk.at.y += 32 + m

      let vibeName = vibe.split("/")[1]

      iconButton(vibe):
        if selected == nil or not selected.isAgent:
          return

        let vibeActionId = replay.actionNames.find("change_vibe_" & vibeName)
        if vibeActionId == -1:
          echo "vibe action not found: change_vibe_", vibeName
          return

        let shiftDown = window.buttonDown[KeyLeftShift] or window.buttonDown[KeyRightShift]

        if shiftDown:
          # Queue the vibe action as an objective.
          let objective = Objective(kind: Vibe, vibeActionId: vibeActionId, repeat: false)
          if not agentObjectives.hasKey(selected.agentId) or agentObjectives[
              selected.agentId].len == 0:
            agentObjectives[selected.agentId] = @[objective]
            # Append vibe action directly to path queue.
            agentPaths[selected.agentId] = @[
              PathAction(kind: Vibe, vibeActionId: vibeActionId)
            ]
          else:
            agentObjectives[selected.agentId].add(objective)
            # Push the vibe action to the end of the current path.
            if agentPaths.hasKey(selected.agentId):
              agentPaths[selected.agentId].add(
                PathAction(kind: Vibe, vibeActionId: vibeActionId)
              )
            else:
              agentPaths[selected.agentId] = @[
                PathAction(kind: Vibe, vibeActionId: vibeActionId)
              ]
        else:
          # Execute immediately.
          sendAction(selected.agentId, replay.actionNames[vibeActionId])
      if sk.shouldShowTooltip:
        tooltip(vibeName)

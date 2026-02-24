import
  std/[algorithm, strutils, tables],
  chroma,
  replays, colors, common

const TeamTag* = "team:"

const TeamColors* = {
  "clips": Red,
  "cogs": Blue,
  "cogs_green": Green,
  "cogs_blue": Blue,
  "cogs_red": Red,
  "cogs_yellow": Yellow,
}.toTable

const FallbackColors = [Purple, Orange, Teal, DarkGreen, DarkOrange, DarkPurple, DarkRed, DarkBlue]

proc teamColor(name: string, fallbackIndex: int): ColorRGBX =
  ## Look up color for a team name, falling back to a rotating palette.
  if name in TeamColors:
    return TeamColors[name]
  FallbackColors[fallbackIndex mod FallbackColors.len]

proc discoverTeams*(replay: Replay) =
  ## Find all teams from replay tags with the team tag prefix.
  replay.teams = @[]
  var teamTags: seq[(string, int)] = @[]
  for tagName, tagId in replay.tags:
    if tagName.startsWith(TeamTag):
      teamTags.add((tagName, tagId))
  teamTags.sort(proc(a, b: (string, int)): int = cmp(a[0], b[0]))
  var fallbackIdx = 0
  for (tagName, tagId) in teamTags:
    let name = tagName[TeamTag.len .. ^1]
    let color = teamColor(name, fallbackIdx)
    if name notin TeamColors:
      inc fallbackIdx
    replay.teams.add(TeamInfo(name: name, tagId: tagId, color: color))

proc getNumTeams*(): int =
  if replay.isNil: 0 else: replay.teams.len

proc getTeamColor*(teamIdx: int): ColorRGBX =
  if replay.isNil or teamIdx < 0 or teamIdx >= replay.teams.len:
    return Gray
  replay.teams[teamIdx].color

proc getTeamName*(teamIdx: int): string =
  if replay.isNil or teamIdx < 0 or teamIdx >= replay.teams.len:
    return ""
  replay.teams[teamIdx].name

proc getEntityTeamIndex*(entity: Entity): int =
  ## Get the team index for an entity at the current step. Returns -1 if no team.
  if entity.isNil or replay.isNil or replay.teams.len == 0:
    return -1
  let tagIds = entity.tagIds.at(step)
  for i, team in replay.teams:
    if team.tagId in tagIds:
      return i
  return -1

var activeTeam*: int = -1

proc getActiveTeam*(): int =
  ## Get the active team index. Auto-selects from the selected entity or defaults to first.
  if activeTeam >= 0 and activeTeam < replay.teams.len:
    return activeTeam
  if selected != nil:
    let idx = getEntityTeamIndex(selected)
    if idx >= 0:
      return idx
  if replay.teams.len > 0:
    return 0
  return -1

proc getGlobalResourceCount*(teamIdx: int, itemName: string): int =
  ## Sum an inventory item across all living hubs in a team.
  if replay.isNil or teamIdx < 0 or teamIdx >= replay.teams.len:
    return 0
  for obj in replay.objects:
    if not obj.alive.at:
      continue
    if normalizeTypeName(obj.typeName) != "hub":
      continue
    if getEntityTeamIndex(obj) != teamIdx:
      continue
    let inv = obj.inventory.at(step)
    for item in inv:
      if item.itemId >= 0 and item.itemId < replay.itemNames.len:
        if replay.itemNames[item.itemId] == itemName:
          result += item.count

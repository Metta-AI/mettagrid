## Agent name assignment module.
## Assigns readable names to agents for display purposes.

import
  std/[os, random, strutils, algorithm, tables],
  common, replays

var
  ## Cog names: maps agentId -> display name ("First L.") for the current episode.
  cogNames*: Table[int, string]
  ## All loaded names grouped by first letter.
  cogNamesByLetter: Table[char, seq[string]]
  cogNamesLoaded: bool = false

proc loadCogNames*() =
  ## Load cog names from data/cog_names.txt and group by first letter.
  if cogNamesLoaded:
    return
  cogNamesLoaded = true
  cogNamesByLetter = initTable[char, seq[string]]()
  let path = dataDir / "cog_names.txt"
  if not fileExists(path):
    echo "cog_names.txt not found at ", path
    return
  for line in lines(path):
    let trimmed = line.strip()
    if trimmed.len == 0 or trimmed[0] == '#':
      continue
    let parts = trimmed.split(" ", maxsplit = 1)
    if parts.len < 2:
      continue
    let firstName = parts[0]
    let lastName = parts[1]
    let displayName = firstName & " " & lastName[0] & "."
    let letter = firstName[0].toUpperAscii
    if letter notin cogNamesByLetter:
      cogNamesByLetter[letter] = @[]
    cogNamesByLetter[letter].add(displayName)

proc assignCogNames*() =
  ## Assign random cog names to agents. Call once per episode.
  loadCogNames()
  cogNames = initTable[int, string]()
  if replay.isNil or replay.agents.len == 0:
    return
  # Collect available letters sorted.
  var letters: seq[char] = @[]
  for letter in cogNamesByLetter.keys:
    letters.add(letter)
  letters.sort()
  if letters.len == 0:
    return
  # Assign names round-robin through the alphabet.
  let numAgents = replay.agents.len
  for i in 0 ..< numAgents:
    let agent = replay.agents[i]
    let letter = letters[i mod letters.len]
    let names = cogNamesByLetter[letter]
    let name = names[rand(names.len - 1)]
    cogNames[agent.agentId] = name

proc getCogName*(agentId: int): string =
  ## Get the cog name for an agent, or empty string if none assigned.
  ## Lazily assigns names if agents exist but names haven't been assigned yet.
  if cogNames.len == 0 and not replay.isNil and replay.agents.len > 0:
    assignCogNames()
  cogNames.getOrDefault(agentId, "")

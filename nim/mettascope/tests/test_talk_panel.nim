import
  vmath,
  mettascope/[common, replays],
  mettascope/talk,
  mettascope/panelmode/talkpanel

proc setupTalkReplay(maxSteps: int, agents: seq[Entity]): Replay =
  ## Create a minimal replay for talk panel history tests.
  Replay(
    version: FormatVersion,
    numAgents: agents.len,
    maxSteps: maxSteps,
    mapSize: (20, 20),
    fileName: "talk-test",
    objects: agents,
    agents: agents,
    config: Config(
      game: GameConfig(
        talk: TalkConfig(
          enabled: true,
          maxLength: 140,
          cooldownSteps: 50
        )
      )
    )
  )

proc createTalkAgent(
  id: int,
  locations: seq[IVec2],
  talkTexts: seq[string],
  talkRemainingSteps: seq[int]
): Entity =
  ## Create a minimal agent entity for talk panel history tests.
  result = Entity(
    id: id,
    typeName: "agent",
    agentId: id,
    isAgent: true,
    location: locations,
    orientation: newSeq[int](locations.len),
    inventory: newSeq[seq[ItemAmount]](locations.len),
    inventoryMax: 10,
    inventoryCapacities: newSeq[seq[CapacityAmount]](locations.len),
    color: newSeq[int](locations.len),
    vibeId: newSeq[int](locations.len),
    actionId: newSeq[int](locations.len),
    actionParameter: newSeq[int](locations.len),
    actionSuccess: newSeq[bool](locations.len),
    animationId: newSeq[int](locations.len),
    currentReward: newSeq[float](locations.len),
    totalReward: newSeq[float](locations.len),
    isFrozen: newSeq[bool](locations.len),
    frozenProgress: newSeq[int](locations.len),
    alive: newSeq[bool](locations.len),
    frozenTime: 0,
    visionSize: 11,
    talkText: talkTexts,
    talkRemainingSteps: talkRemainingSteps
  )

  for i in 0 ..< locations.len:
    result.inventory[i] = @[]
    result.inventoryCapacities[i] = @[]
    result.actionSuccess[i] = true
    result.alive[i] = true

block talk_history_tests:
  block visible_talk_is_logged_once_when_seen_from_start:
    let
      observer = createTalkAgent(
        0,
        @[ivec2(5, 5), ivec2(5, 5), ivec2(5, 5)],
        @["", "", ""],
        @[0, 0, 0]
      )
      speaker = createTalkAgent(
        1,
        @[ivec2(7, 5), ivec2(7, 5), ivec2(7, 5)],
        @["ore east", "ore east", "ore east"],
        @[3, 2, 1]
      )

    replay = setupTalkReplay(3, @[observer, speaker])
    step = 2

    let entries = collectVisibleTalkEntries(observer)
    doAssert entries.len == 1
    doAssert entries[0].step == 0
    doAssert entries[0].speakerId == 1
    doAssert entries[0].message == "ore east"

  block talk_is_logged_when_it_first_becomes_visible:
    let
      observer = createTalkAgent(
        0,
        @[ivec2(5, 5), ivec2(5, 5), ivec2(5, 5)],
        @["", "", ""],
        @[0, 0, 0]
      )
      speaker = createTalkAgent(
        1,
        @[ivec2(15, 15), ivec2(7, 5), ivec2(7, 5)],
        @["hold north", "hold north", "hold north"],
        @[3, 2, 1]
      )

    replay = setupTalkReplay(3, @[observer, speaker])
    step = 2

    let entries = collectVisibleTalkEntries(observer)
    doAssert entries.len == 1
    doAssert entries[0].step == 1
    doAssert entries[0].speakerId == 1
    doAssert entries[0].message == "hold north"

  block multiple_speakers_are_sorted_by_first_visible_step:
    let
      observer = createTalkAgent(
        0,
        @[ivec2(5, 5), ivec2(5, 5), ivec2(5, 5)],
        @["", "", ""],
        @[0, 0, 0]
      )
      speakerA = createTalkAgent(
        1,
        @[ivec2(7, 5), ivec2(7, 5), ivec2(7, 5)],
        @["ore east", "ore east", "ore east"],
        @[3, 2, 1]
      )
      speakerB = createTalkAgent(
        2,
        @[ivec2(15, 15), ivec2(7, 6), ivec2(7, 6)],
        @["hold south", "hold south", "hold south"],
        @[3, 2, 1]
      )

    replay = setupTalkReplay(3, @[observer, speakerA, speakerB])
    step = 2

    let entries = collectVisibleTalkEntries(observer)
    doAssert entries.len == 2
    doAssert entries[0].step == 0
    doAssert entries[0].speakerId == 1
    doAssert entries[0].message == "ore east"
    doAssert entries[1].step == 1
    doAssert entries[1].speakerId == 2
    doAssert entries[1].message == "hold south"

  block talk_input_is_ascii_and_length_limited:
    doAssert sanitizeTalkText("ore east", 20) == "ore east"
    doAssert sanitizeTalkText("ore 😀 east", 20) == "ore  east"
    doAssert sanitizeTalkText("0123456789", 5) == "01234"

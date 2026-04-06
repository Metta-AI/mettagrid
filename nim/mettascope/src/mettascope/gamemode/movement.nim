import
  std/[math, options],
  vmath,
  ../[common, replays]

const
  TurnDisableSpeed* = 50.0f
  CornerRoundingTension* = 0.5f
  BumpDepthTiles* = 0.18f
  BumpActiveFraction* = 0.35f
  BumpDisableSpeed* = 16.0f

proc getMoveActionDir*(agent: Entity, atStep: int): Option[IVec2] =
  ## Return the attempted move direction for the given agent step when present.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)

  let actionId = agent.actionId.at(atStep)
  if actionId == replay.moveNorthActionId:
    return some(ivec2(0, -1))
  if actionId == replay.moveSouthActionId:
    return some(ivec2(0, 1))
  if actionId == replay.moveWestActionId:
    return some(ivec2(-1, 0))
  if actionId == replay.moveEastActionId:
    return some(ivec2(1, 0))
  return none(IVec2)

proc getBumpDirForAction(agent: Entity, actionStep: int): Option[IVec2] =
  ## Return the bump direction implied by one move action.
  const AnimationBump = 1
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)
  if agent.animationId.len > 0 and
      agent.animationId.at(actionStep) == AnimationBump:
    return agent.getMoveActionDir(actionStep)
  return none(IVec2)

proc getBumpDir(agent: Entity, atStep: int): Option[IVec2] =
  ## Return the bump direction for a stationary turn transition.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)
  if atStep < 0 or atStep + 1 >= replay.maxSteps:
    return none(IVec2)

  let
    startPos = agent.location.at(atStep).xy
    endPos = agent.location.at(atStep + 1).xy
  if startPos != endPos:
    return none(IVec2)

  let startActionBump = agent.getBumpDirForAction(atStep)
  if startActionBump.isSome:
    return startActionBump
  return agent.getBumpDirForAction(atStep + 1)

proc getActiveBumpDir*(agent: Entity): Option[IVec2] =
  ## Return the current bump direction while the bump animation is active.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)
  if playSpeed > BumpDisableSpeed:
    return none(IVec2)

  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
  if stepFrac <= 0.0f or stepFrac >= BumpActiveFraction:
    return none(IVec2)
  return agent.getBumpDir(baseStep)

proc bumpOffset(agent: Entity): Vec2 =
  ## Return the render-time offset for the current bump animation frame.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return vec2(0, 0)

  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
  if stepFrac <= 0.0f or stepFrac >= BumpActiveFraction:
    return vec2(0, 0)

  let bumpDir = agent.getActiveBumpDir()
  if not bumpDir.isSome:
    return vec2(0, 0)

  let
    progress = stepFrac / BumpActiveFraction
    depth = sin(PI.float32 * progress) * BumpDepthTiles
  return bumpDir.get.vec2 * depth

proc smoothPos*(entity: Entity): Vec2 =
  ## Interpolate position with Catmull-Rom spline for smooth corners.
  if entity.isNil:
    return vec2(0, 0)

  let
    baseStep = floor(stepFloat).int
    t = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
    p1 = entity.location.at(baseStep).xy.vec2
    p2 = entity.location.at(baseStep + 1).xy.vec2
  if playSpeed > TurnDisableSpeed or baseStep < 1:
    result = p1 + (p2 - p1) * t
  elif p1 == p2:
    # Fall back to linear when stationary this step.
    result = p1
  else:
    let
      p0 = entity.location.at(baseStep - 1).xy.vec2
      p3 = entity.location.at(baseStep + 2).xy.vec2
      # Zero tangent when the adjacent segment is stationary.
      # This prevents overshoot.
      m0 =
        if p0 == p1:
          vec2(0, 0)
        else:
          CornerRoundingTension * (p2 - p0)
      m1 =
        if p2 == p3:
          vec2(0, 0)
        else:
          CornerRoundingTension * (p3 - p1)
      t2 = t * t
      t3 = t2 * t
    # Cubic Hermite spline.
    result = (2.0f*t3 - 3.0f*t2 + 1.0f) * p1 +
      (t3 - 2.0f*t2 + t) * m0 +
      (-2.0f*t3 + 3.0f*t2) * p2 +
      (t3 - t2) * m1

  if entity.isAgent:
    result += bumpOffset(entity)
  return result

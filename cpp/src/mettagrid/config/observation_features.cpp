
#include "config/observation_features.hpp"

namespace ObservationFeature {
std::shared_ptr<ObservationFeaturesImpl> _instance;

// Define the extern variables
ObservationType Group;
ObservationType Frozen;
ObservationType EpisodeCompletionPct;
ObservationType LastAction;
ObservationType LastReward;
ObservationType Vibe;
ObservationType Tag;
ObservationType CooldownRemaining;
ObservationType RemainingUses;
ObservationType Goal;
ObservationType Collective;
ObservationType LpEast;
ObservationType LpWest;
ObservationType LpNorth;
ObservationType LpSouth;
ObservationType AgentId;
ObservationType AgentRole;
ObservationType AgentRoleMiner;
ObservationType AgentRoleAligner;
ObservationType AgentRoleScrambler;
ObservationType AgentRoleScout;

void Initialize(const std::unordered_map<std::string, ObservationType>& feature_ids) {
  _instance = std::make_shared<ObservationFeaturesImpl>(feature_ids);

  // Update the global variables with values from the instance
  Group = _instance->Group;
  Frozen = _instance->Frozen;
  EpisodeCompletionPct = _instance->EpisodeCompletionPct;
  LastAction = _instance->LastAction;
  LastReward = _instance->LastReward;
  Vibe = _instance->Vibe;
  Tag = _instance->Tag;
  CooldownRemaining = _instance->CooldownRemaining;
  RemainingUses = _instance->RemainingUses;
  Goal = _instance->Goal;
  Collective = _instance->Collective;
  LpEast = _instance->LpEast;
  LpWest = _instance->LpWest;
  LpNorth = _instance->LpNorth;
  LpSouth = _instance->LpSouth;
  AgentId = _instance->AgentId;
  AgentRole = _instance->AgentRole;
  AgentRoleMiner = _instance->AgentRoleMiner;
  AgentRoleAligner = _instance->AgentRoleAligner;
  AgentRoleScrambler = _instance->AgentRoleScrambler;
  AgentRoleScout = _instance->AgentRoleScout;
}
}  // namespace ObservationFeature

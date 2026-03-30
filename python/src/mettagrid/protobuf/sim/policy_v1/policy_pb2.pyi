from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AgentObservations(_message.Message):
    __slots__ = ("agent_id", "observations", "visible_talk")
    class Format(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AGENT_OBSERVATIONS_FORMAT_UNKNOWN: _ClassVar[AgentObservations.Format]
        TRIPLET_V1: _ClassVar[AgentObservations.Format]
    AGENT_OBSERVATIONS_FORMAT_UNKNOWN: AgentObservations.Format
    TRIPLET_V1: AgentObservations.Format
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    OBSERVATIONS_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_TALK_FIELD_NUMBER: _ClassVar[int]
    agent_id: int
    observations: bytes
    visible_talk: _containers.RepeatedCompositeFieldContainer[VisibleTalk]
    def __init__(self, agent_id: _Optional[int] = ..., observations: _Optional[bytes] = ..., visible_talk: _Optional[_Iterable[_Union[VisibleTalk, _Mapping]]] = ...) -> None: ...

class BatchStepRequest(_message.Message):
    __slots__ = ("episode_id", "step_id", "agent_observations")
    EPISODE_ID_FIELD_NUMBER: _ClassVar[int]
    STEP_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_OBSERVATIONS_FIELD_NUMBER: _ClassVar[int]
    episode_id: str
    step_id: int
    agent_observations: _containers.RepeatedCompositeFieldContainer[AgentObservations]
    def __init__(self, episode_id: _Optional[str] = ..., step_id: _Optional[int] = ..., agent_observations: _Optional[_Iterable[_Union[AgentObservations, _Mapping]]] = ...) -> None: ...

class AgentActions(_message.Message):
    __slots__ = ("agent_id", "action_id", "talk_text")
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    TALK_TEXT_FIELD_NUMBER: _ClassVar[int]
    agent_id: int
    action_id: _containers.RepeatedScalarFieldContainer[int]
    talk_text: str
    def __init__(self, agent_id: _Optional[int] = ..., action_id: _Optional[_Iterable[int]] = ..., talk_text: _Optional[str] = ...) -> None: ...

class BatchStepResponse(_message.Message):
    __slots__ = ("agent_actions",)
    AGENT_ACTIONS_FIELD_NUMBER: _ClassVar[int]
    agent_actions: _containers.RepeatedCompositeFieldContainer[AgentActions]
    def __init__(self, agent_actions: _Optional[_Iterable[_Union[AgentActions, _Mapping]]] = ...) -> None: ...

class GameRules(_message.Message):
    __slots__ = ("features", "actions")
    class Feature(_message.Message):
        __slots__ = ("id", "name", "normalization")
        ID_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        NORMALIZATION_FIELD_NUMBER: _ClassVar[int]
        id: int
        name: str
        normalization: float
        def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., normalization: _Optional[float] = ...) -> None: ...
    class Action(_message.Message):
        __slots__ = ("id", "name")
        ID_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        id: int
        name: str
        def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ...) -> None: ...
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    features: _containers.RepeatedCompositeFieldContainer[GameRules.Feature]
    actions: _containers.RepeatedCompositeFieldContainer[GameRules.Action]
    def __init__(self, features: _Optional[_Iterable[_Union[GameRules.Feature, _Mapping]]] = ..., actions: _Optional[_Iterable[_Union[GameRules.Action, _Mapping]]] = ...) -> None: ...

class TalkConfig(_message.Message):
    __slots__ = ("max_length", "cooldown_steps")
    MAX_LENGTH_FIELD_NUMBER: _ClassVar[int]
    COOLDOWN_STEPS_FIELD_NUMBER: _ClassVar[int]
    max_length: int
    cooldown_steps: int
    def __init__(self, max_length: _Optional[int] = ..., cooldown_steps: _Optional[int] = ...) -> None: ...

class VisibleTalk(_message.Message):
    __slots__ = ("agent_id", "row", "col", "remaining_steps", "text")
    AGENT_ID_FIELD_NUMBER: _ClassVar[int]
    ROW_FIELD_NUMBER: _ClassVar[int]
    COL_FIELD_NUMBER: _ClassVar[int]
    REMAINING_STEPS_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    agent_id: int
    row: int
    col: int
    remaining_steps: int
    text: str
    def __init__(self, agent_id: _Optional[int] = ..., row: _Optional[int] = ..., col: _Optional[int] = ..., remaining_steps: _Optional[int] = ..., text: _Optional[str] = ...) -> None: ...

class PolicyEnvInterface(_message.Message):
    __slots__ = ("obs_features", "tags", "action_names", "move_energy_cost", "num_agents", "observation_shape", "obs_height", "obs_width", "talk")
    OBS_FEATURES_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    ACTION_NAMES_FIELD_NUMBER: _ClassVar[int]
    MOVE_ENERGY_COST_FIELD_NUMBER: _ClassVar[int]
    NUM_AGENTS_FIELD_NUMBER: _ClassVar[int]
    OBSERVATION_SHAPE_FIELD_NUMBER: _ClassVar[int]
    OBS_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    OBS_WIDTH_FIELD_NUMBER: _ClassVar[int]
    TALK_FIELD_NUMBER: _ClassVar[int]
    obs_features: _containers.RepeatedCompositeFieldContainer[GameRules.Feature]
    tags: _containers.RepeatedScalarFieldContainer[str]
    action_names: _containers.RepeatedScalarFieldContainer[str]
    move_energy_cost: int
    num_agents: int
    observation_shape: _containers.RepeatedScalarFieldContainer[int]
    obs_height: int
    obs_width: int
    talk: TalkConfig
    def __init__(self, obs_features: _Optional[_Iterable[_Union[GameRules.Feature, _Mapping]]] = ..., tags: _Optional[_Iterable[str]] = ..., action_names: _Optional[_Iterable[str]] = ..., move_energy_cost: _Optional[int] = ..., num_agents: _Optional[int] = ..., observation_shape: _Optional[_Iterable[int]] = ..., obs_height: _Optional[int] = ..., obs_width: _Optional[int] = ..., talk: _Optional[_Union[TalkConfig, _Mapping]] = ...) -> None: ...

class PreparePolicyRequest(_message.Message):
    __slots__ = ("episode_id", "game_rules", "agent_ids", "observations_format", "env_interface")
    EPISODE_ID_FIELD_NUMBER: _ClassVar[int]
    GAME_RULES_FIELD_NUMBER: _ClassVar[int]
    AGENT_IDS_FIELD_NUMBER: _ClassVar[int]
    OBSERVATIONS_FORMAT_FIELD_NUMBER: _ClassVar[int]
    ENV_INTERFACE_FIELD_NUMBER: _ClassVar[int]
    episode_id: str
    game_rules: GameRules
    agent_ids: _containers.RepeatedScalarFieldContainer[int]
    observations_format: AgentObservations.Format
    env_interface: PolicyEnvInterface
    def __init__(self, episode_id: _Optional[str] = ..., game_rules: _Optional[_Union[GameRules, _Mapping]] = ..., agent_ids: _Optional[_Iterable[int]] = ..., observations_format: _Optional[_Union[AgentObservations.Format, str]] = ..., env_interface: _Optional[_Union[PolicyEnvInterface, _Mapping]] = ...) -> None: ...

class PreparePolicyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

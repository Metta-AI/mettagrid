from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import AgentObservation
from mettagrid.simulator.interface import Location

_PART_SUFFIX_RE = re.compile(r"^(?P<name>.+):p(?P<part>\d+)$")


@dataclass(slots=True)
class ObservationEnvelope:
    raw_observation: AgentObservation
    policy_env_info: PolicyEnvInterface
    step: int | None = None


@dataclass(slots=True)
class ObservationCell:
    location: Location
    center: Location
    tags: tuple[str, ...]
    features: dict[str, int]

    @property
    def row(self) -> int:
        return self.location.row

    @property
    def col(self) -> int:
        return self.location.col

    @property
    def x(self) -> int:
        return self.location.x - self.center.x

    @property
    def y(self) -> int:
        return self.location.y - self.center.y


@dataclass(slots=True)
class DecodedObservation:
    observation: AgentObservation
    policy_env_info: PolicyEnvInterface
    step: int | None
    center_row: int
    center_col: int
    cells_by_location: dict[tuple[int, int], ObservationCell]
    global_features: dict[str, int]

    @property
    def cells(self) -> list[ObservationCell]:
        return [self.cells_by_location[location] for location in sorted(self.cells_by_location)]

    @property
    def self_cell(self) -> ObservationCell:
        key = (self.center_row, self.center_col)
        if key not in self.cells_by_location:
            self.cells_by_location[key] = ObservationCell(
                location=Location(self.center_row, self.center_col),
                center=Location(self.center_row, self.center_col),
                tags=tuple(),
                features={},
            )
        return self.cells_by_location[key]


def decode_observation(envelope: ObservationEnvelope) -> DecodedObservation:
    tags_by_location: defaultdict[tuple[int, int], list[str]] = defaultdict(list)
    parts_by_location: defaultdict[tuple[int, int], dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
    global_parts: defaultdict[str, dict[int, int]] = defaultdict(dict)
    normalization_bases: dict[str, int] = {}

    for token in envelope.raw_observation.tokens:
        if token.feature.name == "tag":
            location = token.location
            if location is None:
                continue
            tags_by_location[(location.row, location.col)].append(envelope.policy_env_info.tags[token.value])
            continue

        feature_name, part_index = _split_feature_name(token.feature.name)
        normalization_bases[feature_name] = _normalization_base(token.feature.normalization)
        if token.is_global:
            global_parts[feature_name][part_index] = token.value
            continue

        location = token.location
        if location is None:
            continue
        parts_by_location[(location.row, location.col)][feature_name][part_index] = token.value

    center_row = envelope.policy_env_info.obs_height // 2
    center_col = envelope.policy_env_info.obs_width // 2
    center = Location(center_row, center_col)
    cells_by_location: dict[tuple[int, int], ObservationCell] = {}
    for row, col in sorted(set(tags_by_location) | set(parts_by_location)):
        features = {
            feature_name: _decode_feature_parts(parts, normalization_bases[feature_name])
            for feature_name, parts in parts_by_location[(row, col)].items()
        }
        cells_by_location[(row, col)] = ObservationCell(
            location=Location(row, col),
            center=center,
            tags=tuple(sorted(tags_by_location[(row, col)])),
            features=features,
        )

    global_features = {
        feature_name: _decode_feature_parts(parts, normalization_bases[feature_name])
        for feature_name, parts in global_parts.items()
    }
    return DecodedObservation(
        observation=envelope.raw_observation,
        policy_env_info=envelope.policy_env_info,
        step=envelope.step,
        center_row=center_row,
        center_col=center_col,
        cells_by_location=cells_by_location,
        global_features=global_features,
    )


def _split_feature_name(feature_name: str) -> tuple[str, int]:
    match = _PART_SUFFIX_RE.match(feature_name)
    if match is None:
        return feature_name, 0
    return match.group("name"), int(match.group("part"))


def _decode_feature_parts(parts: dict[int, int], normalization_base: int) -> int:
    total = 0
    for part_index, value in sorted(parts.items()):
        total += value * (normalization_base**part_index)
    return total


def _normalization_base(normalization: float) -> int:
    return max(int(normalization), 1)

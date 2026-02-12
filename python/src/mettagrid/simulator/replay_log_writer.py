from __future__ import annotations

import gzip
import json
import logging
import uuid
import zlib
from typing import Any, Dict, List

import numpy as np

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.renderer.common import METTASCOPE_REPLAY_URL_PREFIX
from mettagrid.simulator.interface import SimulatorEventHandler
from mettagrid.simulator.simulator import Simulation
from mettagrid.util.file import http_url, write_data
from mettagrid.util.grid_object_formatter import format_grid_object

logger = logging.getLogger("ReplayLogWriter")


class InMemoryReplayWriter(SimulatorEventHandler):
    """EventHandler that maintains a list of completed replay results in memory, and does not write them anywhere"""

    def __init__(self):
        super().__init__()
        self._episode_replay: EpisodeReplay
        self._completed_replays: list[EpisodeReplay] = []

    def on_episode_start(self) -> None:
        self._episode_replay = EpisodeReplay(self._sim)

    def get_completed_replays(self) -> list[EpisodeReplay]:
        return self._completed_replays

    def on_step(self) -> None:
        self._episode_replay.log_step(
            self._sim.current_step,
            self._sim._c_sim.actions(),  # type: ignore[attr-defined]
            self._sim._c_sim.rewards(),  # type: ignore[attr-defined]
        )

    def on_episode_end(self) -> None:
        self._completed_replays.append(self._episode_replay)


class ReplayLogWriter(InMemoryReplayWriter):
    """EventHandler that writes replay logs to storage (S3 or local files)."""

    def __init__(self, replay_dir: str):
        """Initialize ReplayLogWriter.

        Args:
            replay_dir: Local directory where replays will be written. Must exist.
        """
        super().__init__()
        self._replay_dir = replay_dir
        self._episode_id: str
        self.episodes: Dict[str, EpisodeReplay] = {}
        self._episode_urls: Dict[str, str] = {}
        self._episode_paths: Dict[str, str] = {}

    def on_episode_start(self) -> None:
        """Start recording a new episode."""
        self._episode_id = str(uuid.uuid4())
        self._episode_replay = EpisodeReplay(self._sim)
        self.episodes[self._episode_id] = self._episode_replay
        logger.debug("Started recording episode %s", self._episode_id)

    def on_episode_end(self) -> None:
        """Write the replay to storage and clean up."""
        replay_path = f"{self._replay_dir}/{self._episode_id}.json.z"
        self._episode_replay.write_replay(replay_path)
        url = http_url(replay_path)
        self._episode_urls[self._episode_id] = url
        self._episode_paths[self._episode_id] = replay_path
        self._sim._context["replay_url"] = url
        logger.info("Wrote replay for episode %s to %s", self._episode_id, url)
        logger.debug("Watch replay at %s", METTASCOPE_REPLAY_URL_PREFIX + url)
        logger.debug(
            "Watch locally: " + f"nim r packages/mettagrid/nim/mettascope/src/mettascope.nim --replay={replay_path}"
        )

    def get_written_replay_urls(self) -> Dict[str, str]:
        """Return URLs for every replay file that has been written to disk."""
        return dict(self._episode_urls)

    def get_written_replay_paths(self) -> List[str]:
        """Return file paths for every replay file that has been written to disk."""
        return list(self._episode_paths.values())


class EpisodeReplay:
    """Helper class for managing replay data for a single episode."""

    # Object types that never change state and only need to be recorded once
    STATIC_OBJECT_TYPES = frozenset({"wall"})

    def __init__(self, sim: Simulation):
        self.sim = sim
        self.step = 0
        self.objects: list[dict[str, Any]] = []
        self.total_rewards = np.zeros(sim.num_agents)
        # Map object IDs to their index in self.objects for consistent ordering
        self._object_id_to_index: dict[int, int] = {}
        self.set_compression("zlib")

        self._validate_non_empty_string_list(sim.action_names, "action_names")
        self._validate_non_empty_string_list(sim.resource_names, "item_names")

        # Create PolicyEnvInterface for replay consumers
        policy_env_interface = PolicyEnvInterface.from_mg_cfg(sim.config)

        # Build sorted collective names list (matches C++ sorted order for deterministic IDs)
        self._collective_names: List[str] = sorted(sim.config.game.collectives.keys())
        # Map collective name -> ID for fast lookup
        self._collective_name_to_id: Dict[str, int] = {name: idx for idx, name in enumerate(self._collective_names)}

        # Time-series data for collective inventory
        # Format: list indexed by collective_id, each element is [[step, [[item_id, count], ...]], ...]
        self._collective_inventory: List[list] = [[] for _ in range(len(self._collective_names))]
        # Track last values to only record changes (keyed by collective_id)
        self._last_collective_inventory: Dict[int, Dict[str, int]] = {}

        # Build capacity_names from the first agent's inventory limits config (sorted for determinism).
        # Each capacity group (e.g., "gear", "cargo") is assigned an ID = index in this sorted list.
        agent_inv_limits = sim.config.game.agents[0].inventory.limits if sim.config.game.agents else {}
        self._capacity_names: List[str] = sorted(agent_inv_limits.keys())

        # Build resource_id -> capacity_id mapping for converting per-resource C++ limits
        # to per-capacity-group format in the replay.
        self._resource_to_capacity_id: Dict[int, int] = {}
        for cap_id, cap_name in enumerate(self._capacity_names):
            for resource_name in agent_inv_limits[cap_name].resources:
                if resource_name in sim.resource_names:
                    resource_id = sim.resource_names.index(resource_name)
                    self._resource_to_capacity_id[resource_id] = cap_id

        self.replay_data = {
            "version": 4,
            "action_names": sim.action_names,
            "item_names": sim.resource_names,
            "type_names": sim.object_type_names,
            "collective_names": self._collective_names,
            "capacity_names": self._capacity_names,
            "map_size": [sim.map_width, sim.map_height],
            "num_agents": sim.num_agents,
            "max_steps": sim.config.game.max_steps,
            "mg_config": sim.config.model_dump(mode="json"),
            "policy_env_interface": policy_env_interface.model_dump(mode="json"),
            "objects": self.objects,
            "infos": {},  # Populated at episode end
            "collective_inventory": self._collective_inventory,
        }

    def set_compression(self, compression: str):
        if compression == "zlib":
            self._compression = zlib.compress
            self._content_type = "application/x-compress"
        elif compression == "gzip":
            self._compression = gzip.compress
            self._content_type = "application/gzip"
        else:
            raise ValueError(f"unknown compression {compression!r}, try 'zlib' or 'gzip'")

    def log_step(self, current_step: int, actions: np.ndarray, rewards: np.ndarray):
        """Log a single step of the episode."""
        self.total_rewards += rewards

        # On first step, get ALL objects (including walls) to set up the replay
        # On subsequent steps, use ignore_types to skip static objects at the C++ level
        if self.step == 0:
            grid_objects = self.sim.grid_objects()
        else:
            grid_objects = self.sim.grid_objects(ignore_types=list(self.STATIC_OBJECT_TYPES))

        seen_indices: set[int] = set()

        for obj_id, grid_object in grid_objects.items():
            # Use object ID as index for consistent ordering
            idx = self._object_id_to_index.get(obj_id)
            if idx is None:
                idx = len(self.objects)
                self._object_id_to_index[obj_id] = idx
                # Objects appearing after step 0 start as not-alive.
                if self.step == 0:
                    self.objects.append({})
                else:
                    self.objects.append({"alive": [[0, False]]})

            seen_indices.add(idx)

            update_object = format_grid_object(
                grid_object,
                actions,
                self.sim.action_success,
                rewards,
                self.total_rewards,
            )

            # Convert raw per-resource capacities to per-capacity-group format
            self._convert_raw_capacities(update_object)

            self._seq_key_merge(self.objects[idx], self.step, update_object)

        # Mark objects not seen this step as dead (skip static objects like walls).
        if self.step > 0:
            for _, idx in self._object_id_to_index.items():
                if idx in seen_indices:
                    continue
                obj_data = self.objects[idx]
                # Skip static objects (walls etc.) - they are excluded from grid_objects after step 0.
                type_name_entries = obj_data.get("type_name")
                if type_name_entries:
                    last_type = (
                        type_name_entries[-1][1]
                        if isinstance(type_name_entries[-1], (list, tuple))
                        else type_name_entries
                    )
                    if last_type in self.STATIC_OBJECT_TYPES:
                        continue
                # Set alive to False if it was True.
                alive_entries = obj_data.get("alive")
                if alive_entries and isinstance(alive_entries[-1], (list, tuple)):
                    if alive_entries[-1][1] is not False:
                        obj_data["alive"].append([self.step, False])

        # Log collective inventory time-series
        self._log_collective_inventory(self.step)

        self.step += 1
        if current_step != self.step:
            raise ValueError(
                f"Writing multiple steps at once: step {current_step} != Replay step {self.step}."
                "Probably a vecenv issue."
            )

    def _convert_raw_capacities(self, update_object: dict) -> None:
        """Convert raw per-resource capacities to per-capacity-group format.

        Removes the ``inventory_capacities_raw`` key (a dict of
        ``{resource_id: effective_limit}``) and replaces it with
        ``inventory_capacities`` as ``[[capacity_id, effective_limit], ...]``
        sorted by capacity_id.
        """
        raw = update_object.pop("inventory_capacities_raw", {})
        group_caps: Dict[int, int] = {}
        for resource_id, eff_limit in raw.items():
            cap_id = self._resource_to_capacity_id.get(resource_id)
            if cap_id is not None and cap_id not in group_caps:
                group_caps[cap_id] = eff_limit
        # Format as [[capacity_id, effective_limit], ...] sorted by capacity_id
        update_object["inventory_capacities"] = sorted(group_caps.items())

    @staticmethod
    def _default_for(value):
        """Return the appropriate zero/empty default for a replay value."""
        if isinstance(value, list):
            return []
        elif isinstance(value, int):
            return 0
        elif isinstance(value, float):
            return 0.0
        elif isinstance(value, bool):
            return False
        else:
            raise ValueError(f"Unknown value type: {type(value)}")

    def _seq_key_merge(self, grid_object: dict, step: int, update_object: dict):
        """Add a sequence keys to replay grid object."""
        for key, value in update_object.items():
            if key not in grid_object:
                # Add new key.
                if step == 0:
                    grid_object[key] = [[step, value]]
                else:
                    grid_object[key] = [[0, self._default_for(value)], [step, value]]
            else:
                if grid_object[key][-1][1] != value:
                    grid_object[key].append([step, value])
        # If key has vanished, add a default entry.
        for key in grid_object.keys():
            if key not in update_object:
                last = grid_object[key][-1][1]
                default = self._default_for(last)
                if last != default:
                    grid_object[key].append([step, default])

    def _log_collective_inventory(self, step: int):
        """Log collective inventory for the current step."""
        # Get current collective inventories (keyed by name from C++ API)
        collective_inventories = self.sim._c_sim.get_collective_inventories()
        for collective_name, inventory in collective_inventories.items():
            # Convert name to ID for storage
            collective_id = self._collective_name_to_id.get(collective_name)
            if collective_id is None:
                continue  # Skip unknown collectives

            # Only record if changed from last snapshot
            last_inv = self._last_collective_inventory.get(collective_id, {})
            if inventory != last_inv:
                # Convert {item_name: count} to [[item_id, count], ...] format
                inv_by_id = []
                for item_name, count in inventory.items():
                    if item_name in self.sim.resource_names:
                        item_id = self.sim.resource_names.index(item_name)
                        inv_by_id.append([item_id, count])
                self._collective_inventory[collective_id].append([step, inv_by_id])
                self._last_collective_inventory[collective_id] = dict(inventory)

    def _populate_infos(self) -> Dict[str, Any]:
        """Populate episode infos from simulation state."""
        stats = self.sim.episode_stats
        config = self.sim.config
        num_agents = config.game.num_agents

        infos: Dict[str, Any] = {}

        # Game-level stats
        infos["game"] = stats.get("game", {})

        # Agent stats (averaged across all agents)
        infos["agent"] = {}
        for agent_stats in stats.get("agent", []):
            for n, v in agent_stats.items():
                infos["agent"][n] = infos["agent"].get(n, 0) + v
        for n, v in infos["agent"].items():
            infos["agent"][n] = v / num_agents if num_agents > 0 else 0

        # Collective stats
        collective_stats = stats.get("collective")
        if collective_stats:
            infos["collective"] = collective_stats

        # Attributes
        infos["attributes"] = {
            "seed": self.sim.seed,
            "map_w": self.sim.map_width,
            "map_h": self.sim.map_height,
            "steps": self.sim.current_step,
            "max_steps": config.game.max_steps,
        }

        # Episode rewards
        infos["episode_rewards"] = self.total_rewards.tolist()

        return infos

    def get_replay_data(self):
        """Gets full replay as a tree of plain python dictionaries."""
        self.replay_data["max_steps"] = self.step

        # Populate infos from simulation state
        self.replay_data["infos"] = self._populate_infos()

        # Trim value changes to make them more compact.
        for grid_object in self.objects:
            for key, changes in list(grid_object.items()):
                if (
                    isinstance(changes, list)
                    and len(changes) == 1
                    and isinstance(changes[0], (list, tuple))
                    and len(changes[0]) == 2
                ):
                    grid_object[key] = changes[0][1]

        return self.replay_data

    def write_replay(self, path: str):
        """Writes a replay to a file, inferring compression from extension."""
        if path.endswith(".gz"):
            self.set_compression("gzip")
        elif path.endswith(".z"):
            self.set_compression("zlib")
        replay_data = json.dumps(self.get_replay_data())
        replay_bytes = replay_data.encode("utf-8")
        compressed_data = self._compression(replay_bytes)
        write_data(path, compressed_data, content_type=self._content_type)

    @staticmethod
    def _validate_non_empty_string_list(values: list[str], field_name: str) -> None:
        """Ensure the provided iterable is a list of strings, warn on empty strings with index."""
        if not isinstance(values, list):
            raise ValueError(f"{field_name} must be a list of strings, got {type(values)}")
        for index, value in enumerate(values):
            if not isinstance(value, str):
                raise ValueError(f"{field_name}[{index}] must be a string, got {type(value)}: {repr(value)}")
            if value == "":
                logger.warning(
                    (
                        "%s contains an empty string at index %d; "
                        "frontend tolerates empty names but backend discourages them"
                    ),
                    field_name,
                    index,
                )

"""GUI renderer using mettascope."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from mettagrid.renderer.renderer import Renderer
from mettagrid.simulator.monologue_projection import strip_monologue_transcript_tail
from mettagrid.types import Action
from mettagrid.util.grid_object_formatter import format_grid_object

logger = logging.getLogger(__name__)


class MettascopeRenderer(Renderer):
    """Renderer for GUI mode using mettascope."""

    def __init__(self, autostart: bool = False):
        super().__init__()
        nim_root = _resolve_nim_root()
        nim_bindings_path = nim_root / "bindings" / "generated" if nim_root else None
        sys.path.insert(0, str(nim_bindings_path))
        import mettascope  # noqa: PLC0415

        self._mettascope = mettascope
        self._data_dir = str(nim_root / "data") if nim_root else "."
        os.environ.setdefault("METTASCOPE_DISABLE_CTRL_C", "1")
        self._autostart = autostart

    def on_episode_start(self) -> None:
        # Get the GameConfig from MettaGridConfig
        game_config = self._sim.config.game
        game_config_dict = game_config.model_dump(mode="json", exclude_none=True)

        # Build capacity mapping from agent config (same logic as replay_log_writer).
        agent_inv_limits = game_config.agents[0].inventory.limits if game_config.agents else {}
        self._capacity_names: List[str] = sorted(agent_inv_limits.keys())
        self._resource_to_capacity_id: Dict[int, int] = {}
        for cap_id, cap_name in enumerate(self._capacity_names):
            for resource_name in agent_inv_limits[cap_name].resources:
                assert resource_name in self._sim.resource_names, (
                    f"Resource {resource_name} not found in resource names"
                )
                resource_id = self._sim.resource_names.index(resource_name)
                self._resource_to_capacity_id[resource_id] = cap_id

        # Build tag_name -> tag_id mapping from the canonical id_map source
        id_map = game_config.id_map()
        tag_name_to_id = {name: idx for idx, name in enumerate(id_map.tag_names())}

        initial_replay = {
            "version": 2,
            "action_names": list(self._sim.action_ids.keys()),
            "item_names": self._sim.resource_names,
            "type_names": self._sim.object_type_names,
            "capacity_names": self._capacity_names,
            "tags": tag_name_to_id,
            "map_size": [
                self._sim.map_width,
                self._sim.map_height,
            ],
            "num_agents": self._sim.num_agents,
            "max_steps": 0,
            "mg_config": {
                "label": "MettaGrid Replay",
                "game": game_config_dict,
            },
            "objects": [],
        }

        # mettascope.init requires data_dir, replay, and autostart arguments
        json_str = json.dumps(initial_replay, allow_nan=False)
        try:
            self.response = self._mettascope.init(self._data_dir, json_str, self._autostart)
        except KeyboardInterrupt:
            logger.info("Interrupt received during mettascope init; ending episode.")
            self._sim.end_episode()
            return

    def supports_pending_render(self) -> bool:
        return True

    def _build_step_replay(self) -> dict:
        grid_objects = []
        total_rewards = self._sim.episode_rewards

        # Use zeros as placeholders for actions/rewards since we're rendering the current state
        placeholder_actions = np.zeros((self._sim.num_agents, 2), dtype=np.int32)
        placeholder_rewards = np.zeros(self._sim.num_agents)

        # To optimize, we only send walls on the first step because they don't change.
        ignore_types = []
        if self._sim.current_step > 0:
            ignore_types = ["wall"]

        all_policy_infos = self._sim._context.get("policy_infos", {})
        all_monologue_updates = self._sim._context.get("monologue_updates", {})
        all_talk_states = self._sim.talk_states()
        tutorial_overlay_phases = _extract_tutorial_overlay_phases(all_policy_infos)

        for grid_object in self._sim.grid_objects(ignore_types=ignore_types).values():
            agent_id = grid_object.get("agent_id")
            policy_infos = None
            monologue_update = {}
            talk_state = None
            if agent_id is not None:
                policy_infos = strip_monologue_transcript_tail(all_policy_infos.get(agent_id))
                monologue_update = all_monologue_updates.get(agent_id, {})
                talk_state = all_talk_states.get(agent_id)
            formatted = format_grid_object(
                grid_object,
                placeholder_actions,
                self._sim.action_success,
                placeholder_rewards,
                total_rewards,
                policy_infos=policy_infos,
                monologue_append=_monologue_append(monologue_update),
                monologue_reset=_monologue_reset(monologue_update),
                talk_text=talk_state.text if talk_state is not None else "",
                talk_remaining_steps=talk_state.remaining_steps if talk_state is not None else 0,
            )

            # Convert raw per-resource capacities to per-capacity-group format
            # so the Nim side can parse them as [[capacity_id, effective_limit], ...].
            raw = formatted.pop("inventory_capacities_raw", {})
            group_caps: Dict[int, int] = {}
            for resource_id, eff_limit in raw.items():
                cap_id = self._resource_to_capacity_id.get(resource_id)
                if cap_id is not None and cap_id not in group_caps:
                    group_caps[cap_id] = eff_limit
            formatted["inventory_capacities"] = sorted(group_caps.items())

            grid_objects.append(formatted)

        step_replay = {
            "step": self._sim.current_step,
            "objects": grid_objects,
            "episode_stats": self._sim._c_sim.get_episode_stats(),
        }
        if tutorial_overlay_phases:
            step_replay["tutorial_overlay_phases"] = tutorial_overlay_phases
        return step_replay

    def _apply_render_response(self) -> None:
        if self.response.should_close:
            self._sim.end_episode()
            return

        # Apply user actions immediately (overriding any policy actions)
        if self._sim._context.get("allow_manual_actions", True) is False:
            return
        if self.response.actions:
            for action in self.response.actions:
                raw_action: Any = action
                action_name = raw_action.action_name
                if action_name is None:
                    action_name = ""
                elif isinstance(action_name, bytes):
                    action_name = action_name.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                elif not isinstance(action_name, str):
                    logger.warning("Unexpected action_name type: %s", type(raw_action.action_name))
                    continue

                talk_text = raw_action.talk_text
                if talk_text is None:
                    talk_text = ""
                elif isinstance(talk_text, bytes):
                    talk_text = talk_text.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                elif not isinstance(talk_text, str):
                    talk_text = ""

                if not action_name:
                    if not talk_text:
                        continue

                self.defer_user_action(
                    action.agent_id,
                    Action(name=action_name or "noop", talk=talk_text or None),
                )

    def render(self) -> None:
        """Render current state and capture user input."""
        step_replay = self._build_step_replay()
        try:
            self.response = self._mettascope.render(self._sim.current_step, json.dumps(step_replay, allow_nan=False))
        except KeyboardInterrupt:
            logger.info("Interrupt received during mettascope render; ending episode.")
            self._sim.end_episode()
            return
        self._apply_render_response()

    def render_pending(self) -> None:
        """Pump one UI frame while rollout waits on a blocking policy step."""
        try:
            self.response = self._mettascope.render_pending()
        except KeyboardInterrupt:
            logger.info("Interrupt received during mettascope pending render; ending episode.")
            self._sim.end_episode()
            return
        self._apply_render_response()


def _extract_tutorial_overlay_phases(all_policy_infos: dict[int, dict]) -> list[str]:
    for infos in all_policy_infos.values():
        if not isinstance(infos, dict):
            continue
        if "tutorial_overlay_phases" not in infos:
            continue
        value = infos["tutorial_overlay_phases"]
        if not isinstance(value, list):
            continue
        phases = [phase.strip() for phase in value if isinstance(phase, str) and phase.strip()]
        if phases:
            return phases
    return []


def _monologue_append(monologue_update: object) -> str:
    if not isinstance(monologue_update, dict):
        return ""
    append = monologue_update.get("monologue_append")
    return append if isinstance(append, str) else ""


def _monologue_reset(monologue_update: object) -> bool:
    if not isinstance(monologue_update, dict):
        return False
    return bool(monologue_update.get("monologue_reset", False))


# Find the Nim bindings. Two possible locations:
#
# Source: packages/mettagrid/nim/mettascope/bindings/generated
#   - The canonical location where `nim build` outputs bindings
#   - Present when running from a repo checkout
#
# Packaged: <site-packages>/mettagrid/nim/mettascope/bindings/generated
#   - Created by PEP-517 backend copying nim/ into python/src/mettagrid/ during wheel build
#   - The copy becomes part of the installed package
_python_package_root = Path(__file__).resolve().parent.parent


def _resolve_nim_root() -> Optional[Path]:
    # Source location (repo checkout): packages/mettagrid/nim/mettascope
    # This will not exist when installed in packaged form
    source = _python_package_root.parent.parent.parent / "nim" / "mettascope"

    # Packaged location (installed wheel): <site-packages>/mettagrid/nim/mettascope
    packaged = _python_package_root / "nim" / "mettascope"

    for root in [source, packaged]:
        if (root / "bindings" / "generated").exists():
            return root

    return None


# # Type stubs for static analysis
# if TYPE_CHECKING:
#     from typing import Any

#     def init(replay: Any) -> Any: ...
#     def render(step: int, replay_step: Any) -> Any: ...

#     class MettascopeError(Exception): ...
# else:
#     # Runtime import
#     if nim_bindings_path and nim_bindings_path.exists():
#         # Insert at the beginning to ensure it's found first
#         sys.path.insert(0, str(nim_bindings_path))

#         try:
#             # Import the mettascope module
#             import mettascope

#             # Verify the module has the expected attributes
#             required_attrs = ["init", "render", "MettascopeError"]
#             missing_attrs = [attr for attr in required_attrs if not hasattr(mettascope, attr)]

#             if missing_attrs:
#                 # List what attributes are actually available
#                 available_attrs = [attr for attr in dir(mettascope) if not attr.startswith("_")]
#                 raise ImportError(
#                     f"mettascope module is missing required attributes: {missing_attrs}. "
#                     f"Available attributes: {available_attrs or 'none'}. "
#                     f"The Nim bindings may need to be regenerated."
#                 )

#             # Re-export the functions and classes
#             def init(replay):
#                 return mettascope.init(data_dir=str(nim_root / "data"), replay=replay)

#             render = mettascope.render
#             MettascopeError = mettascope.MettascopeError

#         except ImportError as e:
#             raise ImportError(
#                 f"Failed to import mettascope from {nim_bindings_path}: {e}. "
#                 "Ensure the Nim bindings have been properly generated."
#             ) from e
#         finally:
#             # Remove the path from sys.path to avoid polluting it
#             if str(nim_bindings_path) in sys.path:
#                 sys.path.remove(str(nim_bindings_path))
#     else:
#         searched = ", ".join(str(path) for path in _nim_search_paths)
#         raise ImportError(
#             "Could not find mettascope bindings. "
#             f"Searched locations: {searched}. "
#             "Ensure the Nim bindings have been generated by running the appropriate build command."
#         )

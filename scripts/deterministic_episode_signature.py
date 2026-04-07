from __future__ import annotations

import hashlib
import json

from mettagrid.config.filter import maxDistance
from mettagrid.config.game_value import InventoryValue, weighted_sum
from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig
from mettagrid.config.query import ClosureQuery, MaterializedQuery, query
from mettagrid.config.reward_config import reward
from mettagrid.config.tag import typeTag
from mettagrid.simulator import Simulation


def _round_float(value: float) -> float:
    return round(float(value), 8)


def _object_payload(sim: Simulation) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for obj_id, obj in sorted(sim.grid_objects().items()):
        entry: dict[str, object] = {
            "id": int(obj_id),
            "type_name": obj["type_name"],
            "location": [int(obj["r"]), int(obj["c"])],
            "tag_ids": [int(tag_id) for tag_id in obj.get("tag_ids", [])],
            "inventory_items": [
                (int(resource_id), int(amount)) for resource_id, amount in obj.get("inventory", {}).items()
            ],
        }
        if "agent_id" in obj:
            entry["agent_id"] = int(obj["agent_id"])
            entry["group_id"] = int(obj["group_id"])
            entry["vibe"] = int(obj["vibe"])
            entry["current_stat_reward"] = _round_float(obj["current_stat_reward"])
        payload.append(entry)
    return payload


def _stats_payload(sim: Simulation) -> dict[str, object]:
    stats = sim._c_sim.get_episode_stats()
    return {
        "game": [(name, _round_float(value)) for name, value in stats["game"].items()],
        "agent": [
            [(name, _round_float(value)) for name, value in agent_stats.items()] for agent_stats in stats["agent"]
        ],
    }


def build_signature_payload() -> dict[str, object]:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#", "#", "#", "#", "#"],
            ["#", ".", ".", ".", ".", ".", "#"],
            ["#", ".", "W", "H", "W", ".", "#"],
            ["#", ".", ".", "W", ".", ".", "#"],
            ["#", ".", ".", "@", ".", ".", "#"],
            ["#", "#", "#", "#", "#", "#", "#"],
        ],
        char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
    )
    cfg.game.actions.noop.enabled = True
    cfg.game.resource_names = ["gold", "silver"]
    cfg.game.agent.inventory.initial = {"gold": 10, "silver": 5}
    cfg.game.agent.rewards = {
        "stability": reward(
            weighted_sum(
                [
                    (1.0, InventoryValue(item="gold")),
                    (0.5, InventoryValue(item="silver")),
                ],
                log=True,
            ),
            per_tick=True,
        )
    }
    cfg.game.objects["hub"] = GridObjectConfig(name="hub", map_name="hub", tags=[typeTag("hub")])
    cfg.game.objects["wire"] = GridObjectConfig(name="wire", map_name="wire", tags=[typeTag("wire")])
    cfg.game.materialize_queries = [
        MaterializedQuery(
            tag="connected_one",
            query=ClosureQuery(
                source=typeTag("hub"),
                candidates=query(typeTag("wire")),
                edge_filters=[maxDistance(1)],
                max_items=1,
            ),
        ),
    ]

    sim = Simulation(cfg, seed=42)
    agent = sim.agent(0)
    for _ in range(2):
        agent.set_action("noop")
        sim.step()

    return {
        "seed": 42,
        "steps": sim.current_step,
        "action_success": list(sim.action_success),
        "episode_reward": [_round_float(value) for value in sim.episode_rewards],
        "objects": _object_payload(sim),
        "stats": _stats_payload(sim),
    }


def main() -> None:
    payload = build_signature_payload()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    print(hashlib.sha256(encoded.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()

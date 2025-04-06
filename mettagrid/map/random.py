import numpy as np
from typing import Optional
from .scene import Scene
from .node import Node
from omegaconf import DictConfig

class Random(Scene):
    def __init__(
        self,
        objects: DictConfig,
        agents: int | DictConfig = 0,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self._rng = np.random.default_rng(seed)
        self._objects = objects
        self._agents = agents

    def _render(self, node: Node):
        height, width = node.height, node.width
        symbols = []
        area = height * width

        if isinstance(self._agents, int):
            agents = ["agent.agent"] * self._agents
        elif isinstance(self._agents, DictConfig):
            agents = ["agent." + agent for agent, na in self._agents.items() for _ in range(na)]

        # Check if total objects exceed room size and halve counts if needed
        # TODO - fix infinite loop
        total_objects = sum(count for count in self._objects.values()) + len(agents)
        while total_objects > 2*area / 3:
            for obj_name in self._objects:
                self._objects[obj_name] = max(1, self._objects[obj_name] // 2)
                total_objects = sum(count for count in self._objects.values()) + len(agents)

        # Add all objects in the proper amounts to a single large array.
        for obj_name, count in self._objects.items():
            symbols.extend([obj_name] * count)
        symbols.extend(agents)

        assert(len(symbols) <= area), f"Too many objects in room: {len(symbols)} > {area}"
        symbols.extend(["empty"] * (area - len(symbols)))

        # Shuffle and reshape the array into a room.
        symbols = np.array(symbols).astype(str)
        self._rng.shuffle(symbols)

        node.replace(symbols.reshape(height, width))

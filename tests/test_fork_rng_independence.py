import multiprocessing as mp
import random
import sys

import numpy as np
import pytest

from mettagrid.envs.early_reset_handler import EarlyResetHandler


class _FakeGame:
    def __init__(self, max_steps: int):
        self.max_steps = max_steps


class _FakeConfig:
    def __init__(self, max_steps: int):
        self.game = _FakeGame(max_steps=max_steps)


class _FakeSim:
    def __init__(self, seed: int, max_steps: int):
        self.seed = seed
        self.config = _FakeConfig(max_steps=max_steps)


def _child(seed: int, max_steps: int, q) -> None:
    handler = EarlyResetHandler()
    handler.set_simulation(_FakeSim(seed=seed, max_steps=max_steps))
    handler.on_episode_start()
    q.put(handler._early_reset_step)


def test_early_reset_is_independent_under_fork():
    if sys.platform == "win32":
        pytest.skip("fork start method not available on Windows")

    try:
        ctx = mp.get_context("fork")
    except ValueError:
        pytest.skip("fork start method not available")

    # Mimic the training entrypoint seeding globals once in the parent.
    random.seed(598)
    np.random.seed(598)

    n = 16
    max_steps = 1_000_000
    q = ctx.Queue()
    ps = [ctx.Process(target=_child, args=(10_000 + i, max_steps, q)) for i in range(n)]
    for p in ps:
        p.start()
    outs = [q.get() for _ in ps]
    for p in ps:
        p.join()

    assert len(set(outs)) == n

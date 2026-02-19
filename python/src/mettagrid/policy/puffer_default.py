"""PufferLib 4.0-style default architecture for CoGames training.

This mirrors the shape/activation/init choices in PufferLib's CoGames torch policy:
- Flatten token observations and scale to [0, 1] (divide by 255).
- Linear encoder + GELU.
- Single-layer LSTM core (via PufferLib's LSTMWrapper).
- Linear action head (std=0.01) and value head (std=1).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import pufferlib.models
import pufferlib.pytorch
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


def _obs_to_numpy(obs: AgentObservation, obs_shape: tuple[int, ...]) -> np.ndarray:
    num_tokens, token_dim = obs_shape
    obs_array = np.zeros((num_tokens, token_dim), dtype=np.uint8)
    # Invalid token sentinel: coord=255, rest=0.
    obs_array[:, 0] = 255
    for idx, token in enumerate(obs.tokens):
        if idx >= num_tokens:
            break
        raw = np.asarray(token.raw_token, dtype=np.uint8).reshape(-1)
        if raw.size == 0:
            continue
        copy_len = min(raw.size, token_dim)
        obs_array[idx, :copy_len] = raw[:copy_len]
    return obs_array


class _PufferDefaultBase(nn.Module):
    """Feed-forward encoder/decoder used underneath PufferLib's LSTMWrapper."""

    def __init__(self, env: Any, *, hidden_size: int) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.is_continuous = False

        num_obs = int(np.prod(env.single_observation_space.shape))
        self.encoder = pufferlib.pytorch.layer_init(nn.Linear(num_obs, hidden_size))

        num_actions = int(env.single_action_space.n)
        self.decoder = pufferlib.pytorch.layer_init(nn.Linear(hidden_size, num_actions), std=0.01)
        self.value_function = pufferlib.pytorch.layer_init(nn.Linear(hidden_size, 1), std=1.0)

    def encode_observations(self, observations: torch.Tensor, state: Any = None) -> torch.Tensor:
        batch_size = observations.shape[0]
        flattened = observations.view(batch_size, -1).float() * (1.0 / 255.0)
        return F.gelu(self.encoder(flattened))

    def decode_actions(self, hidden: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.decoder(hidden)
        values = self.value_function(hidden)
        return logits, values


class _PufferDefaultStatefulImpl(StatefulPolicyImpl[dict[str, torch.Tensor | None]]):
    def __init__(
        self,
        net: nn.Module,
        policy_env_info: PolicyEnvInterface,
        device: torch.device,
        *,
        hidden_size: int,
    ) -> None:
        self._net = net
        self._device = device
        self._hidden_size = hidden_size
        self._action_names = policy_env_info.action_names
        self._obs_shape = policy_env_info.observation_space.shape

    def initial_agent_state(self) -> dict[str, torch.Tensor | None]:
        # PufferLib LSTMWrapper accepts None to mean "initialize to zeros".
        return {"lstm_h": None, "lstm_c": None}

    def step_with_state(
        self,
        obs: AgentObservation | np.ndarray,
        state: dict[str, torch.Tensor | None],
    ) -> tuple[Action, dict[str, torch.Tensor | None]]:
        if isinstance(obs, np.ndarray):
            obs_array = obs.astype(np.uint8, copy=False)
        else:
            obs_array = _obs_to_numpy(obs, self._obs_shape)

        obs_tensor = torch.from_numpy(obs_array).to(self._device).unsqueeze(0)

        self._net.eval()
        logits, _ = self._net.forward_eval(obs_tensor, state)  # type: ignore[arg-type]
        sampled, _, _ = pufferlib.pytorch.sample_logits(logits)
        action_idx = int(sampled.item())
        if action_idx < 0 or action_idx >= len(self._action_names):
            raise ValueError(
                f"Policy returned action index {action_idx}, expected range [0, {len(self._action_names) - 1}]"
            )
        return Action(name=self._action_names[action_idx]), state


class PufferDefaultPolicy(MultiAgentPolicy):
    """Trainable LSTM policy matching PufferLib 4.0's CoGames default."""

    short_names = ["puffer"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        *,
        hidden_size: int = 256,
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        super().__init__(policy_env_info, device=device, **kwargs)

        self._device = torch.device(device)
        self._hidden_size = hidden_size

        shim_env = SimpleNamespace(
            single_observation_space=policy_env_info.observation_space,
            single_action_space=policy_env_info.action_space,
            observation_space=policy_env_info.observation_space,
            action_space=policy_env_info.action_space,
            num_agents=policy_env_info.num_agents,
        )
        shim_env.env = shim_env
        self._shim_env = shim_env

        base = _PufferDefaultBase(self._shim_env, hidden_size=hidden_size)
        self._net = pufferlib.models.LSTMWrapper(
            self._shim_env,
            base,
            input_size=hidden_size,
            hidden_size=hidden_size,
        ).to(self._device)

        self._stateful_impl = _PufferDefaultStatefulImpl(
            self._net,
            policy_env_info,
            self._device,
            hidden_size=hidden_size,
        )

    def network(self) -> nn.Module:
        return self._net

    def is_recurrent(self) -> bool:
        return True

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        return StatefulAgentPolicy(self._stateful_impl, self._policy_env_info, agent_id=agent_id)

    def load_policy_data(self, policy_data_path: str) -> None:
        state = torch.load(policy_data_path, map_location=self._device, weights_only=True)
        self._net.load_state_dict(state)
        self._net = self._net.to(self._device)

    def save_policy_data(self, policy_data_path: str) -> None:
        torch.save(self._net.state_dict(), policy_data_path)

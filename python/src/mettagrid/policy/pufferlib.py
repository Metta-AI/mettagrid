"""Helpers for integrating PufferLib-trained policies with MettaGrid."""

from __future__ import annotations

import torch

import pufferlib.pytorch  # type: ignore[import-untyped]
from mettagrid.policy.policy import StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation


class PufferlibStatefulImpl(StatefulPolicyImpl[dict[str, torch.Tensor | None]]):
    """Stateful policy adapter for PufferLib models.

    Expects a PufferLib-compatible model that implements forward_eval(obs, state_dict)
    and mutates "lstm_h"/"lstm_c" in the provided state dict when recurrent.
    """

    def __init__(
        self,
        net: torch.nn.Module,
        policy_env_info: PolicyEnvInterface,
        device: torch.device,
        *,
        is_recurrent: bool,
    ) -> None:
        self._net = net
        self._action_names = policy_env_info.action_names
        self._num_tokens, self._token_dim = policy_env_info.observation_space.shape
        self._device = device
        self._is_recurrent = is_recurrent

    def reset(self) -> None:
        return None

    def initial_agent_state(self) -> dict[str, torch.Tensor | None]:
        if not self._is_recurrent:
            return {}
        return {"lstm_h": None, "lstm_c": None}

    def step_with_state(
        self,
        obs: AgentObservation,
        state: dict[str, torch.Tensor | None],
    ) -> tuple[Action, dict[str, torch.Tensor | None]]:
        obs_tensor = torch.full(
            (self._num_tokens, self._token_dim),
            fill_value=255.0,
            device=self._device,
            dtype=torch.float32,
        )
        for idx, token in enumerate(obs.tokens):
            if idx >= self._num_tokens:
                break
            raw = torch.as_tensor(token.raw_token, device=self._device, dtype=obs_tensor.dtype).flatten()
            if raw.numel() == 0:
                continue
            copy_len = min(raw.numel(), self._token_dim)
            obs_tensor[idx, :copy_len] = raw[:copy_len]

        obs_tensor = obs_tensor * (1.0 / 255.0)
        obs_tensor = obs_tensor.unsqueeze(0)

        state_dict = state if self._is_recurrent else None
        self._net.eval()
        logits, _ = self._net.forward_eval(obs_tensor, state_dict)  # type: ignore[arg-type]
        sampled, _, _ = pufferlib.pytorch.sample_logits(logits)
        action_idx = max(0, min(int(sampled.item()), len(self._action_names) - 1))
        action = Action(name=self._action_names[action_idx])

        return action, state if self._is_recurrent else {}

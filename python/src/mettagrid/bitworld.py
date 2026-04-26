"""BitWorld protocol constants and trainable action helpers."""

from __future__ import annotations

from typing import Iterable

import numpy as np

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
FRAME_PIXELS = SCREEN_WIDTH * SCREEN_HEIGHT
PROTOCOL_BYTES = FRAME_PIXELS // 2
PACKED_FRAME_SHAPE = (PROTOCOL_BYTES,)
UNPACKED_FRAME_SHAPE = (1, SCREEN_HEIGHT, SCREEN_WIDTH)
BITWORLD_DEFAULT_FRAME_STACK = 4

BUTTON_NAMES: tuple[str, ...] = ("up", "down", "left", "right", "select", "a", "b")
BUTTON_TO_MASK: dict[str, int] = {button: 1 << idx for idx, button in enumerate(BUTTON_NAMES)}
BITWORLD_INPUT_MASK_COUNT = 1 << len(BUTTON_NAMES)

DIRECTION_BUTTONS: tuple[tuple[str, ...], ...] = (
    (),
    ("up",),
    ("down",),
    ("left",),
    ("right",),
    ("up", "left"),
    ("up", "right"),
    ("down", "left"),
    ("down", "right"),
)
ACTION_BUTTONS: tuple[str | None, ...] = (None, "a", "b")


def encode_buttons(buttons: Iterable[str]) -> int:
    mask = 0
    for button in buttons:
        mask |= BUTTON_TO_MASK[button]
    return mask


def decode_buttons(mask: int) -> tuple[str, ...]:
    if not 0 <= mask < BITWORLD_INPUT_MASK_COUNT:
        raise ValueError(f"BitWorld input mask must be in [0, {BITWORLD_INPUT_MASK_COUNT}), got {mask}")
    return tuple(button for button in BUTTON_NAMES if mask & BUTTON_TO_MASK[button])


BITWORLD_ACTION_MASKS = np.asarray(
    [
        encode_buttons(direction if button is None else (*direction, button))
        for direction in DIRECTION_BUTTONS
        for button in ACTION_BUTTONS
    ],
    dtype=np.uint8,
)
BITWORLD_ACTION_COUNT = int(len(BITWORLD_ACTION_MASKS))
_ACTION_INDEX_BY_MASK = {int(mask): index for index, mask in enumerate(BITWORLD_ACTION_MASKS)}


def bitworld_input_mask_name(mask: int) -> str:
    buttons = decode_buttons(mask)
    return "+".join(buttons) if buttons else "noop"


BITWORLD_ACTION_NAMES = tuple(bitworld_input_mask_name(int(mask)) for mask in BITWORLD_ACTION_MASKS)


def bitworld_action_mask(action_index: int) -> int:
    if not 0 <= action_index < BITWORLD_ACTION_COUNT:
        raise ValueError(f"BitWorld action index must be in [0, {BITWORLD_ACTION_COUNT}), got {action_index}")
    return int(BITWORLD_ACTION_MASKS[action_index])


def bitworld_action_index(mask: int) -> int:
    try:
        return _ACTION_INDEX_BY_MASK[int(mask)]
    except KeyError as exc:
        raise ValueError(f"BitWorld input mask {mask} is not in the trainable action set") from exc


def bitworld_action_name(action_index: int) -> str:
    if not 0 <= action_index < BITWORLD_ACTION_COUNT:
        raise ValueError(f"BitWorld action index must be in [0, {BITWORLD_ACTION_COUNT}), got {action_index}")
    return BITWORLD_ACTION_NAMES[action_index]


def bitworld_action_names() -> list[str]:
    return list(BITWORLD_ACTION_NAMES)


def dpad_action_indices(*, include_noop: bool = True) -> np.ndarray:
    masks = [BUTTON_TO_MASK[button] for button in ("up", "down", "left", "right")]
    if include_noop:
        masks.insert(0, 0)
    return np.asarray([bitworld_action_index(mask) for mask in masks], dtype=np.int32)


def dpad_action_masks(*, include_noop: bool = True) -> np.ndarray:
    return BITWORLD_ACTION_MASKS[dpad_action_indices(include_noop=include_noop)].astype(np.int32)


__all__ = [
    "ACTION_BUTTONS",
    "BITWORLD_ACTION_COUNT",
    "BITWORLD_ACTION_MASKS",
    "BITWORLD_ACTION_NAMES",
    "BITWORLD_DEFAULT_FRAME_STACK",
    "BITWORLD_INPUT_MASK_COUNT",
    "BUTTON_NAMES",
    "BUTTON_TO_MASK",
    "DIRECTION_BUTTONS",
    "FRAME_PIXELS",
    "PACKED_FRAME_SHAPE",
    "PROTOCOL_BYTES",
    "SCREEN_HEIGHT",
    "SCREEN_WIDTH",
    "UNPACKED_FRAME_SHAPE",
    "bitworld_action_index",
    "bitworld_action_mask",
    "bitworld_action_name",
    "bitworld_action_names",
    "bitworld_input_mask_name",
    "decode_buttons",
    "dpad_action_indices",
    "dpad_action_masks",
    "encode_buttons",
]

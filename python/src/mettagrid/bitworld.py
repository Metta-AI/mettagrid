"""BitWorld protocol constants and trainable action helpers."""

from __future__ import annotations

from enum import IntFlag
from typing import Iterable
from urllib.parse import quote

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
FRAME_PIXELS = SCREEN_WIDTH * SCREEN_HEIGHT
PROTOCOL_BYTES = FRAME_PIXELS // 2
PACKED_FRAME_BYTES = PROTOCOL_BYTES
PACKED_FRAME_SHAPE = (PROTOCOL_BYTES,)
UNPACKED_FRAME_SHAPE = (1, SCREEN_HEIGHT, SCREEN_WIDTH)
BITWORLD_DEFAULT_FRAME_STACK = 4
PACKET_INPUT = 0
PACKET_CHAT = 1
INPUT_PACKET_BYTES = 2
RESET_INPUT_MASK = 0xFF
RESET_INPUT_PACKET = bytes([PACKET_INPUT, RESET_INPUT_MASK])

PLAYER_PATH = "/player"
GLOBAL_PATH = "/global"
REWARD_PATH = "/reward"

PICO8_PALETTE_HEX = (
    "#000000",
    "#1d2b53",
    "#7e2553",
    "#008751",
    "#ab5236",
    "#5f574f",
    "#c2c3c7",
    "#fff1e8",
    "#ff004d",
    "#ffa300",
    "#ffec27",
    "#00e436",
    "#29adff",
    "#83769c",
    "#ff77a8",
    "#ffccaa",
)

BUTTON_NAMES: tuple[str, ...] = ("up", "down", "left", "right", "select", "a", "b")
BUTTON_TO_MASK: dict[str, int] = {button: 1 << idx for idx, button in enumerate(BUTTON_NAMES)}
BITWORLD_INPUT_MASK_COUNT = 1 << len(BUTTON_NAMES)


class Button(IntFlag):
    UP = BUTTON_TO_MASK["up"]
    DOWN = BUTTON_TO_MASK["down"]
    LEFT = BUTTON_TO_MASK["left"]
    RIGHT = BUTTON_TO_MASK["right"]
    SELECT = BUTTON_TO_MASK["select"]
    A = BUTTON_TO_MASK["a"]
    B = BUTTON_TO_MASK["b"]


class ControllerState(BaseModel):
    model_config = ConfigDict(frozen=True)

    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    select: bool = False
    a: bool = False
    b: bool = False

    @classmethod
    def from_mask(cls, mask: int) -> "ControllerState":
        return cls(
            up=bool(mask & Button.UP),
            down=bool(mask & Button.DOWN),
            left=bool(mask & Button.LEFT),
            right=bool(mask & Button.RIGHT),
            select=bool(mask & Button.SELECT),
            a=bool(mask & Button.A),
            b=bool(mask & Button.B),
        )

    def mask(self) -> int:
        mask = 0
        if self.up:
            mask |= Button.UP
        if self.down:
            mask |= Button.DOWN
        if self.left:
            mask |= Button.LEFT
        if self.right:
            mask |= Button.RIGHT
        if self.select:
            mask |= Button.SELECT
        if self.a:
            mask |= Button.A
        if self.b:
            mask |= Button.B
        return int(mask)

    def packet(self) -> bytes:
        return pack_input_packet(self.mask())


class BitWorldEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    address: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    scheme: str = Field(default="ws", pattern=r"^wss?$")

    def websocket_url(self, path: str, player_name: str | None = None) -> str:
        if player_name is not None:
            normalized = player_name.strip()
            if not normalized or " " in normalized:
                raise ValueError("BitWorld player names must not be empty or contain spaces")
            return f"{self.scheme}://{self.address}:{self.port}{path}?name={quote(normalized, safe='')}"
        return f"{self.scheme}://{self.address}:{self.port}{path}"

    def player_url(self, player_name: str | None = None) -> str:
        return self.websocket_url(PLAYER_PATH, player_name)

    def global_url(self) -> str:
        return self.websocket_url(GLOBAL_PATH)

    def reward_url(self) -> str:
        return self.websocket_url(REWARD_PATH)


class BitWorldServerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, serialize_by_alias=True)

    imposter_count: int = Field(default=1, alias="imposterCount", ge=0)


class RewardEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    player: str = Field(min_length=1, pattern=r"^\S+$")
    value: int


class RewardPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: tuple[RewardEntry, ...]

    def values_by_key(self) -> dict[tuple[str, str], int]:
        return {(entry.name, entry.player): entry.value for entry in self.entries}

    def reward_for(self, player: str) -> int:
        return self.values_by_key()[("reward", player)]

    def first_reward(self) -> int:
        for entry in self.entries:
            if entry.name == "reward":
                return entry.value
        raise ValueError("reward packet does not contain a reward line")


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


def pack_input_packet(mask: int) -> bytes:
    if not 0 <= mask <= 0xFF:
        raise ValueError(f"BitWorld input mask must be in [0, 255], got {mask}")
    return bytes([PACKET_INPUT, mask])


def unpack_input_packet(packet: bytes | bytearray | memoryview) -> int:
    raw = bytes(packet)
    if len(raw) != INPUT_PACKET_BYTES or raw[0] != PACKET_INPUT:
        raise ValueError("BitWorld input packets must be two bytes: packet kind 0 followed by a button mask")
    return raw[1]


def parse_reward_packet(payload: bytes | str) -> RewardPacket:
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    entries: list[RewardEntry] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        name, player, raw_value = stripped.split()
        entries.append(RewardEntry(name=name, player=player, value=int(raw_value)))
    return RewardPacket(entries=tuple(entries))


def parse_reward_value(payload: bytes | str, player_name: str | None = None) -> int:
    packet = parse_reward_packet(payload)
    if player_name is not None:
        return packet.reward_for(player_name)
    return packet.first_reward()


def unpack_frame_pixels(packet: bytes | bytearray | memoryview) -> bytes:
    raw = bytes(packet)
    if len(raw) != PROTOCOL_BYTES:
        raise ValueError(f"BitWorld frames must be {PROTOCOL_BYTES} packed bytes, received {len(raw)}")
    pixels = bytearray(FRAME_PIXELS)
    for index, packed in enumerate(raw):
        pixels[index * 2] = packed & 0x0F
        pixels[index * 2 + 1] = packed >> 4
    return bytes(pixels)


def pack_frame_pixels(pixels: bytes | bytearray | memoryview) -> bytes:
    raw = bytes(pixels)
    if len(raw) != FRAME_PIXELS:
        raise ValueError(f"expected {FRAME_PIXELS} unpacked pixels, received {len(raw)}")
    packed = bytearray(PROTOCOL_BYTES)
    for index in range(PROTOCOL_BYTES):
        left = raw[index * 2]
        right = raw[index * 2 + 1]
        if left > 0x0F or right > 0x0F:
            raise ValueError("BitWorld frame pixels must be 4-bit palette indices")
        packed[index] = left | (right << 4)
    return bytes(packed)


__all__ = [
    "ACTION_BUTTONS",
    "BITWORLD_ACTION_COUNT",
    "BITWORLD_ACTION_MASKS",
    "BITWORLD_ACTION_NAMES",
    "BITWORLD_DEFAULT_FRAME_STACK",
    "BITWORLD_INPUT_MASK_COUNT",
    "BitWorldEndpoint",
    "BitWorldServerConfig",
    "Button",
    "BUTTON_NAMES",
    "BUTTON_TO_MASK",
    "ControllerState",
    "DIRECTION_BUTTONS",
    "FRAME_PIXELS",
    "GLOBAL_PATH",
    "INPUT_PACKET_BYTES",
    "PACKET_CHAT",
    "PACKET_INPUT",
    "PACKED_FRAME_BYTES",
    "PACKED_FRAME_SHAPE",
    "PICO8_PALETTE_HEX",
    "PLAYER_PATH",
    "PROTOCOL_BYTES",
    "RESET_INPUT_MASK",
    "RESET_INPUT_PACKET",
    "REWARD_PATH",
    "RewardEntry",
    "RewardPacket",
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
    "pack_input_packet",
    "pack_frame_pixels",
    "parse_reward_packet",
    "parse_reward_value",
    "unpack_input_packet",
    "unpack_frame_pixels",
]

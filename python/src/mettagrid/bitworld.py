"""BitWorld protocol constants and trainable action helpers."""

from __future__ import annotations

from collections import Counter
from enum import IntFlag
from pathlib import Path
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
BITWORLD_AMONG_THEM_PLAYER_COUNT = 8
BITWORLD_AMONG_THEM_IMPOSTER_COUNT = 2
BITWORLD_AMONG_THEM_TASKS_PER_PLAYER = 8
BITWORLD_AMONG_THEM_KILL_COOLDOWN_TICKS = 900
BITWORLD_AMONG_THEM_VOTE_TIMER_TICKS = 6000
PACKET_INPUT = 0
PACKET_CHAT = 1
INPUT_PACKET_BYTES = 2
CHAT_PACKET_HEADER_BYTES = 1
RESET_INPUT_MASK = 0xFF
RESET_INPUT_PACKET = bytes([PACKET_INPUT, RESET_INPUT_MASK])

PLAYER_PATH = "/player"
GLOBAL_PATH = "/global"
REWARD_PATH = "/reward"

_BITWORLD_REPLAY_MAGIC = b"BITWORLD"
_BITWORLD_REPLAY_FORMAT_VERSION = 3
_BITWORLD_REPLAY_GAME_NAME = "among_them"
_BITWORLD_REPLAY_GAME_VERSION = "1"
_BITWORLD_REPLAY_TICK_HASH_RECORD = 0x01
_BITWORLD_REPLAY_INPUT_RECORD = 0x02
_BITWORLD_REPLAY_JOIN_RECORD = 0x03
_BITWORLD_REPLAY_LEAVE_RECORD = 0x04

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


def pack_chat_packet(text: str) -> bytes:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("BitWorld chat packets require non-empty text")
    if any(ord(ch) < 0x20 or ord(ch) >= 0x7F for ch in clean_text):
        raise ValueError("BitWorld chat text must be printable ASCII")
    payload = clean_text.encode("ascii")
    return bytes([PACKET_CHAT]) + payload


def unpack_chat_packet(packet: bytes | bytearray | memoryview) -> str:
    raw = bytes(packet)
    if len(raw) <= CHAT_PACKET_HEADER_BYTES or raw[0] != PACKET_CHAT:
        raise ValueError("BitWorld chat packets must start with packet kind 1")
    payload = raw[1:]
    if any(byte < 0x20 or byte >= 0x7F for byte in payload):
        raise ValueError("BitWorld chat text must be printable ASCII")
    return payload.decode("ascii")


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


def _read_replay_uint(data: bytes, offset: int, size: int) -> tuple[int, int]:
    end = offset + size
    if end > len(data):
        raise ValueError(f"BitWorld replay is truncated at byte {offset}")
    return int.from_bytes(data[offset:end], "little"), end


def _skip_replay_string(data: bytes, offset: int) -> int:
    _value, offset = _read_replay_string(data, offset)
    return offset


def _read_replay_string(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = _read_replay_uint(data, offset, 2)
    end = offset + length
    if end > len(data):
        raise ValueError(f"BitWorld replay string is truncated at byte {offset}")
    return data[offset:end].decode(), end


def _write_replay_string(value: str) -> bytes:
    encoded = value.encode()
    if len(encoded) > 0xFFFF:
        raise ValueError("BitWorld replay strings must fit in 16 bits")
    return len(encoded).to_bytes(2, "little") + encoded


def _read_bitworld_replay_header(data: bytes) -> int:
    if not data.startswith(_BITWORLD_REPLAY_MAGIC):
        raise ValueError("BitWorld replay magic is not BITWORLD")

    offset = len(_BITWORLD_REPLAY_MAGIC)
    format_version, offset = _read_replay_uint(data, offset, 2)
    if format_version != _BITWORLD_REPLAY_FORMAT_VERSION:
        raise ValueError(f"Unsupported BitWorld replay format version: {format_version}")
    game_name, offset = _read_replay_string(data, offset)
    game_version, offset = _read_replay_string(data, offset)
    _game_seed, offset = _read_replay_uint(data, offset, 8)
    _config_json, offset = _read_replay_string(data, offset)
    if game_name != _BITWORLD_REPLAY_GAME_NAME:
        raise ValueError(f"BitWorld replay game name does not match: {game_name}")
    if game_version != _BITWORLD_REPLAY_GAME_VERSION:
        raise ValueError(f"BitWorld replay game version does not match: {game_version}")
    return offset


def validate_bitworld_replay_bytes(data: bytes | bytearray | memoryview) -> None:
    raw = bytes(data)
    offset = _read_bitworld_replay_header(raw)
    has_hash = False
    has_join = False

    while offset < len(raw):
        record_offset = offset
        record_type, offset = _read_replay_uint(raw, offset, 1)
        if record_type == _BITWORLD_REPLAY_TICK_HASH_RECORD:
            _tick, offset = _read_replay_uint(raw, offset, 4)
            _hash, offset = _read_replay_uint(raw, offset, 8)
            has_hash = True
        elif record_type == _BITWORLD_REPLAY_INPUT_RECORD:
            _time_ms, offset = _read_replay_uint(raw, offset, 4)
            _player, offset = _read_replay_uint(raw, offset, 1)
            _keys, offset = _read_replay_uint(raw, offset, 1)
        elif record_type == _BITWORLD_REPLAY_JOIN_RECORD:
            _time_ms, offset = _read_replay_uint(raw, offset, 4)
            _player, offset = _read_replay_uint(raw, offset, 1)
            offset = _skip_replay_string(raw, offset)
            _slot, offset = _read_replay_uint(raw, offset, 2)
            offset = _skip_replay_string(raw, offset)
            has_join = True
        elif record_type == _BITWORLD_REPLAY_LEAVE_RECORD:
            _time_ms, offset = _read_replay_uint(raw, offset, 4)
            _player, offset = _read_replay_uint(raw, offset, 1)
        else:
            raise ValueError(f"Unknown BitWorld replay record type {record_type} at byte {record_offset}")

    if not has_join:
        raise ValueError("BitWorld replay does not contain player joins")
    if not has_hash:
        raise ValueError("BitWorld replay does not contain tick hashes")


def rewrite_bitworld_replay_names(data: bytes | bytearray | memoryview, policy_names: list[str]) -> bytes:
    raw = bytes(data)
    offset = _read_bitworld_replay_header(raw)
    rewritten = bytearray(raw[:offset])
    policy_name_counts = Counter(policy_names)
    slot_names: list[str] = []
    for slot, policy_name in enumerate(policy_names):
        name = policy_name
        if policy_name_counts[policy_name] > 1 or name in slot_names:
            name = f"{policy_name}-slot{slot}"
        suffix = 2
        while name in slot_names:
            name = f"{policy_name}-slot{slot}-{suffix}"
            suffix += 1
        slot_names.append(name)

    while offset < len(raw):
        record_offset = offset
        record_type, offset = _read_replay_uint(raw, offset, 1)
        if record_type == _BITWORLD_REPLAY_TICK_HASH_RECORD:
            _tick, offset = _read_replay_uint(raw, offset, 4)
            _hash, offset = _read_replay_uint(raw, offset, 8)
            rewritten.extend(raw[record_offset:offset])
        elif record_type == _BITWORLD_REPLAY_INPUT_RECORD:
            _time_ms, offset = _read_replay_uint(raw, offset, 4)
            _player, offset = _read_replay_uint(raw, offset, 1)
            _keys, offset = _read_replay_uint(raw, offset, 1)
            rewritten.extend(raw[record_offset:offset])
        elif record_type == _BITWORLD_REPLAY_JOIN_RECORD:
            time_ms, offset = _read_replay_uint(raw, offset, 4)
            player, offset = _read_replay_uint(raw, offset, 1)
            offset = _skip_replay_string(raw, offset)
            slot, offset = _read_replay_uint(raw, offset, 2)
            token, offset = _read_replay_string(raw, offset)
            if slot >= len(slot_names):
                raise ValueError(f"BitWorld replay join slot {slot} has no policy name")
            name = slot_names[slot]

            rewritten.append(_BITWORLD_REPLAY_JOIN_RECORD)
            rewritten.extend(time_ms.to_bytes(4, "little"))
            rewritten.append(player)
            rewritten.extend(_write_replay_string(name))
            rewritten.extend(slot.to_bytes(2, "little"))
            rewritten.extend(_write_replay_string(token))
        elif record_type == _BITWORLD_REPLAY_LEAVE_RECORD:
            _time_ms, offset = _read_replay_uint(raw, offset, 4)
            _player, offset = _read_replay_uint(raw, offset, 1)
            rewritten.extend(raw[record_offset:offset])
        else:
            raise ValueError(f"Unknown BitWorld replay record type {record_type} at byte {record_offset}")

    validate_bitworld_replay_bytes(rewritten)
    return bytes(rewritten)


def trim_bitworld_replay_to_first_round(replay_path: Path) -> bool:
    data = replay_path.read_bytes()
    offset = _read_bitworld_replay_header(data)
    last_hash_tick = -1

    while offset < len(data):
        record_offset = offset
        record_type, offset = _read_replay_uint(data, offset, 1)
        if record_type == _BITWORLD_REPLAY_TICK_HASH_RECORD:
            tick, offset = _read_replay_uint(data, offset, 4)
            _hash, offset = _read_replay_uint(data, offset, 8)
            if tick <= last_hash_tick:
                replay_path.write_bytes(data[:record_offset])
                return True
            last_hash_tick = tick
        elif record_type == _BITWORLD_REPLAY_INPUT_RECORD:
            _time, offset = _read_replay_uint(data, offset, 4)
            _player, offset = _read_replay_uint(data, offset, 1)
            _keys, offset = _read_replay_uint(data, offset, 1)
        elif record_type == _BITWORLD_REPLAY_JOIN_RECORD:
            _time, offset = _read_replay_uint(data, offset, 4)
            _player, offset = _read_replay_uint(data, offset, 1)
            offset = _skip_replay_string(data, offset)
            _slot, offset = _read_replay_uint(data, offset, 2)
            offset = _skip_replay_string(data, offset)
        elif record_type == _BITWORLD_REPLAY_LEAVE_RECORD:
            _time, offset = _read_replay_uint(data, offset, 4)
            _player, offset = _read_replay_uint(data, offset, 1)
        else:
            raise ValueError(f"Unknown BitWorld replay record type {record_type} at byte {record_offset}")

    return False


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
    "BITWORLD_AMONG_THEM_IMPOSTER_COUNT",
    "BITWORLD_AMONG_THEM_KILL_COOLDOWN_TICKS",
    "BITWORLD_AMONG_THEM_PLAYER_COUNT",
    "BITWORLD_AMONG_THEM_TASKS_PER_PLAYER",
    "BITWORLD_AMONG_THEM_VOTE_TIMER_TICKS",
    "BITWORLD_DEFAULT_FRAME_STACK",
    "BITWORLD_INPUT_MASK_COUNT",
    "BitWorldEndpoint",
    "Button",
    "BUTTON_NAMES",
    "BUTTON_TO_MASK",
    "ControllerState",
    "DIRECTION_BUTTONS",
    "FRAME_PIXELS",
    "GLOBAL_PATH",
    "CHAT_PACKET_HEADER_BYTES",
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
    "pack_chat_packet",
    "pack_input_packet",
    "pack_frame_pixels",
    "parse_reward_packet",
    "parse_reward_value",
    "rewrite_bitworld_replay_names",
    "validate_bitworld_replay_bytes",
    "trim_bitworld_replay_to_first_round",
    "unpack_chat_packet",
    "unpack_input_packet",
    "unpack_frame_pixels",
]

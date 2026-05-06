"""BitWorld /sprite_player protocol constants and observation adapter."""

from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np

SCREEN_WIDTH = 128
SPRITE_PLAYER_PATH = "/sprite_player"
PACKET_SPRITE_PLAYER_CHAT = 0x81
PACKET_SPRITE_PLAYER_INPUT = 0x84
SPRITE_PLAYER_INPUT_PACKET_BYTES = 2
AMONG_THEM_MAX_PLAYERS = 16
SPRITE_PLAYER_HEADER_FEATURES = 4
SPRITE_PLAYER_GRID_SIZE = 32
SPRITE_PLAYER_PLAYER_FEATURE_OFFSET = SPRITE_PLAYER_HEADER_FEATURES + SPRITE_PLAYER_GRID_SIZE * SPRITE_PLAYER_GRID_SIZE
SPRITE_PLAYER_PLAYER_FEATURES = 4
SPRITE_PLAYER_BODY_FEATURE_OFFSET = (
    SPRITE_PLAYER_PLAYER_FEATURE_OFFSET + SPRITE_PLAYER_PLAYER_FEATURES * AMONG_THEM_MAX_PLAYERS
)
SPRITE_PLAYER_BODY_FEATURES = 4
SPRITE_PLAYER_TASK_FEATURE_OFFSET = (
    SPRITE_PLAYER_BODY_FEATURE_OFFSET + SPRITE_PLAYER_BODY_FEATURES * AMONG_THEM_MAX_PLAYERS
)
SPRITE_PLAYER_TASK_FEATURES = 5
SPRITE_PLAYER_TASK_COUNT = 15
SPRITE_PLAYER_FEATURES = SPRITE_PLAYER_TASK_FEATURE_OFFSET + SPRITE_PLAYER_TASK_FEATURES * SPRITE_PLAYER_TASK_COUNT
SPRITE_PLAYER_KILL_ICON_INDEX = 1
SPRITE_PLAYER_TASK_PROGRESS_INDEX = 2
SPRITE_PLAYER_TASKS_REMAINING_INDEX = 3
SPRITE_PLAYER_FLAG_TASK_ICON_VISIBLE = 1
SPRITE_PLAYER_FLAG_TASK_ARROW_VISIBLE = 2

AMONG_THEM_PHASE_LOBBY = 0
AMONG_THEM_PHASE_PLAYING = 1
AMONG_THEM_PHASE_VOTING = 2
AMONG_THEM_PHASE_VOTE_RESULT = 3
AMONG_THEM_PHASE_GAME_OVER = 4
AMONG_THEM_PHASE_ROLE_REVEAL = 5

SPRITE_PLAYER_FLAG_PLAYER_PRESENT = 1
SPRITE_PLAYER_FLAG_PLAYER_ALIVE = 4
SPRITE_PLAYER_FLAG_PLAYER_FLIP_H = 16
SPRITE_PLAYER_FLAG_PLAYER_GHOST = 32

MAP_VOID_COLOR = 12
TASK_BAR_WIDTH = 14

PLAYER_OBJECT_BASE = 1000
PROTOCOL_CHAT_ICON_OBJECT_BASE = 9200
PROTOCOL_VOTE_ICON_OBJECT_BASE = 9300
PROTOCOL_LOBBY_ICON_OBJECT_BASE = 9400
PROTOCOL_ROLE_ICON_OBJECT_BASE = 9500
PROTOCOL_RESULT_ICON_OBJECT_BASE = 9600
PROTOCOL_GAME_OVER_ICON_OBJECT_BASE = 9700

PLAYER_COLOR_NAMES = [
    "red",
    "orange",
    "yellow",
    "light blue",
    "pink",
    "lime",
    "blue",
    "pale blue",
    "gray",
    "white",
    "dark brown",
    "brown",
    "dark teal",
    "green",
    "dark navy",
    "black",
]
PLAYER_COLORS = np.array([3, 7, 8, 14, 4, 11, 13, 15, 1, 2, 5, 6, 9, 10, 12, 0], dtype=np.uint8)


@dataclass
class SpritePlayerSpriteInfo:
    width: int
    height: int
    label: str
    kind: str
    color_index: int = -1
    flip_h: bool = False
    pixels: np.ndarray | None = None


@dataclass
class SpritePlayerObjectInfo:
    x: int
    y: int
    z: int
    layer: int
    sprite_id: int


def read_u16(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def read_i16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def pack_sprite_player_input_packet(mask: int) -> bytes:
    if not 0 <= mask <= 0x7F:
        raise ValueError(f"BitWorld /sprite_player input mask must be in [0, 127], got {mask}")
    return bytes([PACKET_SPRITE_PLAYER_INPUT, mask])


def unpack_sprite_player_input_packet(packet: bytes | bytearray | memoryview) -> int:
    raw = bytes(packet)
    if len(raw) != SPRITE_PLAYER_INPUT_PACKET_BYTES or raw[0] != PACKET_SPRITE_PLAYER_INPUT:
        raise ValueError(
            "BitWorld /sprite_player input packets must be two bytes: packet kind 0x84 followed by a button mask"
        )
    return raw[1] & 0x7F


def pack_sprite_player_chat_packet(text: str) -> bytes:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("BitWorld /sprite_player chat packets require non-empty text")
    if any(ord(ch) < 0x20 or ord(ch) >= 0x7F for ch in clean_text):
        raise ValueError("BitWorld /sprite_player chat text must be printable ASCII")
    payload = clean_text.encode("ascii")
    if len(payload) > 0xFFFF:
        raise ValueError("BitWorld /sprite_player chat text is too long")
    return bytes([PACKET_SPRITE_PLAYER_CHAT]) + len(payload).to_bytes(2, "little") + payload


def snappy_decompress(data: bytes) -> bytes:
    index = 0
    expected = 0
    shift = 0
    while True:
        if index >= len(data):
            raise ValueError("truncated snappy length")
        byte = data[index]
        index += 1
        expected |= (byte & 0x7F) << shift
        if byte < 128:
            break
        shift += 7

    output = bytearray()
    while index < len(data):
        tag = data[index]
        index += 1
        tag_type = tag & 0x03
        if tag_type == 0:
            length_code = tag >> 2
            if length_code < 60:
                length = length_code + 1
            else:
                extra = length_code - 59
                if index + extra > len(data):
                    raise ValueError("truncated snappy literal length")
                length = int.from_bytes(data[index : index + extra], "little") + 1
                index += extra
            if index + length > len(data):
                raise ValueError("truncated snappy literal")
            output.extend(data[index : index + length])
            index += length
            continue

        if tag_type == 1:
            if index >= len(data):
                raise ValueError("truncated snappy copy1")
            length = ((tag >> 2) & 0x07) + 4
            offset = ((tag & 0xE0) << 3) | data[index]
            index += 1
        elif tag_type == 2:
            if index + 2 > len(data):
                raise ValueError("truncated snappy copy2")
            length = (tag >> 2) + 1
            offset = read_u16(data, index)
            index += 2
        else:
            if index + 4 > len(data):
                raise ValueError("truncated snappy copy4")
            length = (tag >> 2) + 1
            offset = read_u32(data, index)
            index += 4

        if offset <= 0 or offset > len(output):
            raise ValueError("invalid snappy copy offset")
        for _ in range(length):
            output.append(output[-offset])

    if len(output) != expected:
        raise ValueError(f"snappy length mismatch: expected {expected}, got {len(output)}")
    return bytes(output)


def png_rgba_pixels(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"not a PNG: {path}")
    offset = 8
    width = height = color_type = bit_depth = None
    compressed = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])[:4]
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth != 8 or color_type not in {2, 6}:
        raise ValueError(f"unsupported PNG format: {path}")

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    previous = bytearray(stride)
    rows: list[bytes] = []
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                row[i] = (row[i] + left) & 0xFF
            elif filter_type == 2:
                row[i] = (row[i] + up) & 0xFF
            elif filter_type == 3:
                row[i] = (row[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                row[i] = (row[i] + predictor) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type}")
        previous = row
        if channels == 4:
            rows.append(bytes(row))
        else:
            rgba = bytearray(width * 4)
            for x in range(width):
                rgba[x * 4 : x * 4 + 3] = row[x * 3 : x * 3 + 3]
                rgba[x * 4 + 3] = 255
            rows.append(bytes(rgba))
    return width, height, b"".join(rows)


def palette_candidates(client_data_dir: Path | None = None) -> list[Path]:
    candidates = []
    if client_data_dir is not None:
        candidates.append(client_data_dir / "pallete.png")
    if data_dir := os.environ.get("BITWORLD_CLIENT_DATA_DIR"):
        candidates.append(Path(data_dir) / "pallete.png")
    candidates.append(Path("/opt/bitworld/clients/data/pallete.png"))
    return candidates


def load_palette_lookup(client_data_dir: Path | None = None) -> dict[tuple[int, ...], int]:
    candidates = palette_candidates(client_data_dir)
    for path in candidates:
        if path.exists():
            width, _height, pixels = png_rgba_pixels(path)
            count = min(16, width)
            return {tuple(pixels[index * 4 : index * 4 + 4]): index for index in range(count)}
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"BitWorld /sprite_player palette not found. Searched: {searched}")


def color_index_from_name(name: str) -> int:
    lowered = name.lower().strip()
    for index, color_name in enumerate(PLAYER_COLOR_NAMES):
        if color_name == lowered:
            return index
    return -1


def actor_color_name(label: str, prefix: str) -> str:
    value = label[len(prefix) :].lower().strip()
    for suffix in (" right", " left"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].strip()
    return value


def classify_sprite_player_sprite(label: str) -> tuple[str, int, bool]:
    lowered = label.lower()
    if lowered == "map":
        return "map", -1, False
    if lowered == "task bubble":
        return "task", -1, False
    if lowered == "task arrow":
        return "arrow", -1, False
    if lowered == "imposter icon":
        return "imposter", -1, False
    if lowered == "imposter icon cooldown":
        return "imposter_cooldown", -1, False
    if lowered == "ghost icon":
        return "ghost_icon", -1, False
    if lowered == "player screen":
        return "screen", -1, False
    if lowered.startswith("task counter "):
        return "counter", -1, False
    if lowered.startswith("progress bar "):
        return "progress", -1, False
    if lowered.startswith("body "):
        return "body", color_index_from_name(lowered[len("body ") :]), False
    flip_h = lowered.endswith(" left")
    for prefix, kind in (
        ("selected player ", "player"),
        ("selected ghost ", "ghost"),
        ("player ", "player"),
        ("ghost ", "ghost"),
    ):
        if lowered.startswith(prefix):
            return kind, color_index_from_name(actor_color_name(lowered, prefix)), flip_h
    if label:
        return "text", -1, False
    return "unknown", -1, False


class SpritePlayerObservationAdapter:
    def __init__(self, client_data_dir: Path | None = None) -> None:
        self.sprites: dict[int, SpritePlayerSpriteInfo] = {}
        self.objects: dict[int, SpritePlayerObjectInfo] = {}
        self.palette_lookup = load_palette_lookup(client_data_dir)
        self.frame_count = 0

    def apply_packet(self, packet: bytes) -> bool:
        offset = 0
        changed = False
        while offset < len(packet):
            message_type = packet[offset]
            offset += 1
            if message_type == 0x01:
                if offset + 10 > len(packet):
                    return changed
                sprite_id = read_u16(packet, offset)
                width = read_u16(packet, offset + 2)
                height = read_u16(packet, offset + 4)
                compressed_len = read_u32(packet, offset + 6)
                offset += 10
                if offset + compressed_len + 2 > len(packet):
                    return changed
                compressed = packet[offset : offset + compressed_len]
                offset += compressed_len
                label_len = read_u16(packet, offset)
                offset += 2
                if offset + label_len > len(packet):
                    return changed
                label = packet[offset : offset + label_len].decode("utf-8", errors="replace")
                offset += label_len
                kind, color_index, flip_h = classify_sprite_player_sprite(label)
                pixels = None
                if kind == "map":
                    raw = snappy_decompress(compressed)
                    if len(raw) != width * height * 4:
                        raise ValueError(
                            f"BitWorld /sprite_player map sprite has {len(raw)} RGBA bytes, "
                            f"expected {width * height * 4}"
                        )
                    pixels = np.full((height, width), MAP_VOID_COLOR, dtype=np.uint8)
                    for i in range(width * height):
                        rgba = tuple(raw[i * 4 : i * 4 + 4])
                        pixels.flat[i] = self.palette_lookup[rgba]
                self.sprites[sprite_id] = SpritePlayerSpriteInfo(
                    width=width,
                    height=height,
                    label=label,
                    kind=kind,
                    color_index=color_index,
                    flip_h=flip_h,
                    pixels=pixels,
                )
                changed = True
            elif message_type == 0x02:
                if offset + 11 > len(packet):
                    return changed
                object_id = read_u16(packet, offset)
                self.objects[object_id] = SpritePlayerObjectInfo(
                    x=read_i16(packet, offset + 2),
                    y=read_i16(packet, offset + 4),
                    z=read_i16(packet, offset + 6),
                    layer=packet[offset + 8],
                    sprite_id=read_u16(packet, offset + 9),
                )
                offset += 11
                changed = True
            elif message_type == 0x03:
                if offset + 2 > len(packet):
                    return changed
                self.objects.pop(read_u16(packet, offset), None)
                offset += 2
                changed = True
            elif message_type == 0x04:
                self.objects.clear()
                changed = True
            elif message_type == 0x05:
                offset += 5
            elif message_type == 0x06:
                offset += 3
            else:
                return changed
        if changed:
            self.frame_count += 1
        return changed

    def observation(self) -> np.ndarray:
        obs = np.zeros((SPRITE_PLAYER_FEATURES,), dtype=np.uint8)
        sprites_by_object = {object_id: self.sprites[obj.sprite_id] for object_id, obj in self.objects.items()}

        map_state: tuple[SpritePlayerObjectInfo, np.ndarray] | None = None
        labels = []
        kill_icon = 0
        progress_byte = 0
        counter_value = 0
        progress_seen = False
        counter_seen = False
        for object_id, obj in self.objects.items():
            sprite = sprites_by_object[object_id]
            if sprite.kind in {"screen", "text"}:
                labels.append(sprite.label)
            elif sprite.kind == "map" and map_state is None:
                map_state = (obj, cast(np.ndarray, sprite.pixels))
            elif sprite.kind == "counter" and not counter_seen:
                counter_value = int(sprite.label.rsplit(" ", 1)[-1])
                counter_seen = True
            elif sprite.kind == "imposter":
                kill_icon = 255
            elif sprite.kind == "imposter_cooldown":
                kill_icon = max(kill_icon, 1)
            elif sprite.kind == "progress" and not progress_seen:
                percent = int(sprite.label.split()[-1].rstrip("%"))
                filled = max(0, min(TASK_BAR_WIDTH, percent * TASK_BAR_WIDTH // 100))
                progress_byte = filled * 255 // TASK_BAR_WIDTH
                progress_seen = True

        label_text = " ".join(labels).upper()
        if map_state is not None:
            phase = AMONG_THEM_PHASE_PLAYING
        elif "SKIP" in label_text:
            phase = AMONG_THEM_PHASE_VOTING
        elif "WAS KILLED" in label_text or "NO ONE" in label_text or "DIED" in label_text:
            phase = AMONG_THEM_PHASE_VOTE_RESULT
        elif "CREW WINS" in label_text or "IMPS WIN" in label_text or "DRAW" in label_text:
            phase = AMONG_THEM_PHASE_GAME_OVER
        elif "CREWMATE" in label_text or "IMPS" in label_text:
            phase = AMONG_THEM_PHASE_ROLE_REVEAL
        else:
            phase = AMONG_THEM_PHASE_LOBBY

        obs[0] = phase
        if phase == AMONG_THEM_PHASE_PLAYING and map_state is not None:
            map_object, map_pixels = map_state
            camera_x, camera_y = -map_object.x, -map_object.y
            obs[SPRITE_PLAYER_KILL_ICON_INDEX] = kill_icon
            obs[SPRITE_PLAYER_TASK_PROGRESS_INDEX] = progress_byte
            obs[SPRITE_PLAYER_TASKS_REMAINING_INDEX] = counter_value
            height, width = map_pixels.shape
            step = SCREEN_WIDTH // SPRITE_PLAYER_GRID_SIZE
            grid_start = SPRITE_PLAYER_HEADER_FEATURES
            for gy in range(SPRITE_PLAYER_GRID_SIZE):
                for gx in range(SPRITE_PLAYER_GRID_SIZE):
                    mx = camera_x + gx * step + step // 2
                    my = camera_y + gy * step + step // 2
                    value = MAP_VOID_COLOR
                    if 0 <= mx < width and 0 <= my < height:
                        value = int(map_pixels[my, mx])
                    obs[grid_start + gy * SPRITE_PLAYER_GRID_SIZE + gx] = value

        for object_id, obj in self.objects.items():
            sprite = sprites_by_object[object_id]
            vote_slot = object_id - PROTOCOL_VOTE_ICON_OBJECT_BASE
            is_vote_player_slot = 0 <= vote_slot < AMONG_THEM_MAX_PLAYERS
            is_dead_vote_candidate = is_vote_player_slot and sprite.kind == "body"
            if sprite.kind not in {"player", "ghost"} and not is_dead_vote_candidate:
                continue
            if is_vote_player_slot:
                slot = vote_slot
            elif object_id == PROTOCOL_RESULT_ICON_OBJECT_BASE:
                slot = 0
            elif PROTOCOL_CHAT_ICON_OBJECT_BASE <= object_id < PROTOCOL_CHAT_ICON_OBJECT_BASE + AMONG_THEM_MAX_PLAYERS:
                slot = object_id - PROTOCOL_CHAT_ICON_OBJECT_BASE
            else:
                slot = None
                for base in (
                    PLAYER_OBJECT_BASE,
                    PROTOCOL_VOTE_ICON_OBJECT_BASE,
                    PROTOCOL_LOBBY_ICON_OBJECT_BASE,
                    PROTOCOL_ROLE_ICON_OBJECT_BASE,
                    PROTOCOL_GAME_OVER_ICON_OBJECT_BASE,
                ):
                    base_slot = object_id - base
                    if 0 <= base_slot < AMONG_THEM_MAX_PLAYERS:
                        slot = base_slot
                        break
            if slot is None:
                continue
            sx = obj.x + 1
            sy = obj.y + 1
            flags = SPRITE_PLAYER_FLAG_PLAYER_PRESENT
            if sprite.kind == "player":
                flags |= SPRITE_PLAYER_FLAG_PLAYER_ALIVE
            elif sprite.kind == "ghost":
                flags |= SPRITE_PLAYER_FLAG_PLAYER_GHOST
            if sprite.flip_h:
                flags |= SPRITE_PLAYER_FLAG_PLAYER_FLIP_H
            base = SPRITE_PLAYER_PLAYER_FEATURE_OFFSET + slot * SPRITE_PLAYER_PLAYER_FEATURES
            obs[base] = np.uint8(max(0, min(255, sx)))
            obs[base + 1] = np.uint8(max(0, min(255, sy)))
            if 0 <= sprite.color_index < len(PLAYER_COLORS):
                obs[base + 2] = PLAYER_COLORS[sprite.color_index]
            obs[base + 3] = flags

        body_slot = 0
        for object_id, obj in sorted(self.objects.items()):
            vote_slot = object_id - PROTOCOL_VOTE_ICON_OBJECT_BASE
            if 0 <= vote_slot < AMONG_THEM_MAX_PLAYERS:
                continue
            sprite = sprites_by_object[object_id]
            if sprite.kind != "body" or body_slot >= AMONG_THEM_MAX_PLAYERS:
                continue
            base = SPRITE_PLAYER_BODY_FEATURE_OFFSET + body_slot * SPRITE_PLAYER_BODY_FEATURES
            obs[base] = np.uint8(max(0, min(255, obj.x + 1)))
            obs[base + 1] = np.uint8(max(0, min(255, obj.y + 1)))
            if 0 <= sprite.color_index < len(PLAYER_COLORS):
                obs[base + 2] = PLAYER_COLORS[sprite.color_index]
            obs[base + 3] = 1
            body_slot += 1

        task_objects = sorted(
            (object_id, obj, sprite)
            for object_id, obj in self.objects.items()
            if (sprite := sprites_by_object[object_id]).kind in {"task", "arrow"}
        )
        for task_slot, (_object_id, obj, sprite) in enumerate(task_objects):
            if task_slot >= SPRITE_PLAYER_TASK_COUNT:
                break
            base = SPRITE_PLAYER_TASK_FEATURE_OFFSET + task_slot * SPRITE_PLAYER_TASK_FEATURES
            flags = 0
            if sprite.kind == "task":
                flags |= SPRITE_PLAYER_FLAG_TASK_ICON_VISIBLE
                obs[base] = np.uint8(max(0, min(255, obj.x)))
                obs[base + 1] = np.uint8(max(0, min(255, obj.y)))
            else:
                flags |= SPRITE_PLAYER_FLAG_TASK_ARROW_VISIBLE
                obs[base + 2] = np.uint8(max(0, min(255, obj.x)))
                obs[base + 3] = np.uint8(max(0, min(255, obj.y)))
            obs[base + 4] = flags
        return obs

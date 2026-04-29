from __future__ import annotations

import pytest
from pydantic import ValidationError

from mettagrid.bitworld import (
    BITWORLD_ACTION_MASKS,
    FRAME_PIXELS,
    INPUT_PACKET_BYTES,
    PACKET_CHAT,
    PROTOCOL_BYTES,
    RESET_INPUT_PACKET,
    BitWorldEndpoint,
    Button,
    ControllerState,
    RewardEntry,
    pack_chat_packet,
    pack_frame_pixels,
    pack_input_packet,
    parse_reward_packet,
    parse_reward_value,
    unpack_chat_packet,
    unpack_frame_pixels,
    unpack_input_packet,
)


def test_controller_state_round_trips_current_bitworld_button_masks() -> None:
    state = ControllerState(up=True, right=True, select=True, a=True, b=True)

    mask = state.mask()

    assert mask == Button.UP | Button.RIGHT | Button.SELECT | Button.A | Button.B
    assert mask == 0x79
    assert ControllerState.from_mask(mask) == state
    assert state.packet() == b"\x00\x79"


def test_action_masks_match_direction_by_button_product() -> None:
    assert len(BITWORLD_ACTION_MASKS) == 27
    assert BITWORLD_ACTION_MASKS.tolist()[:6] == [0, 0x20, 0x40, 0x01, 0x21, 0x41]


def test_input_packets_match_current_bitworld_protocol() -> None:
    assert INPUT_PACKET_BYTES == 2
    assert pack_input_packet(0x21) == b"\x00\x21"
    assert unpack_input_packet(b"\x00\x21") == 0x21
    assert RESET_INPUT_PACKET == b"\x00\xff"

    with pytest.raises(ValueError):
        pack_input_packet(0x100)

    with pytest.raises(ValueError):
        unpack_input_packet(b"\x21")

    with pytest.raises(ValueError):
        unpack_input_packet(b"\x01\x21")


def test_chat_packets_match_current_bitworld_protocol() -> None:
    packet = pack_chat_packet(" body in medbay ")

    assert packet == bytes([PACKET_CHAT]) + b"body in medbay"
    assert unpack_chat_packet(packet) == "body in medbay"

    with pytest.raises(ValueError):
        pack_chat_packet("")

    with pytest.raises(ValueError):
        pack_chat_packet("not ascii: \u2603")

    with pytest.raises(ValueError):
        unpack_chat_packet(b"\x00hello")

    with pytest.raises(ValueError):
        unpack_chat_packet(bytes([PACKET_CHAT]))


def test_bitworld_endpoint_builds_protocol_urls() -> None:
    endpoint = BitWorldEndpoint(address="localhost", port=8080)

    assert endpoint.player_url("player/1") == "ws://localhost:8080/player?name=player%2F1"
    assert endpoint.global_url() == "ws://localhost:8080/global"
    assert endpoint.reward_url() == "ws://localhost:8080/reward"


def test_bitworld_endpoint_rejects_normalized_names_with_spaces() -> None:
    endpoint = BitWorldEndpoint(address="localhost", port=8080)

    with pytest.raises(ValueError):
        endpoint.player_url("player one")


def test_reward_packet_parses_entries_and_replaces_duplicates_by_key() -> None:
    packet = parse_reward_packet("reward player1 10\nadvantage player1 3\nreward player2 -4\nreward player1 12\n")

    assert packet.entries == (
        RewardEntry(name="reward", player="player1", value=10),
        RewardEntry(name="advantage", player="player1", value=3),
        RewardEntry(name="reward", player="player2", value=-4),
        RewardEntry(name="reward", player="player1", value=12),
    )
    assert packet.values_by_key() == {
        ("reward", "player1"): 12,
        ("advantage", "player1"): 3,
        ("reward", "player2"): -4,
    }
    assert packet.reward_for("player1") == 12
    assert packet.first_reward() == 10


def test_reward_value_can_select_player_or_first_reward() -> None:
    payload = b"reward player2 7\nreward player1 42\n"

    assert parse_reward_value(payload) == 7
    assert parse_reward_value(payload, "player1") == 42


def test_reward_packet_rejects_players_with_spaces() -> None:
    with pytest.raises(ValueError):
        parse_reward_packet("reward player one 1\n")

    with pytest.raises(ValidationError):
        RewardEntry(name="reward", player="player one", value=1)


def test_frame_pack_unpack_round_trip() -> None:
    pixels = bytes(index % 16 for index in range(FRAME_PIXELS))

    packed = pack_frame_pixels(pixels)

    assert len(packed) == PROTOCOL_BYTES
    assert unpack_frame_pixels(packed) == pixels


def test_frame_helpers_reject_wrong_size_and_invalid_palette_index() -> None:
    with pytest.raises(ValueError):
        unpack_frame_pixels(b"\x00")

    with pytest.raises(ValueError):
        pack_frame_pixels(bytes([0] * (FRAME_PIXELS - 1)))

    with pytest.raises(ValueError):
        pack_frame_pixels(bytes([16] + [0] * (FRAME_PIXELS - 1)))

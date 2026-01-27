"""Tests for ObservationToken coordinate accessors.

These tests document the expected behavior of row/col accessors on ObservationToken.
The goal is to ensure that:
1. PackedCoordinate.pack/unpack have consistent semantics (row, col)
2. ObservationToken.row() and .col() return correct values
3. All code paths that create ObservationTokens use consistent coordinate ordering
"""

import pytest

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.mettagrid_c import PackedCoordinate
from mettagrid.simulator import ObservationToken


class TestPackedCoordinate:
    """Tests for PackedCoordinate pack/unpack semantics."""

    def test_pack_unpack_roundtrip(self):
        """pack(row, col) -> unpack -> (row, col) should roundtrip."""
        row, col = 3, 7
        packed = PackedCoordinate.pack(row, col)
        unpacked = PackedCoordinate.unpack(packed)
        assert unpacked == (row, col), f"Expected ({row}, {col}), got {unpacked}"

    def test_pack_parameter_order_is_row_col(self):
        """pack() takes (row, col) - verify via bit layout."""
        # Per packed_coordinate.hpp: upper 4 bits = row, lower 4 bits = col
        row, col = 5, 11
        packed = PackedCoordinate.pack(row, col)
        # row in upper nibble: 5 << 4 = 0x50
        # col in lower nibble: 11 = 0x0B
        # Expected: 0x5B = 91
        assert packed == 0x5B, f"Expected 0x5B (91), got {hex(packed)} ({packed})"

    def test_unpack_returns_row_col(self):
        """unpack() returns (row, col) tuple."""
        # 0x5B = row=5 (upper nibble), col=11 (lower nibble)
        packed = 0x5B
        unpacked = PackedCoordinate.unpack(packed)
        assert unpacked == (5, 11), f"Expected (5, 11), got {unpacked}"

    def test_unpack_empty_returns_none(self):
        """unpack(0xFF) returns None for empty token marker."""
        assert PackedCoordinate.unpack(0xFF) is None


class TestObservationTokenAccessors:
    """Tests for ObservationToken.row() and .col() accessors."""

    @pytest.fixture
    def feature(self):
        """Create a test feature spec."""
        return ObservationFeatureSpec(id=1, name="test", normalization=1.0)

    def test_row_col_from_packed_coordinate(self, feature):
        """Token extracts row/col from raw_token via PackedCoordinate."""
        row, col = 7, 3
        packed = PackedCoordinate.pack(row, col)

        token = ObservationToken(
            feature=feature,
            value=42,
            raw_token=(packed, 1, 42),
        )

        # location is extracted from raw_token[0] via PackedCoordinate.unpack()
        assert token.row() == row, f"Expected row={row}, got {token.row()}"
        assert token.col() == col, f"Expected col={col}, got {token.col()}"

    def test_location_is_named_tuple(self, feature):
        """Token.location returns a Location named tuple with row/col attributes."""
        row, col = 5, 9
        packed = PackedCoordinate.pack(row, col)

        token = ObservationToken(
            feature=feature,
            value=10,
            raw_token=(packed, 1, 10),
        )

        # location is a named tuple with row/col attributes
        assert token.location.row == row, f"Expected row={row}, got {token.location.row}"
        assert token.location.col == col, f"Expected col={col}, got {token.location.col}"

    def test_location_tuple_indexing_matches_accessors(self, feature):
        """Verify relationship between location tuple indices and row/col accessors."""
        row, col = 10, 12  # PackedCoordinate supports values 0-14
        packed = PackedCoordinate.pack(row, col)

        token = ObservationToken(
            feature=feature,
            value=0,
            raw_token=(packed, 1, 0),
        )

        # location is (row, col): location[0] -> row(), location[1] -> col()
        assert token.row() == token.location[0]
        assert token.col() == token.location[1]
        # Also works with named attributes
        assert token.row() == token.location.row
        assert token.col() == token.location.col
        # x/y aliases: x=col, y=row
        assert token.location.x == col
        assert token.location.y == row

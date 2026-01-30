import numpy as np

from mettagrid.mettagrid_c import PackedCoordinate
from mettagrid.simulator.interface import Location


class ObservationHelper:
    """Helper class for observation-related operations."""

    @staticmethod
    def find_tokens(
        obs: np.ndarray,
        location: None | Location = None,
        feature_id: None | int = None,
        value: None | int = None,
    ) -> np.ndarray:
        """Filter tokens by location, feature id, and value."""
        tokens = obs
        if location is not None:
            tokens = tokens[tokens[:, 0] == PackedCoordinate.pack(location.row, location.col)]
        if feature_id is not None:
            tokens = tokens[tokens[:, 1] == feature_id]
        if value is not None:
            tokens = tokens[tokens[:, 2] == value]
        return tokens

    @staticmethod
    def find_token_values(
        obs: np.ndarray,
        location: None | Location = None,
        feature_id: None | int = None,
        value: None | int = None,
    ) -> np.ndarray:
        """Find the values of tokens by location, feature id, and value.

        Note that because this returns a numpy array, if the array has a single value, you can check equality
        against this as if it were a scalar.
        """
        tokens = ObservationHelper.find_tokens(obs, location, feature_id, value)
        return tokens[:, 2]

    @staticmethod
    def get_positions_from_tokens(tokens: np.ndarray) -> list[Location]:
        """Extract positions from tokens as Location objects.

        Returned Location objects support both .row/.col and .x/.y accessors.
        """
        positions = []
        for token in tokens:
            coords = PackedCoordinate.unpack(token[0])
            if coords:
                positions.append(Location(*coords))
        return positions

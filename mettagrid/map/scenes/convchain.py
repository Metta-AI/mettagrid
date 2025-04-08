from typing import Any
import random
import math
import numpy as np
import numpy.typing as npt
from mettagrid.map.scene import Scene
from mettagrid.map.node import Node


class ConvChain(Scene):
    """
    ConvChain scene generator, based on https://github.com/mxgmn/ConvChain.
    
    This algorithm generates patterns similar to a given sample pattern.
    It uses a statistical model to capture local features of the sample
    and then generates new patterns with similar local characteristics.
    """
    def __init__(self, pattern: str, receptor_size: int = 2, iterations: int = 2, temperature: float = 0.3, children: list[Any] = []):
        super().__init__(children=children)
        self._pattern = pattern
        self._receptor_size = receptor_size

        # Parse the pattern string into a 2D boolean array
        self._parse_pattern(self._pattern)
        self._iterations = iterations
        self._temperature = temperature

    def _parse_pattern(self, pattern: str):
        """Parse a string pattern into a 2D boolean array."""

        lines = []
        for line in pattern.strip().split('\n'):
            if line[0] != '|' or line[-1] != '|':
                raise ValueError("Pattern must be enclosed in | characters")
            line = line[1:-1]
            if not all(c == '#' or c == ' ' for c in line):
                raise ValueError("Pattern must be composed of # and space characters")
            lines.append(line)

        height = len(lines)
        width = max(len(line) for line in lines)
        if not all(len(line) == width for line in lines):
            raise ValueError("All lines must be the same width")
        
        result: npt.NDArray[np.bool_] = np.zeros((height, width), dtype=bool)
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                result[y, x] = char == '#'
        
        sample = result
        n = self._receptor_size

        weights = np.zeros(1 << (n * n))
        
        # Calculate weights from the sample
        for y in range(sample.shape[0]):
            for x in range(sample.shape[1]):
                patterns = []
                
                # Create the base pattern and its rotations/reflections
                p0 = Pattern(sample, x, y, n)
                p1 = p0.rotated()
                p2 = p1.rotated()
                p3 = p2.rotated()
                p4 = p0.reflected()
                p5 = p1.reflected()
                p6 = p2.reflected()
                p7 = p3.reflected()
                
                patterns = [p0, p1, p2, p3, p4, p5, p6, p7]
                
                for p in patterns:
                    weights[p.index()] += 1
        
        # Ensure all weights are positive
        weights = np.maximum(weights, 0.1)

        self._weights = weights

    def _render(self, node: Node):
        # Generate the field using the ConvChain algorithm
        field = np.random.choice([False, True], size=node.grid.shape)
        n = self._receptor_size
        weights = self._weights
        
        # Define energy calculation function
        def energy_exp(i: int, j: int) -> float:
            value = 1.0
            for y in range(j - n + 1, j + n):
                for x in range(i - n + 1, i + n):
                    x_wrapped = x % node.width
                    y_wrapped = y % node.height
                    pattern = Pattern(field, x_wrapped, y_wrapped, n)
                    value *= weights[pattern.index()]
            return value
        
        # Define Metropolis update function
        def metropolis(i: int, j: int) -> None:
            p = energy_exp(i, j)
            field[j, i] = not field[j, i]  # Flip the bit
            q = energy_exp(i, j)
            
            # Revert the change with some probability
            if math.pow(q / p, 1.0 / self._temperature) < random.random():
                field[j, i] = not field[j, i]  # Flip back
        
        # Run the Metropolis algorithm
        for _ in range(self._iterations * node.width * node.height):
            i = random.randint(0, node.width - 1)
            j = random.randint(0, node.height - 1)
            metropolis(i, j)
            
        # Apply the generated field to the node grid
        for y in range(node.height):
            for x in range(node.width):
                node.grid[y, x] = "wall" if field[y, x] else "empty"

class Pattern:
    """Helper class for handling patterns in the ConvChain algorithm."""
    
    def __init__(self, field: np.ndarray, x: int, y: int, size: int):
        self.data = np.zeros((size, size), dtype=bool)
        field_height, field_width = field.shape
        
        for j in range(size):
            for i in range(size):
                wrapped_x = (x + i) % field_width
                wrapped_y = (y + j) % field_height
                self.data[j, i] = field[wrapped_y, wrapped_x]
    
    def size(self) -> int:
        """Return the size of the pattern."""
        return self.data.shape[0]
    
    def rotated(self) -> 'Pattern':
        """Return a new pattern that is this pattern rotated 90 degrees clockwise."""
        result = Pattern.__new__(Pattern)
        size = self.size()
        result.data = np.zeros((size, size), dtype=bool)
        
        for y in range(size):
            for x in range(size):
                result.data[y, x] = self.data[size - 1 - x, y]
                
        return result
    
    def reflected(self) -> 'Pattern':
        """Return a new pattern that is this pattern reflected horizontally."""
        result = Pattern.__new__(Pattern)
        size = self.size()
        result.data = np.zeros((size, size), dtype=bool)
        
        for y in range(size):
            for x in range(size):
                result.data[y, x] = self.data[y, size - 1 - x]
                
        return result
    
    def index(self) -> int:
        """Convert the pattern to an integer index for the weights array."""
        result = 0
        size = self.size()
        
        for y in range(size):
            for x in range(size):
                if self.data[y, x]:
                    result += 1 << (y * size + x)
                    
        return result

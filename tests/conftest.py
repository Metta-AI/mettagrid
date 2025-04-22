import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# This will be needed if your Cython modules require specific setup
# or if you need to mock certain components for testing

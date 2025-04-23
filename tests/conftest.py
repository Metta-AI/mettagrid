"""
Configuration file for pytest to properly test Cython modules.

This file sets up the necessary configurations and fixtures for testing
Cython-based code using pytest-cython.
"""

import os
import sys
from pathlib import Path

import pytest
from _pytest.python import Module


def pytest_collect_file(file_path: Path, parent):
    if file_path.suffix == ".pyx" and file_path.name.startswith("test_"):
        return Module.from_parent(parent, path=file_path)


def pytest_configure(config):
    """
    Configure pytest to work with Cython modules.

    - Add the current directory to sys.path
    - Register markers related to Cython testing
    """
    # Add the current directory to sys.path if not already there
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Register custom markers
    config.addinivalue_line("markers", "cython: mark test to run with Cython support")
    config.addinivalue_line("markers", "cpp: mark test that tests C++ functionality")


@pytest.fixture(scope="session")
def cython_extension_path():
    """
    Return the path to the directory containing Cython-compiled extensions.

    By default, this would be the 'build' directory created by setup.py build_ext --inplace.
    """
    # Check for common build directories
    build_dirs = ["build", "cython_build", "."]

    for build_dir in build_dirs:
        if os.path.isdir(build_dir):
            return build_dir

    # If no build directory is found, use the current directory
    return "."


@pytest.fixture(scope="session")
def cython_imports():
    """
    Return a list of module names that should be imported before running Cython tests.
    """
    return ["mettagrid.grid_object"]

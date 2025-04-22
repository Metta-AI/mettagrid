"""
Build script for the Metta Grid Cython extensions.

This setup file configures the build process for all Cython extension modules,
with configurable debug and performance modes.
"""

import multiprocessing
import os
import sys

import numpy
from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup

# Enable multiprocessing support
multiprocessing.freeze_support()

# Build configuration
DEBUG = os.getenv("DEBUG", "0") == "1"
ANNOTATE = os.getenv("ANNOTATE", "0") == "1"
BUILD_DIR = "build_debug" if DEBUG else "build"
NUM_THREADS = multiprocessing.cpu_count() if sys.platform == "linux" else None

# Create build directory
os.makedirs(BUILD_DIR, exist_ok=True)


def build_ext(sources, module_name=None):
    """
    Create an Extension object for the given sources.

    Args:
        sources: List of source files
        module_name: Optional module name, if None, derived from the first source file

    Returns:
        Extension object configured with appropriate settings
    """
    if module_name is None:
        module_name = sources[0].replace("/", ".").replace(".pyx", "").replace(".cpp", "")

    return Extension(
        module_name,
        sources,
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
        language="c++",
        extra_compile_args=["-std=c++11"],  # Add C++11 flag to fix defaulted function definition error
    )


# List of extension modules to build
ext_modules = [
    build_ext(["mettagrid/action_handler.pyx"]),
    build_ext(["mettagrid/event.pyx"]),
    build_ext(["mettagrid/grid.cpp"]),
    build_ext(["mettagrid/grid_env.pyx"]),
    build_ext(["mettagrid/grid_object.pyx"]),
    build_ext(["mettagrid/stats_tracker.cpp"]),
    build_ext(["mettagrid/observation_encoder.pyx"]),
    build_ext(["mettagrid/actions/attack.pyx"]),
    build_ext(["mettagrid/actions/attack_nearest.pyx"]),
    build_ext(["mettagrid/actions/change_color.pyx"]),
    build_ext(["mettagrid/actions/move.pyx"]),
    build_ext(["mettagrid/actions/noop.pyx"]),
    build_ext(["mettagrid/actions/rotate.pyx"]),
    build_ext(["mettagrid/actions/swap.pyx"]),
    build_ext(["mettagrid/actions/put_recipe_items.pyx"]),
    build_ext(["mettagrid/actions/get_output.pyx"]),
    build_ext(["mettagrid/objects/agent.pyx"]),
    build_ext(["mettagrid/objects/constants.pyx"]),
    build_ext(["mettagrid/objects/converter.pyx"]),
    build_ext(["mettagrid/objects/metta_object.pyx"]),
    build_ext(["mettagrid/objects/production_handler.pyx"]),
    build_ext(["mettagrid/objects/wall.pyx"]),
    build_ext(["mettagrid/mettagrid.pyx"], "mettagrid.mettagrid_c"),
]

# Cython compiler directives based on build mode
compiler_directives = {
    # Always use Python 3 syntax
    "language_level": 3,  # Using integer instead of string
    # String handling
    "c_string_encoding": "utf-8",
    "c_string_type": "str",
}

# Add debug directives only when DEBUG is enabled
if DEBUG:
    debug_directives = {
        # Debug-specific directives
        "embedsignature": True,
        "annotation_typing": True,
        "cdivision": True,
        "boundscheck": True,
        "wraparound": True,
        "initializedcheck": True,
        "nonecheck": True,
        "overflowcheck": True,
        "overflowcheck.fold": True,
        "profile": True,
        "linetrace": True,
    }
    compiler_directives.update(debug_directives)
else:
    # Performance mode directives (disable safety checks for speed)
    perf_directives = {
        "embedsignature": False,
        "cdivision": False,  # Enable fast C division
        "boundscheck": False,  # Disable bounds checking
        "wraparound": False,  # Disable negative indexing
        "initializedcheck": False,  # Disable checking if C arrays are initialized
        "nonecheck": False,  # Disable None checking
        "overflowcheck": False,  # Disable overflow checking
    }
    compiler_directives.update(perf_directives)

# Setup the package
setup(
    name="metta",
    version="0.1",
    packages=find_packages(),
    nthreads=NUM_THREADS,
    entry_points={
        "console_scripts": [
            # If you want to create any executable scripts in your package
            # For example: 'script_name = module:function'
        ]
    },
    include_dirs=[numpy.get_include()],
    ext_modules=cythonize(
        ext_modules,
        build_dir=BUILD_DIR,
        compiler_directives=compiler_directives,
        annotate=DEBUG or ANNOTATE,
    ),
    zip_safe=False,
)

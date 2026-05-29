# BUILD file for mettagrid tests
load("@rules_cc//cc:defs.bzl", "cc_test")

# Basic compiler flags
COPTS = [
    "-std=c++20",
    "-fvisibility=hidden",
    "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
    # "-fsanitize=address",  # Disabled - causes issues on macOS
]

cc_test(
    name = "test_stats_tracker",
    srcs = ["test_stats_tracker.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_grid_object",
    srcs = ["test_grid_object.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_mettagrid",
    srcs = ["test_mettagrid.cpp"],
    copts = COPTS + ["-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid/cpp:mettagrid_bindings",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_observations",
    srcs = ["test_observations.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_has_inventory",
    srcs = ["test_has_inventory.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

# test_handler and test_tag_lifecycle define their own main() — no gtest dep.
cc_test(
    name = "test_handler",
    srcs = ["test_handler.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_aoe_tracker",
    srcs = ["test_aoe_tracker.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@googletest//:gtest_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

cc_test(
    name = "test_tag_lifecycle",
    srcs = ["test_tag_lifecycle.cpp"],
    copts = COPTS + ["-Icpp/include/mettagrid", "-Itests"],
    linkstatic = True,
    size = "small",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

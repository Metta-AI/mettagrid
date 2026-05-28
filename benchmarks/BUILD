# Benchmarks for mettagrid

# Bazel 9 requires explicit load() for cc_binary (removed from native rules)
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "test_mettagrid_env_benchmark",
    srcs = ["test_mettagrid_env_benchmark.cpp"],
    copts = [
        "-std=c++20",
        "-O3",
        "-DNDEBUG",
        "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
    ],
    linkstatic = True,
    deps = [
        "//packages/mettagrid/cpp:mettagrid_bindings",
        "@google_benchmark//:benchmark_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

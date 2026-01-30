# Benchmarks for mettagrid

# Bazel 9 requires explicit load() for cc_binary (removed from native rules)
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "test_mettagrid_env_benchmark",
    srcs = [
        "test_mettagrid_env_benchmark.cpp",
        # We need to include the bindings sources directly
        # since the benchmark uses MettaGrid APIs directly
        "//cpp:bindings/mettagrid_c.cpp",
        "//cpp:bindings/mettagrid_c.hpp",
        "//cpp:bindings/mettagrid_py.cpp",
    ],
    copts = [
        "-std=c++20",
        "-O3",
        "-DNDEBUG",
        "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
        "-Icpp/include/mettagrid",  # To find actions/, objects/ headers
        "-Icpp",  # To find bindings/mettagrid_c.hpp
    ],
    linkstatic = True,
    deps = [
        "//cpp:mettagrid_core",
        "@google_benchmark//:benchmark_main",
        "@rules_python//python/cc:current_py_cc_libs",
    ],
)

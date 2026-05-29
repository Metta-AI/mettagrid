# Benchmarks for mettagrid
load("@rules_cc//cc:defs.bzl", "cc_binary")

# Kept as a cc_binary (not cc_test) so it builds in bazel CI but doesn't
# run. It embeds CPython via `pybind11::scoped_interpreter`, and the
# embedded interpreter can't locate its stdlib under bazel's sandbox
# without PYTHONHOME + stdlib runfiles wiring. The previous `metta cpptest
# --benchmark` path silently info-logged the same segfault and moved on;
# build-only coverage matches that net signal honestly. Run on demand
# from a real shell once the embed-init story is sorted.
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

# BUILD file for custom lint rules

load("@rules_shell//shell:sh_binary.bzl", "sh_binary")
load(":clang_tidy.bzl", "clang_tidy_test", "clang_tidy_all")

# Wrapper for system clang-tidy
sh_binary(
    name = "clang_tidy_wrapper",
    srcs = ["clang_tidy_wrapper.sh"],
    visibility = ["//visibility:public"],
)

# Run clang-tidy on all C++ targets and fail if there are issues.
# "manual" so 'bazel test //...' skips it: the .clang-tidy config uses
# ExcludeHeaderFilterRegex, which CI's clang-tidy doesn't recognize and
# reports as an error on every source file. Run on demand with
# 'bazel test //packages/mettagrid/lint:clang_tidy'. Drop the tag once
# the config is compatible with the version we ship.
clang_tidy_test(
    name = "clang_tidy",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "//packages/mettagrid:mettagrid_c",
    ],
    tags = ["manual"],
)

# Run clang-tidy and generate a report (doesn't fail)
clang_tidy_all(
    name = "clang_tidy_report",
    deps = [
        "//packages/mettagrid:mettagrid_lib",
        "//packages/mettagrid:mettagrid_c",
    ],
)

# Alias for convenience
alias(
    name = "lint",
    actual = ":clang_tidy",
    visibility = ["//visibility:public"],
)

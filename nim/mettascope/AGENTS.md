# A style guide for Nim.
by treeform

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as RFC requirements for this style.

## General Guidelines

- **MUST:** Be data-oriented.
- **MUST:** Be explicit.
- **MUST:** Be ergonomic at API boundaries.
- **MUST:** Be pragmatic about safety and performance tradeoffs.
- **MUST:** Prefer flat data representations (`seq`, arrays, enums, primitive numeric types).
- **MUST:** Map parsing and coercion failures to library-specific exceptions. (LibraryName + "Error")
- **MUST:** Raise an exception for operations that can fail (often wrapping `IOError`).
- **MUST:** Keep internals explicit and low-level.
- **MUST NOT:** Use `return result` in procedures, that line is implied by the compiler.

- **SHOULD:** Implement behavior with free `proc`s over data, not deep type hierarchies.
- **SHOULD:** Prefer strongly procedural, data-centric flow with few abstraction layers.
- **SHOULD:** Declare `raises` effects explicitly.
- **SHOULD:** Use descriptive error messages, not opaque status codes.
- **SHOULD:** Select behavior via enums and explicit `case` statements.
- **SHOULD:** Define local `proc` or `template` helpers near use sites for complex algorithms.
- **SHOULD:** Keep public APIs broad and ergonomic (for example, `Context` canvas-like API).
- **SHOULD:** Compose wrappers from lower-level primitives rather than introducing hidden state magic.
- **SHOULD:** Embrace API coercion where useful (converters and union inputs).
- **SHOULD:** Prefer explicit loops and `case` branches over extra abstraction layers.
- **SHOULD:** Prefer graceful boundary semantics where safe operations can return neutral values or no-op.
- **SHOULD:** Generate code as a data-first runtime, not an abstraction-first framework.
- **SHOULD:** Build systems around an explicit `tick` pipeline with deterministic phase ordering.
- **SHOULD:** Keep protocol and state logic visible in loops, conditionals, and structs.
- **SHOULD:** Include fault simulation controls directly in runtime config for testability.
- **SHOULD:** Preserve one stable public facade while selecting platform-specific implementations at compile time.
- **SHOULD:** Normalize platform and native event details into shared domain enums and callbacks.
- **SHOULD:** Keep create and init paths symmetric with destroy and close paths, including callback and resource cleanup.
- **SHOULD:** Prefer `mummy` for servers, `curly` for http clients, `jsony` for json, `zippy` for gzip, over the standard library.
- **SHOULD:** Use a `return` statement if function is larger than 3 lines and not rely on implicit returns, if the function is larger than 3 lines.

- **SHOULD NOT:** Use dynamic polymorphism as the default mechanism; prefer enum plus `case` dispatch.
- **SHOULD NOT:** Use hidden dynamic dispatch for core blend, fill, or render control flow.
- **SHOULD NOT:** Introduce deep OO architecture.
- **SHOULD NOT:** Hide control flow behind generic indirection.
- **SHOULD NOT:** Prioritize abstraction purity over data movement clarity.
- **SHOULD NOT:** Assume runtime checks remain enabled in release for hot modules.
- **SHOULD NOT:** Replace explicit protocol handling with opaque serialization layers in core runtime code.
- **SHOULD NOT:** Rely on unbounded queues or histories in long-running systems.
- **SHOULD NOT:** Evaluate side-effectful expressions more than once inside macro or template generated accessors.

- **MAY:** Use converters to reduce friction at call sites.
- **MAY:** Use macros or templates for domain syntax sugar when they preserve explicit data flow and predictable behavior.
- **MAY:** Use compile-time feature flags to switch backends pragmatically while keeping public behavior stable.
- **MAY:** Follow this file structure for the project:
  - `README.md` - Readme.
  - `LICENSE` - License.
  - `*.nimble` - Nimble file that has the dependencies and version.
  - `src/libraryname.nim` - Main file.
  - `src/libraryname/common.nim` - Common functions and types.
  - `src/libraryname/*s.nim` - Almost all code should be in this flat directory structure.
  - `tests/` - Test cases.
  - `tests/tests.nim` - Main test entry point.
  - `tests/bench_*.nim` - Benchmark cases.
  - `tests/manual_*.nim` - Manual tests that are usually GUI based or require user interaction.
  - `.github/workflows/build.yml` - GitHub workflows for building and testing.
  - `tools/` - Tools.
  - `tools/gen_*.nim` - Tools that generate data or atlases.
  - `docs/` - Documentation, usually just images for the readme.
  - `examples/` - Examples, usually double up as tests and documentation.
  - `experiments/` - Experiments, usually standalone files for humans.

## Anatomy of a Nim file

- **SHOULD:** Structure each Nim file in this order: Imports, Constants, Types, Variables, Procedures.
- **SHOULD NOT:** Use `when isMainModule` except rarely.
- **MUST NOT:** Use `when isMainModule` for tests.


## Imports

- **SHOULD:** Order imports as standard library modules, then external modules, then local modules.
- **SHOULD:** Keep imports grouped in a compact, readable layout, ideally in three lines as shown:
```
import
  std/[os, random, strutils],
  fidget2, boxy, windy,
  common, internal, models, widgets.
```

- **SHOULD:** Use plural module names unless the module is `common.nim`.
- **SHOULD:** Name domain modules in plural form (for example, use `players.nim` for Player logic).
- **SHOULD:** Prefer single English words for module names.
- **MAY:** Use `test_`, `manual_`, `gen_` or `bench_` prefixes for test, manual, generator and benchmark modules.

## Tests

- **SHOULD NOT:** Use a unit test framework by default.
- **SHOULD:** Use simple `doAssert` and `echo`-based tests.
- **SHOULD:** Keep tests as simple as possible.
- **SHOULD:** Start with a single `tests/tests.nim` file.

```nim
echo "Testing equality"
doAssert a == b, "a should be equal to b"
```

- **MAY:** Split tests into multiple files when the suite grows, using `test_` prefixes.

- **SHOULD:** Treat benchmarking as important as testing.
- **SHOULD:** Add `bench_*.nim` files using the `benchy` library.

```nim
import benchy, std/os, std/random

timeIt "number counter":
  var s = 0
  for i in 0 .. 1_000_000:
    s += s
```

## Names

- **SHOULD:** Prefer single English-word names.
- **SHOULD:** Use two or three words only when necessary.
- **MUST:** Use `camelCase` for variables and functions.
- **MUST:** Use `PascalCase` for types, constants, and enums.
- **SHOULD:** Use plural names for arrays, maps, and other collections.
- **SHOULD:** Use `i`, `j`, `k` for integer loop indices when appropriate.
- **SHOULD NOT:** Prefix enums with polish notation (for example, `nkStatement` -> `StatementNode`).

## Variables

- **MUST:** Use top-level `const` over `let`.
- **MUST:** Use `PascalCase` for `const` names.
- **MUST:** Use `let` over `var` unless mutation is required.
- **MUST:** Merge adjacent `const`, `let`, and `var` declarations into grouped blocks.
```
let a = 1
let b = 2
let c = 3
->
let
  a = 1
  b = 2
  c = 3
```

## Readme

- **MUST:** Restrict README edits to spelling and grammar fixes unless explicitly requested otherwise.
- **SHOULD NOT:** Use emoji in the README.
- **SHOULD NOT:** Use fancy quotes, mdash, semicolons, or other decorative punctuation.
- **SHOULD:** Write in a simple, clear, direct style.
- **MAY:** Use bullet lists or tables to present features clearly.

## Indentation

- **MUST:** Use 2 spaces for indentation.
- **MUST:** Never use double lines between types, procedures, or sections.
- **SHOULD NOT:** Go over 80 characters per line.
- **MAY:** Keep lines under 60 characters except for strings and comments.
- **MUST:** Break long function calls into one argument per line.

```nim
func(
  arg1,
  arg2,
  arg3
)
```

- **MUST:** Break long `if` and loop conditions across lines.
- **MUST:** Indent the corresponding body by 4 spaces in that style.

```nim
if condition or
  longCondition or
  anotherLongCondition:
    statement1
    statement2
    statement3
```

- **MUST NOT:** Add extra indentation before `case` branches.
- **SHOULD:** Prefer enums with `case` statements.
- **SHOULD:** Avoid single line if statements, break them into two lines:
```
if condition:
  do(something(possible() + complex))
```
- **SHOULD:** Prefer indented ternary operators.
```nim
v =
  if condition:
    value1
  else:
    value2
```
- **MAY:** Avoid ternary operators altogether.

## Comments

- **MUST:** Write comments as complete sentences.
- **MUST:** Start comments with a capital letter and end with a period.
- **MUST:** Add doc comments for every function.
- **SHOULD:** Keep doc comments to a single line where possible.
- **MUST NOT:** Exceed 4 lines for a doc comment.
- **SHOULD NOT:** Use top-level section comments, especially decorative separators made of `=` or `#`.

## Numbers

- **MUST:** Never use `1.0'f32` or `1.0'f64`, use `1.0'f` and `1.0` instead.

## For loops

- **MUST:** Add a space between the range operator and the range values: `0 ..< 5` or `1 .. 3`.
- **MAY:** Use `i`, `j`, `k` for integer loop indices when appropriate.
- **MAY:** Use single letter variables for loop indices when appropriate, like `a` for account, `p` for player, `s` for session, etc...

## Error Handling

- **SHOULD:** Let exceptions propagate to the top level.
- **SHOULD NOT:** Silence errors with broad `try/except`.
- **SHOULD NOT:** Use error codes unless absolutely necessary.
- **SHOULD:** Use asserts at procedure boundaries where invariants matter.
- **SHOULD:** Prefer simple neutral returns (`nil`, `""`, `0`, `false`) for non-exceptional fallthrough cases.

## Checking the code

- **SHOULD:** Run `nim check` and look at output and only then run `nim r tests/tests.nim` while developing when available.
- **MUST:** Run checks after major changes and before committing.

## Commit messages

- **MUST:** Use very short commit messages, usually one line.
- **SHOULD:** Use 4 to 10 words max. Can use commas to separate the words.
  - `added a new feature X`
  - `fix bug with X`
  - `refactor code around X`
  - `update documentation for X`
  - `add test for X`
  - `improved performance by X`

## When making changes

When making changes please just run the nim code with `nim r path/to/file.nim` to see if it works. Don't do check or compile, just run it. If there are any compile-time or runtime issues with the code, please fix them and then run it again.

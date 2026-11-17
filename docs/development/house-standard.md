# Software Engineering House Standard

## Purpose

This document defines the default software-engineering philosophy for projects developed under this house style.

It is inspired by the enduring principles of *The Art of Unix Programming*, but updates them for modern software development, current tooling, browser-based interfaces, reproducible research, embedded scripting, structured data formats, continuous integration, and coding agents.

The guiding idea is simple:

> Build software whose behavior, state, interfaces, and assumptions remain explicit, inspectable, composable, portable, and easy to reason about locally.

This document is a **default**, not a dogma. Project-specific constraints may override any recommendation when there is a concrete reason to do so.

When a project departs from these defaults, the deviation should preferably be intentional and documented.

---

## 1. Core philosophy

The primary goals are:

- clarity;
- simplicity;
- modularity;
- inspectability;
- explicit interfaces;
- textual configuration;
- data portability;
- reproducibility;
- local reasoning;
- conservative dependencies;
- composability where natural;
- automation over human memory;
- incremental evolution over rewrites;
- machine-verifiable contracts where practical.

The preferred result is software that is easy to understand, test, automate, inspect, debug, extend, bind from other languages, reproduce, operate, and maintain with both humans and coding agents.

---

## 2. Prefer simple, explicit systems

Prefer the simplest architecture that satisfies the actual problem.

Do not introduce complexity because it is fashionable. Avoid premature adoption of microservices, distributed systems, message brokers, service meshes, Kubernetes, plugin frameworks, event buses, elaborate dependency-injection frameworks, large frontend frameworks, complex build systems, or unnecessary abstraction layers.

Start simple.

A single executable, a modular monolith, a SQLite database, a few text files, and a clear CLI are often enough.

Complexity must justify itself through a concrete requirement.

---

## 3. Preferred implementation language

When there is no strong project-specific reason to choose another implementation language:

> **Prefer C99 as the default core implementation language.**

C99 is favored because it offers broad portability, small runtime requirements, straightforward embedding, easy FFI, predictable deployment, compatibility with Python, R, Lua, WebAssembly, and other systems, excellent compiler and sanitizer tooling, and long-term stability.

This is a default, not an absolute requirement.

Use another language when the task clearly benefits from it.

Do not choose a language merely because it is newer or fashionable.

---

## 4. Lua as the embedded extension language

If a project needs scripting, embedded customization, plugins, programmable behavior, user-defined transformations, or extension hooks, the default embedded language is:

> **Lua**

Do not embed Python merely because Python bindings may exist.

Python and R should be treated primarily as **external binding targets**.

Where practical, reusable libraries should expose a stable C API, Lua integration where embedded scripting is useful, Python bindings, and R bindings.

---

## 5. Canonical computational interface

For C-centered projects with multiple interfaces, prefer:

```text
C core API
    |
    +-- CLI
    +-- Lua
    +-- Python bindings
    +-- R bindings
    +-- WebAssembly
    +-- browser/server interface
```

The computational core should not depend on the CLI, GUI, Python, R, or browser layer.

Bindings should be thin wrappers around the core where practical.

---

## 6. Modular monolith by default

Prefer:

```text
one repository
one deployable unit
clear internal modules
one main data store
```

unless there is a concrete reason to split processes or services.

This is a default principle, not a rigid architectural rule.

Different tasks may justify different decomposition.

A historical-linguistics tool, for example, may sensibly expose many related operations through one executable.

Do not mechanically apply the slogan “one program does one thing.”

Instead prefer:

> Each module should have one coherent responsibility. Executable granularity should be chosen per task.

---

## 7. Single-executable deployment is a virtue

Where practical, prefer software that can be distributed as:

```text
one executable
+
ordinary configuration/data files
```

This is especially valuable for local tools, research software, browser-based local applications, command-line utilities, and portable desktop-like tools.

Do not force this when it creates disproportionate complexity.

---

## 8. Separate mechanism from policy

Reusable mechanisms should be independent from application policy.

Prefer:

```text
read data
    |
    v
core transformation
    |
    v
render/store/send
```

rather than mixing filesystem access, command-line parsing, domain logic, networking, UI, and database access inside the same functions.

A core operation should ideally be callable from tests, CLI, Lua, Python, R, WebAssembly, fuzzers, and browser/server adapters.

---

## 9. Separate pure logic from side effects

Where practical, separate computation from effects.

Prefer:

```text
input
  |
  v
validation
  |
  v
pure or mostly pure transformation
  |
  v
result
  |
  v
I/O
```

Effects include filesystem access, network calls, database writes, environment access, current time, randomness, process termination, and logging.

Do not contort all code into pure functions, but isolate effects when this improves reasoning and testing.

---

## 10. Make dependencies explicit

Avoid hidden dependency discovery through global mutable state, service locators, implicit environment access, magic singleton objects, or undocumented initialization.

Prefer explicit contexts, arguments, configuration structures, or constructors.

A maintainer should be able to see what a component depends on.

---

## 11. Local reasoning is a major design goal

A well-designed module should be understandable without loading the entire program into one's head.

Prefer narrow interfaces, small modules, explicit data flow, clear ownership, stable contracts, predictable naming, and minimal hidden state.

If understanding one function requires tracing half the repository, the architecture should be reconsidered.

---

## 12. Textual configuration by default

Human-authored configuration should normally be textual.

Default preferences:

```text
TOML      human-authored configuration
JSON      machine-oriented structured interchange
JSONL     streaming / record-oriented structured interchange
YAML      only when an existing ecosystem strongly expects it
```

Do not introduce YAML by default.

TOML is preferred for ordinary human-written configuration because it is readable, structured, and supports comments.

---

## 13. Configuration should permit comments

Human-maintained configuration should normally allow explanatory comments.

This is one reason strict JSON is not preferred as the default human-authored configuration format.

---

## 14. Configuration precedence

Use the following precedence unless the project has a reason to differ:

```text
built-in defaults
    <
configuration file
    <
environment variables
    <
command-line arguments
```

Environment variables are useful especially for deployment, containers, secrets, CI, and process-level overrides.

They should not usually be the primary everyday configuration interface.

---

## 15. Configuration is data, not code

Prefer declarative configuration:

```toml
[output]
format = "json"
compress = true
```

over executable configuration.

Do not use Python, Lua, shell scripts, or another programming language merely as a configuration format.

If programmable behavior is genuinely needed, treat it explicitly as an extension/scripting interface rather than pretending it is ordinary configuration.

When such scripting is required, Lua is the default embedded language.

---

## 16. Unknown configuration keys should warn

Unknown configuration keys should normally produce a warning.

This catches common mistakes such as:

```toml
timeuot = 30
```

without making forward compatibility unnecessarily brittle.

Do not silently ignore unknown configuration fields unless there is a deliberate compatibility reason.

---

## 17. Text means UTF-8

Unless an external format explicitly requires otherwise:

> **All text is UTF-8.**

Generated repository text files should normally use LF line endings.

Input may reasonably tolerate CRLF where appropriate.

Do not rely on locale-dependent internal encodings.

---

## 18. Prefer human-readable and inspectable data

Human-authored or human-maintained data should preferably remain usable with ordinary text tools.

Good formats include TOML, TSV, CSV where appropriate, JSON, JSONL, plain line-oriented text, and documented domain-specific text formats.

Do not distort genuinely hierarchical data merely to make it greppable.

Text-tool friendliness is a virtue, not an absolute requirement.

---

## 19. Prefer TSV for controlled tabular formats

When we control a human-inspectable tabular format, prefer TSV over CSV unless there is a specific interoperability requirement for CSV.

TSV is often especially suitable for linguistic data, research data, textual datasets, and lexical data.

Commas appear frequently in natural-language content; tabs more naturally represent field separation.

---

## 20. Structured state may be binary

Not all data should be textual.

For nontrivial structured mutable state, SQLite is a preferred default.

Use textual formats for configuration, interchange, source data, and inspectable exports.

Use SQLite where appropriate for indexes, mutable structured application state, local databases, caches, search structures, and derived state.

Binary internal representation does not violate the textuality principle if the system remains inspectable and exportable.

---

## 21. State must be inspectable

If canonical or important state is stored in SQLite or another non-text format, provide ways to inspect and export it.

Examples:

```bash
tool inspect
tool dump
tool export --json
tool export --tsv
```

The user should not be trapped inside an opaque internal representation.

---

## 22. User data must be portable

This is a strong rule:

> User data must not be trapped in proprietary or opaque formats without straightforward export.

Prefer documented formats, open standards, textual export, stable schemas, and ordinary files.

A user should be able to recover, inspect, convert, or archive their data independently of a specific UI.

---

## 23. Canonical data must be identified

If multiple representations exist, identify one as authoritative.

Prefer:

```text
lexicon.tsv
    |
    v
generated SQLite index
```

rather than allowing both the TSV and the database to be independently edited.

A fact should ideally have one authoritative representation.

Derived representations should be generated.

---

## 24. Caches must be disposable

A cache may improve speed.

Deleting it must not destroy canonical user data.

A cache should be reconstructible, non-authoritative, and safe to remove.

If deleting a cache causes data loss, it is not really a cache.

---

## 25. Prefer project-local state when state belongs to a project

If state logically belongs to a project, dataset, or repository, project-local storage is preferred.

For example:

```text
project/
    data/
    config.toml
    .tool/
```

A hidden project-local directory may contain caches, indexes, derived SQLite databases, and temporary generated metadata.

User-authored canonical data should not be hidden unnecessarily.

---

## 26. Respect platform conventions for global state

Application-global user state should use standard platform locations.

On Unix-like systems, respect XDG conventions where appropriate.

Do not arbitrarily litter `$HOME`.

State location should be predictable and documentable.

---

## 27. Schemas should be explicit

Where practical, schemas and declarative structures should live as data.

Examples:

```text
schema.json
migrations/*.sql
grammar/*.peg
tables/*.tsv
config-schema.toml
```

Do not hard-code large declarative datasets into imperative source unless there is a reason.

This follows the principle:

> Put knowledge into data so that programs can remain simpler.

---

## 28. Version file formats

Formats we control should generally include an explicit version when compatibility matters.

Example:

```toml
format_version = 1
```

This is cheap insurance.

Do not add versioning to trivial ephemeral files where it provides no value.

---

## 29. Prefer explicit migrations over permanent compatibility complexity

When a persistent format changes, define the migration, make it explicit, preserve backups when appropriate, and migrate deliberately.

Do not keep indefinitely accumulating compatibility branches for every historical format unless compatibility requirements justify it.

---

## 30. Generated data should be generated

Do not manually maintain duplicate representations of the same facts.

If the authoritative source is:

```text
languages.toml
```

and the same information is needed in:

```text
languages.c
languages.py
docs/languages.md
```

prefer generating the derived forms.

Generated files should clearly say that they are generated and identify their source where useful.

---

## 31. Generated artifacts usually should not be committed

If a generated artifact is cheap to regenerate, deterministic, not required for bootstrap, and not required for archival distribution, do not commit it by default.

Commit generated files when doing so materially improves distribution, bootstrapping, portability, archival reproducibility, or downstream use.

---

## 32. Design for meaningful diffs

Human-authored text formats should produce small, useful version-control diffs.

Prefer stable ordering, one logical item per line where practical, no meaningless timestamps, no random ordering, no gratuitous reformatting, and deterministic serialization.

Avoid formats that cause entire files to change because one logical value changed.

---

## 33. CLI is a first-class interface

Where a program has meaningful non-interactive functionality, provide a usable CLI even if the primary interface is graphical or browser-based.

For example:

```text
tool import
tool export
tool inspect
tool convert
tool serve
```

The GUI should not be the only way to invoke important operations when those operations can reasonably be automated.

---

## 34. Subcommands are the default for related operations

For a coherent family of operations, prefer:

```text
tool import
tool export
tool inspect
tool serve
```

over:

```text
tool-import
tool-export
tool-inspect
tool-serve
```

unless separate executables genuinely improve composition or deployment.

Executable granularity is a project-specific design decision.

---

## 35. Support stdin/stdout composition when natural

When an operation naturally behaves like a transformation, support Unix-style composition.

Example:

```bash
cat input.tsv | tool convert | other-tool > result.json
```

Do not force every application into filter semantics.

Composition should be natural, not ceremonial.

---

## 36. CLI output conventions

Follow the traditional distinction:

```text
stdout   requested result
stderr   diagnostics, warnings, progress, errors
status   success/failure
```

Do not mix result data and diagnostics on stdout.

---

## 37. Quiet by default

For command-line tools, follow the Rule of Silence.

Successful operation should usually produce no unnecessary chatter.

Avoid:

```text
Starting...
Reading...
Working...
Success!
Done!
```

unless such feedback is actually useful.

Use `-v` / `--verbose` for additional diagnostics.

Interactive interfaces may provide richer feedback.

---

## 38. Machine-readable CLI output

When command output may reasonably be consumed by scripts, provide explicit structured modes.

Preferred conventions:

```bash
tool inspect file
tool inspect --json file
tool inspect --jsonl file
tool inspect --tsv file
```

Use JSON for one structured result, JSONL for streams/multiple records, and TSV for tabular data.

---

## 39. Human output is not a stable machine interface

Scripts should rely on documented machine-readable output modes.

Human-friendly output may evolve.

This prevents scripts from depending on spacing, punctuation, colors, or prose intended for humans.

---

## 40. Exit codes should stay simple

Prefer:

```text
0       success
nonzero failure
```

Do not invent a large taxonomy of exit codes unless scripts have a concrete need to distinguish failure classes.

---

## 41. `--help` is required for nontrivial CLIs

Every nontrivial command-line tool should have useful:

```bash
tool --help
tool subcommand --help
```

Built-in help is the primary immediate reference.

Man pages may be provided or generated, but they are not mandatory for every project.

---

## 42. Network protocols should be inspectable by default

Preferred defaults:

```text
local composition     files / pipes / stdin / stdout
simple network API    HTTP + JSON
streaming             JSONL or appropriate framing
high-volume binary    binary protocol when justified
```

Do not force textual protocols when interoperability or performance clearly favors binary formats.

---

## 43. HTTP + JSON is the default simple network API

For ordinary APIs:

> Prefer HTTP + JSON.

Use OpenAPI or equivalent schema tooling when it provides real value.

Do not automatically turn every small HTTP server into an enterprise API platform.

---

## 44. Browser-based local applications are encouraged

When an application naturally fits a browser UI, a preferred architecture is:

```text
single executable
    |
    +-- starts local HTTP server
    |
    +-- serves browser UI
    |
    +-- exposes core functionality
```

This is often preferable to introducing a large native GUI framework.

---

## 45. Frontend minimalism

For browser interfaces, prefer HTML, CSS, plain JavaScript, and small focused libraries where useful.

Do not introduce React, Vue, Angular, or similar frameworks merely because a project has a browser interface.

Use them only when their complexity is justified by the application.

---

## 46. Browser UI must not trap important state

Persistent settings changed through a UI should, where practical, map to the same underlying configuration/state model available to non-GUI users.

Avoid important browser-only opaque state when textual or inspectable storage is reasonable.

---

## 47. Reproducible noninteractive operation

For scientific, analytical, or data-processing software especially, important workflows should ideally be reproducible noninteractively.

Prefer that a GUI workflow can ultimately correspond to something like:

```bash
tool run --config analysis.toml
```

This is a major requirement for reproducibility, automation, archival research, batch processing, agents, and CI.

---

## 48. Offline operation is preferred

If a program's essential function does not inherently require the network, it should remain useful offline.

Do not turn local functionality into an unnecessary network dependency.

---

## 49. Dependencies must justify themselves

A dependency should normally satisfy at least one of these:

- it solves a genuinely difficult problem;
- it provides important interoperability;
- it removes substantially more code and risk than it adds;
- it implements something we should not reasonably maintain ourselves.

Avoid dependency sprawl.

Do not reimplement cryptography, TLS, complex file formats, or major standards merely to avoid dependencies.

---

## 50. Prefer few, mature dependencies

Between extreme dependency avoidance and indiscriminate package use, prefer the conservative middle.

Favor dependencies that are mature, stable, well-maintained, small enough to understand where possible, widely used, and technically justified.

---

## 51. Vendor small stable C dependencies when useful

For small, stable C libraries, prefer vendoring source when this materially simplifies builds, portability, single-executable distribution, or reproducibility.

Large system libraries and platform facilities may remain external.

Do not vendor enormous dependency trees casually.

---

## 52. Build system

For C projects, CMake is the default compatibility-oriented build system unless the project has a reason to use something else.

Reasons include broad IDE support, compiler support, Windows support, WebAssembly tooling, packaging ecosystem support, and familiarity to coding agents.

Meson or Make may be preferable for some projects.

The important requirement is a reproducible, understandable build.

---

## 53. One obvious build/test path

A new contributor or coding agent should be able to discover an obvious workflow such as:

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build
```

or an even simpler wrapper:

```bash
make check
```

Avoid undocumented sequences of manual steps.

---

## 54. Reproducible builds

A clean checkout should be enough to reproduce the project given documented dependencies.

Document compiler requirements, runtime requirements, external libraries, build commands, environment variables, generated sources, and optional features.

---

## 55. Formatting must be mechanical

Formatting is not a code-review topic.

For C, provide a repository-owned `.clang-format` or equivalent.

Agents and developers must not manually restyle unrelated code while making functional changes.

---

## 56. Warnings are part of correctness

For C99, aim toward a strict warning baseline such as:

```bash
-std=c99
-Wall
-Wextra
-Wpedantic
-Wshadow
-Wconversion
-Wstrict-prototypes
-Wmissing-prototypes
```

Adapt the exact set to the project.

Once first-party code is clean:

> Treat warnings as errors in CI.

Vendor/third-party code may be exempt.

---

## 57. Test with GCC and Clang

Where feasible, build and test C projects with both GCC and Clang.

This catches portability assumptions and warning differences.

---

## 58. Sanitizers are normal development tools

Where supported, use AddressSanitizer and UndefinedBehaviorSanitizer.

Consider other sanitizers when relevant.

Sanitizer-clean test execution should be treated as part of normal quality assurance.

---

## 59. Static analysis is expected

Use static analysis where appropriate.

Examples include compiler analyzers, Clang Static Analyzer, and clang-tidy checks relevant to C.

Establish a baseline and fix high-confidence issues.

Do not blindly chase false positives.

---

## 60. Fuzz parsers and decoders

Parsers, decoders, serializers, Unicode handlers, and untrusted-input boundaries should normally gain fuzz targets once sufficiently mature.

Fuzz harnesses should exercise the real production logic.

Crashes discovered by fuzzing should become regression tests.

---

## 61. Prefer simple C test infrastructure

For C, default to ordinary test executables, `assert` where appropriate, tiny in-project test helpers, and simple fixtures.

Do not introduce a test framework merely because one exists.

Add a framework only when it clearly improves the project.

---

## 62. Use golden files freely

Plain-text golden tests are strongly encouraged for parsers, converters, linguistic tools, renderers, serializers, and data transformations.

Example:

```text
tests/
    input/
        example.tsv
    expected/
        example.json
```

Golden tests are inspectable, versionable, reviewable, and easy for agents to update carefully.

---

## 63. Test behavior, not implementation

Prefer tests that verify meaningful behavior.

Avoid excessive coupling to private helper functions, call counts, internal object layout, or implementation order.

Mocks should be used mainly at genuine external boundaries.

---

## 64. Every significant bug should gain a regression test

When practical:

> A fixed bug should leave behind a test that would have caught it.

This prevents recurring defects and documents edge cases.

---

## 65. Performance requires measurement

Do not optimize from intuition.

Before performance-oriented work:

1. establish representative benchmarks;
2. profile;
3. identify hot paths;
4. optimize measured bottlenecks;
5. compare before and after;
6. preserve correctness.

Prefer algorithmic improvements before micro-optimization.

---

## 66. Undefined behavior is a bug

Do not intentionally depend on signed overflow, invalid pointer arithmetic, strict-aliasing violations, out-of-bounds access, uninitialized data, use-after-free, invalid shifts, or misalignment.

Well-defined C comes before optimization.

---

## 67. Error handling must be explicit

Errors should carry enough context to explain what failed, where, why, what resource/input was involved, and whether retry is meaningful.

Do not return vague failure with no usable information.

Do not log the same error redundantly at many layers.

---

## 68. Validate at boundaries

Validate external data near the boundary.

Examples include config files, CLI input, HTTP requests, files, database rows, and foreign API responses.

Convert external data into trusted internal representations early.

---

## 69. Be strict about ambiguity

Be tolerant of harmless surface variation where useful.

Examples that may be accepted include CRLF, trailing whitespace, and harmless formatting differences.

Be strict about invalid structure, ambiguous semantics, out-of-range values, security-sensitive input, and unknown behavior.

Do not silently guess.

---

## 70. Idempotence is valuable

Where practical, make operations safe to repeat.

This improves retries, automation, crash recovery, batch processing, scheduled execution, and distributed operations.

It is especially important for operations with external side effects.

---

## 71. Database migrations belong in version control

Schema changes should be explicit artifacts.

Example:

```text
migrations/
    001_initial.sql
    002_add_index.sql
    003_add_metadata.sql
```

Do not rely on undocumented manual database changes.

---

## 72. External systems are unreliable

When using networks or external services, design for timeouts, temporary failures, retries, backoff, stale data, duplicate requests, and partial failure.

Retry only operations that are safe to retry.

---

## 73. Security should be boring and explicit

Default practices include:

- no secrets in repositories;
- least privilege;
- parameterized SQL;
- safe temporary-file handling;
- careful file permissions;
- input validation;
- secure defaults;
- dependency updates;
- no homemade cryptography;
- no arbitrary shell execution from untrusted input.

Security should be part of ordinary design, not an afterthought.

---

## 74. No telemetry by default

The default is:

> **No telemetry.**

If telemetry is genuinely useful, it must be explicitly justified, documented, and opt-in.

Do not silently collect usage data.

---

## 75. Logging depends on program type

For ordinary CLI tools:

- concise human-readable diagnostics on stderr;
- quiet operation by default.

For long-running services:

- structured logs are encouraged;
- include contextual fields;
- make logs searchable;
- avoid prose-only debugging output when structured fields are useful.

Do not force JSON logging onto every small utility.

---

## 76. Observability should match the system

For deployed services, consider logs, metrics, and traces.

Use only what the system needs.

Do not add a full observability stack to trivial software.

---

## 77. Concurrency must be justified

Default to single-threaded, synchronous, simple execution unless concurrency solves an observed problem.

Introduce worker threads, processes, async I/O, or queues when a concrete need exists.

Concurrency is not inherently modernity.

---

## 78. Avoid permanent daemons unless needed

Prefer on-demand execution, cron, systemd timers, scheduled jobs, or one ordinary server process over unnecessary always-running background daemons.

---

## 79. Plugin systems are not a default

Do not invent a plugin architecture until there are concrete extension needs.

A useful threshold is:

> At least two real extension use cases should exist before designing a generic plugin system.

Lua scripting may solve many extension needs more simply.

---

## 80. APIs should expose contracts clearly

Important interfaces should make clear inputs, outputs, mutability, ownership, lifetime, errors, units, nullability, and side effects.

In C, compensate for the type system's limitations with explicit naming and concise comments.

---

## 81. C ownership must be explicit

Naming should make ownership understandable.

Examples:

```text
_create / _destroy
_init / _deinit
_copy
_clone
_take
_borrow
_release
```

Do not use ambiguous pointer-returning APIs where the caller cannot tell whether the result is owned.

---

## 82. Pointer + length is a conceptual unit

For buffers and arbitrary text/data, prefer:

```c
const char *data;
size_t length;
```

over assuming NUL termination.

Introduce small view types when repeated use justifies them.

---

## 83. Prefer opaque stateful types

Stateful C objects should usually hide implementation details.

Value-like structures may remain public.

Do not hide every struct mechanically.

---

## 84. Use `const` aggressively

Use `const` wherever mutation is not intended.

This improves contracts, readability, compiler checking, and API understanding.

---

## 85. Avoid pointer typedefs

Prefer:

```c
typedef struct foo foo;
foo *x;
```

over:

```c
typedef struct foo *Foo;
```

Pointer typedefs obscure ownership and nullability.

---

## 86. Prefer explicit contexts over mutable globals

Move mutable process state into explicit context objects where practical.

This improves testing, reentrancy, bindings, concurrency, and multiple instances.

Immutable constants are fine.

---

## 87. Prefer configuration structures

For constructors or operations with many options, prefer a config struct with C99 designated initializers.

This keeps APIs readable and evolvable.

---

## 88. Use coherent error models

Do not randomly mix `NULL`, `-1`, `false`, `errno`, global errors, and magic values.

Use the simplest coherent model appropriate for the project.

---

## 89. `goto cleanup` is good C

For functions acquiring multiple resources, structured cleanup using:

```c
goto cleanup;
```

is encouraged where it avoids duplication or leaks.

Do not ban `goto` ideologically.

---

## 90. Minimize preprocessor metaprogramming

Use the C preprocessor mainly for include guards, feature detection, portability, conditional compilation, and genuinely useful constants/macros.

Prefer functions or `static inline` functions when possible.

Avoid building object systems, templates, or DSLs through macros unless strongly justified.

---

## 91. Comments should preserve non-obvious knowledge

Comments should explain what the code cannot clearly express.

Prioritize comments about intent, invariants, ownership, lifetime, units, safety assumptions, tricky pointer arithmetic, compatibility workarounds, binary layouts, non-obvious algorithmic choices, and reasons why simpler-looking code is incorrect.

Do not narrate obvious code.

---

## 92. Comment why, not what

Bad:

```c
/* Increment i. */
i++;
```

Good:

```c
/*
 * Skip entry zero: it represents the synthetic root and must
 * never be emitted.
 */
i++;
```

---

## 93. Comment suspicious-looking code

If future maintainers are likely to “simplify” something incorrectly, explain why the code is unusual.

Example:

```c
/*
 * Use memmove rather than memcpy because these ranges may overlap.
 */
```

---

## 94. Put API contracts in headers

Public header comments should explain ownership, lifetime, nullability, units, input expectations, and error behavior.

Implementation comments belong in `.c` files.

Avoid verbose generated-documentation boilerplate unless a project explicitly needs it.

---

## 95. Documentation should be layered

Prefer lightweight documentation:

```text
README.md
DEVELOPMENT.md or CONTRIBUTING.md
ARCHITECTURE.md
AGENTS.md
docs/development/adr/
```

Use only the files the project needs.

---

## 96. Architecture Decision Records are encouraged

For important decisions, use lightweight ADRs:

```text
docs/development/adr/
    0001-use-sqlite.md
    0002-use-lua-for-extensions.md
    0003-no-react.md
```

Each can be simple:

```text
Context
Decision
Consequences
```

This is particularly valuable for coding agents.

---

## 97. Repository guidance for coding agents

Repositories should make important rules easy for agents to discover.

An `AGENTS.md` should ideally state build commands, test commands, architecture boundaries, generated files, public API locations, style rules, forbidden shortcuts, ADR location, dependency policy, and required checks.

Agents should not have to infer repository policy from incidental code.

---

## 98. Agents must inspect before refactoring

A coding agent should not immediately “modernize” a repository.

Before major changes it should inspect the build system, architecture, module graph, tests, public API, data formats, ownership, configuration, dependencies, compatibility requirements, and existing conventions.

Then it should propose incremental changes.

---

## 99. Prefer incremental refactoring over rewrites

Do not recommend a rewrite merely because the existing structure is poor.

Preferred sequence:

```text
observe
→ characterize
→ test
→ simplify boundaries
→ clarify contracts
→ harden behavior
→ improve tooling
→ optimize
```

Each milestone should leave the repository working.

---

## 100. Small, coherent commits

Commits should represent one conceptual change where practical.

Prefer:

```text
parser: separate file I/O from tokenization
```

over:

```text
various improvements
```

Do not mix unrelated formatting, dependency upgrades, renames, architecture changes, features, and bug fixes in one commit.

---

## 101. Code review should focus on risk and design

Formatting and trivial style should be automated.

Review effort should focus on behavior, architecture, edge cases, ownership, compatibility, security, performance, and maintainability.

---

## 102. Delete code

Removing unnecessary code is a first-class engineering activity.

Delete unused features, dead compatibility layers, obsolete flags, duplicated implementations, unused dependencies, and abandoned abstractions.

Less code is easier to understand and maintain.

---

## 103. Track technical debt concretely

Avoid vague labels such as:

```text
the parser is messy
```

Prefer actionable descriptions:

```text
The parser mixes filesystem I/O, tokenization, and AST construction,
which prevents fuzz testing and reuse with memory buffers.
```

Technical debt should describe a real constraint or cost.

---

## 104. Backward compatibility must be intentional

Before changing an API or format, determine who consumes it, whether it is public, whether ABI matters, whether source compatibility matters, and whether migration is practical.

Do not maintain compatibility forever by accident.

Do not break users by accident.

---

## 105. Pre-1.0 evolution can be faster

Before a public interface is declared stable, projects may evolve aggressively when useful.

Once stable, changes should become more conservative.

---

## 106. Semantic Versioning

For public libraries and tools, use Semantic Versioning once the interface is considered stable.

Typical interpretation:

```text
MAJOR   incompatible public changes
MINOR   backward-compatible functionality
PATCH   backward-compatible fixes
```

Pre-1.0 projects may change more freely.

---

## 107. Default license

Unless a project explicitly states otherwise:

> **Use GNU General Public License version 3 (GPL-3.0).**

Do not silently substitute another license.

Licensing exceptions should be explicit project decisions.

---

## 108. Final default stack

When no stronger project-specific requirement exists, the preferred baseline is roughly:

```text
Implementation       C99
Embedded scripting   Lua
Python integration   bindings
R integration        bindings
Human config         TOML
Machine interchange  JSON
Streaming records    JSONL
Tabular text         TSV
Persistent local DB  SQLite
Network API          HTTP + JSON
Browser UI           HTML/CSS/plain JS
Build system         CMake
Formatting           clang-format
Warnings             strict GCC/Clang warnings
Testing              simple executables + local helpers
Dynamic analysis     ASan + UBSan
Fuzzing              parsers / untrusted inputs
License              GPL-3.0
Versioning           SemVer once stable
Telemetry            none by default
Deployment           single executable where practical
Architecture         modular monolith by default
```

This table is a default, not a prohibition against alternatives.

---

## 109. Final decision heuristics

When uncertain, prefer:

```text
simple                  over elaborate
explicit                over implicit
inspectable             over opaque
textual                 over proprietary
portable                over trapped
local                   over network-dependent
deterministic           over hidden state
one canonical source    over duplicated truth
generated derivative    over hand-maintained duplication
stable data format      over UI-specific state
small dependency set    over dependency sprawl
single executable       over deployment complexity
modular monolith        over premature distribution
CLI automation          over GUI-only workflows
Lua extension           over embedded Python
C API                   over language-specific core logic
SQLite                  over homemade persistent stores
TOML                    over YAML for human configuration
JSON/JSONL              over custom interchange formats
TSV                     over CSV when we control tabular text
measurement             over performance intuition
tests                    over confidence
sanitizers               over assumptions
incremental refactoring  over rewrite
documented decisions     over rediscovering rationale
```

---

## 110. Final standard

The software should make it easy to answer:

- What is the canonical source of this data?
- Where is configuration stored?
- Can I inspect it with ordinary tools?
- Can I automate this operation without the GUI?
- Can I export my data?
- What does this module depend on?
- Which state is authoritative?
- Which state is only cached?
- What happens if this operation fails?
- Can this be reproduced?
- Can this be tested independently?
- Can another language call the core logic?
- Why does this unusual code exist?
- Can this system be deployed simply?
- Can a coding agent safely understand and modify it?

A good implementation should minimize the amount of hidden knowledge required to answer those questions.

The house philosophy is therefore:

> **Keep mechanisms simple, data explicit, interfaces composable, state inspectable, and complexity justified.**

And, in the spirit of Unix:

> **Write software that cooperates well with other software, remains useful outside its original interface, and keeps the user's data under the user's control.**

# LANGUAGES

Per-ecosystem lookup for MAP and FIX. The graph format, the phases and the script are language-neutral — only these four things change per stack: **what to read**, **what to skip**, **what to grep**, **how to verify**.

Read this when mapping or fixing a repo whose stack you don't already know cold. Skip it for a pure JS/TS repo — `map.md` alone covers that.

## 0. Detect the stack first

Marker files in the repo root (and in each workspace/package dir — see **Polyglot repos**):

| Marker                                                        | Ecosystem                         |
| ------------------------------------------------------------- | --------------------------------- |
| `package.json` · `deno.json` · `bun.lockb`                    | JS/TS                             |
| `pyproject.toml` · `setup.py` · `requirements.txt`            | Python                            |
| `go.mod`                                                      | Go                                |
| `Cargo.toml`                                                  | Rust                              |
| `pom.xml` · `build.gradle{,.kts}`                             | JVM (Java, Kotlin, Scala, Groovy) |
| `*.csproj` · `*.sln` · `*.fsproj`                             | .NET (C#, F#)                     |
| `Gemfile`                                                     | Ruby                              |
| `composer.json`                                               | PHP                               |
| `Package.swift` · `*.xcodeproj` · `Podfile`                   | Swift/ObjC                        |
| `pubspec.yaml`                                                | Dart/Flutter                      |
| `CMakeLists.txt` · `Makefile` · `meson.build` · `conanfile.*` | C/C++                             |
| `mix.exs`                                                     | Elixir                            |
| `*.cabal` · `stack.yaml`                                      | Haskell                           |
| `Dockerfile` · `docker-compose.yml` · `*.tf` · `*.k8s.yaml`   | infra — nodes, not a language     |

Write what you found into `graph.json`'s `stack` line. It is the one place a reader learns the repo is Go + React, not Node.

## 1. Read for context

`map.md` §1 gives the order. This is what fills the **manifests** and **structure config** slots. Deps and scripts sections only — never the whole file.

| Ecosystem | Manifest (deps + scripts)                  | Structure config worth reading                                                     |
| --------- | ------------------------------------------ | ---------------------------------------------------------------------------------- |
| JS/TS     | `package.json`, workspace globs            | router config, `next.config`/`nuxt.config`/`vite.config`, `tsconfig` `paths` block |
| Python    | `pyproject.toml`, `requirements*.txt`      | `settings.py` INSTALLED_APPS, `urls.py`, FastAPI/Flask app factory, `alembic.ini`  |
| Go        | `go.mod`                                   | `main.go` route registration, `wire.go`/DI setup, `//go:generate` lines            |
| Rust      | `Cargo.toml` (incl. `[workspace] members`) | `main.rs`/`lib.rs` `mod` tree — it _is_ the module map                             |
| JVM       | `pom.xml` / `build.gradle`                 | `application.{yml,properties}`, component-scan base packages, `module-info.java`   |
| .NET      | `*.csproj`, `Directory.Packages.props`     | `Program.cs` / `Startup.cs` DI + endpoint registration, `appsettings.json` keys    |
| Ruby      | `Gemfile`                                  | `config/routes.rb`, `config/application.rb`, `db/schema.rb` (table names only)     |
| PHP       | `composer.json` (incl. `autoload.psr-4`)   | `routes/*.php`, `config/app.php` providers, `services.yaml`                        |
| Swift     | `Package.swift`, `Podfile`                 | `*App.swift` / `AppDelegate`, `Info.plist` capability keys                         |
| Dart      | `pubspec.yaml`                             | `main.dart`, router config (`go_router` tables), `build.yaml`                      |
| C/C++     | `CMakeLists.txt` targets                   | target → source-list mapping _is_ the structure                                    |
| Elixir    | `mix.exs`                                  | `router.ex`, `application.ex` supervision tree, `endpoint.ex`                      |

**Supervision trees, DI registrations and route tables are worth more than any source file.** They name the real entry points and the real edges.

## 2. Skip

Add these to `map.md`'s never-read table for the ecosystem in play.

| Ecosystem | Generated / vendored                                                                                                 | Lockfile                                                        | Tests                                                    |
| --------- | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------- |
| JS/TS     | `node_modules`, `dist`, `build`, `.next`, `.nuxt`, `.svelte-kit`, `.turbo`, `*.d.ts`, prisma/openapi/graphql clients | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb` | `*.test.*`, `*.spec.*`, `__tests__/`, `e2e/`, `cypress/` |
| Python    | `__pycache__`, `.venv`, `*.egg-info`, `build/`, `migrations/*.py` (roll up), `*_pb2.py`                              | `poetry.lock`, `uv.lock`, `Pipfile.lock`                        | `test_*.py`, `*_test.py`, `tests/`, `conftest.py`        |
| Go        | `vendor/`, `*.pb.go`, `*_gen.go`, `mocks/`, `bin/`                                                                   | `go.sum`                                                        | `*_test.go`, `testdata/`                                 |
| Rust      | `target/`, `*.rs` under `OUT_DIR`, generated bindings                                                                | `Cargo.lock`                                                    | `tests/`, `benches/`, `#[cfg(test)]` blocks              |
| JVM       | `build/`, `target/`, `out/`, `.gradle/`, generated sources, `*Dto` mapstruct impls (`*Impl.java`)                    | `gradle.lockfile`                                               | `src/test/**`                                            |
| .NET      | `bin/`, `obj/`, `*.Designer.cs`, `*.g.cs`, `Migrations/` (roll up)                                                   | `packages.lock.json`                                            | `*.Tests/`, `*Tests.cs`                                  |
| Ruby      | `vendor/bundle`, `tmp/`, `public/assets`, `db/migrate/*` (roll up)                                                   | `Gemfile.lock`                                                  | `spec/`, `test/`                                         |
| PHP       | `vendor/`, `var/cache`, `public/build`                                                                               | `composer.lock`                                                 | `tests/`, `*Test.php`                                    |
| Swift     | `.build/`, `Pods/`, `DerivedData/`, `*.generated.swift`                                                              | `Package.resolved`, `Podfile.lock`                              | `*Tests/`, `*Tests.swift`                                |
| Dart      | `.dart_tool/`, `build/`, `*.g.dart`, `*.freezed.dart`, `*.gr.dart`                                                   | `pubspec.lock`                                                  | `test/`, `integration_test/`                             |
| C/C++     | `build/`, `cmake-build-*/`, `third_party/`, `*.o`, `*.so`, moc/ui generated                                          | `conan.lock`                                                    | `test/`, `*_test.cc`, `*_unittest.cc`                    |
| Elixir    | `_build/`, `deps/`, `priv/static`                                                                                    | `mix.lock`                                                      | `test/`                                                  |

Universal skips (any stack): `.env*`, `*.properties` except `.env.example`, formatter/lint config (`.prettierrc*`, `.editorconfig`, `eslint.config.*`, `ruff.toml`, `.rubocop.yml`, `.golangci.yml`, `rustfmt.toml`, `.clang-format`, `checkstyle.xml`, `.php-cs-fixer.php`, `analysis_options.yaml`, `.swiftformat`, and any other stack's equivalent), assets, i18n bundles, fixtures, CI workflows.

## 3. Grep — symbols and edges

One repo-wide pass each. `map.md` §4 wants **exported/public** symbols; §5 wants **imports**.

| Ecosystem | Public symbols                                                                      | Imports                                                                                      |
| --------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| JS/TS     | `^export (async )?(function\|const\|class)`, `^export default`, `export {`          | `^import .* from`, `require(`, `import(`                                                     |
| Python    | `^def `, `^class ` at col 0 (leading `_` = private), `__all__`                      | `^\s*(from .* )?import `                                                                     |
| Go        | `^func [A-Z]`, `^func \(.*\) [A-Z]`, `^type [A-Z]` (capital = exported)             | `import (` blocks, single `import "`                                                         |
| Rust      | `^pub (fn\|struct\|enum\|trait\|const\|type)`                                       | `^use `, `^\s*mod ` (declares a child file)                                                  |
| JVM       | `public (class\|interface\|record\|enum)`, `public .* \w+\(`                        | `^import `                                                                                   |
| .NET      | `public (class\|record\|interface\|static)`, `public .* \w+\(`                      | `^using `, `global using`                                                                    |
| Ruby      | `^\s*def [^s]`, `^\s*class `, `^\s*module `                                         | `require`, `require_relative`, or **none** — Rails autoloads by constant, so resolve by name |
| PHP       | `public function`, `^(final \|abstract )?class`, `^interface`                       | `^use ` (PSR-4 FQCN)                                                                         |
| Swift     | `public \|open func\|struct\|class\|enum`, plus internal ones in single-module apps | `^import ` (module-level, not file-level)                                                    |
| Dart      | top-level `\w+ \w+\(`, `^class `, `^mixin ` (leading `_` = private)                 | `^import '`, `^part '`                                                                       |
| C/C++     | declarations in `.h`/`.hpp` — the header _is_ the export list                       | `^#include "` (quotes = internal, `<>` = external)                                           |
| Elixir    | `^\s*def `, `^\s*defmodule ` (`defp` = private)                                     | `alias`, `import`, `use`                                                                     |

**Only export-shaped symbols go in `symbols[]`.** Where a language has no visibility marker (Ruby, Dart, single-module Swift), take what a sibling file could plausibly call and skip obvious internals.

## 4. Resolve — import string → node id

An edge only counts once both endpoints are node ids (repo-relative paths).

| Ecosystem        | Rule                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| JS/TS            | Relative paths + `tsconfig`/`jsconfig` `paths` aliases (`@/lib/auth` → `lib/auth.ts`). Bare specifier = external node.                                       |
| Python           | Dotted module → path (`app.services.billing` → `app/services/billing.py`); `__init__.py` re-exports mean the real owner may be a sibling.                    |
| Go               | Module path prefix from `go.mod` strips to a directory; **the package dir is the node**, not the file — one node per package is usually right.               |
| Rust             | `crate::a::b` → `src/a/b.rs` or `src/a/b/mod.rs`; `super::` is relative; other workspace crates are their own subtree.                                       |
| JVM / .NET / PHP | FQCN mirrors the directory (`com.acme.billing.Invoice` → `.../billing/Invoice.java`; PSR-4 root from `composer.json`).                                       |
| Ruby             | Rails: constant name ↔ path by convention (`BillingService` → `app/services/billing_service.rb`). Imports are often absent — resolve by constant reference. |
| Swift            | Imports are module-level, so intra-module edges are invisible to grep — use **type references** instead.                                                     |
| Dart             | `package:app/x/y.dart` → `lib/x/y.dart`; relative imports as-is.                                                                                             |
| C/C++            | `#include "a/b.h"` → the header, then pair `b.h` with `b.cc` as one node unless they diverge.                                                                |
| Elixir           | `alias App.Billing.Invoice` → `lib/app/billing/invoice.ex`.                                                                                                  |

**Fallbacks when imports don't tell the story** — these are the _most_ valuable edges, and no grep pass finds them:

| Pattern                                      | How to catch it                                                                                 |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Rails/Spring/Laravel autoload, DI containers | Read the container/route config once; every registration is an edge.                            |
| Swift/single-module, C# partial classes      | Grep for the type name instead of an import.                                                    |
| HTTP calls between services                  | Grep the client for the URL path, match it to the route node in the server. `label: "POST /x"`. |
| Queues, cron, pub/sub                        | Producer → queue node → consumer. Give the queue its own `kind: "external"` node.               |
| SQL / ORM                                    | Table name grep → `kind: "db"` node. Don't map every column.                                    |
| Generated clients (gRPC, GraphQL, OpenAPI)   | Skip the generated file; edge from caller straight to the service node.                         |

## 5. Verify — the FIX gate

`fix.md` step 2 runs the repo's **own** checks. Prefer a script declared in the manifest; fall back to the ecosystem default.

| Ecosystem | Default gate                                                        |
| --------- | ------------------------------------------------------------------- |
| JS/TS     | `tsc --noEmit`, then the manifest's `lint` / `test` scripts         |
| Python    | `mypy .` or `pyright`, `ruff check`, `pytest -q`                    |
| Go        | `go build ./...`, `go vet ./...`, `go test ./...`                   |
| Rust      | `cargo check`, `cargo clippy -- -D warnings`, `cargo test`          |
| JVM       | `./gradlew build -x test` then `test`, or `mvn -q verify`           |
| .NET      | `dotnet build`, `dotnet test`                                       |
| Ruby      | `bundle exec rubocop`, `bundle exec rspec`                          |
| PHP       | `composer exec phpstan`, `composer exec phpunit`                    |
| Swift     | `swift build`, `swift test`, or `xcodebuild -scheme <s> build test` |
| Dart      | `dart analyze`, `flutter test`                                      |
| C/C++     | configured build (`cmake --build build`), then `ctest`              |
| Elixir    | `mix compile --warnings-as-errors`, `mix test`                      |

Rules that don't change: **baseline red → stop**, green → red → revert the touched paths. Never install a toolchain to create a gate that the repo doesn't already have — if there's no check available, say so and let the user decide before editing.

## Polyglot repos

A fullstack repo is normal, not a special case. One graph covers it all.

- Detect **per directory**, not per repo — `web/package.json` + `api/go.mod` is two ecosystems, one graph.
- **Features stay language-neutral.** `billing` owns the React page, the Go handler and the migration. Never split a feature by language; that recreates the folder-shaped features `map.md` forbids.
- Cross-language edges are the whole point of mapping a fullstack repo — spend the tokens on §4's fallback table before you spend them on any source file.
- `shared` may hold modules from several languages. That's fine.
- FIX gates are per-language: run only the checks for the ecosystem you touched.

## Stack not listed?

Derive the same five answers and carry on — the format doesn't care:

1. Which file declares dependencies? → read its deps section.
2. Which directory is build output? → skip it.
3. What marks a symbol public? → grep that.
4. How does one file name another? → that's the edge, resolve it to a path.
5. What command tells you the repo still compiles? → that's the FIX gate.

If a language has no visibility marker or no import syntax, fall back to §4's reference-grep and config-reading tactics.

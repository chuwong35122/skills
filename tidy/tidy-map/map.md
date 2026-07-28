# MAP

Build or patch `.tidy/graph.json`, then run the script. Read this file only when you're actually mapping.

## 0. Detect the stack

Every stack is in scope — any language, any framework, fullstack and polyglot repos included. Only four things vary: what to read, what to skip, what to grep, how to verify.

Glob the root (and each workspace dir) for manifest markers: `package.json` · `pyproject.toml` · `go.mod` · `Cargo.toml` · `pom.xml` · `build.gradle*` · `*.csproj` · `Gemfile` · `composer.json` · `Package.swift` · `pubspec.yaml` · `CMakeLists.txt` · `mix.exs`.

**Read `../tidy/languages.md` unless the repo is pure JS/TS** — it carries the per-ecosystem read/skip/grep/resolve/verify tables the rest of this file assumes. A repo with two manifests in two directories is one graph with two ecosystems, not two graphs.

## 1. Read project context — and only this

Do not open source at random. In order: **agent instructions** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.github/copilot-instructions.md`) → **root `README.md`** → **manifests** (deps and scripts sections only — the dep list is your library vocabulary) → **structure config only** (route tables, DI/container registration, supervision trees, module/alias resolution config, `docker-compose.yml`, migrations directory *listing*) → **the filetree**, honoring `.gitignore` and `.tidyignore`.

Per-ecosystem manifest and structure-config names: `../tidy/languages.md` §1. **Route tables, DI registrations and supervision trees outrank any source file** — they name the real entry points and the cross-boundary edges.

**Markdown rule:** only `README.md` and the agent instruction files. Every other `.md` — CHANGELOG, CONTRIBUTING, `docs/**`, ADRs — is skipped unless the user names it.

**Never read:**

| Category | Examples |
| --- | --- |
| Secrets | `.env*` — **the one exception is `.env.local`**, and from it take only *key names*, never values |
| Format/lint config | any — `.prettierrc*`, `.editorconfig`, `eslint.config.*`, `biome.json`, `ruff.toml`, `.flake8`, `.rubocop.yml`, `.golangci.yml`, `gofmt`/`rustfmt.toml`, `.clang-format`, `checkstyle.xml`, `.php-cs-fixer.php`, `analysis_options.yaml`, `.swiftformat`, `.editorconfig` |
| Lockfiles | any — `package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`, `pubspec.lock`, `mix.lock` |
| Dependency trees | `node_modules`, `vendor`, `.venv`, `Pods`, `deps`, `third_party` |
| Build output | `dist`, `build`, `out`, `bin`, `obj`, `target`, `.next`, `.turbo`, `.gradle`, `_build`, `.dart_tool`, `DerivedData`, `__pycache__` |
| Generated code | `*.gen.*`, `*.d.ts`, `*.g.dart`, `*.freezed.dart`, `*_pb2.py`, `*.pb.go`, `*.g.cs`, protobuf/prisma/openapi/graphql clients, `__snapshots__` |
| Assets & data | images, fonts, video, PDFs, `*.min.*`, i18n bundles, fixtures, seed data, CSV |
| Tests & stories | `*.test.*`, `*.spec.*`, `*.stories.*`, `__tests__/`, `test_*.py`, `*_test.go`, `src/test/**`, `spec/`, `e2e/` |
| CI/meta | `.github/workflows`, `LICENSE`, `.gitattributes` |

Per-ecosystem specifics: `../tidy/languages.md` §2.

## 2. Cut the tree into features

A **feature** is a user-visible capability or bounded domain — not a folder, and **not a language**. Derive from, in preference order: routes/pages/screens → domain modules the project already names → API surface groupings → clusters of files that only import each other.

In a fullstack repo one feature spans the whole slice: `billing` owns the web page, the API handler, the service and the migration. Splitting `frontend` from `backend` recreates the folder-shaped features this rule exists to prevent.

Add a feature named **`shared`** for anything used by 3+ features (utils, ui primitives, db client, logger, auth middleware) — it may hold modules from more than one language. Highest-value nodes in the graph. Name features kebab-case, from domain language, not folder names.

## 3. Describe every file in caveman

One line per node. **Keywords, not sentences.** 4–10 comma-separated tokens answering *what would I need to know to decide whether to open this?*

```
lib/auth.ts                  → "better-auth config, session cookie, jwt, google provider"
intake-form.tsx              → "intake property, multi-step, rhf+zod, pdf upload"
internal/billing/invoice.go  → "build invoice, prorate, pdf render, writes db"
app/services/payout.rb       → "payout agent commission, stripe transfer, idempotent"
lib/app/auth/guard.ex        → "plug, verify session, halt 401, assigns current_user"
```

Earns a token: route/entry it serves · library it configures · domain nouns it owns · access control (`rbac: admin`) · side effects (`writes db`, `sends email`) · reusable shape (`multi-step`, `paginated`, `debounced`).

Does not: framework boilerplate ("React component", "Spring service", "Django view"), the language ("Go file" — `stack` already says so), restating the filename, line counts, quality opinions.

Never invent — mark inferred lines with a trailing `?`. The script rejects lines over 10 tokens; if a file needs more, that's a finding about the file.

## 4. Record symbols

Each internal file node gets a `symbols` list: **publicly visible** functions/classes only, each with a 3–8 token caveman line. Names come free from the same grep pass as edges — the per-language pattern is in `../tidy/languages.md` §3 (`export function` · `^def ` at col 0 · `^func [A-Z]` · `^pub fn` · `public class` · declarations in a `.h`). Derive the caveman line from the signature and only read the head when it's opaque.

Where a language has no visibility marker (Ruby, Dart, single-module Swift), take what a sibling file could plausibly call and skip obvious internals.

Symbols are what make duplicate detection possible — **no symbols, no `DUP`/`REUSE` findings.** They're optional in the schema, so old graphs stay valid and a scoped `/tidy` can backfill them feature by feature. When a full scan would be too expensive, record symbols for `shared` and high-degree nodes first.

## 5. Record edges — forward only

From a **single repo-wide search** of import/require/use/include statements, not file by file. `{from, to}` where `from` depends on `to`. Resolve each import string to a node id — alias config, module-path-to-directory, FQCN-mirrors-directory, header-pairs-with-source; the per-language rule is in `../tidy/languages.md` §4. Give external services and datastores their own nodes (`kind: "external"` / `"db"`).

**Cross-boundary edges matter most and no import grep finds them**: frontend → HTTP route → service → table, producer → queue → consumer, DI/autoload registration, constant references in a language without file-level imports. `../tidy/languages.md` §4 lists how to catch each. In a fullstack repo, spend tokens there before opening any source file.

For a compiled language, prefer the granularity the language uses: Go's node is usually the **package directory**, C++'s is the header+source pair.

**Never record reverse edges.** The script computes `used by`, shared detection, entry points, orphans, degrees and feature edges. Edges stay file-level — symbols don't get their own edges.

## 6. Build and report

```bash
python3 ../tidy/scripts/tidy_graph.py build --root <repo root>   # write html + markdown
python3 ../tidy/scripts/tidy_graph.py check --root <repo root>   # validate, write nothing
```

Standard library only. **Fix everything it reports** and re-run until clean. Then summarize: features, files, shared modules, orphans, anything suspicious. Point the user at `.tidy/index.html`.

---

## Schema

The validator enforces the rules, so this is the working subset — the full key tables are in `../tidy/graph-format.md` if a validator message isn't enough.

```json
{
  "repo": "chuwii-real-estate",
  "updated": "2026-07-27",
  "stack": "next 15, typescript, postgres/prisma, better-auth",

  "features": [
    { "name": "auth", "route": "/login, /signup", "rbac": "public", "libs": ["better-auth"] },
    { "name": "shared", "libs": ["date-fns", "zod"] }
  ],

  "nodes": [
    { "id": "app/login/page.tsx", "feature": "auth", "kind": "route",
      "caveman": "/login, dialog, email+password, google btn, redirect /dash" },
    { "id": "utils/format.ts", "feature": "shared", "kind": "file",
      "caveman": "format number, format date, currency THB, phone mask",
      "symbols": [
        { "name": "formatTHB",  "caveman": "format number, currency THB, 2dp" },
        { "name": "formatDate", "caveman": "format date, dd/mm/yyyy, th locale" }
      ] },
    { "id": "better-auth", "kind": "external",
      "caveman": "auth provider, oauth google, session jwt" }
  ],

  "edges": [
    { "from": "app/login/page.tsx", "to": "utils/format.ts" },
    { "from": "app/login/page.tsx", "to": "app/api/login/route.ts", "label": "on submit" }
  ]
}
```

Required: `repo`, `updated`, `stack`, `features`, `nodes`, `edges`. Node `id` is the repo-relative path (a short stable name for services), `caveman` is **max 10 tokens**, symbol `caveman` is **max 8**. `kind` ∈ `file` (default) · `route` · `db` · `external` · `job` · `config`. `feature` must match a declared one; omit it for externals. Both edge endpoints must exist as nodes; self-loops are rejected.

The example above is JS/TS-shaped; nothing in the schema is. A fullstack feature mixes languages freely, and the interesting edges are the ones that cross:

```json
{ "name": "billing", "route": "/billing, POST /api/invoices", "libs": ["stripe", "sqlc"] }
```
```json
{ "id": "internal/billing/invoice.go", "feature": "billing", "kind": "file",
  "caveman": "build invoice, prorate, pdf render, writes db" }
{ "id": "postgres", "kind": "db", "caveman": "invoices, line_items, payments" }
```
```json
{ "from": "app/billing/page.tsx", "to": "internal/api/invoice_handler.go", "label": "POST /api/invoices" }
{ "from": "internal/billing/invoice.go", "to": "postgres", "label": "writes invoices" }
```

`stack` carries the languages, so no node needs to repeat them.

## Token Budget

A full scan is the most expensive thing here. Reading a whole file is the **last** resort.

1. **Grep before reading.** One repo-wide pass for imports/exports/routes/access-control markers yields nearly the whole graph for a fraction of the tokens.
2. **Heads, not wholes.** The first ~60 lines carry everything a caveman line needs.
3. **Sample and generalize.** 20 files sharing a shape — read 2–3, infer the rest, mark inferred lines `?`, spot-check one at the end.
4. **Skip the long tail.** Files under ~10 lines get a line from the grep pass. Roll up `locales/`, `icons/`, `migrations/`, generated clients and protobuf output into a single node each.
5. **Never quote code.** The graph holds descriptions. Don't echo file contents back into the conversation.
6. **Let the script do the bookkeeping.** Everything it computes is free.
7. **Prefer incremental.** Check `stale.txt` first. Full rebuilds are once per repo, not once per session.
8. **Budget out loud.** Over ~500 files, say the scan is big and offer to scope it. Don't silently burn a context window.

## Incremental Updates

When `stale.txt` has content: read only those paths → patch their nodes, symbols and **outgoing** edges in `graph.json`, add new files, drop deleted ones → re-run `build` → bump `updated`, empty `stale.txt`. Don't rewrite untouched nodes; keep the diff small.

## Running as a Post Hook

**MAP is the only hooked phase.** FIND opines and FIX edits source; both stay invocation-only, never wired to a commit. Hook scripts live here, in `hooks/`.

Install with `../install.sh --hook`, which copies both into the target repo's `.tidy/hooks/` and appends them to git `post-commit` (works for any agent and for humans):

| Script | Calls an LLM | Does |
| --- | --- | --- |
| `tidy-stale.sh` | no | Appends changed paths to `.tidy/stale.txt`. Fast, free, always runs. |
| `tidy-automap.sh` | yes, detached | Launches headless `claude -p "/tidy-map"` with `nohup ... &` so the commit returns immediately. Only fires if `.tidy/graph.json` already exists and `claude` is on PATH; logs to `.tidy/hooks/automap.log`. |

Layered on purpose: if `claude` is missing or the background run fails, `stale.txt` is still correct and the next interactive `/tidy-map` picks it up.

Optional **harness stop hook**, so uncommitted work is tracked too. Claude Code, in `.claude/settings.json`:

```json
{ "hooks": { "Stop": [ { "hooks": [{ "type": "command", "command": ".tidy/hooks/tidy-stale.sh" }] } ] } }
```

Other harnesses: point their post-turn hook at the same `.tidy/hooks/tidy-stale.sh`. Wire only `tidy-stale.sh` here — an automap on every turn would remap mid-task. Both scripts are plain POSIX shell, take no arguments, and always exit 0.

## Mistakes

- **Authoring reverse edges.** `used by` is computed.
- **Reading every markdown file.** `README.md` + agent instruction files only.
- **Opening files the grep pass already answered.**
- **Touching `.env*` or formatter configs.** Only `.env.local`, only key names.
- **Prose instead of caveman.** "This file handles authentication using better-auth" costs 3× "better-auth config, session, jwt" and says less.
- **Folder-shaped features.** `components/` is not a feature. `/login` is.
- **Language-shaped features.** `frontend` and `backend` are not features either. One feature owns its whole vertical slice.
- **Assuming JS/TS.** Detect the stack first; read `../tidy/languages.md` when it isn't JS/TS.
- **Stopping at import statements.** In a fullstack repo the HTTP, queue and DI edges are the ones worth having.
- **Mapping generated code.** Protobuf/ORM/OpenAPI output is one rolled-up node — edge from the caller to the real service instead.

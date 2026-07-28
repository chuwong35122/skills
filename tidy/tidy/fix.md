# FIX

`/tidy <input>` — resolve `<input>` against `.tidy/findings.md` to one or more findings, then run the procedure below on each.

## 0. Resolve the input

| Input looks like | Resolves to |
| --- | --- |
| A finding ID — `DUP-01`, `dup-01`, `#DUP-01` | That exact finding. Case-insensitive, `#` optional. |
| A bare type — `DUP`, `dead`, `god` | Every open (not `✔ fixed`) finding of that type. List them and confirm before running — this can be several fixes, not one. |
| `all` | Every open finding with `effort: S`, per the rule below. |
| Free text — `"the duplicate formatTHB"`, `"remove the legacy mailer"` | Match against finding headings and bodies in `findings.md`. One clear match → confirm the ID back to the user in one line, then proceed. Multiple or no match → list the candidates (or say nothing matched) and stop; don't guess. |

An input naming an already-`✔ fixed` finding: say so and stop — nothing to do.

## 1. Fix procedure, per resolved finding

1. **Re-verify** against current source. The graph may be stale; if the finding no longer holds, say so and stop.
2. **Baseline.** Detect the repo's own checks — a `typecheck`/`lint`/`test` script declared in the manifest first, else the ecosystem default from `languages.md` §5 (`tsc --noEmit` · `pytest` · `go build ./...` · `cargo check` · `./gradlew build` · `dotnet build` · `dart analyze` · `mix compile`) — and run them. In a polyglot repo run only the checks for the ecosystem you're about to touch. **Baseline red → stop and report. Never refactor on top of a broken build.** No check available at all → say so and let the user decide before editing; never install a toolchain to manufacture a gate.
3. **Apply** the edit.
4. **Re-run the same checks.** Green → green: keep. Green → red: **revert the touched paths** and report which check failed and why.
5. **Patch `graph.json`** (nodes, symbols, edges), append touched paths to `.tidy/stale.txt`, re-run `build`.
6. **Mark** the finding `✔ fixed YYYY-MM-DD` in place in `findings.md` — never delete it, so the file doubles as a cleanup log.

Multiple resolved findings (a type, `all`, or an ambiguous-but-confirmed free-text match spanning several) run **sequentially**, same gate on each, halting on the first revert.

Needs `.tidy/findings.md` triaged already — run `/tidy-map` then `/tidy-find` first if it doesn't exist.

## Never

- Apply a refactor that wasn't resolved to a specific finding in `findings.md`.
- Guess at a free-text match when more than one finding fits — list them and ask instead.
- Batch unrelated findings into one edit.
- Skip the gate because the change "looks trivial".
- Fix while the baseline is already red.
- Install a linter, formatter or test runner the repo doesn't already use.
- Move a symbol across a language boundary. `shared` spans languages; a single refactor doesn't.

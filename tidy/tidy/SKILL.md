---
name: tidy
description: Use when the user types /tidy <ID>, /tidy <type>, /tidy all, or names a finding in plain text ("fix the duplicate formatTHB", "remove the legacy mailer") — or when an LLM working autonomously has a triaged finding from .tidy/findings.md it should resolve rather than hand-rolling the fix. Applies whenever a named or triaged finding needs fixing, not only on explicit invocation. Resolves the input to one or more findings, re-verifies against current source, runs the repo's own typecheck/lint/test as a baseline, applies the edit, re-runs the checks, and reverts on red. Never applies an unnamed or un-triaged refactor, and never guesses when free text matches more than one finding. Third of three sibling skills — tidy-map (/tidy-map) builds the graph, tidy-find (/tidy-find) produces the findings this one fixes. This skill's directory also hosts the shared graph engine (tidy_graph.py, languages.md, graph-format.md) that tidy-map and tidy-find reference.
---

# Tidy · FIX

Applies one named finding from `.tidy/findings.md`, behind the target repo's own verification gate. The only phase that touches source.

Part of a 3-skill set sharing one graph:

| Skill | Command | Does |
| --- | --- | --- |
| tidy-map | `/tidy-map` | builds/updates the graph — **run this first if `.tidy/graph.json` doesn't exist** |
| tidy-find | `/tidy-find` | triages leads into ranked findings — **run this first if `.tidy/findings.md` doesn't exist** |
| **tidy** (this one) | `/tidy <ID>` | applies one named finding, behind a verification gate |

**One rule.** Only ever act on a finding resolved from `findings.md` — never an unnamed or un-triaged refactor.

## Read before you work

Read `fix.md` for the full procedure, including how `<input>` (an ID, a type like `DUP`, `all`, or free text) resolves to specific findings. It points at `languages.md` §5 for the per-ecosystem verification-gate command when the repo doesn't declare its own.

## Shared engine

This directory also holds the graph engine the other two skills run against, since it must exist in exactly one place:

| File | Used by |
| --- | --- |
| `scripts/tidy_graph.py` | all three, via `../tidy/scripts/tidy_graph.py` from the sibling skills |
| `languages.md` | all three — per-ecosystem read/skip/grep/resolve/verify tables |
| `graph-format.md` | all three — full key tables and generated-view reference |

`install.sh` lives one level up, at the container root (`../install.sh` from here) — it installs all three sibling skill directories together.

**Never hooked.** This skill edits source, so it only ever runs when a user or agent invokes it. The post-commit hook scripts belong to tidy-map (`../tidy-map/hooks/`) and run `/tidy-map` alone.

## When to Use

- `/tidy DUP-01` — apply the exact finding.
- `/tidy DUP` — apply every open finding of that type, after listing them and confirming.
- `/tidy all` — apply every `effort: S` finding, sequentially, halting on the first revert.
- `/tidy remove the legacy mailer` — match free text against `findings.md`; one clear match confirms and proceeds, more than one lists candidates and stops.
- No `findings.md` yet → say so and point at `/tidy-find` first.

**Not for:** building the graph (`/tidy-map`), triaging leads (`/tidy-find`), an edit that doesn't resolve to a specific finding.

## Common Mistakes

- **Fixing without a baseline check.** Baseline red → stop and report, never refactor on top of a broken build.
- **Guessing at an ambiguous free-text match.** List the candidates and ask instead.
- **Batching unrelated findings into one edit.**
- **Skipping the gate because the change "looks trivial."**
- **Installing a linter, formatter or test runner the repo doesn't already use** to manufacture a gate.
- **Moving a symbol across a language boundary.** `shared` spans languages; a single refactor doesn't.

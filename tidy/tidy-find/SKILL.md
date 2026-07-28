---
name: tidy-find
description: Use when the user types /tidy-find, wants cleanup, dedupe, or an answer to "what's messy here?", or — for an LLM working autonomously — before adding code, to check whether the change would create a duplicate, misplaced module, or god file rather than reusing what's already mapped. Applies whenever the need arises, not only on explicit invocation. Runs deterministic set maths over the .tidy/graph.json knowledge graph (built by tidy-map) to surface duplicate functions, missed reuse, misplaced modules, dead code and god files, then triages the raw leads into ranked, fixable findings. No source is modified. Second of three sibling skills — tidy-map (/tidy-map) builds the graph this reads, tidy (/tidy <ID>) later applies one named finding.
---

# Tidy · FIND

Triages mechanical leads into ranked, fixable findings. No source is modified.

Part of a 3-skill set sharing one graph:

| Skill | Command | Does |
| --- | --- | --- |
| tidy-map | `/tidy-map` | builds/updates the graph — **run this first if `.tidy/graph.json` doesn't exist** |
| **tidy-find** (this one) | `/tidy-find` | triages leads into ranked findings |
| tidy | `/tidy <ID>` | applies one named finding, behind a verification gate |

| Path | Written by | What it is |
| --- | --- | --- |
| `.tidy/candidates.json` | script | Raw mechanical leads. Noisy by design. |
| `.tidy/findings.md` | **you** | Triaged, ranked, fixable findings. What `/tidy <ID>` reads. |

**One rule.** `findings.md` is the only file you author here — never fix straight from `candidates.json`.

## Read before you work

Read `find.md` for the full procedure. It points at `../tidy/languages.md` for anything not pure JS/TS (per-ecosystem `DEAD`/dynamic-dispatch caveats) and `../tidy/graph-format.md` for the full `candidates.json` schema if needed.

## When to Use

- `/tidy-find` — the user wants cleanup, dedupe, or "what's messy here?".
- No graph yet → say so and point at `/tidy-map` first.

**Not for:** building or updating the graph (`/tidy-map`), applying a fix (`/tidy <ID>`).

## Common Mistakes

- **Treating candidates as findings.** `candidates.json` is unreviewed machine output — never fix straight from it.
- **Hand-editing `candidates.json`.** It's regenerated on every run.
- **Proposing a deletion on a `DEAD` finding** without confirming it isn't reached dynamically.
- **Running on a graph with no `symbols`.** Yields no `DUP`/`REUSE` at all — backfill symbols via `/tidy-map` first.

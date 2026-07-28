---
name: tidy-map
description: Use when the user types /tidy-map, wants to see how a codebase fits together so each change can be visualized in context, or — for an LLM — needs to understand the existing codebase before implementing something new, so the new work reuses existing files, components, and API routes instead of duplicating them. Also answers "what uses X?", "what breaks if X changes?", "does X already exist?" against an already-mapped repo. Works on any language, framework, or fullstack/polyglot repo. Scans the repo into a caveman-compressed knowledge graph (.tidy/graph.json) and renders an interactive force-directed graph plus grep-friendly markdown. First of three sibling skills — tidy-map builds the graph, tidy-find (/tidy-find) triages cleanup leads from it, tidy (/tidy <ID>) applies one named fix.
---

# Tidy · MAP

Builds or patches `.tidy/graph.json`, then renders it. Touches no source.

Part of a 3-skill set sharing one graph:

| Skill | Command | Does |
| --- | --- | --- |
| **tidy-map** (this one) | `/tidy-map` | builds/updates the graph, answers "what uses X?" |
| tidy-find | `/tidy-find` | triages leads into ranked findings |
| tidy | `/tidy <ID>` | applies one named finding, behind a verification gate |

Language-agnostic: the graph format and this skill care about files, symbols and edges, not syntax. `../tidy/languages.md` supplies per-ecosystem specifics — read it unless the repo is pure JS/TS.

| Path | Written by | What it is |
| --- | --- | --- |
| `.tidy/graph.json` | **you** | Features, nodes (caveman line + symbols), directed edges. The source of truth. |
| `.tidy/index.html` | script | Interactive graph — drag, zoom, search, click for caveman line and both edge lists. |
| `.tidy/contexts.md` | script | Index: feature pointers, shared, external, orphans, feature edges. |
| `.tidy/features/<name>.md` | script | Per-feature entries with `→ uses` / `← used by`. What you grep. |

**One rule.** `graph.json` is the only file you author here — never hand-edit the script's output.

## Read before you work

| Doing | Read first |
| --- | --- |
| Any scan, rebuild, incremental, or scoped map | `map.md` |
| Mapping anything that isn't pure JS/TS | `../tidy/languages.md` **as well** |
| A question about an existing graph | nothing — see **Query** below |
| Full key tables, or how the generated views work | `../tidy/graph-format.md` |

## When to use

- `/tidy-map` — full or incremental map (see Modes).
- "what uses X?", "what breaks if I change X?", "is there already something that does X?" — answer from the graph, don't re-read source.
- **Before building anything** — check the graph first so new code reuses existing files, components and API routes instead of duplicating them.
- **Automatically, after every commit** — this is the only phase safe to hook, because it touches no source. `hooks/` holds the two scripts, `../install.sh --hook` wires them into git `post-commit`. See **Running as a Post Hook** in `map.md`.

**Not for:** cleanup/dedupe triage (`/tidy-find`), applying a fix (`/tidy <ID>`), end-user docs, API reference, architecture prose.

## Modes

| Mode | Trigger | What you do |
| --- | --- | --- |
| **Full** | no `graph.json`, or `/tidy-map full` | Read `map.md`. Scan repo, write `graph.json`, run `build`. |
| **Incremental** | `stale.txt` non-empty, or `/tidy-map` with a graph | Read `map.md`. Patch only stale paths, re-run `build`, clear `stale.txt`. |
| **Query** | `/tidy-map <question>` | Grep `.tidy/features/*.md` — see below. |
| **Scoped** | `/tidy-map <path-or-feature>` | Read `map.md`. Re-map that subtree only. |

With an existing graph and empty `stale.txt`, still diff against the filetree: add new files, drop deleted ones.

## Query

Grep the generated markdown instead of parsing `graph.json` or reading source. `grep -l "<path>" .tidy/features/*.md` names a file's owning feature; `grep -A2 "<path>" .tidy/features/*.md` gives its caveman line plus both edge lists — a few dozen tokens, cheapest way to answer impact/reuse questions.

Open source only when the graph genuinely can't answer. Never quote file contents back into the conversation.

## Session start

If `.tidy/stale.txt` is non-empty, mention it and offer the incremental update. Don't run one unasked.

## Common Mistakes

- **Hand-editing generated files.** Edit `graph.json` and re-run the script.
- **Full rescan every time.** Check `stale.txt` first.
- **Assuming the repo is JS/TS.** Detect the stack before mapping; a fullstack repo is one graph, not one per language.
- **Skipping the script.** An unvalidated `graph.json` means broken edges nobody noticed.
- **Committing `.tidy/` blindly.** Ask: tracked (useful for teams) or gitignored (personal cache). Default tracked, with `stale.txt` and `candidates.json` ignored.

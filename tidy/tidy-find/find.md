# FIND

Triage mechanical leads into ranked, fixable findings. No source is modified.

## 1. Run the script

```bash
python3 ../tidy/scripts/tidy_graph.py find --root <repo root>
```

Needs an existing `.tidy/graph.json` — run `/tidy-map` first if there isn't one.

Deterministic set maths over `graph.json` alone — no file reads, no LLM, free. It writes `.tidy/candidates.json`:

| ID | Pass |
| --- | --- |
| `DUP` | symbol pairs in different features with a matching normalized name or ≥0.6 caveman overlap. Names normalize across conventions (`getFormatTHB`, `format_thb`, `MustFormatTHB`, `Billing::formatTHB` all collapse), so this fires **across languages** too — that's a real finding in a fullstack repo, and often the one worth having |
| `REUSE` | same, but one side already lives in `shared` — so there's a canonical version to point at |
| `MOVE` | node reaching 3+ features but not filed under `shared`; scattered siblings that belong together |
| `DEAD` | no importers, and not entry-point-shaped |
| `GOD` | ≥12 dependencies or ≥15 exported symbols — one file doing too many jobs |

Every entry carries a stable `id`, a `type`, a `why` naming the rule that fired, and a `blast_radius`. Thresholds live at the top of the script (`SIMILARITY`, `SHARED_THRESHOLD`, `GOD_USES`, `GOD_SYMBOLS`).

**Candidates are leads, not findings.** The thresholds are deliberately loose: a strict script finds nothing, and you are the filter.

## 2. Triage into `findings.md`

For each candidate, open only the files it names and decide. Kill false positives silently. Then write `.tidy/findings.md`:

```markdown
### DUP-01 · payoff high · effort S
`billing/format.ts:formatTHB` ≡ `shared/format.ts:formatTHB`
both: format number, currency THB, 2dp
fix: delete billing copy, import from shared/format.ts
blast radius: 4 files

### DEAD-02 · payoff low · effort S · unsure
`lib/legacy-mailer.ts` — no importers in the graph
check: registered by name anywhere? DI container, cron config, string lookup?
fix: if genuinely unreachable, delete
```

- **effort** `S` (mechanical, one obvious edit) · `M` (needs a judgement call) · `L` (design change). Only `S` is eligible for `/tidy all`.
- **payoff** high/medium/low — weight by blast radius and how likely the next feature is to trip over it.
- Order by payoff, then effort ascending.
- Keep the candidate id as the heading key, so `/tidy DUP-01` can find it.

**`DEAD` findings never propose deletion outright.** Dynamic dispatch — DI containers, route auto-discovery, string-keyed registries, reflection, Rails-style constant autoloading, C# partial classes — is invisible to the graph. Mark them `unsure` and say what to check.

**A cross-language duplicate is a finding, not a fix.** Two implementations of the same rule in Go and TypeScript are worth naming — but the fix is a shared contract or a single owner, which is `effort: L`, never a mechanical move. Say which side should be canonical and stop there.

Report the counts and the top few. Don't fix anything yet.

## Mistakes

- **Treating candidates as findings.** `candidates.json` is unreviewed machine output — never fix straight from it.
- **Hand-editing `candidates.json`.** It's regenerated on every `find`.
- **Proposing a deletion on a `DEAD` finding** without confirming it isn't reached dynamically.
- **Running `find` on a graph with no `symbols`.** It yields no `DUP`/`REUSE` at all — backfill symbols first.

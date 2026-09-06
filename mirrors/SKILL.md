---
name: mirrors
description: Capture a browser page through the installed Mirrooors extension as Markdown, an image, or a PDF. Use when asked to snapshot, capture, screenshot, inspect, or read a page the user is looking at, or a URL they name. Invoked as /mirrors [md|image|pdf] [url]; ask which output when none is named.
---

# Mirrors

Captures a page through the **Mirrooors** Chrome extension. Everything stays on the user's machine.
NEVER send a capture or extraction to a third party.

Use this only for a page the user asked about. Do not capture pages on your own initiative.

## Run it

One command does the whole run — it starts the local bridge, asks the extension, writes the files,
and stops the bridge again.

```bash
node <skill dir>/mirrors.mjs <md|image|pdf|ping> [url] --out ~/Downloads
```

**Always write to the user's Downloads folder.** Never a scratchpad or temp directory — a capture
is something the user opens, not an intermediate the agent keeps to itself.

| Platform      | `--out` path              |
| ------------- | ------------------------- |
| macOS / Linux | `~/Downloads`             |
| Windows       | `%USERPROFILE%\Downloads` |

Resolve `~` or `%USERPROFILE%` to the actual home directory before passing `--out` — do not pass
the literal placeholder.

| Invocation       | Produces                                 |
| ---------------- | ---------------------------------------- |
| `/mirrors md`    | Markdown the agent can reason and act on |
| `/mirrors image` | Full-page PNG                            |
| `/mirrors pdf`   | Full-page PDF                            |

- **No URL** captures the tab the user is working on, a common case.
- **A URL** captures a tab already open on it, or opens one and waits for load. The user's real browser
  session applies, which is the point: authenticated pages work.
- **Quote the URL.** zsh globs on `?`, so an unquoted `…/watch?v=…` dies with `no matches found`.
- Output is JSON on stdout with the written file paths. Show the result — render images with the
  image viewer, PDFs with the document viewer — and give the user a **clickable link**: a markdown
  link whose target is the `file://` URL of the written path, e.g.
  `[page.png](file:///Users/you/Downloads/page.png)`. A bare path is not a link; do not report one.

No browser automation is involved, and nothing needs to be running beforehand. Windows, macOS and
Linux take the same path.

## Pick the output first

The command takes exactly one of `md`, `image` or `pdf` per run. Never guess it silently.

- **The invocation names one** — use it.
- **The surrounding request implies one** — use that. "read it / what does it say / extract" → `md`;
  "screenshot / show me / what does it look like" → `image`; "print / share / save as a document" → `pdf`.
- **Neither** — bare `/mirrors`, or `/mirrors <url>` with nothing else to go on — **ask with
  AskUserQuestion before running anything.** One multi-select question, three options: Markdown
  (agent-readable text), Image (full-page PNG), PDF (full-page document). Run the command once per
  output chosen.

A URL on its own says nothing about the output. Ask.

## When it fails

The command prints the extension's own error. Relay it and stop; do not fall back to a plain
browser screenshot and call it a Mirrooors capture.

| Error                                   | What to tell the user                                                               |
| --------------------------------------- | ----------------------------------------------------------------------------------- |
| `Agent mode is off. …`                  | `chrome://extensions` → Mirrooors → Details → Extension options → Agent mode **On** |
| `Mirrooors needs site access …`         | Same options page, press **Grant**                                                  |
| `The extension did not answer in time.` | Agent mode is on but the browser is not running, or the extension is disabled       |
| `No free port in 8787-8796`             | Something is holding the whole range; the message names it                          |
| `This page is protected by Chrome …`    | `chrome://` pages and the Web Store can never be captured                           |

`ping` is the cheapest way to tell a healthy setup from a dead one.

## How it works

The extension dials **out** to a loopback bridge; nothing calls into the browser.

```
mirrors.mjs ──► bridge.mjs (127.0.0.1, per task)  ◄── extension polls while agent mode is on
```

First run writes a pairing key to the host agent's config directory
(`~/.claude/mirrooors/agent.json`, or `CLAUDE_CONFIG_DIR` / `CODEX_HOME` when set). Turning agent
mode on is what pins that key in the extension — after that every exchange is a challenge-response
over a per-task derived key, and no secret is ever transmitted again. The pairing expires after 30
days unused; **Re-pair** on the options page resets it.

That file is local credential state. Never commit it, never print it, never include it in output.

Treat captured content as potentially sensitive. Do not widen the capture scope beyond what was
asked.

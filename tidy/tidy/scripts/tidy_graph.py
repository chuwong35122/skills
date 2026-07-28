#!/usr/bin/env python3
"""
tidy_graph.py — turn .tidy/graph.json into an interactive graph + markdown views.

graph.json is the single source of truth: the agent writes it, this script derives
everything else. Reverse edges (`used by`), shared-module detection, orphans,
feature-level edges and degrees are all computed here, never hand-maintained.

  python3 tidy_graph.py build [--root .]   # write index.html + contexts.md + features/*.md
  python3 tidy_graph.py check [--root .]   # validate graph.json, write nothing
  python3 tidy_graph.py find  [--root .]   # write candidates.json — raw tidy-up leads

Standard library only — no pip install, no CDN, no network. The generated HTML is
fully self-contained and opens straight from disk.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import defaultdict

SHARED = "shared"
# A node used by this many distinct features is flagged shared even if the agent
# didn't file it there.
SHARED_THRESHOLD = 3

KINDS = ("file", "route", "db", "external", "job", "config")

# Caveman token caps.
MAX_NODE_TOKENS = 10
MAX_SYMBOL_TOKENS = 8

# `find` thresholds. Deliberately blunt — the script produces leads, the agent
# triages them. Too strict here and real duplicates never surface at all.
SIMILARITY = 0.6      # Jaccard over caveman token sets to call two symbols alike.
GOD_USES = 12         # out-degree at which a file is doing too many things.
GOD_SYMBOLS = 15      # exported-symbol count with the same meaning.

# Name noise stripped before comparing symbols: get/fetch/load all mean "read",
# make/build/new/create all mean "construct". Spans naming conventions — Go's
# `MustX`, Rust's `try_x` and JS's `useX` are the same wrapper idiom.
NAME_PREFIXES = ("get", "fetch", "load", "read", "do", "handle", "use", "make",
                 "build", "to", "new", "create", "must", "try", "compute")


# ---------------------------------------------------------------- load & verify


def load(root: str) -> dict:
    path = os.path.join(root, ".tidy", "graph.json")
    if not os.path.exists(path):
        die(f"{path} not found — run /tidy to build the graph first.")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def validate_symbols(nid: str, node: dict) -> list[str]:
    """`symbols` is optional; when present it must be usable by `find`."""
    symbols = node.get("symbols")
    if symbols is None:
        return []
    if not isinstance(symbols, list):
        return [f"{nid}: symbols must be a list"]

    problems: list[str] = []
    seen: set[str] = set()
    for sym in symbols:
        if not isinstance(sym, dict) or not sym.get("name"):
            problems.append(f"{nid}: every symbol needs a name")
            continue
        name = sym["name"]
        if name in seen:
            problems.append(f"{nid}: duplicate symbol name {name!r}")
        seen.add(name)
        if not sym.get("caveman"):
            problems.append(f"{nid}:{name}: missing caveman description")
        elif len(sym["caveman"].split(",")) > MAX_SYMBOL_TOKENS:
            problems.append(f"{nid}:{name}: caveman line has more than "
                            f"{MAX_SYMBOL_TOKENS} tokens — trim it")
    return problems


def validate(graph: dict) -> list[str]:
    """Return a list of problems. Empty list means the graph is well-formed."""
    problems: list[str] = []
    nodes = graph.get("nodes") or []
    if not nodes:
        problems.append("no nodes")

    seen: set[str] = set()
    features = {f["name"] for f in graph.get("features") or []}
    features.add(SHARED)

    for i, node in enumerate(nodes):
        nid = node.get("id")
        if not nid:
            problems.append(f"node #{i} has no id")
            continue
        if nid in seen:
            problems.append(f"duplicate node id: {nid}")
        seen.add(nid)
        if ":" in nid:
            # `find` writes `path:symbol` refs and splits them back on the colon.
            problems.append(f"{nid}: node id may not contain ':'")
        if not node.get("caveman"):
            problems.append(f"{nid}: missing caveman description")
        kind = node.get("kind", "file")
        if kind not in KINDS:
            problems.append(f"{nid}: unknown kind {kind!r} (expected one of {', '.join(KINDS)})")
        feat = node.get("feature")
        if feat and feat not in features:
            problems.append(f"{nid}: feature {feat!r} is not declared in features[]")
        if len((node.get("caveman") or "").split(",")) > MAX_NODE_TOKENS:
            problems.append(f"{nid}: caveman line has more than {MAX_NODE_TOKENS} tokens — trim it")
        problems.extend(validate_symbols(nid, node))

    for i, edge in enumerate(graph.get("edges") or []):
        src, dst = edge.get("from"), edge.get("to")
        if src not in seen:
            problems.append(f"edge #{i}: unknown source {src!r}")
        if dst not in seen:
            problems.append(f"edge #{i}: unknown target {dst!r}")
        if src == dst:
            problems.append(f"edge #{i}: self-loop on {src!r}")

    return problems


# ---------------------------------------------------------------------- derive


def derive(graph: dict) -> dict:
    """Compute everything the agent should never hand-maintain."""
    nodes = {n["id"]: dict(n) for n in graph["nodes"]}
    edges = [e for e in (graph.get("edges") or []) if e.get("from") in nodes and e.get("to") in nodes]

    uses: dict[str, list[str]] = defaultdict(list)
    used_by: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        uses[edge["from"]].append(edge["to"])
        used_by[edge["to"]].append(edge["from"])

    for nid, node in nodes.items():
        node.setdefault("kind", "file")
        node.setdefault("feature", None)
        node["uses"] = sorted(set(uses[nid]))
        node["used_by"] = sorted(set(used_by[nid]))
        node["degree"] = len(node["uses"]) + len(node["used_by"])
        # Which features reach into this node — the reuse signal.
        consumers = {nodes[u].get("feature") for u in node["used_by"]}
        consumers.discard(None)
        consumers.discard(node.get("feature"))
        node["consumer_features"] = sorted(consumers)
        node["shared"] = node.get("feature") == SHARED or len(consumers) >= SHARED_THRESHOLD
        node["entry"] = not node["used_by"] and node["kind"] in ("file", "route")

    # Feature-level edges, deduped.
    feature_edges: set[tuple[str, str]] = set()
    for edge in edges:
        a = nodes[edge["from"]].get("feature")
        b = nodes[edge["to"]].get("feature")
        if a and b and a != b:
            feature_edges.add((a, b))

    features = []
    for feat in graph.get("features") or []:
        feat = dict(feat)
        members = [n for n in nodes.values() if n.get("feature") == feat["name"]]
        feat["count"] = len(members)
        features.append(feat)

    # Only real source files can be orphans. An unowned datastore or third-party
    # service is infrastructure, not dead code — it gets its own section.
    orphans = [n for n in nodes.values()
               if not n.get("feature") and n["kind"] in ("file", "route", "config")]
    external = [n for n in nodes.values()
                if not n.get("feature") and n["kind"] in ("db", "external", "job")]

    return {
        "meta": {
            "repo": graph.get("repo", ""),
            "updated": graph.get("updated", ""),
            "stack": graph.get("stack", ""),
        },
        "features": features,
        "nodes": list(nodes.values()),
        "edges": edges,
        "feature_edges": sorted(feature_edges),
        "orphans": orphans,
        "external": external,
    }


# ----------------------------------------------------------------------- find


def tokens(caveman: str) -> frozenset[str]:
    """Caveman line → comparable token set. `?` marks an inferred line, not a token."""
    return frozenset(t.strip().rstrip("?").lower() for t in (caveman or "").split(",") if t.strip())


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def norm_name(name: str) -> str:
    """formatTHB / format_thb / getFormatTHB all collapse to the same key.

    Qualifiers are dropped first, so `Billing::formatTHB`, `Billing.formatTHB`
    and `(*Billing).FormatTHB` compare as the bare method across languages."""
    for sep in ("::", ".", "->", "#"):
        name = name.rsplit(sep, 1)[-1]
    flat = "".join(ch for ch in name.lower() if ch.isalnum())
    for prefix in NAME_PREFIXES:
        if flat.startswith(prefix) and len(flat) > len(prefix) + 2:
            return flat[len(prefix):]
    return flat


def source_nodes(model: dict) -> list[dict]:
    """Real files we could refactor — never externals, datastores or jobs."""
    return [n for n in model["nodes"] if n["kind"] in ("file", "route", "config")]


def find_candidates(model: dict) -> list[dict]:
    """Mechanical leads only. Deterministic set maths over graph.json — no file reads,
    no judgement. The agent confirms each one before it becomes a finding."""
    nodes = source_nodes(model)
    out: list[dict] = []
    counter: defaultdict[str, int] = defaultdict(int)

    def emit(kind: str, prefix: str, **fields) -> None:
        counter[prefix] += 1
        out.append({"id": f"{prefix}-{counter[prefix]:02d}", "type": kind, **fields})

    # --- DUP / REUSE: every cross-file symbol pair that looks like the same idea.
    flat = [(n, s) for n in nodes for s in (n.get("symbols") or [])]
    for i, (node_a, sym_a) in enumerate(flat):
        for node_b, sym_b in flat[i + 1:]:
            if node_a["id"] == node_b["id"]:
                continue
            same_name = norm_name(sym_a["name"]) == norm_name(sym_b["name"])
            score = similarity(tokens(sym_a["caveman"]), tokens(sym_b["caveman"]))
            if not same_name and score < SIMILARITY:
                continue
            # One side already lives in shared → the other side is a missed reuse,
            # which has an obvious fix. Neither side shared → a plain duplicate.
            a_shared, b_shared = node_a.get("feature") == SHARED, node_b.get("feature") == SHARED
            fields = {
                "a": f"{node_a['id']}:{sym_a['name']}",
                "b": f"{node_b['id']}:{sym_b['name']}",
                "a_caveman": sym_a["caveman"],
                "b_caveman": sym_b["caveman"],
                "why": ("same normalized name" if same_name else "")
                       + (" + " if same_name and score >= SIMILARITY else "")
                       + (f"caveman overlap {score:.2f}" if score >= SIMILARITY else ""),
                "blast_radius": len(set(node_a["used_by"]) | set(node_b["used_by"])),
            }
            if a_shared != b_shared:
                canonical, copy = (node_a, node_b) if a_shared else (node_b, node_a)
                emit("reuse-miss", "REUSE", canonical=canonical["id"], copy=copy["id"], **fields)
            else:
                emit("duplicate", "DUP", **fields)

    # --- MOVE: pulled on by many features but never filed as shared. Unlike the
    # `shared` flag on the node, the owning feature counts here — a util in `auth`
    # that auth, billing and props all import belongs in shared, not in auth.
    feature_of = {n["id"]: n.get("feature") for n in model["nodes"]}
    for node in sorted(nodes, key=lambda n: -len(n["used_by"])):
        if node.get("feature") == SHARED:
            continue
        reach = {feature_of.get(u) for u in node["used_by"]} | {node.get("feature")}
        reach.discard(None)
        if len(reach) >= SHARED_THRESHOLD:
            emit("misplaced", "MOVE", node=node["id"], feature=node.get("feature"),
                 consumers=sorted(reach),
                 why=f"reaches {len(reach)} features, not filed under {SHARED}")

    # --- DEAD: nothing imports it. Always unsure — dynamic dispatch is invisible
    # here. A file that imports things but exports nothing importable is an entry
    # point, not dead code, so it is skipped.
    for node in nodes:
        if node["kind"] != "file" or node["used_by"]:
            continue
        if node["uses"] and not node.get("symbols"):
            continue
        emit("dead", "DEAD", node=node["id"], feature=node.get("feature"),
             confidence="unsure",
             why="no importers in the graph; confirm it is not reached dynamically")

    # --- GOD: one file, too many jobs.
    for node in nodes:
        n_syms = len(node.get("symbols") or [])
        if len(node["uses"]) >= GOD_USES or n_syms >= GOD_SYMBOLS:
            emit("god-file", "GOD", node=node["id"], feature=node.get("feature"),
                 uses=len(node["uses"]), symbols=n_syms,
                 why=f"{len(node['uses'])} dependencies, {n_syms} exported symbols")

    return out


FLAGS = ("DUP", "REUSE", "MOVE", "DEAD", "GOD")


def node_of(ref: str) -> str:
    """`billing/fmt.ts:formatTHB` → `billing/fmt.ts`. Bare ids pass through.

    Splits on the *first* colon, not the last: a qualified symbol name may hold
    its own separators (`Billing::format`, `Billing.format`), while node ids are
    repo-relative paths and never contain one."""
    return ref.split(":", 1)[0] if ":" in ref else ref


def attach_candidates(model: dict, candidates: list[dict]) -> None:
    """Hang each candidate off every node it names, so the graph can show them.
    A DUP names two files and lands on both — either end is a valid place to
    notice it."""
    by_node: defaultdict[str, list[dict]] = defaultdict(list)
    for cand in candidates:
        refs = [cand[k] for k in ("a", "b", "node") if cand.get(k)]
        for ref in refs:
            nid = node_of(ref)
            partners = [node_of(r) for r in refs if node_of(r) != nid]
            by_node[nid].append({
                "id": cand["id"],
                "flag": cand["id"].split("-")[0],
                "why": cand.get("why", ""),
                "partner": partners[0] if partners else None,
                "unsure": cand.get("confidence") == "unsure",
            })

    for node in model["nodes"]:
        hits = by_node.get(node["id"], [])
        node["candidates"] = hits
        node["flags"] = sorted({h["flag"] for h in hits}, key=FLAGS.index)


def load_candidates(root: str) -> list[dict]:
    """Read `find` output if it exists. Absent or malformed is not an error —
    the graph simply renders without findings."""
    path = os.path.join(root, ".tidy", "candidates.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("candidates") or []
    except (json.JSONDecodeError, AttributeError):
        print(f"warning: {path} is unreadable — rendering without findings", file=sys.stderr)
        return []


def write_candidates(model: dict, root: str) -> tuple[str, list[dict]]:
    candidates = find_candidates(model)
    payload = {
        "generated": "tidy_graph.py find — machine output, do not hand-edit",
        "repo": model["meta"]["repo"],
        "counts": {k: sum(1 for c in candidates if c["id"].startswith(k))
                   for k in ("DUP", "REUSE", "MOVE", "DEAD", "GOD")},
        "candidates": candidates,
    }
    path = os.path.join(root, ".tidy", "candidates.json")
    write(path, json.dumps(payload, indent=2) + "\n")
    return path, candidates


# ------------------------------------------------------------------- markdown


def fmt_entry(node: dict) -> str:
    lines = [f"- `{node['id']}` — {node['caveman']}"
             + ("  (SHARED)" if node["shared"] and node.get("feature") != SHARED else "")]
    if node["uses"]:
        lines.append("  → uses: " + ", ".join(node["uses"]))
    if node["used_by"]:
        lines.append("  ← used by: " + ", ".join(node["used_by"]))
    elif node["entry"]:
        lines.append("  ← used by: (entry point)")
    return "\n".join(lines)


def write_markdown(model: dict, root: str) -> list[str]:
    tidy = os.path.join(root, ".tidy")
    feat_dir = os.path.join(tidy, "features")
    os.makedirs(feat_dir, exist_ok=True)
    written = []

    meta = model["meta"]
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for node in model["nodes"]:
        if node.get("feature"):
            by_feature[node["feature"]].append(node)
    # Entry points first, then by descending degree — readable top-down.
    for members in by_feature.values():
        members.sort(key=lambda n: (not n["entry"], -n["degree"], n["id"]))

    named = [f for f in model["features"] if f["name"] != SHARED]
    shared_nodes = by_feature.get(SHARED, [])

    out = [
        "# contexts",
        "",
        "<!-- generated by tidy_graph.py from graph.json — edit graph.json, not this file -->",
        "",
        f"updated: {meta['updated']}",
        f"repo: {meta['repo']}",
        f"stack: {meta['stack']}",
        f"features: {len(named)} · files mapped: {len(model['nodes'])} · "
        f"shared: {len(shared_nodes)} · external: {len(model['external'])} · "
        f"orphans: {len(model['orphans'])}",
        "routing: entries in features/<name>.md · interactive graph: index.html",
        'find a file\'s owner: grep -l "<path>" .tidy/features/*.md',
        "legend: `→ uses` outgoing · `← used by` incoming · (SHARED) 3+ features · "
        "(entry point) nothing imports it",
        "",
        "## FEATURES",
        "",
    ]
    for feat in named:
        bits = [f"{feat['count']} files"]
        for key in ("route", "rbac"):
            if feat.get(key):
                bits.append(f"{key}: {feat[key]}")
        if feat.get("libs"):
            bits.append("libs: " + ", ".join(feat["libs"]))
        out.append(f"- **{feat['name']}** — " + " · ".join(bits))
        out.append(f"  → `features/{feat['name']}.md`")
    out.append("")

    if shared_nodes:
        out += ["## FEATURE: shared", ""]
        out += [fmt_entry(n) for n in shared_nodes]
        out.append("")

    if model["external"]:
        out += ["## EXTERNAL", ""]
        out += [f"- `{n['id']}` ({n['kind']}) — {n['caveman']}"
                + ("\n  ← used by: " + ", ".join(n["used_by"]) if n["used_by"] else "")
                for n in model["external"]]
        out.append("")

    if model["orphans"]:
        out += ["## ORPHANS", "", "Nothing imports these and they belong to no feature — review before deleting.", ""]
        out += [f"- `{n['id']}` — {n['caveman']}" for n in model["orphans"]]
        out.append("")

    if model["feature_edges"]:
        out += ["## EDGES", ""]
        grouped: dict[str, list[str]] = defaultdict(list)
        for a, b in model["feature_edges"]:
            grouped[a].append(b)
        for a in sorted(grouped):
            out.append(f"{a} → {', '.join(sorted(grouped[a]))}")
        out.append("")

    path = os.path.join(tidy, "contexts.md")
    write(path, "\n".join(out))
    written.append(path)

    for feat in named:
        members = by_feature.get(feat["name"], [])
        bits = [f"updated: {meta['updated']}"]
        for key in ("route", "rbac"):
            if feat.get(key):
                bits.insert(-1, f"{key}: {feat[key]}")
        if feat.get("libs"):
            bits.insert(-1, "libs: " + ", ".join(feat["libs"]))
        body = [
            f"# {feat['name']}",
            "",
            "<!-- generated by tidy_graph.py from graph.json — edit graph.json, not this file -->",
            "",
            " · ".join(bits),
            "index: `../contexts.md` · graph: `../index.html`",
            "",
        ]
        body += [fmt_entry(n) for n in members]
        body.append("")
        path = os.path.join(feat_dir, f"{feat['name']}.md")
        write(path, "\n".join(body))
        written.append(path)

    # Drop feature files whose feature no longer exists.
    keep = {f"{f['name']}.md" for f in named}
    for name in os.listdir(feat_dir):
        if name.endswith(".md") and name not in keep:
            os.remove(os.path.join(feat_dir, name))

    return written


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


# ------------------------------------------------------------------------ html


def short_labels(ids: list[str]) -> dict[str, str]:
    """Shortest unambiguous label per node. `page.tsx` is useless when six files
    share the basename, so collisions grow leftward until they're distinct."""
    labels: dict[str, str] = {}
    for depth in range(1, 5):
        counts: dict[str, int] = defaultdict(int)
        candidate = {}
        for nid in ids:
            parts = nid.split("/")
            candidate[nid] = "/".join(parts[-depth:])
            counts[candidate[nid]] += 1
        for nid in ids:
            if nid not in labels and counts[candidate[nid]] == 1:
                labels[nid] = candidate[nid]
        if len(labels) == len(ids):
            break
    for nid in ids:
        labels.setdefault(nid, nid)
    return labels


def write_html(model: dict, root: str) -> str:
    labels = short_labels([n["id"] for n in model["nodes"]])
    payload = {
        "meta": model["meta"],
        "features": [
            {k: f.get(k) for k in ("name", "route", "rbac", "libs", "count")}
            for f in model["features"]
        ],
        "nodes": [
            {
                "id": n["id"],
                "label": labels[n["id"]],
                "feature": n.get("feature"),
                "caveman": n.get("caveman", ""),
                "kind": n.get("kind", "file"),
                "path": n.get("path") or (n["id"] if n.get("kind", "file") in ("file", "route", "config") else None),
                "uses": n["uses"],
                "used_by": n["used_by"],
                "degree": n["degree"],
                "shared": n["shared"],
                "entry": n["entry"],
            }
            for n in model["nodes"]
        ],
        "edges": [{"s": e["from"], "t": e["to"], "l": e.get("label", "")} for e in model["edges"]],
    }
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    # </script> inside the JSON would close the tag early.
    data = data.replace("</", "<\\/")
    doc = HTML.replace("__TITLE__", html.escape(model["meta"].get("repo") or "tidy graph"))
    doc = doc.replace("__DATA__", data)
    path = os.path.join(root, ".tidy", "index.html")
    write(path, doc)
    return path


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · tidy graph</title>
<style>
/* Palette: dataviz reference instance. Both modes are selected, not flipped. */
:root {
  color-scheme: light;
  --surface: #fcfcfb;
  --plane: #f9f9f7;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --hair: #e1e0d9;
  --edge: #c3c2b7;
  --accent: #2a78d6;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100;
  --s5: #e87ba4; --s6: #008300; --s7: #4a3aa7; --s8: #e34948;
  --other: #898781;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --plane: #0d0d0d; --ink: #fff; --ink-2: #c3c2b7;
    --muted: #898781; --hair: #2c2c2a; --edge: #383835; --accent: #3987e5;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
    --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --plane: #0d0d0d; --ink: #fff; --ink-2: #c3c2b7;
  --muted: #898781; --hair: #2c2c2a; --edge: #383835; --accent: #3987e5;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
  --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  background: var(--plane); color: var(--ink);
  font: 13px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  display: grid; grid-template-columns: 1fr 320px; grid-template-rows: auto 1fr;
  grid-template-areas: "bar bar" "canvas panel";
}
header {
  grid-area: bar; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding: 10px 14px; background: var(--surface); border-bottom: 1px solid var(--hair);
}
h1 { font-size: 13px; font-weight: 600; margin: 0 8px 0 0; }
h1 span { color: var(--muted); font-weight: 400; }
input[type=search], select {
  font: inherit; color: var(--ink); background: var(--plane);
  border: 1px solid var(--hair); border-radius: 6px; padding: 5px 9px;
}
input[type=search] { flex: 1 1 160px; min-width: 130px; max-width: 300px; }
label.toggle { display: inline-flex; gap: 5px; align-items: center; color: var(--ink-2); cursor: pointer; }
button {
  font: inherit; color: var(--ink-2); background: var(--plane);
  border: 1px solid var(--hair); border-radius: 6px; padding: 5px 10px; cursor: pointer;
}
button:hover { color: var(--ink); }
#stage { grid-area: canvas; position: relative; background: var(--surface); overflow: hidden; }
canvas { display: block; width: 100%; height: 100%; }
#hint { position: absolute; left: 12px; bottom: 10px; color: var(--muted); font-size: 11px; pointer-events: none; }
aside {
  grid-area: panel; background: var(--surface); border-left: 1px solid var(--hair);
  padding: 14px; overflow: auto;
}
aside h2 { font-size: 12px; margin: 0 0 2px; word-break: break-all; }
aside .caveman { color: var(--ink-2); margin: 6px 0 12px; }
aside h3 { font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
           color: var(--muted); margin: 14px 0 5px; font-weight: 600; }
aside ul { list-style: none; margin: 0; padding: 0; }
aside li { padding: 2px 0; word-break: break-all; }
aside a { color: var(--accent); text-decoration: none; cursor: pointer; }
aside a:hover { text-decoration: underline; }
.chip {
  display: inline-flex; align-items: center; gap: 5px; font-size: 11px;
  color: var(--ink-2); border: 1px solid var(--hair); border-radius: 999px;
  padding: 2px 8px; margin: 0 4px 4px 0; cursor: pointer; background: none;
}
.chip .dot { width: 8px; height: 8px; border-radius: 50%; }
.chip.off { opacity: .4; }
.legend-shapes { color: var(--muted); font-size: 11px; line-height: 1.9; }
.empty { color: var(--muted); }
@media (max-width: 760px) {
  body { grid-template-columns: 1fr; grid-template-areas: "bar" "canvas" "panel"; }
  aside { border-left: 0; border-top: 1px solid var(--hair); max-height: 45vh; }
}
</style>
</head>
<body>
<header>
  <h1>__TITLE__ <span id="counts"></span></h1>
  <input type="search" id="search" placeholder="Search files, features, keywords…" autocomplete="off">
  <select id="focus"><option value="">All features</option></select>
  <label class="toggle"><input type="checkbox" checked id="colorByFeature"> Color by feature</label>
  <label class="toggle"><input type="checkbox" id="labelsAlways" checked> Labels</label>
  <button id="fit">Fit</button>
  <button id="reheat">Re-layout</button>
  <button id="theme">Theme</button>
</header>

<div id="stage">
  <canvas id="cv"></canvas>
  <div id="hint">drag node · scroll zoom · drag background pan · click select · double-click pin</div>
</div>

<aside>
  <div id="detail"><p class="empty">Click a node to inspect it.</p></div>
  <h3>Features</h3>
  <div id="legend"></div>
  <h3>Shapes</h3>
  <div class="legend-shapes">
    ● file &nbsp; ◆ route / entry &nbsp; ■ datastore<br>
    ⬢ external service &nbsp; ▲ job / cron<br>
    ring = shared across features · size = connections
  </div>
</aside>

<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

/* Feature colours use the fixed categorical order and are never cycled: past
   eight features everything else is grey "other". Colour is a grouping aid here,
   not the identity channel — every node carries a visible label, which is what
   keeps this legible under CVD (only the first three slots clear the all-pairs
   separation gate). */
const SLOTS = ['--s1','--s2','--s3','--s4','--s5','--s6','--s7','--s8'];
const featureOrder = DATA.features.map(f => f.name);
const featureColor = name => {
  const i = featureOrder.indexOf(name);
  return (i > -1 && i < SLOTS.length) ? css(SLOTS[i]) : css('--other');
};

const nodes = DATA.nodes.map(n => ({...n, x: 0, y: 0, vx: 0, vy: 0, pinned: false}));
const index = new Map(nodes.map(n => [n.id, n]));
const links = DATA.edges.map(e => ({s: index.get(e.s), t: index.get(e.t), l: e.l}))
                        .filter(l => l.s && l.t);
const neighbours = new Map(nodes.map(n => [n.id, new Set()]));
links.forEach(l => { neighbours.get(l.s.id).add(l.t.id); neighbours.get(l.t.id).add(l.s.id); });

/* Seed each feature's members around its own anchor so the layout starts
   clustered instead of untangling from a random cloud. */
const anchors = new Map();
const groups = [...new Set(nodes.map(n => n.feature || 'orphans'))];
groups.forEach((g, i) => {
  const a = (i / groups.length) * Math.PI * 2, r = 190 + groups.length * 9;
  anchors.set(g, {x: Math.cos(a) * r, y: Math.sin(a) * r});
});
nodes.forEach((n, i) => {
  const a = anchors.get(n.feature || 'orphans');
  n.x = a.x + Math.cos(i * 2.4) * 46;
  n.y = a.y + Math.sin(i * 2.4) * 46;
});

const radius = n => 4.5 + Math.min(11, Math.sqrt(n.degree) * 2.6);
let view = {x: 0, y: 0, k: 1}, alpha = 1, settleFit = true;
let hover = null, selected = null, dragging = null, panning = null;
let query = '', focusFeature = '', colorByFeature = true, labelsAlways = true;

function resize() {
  const r = cv.getBoundingClientRect(), dpr = devicePixelRatio || 1;
  cv.width = r.width * dpr; cv.height = r.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  view.x = view.x || r.width / 2; view.y = view.y || r.height / 2;
}
addEventListener('resize', () => { resize(); fit(); draw(); });

/* Frame the whole graph. The force layout has no idea how big the viewport is,
   so without this the drawing drifts off-screen on wide or small displays. */
function fit() {
  const w = cv.clientWidth, h = cv.clientHeight;
  if (!nodes.length || !w || !h) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) {
    const r = radius(n) + 26;                        // leave room for the label
    x0 = Math.min(x0, n.x - r); x1 = Math.max(x1, n.x + r);
    y0 = Math.min(y0, n.y - r); y1 = Math.max(y1, n.y + r);
  }
  const pad = 28;
  view.k = Math.max(0.15, Math.min(2.2, Math.min((w - pad * 2) / (x1 - x0), (h - pad * 2) / (y1 - y0))));
  view.x = w / 2 - ((x0 + x1) / 2) * view.k;
  view.y = h / 2 - ((y0 + y1) / 2) * view.k;
}

function tick() {
  if (alpha > 0.005) {
    alpha *= 0.985;
    const n = nodes.length;
    for (let i = 0; i < n; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < n; j++) {
        const b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
        if (d2 < 1e-4) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        if (d2 > 90000) continue;                       // ignore distant pairs
        const f = 2600 / d2, d = Math.sqrt(d2);
        const ux = dx / d * f, uy = dy / d * f;
        a.vx -= ux; a.vy -= uy; b.vx += ux; b.vy += uy;
      }
    }
    for (const l of links) {                            // springs
      const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
      const d = Math.hypot(dx, dy) || 1, f = (d - 74) * 0.012;
      const ux = dx / d * f, uy = dy / d * f;
      l.s.vx += ux; l.s.vy += uy; l.t.vx -= ux; l.t.vy -= uy;
    }
    for (const nd of nodes) {                           // cluster + centre gravity
      const a = anchors.get(nd.feature || 'orphans');
      nd.vx += (a.x - nd.x) * 0.006 - nd.x * 0.0016;
      nd.vy += (a.y - nd.y) * 0.006 - nd.y * 0.0016;
      if (nd === dragging || nd.pinned) { nd.vx = nd.vy = 0; continue; }
      nd.vx *= 0.82; nd.vy *= 0.82;
      nd.x += nd.vx * alpha * 2.2; nd.y += nd.vy * alpha * 2.2;
    }
    // Keep the whole graph framed while it settles, then leave the view alone
    // so the user's own pan/zoom is never yanked away.
    if (settleFit && !dragging && !panning) { fit(); if (alpha < 0.02) settleFit = false; }
  }
  draw();
  requestAnimationFrame(tick);
}

const matches = n => !query || n.id.toLowerCase().includes(query)
  || (n.caveman || '').toLowerCase().includes(query)
  || (n.feature || '').toLowerCase().includes(query);
const inFocus = n => !focusFeature || n.feature === focusFeature
  || (focusFeature && neighbours.get(n.id) && [...neighbours.get(n.id)]
      .some(id => index.get(id).feature === focusFeature));

function nodeAlpha(n) {
  if (!inFocus(n) || !matches(n)) return 0.12;
  const key = hover || selected;
  if (!key) return 1;
  return (n.id === key || neighbours.get(key).has(n.id)) ? 1 : 0.16;
}

function shape(p, x, y, r, kind) {
  p.beginPath();
  if (kind === 'db') { p.rect(x - r, y - r * 0.86, r * 2, r * 1.72); }
  else if (kind === 'route') {
    p.moveTo(x, y - r); p.lineTo(x + r, y); p.lineTo(x, y + r); p.lineTo(x - r, y); p.closePath();
  } else if (kind === 'external') {
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 6 + i * Math.PI / 3, px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
      i ? p.lineTo(px, py) : p.moveTo(px, py);
    }
    p.closePath();
  } else if (kind === 'job') {
    p.moveTo(x, y - r); p.lineTo(x + r, y + r * 0.8); p.lineTo(x - r, y + r * 0.8); p.closePath();
  } else { p.arc(x, y, r, 0, Math.PI * 2); }
}

function draw() {
  const w = cv.clientWidth, h = cv.clientHeight;
  ctx.clearRect(0, 0, w, h);
  ctx.save();
  ctx.translate(view.x, view.y); ctx.scale(view.k, view.k);
  const key = hover || selected;

  ctx.lineWidth = 1 / view.k;
  for (const l of links) {
    const lit = key && (l.s.id === key || l.t.id === key);
    const a = Math.min(nodeAlpha(l.s), nodeAlpha(l.t));
    ctx.globalAlpha = lit ? 0.95 : a * 0.42;
    ctx.strokeStyle = lit ? css('--accent') : css('--edge');
    ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke();
    if (lit) {                                          // arrowhead on the lit edge
      const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.hypot(dx, dy) || 1;
      const ex = l.t.x - dx / d * (radius(l.t) + 2), ey = l.t.y - dy / d * (radius(l.t) + 2);
      const a1 = Math.atan2(dy, dx), s = 7 / view.k;
      ctx.beginPath(); ctx.moveTo(ex, ey);
      ctx.lineTo(ex - Math.cos(a1 - 0.4) * s, ey - Math.sin(a1 - 0.4) * s);
      ctx.lineTo(ex - Math.cos(a1 + 0.4) * s, ey - Math.sin(a1 + 0.4) * s);
      ctx.closePath(); ctx.fillStyle = css('--accent'); ctx.fill();
    }
  }

  for (const n of nodes) {
    const r = radius(n), a = nodeAlpha(n);
    ctx.globalAlpha = a;
    ctx.fillStyle = colorByFeature ? featureColor(n.feature) : css('--accent');
    shape(ctx, n.x, n.y, r, n.kind); ctx.fill();
    if (n.shared) {                                     // ring = crosses features
      ctx.lineWidth = 2 / view.k; ctx.strokeStyle = css('--surface');
      shape(ctx, n.x, n.y, r + 2.5 / view.k, n.kind); ctx.stroke();
      ctx.lineWidth = 1.5 / view.k; ctx.strokeStyle = ctx.fillStyle;
      shape(ctx, n.x, n.y, r + 4 / view.k, n.kind); ctx.stroke();
    }
    if (n.id === selected) {
      ctx.lineWidth = 2 / view.k; ctx.strokeStyle = css('--ink');
      shape(ctx, n.x, n.y, r + 5 / view.k, n.kind); ctx.stroke();
    }
    const big = r > 8 || n.id === key || (query && matches(n));
    if ((labelsAlways && view.k > 0.55) || big) {
      ctx.globalAlpha = a;
      ctx.fillStyle = n.id === key ? css('--ink') : css('--ink-2');
      ctx.font = `${11 / view.k}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(n.label, n.x, n.y + r + 12 / view.k);
    }
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}

/* ---- picking & interaction ---- */
const toWorld = e => {
  const r = cv.getBoundingClientRect();
  return {x: (e.clientX - r.left - view.x) / view.k, y: (e.clientY - r.top - view.y) / view.k};
};
function pick(e) {
  const p = toWorld(e);
  let best = null, bd = Infinity;
  for (const n of nodes) {
    if (!inFocus(n) || !matches(n)) continue;
    const d = Math.hypot(n.x - p.x, n.y - p.y), r = radius(n) + 6;
    if (d < r && d < bd) { bd = d; best = n; }
  }
  return best;
}
cv.addEventListener('mousedown', e => {
  const n = pick(e);
  if (n) { dragging = n; n.pinned = true; alpha = Math.max(alpha, 0.35); }
  else panning = {x: e.clientX - view.x, y: e.clientY - view.y};
});
addEventListener('mousemove', e => {
  if (dragging) { const p = toWorld(e); dragging.x = p.x; dragging.y = p.y; return; }
  if (panning) { view.x = e.clientX - panning.x; view.y = e.clientY - panning.y; return; }
  const n = pick(e);
  const id = n ? n.id : null;
  if (id !== hover) { hover = id; cv.style.cursor = n ? 'pointer' : 'grab'; }
});
addEventListener('mouseup', e => {
  if (!dragging && !panning) return;
  if (dragging && Math.abs(e.movementX) < 2) { /* click-through handled below */ }
  dragging = null; panning = null;
});
cv.addEventListener('click', e => { const n = pick(e); select(n ? n.id : null); });
cv.addEventListener('dblclick', e => { const n = pick(e); if (n) { n.pinned = !n.pinned; alpha = 0.4; } });
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const k = Math.max(0.15, Math.min(4, view.k * (e.deltaY < 0 ? 1.12 : 0.89)));
  view.x = mx - (mx - view.x) * (k / view.k);
  view.y = my - (my - view.y) * (k / view.k);
  view.k = k;
}, {passive: false});

/* ---- detail panel ---- */
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const linkList = ids => ids.length
  ? '<ul>' + ids.map(i => `<li><a data-goto="${esc(i)}">${esc(i)}</a></li>`).join('') + '</ul>'
  : '<p class="empty">none</p>';

function select(id) {
  selected = id;
  const box = document.getElementById('detail');
  if (!id) { box.innerHTML = '<p class="empty">Click a node to inspect it.</p>'; return; }
  const n = index.get(id);
  const meta = [n.feature || 'orphan', n.kind];
  if (n.shared) meta.push('shared');
  if (n.entry) meta.push('entry point');
  box.innerHTML =
    `<h2>${esc(n.id)}</h2>` +
    `<div class="caveman">${esc(n.caveman)}</div>` +
    `<div>${meta.map(m => `<span class="chip">${esc(m)}</span>`).join('')}</div>` +
    (n.path ? `<h3>Source</h3><ul><li><a href="../${esc(n.path)}" target="_blank">open ${esc(n.path)}</a></li></ul>` : '') +
    `<h3>Uses (${n.uses.length})</h3>${linkList(n.uses)}` +
    `<h3>Used by (${n.used_by.length})</h3>${linkList(n.used_by)}`;
  box.querySelectorAll('[data-goto]').forEach(a =>
    a.addEventListener('click', () => { select(a.dataset.goto); centre(a.dataset.goto); }));
}
function centre(id) {
  const n = index.get(id);
  if (!n) return;
  view.x = cv.clientWidth / 2 - n.x * view.k;
  view.y = cv.clientHeight / 2 - n.y * view.k;
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-goto]');
  if (a && !a.closest('#detail')) { select(a.dataset.goto); centre(a.dataset.goto); }
});

/* ---- controls ---- */
document.getElementById('counts').textContent =
  `${nodes.length} files · ${DATA.features.length} features · ${links.length} edges`
  + (DATA.meta.updated ? ` · updated ${DATA.meta.updated}` : '');
const sel = document.getElementById('focus');
DATA.features.forEach(f => {
  const o = document.createElement('option');
  o.value = f.name; o.textContent = `${f.name} (${f.count})`;
  sel.appendChild(o);
});
sel.addEventListener('change', () => { focusFeature = sel.value; });
document.getElementById('search').addEventListener('input', e => { query = e.target.value.trim().toLowerCase(); });
document.getElementById('colorByFeature').addEventListener('change', e => {
  colorByFeature = e.target.checked; paintLegend();
});
document.getElementById('labelsAlways').addEventListener('change', e => { labelsAlways = e.target.checked; });
document.getElementById('fit').addEventListener('click', fit);
document.getElementById('reheat').addEventListener('click', () => {
  nodes.forEach(n => n.pinned = false); alpha = 1; settleFit = true;
});
document.getElementById('theme').addEventListener('click', () => {
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  const cur = document.documentElement.dataset.theme || (dark ? 'dark' : 'light');
  document.documentElement.dataset.theme = cur === 'dark' ? 'light' : 'dark';
});

const legend = document.getElementById('legend');
DATA.features.forEach(f => {
  const b = document.createElement('button');
  b.className = 'chip'; b.dataset.feature = f.name;
  b.innerHTML = `<span class="dot"></span>${esc(f.name)} <span style="color:var(--muted)">${f.count}</span>`;
  b.addEventListener('click', () => {
    focusFeature = focusFeature === f.name ? '' : f.name;
    sel.value = focusFeature;
    [...legend.children].forEach(c => c.classList.toggle('off', !!focusFeature && c !== b));
  });
  legend.appendChild(b);
});
/* The swatch must show the colour actually on screen — with "colour by feature"
   off every node is one accent hue, so a colourful legend would be a lie. */
function paintLegend() {
  [...legend.children].forEach(c => {
    c.querySelector('.dot').style.background =
      colorByFeature ? featureColor(c.dataset.feature) : css('--accent');
  });
}
paintLegend();
new MutationObserver(paintLegend).observe(document.documentElement, {attributeFilter: ['data-theme']});

addEventListener('keydown', e => {
  if (e.key === 'Escape') { select(null); focusFeature = ''; sel.value = ''; }
  if (e.key === '/' && document.activeElement.id !== 'search') {
    e.preventDefault(); document.getElementById('search').focus();
  }
});

resize(); tick();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------------ main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("build", "check", "find"), nargs="?", default="build")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    graph = load(root)

    problems = validate(graph)
    if problems:
        print(f"{len(problems)} problem(s) in .tidy/graph.json:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if args.command == "check":
            raise SystemExit(1)
        print("  (building anyway — fix these and re-run)\n", file=sys.stderr)
    elif args.command == "check":
        print("graph.json OK")
        return

    model = derive(graph)

    if args.command == "find":
        path, candidates = write_candidates(model, root)
        symbols = sum(len(n.get("symbols") or []) for n in model["nodes"])
        print(f"{len(candidates)} candidate(s) from {symbols} symbols "
              f"across {len(model['nodes'])} nodes")
        for prefix in ("DUP", "REUSE", "MOVE", "DEAD", "GOD"):
            hits = sum(1 for c in candidates if c["id"].startswith(prefix))
            if hits:
                print(f"  {prefix:<5} {hits}")
        if not symbols:
            print("  note: no symbols recorded — DUP/REUSE need nodes[].symbols", file=sys.stderr)
        print(f"  wrote {os.path.relpath(path, root)} — triage into .tidy/findings.md")
        return

    written = write_markdown(model, root)
    written.append(write_html(model, root))

    shared = sum(1 for n in model["nodes"] if n["shared"])
    print(f"{len(model['nodes'])} files · {len(model['features'])} features · "
          f"{len(model['edges'])} edges · {shared} shared · {len(model['orphans'])} orphans")
    for path in written:
        print(f"  wrote {os.path.relpath(path, root)}")


if __name__ == "__main__":
    main()

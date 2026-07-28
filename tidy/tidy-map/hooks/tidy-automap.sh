#!/bin/sh
#
# tidy-automap.sh — run /tidy-map in the background after every commit.
#
# Unlike tidy-stale.sh (which only marks what changed), this actually
# refreshes the graph by shelling out to a headless `claude -p` call. It is
# launched detached so it never blocks the commit — the commit returns
# immediately and the graph updates a few seconds/minutes later, in the
# background. Requires the `claude` CLI on PATH and already authenticated
# for non-interactive use; silently no-ops otherwise.
#
# Only runs against a repo that has already been tidied once (.tidy/ exists)
# — first-run mapping stays a deliberate, interactive /tidy-map.
#
# Always exits 0 — this must never block a commit.
#
set -u

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$REPO_ROOT" || exit 0

TIDY_DIR="$REPO_ROOT/.tidy"
[ -d "$TIDY_DIR" ] || exit 0

command -v claude >/dev/null 2>&1 || exit 0

mkdir -p "$TIDY_DIR/hooks"
LOG="$TIDY_DIR/hooks/automap.log"

nohup claude -p "/tidy-map" \
  --permission-mode acceptEdits \
  --allowedTools "Read Write Bash Glob Grep" \
  --no-session-persistence \
  >>"$LOG" 2>&1 &

exit 0

#!/bin/sh
#
# tidy-stale.sh — mark the tidy graph stale.
#
# Fast, dependency-free, no LLM. Appends changed repo-relative paths to
# .tidy/stale.txt so the next /tidy can do an incremental update instead of a
# full rescan. Safe to run from a git post-commit hook, from a harness
# stop/post-turn hook, or by hand.
#
# Sources of "what changed", in order:
#   1. Files in the most recent commit (if run right after a commit).
#   2. Uncommitted changes in the working tree (staged + unstaged + untracked).
#
# Always exits 0 — this must never block a commit or an agent turn.
#
set -u

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$REPO_ROOT" || exit 0

TIDY_DIR="$REPO_ROOT/.tidy"
# Only track a repo that has actually been tidied. Nothing to mark stale otherwise.
[ -d "$TIDY_DIR" ] || exit 0

STALE="$TIDY_DIR/stale.txt"
TMP="$STALE.tmp.$$"

{
  [ -f "$STALE" ] && cat "$STALE"

  # Files touched by the latest commit.
  git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null

  # Anything still dirty in the working tree, plus untracked files.
  git diff --name-only HEAD 2>/dev/null
  git ls-files --others --exclude-standard 2>/dev/null
} 2>/dev/null \
  | grep -v '^\.tidy/' \
  | grep -v '^$' \
  | sort -u > "$TMP" 2>/dev/null

if [ -s "$TMP" ]; then
  mv "$TMP" "$STALE" 2>/dev/null || rm -f "$TMP"
else
  rm -f "$TMP"
fi

exit 0

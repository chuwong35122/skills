#!/bin/sh
#
# install.sh — install the tidy / tidy-map / tidy-find sibling skills, and/or
# wire tidy-map's post-commit hook into a target repo.
#
# Usage:
#   install.sh [--user|--project] [--link|--copy] [--no-hook]
#   install.sh --hook                 # only wire the hook into the current repo
#
#   --user     install into this machine's per-user skill dirs (default)
#   --project  install into the current repo's .claude/skills (and friends)
#   --link     symlink skills into place (default)
#   --copy     copy skills into place instead of symlinking
#   --no-hook  skip the git post-commit hook step
#   --hook     do ONLY the hook step (implies no skill install)
#
# Only tidy-map is ever wired into a git hook. /tidy-find and /tidy edit or
# opine on source and must stay invocation-only — never install them as hooks.
# The hook scripts therefore live in tidy-map/hooks/, not tidy/hooks/.
#
# Skills are installed to a shared per-user hub, $HOME/.agents/skills/<name>,
# then each harness's own skills directory gets a symlink to that hub entry
# (this is how a skill installed once is visible to Claude Code, Codex,
# Gemini CLI, Cursor, ... without N copies). --copy still uses the hub as the
# canonical copy; harness dirs always symlink to it.
#
# Lives at the container level, next to all three skill directories:
#   tidy/install.sh, tidy/tidy/, tidy/tidy-map/, tidy/tidy-find/
#
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
TIDY_DIR="$SCRIPT_DIR/tidy"
TIDY_MAP_DIR="$SCRIPT_DIR/tidy-map"
TIDY_FIND_DIR="$SCRIPT_DIR/tidy-find"

SCOPE=user
METHOD=link
DO_SKILLS=true
DO_HOOK=true

for arg in "$@"; do
  case "$arg" in
    --user) SCOPE=user ;;
    --project) SCOPE=project ;;
    --link) METHOD=link ;;
    --copy) METHOD=copy ;;
    --no-hook) DO_HOOK=false ;;
    --hook) DO_SKILLS=false; DO_HOOK=true ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "install.sh: unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

install_skill() {
  # $1 = skill name, $2 = source directory
  name="$1"
  src="$2"
  [ -f "$src/SKILL.md" ] || { echo "install.sh: $src has no SKILL.md, skipping" >&2; return 1; }
  src=$(cd "$src" && pwd)

  hub_dir="$HOME/.agents/skills"
  mkdir -p "$hub_dir"
  hub_dest="$hub_dir/$name"
  rm -rf "$hub_dest"
  if [ "$METHOD" = "link" ]; then
    ln -s "$src" "$hub_dest"
  else
    cp -R "$src" "$hub_dest"
  fi

  if [ "$SCOPE" = "user" ]; then
    for harness_root in "$HOME/.claude" "$HOME/.codex" "$HOME/.gemini" "$HOME/.cursor"; do
      [ -d "$harness_root" ] || continue
      dir="$harness_root/skills"
      mkdir -p "$dir"
      dest="$dir/$name"
      rm -rf "$dest"
      ln -s "$hub_dest" "$dest"
      echo "installed $name -> $dest"
    done
  else
    dir=".claude/skills"
    mkdir -p "$dir"
    dest="$dir/$name"
    rm -rf "$dest"
    ln -s "$hub_dest" "$dest"
    echo "installed $name -> $dest"
  fi
}

install_hook() {
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "install.sh: --hook must be run from inside a git repo" >&2
    exit 1
  }

  # tidy-map owns the only hooked phase; its scripts live in tidy-map/hooks/.
  hooks_dest="$repo_root/.tidy/hooks"
  mkdir -p "$hooks_dest"
  cp "$TIDY_MAP_DIR/hooks/tidy-stale.sh" "$hooks_dest/tidy-stale.sh"
  cp "$TIDY_MAP_DIR/hooks/tidy-automap.sh" "$hooks_dest/tidy-automap.sh"
  chmod +x "$hooks_dest/tidy-stale.sh" "$hooks_dest/tidy-automap.sh"

  git_hook="$repo_root/.git/hooks/post-commit"
  marker="# tidy-map: mark graph stale + background remap"
  # Older installs used an unprefixed marker — treat either as already wired.
  if [ -f "$git_hook" ] && grep -qE '^# tidy(-map)?: mark graph stale \+ background remap$' "$git_hook"; then
    echo "install.sh: post-commit hook already wired, leaving it"
  else
    [ -f "$git_hook" ] || printf '#!/bin/sh\n' > "$git_hook"
    {
      echo ""
      echo "$marker"
      echo '.tidy/hooks/tidy-stale.sh'
      echo '.tidy/hooks/tidy-automap.sh'
    } >> "$git_hook"
    chmod +x "$git_hook"
    echo "installed git post-commit hook -> $git_hook"
  fi

  cat <<'EOF'

Optional: also run tidy-stale.sh on your harness's stop/post-turn hook, so
uncommitted work is tracked too. Claude Code, in .claude/settings.json:

{ "hooks": { "Stop": [ { "hooks": [{ "type": "command", "command": ".tidy/hooks/tidy-stale.sh" }] } ] } }
EOF
}

if [ "$DO_SKILLS" = "true" ]; then
  install_skill tidy "$TIDY_DIR"
  install_skill tidy-map "$TIDY_MAP_DIR"
  install_skill tidy-find "$TIDY_FIND_DIR"
fi

if [ "$DO_HOOK" = "true" ]; then
  install_hook
fi

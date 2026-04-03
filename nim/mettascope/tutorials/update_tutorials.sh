#!/usr/bin/env bash
# Regenerate tutorial docs from prompts using claude-code.
# Run from anywhere — the script resolves paths relative to the repo root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
PROMPTS_DIR="$SCRIPT_DIR/prompts"

cd "$REPO_ROOT"

echo "=== Generating: Playing CoGames tutorial ==="
claude --dangerously-skip-permissions -p "$(cat "$PROMPTS_DIR/playing_cogames_prompt.md")"

echo ""
echo "=== Generating: Simulation guide ==="
claude --dangerously-skip-permissions -p "$(cat "$PROMPTS_DIR/simulation_guide_prompt.md")"

echo ""
echo "=== Done. Check tutorials/docs/ for output. ==="

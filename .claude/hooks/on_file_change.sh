#!/bin/sh
file=$(jq -r '.tool_input.file_path // empty')
if [ -z "$file" ]; then
  exit 0
fi
case "$file" in
  *.py)
    cd "$CLAUDE_PROJECT_DIR"
    uv run ruff check --fix "$file"
    uv run ruff format "$file"
    ;;
esac

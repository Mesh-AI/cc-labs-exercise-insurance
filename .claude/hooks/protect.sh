#!/bin/sh
# PreToolUse hook: block edits to paths that must never change.
path=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
case "$path" in
  */server/legacy/*|server/legacy/*|*/tests/backend/test_characterisation_*|tests/backend/test_characterisation_*|*/server/data/legacy/RATTBL.csv|server/data/legacy/RATTBL.csv)
    echo "Blocked: $path is protected (see CLAUDE.md)." >&2
    exit 2 ;;
esac
exit 0

#!/usr/bin/env bash
# The task queue's labels (docs/dev/automation.md); idempotent: creates or
# updates each. The same names are ops/repo/gh.py's LABELS.
set -euo pipefail
cd "$(dirname "$0")/../.."
label() { gh label create "$1" --color "$2" --description "$3" --force; }
label regression  d73a4a "Found by the nightly evidence run (ops/repo/status.py)"
label redteam     b60205 "Found by the weekly correctness review"
label hygiene     0e8a16 "Found by the weekly hygiene review"
label agent-ok    1d76db "Safe for an unattended agent (the fixer takes the oldest)"
label needs-owner fbca04 "A product decision or a weakening: the owner decides"
label in-progress c5def5 "Taken by a fixer run"

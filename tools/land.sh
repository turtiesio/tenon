#!/usr/bin/env bash
# The landing path (budget: 5 min): commit local changes, rebase onto
# origin/main, pass ./check --fast, push. Nothing reaches main unless the
# check passes on exactly what is pushed. Usage: tools/land.sh "message" [NEW_PATH...]
# Commits changes to tracked files, plus the new files or directories listed;
# other untracked files (another agent's drafts) are left alone.
set -euo pipefail
cd "$(dirname "$0")/.."
msg=${1:?usage: tools/land.sh MESSAGE [NEW_PATH...]}; shift
start=$(date +%s)
git add -u
[ $# -gt 0 ] && git add -- "$@"
if ! git diff --cached --quiet; then
  git commit -q -m "$msg" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
fi
for attempt in 1 2 3; do
  git fetch -q origin main
  git rebase -q --autostash origin/main
  if ! python3 tools/approvals.py origin/main; then
    echo "land: unapproved weakening of a guarded test; nothing pushed (governance/README.md)"
    exit 1
  fi
  if ! ./check --fast > .check.log 2>&1; then
    tail -20 .check.log
    echo "land: check failed; nothing pushed (fix, then rerun)"
    exit 1
  fi
  if git push -q origin HEAD:main; then
    echo "land: pushed $(git rev-parse --short HEAD) in $(( $(date +%s) - start ))s (attempt $attempt)"
    exit 0
  fi
  echo "land: main moved; retrying"
done
echo "land: could not push after 3 attempts"
exit 1

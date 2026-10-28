#!/usr/bin/env bash
# The landing path (budget: 5 min): commit local changes, rebase onto
# origin/main, pass ./check --fast, push. Nothing reaches main unless the
# check passes on exactly what is pushed. Usage: ops/repo/land.sh "message" [NEW_PATH...]
# Commits changes to tracked files, plus the new files or directories listed;
# other untracked files (another agent's drafts) are left alone.
set -euo pipefail
cd "$(dirname "$0")/../.."
msg=${1:?usage: ops/repo/land.sh MESSAGE [NEW_PATH...]}; shift
start=$(date +%s)
git add -u
[ $# -gt 0 ] && git add -- "$@"
if ! git diff --cached --quiet; then
  git commit -q -m "$msg"
fi
# Owner rule (docs/log.md): no AI co-author trailers, ever (also enforced in CI).
if git log origin/main..HEAD --format=%B | grep -qiE '^co-authored-by:.*(claude|anthropic|openai|codex|gpt)'; then
  echo "land: a commit carries an AI Co-Authored-By trailer; remove it (git commit --amend)"
  exit 1
fi
for attempt in 1 2 3; do
  git fetch -q origin main
  git rebase -q --autostash origin/main
  if ! python3 ops/repo/approvals.py origin/main; then
    echo "land: unapproved weakening of a guarded test; nothing pushed (ops/governance/README.md)"
    exit 1
  fi
  mkdir -p target
  if ! ./check --fast > target/check.log 2>&1; then
    tail -20 target/check.log
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

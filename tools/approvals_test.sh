#!/usr/bin/env bash
# The approvals checker must refuse real weakenings (governance/README.md).
set -u
cd "$(dirname "$0")/.."
src=$PWD
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone -q "$src" "$tmp/r" && cd "$tmp/r"
git config user.email t@t && git config user.name t
mkdir -p governance tools && cp "$src/tools/approvals.py" tools/ && cp "$src/governance/"* governance/
git add -A && git commit -qm base --allow-empty
base=$(git rev-parse HEAD)
fail=0
expect() { # expect OK|REFUSE description
  if python3 tools/approvals.py "$base" > out.txt; then got=OK; else got=REFUSE; fi
  if [ "$got" != "$1" ]; then echo "approvals_test: FAIL: $2 (got $got)"; cat out.txt; fail=1; fi
  git reset -q --hard "$base"
}
victim=$(ls tests/reject/*.tn | head -1)
git rm -q "$victim" && git commit -qm "drop a reject test"
expect REFUSE "deleting a guarded reject test without approval"
sed -i.bak '1s/.*/\/\/ error: something weaker/' "$victim" && rm -f "$victim.bak" && git commit -qam "weaken expected error"
expect REFUSE "changing a guarded test's expected diagnostic"
git rm -q "$victim" && echo "2026-10-28 | tester | $victim | rule intentionally removed" >> governance/approvals.log && git add -A && git commit -qm "approved removal"
expect OK "deleting a guarded test with an approval line"
sed -i.bak '1s/.*/# rewritten history/' governance/approvals.log && rm -f governance/approvals.log.bak && git commit -qam "rewrite log"
expect REFUSE "rewriting the approvals log"
echo "// a comment" >> "$victim" && git commit -qam "harmless edit below the expectation"
expect OK "editing a guarded test without changing what it expects"
[ $fail = 0 ] && echo "approvals_test: refuses unapproved weakening (5 scenarios)"
exit $fail

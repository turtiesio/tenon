#!/usr/bin/env bash
# The approvals checker must refuse real weakenings (governance/README.md).
set -u
cd "$(dirname "$0")/.."
src=$PWD
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
# a fixture repository with what the scenarios touch: the checker, the
# governance files, one guarded test and one file of the frozen seed
victim=tests/reject/$(ls "$src/tests/reject" | grep '\.tn$' | head -1)
seed=bootstrap/src/diag.rs
mkdir -p "$tmp/r" && cd "$tmp/r" && git init -q
git config user.email t@t && git config user.name t
for f in tools/approvals.py $(cd "$src" && echo governance/*) "$victim" "$seed"; do mkdir -p "$(dirname "$f")"; cp "$src/$f" "$f"; done
git add -A && git commit -qm base
base=$(git rev-parse HEAD)
fail=0
expect() { # expect OK|REFUSE description [--pr]
  if python3 tools/approvals.py ${3:-} "$base" > "$tmp/out.txt"; then got=OK; else got=REFUSE; fi
  if [ "$got" != "$1" ]; then echo "approvals_test: FAIL: $2 (got $got)"; cat "$tmp/out.txt"; fail=1; fi
  git reset -q --hard "$base"
}
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
# the frozen bootstrap: any change needs an approval, and it may only shrink
sed -i.bak 's/Diagnostics/Diagnostic notes/' "$seed" && rm -f "$seed.bak" && git commit -qam "edit the seed"
expect REFUSE "changing a frozen bootstrap file without approval"
echo "// new" > bootstrap/src/extra.rs && git add bootstrap/src/extra.rs && git commit -qm "add to the seed"
expect REFUSE "adding a file under the frozen bootstrap without approval"
sed -i.bak '$d' "$seed" && rm -f "$seed.bak" && echo "2026-10-28 | tester | $seed | drop a line" >> governance/approvals.log && git commit -qam "approved shrink"
expect OK "shrinking a frozen file with an approval line"
echo "// one more line" >> "$seed" && echo "2026-10-28 | tester | bootstrap/* | grow the seed" >> governance/approvals.log && git commit -qam "approved growth"
expect REFUSE "growing the frozen bootstrap's line count, even with an approval"
git rm -q "$seed" && echo "2026-10-28 | tester | bootstrap/* | remove a file" >> governance/approvals.log && git add -A && git commit -qm "approved removal"
expect OK "removing a frozen file with an approval covering it"
# an unattended pull request (--pr, CI): approvals only from the owner, rules only added
git rm -q "$victim" && echo "2026-10-28 | agent | $victim | looks redundant" >> governance/approvals.log && git add -A && git commit -qm "self-approved removal"
expect REFUSE "a pull request that adds its own approval line" --pr
sed -i.bak '/^tests\/reject/d' governance/guarded.txt && rm -f governance/guarded.txt.bak && git rm -q "$victim" && git commit -qam "unguard, then delete"
expect REFUSE "a pull request that removes a rule from guarded.txt" --pr
echo "more" >> governance/README.md && git commit -qam "edit an owner path"
expect REFUSE "a pull request that changes a path under an owner rule" --pr
echo "// x" > tests/new_guard.tn && echo "tests/new_guard.tn" >> governance/guarded.txt && git add -A && git commit -qm "guard a new regression test"
expect OK "a pull request that adds a guarded regression test" --pr
[ $fail = 0 ] && echo "approvals_test: refuses unapproved weakening, unapproved or growing changes to the frozen bootstrap, and self-approval in pull requests (14 scenarios)"
exit $fail

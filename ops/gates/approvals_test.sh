#!/usr/bin/env bash
# The approvals checker must refuse real weakenings (ops/governance/README.md).
set -u
cd "$(dirname "$0")/../.."
src=$PWD
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
# a fixture repository with what the scenarios touch: the checker, the
# governance files, one guarded test and one file of the frozen seed
victim=tests/reject/$(ls "$src/tests/reject" | grep '\.tn$' | head -1)
seed=seed/src/diag.rs
mkdir -p "$tmp/r" && cd "$tmp/r" && git init -q
git config user.email t@t && git config user.name t
for f in ops/repo/approvals.py $(cd "$src" && echo ops/governance/*) "$victim" "$seed"; do mkdir -p "$(dirname "$f")"; cp "$src/$f" "$f"; done
git add -A && git commit -qm base
base=$(git rev-parse HEAD)
fail=0
expect() { # expect OK|REFUSE description [--pr]
  if python3 ops/repo/approvals.py ${3:-} "$base" > "$tmp/out.txt"; then got=OK; else got=REFUSE; fi
  if [ "$got" != "$1" ]; then echo "approvals_test: FAIL: $2 (got $got)"; cat "$tmp/out.txt"; fail=1; fi
  git reset -q --hard "$base"
}
git rm -q "$victim" && git commit -qm "drop a reject test"
expect REFUSE "deleting a guarded reject test without approval"
sed -i.bak '1s/.*/\/\/ error: something weaker/' "$victim" && rm -f "$victim.bak" && git commit -qam "weaken expected error"
expect REFUSE "changing a guarded test's expected diagnostic"
git rm -q "$victim" && echo "2026-10-28 | tester | $victim | rule intentionally removed" >> ops/governance/approvals.log && git add -A && git commit -qm "approved removal"
expect OK "deleting a guarded test with an approval line"
sed -i.bak '1s/.*/# rewritten history/' ops/governance/approvals.log && rm -f ops/governance/approvals.log.bak && git commit -qam "rewrite log"
expect REFUSE "rewriting the approvals log"
echo "// a comment" >> "$victim" && git commit -qam "harmless edit below the expectation"
expect OK "editing a guarded test without changing what it expects"
# the frozen seed: any change needs an approval, and it may only shrink
sed -i.bak 's/Diagnostics/Diagnostic notes/' "$seed" && rm -f "$seed.bak" && git commit -qam "edit the seed"
expect REFUSE "changing a frozen seed file without approval"
echo "// new" > seed/src/extra.rs && git add seed/src/extra.rs && git commit -qm "add to the seed"
expect REFUSE "adding a file under the frozen seed without approval"
sed -i.bak '$d' "$seed" && rm -f "$seed.bak" && echo "2026-10-28 | tester | $seed | drop a line" >> ops/governance/approvals.log && git commit -qam "approved shrink"
expect OK "shrinking a frozen file with an approval line"
echo "// one more line" >> "$seed" && echo "2026-10-28 | tester | seed/* | grow the seed" >> ops/governance/approvals.log && git commit -qam "approved growth"
expect REFUSE "growing the frozen seed's line count, even with an approval"
git rm -q "$seed" && echo "2026-10-28 | tester | seed/* | remove a file" >> ops/governance/approvals.log && git add -A && git commit -qm "approved removal"
expect OK "removing a frozen file with an approval covering it"
# renames: the base's rules and HEAD's both apply; identical content moved to a guarded path is no weakening
git mv "$victim" tests/reject/renamed.tn && git commit -qm "rename a guarded test"
expect OK "renaming a guarded test, content unchanged, to a path still guarded"
mkdir -p tests/moved && git mv "$victim" tests/moved/x.tn && git commit -qm "move a guarded test out of the guard"
expect REFUSE "moving a guarded test to a path no rule guards"
moved() { # moved APPROVED_GLOB...: rename the seed to seed2/ and its rule with it, approving each glob
  git mv seed seed2 && sed -i.bak 's|^frozen seed/\*|frozen seed2/*|' ops/governance/guarded.txt && rm -f ops/governance/guarded.txt.bak
  for g in "$@"; do echo "2026-10-28 | tester | $g | rename the seed" >> ops/governance/approvals.log; done
}
moved 'seed/*' 'seed2/*' && git commit -qam "approved rename of the seed"
expect OK "renaming the frozen seed and its rule, both paths approved"
moved 'seed2/*' && git commit -qam "rename approved only where it lands"
expect REFUSE "renaming the frozen seed with the old paths unapproved"
moved 'seed/*' 'seed2/*' && echo "// one more line" >> "seed2/src/diag.rs" && git commit -qam "rename and grow"
expect REFUSE "renaming the frozen seed and growing it"
# an unattended pull request (--pr, CI): approvals only from the owner, rules only added
git rm -q "$victim" && echo "2026-10-28 | agent | $victim | looks redundant" >> ops/governance/approvals.log && git add -A && git commit -qm "self-approved removal"
expect REFUSE "a pull request that adds its own approval line" --pr
sed -i.bak '/^tests\/reject/d' ops/governance/guarded.txt && rm -f ops/governance/guarded.txt.bak && git rm -q "$victim" && git commit -qam "unguard, then delete"
expect REFUSE "a pull request that removes a rule from guarded.txt" --pr
echo "more" >> ops/governance/README.md && git commit -qam "edit an owner path"
expect REFUSE "a pull request that changes a path under an owner rule" --pr
echo "// x" > tests/new_guard.tn && echo "tests/new_guard.tn" >> ops/governance/guarded.txt && git add -A && git commit -qm "guard a new regression test"
expect OK "a pull request that adds a guarded regression test" --pr
[ $fail = 0 ] && echo "approvals_test: refuses unapproved weakening, unapproved or growing changes to the frozen seed (renames included), and self-approval in pull requests (19 scenarios)"
exit $fail

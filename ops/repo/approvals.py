#!/usr/bin/env python3
"""Refuse unapproved weakening of guarantee-bearing tests, and any unapproved
change to a frozen path (ops/governance/README.md).

    ops/repo/approvals.py BASE       compare the working tree's HEAD with BASE
    ops/repo/approvals.py --pr BASE  the same for an unattended pull request

Exit 0 if every deleted or weakened guarded file has an approval line added in
this change, every changed file under a frozen path (`frozen GLOB` lines of
ops/governance/guarded.txt: the bootstrap seed) has one too, the frozen paths did
not grow in line count, and the approvals log only grew; otherwise print why
and exit 1. The rules are the base's and HEAD's together: a rule the change
removes or rewrites still applies to it (renaming the seed deletes files the
base freezes and adds files HEAD freezes, so both need the approval and the
line count is compared across the rename). A guarded file deleted while the
same content is added at a path HEAD guards is a rename, not a weakening.

With --pr (CI on pull requests, docs/dev/automation.md) approvals come only
from the owner, so the change may not touch the approvals log at all, may
only add lines to ops/governance/guarded.txt, and may not change a path under an
`owner GLOB` line (the gate, this checker, CI): such a change needs the owner.
"""
import fnmatch, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = "ops/governance/approvals.log"
GUARDED = "ops/governance/guarded.txt"
# where they were before the layout of 2026-10-28 (docs/log.md), for a base that old
BEFORE = {LOG: "governance/approvals.log", GUARDED: "governance/guarded.txt"}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def at_base(base, path):
    text = show(base, path)
    return text if text is not None else show(base, BEFORE[path])


def expected(text):
    """The part of a guarded file that states what must happen."""
    if text is None:
        return None
    first = text.splitlines()[0] if text else ""
    return first if first.startswith("// error:") else text


def frozen_growth(base, paths):
    """Lines added minus lines removed in the changed frozen files (one git call)."""
    if not paths:
        return 0
    grew = 0
    for row in git("diff", "--numstat", "--no-renames", base, "HEAD", "--", *paths).splitlines():
        added, removed = row.split("\t")[:2]
        if added != "-":
            grew += int(added) - int(removed)
    return grew


def rules_of(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip() and not l.startswith("#")]


def main():
    args = sys.argv[1:]
    pr = "--pr" in args
    args = [a for a in args if a != "--pr"]
    base = args[0] if args else "origin/main"
    head_rules = rules_of(show("HEAD", GUARDED))
    base_rules = rules_of(at_base(base, GUARDED))
    rules = head_rules + [r for r in base_rules if r not in head_rules]
    head_globs = [r for r in head_rules if not r.startswith(("frozen ", "owner "))]
    frozen = [r[len("frozen "):].strip() for r in rules if r.startswith("frozen ")]
    owner = [r[len("owner "):].strip() for r in rules if r.startswith("owner ")]
    globs = [r for r in rules if not r.startswith(("frozen ", "owner "))]
    problems = []
    old_log = at_base(base, LOG) or ""
    new_log = show("HEAD", LOG) or ""
    if pr:
        dropped = [r for r in base_rules if r not in head_rules]
        problems += [f"{GUARDED}: rule {r!r} removed; an unattended change may only add rules" for r in dropped]
        if new_log != old_log:
            problems.append(f"{LOG}: changed; approvals are added by the owner, not in a pull request")
    if not new_log.startswith(old_log):
        problems.append(f"{LOG}: existing lines were changed or removed (the log is append-only)")
    added = new_log[len(old_log):] if new_log.startswith(old_log) else ""
    approved = set()
    for line in added.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[1] and parts[3]:
            approved.add(parts[2])
        elif line.strip():
            problems.append(f"{LOG}: malformed approval line: {line!r} (want DATE | APPROVER | PATH | reason)")
    # `:MODE MODE OLD_BLOB NEW_BLOB STATUS<tab>PATH` per changed file
    changed = []
    for row in git("diff", "--raw", "--no-renames", "--no-abbrev", base, "HEAD").splitlines():
        meta, path = row.split("\t", 1)
        _, _, old_blob, new_blob, status = meta.split(" ")[:5]
        changed.append((status, path, old_blob, new_blob))
    added_as = {}  # blob -> the paths this change adds with exactly that content
    for status, path, _, new_blob in changed:
        if status == "A":
            added_as.setdefault(new_blob, []).append(path)
    frozen_changed = []
    for status, path, old_blob, _ in changed:
        if pr and any(fnmatch.fnmatch(path, g) for g in owner):
            problems.append(f"{path}: changes need the owner (`owner` in {GUARDED}); not in a pull request")
        if any(fnmatch.fnmatch(path, g) for g in frozen):
            frozen_changed.append(path)
            # a frozen path: any change at all (added, changed or deleted) needs
            # an approval naming the file, or a glob that covers it
            if not any(path == a or fnmatch.fnmatch(path, a) for a in approved):
                problems.append(f"{path}: frozen (ops/governance/guarded.txt); any change needs an approval line in {LOG}")
            continue
        if not any(fnmatch.fnmatch(path, g) for g in globs):
            continue
        if status == "A":
            continue
        before, after = show(base, path), show("HEAD", path)
        weakened = after is None or expected(before) != expected(after)
        if after is None and any(fnmatch.fnmatch(p, g) for p in added_as.get(old_blob, []) for g in head_globs):
            weakened = False  # renamed, unchanged, and still guarded
        if weakened and path not in approved:
            what = "deleted" if after is None else "changed what it expects"
            problems.append(f"{path}: guarded test {what}; add an approval line to {LOG}")
    grew = frozen_growth(base, frozen_changed)
    if grew > 0:
        problems.append(f"frozen paths grew by {grew} lines; their line count may only shrink (an approval does not lift this)")
    for p in problems:
        print("approvals:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

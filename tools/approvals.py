#!/usr/bin/env python3
"""Refuse unapproved weakening of guarantee-bearing tests (governance/README.md).

    tools/approvals.py BASE       compare the working tree's HEAD with BASE

Exit 0 if every deleted or weakened guarded file has an approval line added in
this change, and the approvals log only grew; otherwise print why and exit 1.
"""
import fnmatch, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = "governance/approvals.log"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def expected(text):
    """The part of a guarded file that states what must happen."""
    if text is None:
        return None
    first = text.splitlines()[0] if text else ""
    return first if first.startswith("// error:") else text


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    globs = [l.strip() for l in open(os.path.join(ROOT, "governance", "guarded.txt")) if l.strip() and not l.startswith("#")]
    problems = []
    old_log = show(base, LOG) or ""
    new_log = show("HEAD", LOG) or ""
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
    changed = git("diff", "--name-status", "--no-renames", base, "HEAD").splitlines()
    for row in changed:
        status, path = row.split("\t", 1)
        if not any(fnmatch.fnmatch(path, g) for g in globs):
            continue
        if status == "A":
            continue
        before, after = show(base, path), show("HEAD", path)
        weakened = after is None or expected(before) != expected(after)
        if weakened and path not in approved:
            what = "deleted" if after is None else "changed what it expects"
            problems.append(f"{path}: guarded test {what}; add an approval line to {LOG}")
    for p in problems:
        print("approvals:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

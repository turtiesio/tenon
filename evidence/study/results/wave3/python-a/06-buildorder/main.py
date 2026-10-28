import heapq
import re
import sys

NAME = re.compile(r"[A-Za-z0-9_./-]+")


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


def parse_args(argv):
    levels = False
    targets = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-l":
            levels = True
        elif arg == "-t":
            if i + 1 >= len(argv):
                raise UsageError("-t needs a name")
            targets.append(argv[i + 1])
            i += 1
        else:
            raise UsageError(f"unexpected argument {arg!r}")
        i += 1
    return levels, targets


def parse_rules(text):
    """Return {item: set of dependencies} for every item that appears."""
    deps = {}
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    for number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        target_part, colon, dep_part = line.partition(":")
        if not colon:
            raise InputError(f"line {number}: missing ':'")
        target = target_part.strip(" ")
        if not NAME.fullmatch(target):
            raise InputError(f"line {number}: bad target {target!r}")
        names = dep_part.split(" ")
        names = [n for n in names if n]
        for name in names:
            if not NAME.fullmatch(name):
                raise InputError(f"line {number}: bad dependency {name!r}")
        deps.setdefault(target, set()).update(names)
        for name in names:
            deps.setdefault(name, set())
    return deps


def select(deps, targets):
    if not targets:
        return set(deps)
    for t in targets:
        if t not in deps:
            raise InputError(f"unknown target {t!r}")
    selected = set()
    stack = list(targets)
    while stack:
        item = stack.pop()
        if item not in selected:
            selected.add(item)
            stack.extend(deps[item])
    return selected


def order(deps, selected):
    """Kahn's algorithm taking the smallest ready item each time.

    Returns (printed order, level of each printed item)."""
    waiting = {item: len(deps[item]) for item in selected}
    dependents = {item: [] for item in selected}
    for item in selected:
        for d in deps[item]:
            dependents[d].append(item)
    level = {}
    ready = [item for item, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    printed = []
    while ready:
        item = heapq.heappop(ready)
        printed.append(item)
        level[item] = 1 + max((level[d] for d in deps[item]), default=-1)
        for dependent in dependents[item]:
            waiting[dependent] -= 1
            if waiting[dependent] == 0:
                heapq.heappush(ready, dependent)
    return printed, level


def main():
    try:
        show_levels, targets = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"buildorder: {e}", file=sys.stderr)
        print("usage: buildorder [-l] [-t NAME]...", file=sys.stderr)
        return 2

    try:
        deps = parse_rules(sys.stdin.buffer.read().decode("latin-1"))
        selected = select(deps, targets)
    except InputError as e:
        print(f"buildorder: {e}", file=sys.stderr)
        return 3

    printed, level = order(deps, selected)
    if len(printed) < len(selected):
        stuck = sorted(selected.difference(printed))
        print("CYCLE " + " ".join(stuck))
        return 1

    if show_levels:
        by_level = {}
        for item in printed:
            by_level.setdefault(level[item], []).append(item)
        for n in sorted(by_level):
            print(f"{n}: {' '.join(sorted(by_level[n]))}")
    else:
        for item in printed:
            print(item)
    return 0


sys.exit(main())

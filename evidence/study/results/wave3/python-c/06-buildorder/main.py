"""buildorder: dependency ordering from a rules file."""
import heapq
import re
import sys
from collections import defaultdict

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
                raise UsageError("-t needs a NAME")
            targets.append(argv[i + 1])
            i += 1
        else:
            raise UsageError(f"unexpected argument {arg!r}")
        i += 1
    return levels, targets


def parse_rules(data):
    """Return a dict mapping every item to its set of dependencies."""
    deps = defaultdict(set)
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        stripped = line.strip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        target, colon, rest = line.partition(":")
        if not colon:
            raise InputError(f"line {number}: missing ':'")
        target = target.strip(" ")
        if not NAME.fullmatch(target):
            raise InputError(f"line {number}: invalid target {target!r}")
        names = [n for n in rest.split(" ") if n]
        for name in names:
            if not NAME.fullmatch(name):
                raise InputError(f"line {number}: invalid dependency {name!r}")
            deps[name]  # make sure every dependency is an item
        deps[target].update(names)
    return dict(deps)


def select(deps, targets):
    if not targets:
        return set(deps)
    for name in targets:
        if name not in deps:
            raise InputError(f"{name!r} is not an item")
    selected = set()
    stack = list(targets)
    while stack:
        name = stack.pop()
        if name not in selected:
            selected.add(name)
            stack.extend(deps[name])
    return selected


def build_order(deps, selected):
    """Kahn's algorithm, always taking the smallest ready name.

    Returns (order, unprinted)."""
    waiting = {name: len(deps[name]) for name in selected}
    dependents = defaultdict(list)
    for name in selected:
        for dep in deps[name]:
            dependents[dep].append(name)
    ready = [name for name, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for dependent in dependents[name]:
            waiting[dependent] -= 1
            if waiting[dependent] == 0:
                heapq.heappush(ready, dependent)
    unprinted = sorted(selected.difference(order))
    return order, unprinted


def level_lines(deps, order):
    level = {}
    for name in order:  # dependencies always come first
        level[name] = 1 + max((level[d] for d in deps[name]), default=-1)
    by_level = defaultdict(list)
    for name in sorted(order):
        by_level[level[name]].append(name)
    return [f"{k}: {' '.join(by_level[k])}" for k in range(len(by_level))]


def main():
    try:
        levels, targets = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"buildorder: {e}", file=sys.stderr)
        return 2
    try:
        deps = parse_rules(sys.stdin.buffer.read().decode("latin-1"))
        selected = select(deps, targets)
    except InputError as e:
        print(f"buildorder: {e}", file=sys.stderr)
        return 3
    order, unprinted = build_order(deps, selected)
    if unprinted:
        print("CYCLE " + " ".join(unprinted))
        return 1
    lines = level_lines(deps, order) if levels else order
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

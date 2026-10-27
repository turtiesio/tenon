import heapq
import re
import sys
from collections import defaultdict


def main():
    levels_output = False
    targets = []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-l':
                levels_output = True
            elif arg == '-t':
                targets.append(next(args))
            else:
                raise ValueError()
    except (ValueError, StopIteration):
        print('invalid arguments', file=sys.stderr)
        return 2
    graph = {}
    try:
        for raw in sys.stdin.buffer.read().split(b'\n'):
            line = raw.removesuffix(b'\r').decode('ascii')
            if not line.strip(' ') or line.lstrip(' ').startswith('#'):
                continue
            target, rest = line.split(':', 1)
            target = target.strip(' ')
            deps = [name for name in rest.split(' ') if name]
            if any(not re.fullmatch('[A-Za-z0-9_./-]+', name) for name in [target] + deps):
                raise ValueError('invalid name')
            graph.setdefault(target, set()).update(deps)
            for name in deps:
                graph.setdefault(name, set())
        if any(target not in graph for target in targets):
            raise ValueError('unknown target')
    except (ValueError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    selected = set()
    stack = targets or list(graph)
    while stack:
        name = stack.pop()
        if name not in selected:
            selected.add(name)
            stack.extend(graph[name])
    remaining = {name: len(graph[name]) for name in selected}
    dependents = defaultdict(list)
    for name in selected:
        for dep in graph[name]:
            dependents[dep].append(name)
    ready = [name for name, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    levels = {}
    while ready:
        name = heapq.heappop(ready)
        ordered.append(name)
        levels[name] = max((levels[dep] + 1 for dep in graph[name]), default=0)
        for child in dependents[name]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, child)
    if len(ordered) != len(selected):
        print('CYCLE ' + ' '.join(sorted(selected - set(ordered))))
        return 1
    if levels_output:
        groups = defaultdict(list)
        for name in sorted(selected):
            groups[levels[name]].append(name)
        for level in sorted(groups):
            print(f'{level}: {" ".join(groups[level])}')
    elif ordered:
        print('\n'.join(ordered))
    return 0


if __name__ == '__main__':
    sys.exit(main())

import re
import sys


def orgchart(data, selected):
    lines = [line[:-1] if line.endswith('\r') else line for line in data.split('\n')]
    if lines[0] != 'id,name,manager,salary':
        raise ValueError('invalid header')
    employees = {}
    for line in lines[1:]:
        if not line:
            continue
        fields = line.split(',')
        if len(fields) != 4:
            raise ValueError('invalid employee fields')
        eid, name, manager, salary = fields
        if (not re.fullmatch(r'[a-z0-9]{1,8}', eid) or eid in employees
                or not name or name.startswith(' ') or name.endswith(' ')
                or (manager and not re.fullmatch(r'[a-z0-9]{1,8}', manager))
                or not re.fullmatch(r'[0-9]{1,9}', salary)):
            raise ValueError('invalid employee')
        employees[eid] = (name, manager, int(salary))
    children = {eid: [] for eid in employees}
    roots = []
    for eid, (_, manager, _) in employees.items():
        if manager:
            if manager not in employees:
                raise ValueError('unknown manager')
            children[manager].append(eid)
        else:
            roots.append(eid)
    key = lambda eid: (employees[eid][0].encode('utf-8'), eid)
    roots.sort(key=key)
    for group in children.values():
        group.sort(key=key)
    traversal = []
    stack = list(reversed(roots))
    while stack:
        eid = stack.pop()
        traversal.append(eid)
        stack.extend(reversed(children[eid]))
    if len(traversal) != len(employees):
        raise ValueError('cycle')
    totals = {}
    for eid in reversed(traversal):
        reports = sum(totals[child][0] + 1 for child in children[eid])
        cost = employees[eid][2] + sum(totals[child][1] for child in children[eid])
        totals[eid] = reports, cost
    if selected is not None:
        if selected not in employees:
            raise ValueError('unknown employee')
        roots = [selected]
    output = []
    stack = [(eid, 0) for eid in reversed(roots)]
    while stack:
        eid, depth = stack.pop()
        reports, cost = totals[eid]
        output.append(f'{"  " * depth}{employees[eid][0]} [{eid}] reports={reports} cost={cost:,}')
        stack.extend((child, depth + 1) for child in reversed(children[eid]))
    return output


def main():
    if len(sys.argv) > 2:
        print('expected at most one ID', file=sys.stderr)
        return 2
    try:
        output = orgchart(sys.stdin.buffer.read().decode('utf-8'), sys.argv[1] if len(sys.argv) == 2 else None)
    except (ValueError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for line in output:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())

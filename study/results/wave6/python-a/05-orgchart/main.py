import re
import sys

HEADER = "id,name,manager,salary"
ID_RE = re.compile(r"[a-z0-9]{1,8}")
SALARY_RE = re.compile(r"[0-9]{1,9}")


class InputError(Exception):
    pass


class Employee:
    def __init__(self, id, name, manager, salary):
        self.id = id
        self.name = name
        self.manager = manager
        self.salary = salary
        self.children = []
        self.reports = 0
        self.cost = salary

    def sort_key(self):
        return (self.name.encode("utf-8"), self.id.encode("utf-8"))


def parse(text):
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if not lines or lines[0] != HEADER:
        raise InputError("bad header")

    employees = {}
    for lineno, line in enumerate(lines[1:], 2):
        if line == "":
            continue
        fields = line.split(",")
        if len(fields) != 4:
            raise InputError(f"line {lineno}: expected 4 fields")
        id, name, manager, salary = fields
        if not ID_RE.fullmatch(id):
            raise InputError(f"line {lineno}: bad id")
        if id in employees:
            raise InputError(f"line {lineno}: duplicate id {id}")
        if name == "" or name.startswith(" ") or name.endswith(" "):
            raise InputError(f"line {lineno}: bad name")
        if manager != "" and not ID_RE.fullmatch(manager):
            raise InputError(f"line {lineno}: bad manager")
        if not SALARY_RE.fullmatch(salary):
            raise InputError(f"line {lineno}: bad salary")
        employees[id] = Employee(id, name, manager, int(salary))
    return employees


def build_forest(employees):
    roots = []
    for emp in employees.values():
        if emp.manager == "":
            roots.append(emp)
        elif emp.manager in employees:
            employees[emp.manager].children.append(emp)
        else:
            raise InputError(f"unknown manager {emp.manager}")
    for emp in employees.values():
        emp.children.sort(key=Employee.sort_key)
    roots.sort(key=Employee.sort_key)

    # Pre-order walk from the roots; anything not reached is on or below a cycle.
    order = []
    stack = [(root, 0) for root in reversed(roots)]
    depths = {}
    while stack:
        emp, depth = stack.pop()
        order.append(emp)
        depths[emp.id] = depth
        stack.extend((c, depth + 1) for c in reversed(emp.children))
    if len(order) != len(employees):
        raise InputError("cycle in management chain")

    for emp in reversed(order):
        for child in emp.children:
            emp.reports += child.reports + 1
            emp.cost += child.cost
    return roots


def render(root):
    out = []
    stack = [(root, 0)]
    while stack:
        emp, depth = stack.pop()
        out.append(f"{'  ' * depth}{emp.name} [{emp.id}] "
                   f"reports={emp.reports} cost={emp.cost:,}\n")
        stack.extend((c, depth + 1) for c in reversed(emp.children))
    return "".join(out)


def main(argv):
    if len(argv) > 1:
        print("usage: orgchart [ID]", file=sys.stderr)
        return 2
    try:
        text = sys.stdin.buffer.read().decode("utf-8")
        employees = parse(text)
        roots = build_forest(employees)
        if argv:
            if argv[0] not in employees:
                raise InputError(f"unknown id {argv[0]}")
            roots = [employees[argv[0]]]
    except (InputError, UnicodeDecodeError) as e:
        print(f"orgchart: {e}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(render(root) for root in roots))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

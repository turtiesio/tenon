"""orgchart: print a reporting tree with subtree sizes and costs."""
import re
import sys
from dataclasses import dataclass, field

HEADER = "id,name,manager,salary"
ID_RE = re.compile(r"[a-z0-9]{1,8}")
SALARY_RE = re.compile(r"[0-9]{1,9}")


class InputError(Exception):
    pass


@dataclass
class Employee:
    id: str
    name: str
    manager: str
    salary: int
    reports: list["Employee"] = field(default_factory=list)
    count: int = 0
    cost: int = 0

    def sort_key(self) -> tuple[bytes, bytes]:
        return (self.name.encode(), self.id.encode())


def read_lines(data: bytes) -> list[str]:
    text = data.decode("utf-8")
    lines = text.split("\n")
    if text.endswith("\n") or text == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def parse(lines: list[str]) -> dict[str, Employee]:
    if not lines or lines[0] != HEADER:
        raise InputError("missing or wrong header")
    employees = {}
    for number, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        fields = line.split(",")
        if len(fields) != 4:
            raise InputError(f"line {number}: expected 4 fields")
        emp_id, name, manager, salary = fields
        if not ID_RE.fullmatch(emp_id):
            raise InputError(f"line {number}: invalid id")
        if not name or name[0] == " " or name[-1] == " ":
            raise InputError(f"line {number}: invalid name")
        if manager and not ID_RE.fullmatch(manager):
            raise InputError(f"line {number}: invalid manager")
        if not SALARY_RE.fullmatch(salary):
            raise InputError(f"line {number}: invalid salary")
        if emp_id in employees:
            raise InputError(f"line {number}: duplicate id {emp_id}")
        employees[emp_id] = Employee(emp_id, name, manager, int(salary))
    return employees


def build_forest(employees: dict[str, Employee]) -> list[Employee]:
    """Link reports to managers, compute counts and costs, return sorted roots."""
    roots = []
    for emp in employees.values():
        if not emp.manager:
            roots.append(emp)
        elif emp.manager in employees:
            employees[emp.manager].reports.append(emp)
        else:
            raise InputError(f"{emp.id}: unknown manager {emp.manager}")
    roots.sort(key=Employee.sort_key)

    # Iterative pre-order walk from the roots; whoever is not reached is on
    # or below a cycle.
    order = []
    stack = list(roots)
    while stack:
        emp = stack.pop()
        order.append(emp)
        emp.reports.sort(key=Employee.sort_key)
        stack.extend(emp.reports)
    if len(order) != len(employees):
        raise InputError("reporting cycle")

    for emp in reversed(order):  # children before parents
        emp.count = sum(r.count + 1 for r in emp.reports)
        emp.cost = emp.salary + sum(r.cost for r in emp.reports)
    return roots


def render(tops: list[Employee]) -> str:
    out = []
    stack = [(emp, 0) for emp in reversed(tops)]
    while stack:
        emp, depth = stack.pop()
        out.append(f"{'  ' * depth}{emp.name} [{emp.id}] "
                   f"reports={emp.count} cost={emp.cost:,}\n")
        stack.extend((r, depth + 1) for r in reversed(emp.reports))
    return "".join(out)


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print("usage: orgchart [ID]", file=sys.stderr)
        return 2
    try:
        employees = parse(read_lines(sys.stdin.buffer.read()))
        roots = build_forest(employees)
        if argv:
            if argv[0] not in employees:
                raise InputError(f"unknown id {argv[0]}")
            roots = [employees[argv[0]]]
    except (InputError, UnicodeDecodeError) as e:
        print(f"orgchart: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(render(roots))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

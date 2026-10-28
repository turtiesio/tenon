import * as fs from "node:fs";

interface Employee {
  id: string;
  name: string;
  nameBytes: Buffer;
  manager: string;
  salary: number;
  reports: Employee[];
  count: number; // employees below, at any depth
  cost: number; // own salary plus everyone below
}

class InputError extends Error {}

const ID_RE = /^[a-z0-9]{1,8}$/;
const SALARY_RE = /^[0-9]{1,9}$/;

function compareEmployees(a: Employee, b: Employee): number {
  return Buffer.compare(a.nameBytes, b.nameBytes) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

function parse(text: string): Map<string, Employee> {
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const stripped = lines.map((l) => (l.endsWith("\r") ? l.slice(0, -1) : l));
  if (stripped.length === 0 || stripped[0] !== "id,name,manager,salary") {
    throw new InputError("missing or wrong header");
  }
  const employees = new Map<string, Employee>();
  for (let i = 1; i < stripped.length; i++) {
    const line = stripped[i];
    if (line === "") continue;
    const where = `line ${i + 1}`;
    const fields = line.split(",");
    if (fields.length !== 4) throw new InputError(`${where}: expected 4 fields`);
    const [id, name, manager, salary] = fields;
    if (!ID_RE.test(id)) throw new InputError(`${where}: invalid id`);
    if (name === "" || name.startsWith(" ") || name.endsWith(" ")) throw new InputError(`${where}: invalid name`);
    if (manager !== "" && !ID_RE.test(manager)) throw new InputError(`${where}: invalid manager`);
    if (!SALARY_RE.test(salary)) throw new InputError(`${where}: invalid salary`);
    if (employees.has(id)) throw new InputError(`${where}: duplicate id '${id}'`);
    employees.set(id, {
      id, name, nameBytes: Buffer.from(name, "utf8"), manager, salary: Number(salary),
      reports: [], count: 0, cost: 0,
    });
  }
  return employees;
}

/** Links reports to managers, checks the structure, and returns the sorted roots. */
function build(employees: Map<string, Employee>): Employee[] {
  const roots: Employee[] = [];
  for (const e of employees.values()) {
    if (e.manager === "") {
      roots.push(e);
      continue;
    }
    const boss = employees.get(e.manager);
    if (!boss) throw new InputError(`employee '${e.id}' has unknown manager '${e.manager}'`);
    boss.reports.push(e);
  }
  roots.sort(compareEmployees);
  for (const e of employees.values()) e.reports.sort(compareEmployees);

  // Pre-order walk from the roots; anything not reached is on or below a cycle.
  const order: Employee[] = [];
  const stack = [...roots].reverse();
  while (stack.length > 0) {
    const e = stack.pop()!;
    order.push(e);
    for (let i = e.reports.length - 1; i >= 0; i--) stack.push(e.reports[i]);
  }
  if (order.length !== employees.size) throw new InputError("the reporting lines contain a cycle");
  for (let i = order.length - 1; i >= 0; i--) {
    const e = order[i];
    e.cost = e.salary;
    e.count = 0;
    for (const r of e.reports) {
      e.cost += r.cost;
      e.count += r.count + 1;
    }
  }
  return roots;
}

function groupDigits(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+$)/g, ",");
}

function render(e: Employee, depth: number, out: string[]): void {
  out.push(`${"  ".repeat(depth)}${e.name} [${e.id}] reports=${e.count} cost=${groupDigits(e.cost)}\n`);
  for (const r of e.reports) render(r, depth + 1, out);
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length > 1) {
    process.stderr.write("usage: orgchart [ID]\n");
    return 2;
  }
  try {
    const employees = parse(fs.readFileSync(0, "utf8"));
    let tops = build(employees);
    if (args.length === 1) {
      const top = employees.get(args[0]);
      if (!top) throw new InputError(`no employee with id '${args[0]}'`);
      tops = [top];
    }
    const out: string[] = [];
    for (const t of tops) render(t, 0, out);
    process.stdout.write(out.join(""));
    return 0;
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`orgchart: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();

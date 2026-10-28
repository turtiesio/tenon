import { readFileSync } from "node:fs";

interface Employee {
  id: string;
  name: string;
  manager: string;
  salary: number;
  reports: Employee[];
  count: number; // everyone below, at any depth
  cost: number; // own salary plus everyone below
}

class InputError extends Error {}

const HEADER = "id,name,manager,salary";
const ID = /^[a-z0-9]{1,8}$/;
const SALARY = /^[0-9]{1,9}$/;

function readStdin(): string {
  try {
    return readFileSync(0, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "EOF") return "";
    throw e;
  }
}

function splitLines(text: string): string[] {
  if (text === "") return [];
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function parse(text: string): Map<string, Employee> {
  const lines = splitLines(text);
  if (lines[0] !== HEADER) throw new InputError("missing or wrong header");

  const byId = new Map<string, Employee>();
  for (const line of lines.slice(1)) {
    if (line === "") continue;
    const fields = line.split(",");
    if (fields.length !== 4) throw new InputError(`expected 4 fields: '${line}'`);
    const [id, name, manager, salary] = fields;
    if (!ID.test(id)) throw new InputError(`bad id '${id}'`);
    if (byId.has(id)) throw new InputError(`duplicate id '${id}'`);
    if (name === "" || name.startsWith(" ") || name.endsWith(" ")) {
      throw new InputError(`bad name '${name}'`);
    }
    if (manager !== "" && !ID.test(manager)) throw new InputError(`bad manager '${manager}'`);
    if (!SALARY.test(salary)) throw new InputError(`bad salary '${salary}'`);
    byId.set(id, { id, name, manager, salary: Number(salary), reports: [], count: 0, cost: 0 });
  }
  return byId;
}

function compareBytes(a: string, b: string): number {
  return Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
}

function byNameThenId(a: Employee, b: Employee): number {
  return compareBytes(a.name, b.name) || compareBytes(a.id, b.id);
}

/** Links reports to managers, sorts them, and fills in counts and costs. Returns the roots. */
function buildForest(byId: Map<string, Employee>): Employee[] {
  const roots: Employee[] = [];
  for (const emp of byId.values()) {
    if (emp.manager === "") {
      roots.push(emp);
      continue;
    }
    const boss = byId.get(emp.manager);
    if (!boss) throw new InputError(`unknown manager '${emp.manager}'`);
    boss.reports.push(emp);
  }
  roots.sort(byNameThenId);

  let reached = 0;
  const visit = (emp: Employee): void => {
    reached++;
    emp.reports.sort(byNameThenId);
    emp.cost = emp.salary;
    for (const r of emp.reports) {
      visit(r);
      emp.count += r.count + 1;
      emp.cost += r.cost;
    }
  };
  roots.forEach(visit);
  if (reached !== byId.size) throw new InputError("cycle in reporting structure");
  return roots;
}

function groupDigits(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+$)/g, ",");
}

function render(emp: Employee, depth: number, out: string[]): void {
  out.push(`${"  ".repeat(depth)}${emp.name} [${emp.id}] reports=${emp.count} cost=${groupDigits(emp.cost)}\n`);
  for (const r of emp.reports) render(r, depth + 1, out);
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length > 1) {
    process.stderr.write("usage: orgchart [ID]\n");
    return 2;
  }
  try {
    const byId = parse(readStdin());
    const roots = buildForest(byId);
    let start = roots;
    if (args.length === 1) {
      const emp = byId.get(args[0]);
      if (!emp) throw new InputError(`unknown id '${args[0]}'`);
      start = [emp];
    }
    const out: string[] = [];
    for (const emp of start) render(emp, 0, out);
    process.stdout.write(out.join(""));
    return 0;
  } catch (e) {
    if (!(e instanceof InputError)) throw e;
    process.stderr.write(`orgchart: ${e.message}\n`);
    return 1;
  }
}

process.exitCode = main();

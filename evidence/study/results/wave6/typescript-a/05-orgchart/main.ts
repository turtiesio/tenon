import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length > 1) { console.error('Usage: orgchart [ID]'); process.exit(2); }
type Employee = { id: string; name: string; manager: string; salary: number; children: Employee[]; reports: number; cost: number; state: number };
try {
  const lines = readFileSync(0, 'utf8').split('\n').map(s => s.replace(/\r$/, ''));
  if (lines.shift() !== 'id,name,manager,salary') throw new Error('Invalid header');
  const employees = new Map<string, Employee>();
  for (const line of lines) {
    if (line === '') continue;
    const fields = line.split(',');
    const [id, name, manager, salary] = fields;
    if (fields.length !== 4 || !/^[a-z0-9]{1,8}$/.test(id) || !name || name.startsWith(' ') || name.endsWith(' ') || (manager !== '' && !/^[a-z0-9]{1,8}$/.test(manager)) || !/^[0-9]{1,9}$/.test(salary) || employees.has(id)) throw new Error('Invalid employee');
    employees.set(id, { id, name, manager, salary: Number(salary), children: [], reports: 0, cost: 0, state: 0 });
  }
  const roots: Employee[] = [];
  for (const employee of employees.values()) {
    if (!employee.manager) roots.push(employee);
    else {
      const manager = employees.get(employee.manager);
      if (!manager) throw new Error('Unknown manager');
      manager.children.push(employee);
    }
  }
  function calculate(employee: Employee): void {
    if (employee.state === 1) throw new Error('Cycle');
    if (employee.state === 2) return;
    employee.state = 1;
    employee.cost = employee.salary;
    for (const child of employee.children) {
      calculate(child);
      employee.reports += 1 + child.reports;
      employee.cost += child.cost;
    }
    employee.state = 2;
  }
  for (const employee of employees.values()) calculate(employee);
  const compare = (a: Employee, b: Employee) => Buffer.compare(Buffer.from(a.name), Buffer.from(b.name)) || Buffer.compare(Buffer.from(a.id), Buffer.from(b.id));
  const output: string[] = [];
  function print(employee: Employee, depth: number): void {
    const cost = String(employee.cost).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    output.push(`${'  '.repeat(depth)}${employee.name} [${employee.id}] reports=${employee.reports} cost=${cost}`);
    for (const child of employee.children.sort(compare)) print(child, depth + 1);
  }
  if (args.length) {
    const employee = employees.get(args[0]);
    if (!employee) throw new Error('Unknown ID');
    print(employee, 0);
  } else for (const root of roots.sort(compare)) print(root, 0);
  if (output.length) console.log(output.join('\n'));
} catch (error) { console.error(String(error)); process.exitCode = 1; }

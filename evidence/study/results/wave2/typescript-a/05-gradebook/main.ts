import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
if (args.length !== 2) process.exit(2);
function read(path: string, header: string): string[] {
  let text: string;
  try { text = readFileSync(path, 'utf8'); } catch { process.exit(1); }
  const lines = text.split('\n').map(line => line.replace(/\r$/, ''));
  if (lines.shift() !== header) process.exit(1);
  return lines.filter(line => line !== '');
}
const studentLines = read(args[0], 'id,name,section');
const scoreLines = read(args[1], 'id,assignment,points,max');
type Student = { id: string; name: string; section: string; scores: Map<string, [bigint, bigint]>; p: bigint; m: bigint; letter: string };
const students = new Map<string, Student>();
let badStudents = 0, badScores = 0, orphans = 0;
for (const line of studentLines) {
  const [id, name, section, extra] = line.split(',');
  if (extra !== undefined || !/^[A-Za-z0-9]{1,16}$/.test(id) || !name || name.length > 40 || !/^[A-Z]$/.test(section ?? '') || students.has(id)) { badStudents++; continue; }
  students.set(id, { id, name, section, scores: new Map(), p: 0n, m: 0n, letter: 'none' });
}
for (const line of scoreLines) {
  const fields = line.split(',');
  const [id, assignment, points, max] = fields;
  if (fields.length !== 4 || !/^[A-Za-z0-9]{1,16}$/.test(id) || !/^[A-Za-z0-9_-]{1,32}$/.test(assignment ?? '') || !/^[0-9]{1,6}$/.test(points ?? '') || !/^[0-9]{1,6}$/.test(max ?? '') || Number(max) < 1 || Number(points) > Number(max)) { badScores++; continue; }
  const student = students.get(id);
  if (!student) { orphans++; continue; }
  student.scores.set(assignment, [BigInt(points), BigInt(max)]);
}
for (const student of students.values()) {
  for (const [p, m] of student.scores.values()) { student.p += p; student.m += m; }
  if (student.m) student.letter = ['A', 'B', 'C', 'D'].find((_, i) => 100n * student.p >= BigInt(90 - i * 10) * student.m) ?? 'F';
}
const compareText = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
const sorted = [...students.values()].sort((a, b) => {
  if (a.section !== b.section) return compareText(a.section, b.section);
  if (!a.m !== !b.m) return a.m ? -1 : 1;
  const difference = a.p * b.m - b.p * a.m;
  return difference ? (difference > 0n ? -1 : 1) : compareText(a.id, b.id);
});
const sections = new Map<string, Record<string, number>>();
for (const student of sorted) {
  const { section, id, name, p, m, letter } = student;
  const counts = sections.get(section) ?? { students: 0, A: 0, B: 0, C: 0, D: 0, F: 0, none: 0 };
  sections.set(section, counts);
  counts.students++;
  counts[letter]++;
  if (!m) console.log(`${section} ${id} ${name} 0/0 - -`);
  else {
    const tenths = (2000n * p + m) / (2n * m);
    console.log(`${section} ${id} ${name} ${p}/${m} ${tenths / 10n}.${tenths % 10n}% ${letter}`);
  }
}
for (const [section, counts] of sections) console.log(`section ${section}: ${Object.entries(counts).map(([key, value]) => `${key}=${value}`).join(' ')}`);
console.log(`bad_students=${badStudents} bad_scores=${badScores} orphans=${orphans}`);

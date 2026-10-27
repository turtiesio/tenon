import { readFileSync } from "node:fs";

const ID_RE = /^[A-Za-z0-9]{1,16}$/;
const ASSIGNMENT_RE = /^[A-Za-z0-9_-]{1,32}$/;
const NUMBER_RE = /^[0-9]{1,6}$/;
const SECTION_RE = /^[A-Z]$/;

interface Student {
  id: string;
  name: string;
  section: string;
  // assignment -> [points, max]; the last well-formed score line wins.
  assignments: Map<string, [number, number]>;
  points: bigint;
  max: bigint;
}

type Letter = "A" | "B" | "C" | "D" | "F";

// Returns the data lines after the header, or null if the file cannot be
// read or its first line is not the expected header.
function readRecords(path: string, header: string): string[][] | null {
  let text: string;
  try {
    text = readFileSync(path, "latin1");
  } catch {
    return null;
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  const cleaned = lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
  if (cleaned.length === 0 || cleaned[0] !== header) {
    return null;
  }
  return cleaned.slice(1).filter((line) => line !== "").map((line) => line.split(","));
}

function letterFor(points: bigint, max: bigint): Letter {
  if (100n * points >= 90n * max) {
    return "A";
  }
  if (100n * points >= 80n * max) {
    return "B";
  }
  if (100n * points >= 70n * max) {
    return "C";
  }
  if (100n * points >= 60n * max) {
    return "D";
  }
  return "F";
}

// 100 * points / max rounded half up to one decimal place.
function formatPercent(points: bigint, max: bigint): string {
  const tenths = (2000n * points + max) / (2n * max);
  return `${tenths / 10n}.${tenths % 10n}`;
}

function compareStrings(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function compareStudents(a: Student, b: Student): number {
  if (a.section !== b.section) {
    return compareStrings(a.section, b.section);
  }
  const aNone = a.max === 0n;
  const bNone = b.max === 0n;
  if (aNone !== bNone) {
    return aNone ? 1 : -1;
  }
  if (!aNone) {
    const left = a.points * b.max;
    const right = b.points * a.max;
    if (left !== right) {
      return left > right ? -1 : 1;
    }
  }
  return compareStrings(a.id, b.id);
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    console.error("usage: gradebook STUDENTS SCORES");
    return 2;
  }
  const studentRecords = readRecords(args[0], "id,name,section");
  const scoreRecords = readRecords(args[1], "id,assignment,points,max");
  if (studentRecords === null || scoreRecords === null) {
    console.error("cannot read input or bad header");
    return 1;
  }

  let badStudents = 0;
  let badScores = 0;
  let orphans = 0;

  const students = new Map<string, Student>();
  for (const [id, name, section, ...rest] of studentRecords) {
    const wellFormed =
      rest.length === 0 &&
      section !== undefined &&
      ID_RE.test(id) &&
      name.length >= 1 &&
      name.length <= 40 &&
      SECTION_RE.test(section);
    if (!wellFormed || students.has(id)) {
      badStudents++;
      continue;
    }
    students.set(id, {
      id,
      name,
      section,
      assignments: new Map(),
      points: 0n,
      max: 0n,
    });
  }

  for (const [id, assignment, points, max, ...rest] of scoreRecords) {
    const wellFormed =
      rest.length === 0 &&
      max !== undefined &&
      ID_RE.test(id) &&
      ASSIGNMENT_RE.test(assignment) &&
      NUMBER_RE.test(points) &&
      NUMBER_RE.test(max) &&
      Number(max) >= 1 &&
      Number(points) <= Number(max);
    if (!wellFormed) {
      badScores++;
      continue;
    }
    const student = students.get(id);
    if (student === undefined) {
      orphans++;
      continue;
    }
    student.assignments.set(assignment, [Number(points), Number(max)]);
  }

  for (const student of students.values()) {
    for (const [points, max] of student.assignments.values()) {
      student.points += BigInt(points);
      student.max += BigInt(max);
    }
  }

  const sorted = [...students.values()].sort(compareStudents);
  const out: string[] = [];
  const sectionCounts = new Map<string, { students: number; letters: Record<Letter | "none", number> }>();

  for (const student of sorted) {
    const prefix = `${student.section} ${student.id} ${student.name} ${student.points}/${student.max}`;
    let counts = sectionCounts.get(student.section);
    if (counts === undefined) {
      counts = { students: 0, letters: { A: 0, B: 0, C: 0, D: 0, F: 0, none: 0 } };
      sectionCounts.set(student.section, counts);
    }
    counts.students++;
    if (student.max === 0n) {
      out.push(`${prefix} - -`);
      counts.letters.none++;
    } else {
      const letter = letterFor(student.points, student.max);
      out.push(`${prefix} ${formatPercent(student.points, student.max)}% ${letter}`);
      counts.letters[letter]++;
    }
  }

  // Sections come out in order because the students are sorted by section.
  for (const [section, counts] of sectionCounts) {
    const l = counts.letters;
    out.push(
      `section ${section}: students=${counts.students} A=${l.A} B=${l.B} C=${l.C} D=${l.D} F=${l.F} none=${l.none}`,
    );
  }
  out.push(`bad_students=${badStudents} bad_scores=${badScores} orphans=${orphans}`);
  process.stdout.write(out.join("\n") + "\n");
  return 0;
}

process.exitCode = main();

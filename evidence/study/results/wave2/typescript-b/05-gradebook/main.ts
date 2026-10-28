import * as fs from "node:fs";

const STUDENTS_HEADER = "id,name,section";
const SCORES_HEADER = "id,assignment,points,max";
const ID_RE = /^[A-Za-z0-9]{1,16}$/;
const SECTION_RE = /^[A-Z]$/;
const ASSIGNMENT_RE = /^[A-Za-z0-9_-]{1,32}$/;
const NUMBER_RE = /^[0-9]{1,6}$/;
const LETTERS = ["A", "B", "C", "D", "F"] as const;

type Letter = (typeof LETTERS)[number];

interface Student {
  id: string;
  name: string;
  section: string;
  scores: Map<string, { points: number; max: number }>;
  points: bigint;
  max: bigint;
}

class InputError extends Error {}

// Returns the data lines after checking the header; empty lines are dropped.
function readDataLines(path: string, header: string): string[] {
  let text: string;
  try {
    text = fs.readFileSync(path, "latin1");
  } catch (err) {
    throw new InputError(`cannot read ${path}: ${(err as Error).message}`);
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  const cleaned = lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
  if (cleaned.length === 0 || cleaned[0] !== header) {
    throw new InputError(`${path}: missing header ${header}`);
  }
  return cleaned.slice(1).filter((line) => line !== "");
}

function letterFor(points: bigint, max: bigint): Letter {
  const scaled = 100n * points;
  if (scaled >= 90n * max) {
    return "A";
  }
  if (scaled >= 80n * max) {
    return "B";
  }
  if (scaled >= 70n * max) {
    return "C";
  }
  if (scaled >= 60n * max) {
    return "D";
  }
  return "F";
}

function formatPercent(points: bigint, max: bigint): string {
  // Tenths of a percent, rounded half up.
  const tenths = (2000n * points + max) / (2n * max);
  return `${tenths / 10n}.${tenths % 10n}`;
}

function compareStudents(a: Student, b: Student): number {
  if (a.section !== b.section) {
    return a.section < b.section ? -1 : 1;
  }
  const aGraded = a.max > 0n;
  const bGraded = b.max > 0n;
  if (aGraded !== bGraded) {
    return aGraded ? -1 : 1;
  }
  if (aGraded) {
    const left = a.points * b.max;
    const right = b.points * a.max;
    if (left !== right) {
      return left > right ? -1 : 1;
    }
  }
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

function run(studentsPath: string, scoresPath: string): string {
  const studentLines = readDataLines(studentsPath, STUDENTS_HEADER);
  const scoreLines = readDataLines(scoresPath, SCORES_HEADER);

  const students = new Map<string, Student>();
  let badStudents = 0;
  for (const line of studentLines) {
    const fields = line.split(",");
    if (fields.length !== 3) {
      badStudents++;
      continue;
    }
    const [id, name, section] = fields;
    if (!ID_RE.test(id) || name.length < 1 || name.length > 40 || !SECTION_RE.test(section)) {
      badStudents++;
      continue;
    }
    if (students.has(id)) {
      badStudents++;
      continue;
    }
    students.set(id, { id, name, section, scores: new Map(), points: 0n, max: 0n });
  }

  let badScores = 0;
  let orphans = 0;
  for (const line of scoreLines) {
    const fields = line.split(",");
    if (fields.length !== 4) {
      badScores++;
      continue;
    }
    const [id, assignment, pointsText, maxText] = fields;
    if (!ID_RE.test(id) || !ASSIGNMENT_RE.test(assignment) || !NUMBER_RE.test(pointsText) || !NUMBER_RE.test(maxText)) {
      badScores++;
      continue;
    }
    const points = Number(pointsText);
    const max = Number(maxText);
    if (max < 1 || points > max) {
      badScores++;
      continue;
    }
    const student = students.get(id);
    if (student === undefined) {
      orphans++;
      continue;
    }
    student.scores.set(assignment, { points, max });
  }

  for (const student of students.values()) {
    for (const score of student.scores.values()) {
      student.points += BigInt(score.points);
      student.max += BigInt(score.max);
    }
  }

  const sorted = [...students.values()].sort(compareStudents);
  const out: string[] = [];
  const summaries = new Map<string, { students: number; none: number; letters: Record<Letter, number> }>();
  for (const student of sorted) {
    let summary = summaries.get(student.section);
    if (summary === undefined) {
      summary = { students: 0, none: 0, letters: { A: 0, B: 0, C: 0, D: 0, F: 0 } };
      summaries.set(student.section, summary);
    }
    summary.students++;
    const prefix = `${student.section} ${student.id} ${student.name}`;
    if (student.max === 0n) {
      summary.none++;
      out.push(`${prefix} 0/0 - -`);
    } else {
      const letter = letterFor(student.points, student.max);
      summary.letters[letter]++;
      const percent = formatPercent(student.points, student.max);
      out.push(`${prefix} ${student.points}/${student.max} ${percent}% ${letter}`);
    }
  }
  for (const [section, summary] of summaries) {
    const counts = LETTERS.map((letter) => `${letter}=${summary.letters[letter]}`).join(" ");
    out.push(`section ${section}: students=${summary.students} ${counts} none=${summary.none}`);
  }
  out.push(`bad_students=${badStudents} bad_scores=${badScores} orphans=${orphans}`);
  return out.map((line) => line + "\n").join("");
}

function main(argv: string[]): number {
  if (argv.length !== 2) {
    process.stderr.write("usage: gradebook STUDENTS SCORES\n");
    return 2;
  }
  try {
    process.stdout.write(Buffer.from(run(argv[0], argv[1]), "latin1"));
    return 0;
  } catch (err) {
    if (err instanceof InputError) {
      process.stderr.write(`gradebook: ${err.message}\n`);
      return 1;
    }
    throw err;
  }
}

process.exitCode = main(process.argv.slice(2));

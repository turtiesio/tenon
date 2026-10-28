import * as fs from "node:fs";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAILY_LIMIT = 480;
const PUNCH = /^([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([01][0-9]|2[0-3]):([0-5][0-9]) (IN|OUT)$/;

interface Punch {
  minute: number;
  isIn: boolean;
}

interface Employee {
  // Punches per day index, in input order.
  days: Punch[][];
}

interface Summary {
  dayMinutes: number[];
  anomalies: number;
}

function formatTime(minutes: number): string {
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

// Pairs one day's punches (already in input order) and returns worked minutes
// and the anomaly count.
function pairDay(punches: Punch[]): { minutes: number; anomalies: number } {
  // Array.prototype.sort is stable, so equal times keep input order.
  const sorted = [...punches].sort((a, b) => a.minute - b.minute);
  let minutes = 0;
  let anomalies = 0;
  let openAt: number | null = null;
  for (const p of sorted) {
    if (p.isIn) {
      if (openAt !== null) anomalies++;
      openAt = p.minute;
    } else if (openAt !== null) {
      minutes += p.minute - openAt;
      openAt = null;
    } else {
      anomalies++;
    }
  }
  if (openAt !== null) anomalies++;
  return { minutes, anomalies };
}

function summarize(emp: Employee): Summary {
  const dayMinutes: number[] = [];
  let anomalies = 0;
  for (const punches of emp.days) {
    const r = pairDay(punches);
    dayMinutes.push(r.minutes);
    anomalies += r.anomalies;
  }
  return { dayMinutes, anomalies };
}

function main(): number {
  if (process.argv.length > 2) {
    console.error("timesheet: takes no arguments");
    return 2;
  }

  let text: string;
  try {
    text = fs.readFileSync(0, "latin1");
  } catch {
    text = "";
  }

  const employees = new Map<string, Employee>();
  let skipped = 0;
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  for (let line of lines) {
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (/^ *$/.test(line)) continue;
    const m = PUNCH.exec(line);
    if (m === null) {
      skipped++;
      continue;
    }
    const [, name, day, hh, mm, kind] = m;
    let emp = employees.get(name);
    if (emp === undefined) {
      emp = { days: DAYS.map(() => []) };
      employees.set(name, emp);
    }
    emp.days[DAYS.indexOf(day)].push({
      minute: Number(hh) * 60 + Number(mm),
      isIn: kind === "IN",
    });
  }

  const out: string[] = [];
  const names = [...employees.keys()].sort();
  for (const name of names) {
    const { dayMinutes, anomalies } = summarize(employees.get(name)!);
    let total = 0;
    let overtime = 0;
    const parts = [name];
    dayMinutes.forEach((m, i) => {
      total += m;
      overtime += Math.max(0, m - DAILY_LIMIT);
      if (m > 0) parts.push(`${DAYS[i]}=${formatTime(m)}`);
    });
    parts.push(`total=${formatTime(total)}`, `overtime=${formatTime(overtime)}`, `anomalies=${anomalies}`);
    out.push(parts.join(" ") + "\n");
  }
  out.push(`skipped=${skipped}\n`);
  process.stdout.write(out.join(""));
  return 0;
}

process.exitCode = main();

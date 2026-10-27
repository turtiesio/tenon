import * as fs from "node:fs";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PUNCH = /^([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([01][0-9]|2[0-3]):([0-5][0-9]) (IN|OUT)$/;
const REGULAR_DAY = 480;

interface Punch {
  minute: number;
  isIn: boolean;
}

interface DayResult {
  minutes: number;
  anomalies: number;
}

function formatTime(m: number): string {
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
}

function pairDay(punches: Punch[]): DayResult {
  const sorted = [...punches].sort((a, b) => a.minute - b.minute);
  let openAt: number | null = null;
  let minutes = 0;
  let anomalies = 0;
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

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: timesheet < punches\n");
    process.exit(2);
  }

  // name -> punches per day index
  const employees = new Map<string, Punch[][]>();
  let skipped = 0;
  for (const raw of fs.readFileSync(0, "latin1").split("\n")) {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (/^ *$/.test(line)) continue;
    const m = PUNCH.exec(line);
    if (m === null) {
      skipped++;
      continue;
    }
    const [, name, day, hh, mm, kind] = m;
    let week = employees.get(name);
    if (week === undefined) {
      week = DAYS.map(() => []);
      employees.set(name, week);
    }
    week[DAYS.indexOf(day)].push({ minute: Number(hh) * 60 + Number(mm), isIn: kind === "IN" });
  }

  const out: string[] = [];
  const names = [...employees.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  for (const name of names) {
    const week = employees.get(name)!;
    const parts = [name];
    let total = 0;
    let overtime = 0;
    let anomalies = 0;
    week.forEach((punches, i) => {
      const day = pairDay(punches);
      if (day.minutes > 0) parts.push(`${DAYS[i]}=${formatTime(day.minutes)}`);
      total += day.minutes;
      overtime += Math.max(0, day.minutes - REGULAR_DAY);
      anomalies += day.anomalies;
    });
    parts.push(`total=${formatTime(total)}`, `overtime=${formatTime(overtime)}`, `anomalies=${anomalies}`);
    out.push(parts.join(" ") + "\n");
  }
  out.push(`skipped=${skipped}\n`);
  process.stdout.write(out.join(""));
}

main();

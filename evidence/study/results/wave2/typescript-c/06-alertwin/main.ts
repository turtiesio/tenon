import { readFileSync } from "node:fs";

interface Options {
  window: number;
  threshold: number;
  cooldown: number;
}

interface ServiceStats {
  errors: number;
  warns: number;
  alerts: number;
  peak: number;
  // Timestamps of accepted ERROR events still inside the window, oldest at `head`.
  recent: number[];
  head: number;
  lastAlert: number | null;
}

const LINE_RE = /^([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)$/;
const VALUE_RE = /^[0-9]{1,9}$/;

function parseOptions(args: string[]): Options | null {
  const options: Options = { window: 60, threshold: 3, cooldown: 300 };
  for (let i = 0; i < args.length; i += 2) {
    const flag = args[i];
    const raw = args[i + 1];
    if (raw === undefined || !VALUE_RE.test(raw)) {
      return null;
    }
    const value = Number(raw);
    if (flag === "-w" && value >= 1) {
      options.window = value;
    } else if (flag === "-t" && value >= 1) {
      options.threshold = value;
    } else if (flag === "-c") {
      options.cooldown = value;
    } else {
      return null;
    }
  }
  return options;
}

function main(): number {
  const options = parseOptions(process.argv.slice(2));
  if (options === null) {
    console.error("usage: alertwin [-w WINDOW] [-t THRESHOLD] [-c COOLDOWN]");
    return 2;
  }

  const lines = readFileSync(0, "latin1").split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }

  const services = new Map<string, ServiceStats>();
  const out: string[] = [];
  let skipped = 0;
  let lastTs = -1;

  for (let line of lines) {
    if (line.endsWith("\r")) {
      line = line.slice(0, -1);
    }
    if (/^ *$/.test(line)) {
      continue;
    }
    const match = LINE_RE.exec(line);
    if (match === null) {
      skipped++;
      continue;
    }
    const ts = Number(match[1]);
    if (ts < lastTs) {
      skipped++;
      continue;
    }
    lastTs = ts;

    const name = match[2];
    const level = match[3];
    let stats = services.get(name);
    if (stats === undefined) {
      stats = { errors: 0, warns: 0, alerts: 0, peak: 0, recent: [], head: 0, lastAlert: null };
      services.set(name, stats);
    }
    if (level === "WARN") {
      stats.warns++;
    }
    if (level !== "ERROR") {
      continue;
    }

    stats.errors++;
    stats.recent.push(ts);
    while (stats.recent[stats.head] <= ts - options.window) {
      stats.head++;
    }
    const count = stats.recent.length - stats.head;
    stats.peak = Math.max(stats.peak, count);
    const inCooldown = stats.lastAlert !== null && ts - stats.lastAlert < options.cooldown;
    if (count >= options.threshold && !inCooldown) {
      stats.alerts++;
      stats.lastAlert = ts;
      out.push(`ALERT ${ts} ${name} ${count}`);
    }
  }

  const names = [...services.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  for (const name of names) {
    const s = services.get(name)!;
    out.push(`${name} errors=${s.errors} warns=${s.warns} alerts=${s.alerts} peak=${s.peak}`);
  }
  out.push(`skipped=${skipped}`);
  process.stdout.write(out.join("\n") + "\n");
  return 0;
}

process.exitCode = main();

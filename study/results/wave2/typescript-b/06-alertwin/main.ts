import * as fs from "node:fs";

interface Config {
  window: number;
  threshold: number;
  cooldown: number;
}

interface ServiceState {
  errors: number;
  warns: number;
  alerts: number;
  peak: number;
  lastAlert: number | null;
  // Timestamps of errors still inside the window are recentErrors[head..].
  recentErrors: number[];
  head: number;
}

const EVENT_RE = /^([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)$/;

const OPTIONS: Record<string, { key: keyof Config; min: number }> = {
  "-w": { key: "window", min: 1 },
  "-t": { key: "threshold", min: 1 },
  "-c": { key: "cooldown", min: 0 },
};

function parseArgs(argv: string[]): Config | null {
  const config: Config = { window: 60, threshold: 3, cooldown: 300 };
  for (let i = 0; i < argv.length; i += 2) {
    const option = Object.hasOwn(OPTIONS, argv[i]) ? OPTIONS[argv[i]] : undefined;
    const value = argv[i + 1];
    if (option === undefined || value === undefined || !/^[0-9]{1,9}$/.test(value)) {
      return null;
    }
    const n = Number(value);
    if (n < option.min) {
      return null;
    }
    config[option.key] = n;
  }
  return config;
}

function splitLines(text: string): string[] {
  if (text === "") {
    return [];
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines.map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line));
}

function main(argv: string[]): number {
  const config = parseArgs(argv);
  if (config === null) {
    process.stderr.write("usage: alertwin [-w WINDOW] [-t THRESHOLD] [-c COOLDOWN]\n");
    return 2;
  }

  const services = new Map<string, ServiceState>();
  const out: string[] = [];
  let skipped = 0;
  let lastTs = -1;

  for (const line of splitLines(fs.readFileSync(0, "latin1"))) {
    if (/^ *$/.test(line)) {
      continue;
    }
    const m = EVENT_RE.exec(line);
    if (!m) {
      skipped++;
      continue;
    }
    const ts = Number(m[1]);
    if (ts < lastTs) {
      skipped++;
      continue;
    }
    lastTs = ts;
    const name = m[2];
    const level = m[3];

    let state = services.get(name);
    if (state === undefined) {
      state = { errors: 0, warns: 0, alerts: 0, peak: 0, lastAlert: null, recentErrors: [], head: 0 };
      services.set(name, state);
    }
    if (level === "WARN") {
      state.warns++;
    }
    if (level !== "ERROR") {
      continue;
    }

    state.errors++;
    state.recentErrors.push(ts);
    while (state.recentErrors[state.head] <= ts - config.window) {
      state.head++;
    }
    if (state.head > 1024 && state.head * 2 > state.recentErrors.length) {
      state.recentErrors = state.recentErrors.slice(state.head);
      state.head = 0;
    }
    const count = state.recentErrors.length - state.head;
    state.peak = Math.max(state.peak, count);

    const inCooldown = state.lastAlert !== null && ts - state.lastAlert < config.cooldown;
    if (count >= config.threshold && !inCooldown) {
      state.alerts++;
      state.lastAlert = ts;
      out.push(`ALERT ${ts} ${name} ${count}\n`);
    }
  }

  const names = [...services.keys()].sort();
  for (const name of names) {
    const s = services.get(name)!;
    out.push(`${name} errors=${s.errors} warns=${s.warns} alerts=${s.alerts} peak=${s.peak}\n`);
  }
  out.push(`skipped=${skipped}\n`);
  process.stdout.write(out.join(""));
  return 0;
}

process.exitCode = main(process.argv.slice(2));

import * as fs from "node:fs";
import * as path from "node:path";

const NAME = "[a-z][a-z0-9_]{0,31}";
const INT = "-?[0-9]{1,15}";
const NAME_RE = new RegExp(`^${NAME}$`);
const INT_RE = new RegExp(`^${INT}$`);
const RECORD_RE = new RegExp(`^(?:S (${NAME}) (${INT})|A (${NAME}) (${INT})|D (${NAME}))$`);
// The largest magnitude a single record can carry.
const MAX_RECORD_INT = 999_999_999_999_999n;

class Store {
  private readonly counters = new Map<string, bigint>();
  private readonly logPath: string;
  private readonly tmpPath: string;
  private logFd: number;
  private logRecords = 0;

  constructor(dir: string) {
    this.logPath = path.join(dir, "tally.log");
    this.tmpPath = path.join(dir, "tally.log.tmp");
    fs.rmSync(this.tmpPath, { force: true });
    this.recover();
    this.logFd = fs.openSync(this.logPath, "a");
  }

  // Replays the valid prefix of the log and truncates everything after it.
  private recover(): void {
    let text: string;
    try {
      text = fs.readFileSync(this.logPath, "latin1");
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code === "ENOENT") {
        return;
      }
      throw err;
    }
    let validLength = 0;
    let start = 0;
    while (true) {
      const newline = text.indexOf("\n", start);
      if (newline < 0) {
        break;
      }
      const m = RECORD_RE.exec(text.slice(start, newline));
      if (!m) {
        break;
      }
      if (m[1] !== undefined) {
        this.counters.set(m[1], BigInt(m[2]));
      } else if (m[3] !== undefined) {
        this.counters.set(m[3], (this.counters.get(m[3]) ?? 0n) + BigInt(m[4]));
      } else {
        this.counters.delete(m[5]);
      }
      this.logRecords++;
      start = newline + 1;
      validLength = start;
    }
    if (validLength < text.length) {
      fs.truncateSync(this.logPath, validLength);
    }
  }

  private append(record: string): void {
    fs.writeSync(this.logFd, record + "\n");
    this.logRecords++;
  }

  handle(line: string): string {
    const tokens = line.split(" ");
    const [command, name, value] = tokens;
    const hasName = tokens.length >= 2 && NAME_RE.test(name);
    const hasValue = tokens.length === 3 && INT_RE.test(value);

    switch (command) {
      case "SET":
        if (tokens.length !== 3 || !hasName || !hasValue) {
          break;
        }
        this.append(`S ${name} ${BigInt(value)}`);
        this.counters.set(name, BigInt(value));
        return "OK";
      case "ADD": {
        if (tokens.length !== 3 || !hasName || !hasValue) {
          break;
        }
        const delta = BigInt(value);
        const result = (this.counters.get(name) ?? 0n) + delta;
        this.append(`A ${name} ${delta}`);
        this.counters.set(name, result);
        return String(result);
      }
      case "GET":
        if (tokens.length !== 2 || !hasName) {
          break;
        }
        return this.counters.get(name)?.toString() ?? "NONE";
      case "DEL":
        if (tokens.length !== 2 || !hasName) {
          break;
        }
        if (!this.counters.has(name)) {
          return "NONE";
        }
        this.append(`D ${name}`);
        this.counters.delete(name);
        return "OK";
      case "LIST":
        if (tokens.length !== 1) {
          break;
        }
        return [String(this.counters.size), ...this.sortedEntries().map(([k, v]) => `${k}=${v}`)].join(" ");
      case "INFO":
        if (tokens.length !== 1) {
          break;
        }
        return `counters=${this.counters.size} log_records=${this.logRecords}`;
      case "COMPACT":
        if (tokens.length !== 1) {
          break;
        }
        return `OK ${this.compact()}`;
    }
    return "ERR bad command";
  }

  private sortedEntries(): [string, bigint][] {
    return [...this.counters.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  }

  private compact(): number {
    const records: string[] = [];
    for (const [name, value] of this.sortedEntries()) {
      records.push(...compactRecords(name, value));
    }
    const fd = fs.openSync(this.tmpPath, "w");
    try {
      fs.writeSync(fd, records.map((record) => record + "\n").join(""));
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.closeSync(this.logFd);
    fs.renameSync(this.tmpPath, this.logPath);
    this.logFd = fs.openSync(this.logPath, "a");
    this.logRecords = records.length;
    return records.length;
  }
}

// One S record per counter; values too large for a single record are
// written as an S record followed by A records so the log stays replayable.
function compactRecords(name: string, value: bigint): string[] {
  const negative = value < 0n;
  let remaining = negative ? -value : value;
  const sign = negative ? -1n : 1n;
  const first = remaining > MAX_RECORD_INT ? MAX_RECORD_INT : remaining;
  const records = [`S ${name} ${sign * first}`];
  remaining -= first;
  while (remaining > 0n) {
    const chunk = remaining > MAX_RECORD_INT ? MAX_RECORD_INT : remaining;
    records.push(`A ${name} ${sign * chunk}`);
    remaining -= chunk;
  }
  return records;
}

function prepareDirectory(dir: string): boolean {
  try {
    const stat = fs.statSync(dir, { throwIfNoEntry: false });
    if (stat === undefined) {
      fs.mkdirSync(dir);
      return true;
    }
    return stat.isDirectory();
  } catch {
    return false;
  }
}

function main(argv: string[]): void {
  if (argv.length !== 1) {
    process.stderr.write("usage: tally DIR\n");
    process.exitCode = 2;
    return;
  }
  const dir = argv[0];
  if (!prepareDirectory(dir)) {
    process.stderr.write(`tally: cannot use directory ${dir}\n`);
    process.exitCode = 1;
    return;
  }
  let store: Store;
  try {
    store = new Store(dir);
  } catch (err) {
    process.stderr.write(`tally: ${(err as Error).message}\n`);
    process.exitCode = 1;
    return;
  }

  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(store.handle(line) + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let start = 0;
    let newline = pending.indexOf("\n", start);
    while (newline >= 0) {
      respond(pending.slice(start, newline));
      start = newline + 1;
      newline = pending.indexOf("\n", start);
    }
    pending = pending.slice(start);
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main(process.argv.slice(2));

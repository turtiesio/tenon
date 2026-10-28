import {
  closeSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  statSync,
  truncateSync,
  unlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { join } from "node:path";

const NAME = "[a-z][a-z0-9_]{0,31}";
const INT = "-?[0-9]{1,15}";
const NAME_RE = new RegExp(`^${NAME}$`);
const INT_RE = new RegExp(`^${INT}$`);
const RECORD_RE = new RegExp(`^(?:([SA]) (${NAME}) (${INT})|(D) (${NAME}))$`);

const BAD_COMMAND = "ERR bad command";

class Store {
  private counters = new Map<string, bigint>();
  private logRecords = 0;
  private logFd: number;
  private readonly logPath: string;
  private readonly tmpPath: string;

  constructor(dir: string) {
    this.logPath = join(dir, "tally.log");
    this.tmpPath = join(dir, "tally.log.tmp");
    this.removeStaleTemp();
    this.recover();
    this.logFd = openSync(this.logPath, "a");
  }

  private removeStaleTemp(): void {
    try {
      unlinkSync(this.tmpPath);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
        throw error;
      }
    }
  }

  // Replays the valid prefix of the log and truncates anything after it.
  private recover(): void {
    let text: string;
    try {
      text = readFileSync(this.logPath, "latin1");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        return;
      }
      throw error;
    }

    let validLength = 0;
    let start = 0;
    while (true) {
      const newline = text.indexOf("\n", start);
      if (newline < 0) {
        break;
      }
      const match = RECORD_RE.exec(text.slice(start, newline));
      if (match === null) {
        break;
      }
      if (match[4] === "D") {
        this.counters.delete(match[5]);
      } else if (match[1] === "S") {
        this.counters.set(match[2], BigInt(match[3]));
      } else {
        this.counters.set(match[2], (this.counters.get(match[2]) ?? 0n) + BigInt(match[3]));
      }
      this.logRecords++;
      start = newline + 1;
      validLength = start;
    }
    if (validLength < text.length) {
      truncateSync(this.logPath, validLength);
    }
  }

  private append(record: string): void {
    writeSync(this.logFd, record + "\n");
    this.logRecords++;
  }

  handle(line: string): string {
    const tokens = line.split(" ");
    switch (tokens[0]) {
      case "SET":
      case "ADD": {
        if (tokens.length !== 3 || !NAME_RE.test(tokens[1]) || !INT_RE.test(tokens[2])) {
          return BAD_COMMAND;
        }
        const name = tokens[1];
        const number = BigInt(tokens[2]);
        if (tokens[0] === "SET") {
          this.append(`S ${name} ${number}`);
          this.counters.set(name, number);
          return "OK";
        }
        this.append(`A ${name} ${number}`);
        const total = (this.counters.get(name) ?? 0n) + number;
        this.counters.set(name, total);
        return String(total);
      }
      case "GET": {
        if (tokens.length !== 2 || !NAME_RE.test(tokens[1])) {
          return BAD_COMMAND;
        }
        const value = this.counters.get(tokens[1]);
        return value === undefined ? "NONE" : String(value);
      }
      case "DEL": {
        if (tokens.length !== 2 || !NAME_RE.test(tokens[1])) {
          return BAD_COMMAND;
        }
        if (!this.counters.has(tokens[1])) {
          return "NONE";
        }
        this.append(`D ${tokens[1]}`);
        this.counters.delete(tokens[1]);
        return "OK";
      }
      case "LIST": {
        if (tokens.length !== 1) {
          return BAD_COMMAND;
        }
        const parts = [String(this.counters.size)];
        for (const [name, value] of this.sortedCounters()) {
          parts.push(`${name}=${value}`);
        }
        return parts.join(" ");
      }
      case "INFO":
        if (tokens.length !== 1) {
          return BAD_COMMAND;
        }
        return `counters=${this.counters.size} log_records=${this.logRecords}`;
      case "COMPACT":
        if (tokens.length !== 1) {
          return BAD_COMMAND;
        }
        return this.compact();
      default:
        return BAD_COMMAND;
    }
  }

  private sortedCounters(): [string, bigint][] {
    return [...this.counters.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  }

  private compact(): string {
    const records = this.sortedCounters().map(([name, value]) => `S ${name} ${value}\n`);
    const fd = openSync(this.tmpPath, "w");
    try {
      writeFileSync(fd, records.join(""));
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    renameSync(this.tmpPath, this.logPath);
    closeSync(this.logFd);
    this.logFd = openSync(this.logPath, "a");
    this.logRecords = records.length;
    return `OK ${records.length}`;
  }
}

function prepareDirectory(dir: string): boolean {
  try {
    if (!statSync(dir, { throwIfNoEntry: false })) {
      mkdirSync(dir);
    }
    return statSync(dir).isDirectory();
  } catch {
    return false;
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.error("usage: tally DIR");
    process.exitCode = 2;
    return;
  }
  if (!prepareDirectory(args[0])) {
    console.error(`cannot use data directory: ${args[0]}`);
    process.exitCode = 1;
    return;
  }

  let store: Store;
  try {
    store = new Store(args[0]);
  } catch (error) {
    console.error(`cannot open store: ${(error as Error).message}`);
    process.exitCode = 1;
    return;
  }

  let pending = "";
  const respond = (rawLine: string) => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(store.handle(line) + "\n");
  };

  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline = pending.indexOf("\n");
    while (newline >= 0) {
      respond(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
      newline = pending.indexOf("\n");
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") {
      respond(pending);
    }
  });
}

main();

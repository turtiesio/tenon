import {
  closeSync,
  existsSync,
  ftruncateSync,
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

interface Bookmark {
  url: string;
  tags: Set<string>;
}

type Command =
  | { op: "ADD"; name: string; url: string }
  | { op: "DEL"; name: string }
  | { op: "TAG"; name: string; tag: string }
  | { op: "UNTAG"; name: string; tag: string }
  | { op: "GET"; name: string }
  | { op: "FIND"; tag: string }
  | { op: "COMPACT" };

const NAME = /^[a-z0-9-]{1,20}$/;
const URL_RE = /^[\x21-\x7E]{1,200}$/;
const TAG = /^[a-z0-9]{1,12}$/;
const NUMBER = /^(0|[1-9][0-9]*)$/;

class DataError extends Error {}

// Returns null for a line that is not exactly one of the command forms.
function parseCommand(line: string): Command | null {
  const t = line.split(" ");
  switch (t[0]) {
    case "ADD":
      return t.length === 3 && NAME.test(t[1]) && URL_RE.test(t[2]) ? { op: "ADD", name: t[1], url: t[2] } : null;
    case "DEL":
      return t.length === 2 && NAME.test(t[1]) ? { op: "DEL", name: t[1] } : null;
    case "TAG":
    case "UNTAG":
      return t.length === 3 && NAME.test(t[1]) && TAG.test(t[2]) ? { op: t[0], name: t[1], tag: t[2] } : null;
    case "GET":
      return t.length === 2 && NAME.test(t[1]) ? { op: "GET", name: t[1] } : null;
    case "FIND":
      return t.length === 2 && TAG.test(t[1]) ? { op: "FIND", tag: t[1] } : null;
    case "COMPACT":
      return t.length === 1 ? { op: "COMPACT" } : null;
    default:
      return null;
  }
}

function tagList(tags: Set<string>): string {
  return tags.size === 0 ? "-" : [...tags].sort().join(",");
}

class Store {
  readonly bookmarks = new Map<string, Bookmark>();

  // Applies a state-changing or reading command; COMPACT is handled by the caller.
  apply(cmd: Command): string {
    switch (cmd.op) {
      case "ADD":
        if (this.bookmarks.has(cmd.name)) return "ERR exists";
        this.bookmarks.set(cmd.name, { url: cmd.url, tags: new Set() });
        return "OK";
      case "DEL":
        return this.bookmarks.delete(cmd.name) ? "OK" : "ERR no such bookmark";
      case "TAG": {
        const b = this.bookmarks.get(cmd.name);
        if (b === undefined) return "ERR no such bookmark";
        if (b.tags.has(cmd.tag)) return "UNCHANGED";
        b.tags.add(cmd.tag);
        return "OK";
      }
      case "UNTAG": {
        const b = this.bookmarks.get(cmd.name);
        if (b === undefined) return "ERR no such bookmark";
        return b.tags.delete(cmd.tag) ? "OK" : "UNCHANGED";
      }
      case "GET": {
        const b = this.bookmarks.get(cmd.name);
        return b === undefined ? "ERR no such bookmark" : `${cmd.name} ${b.url} ${tagList(b.tags)}`;
      }
      case "FIND": {
        const names = [...this.bookmarks].filter(([, b]) => b.tags.has(cmd.tag)).map(([n]) => n).sort();
        return names.length === 0 ? "-" : names.join(" ");
      }
      case "COMPACT":
        throw new Error("COMPACT is not applied to the store");
    }
  }

  snapshotText(seq: number): string {
    const lines = [...this.bookmarks.keys()].sort().map((n) => {
      const b = this.bookmarks.get(n)!;
      return `${n} ${b.url} ${tagList(b.tags)}\n`;
    });
    return `bookmarks ${seq}\n${lines.join("")}`;
  }
}

// Strictly increasing in byte order (ASCII, so code-unit order is byte order).
function strictlyIncreasing(items: string[]): boolean {
  return items.every((x, i) => i === 0 || items[i - 1] < x);
}

function loadSnapshot(path: string, store: Store): number {
  const text = readFileSync(path, "latin1");
  if (!text.endsWith("\n")) throw new DataError("snapshot does not end with a newline");
  const lines = text.slice(0, -1).split("\n");
  const header = /^bookmarks (0|[1-9][0-9]*)$/.exec(lines[0]);
  if (header === null) throw new DataError("bad snapshot header");
  const body = lines.slice(1);
  const names: string[] = [];
  for (const line of body) {
    const t = line.split(" ");
    if (t.length !== 3 || !NAME.test(t[0]) || !URL_RE.test(t[1])) throw new DataError(`bad snapshot line: ${line}`);
    let tags: string[] = [];
    if (t[2] !== "-") {
      tags = t[2].split(",");
      if (!tags.every((x) => TAG.test(x)) || !strictlyIncreasing(tags)) throw new DataError(`bad tags: ${line}`);
    }
    names.push(t[0]);
    store.bookmarks.set(t[0], { url: t[1], tags: new Set(tags) });
  }
  if (!strictlyIncreasing(names)) throw new DataError("snapshot names are not strictly increasing");
  return Number(header[1]);
}

interface Loaded {
  store: Store;
  lastSeq: number;
  journalKeep: number; // bytes of the journal to keep (up to the last newline)
}

function load(dir: string): Loaded {
  const store = new Store();
  const snapshotPath = join(dir, "snapshot");
  const snapshotSeq = existsSync(snapshotPath) ? loadSnapshot(snapshotPath, store) : 0;

  const journalPath = join(dir, "journal");
  const raw = existsSync(journalPath) ? readFileSync(journalPath, "latin1") : "";
  const keep = raw.lastIndexOf("\n") + 1; // everything after it is a torn record
  const lines = keep === 0 ? [] : raw.slice(0, keep - 1).split("\n");

  const seqs: number[] = [];
  const records: { seq: number; cmd: Command }[] = [];
  for (const line of lines) {
    const space = line.indexOf(" ");
    const seqText = space === -1 ? line : line.slice(0, space);
    const cmd = space === -1 ? null : parseCommand(line.slice(space + 1));
    if (!NUMBER.test(seqText) || cmd === null || !["ADD", "DEL", "TAG", "UNTAG"].includes(cmd.op)) {
      throw new DataError(`bad journal record: ${line}`);
    }
    const seq = Number(seqText);
    if (seqs.length > 0 && seq !== seqs[seqs.length - 1] + 1) throw new DataError("journal sequence numbers are not consecutive");
    seqs.push(seq);
    records.push({ seq, cmd });
  }
  if (seqs.length > 0 && (seqs[0] > snapshotSeq + 1 || seqs[seqs.length - 1] < snapshotSeq)) {
    throw new DataError("journal does not continue the snapshot");
  }
  for (const { seq, cmd } of records) {
    if (seq <= snapshotSeq) continue;
    if (store.apply(cmd) !== "OK") throw new DataError(`journal record ${seq} does not apply`);
  }
  const lastSeq = seqs.length > 0 ? Math.max(snapshotSeq, seqs[seqs.length - 1]) : snapshotSeq;
  return { store, lastSeq, journalKeep: keep };
}

function fail(message: string, code: number): never {
  process.stderr.write(`bookmarks: ${message}\n`);
  process.exit(code);
}

function ensureDirectory(dir: string): void {
  if (!existsSync(dir)) {
    try {
      mkdirSync(dir);
    } catch (e) {
      fail(`cannot create ${dir}: ${(e as Error).message}`, 1);
    }
  }
  if (!statSync(dir).isDirectory()) fail(`${dir} is not a directory`, 1);
}

function writeAll(fd: number, text: string): void {
  const buf = Buffer.from(text, "latin1");
  let offset = 0;
  while (offset < buf.length) {
    try {
      offset += writeSync(fd, buf, offset);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e;
    }
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) fail("usage: bookmarks DIR", 2);
  const dir = args[0];
  ensureDirectory(dir);

  const tmpPath = join(dir, "snapshot.tmp");
  const journalPath = join(dir, "journal");
  const snapshotPath = join(dir, "snapshot");

  let loaded: Loaded;
  try {
    loaded = load(dir);
  } catch (e) {
    if (e instanceof DataError || (e as NodeJS.ErrnoException).code !== undefined) {
      fail(`unusable data directory: ${(e as Error).message}`, 1);
    }
    throw e;
  }
  const { store } = loaded;
  let lastSeq = loaded.lastSeq;

  if (existsSync(tmpPath)) unlinkSync(tmpPath);
  if (existsSync(journalPath)) truncateSync(journalPath, loaded.journalKeep);
  const journal = openSync(journalPath, "a");

  const compact = (): string => {
    writeFileSync(tmpPath, store.snapshotText(lastSeq), "latin1");
    renameSync(tmpPath, snapshotPath);
    ftruncateSync(journal, 0);
    return `OK ${lastSeq}`;
  };

  const handle = (line: string): string => {
    const cmd = parseCommand(line);
    if (cmd === null) return "ERR bad command";
    if (cmd.op === "COMPACT") return compact();
    const response = store.apply(cmd);
    if (response === "OK" && cmd.op !== "GET" && cmd.op !== "FIND") {
      // The record must be in the file before the response is printed.
      lastSeq += 1;
      writeAll(journal, `${lastSeq} ${line}\n`);
    }
    return response;
  };

  const processLine = (raw: string): void => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    writeAll(1, handle(line) + "\n");
  };

  // Split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline: number;
    while ((newline = pending.indexOf("\n")) !== -1) {
      processLine(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") processLine(pending);
    closeSync(journal);
  });
}

main();

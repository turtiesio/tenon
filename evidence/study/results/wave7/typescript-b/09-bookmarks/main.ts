import * as fs from "node:fs";
import * as path from "node:path";

type Command =
  | { kind: "ADD"; name: string; url: string }
  | { kind: "DEL"; name: string }
  | { kind: "TAG" | "UNTAG"; name: string; tag: string }
  | { kind: "GET"; name: string }
  | { kind: "FIND"; tag: string }
  | { kind: "COMPACT" };

interface Bookmark {
  url: string;
  tags: Set<string>;
}

type State = Map<string, Bookmark>;

class DataError extends Error {}

const NAME = /^[a-z0-9-]{1,20}$/;
const URL = /^[!-~]{1,200}$/;
const TAG = /^[a-z0-9]{1,12}$/;

function byteOrder(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function parseCommand(line: string): Command | null {
  const t = line.split(" ");
  switch (t[0]) {
    case "ADD":
      return t.length === 3 && NAME.test(t[1]) && URL.test(t[2]) ? { kind: "ADD", name: t[1], url: t[2] } : null;
    case "DEL":
    case "GET":
      return t.length === 2 && NAME.test(t[1]) ? { kind: t[0], name: t[1] } : null;
    case "TAG":
    case "UNTAG":
      return t.length === 3 && NAME.test(t[1]) && TAG.test(t[2]) ? { kind: t[0], name: t[1], tag: t[2] } : null;
    case "FIND":
      return t.length === 2 && TAG.test(t[1]) ? { kind: "FIND", tag: t[1] } : null;
    case "COMPACT":
      return t.length === 1 ? { kind: "COMPACT" } : null;
    default:
      return null;
  }
}

function isRecordable(cmd: Command): boolean {
  return cmd.kind === "ADD" || cmd.kind === "DEL" || cmd.kind === "TAG" || cmd.kind === "UNTAG";
}

function formatTags(tags: Set<string>): string {
  return tags.size === 0 ? "-" : [...tags].sort(byteOrder).join(",");
}

/** Applies a command other than COMPACT to the state and returns its response. */
function apply(state: State, cmd: Exclude<Command, { kind: "COMPACT" }>): string {
  if (cmd.kind === "FIND") {
    const names = [...state.entries()].filter(([, b]) => b.tags.has(cmd.tag)).map(([n]) => n).sort(byteOrder);
    return names.length === 0 ? "-" : names.join(" ");
  }
  if (cmd.kind === "ADD") {
    if (state.has(cmd.name)) return "ERR exists";
    state.set(cmd.name, { url: cmd.url, tags: new Set() });
    return "OK";
  }
  const bookmark = state.get(cmd.name);
  if (bookmark === undefined) return "ERR no such bookmark";
  switch (cmd.kind) {
    case "DEL":
      state.delete(cmd.name);
      return "OK";
    case "GET":
      return `${cmd.name} ${bookmark.url} ${formatTags(bookmark.tags)}`;
    case "TAG":
      if (bookmark.tags.has(cmd.tag)) return "UNCHANGED";
      bookmark.tags.add(cmd.tag);
      return "OK";
    case "UNTAG":
      if (!bookmark.tags.has(cmd.tag)) return "UNCHANGED";
      bookmark.tags.delete(cmd.tag);
      return "OK";
  }
}

function readIfExists(file: string): string | null {
  try {
    return fs.readFileSync(file, "latin1");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw new DataError(`cannot read ${file}: ${(e as Error).message}`);
  }
}

function loadSnapshot(file: string): { state: State; seq: number } {
  const state: State = new Map();
  const text = readIfExists(file);
  if (text === null) return { state, seq: 0 };
  if (!text.endsWith("\n")) throw new DataError("snapshot does not end with a newline");
  const lines = text.slice(0, -1).split("\n");
  const header = /^bookmarks (0|[1-9][0-9]*)$/.exec(lines[0]);
  if (header === null) throw new DataError("bad snapshot header");
  let previous: string | null = null;
  for (const line of lines.slice(1)) {
    const t = line.split(" ");
    if (t.length !== 3 || !NAME.test(t[0]) || !URL.test(t[1])) throw new DataError(`bad snapshot line: ${line}`);
    if (previous !== null && t[0] <= previous) throw new DataError("snapshot names are not strictly increasing");
    previous = t[0];
    const tags = t[2] === "-" ? [] : t[2].split(",");
    for (let i = 0; i < tags.length; i++) {
      if (!TAG.test(tags[i]) || (i > 0 && tags[i] <= tags[i - 1])) throw new DataError(`bad snapshot tags: ${line}`);
    }
    state.set(t[0], { url: t[1], tags: new Set(tags) });
  }
  return { state, seq: Number(header[1]) };
}

interface Store {
  state: State;
  lastSeq: number;
  journalFd: number;
  dir: string;
}

function openStore(dir: string): Store {
  try {
    fs.mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw new DataError(`cannot create ${dir}: ${(e as Error).message}`);
  }
  if (!fs.statSync(dir).isDirectory()) throw new DataError(`${dir} is not a directory`);

  fs.rmSync(path.join(dir, "snapshot.tmp"), { force: true });
  const { state, seq: snapshotSeq } = loadSnapshot(path.join(dir, "snapshot"));

  const journalPath = path.join(dir, "journal");
  const journal = readIfExists(journalPath) ?? "";
  const completeLength = journal.lastIndexOf("\n") + 1;
  const records = journal.slice(0, completeLength).split("\n");
  records.pop(); // the empty string after the last "\n"

  let lastRecord: number | null = null;
  for (const record of records) {
    const m = /^([1-9][0-9]*) (.*)$/.exec(record);
    const cmd = m === null ? null : parseCommand(m[2]);
    if (m === null || cmd === null || !isRecordable(cmd)) throw new DataError(`bad journal record: ${record}`);
    const seq = Number(m[1]);
    if (lastRecord === null) {
      if (seq > snapshotSeq + 1) throw new DataError("journal starts after a gap");
    } else if (seq !== lastRecord + 1) {
      throw new DataError("journal sequence numbers are not consecutive");
    }
    lastRecord = seq;
    if (seq <= snapshotSeq) continue;
    if (apply(state, cmd as Exclude<Command, { kind: "COMPACT" }>) !== "OK") {
      throw new DataError(`journal record ${seq} does not apply`);
    }
  }
  if (lastRecord !== null && lastRecord < snapshotSeq) throw new DataError("journal ends before the snapshot");

  if (completeLength < journal.length) fs.truncateSync(journalPath, completeLength);
  const journalFd = fs.openSync(journalPath, "a");
  return { state, lastSeq: Math.max(snapshotSeq, lastRecord ?? 0), journalFd, dir };
}

function compact(store: Store): string {
  const lines = [`bookmarks ${store.lastSeq}`];
  for (const name of [...store.state.keys()].sort(byteOrder)) {
    const b = store.state.get(name)!;
    lines.push(`${name} ${b.url} ${formatTags(b.tags)}`);
  }
  const tmp = path.join(store.dir, "snapshot.tmp");
  const fd = fs.openSync(tmp, "w");
  fs.writeSync(fd, lines.map((l) => l + "\n").join(""));
  fs.fsyncSync(fd);
  fs.closeSync(fd);
  fs.renameSync(tmp, path.join(store.dir, "snapshot"));
  fs.ftruncateSync(store.journalFd, 0);
  return `OK ${store.lastSeq}`;
}

function execute(store: Store, line: string): string {
  const cmd = parseCommand(line);
  if (cmd === null) return "ERR bad command";
  if (cmd.kind === "COMPACT") return compact(store);
  const response = apply(store.state, cmd);
  if (response === "OK" && isRecordable(cmd)) {
    store.lastSeq += 1;
    fs.writeSync(store.journalFd, `${store.lastSeq} ${line}\n`);
  }
  return response;
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    process.stderr.write("usage: bookmarks DIR\n");
    process.exit(2);
  }

  let store: Store;
  try {
    store = openStore(args[0]);
  } catch (e) {
    if (e instanceof DataError) {
      process.stderr.write(`bookmarks: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    fs.writeSync(1, execute(store, line) + "\n");
  };

  // Lines are split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) !== -1) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();

import * as fs from "node:fs";
import * as path from "node:path";

class FatalError extends Error {}

interface Item {
  id: number;
  prio: number;
  done: boolean;
  text: string;
}

interface State {
  next: number;
  /** Items keyed by id; Map keeps insertion order, which is always id order. */
  items: Map<number, Item>;
}

const TEXT = /^[\x20-\x7e]+$/;
const ITEM_LINE = /^([1-9][0-9]{0,8}) ([1-9]) ([od]) ([\x20-\x7e]+)$/;

function parseState(content: string, file: string): State {
  const invalid = (msg: string): never => {
    throw new FatalError(`${file}: invalid state file: ${msg}`);
  };
  if (!content.endsWith("\n")) invalid("missing final newline");
  const lines = content.slice(0, -1).split("\n");
  if (lines[0] !== "TODO 1") invalid("bad header");
  const nextMatch = /^next ([1-9][0-9]{0,8})$/.exec(lines[1] ?? "");
  if (!nextMatch) invalid("bad next line");
  const next = Number(nextMatch![1]);
  const items = new Map<number, Item>();
  let lastId = 0;
  for (let i = 2; i < lines.length; i++) {
    const m = ITEM_LINE.exec(lines[i]);
    if (!m) invalid(`bad item on line ${i + 1}`);
    const id = Number(m![1]);
    if (id <= lastId) invalid(`ids not increasing on line ${i + 1}`);
    if (id >= next) invalid(`id ${id} not smaller than next on line ${i + 1}`);
    lastId = id;
    items.set(id, { id, prio: Number(m![2]), done: m![3] === "d", text: m![4] });
  }
  return { next, items };
}

function serialize(state: State): string {
  let out = `TODO 1\nnext ${state.next}\n`;
  for (const item of state.items.values()) {
    out += `${item.id} ${item.prio} ${item.done ? "d" : "o"} ${item.text}\n`;
  }
  return out;
}

class TodoStore {
  private readonly dbPath: string;
  private readonly tmpPath: string;
  private state: State;

  constructor(dir: string) {
    this.dbPath = path.join(dir, "todo.db");
    this.tmpPath = path.join(dir, "todo.db.tmp");
    fs.rmSync(this.tmpPath, { force: true });
    let content: string | undefined;
    try {
      content = fs.readFileSync(this.dbPath, "latin1");
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "ENOENT") {
        throw new FatalError(`cannot read ${this.dbPath}: ${(e as Error).message}`);
      }
    }
    this.state = content === undefined ? { next: 1, items: new Map() } : parseState(content, this.dbPath);
  }

  /** Atomically replaces the state file with the current state. */
  private save(): void {
    const fd = fs.openSync(this.tmpPath, "w");
    try {
      fs.writeSync(fd, serialize(this.state), null, "latin1");
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(this.tmpPath, this.dbPath);
  }

  private openItems(): Item[] {
    return [...this.state.items.values()].filter((i) => !i.done).sort((a, b) => a.prio - b.prio || a.id - b.id);
  }

  private static show(item: Item): string {
    return `${item.id} ${item.prio} ${item.done ? "done" : "open"} ${item.text}`;
  }

  execute(line: string): string {
    let m: RegExpExecArray | null;
    if ((m = /^ADD ([1-9]) (.+)$/s.exec(line)) && TEXT.test(m[2])) {
      const id = this.state.next++;
      this.state.items.set(id, { id, prio: Number(m[1]), done: false, text: m[2] });
      this.save();
      return `ADDED ${id}`;
    }
    if ((m = /^DONE ([0-9]{1,9})$/.exec(line))) {
      const item = this.state.items.get(Number(m[1]));
      if (!item) return "ERR no such item";
      if (item.done) return "ERR already done";
      item.done = true;
      this.save();
      return "OK";
    }
    if ((m = /^SHOW ([0-9]{1,9})$/.exec(line))) {
      const item = this.state.items.get(Number(m[1]));
      return item ? TodoStore.show(item) : "ERR no such item";
    }
    switch (line) {
      case "LIST":
        return ["OPEN", ...this.openItems().map((i) => i.id)].join(" ");
      case "NEXT": {
        const first = this.openItems()[0];
        return first ? TodoStore.show(first) : "NONE";
      }
      case "PURGE": {
        const done = [...this.state.items.values()].filter((i) => i.done);
        for (const item of done) this.state.items.delete(item.id);
        if (done.length > 0) this.save();
        return `PURGED ${done.length}`;
      }
      case "STATS": {
        const all = [...this.state.items.values()];
        const done = all.filter((i) => i.done).length;
        return `open=${all.length - done} done=${done} next_id=${this.state.next}`;
      }
    }
    return "ERR bad command";
  }
}

function openDirectory(dir: string): void {
  try {
    fs.mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") {
      throw new FatalError(`cannot create ${dir}: ${(e as Error).message}`);
    }
  }
  if (!fs.statSync(dir).isDirectory()) throw new FatalError(`${dir} is not a directory`);
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    process.stderr.write("usage: todo DIR\n");
    process.exitCode = 2;
    return;
  }
  let store: TodoStore;
  try {
    openDirectory(args[0]);
    store = new TodoStore(args[0]);
  } catch (e) {
    if (e instanceof FatalError) {
      process.stderr.write(`todo: ${e.message}\n`);
      process.exitCode = 1;
      return;
    }
    throw e;
  }
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    // Synchronous write so each response is flushed before the next command is read.
    fs.writeSync(1, store.execute(line) + "\n");
  };
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) >= 0) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending.length > 0) respond(pending);
  });
}

main();

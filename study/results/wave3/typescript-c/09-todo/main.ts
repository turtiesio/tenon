import {
  closeSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  writeSync,
} from "node:fs";
import { join } from "node:path";

class StateError extends Error {}

interface Item {
  id: number;
  prio: number;
  done: boolean;
  text: string;
}

const ITEM_LINE = /^([1-9][0-9]{0,8}) ([1-9]) ([od]) ([\x20-\x7e]+)$/;

class Todo {
  private items = new Map<number, Item>();
  private next = 1;

  private readonly dir: string;

  constructor(dir: string) {
    this.dir = dir;
  }

  private get path(): string {
    return join(this.dir, "todo.db");
  }

  private get tmpPath(): string {
    return join(this.dir, "todo.db.tmp");
  }

  load(): void {
    rmSync(this.tmpPath, { force: true });
    let text: string;
    try {
      text = readFileSync(this.path).toString("latin1");
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") return;
      throw new StateError(`cannot read ${this.path}`);
    }
    this.parse(text);
  }

  private parse(text: string): void {
    if (!text.endsWith("\n")) throw new StateError("state file does not end with a newline");
    const lines = text.slice(0, -1).split("\n");
    if (lines[0] !== "TODO 1") throw new StateError("bad state file header");
    const nextMatch = lines[1]?.match(/^next ([1-9][0-9]{0,8})$/);
    if (!nextMatch) throw new StateError("bad next line");
    const next = Number(nextMatch[1]);
    const items = new Map<number, Item>();
    let last = 0;
    for (const line of lines.slice(2)) {
      const m = line.match(ITEM_LINE);
      if (!m) throw new StateError(`bad item line: ${line}`);
      const id = Number(m[1]);
      if (id <= last || id >= next) throw new StateError(`bad item id: ${id}`);
      last = id;
      items.set(id, { id, prio: Number(m[2]), done: m[3] === "d", text: m[4] });
    }
    this.items = items;
    this.next = next;
  }

  // Writes a temporary file and renames it over the real one.
  private save(): void {
    let out = `TODO 1\nnext ${this.next}\n`;
    for (const item of this.items.values()) {
      out += `${item.id} ${item.prio} ${item.done ? "d" : "o"} ${item.text}\n`;
    }
    const fd = openSync(this.tmpPath, "w");
    try {
      writeSync(fd, out);
      fsyncSync(fd);
    } finally {
      closeSync(fd);
    }
    renameSync(this.tmpPath, this.path);
  }

  private show(item: Item): string {
    return `${item.id} ${item.prio} ${item.done ? "done" : "open"} ${item.text}`;
  }

  private openItems(): Item[] {
    return [...this.items.values()]
      .filter((item) => !item.done)
      .sort((a, b) => a.prio - b.prio || a.id - b.id);
  }

  execute(line: string): string {
    let m: RegExpMatchArray | null;
    if ((m = line.match(/^ADD ([1-9]) ([\x20-\x7e]+)$/))) {
      const id = this.next++;
      this.items.set(id, { id, prio: Number(m[1]), done: false, text: m[2] });
      this.save();
      return `ADDED ${id}`;
    }
    if ((m = line.match(/^DONE ([0-9]{1,9})$/))) {
      const item = this.items.get(Number(m[1]));
      if (!item) return "ERR no such item";
      if (item.done) return "ERR already done";
      item.done = true;
      this.save();
      return "OK";
    }
    if ((m = line.match(/^SHOW ([0-9]{1,9})$/))) {
      const item = this.items.get(Number(m[1]));
      return item ? this.show(item) : "ERR no such item";
    }
    switch (line) {
      case "LIST":
        return ["OPEN", ...this.openItems().map((i) => i.id)].join(" ");
      case "NEXT": {
        const first = this.openItems()[0];
        return first ? this.show(first) : "NONE";
      }
      case "PURGE": {
        const doneIds = [...this.items.values()].filter((i) => i.done).map((i) => i.id);
        if (doneIds.length === 0) return "PURGED 0";
        for (const id of doneIds) this.items.delete(id);
        this.save();
        return `PURGED ${doneIds.length}`;
      }
      case "STATS": {
        const open = this.openItems().length;
        return `open=${open} done=${this.items.size - open} next_id=${this.next}`;
      }
    }
    return "ERR bad command";
  }
}

// Writes straight to the descriptor, so a response is out before the next command is read.
function writeLine(text: string): void {
  const data = Buffer.from(text + "\n", "latin1");
  let offset = 0;
  while (offset < data.length) {
    try {
      offset += writeSync(1, data, offset);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e;
    }
  }
}

function fail(message: string, code: number): never {
  process.stderr.write(`todo: ${message}\n`);
  process.exit(code);
}

function openDirectory(dir: string): void {
  try {
    mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") fail(`cannot create ${dir}`, 1);
  }
  if (!statSync(dir).isDirectory()) fail(`${dir} is not a directory`, 1);
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) fail("usage: todo DIR", 2);
  const dir = args[0];
  openDirectory(dir);
  const todo = new Todo(dir);
  try {
    todo.load();
  } catch (e) {
    if (e instanceof StateError) fail(e.message, 1);
    throw e;
  }

  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    writeLine(todo.execute(line));
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
    if (pending !== "") respond(pending);
  });
}

main();

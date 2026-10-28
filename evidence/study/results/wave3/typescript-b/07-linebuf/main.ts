import * as fs from "node:fs";

/** A change replaces `removed` with `inserted` starting at 0-based `index`. */
interface Change {
  index: number;
  removed: string[];
  inserted: string[];
}

const NUM = "([0-9]{1,9})";
const FORMS = {
  append: /^APPEND (.*)$/s,
  insert: new RegExp(`^INSERT ${NUM} (.*)$`, "s"),
  delete: new RegExp(`^DELETE ${NUM}(?: ${NUM})?$`),
  replace: new RegExp(`^REPLACE ${NUM} (.*)$`, "s"),
  print: new RegExp(`^PRINT ${NUM}$`),
  find: /^FIND (.+)$/s,
};

class LineBuffer {
  private lines: string[] = [];
  private undoStack: Change[] = [];
  private redoStack: Change[] = [];

  private ok(): string {
    return `OK ${this.lines.length}`;
  }

  private apply(change: Change): string {
    this.lines.splice(change.index, change.removed.length, ...change.inserted);
    this.undoStack.push(change);
    this.redoStack = [];
    return this.ok();
  }

  /** True if n is a 1-based line number of an existing line. */
  private valid(n: number): boolean {
    return n >= 1 && n <= this.lines.length;
  }

  execute(command: string): string {
    let m: RegExpExecArray | null;
    if ((m = FORMS.append.exec(command))) {
      return this.apply({ index: this.lines.length, removed: [], inserted: [m[1]] });
    }
    if ((m = FORMS.insert.exec(command))) {
      const n = Number(m[1]);
      if (n < 1 || n > this.lines.length + 1) return "ERR bad line";
      return this.apply({ index: n - 1, removed: [], inserted: [m[2]] });
    }
    if ((m = FORMS.delete.exec(command))) {
      const a = Number(m[1]);
      const b = m[2] === undefined ? a : Number(m[2]);
      if (!this.valid(a) || !this.valid(b) || a > b) return "ERR bad line";
      return this.apply({ index: a - 1, removed: this.lines.slice(a - 1, b), inserted: [] });
    }
    if ((m = FORMS.replace.exec(command))) {
      const n = Number(m[1]);
      if (!this.valid(n)) return "ERR bad line";
      return this.apply({ index: n - 1, removed: [this.lines[n - 1]], inserted: [m[2]] });
    }
    if ((m = FORMS.print.exec(command))) {
      const n = Number(m[1]);
      if (!this.valid(n)) return "ERR bad line";
      return `${n}|${this.lines[n - 1]}`;
    }
    if ((m = FORMS.find.exec(command))) {
      const needle = m[1];
      const found: number[] = [];
      this.lines.forEach((line, i) => {
        if (line.includes(needle)) found.push(i + 1);
      });
      return found.length > 0 ? found.join(" ") : "NONE";
    }
    switch (command) {
      case "COUNT":
        return String(this.lines.length);
      case "UNDO": {
        const change = this.undoStack.pop();
        if (!change) return "ERR nothing to undo";
        this.lines.splice(change.index, change.inserted.length, ...change.removed);
        this.redoStack.push(change);
        return this.ok();
      }
      case "REDO": {
        const change = this.redoStack.pop();
        if (!change) return "ERR nothing to redo";
        this.lines.splice(change.index, change.removed.length, ...change.inserted);
        this.undoStack.push(change);
        return this.ok();
      }
    }
    return "ERR bad command";
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("linebuf: takes no arguments\nusage: linebuf\n");
    process.exitCode = 2;
    return;
  }
  const buffer = new LineBuffer();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    // Synchronous write so each response is flushed before the next command is read.
    fs.writeSync(1, buffer.execute(line) + "\n");
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

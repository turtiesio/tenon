// A change replaces `removed` lines at `index` with `added` lines.
interface Change {
  index: number;
  removed: string[];
  added: string[];
}

class Editor {
  private lines: string[] = [];
  private undoStack: Change[] = [];
  private redoStack: Change[] = [];

  private apply(change: Change, forward: boolean): void {
    const [from, to] = forward ? [change.removed, change.added] : [change.added, change.removed];
    this.lines.splice(change.index, from.length, ...to);
  }

  private commit(change: Change): string {
    this.apply(change, true);
    this.undoStack.push(change);
    this.redoStack = [];
    return `OK ${this.lines.length}`;
  }

  private validLine(n: number, max: number): boolean {
    return n >= 1 && n <= max;
  }

  execute(line: string): string {
    let m: RegExpMatchArray | null;
    if (line.startsWith("APPEND ")) {
      return this.commit({ index: this.lines.length, removed: [], added: [line.slice(7)] });
    }
    if ((m = line.match(/^INSERT ([0-9]{1,9}) (.*)$/s))) {
      const n = Number(m[1]);
      if (!this.validLine(n, this.lines.length + 1)) return "ERR bad line";
      return this.commit({ index: n - 1, removed: [], added: [m[2]] });
    }
    if ((m = line.match(/^DELETE ([0-9]{1,9})(?: ([0-9]{1,9}))?$/))) {
      const a = Number(m[1]);
      const b = m[2] === undefined ? a : Number(m[2]);
      if (!this.validLine(a, this.lines.length) || b < a || b > this.lines.length) {
        return "ERR bad line";
      }
      return this.commit({ index: a - 1, removed: this.lines.slice(a - 1, b), added: [] });
    }
    if ((m = line.match(/^REPLACE ([0-9]{1,9}) (.*)$/s))) {
      const n = Number(m[1]);
      if (!this.validLine(n, this.lines.length)) return "ERR bad line";
      return this.commit({ index: n - 1, removed: [this.lines[n - 1]], added: [m[2]] });
    }
    if ((m = line.match(/^PRINT ([0-9]{1,9})$/))) {
      const n = Number(m[1]);
      if (!this.validLine(n, this.lines.length)) return "ERR bad line";
      return `${n}|${this.lines[n - 1]}`;
    }
    if (line.startsWith("FIND ") && line.length > 5) {
      const needle = line.slice(5);
      const found: number[] = [];
      this.lines.forEach((text, i) => {
        if (text.includes(needle)) found.push(i + 1);
      });
      return found.length > 0 ? found.join(" ") : "NONE";
    }
    switch (line) {
      case "COUNT":
        return String(this.lines.length);
      case "UNDO": {
        const change = this.undoStack.pop();
        if (!change) return "ERR nothing to undo";
        this.apply(change, false);
        this.redoStack.push(change);
        return `OK ${this.lines.length}`;
      }
      case "REDO": {
        const change = this.redoStack.pop();
        if (!change) return "ERR nothing to redo";
        this.apply(change, true);
        this.undoStack.push(change);
        return `OK ${this.lines.length}`;
      }
    }
    return "ERR bad command";
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("linebuf: takes no arguments\n");
    process.exitCode = 2;
    return;
  }
  const editor = new Editor();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(editor.execute(line) + "\n");
  };
  // Lines are split on "\n" only, and each is answered as soon as it is complete.
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

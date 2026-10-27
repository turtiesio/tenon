import * as fs from "node:fs";

const LIMIT = 1_000_000_000_000;
const CELL = /^[A-Z][1-9][0-9]?$/;
const LITERAL = /^-?[0-9]{1,9}$/;

type Term =
  | { kind: "number"; value: number }
  | { kind: "cell"; name: string }
  | { kind: "sum"; cells: string[] };

interface Contents {
  source: string;
  /** For a literal: its value. */
  literal?: number;
  /** For a formula: signed terms and every referenced cell. */
  terms?: Array<{ sign: 1 | -1; term: Term }>;
  references: Set<string>;
}

function rectangle(a: string, b: string): string[] {
  const colA = a.charCodeAt(0);
  const colB = b.charCodeAt(0);
  const rowA = Number(a.slice(1));
  const rowB = Number(b.slice(1));
  const cells: string[] = [];
  for (let c = Math.min(colA, colB); c <= Math.max(colA, colB); c++) {
    for (let r = Math.min(rowA, rowB); r <= Math.max(rowA, rowB); r++) {
      cells.push(String.fromCharCode(c) + r);
    }
  }
  return cells;
}

const TERM = /SUM\(([A-Z][1-9][0-9]?):([A-Z][1-9][0-9]?)\)|([A-Z][1-9][0-9]?)|([0-9]{1,9})/y;

function readTerm(text: string, pos: number): { term: Term; end: number } | null {
  TERM.lastIndex = pos;
  const m = TERM.exec(text);
  if (!m) return null;
  let term: Term;
  if (m[1] !== undefined) term = { kind: "sum", cells: rectangle(m[1], m[2]) };
  else if (m[3] !== undefined) term = { kind: "cell", name: m[3] };
  else term = { kind: "number", value: Number(m[4]) };
  return { term, end: TERM.lastIndex };
}

function parseContents(source: string): Contents | null {
  if (LITERAL.test(source)) return { source, literal: Number(source), references: new Set() };
  if (!source.startsWith("=")) return null;
  const terms: Array<{ sign: 1 | -1; term: Term }> = [];
  let pos = 1;
  let sign: 1 | -1 = 1;
  if (source[pos] === "-") {
    sign = -1;
    pos++;
  }
  for (;;) {
    const read = readTerm(source, pos);
    if (!read) return null;
    terms.push({ sign, term: read.term });
    pos = read.end;
    if (pos === source.length) break;
    if (source[pos] === "+") sign = 1;
    else if (source[pos] === "-") sign = -1;
    else return null;
    pos++;
  }
  const references = new Set<string>();
  for (const { term } of terms) {
    if (term.kind === "cell") references.add(term.name);
    else if (term.kind === "sum") term.cells.forEach((c) => references.add(c));
  }
  return { source, terms, references };
}

class Sheet {
  private cells = new Map<string, Contents>();
  /** Values computed since the last change; null means overflow. */
  private cache = new Map<string, number | null>();

  set(name: string, contents: Contents): boolean {
    if (this.wouldCycle(name, contents)) return false;
    this.cells.set(name, contents);
    this.cache.clear();
    return true;
  }

  clear(name: string): void {
    this.cells.delete(name);
    this.cache.clear();
  }

  show(name: string): string {
    return this.cells.get(name)?.source ?? "EMPTY";
  }

  /** Returns the cell's value, or null on overflow. */
  value(name: string): number | null {
    const cached = this.cache.get(name);
    if (cached !== undefined) return cached;
    const result = this.compute(name);
    this.cache.set(name, result);
    return result;
  }

  private compute(name: string): number | null {
    const contents = this.cells.get(name);
    if (!contents) return 0;
    if (contents.literal !== undefined) return contents.literal;
    let total = 0;
    for (const { sign, term } of contents.terms!) {
      let v: number | null;
      if (term.kind === "number") v = term.value;
      else if (term.kind === "cell") v = this.value(term.name);
      else {
        v = 0;
        for (const c of term.cells) {
          const cv = this.value(c);
          if (cv === null) return null;
          v += cv;
        }
      }
      if (v === null) return null;
      total += sign * v;
    }
    return Math.abs(total) > LIMIT ? null : total;
  }

  /** True if `name` would depend on itself after storing `contents`. */
  private wouldCycle(name: string, contents: Contents): boolean {
    const visited = new Set<string>();
    const stack = [...contents.references];
    while (stack.length > 0) {
      const cell = stack.pop()!;
      if (cell === name) return true;
      if (visited.has(cell)) continue;
      visited.add(cell);
      const refs = this.cells.get(cell)?.references;
      if (refs) stack.push(...refs);
    }
    return false;
  }
}

function execute(sheet: Sheet, line: string): string {
  const tokens = line.split(" ");
  const [command, cell] = tokens;
  if (cell === undefined || !CELL.test(cell)) return "ERR bad command";
  if (command === "SET" && tokens.length === 3) {
    const contents = parseContents(tokens[2]);
    if (!contents) return "ERR bad command";
    return sheet.set(cell, contents) ? "OK" : "ERR cycle";
  }
  if (tokens.length !== 2) return "ERR bad command";
  switch (command) {
    case "CLEAR":
      sheet.clear(cell);
      return "OK";
    case "GET": {
      const v = sheet.value(cell);
      return v === null ? "ERR overflow" : String(v);
    }
    case "SHOW":
      return sheet.show(cell);
  }
  return "ERR bad command";
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("sheet: takes no arguments\nusage: sheet\n");
    process.exitCode = 2;
    return;
  }
  const sheet = new Sheet();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    // Synchronous write so each response is flushed before the next command is read.
    fs.writeSync(1, execute(sheet, line) + "\n");
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

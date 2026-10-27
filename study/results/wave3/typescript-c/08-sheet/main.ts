const CELL = /^[A-Z][1-9][0-9]?$/;
const LITERAL = /^-?[0-9]{1,9}$/;
const TERM = /[0-9]{1,9}|[A-Z][1-9][0-9]?|SUM\([A-Z][1-9][0-9]?:[A-Z][1-9][0-9]?\)/y;
const LIMIT = 1_000_000_000_000n;

type Term =
  | { kind: "number"; value: bigint }
  | { kind: "cell"; name: string }
  | { kind: "sum"; cells: string[] };

interface Signed {
  negative: boolean;
  term: Term;
}

type Contents =
  | { kind: "literal"; value: bigint }
  | { kind: "formula"; terms: Signed[]; refs: string[] };

interface Cell {
  text: string;
  contents: Contents;
}

function rectangle(from: string, to: string): string[] {
  const cols = [from.charCodeAt(0), to.charCodeAt(0)].sort((a, b) => a - b);
  const rows = [Number(from.slice(1)), Number(to.slice(1))].sort((a, b) => a - b);
  const cells: string[] = [];
  for (let c = cols[0]; c <= cols[1]; c++) {
    for (let r = rows[0]; r <= rows[1]; r++) cells.push(String.fromCharCode(c) + r);
  }
  return cells;
}

function parseTerm(text: string): Term {
  if (text.startsWith("SUM(")) {
    const [from, to] = text.slice(4, -1).split(":");
    return { kind: "sum", cells: rectangle(from, to) };
  }
  if (CELL.test(text)) return { kind: "cell", name: text };
  return { kind: "number", value: BigInt(text) };
}

// Returns null if the text is neither an integer literal nor a valid formula.
function parseContents(text: string): Contents | null {
  if (LITERAL.test(text)) return { kind: "literal", value: BigInt(text) };
  if (!text.startsWith("=")) return null;
  let pos = 1;
  const terms: Signed[] = [];
  let negative = false;
  if (text[pos] === "-") {
    negative = true;
    pos++;
  }
  for (;;) {
    TERM.lastIndex = pos;
    const m = TERM.exec(text);
    if (!m) return null;
    terms.push({ negative, term: parseTerm(m[0]) });
    pos += m[0].length;
    if (pos === text.length) break;
    if (text[pos] !== "+" && text[pos] !== "-") return null;
    negative = text[pos] === "-";
    pos++;
  }
  const refs = terms.flatMap(({ term }) =>
    term.kind === "cell" ? [term.name] : term.kind === "sum" ? term.cells : [],
  );
  return { kind: "formula", terms, refs };
}

class Sheet {
  private cells = new Map<string, Cell>();
  // Computed values; null means overflow. Cleared on every change.
  private cache = new Map<string, bigint | null>();

  private references(name: string): string[] {
    const contents = this.cells.get(name)?.contents;
    return contents?.kind === "formula" ? contents.refs : [];
  }

  // Would `name` depend on itself if it referenced `refs`?
  private makesCycle(name: string, refs: string[]): boolean {
    const seen = new Set<string>();
    const pending = [...refs];
    for (let next = pending.pop(); next !== undefined; next = pending.pop()) {
      if (next === name) return true;
      if (seen.has(next)) continue;
      seen.add(next);
      pending.push(...this.references(next));
    }
    return false;
  }

  // Evaluates dependencies first with an explicit stack, so long chains of
  // formulas cannot overflow the call stack.
  private value(name: string): bigint | null {
    const stack = [name];
    for (let top = stack.pop(); top !== undefined; top = stack.pop()) {
      if (this.cache.has(top)) continue;
      const missing = this.references(top).filter((ref) => !this.cache.has(ref));
      if (missing.length === 0) {
        this.cache.set(top, this.compute(top));
      } else {
        stack.push(top, ...missing);
      }
    }
    return this.cache.get(name)!;
  }

  private compute(name: string): bigint | null {
    const contents = this.cells.get(name)?.contents;
    if (!contents) return 0n;
    if (contents.kind === "literal") return contents.value;
    let total = 0n;
    let overflow = false;
    const add = (v: bigint | null, negative: boolean) => {
      if (v === null) overflow = true;
      else total += negative ? -v : v;
    };
    for (const { negative, term } of contents.terms) {
      switch (term.kind) {
        case "number":
          add(term.value, negative);
          break;
        case "cell":
          add(this.value(term.name), negative);
          break;
        case "sum": {
          let sum = 0n;
          for (const cell of term.cells) {
            const v = this.value(cell);
            if (v === null) overflow = true;
            else sum += v;
          }
          add(sum, negative);
          break;
        }
      }
    }
    if (overflow || total > LIMIT || total < -LIMIT) return null;
    return total;
  }

  set(name: string, text: string, contents: Contents): string {
    if (contents.kind === "formula" && this.makesCycle(name, contents.refs)) return "ERR cycle";
    this.cells.set(name, { text, contents });
    this.cache.clear();
    return "OK";
  }

  clear(name: string): string {
    this.cells.delete(name);
    this.cache.clear();
    return "OK";
  }

  get(name: string): string {
    const v = this.value(name);
    return v === null ? "ERR overflow" : v.toString();
  }

  show(name: string): string {
    return this.cells.get(name)?.text ?? "EMPTY";
  }
}

function execute(sheet: Sheet, line: string): string {
  const tokens = line.split(" ");
  const [command, name] = tokens;
  if (name === undefined || !CELL.test(name)) return "ERR bad command";
  switch (command) {
    case "SET": {
      if (tokens.length !== 3) break;
      const contents = parseContents(tokens[2]);
      if (contents === null) break;
      return sheet.set(name, tokens[2], contents);
    }
    case "CLEAR":
      if (tokens.length === 2) return sheet.clear(name);
      break;
    case "GET":
      if (tokens.length === 2) return sheet.get(name);
      break;
    case "SHOW":
      if (tokens.length === 2) return sheet.show(name);
      break;
  }
  return "ERR bad command";
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("sheet: takes no arguments\n");
    process.exitCode = 2;
    return;
  }
  const sheet = new Sheet();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(execute(sheet, line) + "\n");
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

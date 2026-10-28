import * as fs from "node:fs";
import * as path from "node:path";

const URL_RE = /^[!-~]{1,200}$/;
const CODE_RE = /^[0-9a-z]{1,8}$/;
const RECORD_RE = /^([1-9][0-9]{0,8}) ([PHD]) ([!-~]+)$/;

interface Link {
  url: string;
  hits: number;
}

// Link state plus the journal it is persisted in.
class Store {
  private readonly links = new Map<string, Link>();
  private nextId = 1;
  private records = 0;
  private readonly fd: number;

  constructor(journalPath: string) {
    const validBytes = this.replay(journalPath);
    if (fs.existsSync(journalPath) && fs.statSync(journalPath).size !== validBytes) {
      fs.truncateSync(journalPath, validBytes);
    }
    this.fd = fs.openSync(journalPath, "a");
  }

  // Replays the longest valid prefix of the journal and returns its length in bytes.
  private replay(journalPath: string): number {
    if (!fs.existsSync(journalPath)) return 0;
    // latin1 keeps character offsets equal to byte offsets.
    const text = fs.readFileSync(journalPath, "latin1");
    let offset = 0;
    for (;;) {
      const nl = text.indexOf("\n", offset);
      if (nl < 0) break; // torn (unterminated) final line
      if (!this.applyRecord(text.slice(offset, nl))) break;
      offset = nl + 1;
    }
    return offset;
  }

  private applyRecord(line: string): boolean {
    const m = RECORD_RE.exec(line);
    if (m === null || Number(m[1]) !== this.records + 1) return false;
    const [, , kind, arg] = m;
    if (kind === "P") {
      if (!URL_RE.test(arg)) return false;
      this.links.set(Store.codeOf(this.nextId++), { url: arg, hits: 0 });
    } else {
      const link = CODE_RE.test(arg) ? this.links.get(arg) : undefined;
      if (link === undefined) return false;
      if (kind === "H") link.hits++;
      else this.links.delete(arg);
    }
    this.records++;
    return true;
  }

  private static codeOf(id: number): string {
    return id.toString(36);
  }

  private append(kind: string, arg: string): void {
    fs.writeSync(this.fd, `${this.records + 1} ${kind} ${arg}\n`);
    this.records++;
  }

  put(url: string): string {
    this.append("P", url);
    const code = Store.codeOf(this.nextId++);
    this.links.set(code, { url, hits: 0 });
    return `CODE ${code}`;
  }

  get(code: string): string {
    const link = this.links.get(code);
    if (link === undefined) return "ERR not found";
    this.append("H", code);
    link.hits++;
    return `URL ${link.url}`;
  }

  hits(code: string): string {
    const link = this.links.get(code);
    return link === undefined ? "ERR not found" : `HITS ${link.hits}`;
  }

  del(code: string): string {
    if (!this.links.has(code)) return "ERR not found";
    this.append("D", code);
    this.links.delete(code);
    return "OK";
  }

  info(): string {
    return `links=${this.links.size} next=${Store.codeOf(this.nextId)} records=${this.records}`;
  }
}

function handle(store: Store, line: string): string {
  const tokens = line.split(" ");
  const [cmd, arg] = tokens;
  if (cmd === "PUT" && tokens.length === 2 && URL_RE.test(arg)) return store.put(arg);
  if (tokens.length === 2 && CODE_RE.test(arg)) {
    if (cmd === "GET") return store.get(arg);
    if (cmd === "HITS") return store.hits(arg);
    if (cmd === "DEL") return store.del(arg);
  }
  if (cmd === "INFO" && tokens.length === 1) return store.info();
  return "ERR bad command";
}

function openStore(dir: string): Store | null {
  try {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir);
    if (!fs.statSync(dir).isDirectory()) throw new Error(`${dir} is not a directory`);
    return new Store(path.join(dir, "journal"));
  } catch (e) {
    console.error(`shorten: cannot use ${dir}: ${(e as Error).message}`);
    return null;
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    console.error("usage: shorten DIR");
    process.exitCode = 2;
    return;
  }
  const store = openStore(args[0]);
  if (store === null) {
    process.exitCode = 1;
    return;
  }

  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(handle(store, line) + "\n");
  };

  // Split on "\n" by hand and answer each line as soon as it is complete.
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl = pending.indexOf("\n");
    while (nl >= 0) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
      nl = pending.indexOf("\n");
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();

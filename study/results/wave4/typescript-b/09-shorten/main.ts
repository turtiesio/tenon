import * as fs from "node:fs";
import * as path from "node:path";
import * as readline from "node:readline";

const URL_RE = "[!-~]{1,200}";
const CODE_RE = "[0-9a-z]{1,8}";
const COMMAND_PUT = new RegExp(`^PUT (${URL_RE})$`);
const COMMAND_CODE = new RegExp(`^(GET|HITS|DEL) (${CODE_RE})$`);
const RECORD = new RegExp(`^([1-9][0-9]{0,8}) (?:P (${URL_RE})|([HD]) (${CODE_RE}))$`);

interface Link {
  url: string;
  hits: number;
}

function toCode(id: number): string {
  return id.toString(36);
}

/** The id of a code in canonical form (no leading zeros), or null. */
function fromCode(code: string): number | null {
  const id = parseInt(code, 36);
  return toCode(id) === code ? id : null;
}

class Store {
  private readonly links = new Map<number, Link>();
  private nextId = 1;
  records = 0;

  find(code: string): Link | undefined {
    const id = fromCode(code);
    return id === null ? undefined : this.links.get(id);
  }

  put(url: string): string {
    const id = this.nextId++;
    this.links.set(id, { url, hits: 0 });
    return toCode(id);
  }

  hit(code: string): void {
    this.find(code)!.hits++;
  }

  delete(code: string): void {
    this.links.delete(fromCode(code)!);
  }

  info(): string {
    return `links=${this.links.size} next=${toCode(this.nextId)} records=${this.records}`;
  }
}

/** Replays the valid prefix of the journal text; returns its length in bytes. */
function replay(text: string, store: Store): number {
  let offset = 0;
  while (true) {
    const end = text.indexOf("\n", offset);
    if (end < 0) break;
    const m = RECORD.exec(text.slice(offset, end));
    if (m === null || Number(m[1]) !== store.records + 1) break;
    const [, , url, kind, code] = m;
    if (url !== undefined) {
      store.put(url);
    } else {
      if (store.find(code) === undefined) break;
      if (kind === "H") store.hit(code);
      else store.delete(code);
    }
    store.records++;
    offset = end + 1;
  }
  return offset;
}

function openDataDir(dir: string): void {
  try {
    fs.mkdirSync(dir);
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code !== "EEXIST") {
      process.stderr.write(`shorten: cannot create ${dir}: ${(err as Error).message}\n`);
      process.exit(1);
    }
  }
  if (!fs.statSync(dir).isDirectory()) {
    process.stderr.write(`shorten: ${dir} is not a directory\n`);
    process.exit(1);
  }
}

function loadJournal(file: string, store: Store): number {
  let text: string;
  try {
    text = fs.readFileSync(file, "latin1");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") text = "";
    else throw err;
  }
  const valid = replay(text, store);
  if (valid < text.length) fs.truncateSync(file, valid);
  return fs.openSync(file, "a");
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    process.stderr.write("usage: shorten DIR\n");
    process.exit(2);
  }
  const dir = args[0];
  openDataDir(dir);

  const store = new Store();
  const journalPath = path.join(dir, "journal");
  let journal: number;
  try {
    journal = loadJournal(journalPath, store);
  } catch (err) {
    process.stderr.write(`shorten: cannot use ${journalPath}: ${(err as Error).message}\n`);
    process.exit(1);
  }

  const append = (record: string): void => {
    fs.writeSync(journal, `${store.records + 1} ${record}\n`);
    store.records++;
  };

  const handle = (line: string): string => {
    const put = COMMAND_PUT.exec(line);
    if (put !== null) {
      append(`P ${put[1]}`);
      return `CODE ${store.put(put[1])}`;
    }
    const m = COMMAND_CODE.exec(line);
    if (m !== null) {
      const [, cmd, code] = m;
      const link = store.find(code);
      if (link === undefined) return "ERR not found";
      switch (cmd) {
        case "GET":
          append(`H ${code}`);
          store.hit(code);
          return `URL ${link.url}`;
        case "HITS":
          return `HITS ${link.hits}`;
        default:
          append(`D ${code}`);
          store.delete(code);
          return "OK";
      }
    }
    if (line === "INFO") return store.info();
    return "ERR bad command";
  };

  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (raw) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(handle(line) + "\n");
  });
  rl.on("close", () => fs.closeSync(journal));
}

main();

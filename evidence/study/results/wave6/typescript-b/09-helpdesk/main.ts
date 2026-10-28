import * as fs from "node:fs";
import * as path from "node:path";

interface Ticket {
  id: number;
  customer: string;
  title: string;
  agent: string | null;
  open: boolean;
}

type Command =
  | { kind: "open"; customer: string; title: string; id?: number }
  | { kind: "assign"; id: number; agent: string }
  | { kind: "close"; id: number }
  | { kind: "reopen"; id: number }
  | { kind: "show"; id: number }
  | { kind: "queue"; agent: string | null };

const NAME = "[a-z0-9]{1,12}";
const TICKET = "T([1-9][0-9]{0,8})";
const OPEN_RE = new RegExp(`^OPEN (${NAME}) (.*)$`, "s");
const OPEN_RECORD_RE = new RegExp(`^OPEN ${TICKET} (${NAME}) (.*)$`, "s");
const ASSIGN_RE = new RegExp(`^ASSIGN ${TICKET} (${NAME})$`);
const CLOSE_RE = new RegExp(`^CLOSE ${TICKET}$`);
const REOPEN_RE = new RegExp(`^REOPEN ${TICKET}$`);
const SHOW_RE = new RegExp(`^SHOW ${TICKET}$`);
const QUEUE_RE = new RegExp(`^QUEUE (${NAME}|-)$`);
const TITLE_RE = /^[\x20-\x7e]{1,60}$/;

function isValidTitle(title: string): boolean {
  return TITLE_RE.test(title) && !title.startsWith(" ") && !title.endsWith(" ");
}

/** Parses a state-changing command (or, for journal records, an OPEN with its number). */
function parseChange(line: string, isRecord: boolean): Command | null {
  let m: RegExpExecArray | null;
  if (isRecord) {
    if ((m = OPEN_RECORD_RE.exec(line)) && isValidTitle(m[3])) {
      return { kind: "open", id: Number(m[1]), customer: m[2], title: m[3] };
    }
  } else if ((m = OPEN_RE.exec(line)) && isValidTitle(m[2])) {
    return { kind: "open", customer: m[1], title: m[2] };
  }
  if ((m = ASSIGN_RE.exec(line))) return { kind: "assign", id: Number(m[1]), agent: m[2] };
  if ((m = CLOSE_RE.exec(line))) return { kind: "close", id: Number(m[1]) };
  if ((m = REOPEN_RE.exec(line))) return { kind: "reopen", id: Number(m[1]) };
  return null;
}

function parseCommand(line: string): Command | null {
  const change = parseChange(line, false);
  if (change) return change;
  let m: RegExpExecArray | null;
  if ((m = SHOW_RE.exec(line))) return { kind: "show", id: Number(m[1]) };
  if ((m = QUEUE_RE.exec(line))) return { kind: "queue", agent: m[1] === "-" ? null : m[1] };
  return null;
}

class Desk {
  tickets: Ticket[] = []; // ticket n is at index n - 1

  get nextId(): number {
    return this.tickets.length + 1;
  }

  /**
   * Checks a command against the current state without changing anything.
   * Returns the response it would get; state-changing commands that would
   * succeed return "OK" (or "T<n>" for OPEN).
   */
  check(cmd: Command): string {
    if (cmd.kind === "open") return `T${this.nextId}`;
    if (cmd.kind === "queue") return "";
    const t = this.tickets[cmd.id - 1];
    if (t === undefined) return "ERR no such ticket";
    switch (cmd.kind) {
      case "assign":
        if (!t.open) return "ERR closed";
        return t.agent === cmd.agent ? "UNCHANGED" : "OK";
      case "close":
        return t.open ? "OK" : "ERR closed";
      case "reopen":
        return t.open ? "ERR not closed" : "OK";
      case "show":
        return "";
    }
  }

  /** Applies a command that check() accepted. */
  apply(cmd: Command): void {
    switch (cmd.kind) {
      case "open":
        this.tickets.push({ id: this.nextId, customer: cmd.customer, title: cmd.title, agent: null, open: true });
        break;
      case "assign":
        this.tickets[cmd.id - 1].agent = cmd.agent;
        break;
      case "close":
        this.tickets[cmd.id - 1].open = false;
        break;
      case "reopen":
        this.tickets[cmd.id - 1].open = true;
        break;
    }
  }

  show(id: number): string {
    const t = this.tickets[id - 1];
    return `T${t.id} ${t.open ? "open" : "closed"} ${t.customer} ${t.agent ?? "-"} ${t.title}`;
  }

  queue(agent: string | null): string {
    const ids = this.tickets.filter((t) => t.open && t.agent === agent).map((t) => `T${t.id}`);
    return ids.length === 0 ? "-" : ids.join(" ");
  }
}

class StartupError extends Error {}

/** Loads the journal into a fresh Desk, truncating a torn last record. */
function load(journal: string): Desk {
  const desk = new Desk();
  let data: string;
  try {
    data = fs.readFileSync(journal, "latin1");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return desk;
    throw new StartupError(`cannot read ${journal}: ${(e as Error).message}`);
  }
  const complete = data.lastIndexOf("\n") + 1;
  const lines = data.slice(0, complete).split("\n");
  lines.pop(); // the empty string after the final "\n"
  lines.forEach((line, i) => {
    const cmd = parseChange(line, true);
    if (cmd === null) throw new StartupError(`${journal}:${i + 1}: malformed record`);
    if (cmd.kind === "open") {
      if (cmd.id !== desk.nextId) throw new StartupError(`${journal}:${i + 1}: expected ticket T${desk.nextId}`);
    } else if (desk.check(cmd) !== "OK") {
      throw new StartupError(`${journal}:${i + 1}: record does not apply`);
    }
    desk.apply(cmd);
  });
  if (complete < data.length) fs.truncateSync(journal, complete);
  return desk;
}

function writeAll(fd: number, text: string): void {
  const buf = Buffer.from(text, "latin1");
  let offset = 0;
  while (offset < buf.length) {
    try {
      offset += fs.writeSync(fd, buf, offset);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e;
    }
  }
}

function prepareDir(dir: string): void {
  try {
    fs.mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") {
      throw new StartupError(`cannot create ${dir}: ${(e as Error).message}`);
    }
  }
  if (!fs.statSync(dir).isDirectory()) throw new StartupError(`${dir} is not a directory`);
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) {
    process.stderr.write("usage: helpdesk DIR\n");
    process.exitCode = 2;
    return;
  }
  const journal = path.join(args[0], "tickets.log");
  let desk: Desk;
  try {
    prepareDir(args[0]);
    desk = load(journal);
  } catch (e) {
    if (!(e instanceof StartupError)) throw e;
    process.stderr.write(`helpdesk: ${e.message}\n`);
    process.exitCode = 1;
    return;
  }

  let journalFd: number | null = null;
  const record = (text: string): void => {
    if (journalFd === null) journalFd = fs.openSync(journal, "a");
    writeAll(journalFd, text + "\n");
  };

  const handle = (line: string): string => {
    const cmd = parseCommand(line);
    if (cmd === null) return "ERR bad command";
    const verdict = desk.check(cmd);
    if (cmd.kind === "queue") return desk.queue(cmd.agent);
    if (verdict.startsWith("ERR")) return verdict;
    if (cmd.kind === "show") return desk.show(cmd.id);
    if (verdict === "UNCHANGED") return verdict;
    if (cmd.kind === "open") {
      record(`OPEN T${desk.nextId} ${cmd.customer} ${cmd.title}`);
    } else {
      record(line);
    }
    desk.apply(cmd);
    return verdict;
  };

  const respond = (raw: string): void => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    writeAll(1, handle(line) + "\n");
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
    if (journalFd !== null) fs.closeSync(journalFd);
  });
}

main();

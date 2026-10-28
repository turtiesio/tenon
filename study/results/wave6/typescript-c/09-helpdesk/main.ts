import { appendFileSync, mkdirSync, readFileSync, statSync, truncateSync } from "node:fs";
import { join } from "node:path";

interface Ticket {
  number: number;
  open: boolean;
  customer: string;
  agent: string | null;
  title: string;
}

type Command =
  | { kind: "OPEN"; customer: string; title: string }
  | { kind: "ASSIGN"; ticket: number; agent: string }
  | { kind: "CLOSE" | "REOPEN" | "SHOW"; ticket: number }
  | { kind: "QUEUE"; agent: string | null };

interface Outcome {
  response: string;
  record: string | null; // journal line (without newline) when the state changed
}

const NAME = "[a-z0-9]{1,12}";
const TICKET = "T([1-9][0-9]{0,8})";
const TITLE = "([\\x20-\\x7e]{1,60})";
const NAME_RE = new RegExp(`^${NAME}$`);
const TICKET_RE = new RegExp(`^${TICKET}$`);
const OPEN_RE = new RegExp(`^OPEN (${NAME}) ${TITLE}$`);
const OPEN_RECORD_RE = new RegExp(`^OPEN ${TICKET} (${NAME}) ${TITLE}$`);

function validTitle(title: string): boolean {
  return !title.startsWith(" ") && !title.endsWith(" ");
}

function parseTicket(token: string): number | null {
  const m = TICKET_RE.exec(token);
  return m ? Number(m[1]) : null;
}

/** Parses a client command line; null if it is not exactly one of the valid forms. */
function parseCommand(line: string): Command | null {
  if (line.startsWith("OPEN ")) {
    const m = OPEN_RE.exec(line);
    return m && validTitle(m[2]) ? { kind: "OPEN", customer: m[1], title: m[2] } : null;
  }
  const t = line.split(" ");
  switch (t[0]) {
    case "ASSIGN": {
      const ticket = t.length === 3 ? parseTicket(t[1]) : null;
      return ticket !== null && NAME_RE.test(t[2]) ? { kind: "ASSIGN", ticket, agent: t[2] } : null;
    }
    case "CLOSE":
    case "REOPEN":
    case "SHOW": {
      const ticket = t.length === 2 ? parseTicket(t[1]) : null;
      return ticket !== null ? { kind: t[0], ticket } : null;
    }
    case "QUEUE":
      if (t.length === 2 && t[1] === "-") return { kind: "QUEUE", agent: null };
      if (t.length === 2 && NAME_RE.test(t[1])) return { kind: "QUEUE", agent: t[1] };
      return null;
  }
  return null;
}

class Helpdesk {
  private tickets: Ticket[] = []; // tickets[n - 1] is ticket Tn

  private get nextNumber(): number {
    return this.tickets.length + 1;
  }

  execute(cmd: Command): Outcome {
    const reply = (response: string): Outcome => ({ response, record: null });
    switch (cmd.kind) {
      case "OPEN": {
        const number = this.nextNumber;
        this.tickets.push({ number, open: true, customer: cmd.customer, agent: null, title: cmd.title });
        return { response: `T${number}`, record: `OPEN T${number} ${cmd.customer} ${cmd.title}` };
      }
      case "QUEUE": {
        const numbers = this.tickets.filter((t) => t.open && t.agent === cmd.agent).map((t) => `T${t.number}`);
        return reply(numbers.join(" ") || "-");
      }
    }

    const ticket = this.tickets[cmd.ticket - 1];
    if (!ticket) return reply("ERR no such ticket");
    switch (cmd.kind) {
      case "SHOW":
        return reply(
          `T${ticket.number} ${ticket.open ? "open" : "closed"} ${ticket.customer} ${ticket.agent ?? "-"} ${ticket.title}`,
        );
      case "ASSIGN":
        if (!ticket.open) return reply("ERR closed");
        if (ticket.agent === cmd.agent) return reply("UNCHANGED");
        ticket.agent = cmd.agent;
        return { response: "OK", record: `ASSIGN T${ticket.number} ${cmd.agent}` };
      case "CLOSE":
        if (!ticket.open) return reply("ERR closed");
        ticket.open = false;
        return { response: "OK", record: `CLOSE T${ticket.number}` };
      case "REOPEN":
        if (ticket.open) return reply("ERR not closed");
        ticket.open = true;
        return { response: "OK", record: `REOPEN T${ticket.number}` };
    }
  }

  /** Applies one journal line; false if it is not a valid record at this point. */
  replay(line: string): boolean {
    const open = OPEN_RECORD_RE.exec(line);
    if (line.startsWith("OPEN ")) {
      if (!open || !validTitle(open[3]) || Number(open[1]) !== this.nextNumber) return false;
      this.execute({ kind: "OPEN", customer: open[2], title: open[3] });
      return true;
    }
    const cmd = parseCommand(line);
    if (!cmd || cmd.kind === "SHOW" || cmd.kind === "QUEUE") return false;
    return this.execute(cmd).response === "OK";
  }
}

function fail(message: string, code: number): never {
  process.stderr.write(`helpdesk: ${message}\n`);
  process.exit(code);
}

/** Creates the data directory if needed and returns the journal path. */
function prepareDirectory(dir: string): string {
  try {
    mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") fail(`cannot create '${dir}': ${(e as Error).message}`, 1);
  }
  try {
    if (!statSync(dir).isDirectory()) fail(`'${dir}' is not a directory`, 1);
  } catch (e) {
    fail(`cannot use '${dir}': ${(e as Error).message}`, 1);
  }
  return join(dir, "tickets.log");
}

function loadJournal(path: string, desk: Helpdesk): void {
  let text: string;
  try {
    text = readFileSync(path, "latin1");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return;
    fail(`cannot read journal: ${(e as Error).message}`, 1);
  }
  const end = text.lastIndexOf("\n") + 1; // everything after this is a torn record
  const lines = text.slice(0, end).split("\n");
  lines.pop();
  lines.forEach((line, i) => {
    if (!desk.replay(line)) fail(`invalid journal record at line ${i + 1}`, 1);
  });
  if (end < text.length) {
    try {
      truncateSync(path, end);
    } catch (e) {
      fail(`cannot truncate journal: ${(e as Error).message}`, 1);
    }
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) fail("usage: helpdesk DIR", 2);

  const journal = prepareDirectory(args[0]);
  const desk = new Helpdesk();
  loadJournal(journal, desk);

  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    const cmd = parseCommand(line);
    let response = "ERR bad command";
    if (cmd) {
      const outcome = desk.execute(cmd);
      if (outcome.record !== null) {
        // The record must reach the file before the client hears about the change.
        try {
          appendFileSync(journal, outcome.record + "\n", "latin1");
        } catch (e) {
          fail(`cannot write journal: ${(e as Error).message}`, 1);
        }
      }
      response = outcome.response;
    }
    process.stdout.write(response + "\n");
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

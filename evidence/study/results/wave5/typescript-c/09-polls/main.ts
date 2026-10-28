import { closeSync, existsSync, mkdirSync, openSync, readFileSync, statSync, truncateSync, writeSync } from "node:fs";
import { join } from "node:path";

const NAME = /^[a-z0-9]{1,12}$/;

interface Poll {
  options: string[];
  votes: Map<string, string>;
  closed: boolean;
}

interface Outcome {
  response: string;
  /** True when the command changed the state and must be journaled. */
  changed: boolean;
}

const reply = (response: string, changed = false): Outcome => ({ response, changed });

class Polls {
  private polls = new Map<string, Poll>();

  apply(line: string): Outcome {
    const parts = line.split(" ");
    const [cmd, name, ...rest] = parts;
    if (!parts.slice(1).every((p) => NAME.test(p))) return reply("ERR bad command");

    switch (cmd) {
      case "CREATE": {
        if (rest.length < 2 || rest.length > 9 || new Set(rest).size !== rest.length) {
          return reply("ERR bad command");
        }
        if (this.polls.has(name)) return reply("ERR poll exists");
        this.polls.set(name, { options: rest, votes: new Map(), closed: false });
        return reply("OK", true);
      }
      case "VOTE": {
        if (rest.length !== 2) return reply("ERR bad command");
        const poll = this.polls.get(name);
        if (poll === undefined) return reply("ERR no such poll");
        if (poll.closed) return reply("ERR poll closed");
        const [voter, option] = rest;
        if (!poll.options.includes(option)) return reply("ERR no such option");
        const previous = poll.votes.get(voter);
        if (previous === option) return reply("UNCHANGED");
        poll.votes.set(voter, option);
        return reply(previous === undefined ? "VOTED" : "CHANGED", true);
      }
      case "CLOSE": {
        if (rest.length !== 0 || name === undefined) return reply("ERR bad command");
        const poll = this.polls.get(name);
        if (poll === undefined) return reply("ERR no such poll");
        if (poll.closed) return reply("ERR poll closed");
        poll.closed = true;
        return reply("OK", true);
      }
      case "RESULT": {
        if (rest.length !== 0 || name === undefined) return reply("ERR bad command");
        const poll = this.polls.get(name);
        if (poll === undefined) return reply("ERR no such poll");
        const counts = poll.options.map((o) => {
          let n = 0;
          for (const v of poll.votes.values()) if (v === o) n++;
          return ` ${o}=${n}`;
        });
        return reply(`${name} ${poll.closed ? "closed" : "open"}${counts.join("")}`);
      }
      default:
        return reply("ERR bad command");
    }
  }
}

function fail(message: string, code: number): never {
  process.stderr.write(`polls: ${message}\n`);
  process.exit(code);
}

function prepareDir(dir: string): void {
  if (!existsSync(dir)) {
    try {
      mkdirSync(dir);
    } catch (e) {
      fail(`cannot create ${dir}: ${(e as Error).message}`, 1);
    }
  }
  if (!statSync(dir).isDirectory()) fail(`${dir} is not a directory`, 1);
}

/** Replays the journal into `polls`; truncates a torn tail only once the journal is known valid. */
function loadJournal(path: string, polls: Polls): void {
  if (!existsSync(path)) return;
  let data: Buffer;
  try {
    data = readFileSync(path);
  } catch (e) {
    fail(`cannot read journal: ${(e as Error).message}`, 1);
  }
  const keep = data.lastIndexOf(0x0a) + 1;
  const complete = data.subarray(0, keep).toString("utf8");
  if (complete !== "") {
    const lines = complete.slice(0, -1).split("\n");
    lines.forEach((line, i) => {
      const { response } = polls.apply(line);
      if (response !== "OK" && response !== "VOTED" && response !== "CHANGED") {
        fail(`invalid journal at record ${i + 1}: ${line}`, 1);
      }
    });
  }
  if (keep < data.length) truncateSync(path, keep);
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1) fail("usage: polls DIR", 2);
  const dir = args[0];

  prepareDir(dir);
  const journalPath = join(dir, "polls.log");
  const polls = new Polls();
  loadJournal(journalPath, polls);

  let fd: number;
  try {
    fd = openSync(journalPath, "a");
  } catch (e) {
    fail(`cannot open journal: ${(e as Error).message}`, 1);
  }

  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    const { response, changed } = polls.apply(line);
    if (changed) writeSync(fd, line + "\n");
    process.stdout.write(response + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("utf8");
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
    closeSync(fd);
  });
}

main();

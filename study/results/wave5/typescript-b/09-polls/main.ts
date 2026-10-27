import * as fs from "node:fs";
import * as path from "node:path";

class FatalError extends Error {}

type Poll = { options: string[]; votes: Map<string, string>; closed: boolean };

type Command =
  | { kind: "CREATE"; poll: string; options: string[] }
  | { kind: "VOTE"; poll: string; voter: string; option: string }
  | { kind: "CLOSE"; poll: string }
  | { kind: "RESULT"; poll: string };

const NAME_RE = /^[a-z0-9]{1,12}$/;

function parseCommand(line: string): Command | null {
  const tokens = line.split(" ");
  if (!tokens.slice(1).every((t) => NAME_RE.test(t))) return null;
  const [name, ...args] = tokens;
  switch (name) {
    case "CREATE": {
      const options = args.slice(1);
      if (args.length < 3 || options.length > 9 || new Set(options).size !== options.length) return null;
      return { kind: "CREATE", poll: args[0], options };
    }
    case "VOTE":
      return args.length === 3 ? { kind: "VOTE", poll: args[0], voter: args[1], option: args[2] } : null;
    case "CLOSE":
    case "RESULT":
      return args.length === 1 ? { kind: name, poll: args[0] } : null;
    default:
      return null;
  }
}

class PollStore {
  private polls = new Map<string, Poll>();

  // Returns the response and whether the command changed the state.
  apply(cmd: Command): { response: string; changed: boolean } {
    const err = (response: string) => ({ response, changed: false });
    if (cmd.kind === "CREATE") {
      if (this.polls.has(cmd.poll)) return err("ERR poll exists");
      this.polls.set(cmd.poll, { options: cmd.options, votes: new Map(), closed: false });
      return { response: "OK", changed: true };
    }
    const poll = this.polls.get(cmd.poll);
    if (!poll) return err("ERR no such poll");
    switch (cmd.kind) {
      case "VOTE": {
        if (poll.closed) return err("ERR poll closed");
        if (!poll.options.includes(cmd.option)) return err("ERR no such option");
        const previous = poll.votes.get(cmd.voter);
        if (previous === cmd.option) return err("UNCHANGED");
        poll.votes.set(cmd.voter, cmd.option);
        return { response: previous === undefined ? "VOTED" : "CHANGED", changed: true };
      }
      case "CLOSE":
        if (poll.closed) return err("ERR poll closed");
        poll.closed = true;
        return { response: "OK", changed: true };
      case "RESULT": {
        const counts = new Map(poll.options.map((o) => [o, 0]));
        for (const option of poll.votes.values()) counts.set(option, counts.get(option)! + 1);
        const parts = poll.options.map((o) => `${o}=${counts.get(o)}`);
        return { response: [cmd.poll, poll.closed ? "closed" : "open", ...parts].join(" "), changed: false };
      }
    }
  }
}

function prepareDir(dir: string): void {
  try {
    fs.mkdirSync(dir);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") {
      throw new FatalError(`cannot create ${dir}: ${(e as Error).message}`);
    }
    if (!fs.statSync(dir).isDirectory()) throw new FatalError(`${dir} is not a directory`);
  }
}

// Replays the journal into the store and cuts off a torn last record.
function loadJournal(file: string, store: PollStore): void {
  let data: Buffer;
  try {
    data = fs.readFileSync(file);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return;
    throw new FatalError(`cannot read ${file}: ${(e as Error).message}`);
  }
  const completeLength = data.lastIndexOf(0x0a) + 1;
  const lines = data.subarray(0, completeLength).toString("utf8").split("\n");
  lines.pop();
  lines.forEach((line, i) => {
    const cmd = parseCommand(line);
    if (!cmd || cmd.kind === "RESULT" || !store.apply(cmd).changed) {
      throw new FatalError(`${file}:${i + 1}: invalid record`);
    }
  });
  if (completeLength < data.length) fs.truncateSync(file, completeLength);
}

function main(argv: string[]): void {
  if (argv.length !== 1) {
    process.stderr.write("usage: polls DIR\n");
    process.exit(2);
  }
  const dir = argv[0];
  const journalPath = path.join(dir, "polls.log");
  const store = new PollStore();
  let journal: number | null = null;

  try {
    prepareDir(dir);
    loadJournal(journalPath, store);
  } catch (e) {
    if (e instanceof FatalError) {
      process.stderr.write(`polls: ${e.message}\n`);
      process.exit(1);
    }
    throw e;
  }

  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    const cmd = parseCommand(line);
    if (!cmd) {
      process.stdout.write("ERR bad command\n");
      return;
    }
    const { response, changed } = store.apply(cmd);
    if (changed) {
      journal ??= fs.openSync(journalPath, "a");
      fs.writeSync(journal, line + "\n");
    }
    process.stdout.write(response + "\n");
  };

  let pending = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) !== -1) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
    if (journal !== null) fs.closeSync(journal);
  });
}

main(process.argv.slice(2));

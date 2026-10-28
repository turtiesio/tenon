type Mode = "S" | "X";

interface Request {
  client: string;
  mode: Mode;
}

interface Resource {
  holders: Map<string, Mode>;
  queue: Request[];
}

const NAME = "[a-z0-9]{1,12}";
const LOCK_RE = new RegExp(`^LOCK (${NAME}) (${NAME}) ([SX])$`);
const UNLOCK_RE = new RegExp(`^UNLOCK (${NAME}) (${NAME})$`);
const DROP_RE = new RegExp(`^DROP (${NAME})$`);
const STATUS_RE = new RegExp(`^STATUS (${NAME})$`);
const HELD_RE = new RegExp(`^HELD (${NAME})$`);

function listOrDash(items: string[]): string {
  return items.length === 0 ? "-" : items.join(",");
}

function withGrants(head: string, grants: string[]): string {
  return [head, ...grants].join(" ");
}

class LockManager {
  private resources = new Map<string, Resource>();

  private resource(name: string): Resource {
    let r = this.resources.get(name);
    if (r === undefined) {
      r = { holders: new Map(), queue: [] };
      this.resources.set(name, r);
    }
    return r;
  }

  handle(line: string): string {
    let m: RegExpExecArray | null;
    if ((m = LOCK_RE.exec(line))) return this.lock(m[1], m[2], m[3] as Mode);
    if ((m = UNLOCK_RE.exec(line))) return this.unlock(m[1], m[2]);
    if ((m = DROP_RE.exec(line))) return this.drop(m[1]);
    if ((m = STATUS_RE.exec(line))) return this.status(m[1]);
    if ((m = HELD_RE.exec(line))) return this.held(m[1]);
    return "ERR bad command";
  }

  private static compatible(r: Resource, mode: Mode): boolean {
    if (r.holders.size === 0) return true;
    return mode === "S" && [...r.holders.values()].every((h) => h === "S");
  }

  /** Grants requests from the front of the queue while they are compatible. */
  private pump(name: string, grants: string[]): void {
    const r = this.resource(name);
    while (r.queue.length > 0 && LockManager.compatible(r, r.queue[0].mode)) {
      const req = r.queue.shift()!;
      r.holders.set(req.client, req.mode);
      grants.push(`${req.client}:${name}:${req.mode}`);
    }
  }

  private lock(client: string, name: string, mode: Mode): string {
    const r = this.resource(name);
    if (r.holders.has(client)) return "ERR already held";
    if (r.queue.some((q) => q.client === client)) return "ERR already waiting";
    if (r.queue.length === 0 && LockManager.compatible(r, mode)) {
      r.holders.set(client, mode);
      return "GRANTED";
    }
    r.queue.push({ client, mode });
    return "WAITING";
  }

  private unlock(client: string, name: string): string {
    const r = this.resource(name);
    if (!r.holders.delete(client)) return "ERR not held";
    const grants: string[] = [];
    this.pump(name, grants);
    return withGrants("OK", grants);
  }

  private drop(client: string): string {
    const touched = new Set<string>();
    let cancelled = 0;
    let released = 0;
    for (const [name, r] of this.resources) {
      const before = r.queue.length;
      r.queue = r.queue.filter((q) => q.client !== client);
      if (r.queue.length !== before) {
        cancelled += before - r.queue.length;
        touched.add(name);
      }
    }
    for (const [name, r] of this.resources) {
      if (r.holders.delete(client)) {
        released++;
        touched.add(name);
      }
    }
    const grants: string[] = [];
    for (const name of [...touched].sort()) this.pump(name, grants);
    return withGrants(`OK released=${released} cancelled=${cancelled}`, grants);
  }

  private status(name: string): string {
    const r = this.resources.get(name);
    const holders = r ? [...r.holders.keys()].sort().map((c) => `${c}:${r.holders.get(c)}`) : [];
    const queue = r ? r.queue.map((q) => `${q.client}:${q.mode}`) : [];
    return `${name} holders=${listOrDash(holders)} queue=${listOrDash(queue)}`;
  }

  private held(client: string): string {
    const locks: string[] = [];
    for (const name of [...this.resources.keys()].sort()) {
      const mode = this.resources.get(name)!.holders.get(client);
      if (mode !== undefined) locks.push(`${name}:${mode}`);
    }
    return listOrDash(locks);
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: locks\n");
    process.exitCode = 2;
    return;
  }
  const manager = new LockManager();
  const respond = (raw: string): void => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(manager.handle(line) + "\n");
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

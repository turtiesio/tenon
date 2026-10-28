type Mode = "S" | "X";

interface Request {
  client: string;
  mode: Mode;
}

interface Resource {
  holders: Map<string, Mode>;
  queue: Request[];
}

const NAME = /^[a-z0-9]{1,12}$/;
const MODE = /^[SX]$/;

// Names are ASCII, so code-unit order is byte order.
function byName(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

class LockManager {
  private resources = new Map<string, Resource>();

  handle(line: string): string {
    const t = line.split(" ");
    switch (t[0]) {
      case "LOCK":
        if (t.length === 4 && NAME.test(t[1]) && NAME.test(t[2]) && MODE.test(t[3])) {
          return this.lock(t[1], t[2], t[3] as Mode);
        }
        break;
      case "UNLOCK":
        if (t.length === 3 && NAME.test(t[1]) && NAME.test(t[2])) return this.unlock(t[1], t[2]);
        break;
      case "DROP":
        if (t.length === 2 && NAME.test(t[1])) return this.drop(t[1]);
        break;
      case "STATUS":
        if (t.length === 2 && NAME.test(t[1])) return this.status(t[1]);
        break;
      case "HELD":
        if (t.length === 2 && NAME.test(t[1])) return this.held(t[1]);
        break;
    }
    return "ERR bad command";
  }

  private resource(name: string): Resource {
    let r = this.resources.get(name);
    if (!r) {
      r = { holders: new Map(), queue: [] };
      this.resources.set(name, r);
    }
    return r;
  }

  private compatible(r: Resource, mode: Mode): boolean {
    if (r.holders.size === 0) return true;
    return mode === "S" && [...r.holders.values()].every((m) => m === "S");
  }

  /** Grants requests from the front of the queue while they fit; returns the grant reports. */
  private pump(name: string, r: Resource): string[] {
    const grants: string[] = [];
    while (r.queue.length > 0 && this.compatible(r, r.queue[0].mode)) {
      const { client, mode } = r.queue.shift()!;
      r.holders.set(client, mode);
      grants.push(`${client}:${name}:${mode}`);
    }
    return grants;
  }

  private lock(client: string, name: string, mode: Mode): string {
    const r = this.resource(name);
    if (r.holders.has(client)) return "ERR already held";
    if (r.queue.some((q) => q.client === client)) return "ERR already waiting";
    if (r.queue.length === 0 && this.compatible(r, mode)) {
      r.holders.set(client, mode);
      return "GRANTED";
    }
    r.queue.push({ client, mode });
    return "WAITING";
  }

  private unlock(client: string, name: string): string {
    const r = this.resources.get(name);
    if (!r || !r.holders.delete(client)) return "ERR not held";
    return ["OK", ...this.pump(name, r)].join(" ");
  }

  private drop(client: string): string {
    const touched = new Set<string>();
    let released = 0;
    let cancelled = 0;
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
    for (const name of [...touched].sort(byName)) {
      grants.push(...this.pump(name, this.resources.get(name)!));
    }
    return [`OK released=${released} cancelled=${cancelled}`, ...grants].join(" ");
  }

  private status(name: string): string {
    const r = this.resources.get(name);
    const holders = r ? [...r.holders].sort(([a], [b]) => byName(a, b)).map(([c, m]) => `${c}:${m}`) : [];
    const queue = r ? r.queue.map((q) => `${q.client}:${q.mode}`) : [];
    return `${name} holders=${holders.join(",") || "-"} queue=${queue.join(",") || "-"}`;
  }

  private held(client: string): string {
    const locks: [string, Mode][] = [];
    for (const [name, r] of this.resources) {
      const mode = r.holders.get(client);
      if (mode) locks.push([name, mode]);
    }
    locks.sort(([a], [b]) => byName(a, b));
    return locks.map(([name, mode]) => `${name}:${mode}`).join(",") || "-";
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: locks\n");
    process.exitCode = 2;
    return;
  }
  const manager = new LockManager();
  const respond = (line: string): void => {
    const clean = line.endsWith("\r") ? line.slice(0, -1) : line;
    process.stdout.write(manager.handle(clean) + "\n");
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

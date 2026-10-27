const GRACE_MINUTES = 15;
const HOUR_RATE = 250;
const DAY_CAP = 2000;
const MINUTES_PER_DAY = 1440;

const PLATE = /^[A-Z0-9]{1,8}$/;
const TIME = /^[0-9]{1,7}$/;

function fee(duration: number): number {
  if (duration <= GRACE_MINUTES) return 0;
  const days = Math.floor(duration / MINUTES_PER_DAY);
  const rest = duration % MINUTES_PER_DAY;
  return days * DAY_CAP + Math.min(DAY_CAP, HOUR_RATE * Math.ceil(rest / 60));
}

function formatAmount(cents: number): string {
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;
}

interface Stay {
  spot: number;
  entry: number;
}

class Garage {
  private readonly capacity: number;
  private clock = 0;
  private revenue = 0;
  private readonly parked = new Map<string, Stay>();
  private readonly taken = new Set<number>();

  constructor(capacity: number) {
    this.capacity = capacity;
  }

  handle(line: string): string {
    const tokens = line.split(" ");
    const [cmd, plate, timeText] = tokens;
    if ((cmd === "IN" || cmd === "OUT") && tokens.length === 3) {
      if (!PLATE.test(plate) || !TIME.test(timeText)) return "ERR bad command";
      const time = Number(timeText);
      if (time < this.clock) return "ERR bad time";
      this.clock = time;
      return cmd === "IN" ? this.enter(plate, time) : this.leave(plate, time);
    }
    if (cmd === "WHERE" && tokens.length === 2 && PLATE.test(plate)) {
      const stay = this.parked.get(plate);
      return stay === undefined ? "ERR not parked" : `SPOT ${stay.spot}`;
    }
    if (cmd === "STATUS" && tokens.length === 1) {
      const p = this.parked.size;
      return `free=${this.capacity - p} parked=${p} revenue=${formatAmount(this.revenue)}`;
    }
    return "ERR bad command";
  }

  private enter(plate: string, time: number): string {
    if (this.parked.has(plate)) return "ERR already parked";
    if (this.parked.size >= this.capacity) return "FULL";
    let spot = 1;
    while (this.taken.has(spot)) spot++;
    this.taken.add(spot);
    this.parked.set(plate, { spot, entry: time });
    return `OK ${spot}`;
  }

  private leave(plate: string, time: number): string {
    const stay = this.parked.get(plate);
    if (stay === undefined) return "ERR not parked";
    this.parked.delete(plate);
    this.taken.delete(stay.spot);
    const amount = fee(time - stay.entry);
    this.revenue += amount;
    return `FEE ${formatAmount(amount)}`;
  }
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 1 || !/^[0-9]{1,4}$/.test(args[0]) || Number(args[0]) < 1 || Number(args[0]) > 1000) {
    console.error("usage: parking CAPACITY (1-1000)");
    process.exitCode = 2;
    return;
  }
  const garage = new Garage(Number(args[0]));

  const respond = (rawLine: string): void => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    process.stdout.write(garage.handle(line) + "\n");
  };

  // Split on "\n" by hand (readline would also split on a lone "\r") and
  // answer each line as soon as it is complete.
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

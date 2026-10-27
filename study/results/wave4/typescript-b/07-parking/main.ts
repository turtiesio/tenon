import * as readline from "node:readline";

const PLATE = "[A-Z0-9]{1,8}";
const TIME = "[0-9]{1,7}";
const MOVE = new RegExp(`^(IN|OUT) (${PLATE}) (${TIME})$`);
const WHERE = new RegExp(`^WHERE (${PLATE})$`);

const GRACE_MINUTES = 15;
const DAY_MINUTES = 1440;
const HOUR_CENTS = 250;
const DAY_CAP_CENTS = 2000;

function parseCapacity(args: string[]): number {
  if (args.length === 1 && /^[0-9]{1,4}$/.test(args[0])) {
    const n = Number(args[0]);
    if (n >= 1 && n <= 1000) return n;
  }
  process.stderr.write("usage: parking CAPACITY   (1-1000)\n");
  process.exit(2);
}

function fee(duration: number): number {
  if (duration <= GRACE_MINUTES) return 0;
  const days = Math.floor(duration / DAY_MINUTES);
  const rest = duration % DAY_MINUTES;
  return days * DAY_CAP_CENTS + Math.min(DAY_CAP_CENTS, HOUR_CENTS * Math.ceil(rest / 60));
}

function formatCents(c: number): string {
  return `${Math.floor(c / 100)}.${String(c % 100).padStart(2, "0")}`;
}

interface Stay {
  spot: number;
  entry: number;
}

class Garage {
  private clock = 0;
  private revenue = 0;
  private readonly spots: (string | null)[];
  private readonly parked = new Map<string, Stay>();

  constructor(capacity: number) {
    this.spots = new Array<string | null>(capacity).fill(null);
  }

  handle(line: string): string {
    let m = MOVE.exec(line);
    if (m !== null) {
      const [, cmd, plate, timeText] = m;
      const time = Number(timeText);
      if (time < this.clock) return "ERR bad time";
      this.clock = time;
      return cmd === "IN" ? this.enter(plate) : this.leave(plate);
    }
    m = WHERE.exec(line);
    if (m !== null) {
      const stay = this.parked.get(m[1]);
      return stay === undefined ? "ERR not parked" : `SPOT ${stay.spot}`;
    }
    if (line === "STATUS") {
      const parked = this.parked.size;
      return `free=${this.spots.length - parked} parked=${parked} revenue=${formatCents(this.revenue)}`;
    }
    return "ERR bad command";
  }

  private enter(plate: string): string {
    if (this.parked.has(plate)) return "ERR already parked";
    const index = this.spots.indexOf(null);
    if (index < 0) return "FULL";
    this.spots[index] = plate;
    this.parked.set(plate, { spot: index + 1, entry: this.clock });
    return `OK ${index + 1}`;
  }

  private leave(plate: string): string {
    const stay = this.parked.get(plate);
    if (stay === undefined) return "ERR not parked";
    this.parked.delete(plate);
    this.spots[stay.spot - 1] = null;
    const amount = fee(this.clock - stay.entry);
    this.revenue += amount;
    return `FEE ${formatCents(amount)}`;
  }
}

function main(): void {
  const garage = new Garage(parseCapacity(process.argv.slice(2)));
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (raw) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    process.stdout.write(garage.handle(line) + "\n");
  });
}

main();

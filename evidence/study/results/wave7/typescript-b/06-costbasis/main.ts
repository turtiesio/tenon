import * as fs from "node:fs";

interface Lot {
  qty: number;
  cost: number; // cents
}

type Trade =
  | { kind: "BUY" | "SELL"; sym: string; qty: number; price: number }
  | { kind: "SPLIT"; sym: string; ratio: number };

const TRADE = /^(BUY|SELL) ([A-Z]{1,5}) ([1-9][0-9]{0,5}) (0|[1-9][0-9]{0,5})\.([0-9]{2})$/;
const SPLIT = /^SPLIT ([A-Z]{1,5}) ([2-9]|10)$/;

function parseTrade(line: string): Trade | null {
  let m = TRADE.exec(line);
  if (m !== null) {
    const kind = m[1] === "BUY" ? "BUY" : "SELL";
    return { kind, sym: m[2], qty: Number(m[3]), price: Number(m[4]) * 100 + Number(m[5]) };
  }
  m = SPLIT.exec(line);
  if (m !== null) return { kind: "SPLIT", sym: m[1], ratio: Number(m[2]) };
  return null;
}

function formatMoney(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** C × j / q rounded to the nearest cent, halves up. 2 × C × j may exceed 2^53, hence BigInt. */
function proportionalCost(cost: number, j: number, q: number): number {
  const bq = BigInt(q);
  return Number((2n * BigInt(cost) * BigInt(j) + bq) / (2n * bq));
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: costbasis (trades on stdin)\n");
    process.exit(2);
  }

  const text = fs.readFileSync(0, "latin1");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();

  const holdings = new Map<string, Lot[]>();
  const out: string[] = [];
  let totalGain = 0;
  let hadError = false;
  const sumQty = (lots: Lot[]) => lots.reduce((s, lot) => s + lot.qty, 0);

  lines.forEach((raw, index) => {
    const n = index + 1;
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;
    const trade = parseTrade(line);
    if (trade === null) {
      out.push(`${n}: ERR bad line`);
      hadError = true;
      return;
    }
    const lots = holdings.get(trade.sym) ?? [];
    switch (trade.kind) {
      case "BUY":
        lots.push({ qty: trade.qty, cost: trade.qty * trade.price });
        holdings.set(trade.sym, lots);
        break;
      case "SELL": {
        const held = sumQty(lots);
        if (trade.qty > held) {
          out.push(`${n}: ERR insufficient ${trade.sym} held=${held}`);
          hadError = true;
          break;
        }
        let remaining = trade.qty;
        let cost = 0;
        while (remaining > 0) {
          const lot = lots[0];
          if (lot.qty <= remaining) {
            cost += lot.cost;
            remaining -= lot.qty;
            lots.shift();
          } else {
            const part = proportionalCost(lot.cost, remaining, lot.qty);
            cost += part;
            lot.qty -= remaining;
            lot.cost -= part;
            remaining = 0;
          }
        }
        if (lots.length === 0) holdings.delete(trade.sym);
        const proceeds = trade.qty * trade.price;
        const gain = proceeds - cost;
        totalGain += gain;
        out.push(
          `${n}: SELL ${trade.sym} ${trade.qty} proceeds=${formatMoney(proceeds)} cost=${formatMoney(cost)} gain=${formatMoney(gain)}`,
        );
        break;
      }
      case "SPLIT":
        if (lots.length === 0) {
          out.push(`${n}: ERR not held ${trade.sym}`);
          hadError = true;
          break;
        }
        for (const lot of lots) lot.qty *= trade.ratio;
        out.push(`${n}: SPLIT ${trade.sym} ${trade.ratio} held=${sumQty(lots)}`);
        break;
    }
  });

  const symbols = [...holdings.keys()].sort();
  for (const sym of symbols) {
    const lots = holdings.get(sym)!;
    const cost = lots.reduce((s, lot) => s + lot.cost, 0);
    out.push(`HOLD ${sym} ${sumQty(lots)} cost=${formatMoney(cost)} lots=${lots.length}`);
  }
  out.push(`TOTAL gain=${formatMoney(totalGain)}`);
  process.stdout.write(out.map((l) => l + "\n").join(""));
  process.exitCode = hadError ? 1 : 0;
}

main();

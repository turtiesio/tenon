import { readFileSync } from "node:fs";

// Money and quantities are BigInt: 2 * C * j can exceed 2^53.
interface Lot {
  qty: bigint;
  cost: bigint; // cents
}

const BUY_SELL = /^(BUY|SELL) ([A-Z]{1,5}) ([1-9][0-9]{0,5}) ((?:0|[1-9][0-9]{0,5})\.[0-9]{2})$/;
const SPLIT = /^SPLIT ([A-Z]{1,5}) ([2-9]|10)$/;

function priceToCents(price: string): bigint {
  return BigInt(price.replace(".", ""));
}

function money(cents: bigint): string {
  const sign = cents < 0n ? "-" : "";
  const abs = cents < 0n ? -cents : cents;
  return `${sign}${abs / 100n}.${String(abs % 100n).padStart(2, "0")}`;
}

function totalQty(lots: Lot[]): bigint {
  return lots.reduce((sum, lot) => sum + lot.qty, 0n);
}

// Takes `k` shares (k <= held) from the oldest lots; returns their cost in cents.
function takeShares(lots: Lot[], k: bigint): bigint {
  let remaining = k;
  let cost = 0n;
  while (remaining > 0n) {
    const lot = lots[0];
    if (lot.qty <= remaining) {
      cost += lot.cost;
      remaining -= lot.qty;
      lots.shift();
    } else {
      const part = (2n * lot.cost * remaining + lot.qty) / (2n * lot.qty);
      cost += part;
      lot.qty -= remaining;
      lot.cost -= part;
      remaining = 0n;
    }
  }
  return cost;
}

function main(): number {
  if (process.argv.length > 2) {
    process.stderr.write("usage: costbasis (reads trades from stdin)\n");
    return 2;
  }

  const lines = readFileSync(0, "latin1").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();

  const holdings = new Map<string, Lot[]>();
  const out: string[] = [];
  let totalGain = 0n;
  let failed = false;

  const error = (n: number, message: string) => {
    out.push(`${n}: ERR ${message}`);
    failed = true;
  };

  lines.forEach((raw, index) => {
    const n = index + 1;
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith("#")) return;

    const trade = BUY_SELL.exec(line);
    if (trade !== null) {
      const [, action, sym, qtyText, priceText] = trade;
      const qty = BigInt(qtyText);
      const price = priceToCents(priceText);
      const lots = holdings.get(sym) ?? [];
      if (action === "BUY") {
        lots.push({ qty, cost: qty * price });
        holdings.set(sym, lots);
        return;
      }
      const held = totalQty(lots);
      if (qty > held) {
        error(n, `insufficient ${sym} held=${held}`);
        return;
      }
      const cost = takeShares(lots, qty);
      const proceeds = qty * price;
      const gain = proceeds - cost;
      totalGain += gain;
      if (lots.length === 0) holdings.delete(sym);
      out.push(`${n}: SELL ${sym} ${qty} proceeds=${money(proceeds)} cost=${money(cost)} gain=${money(gain)}`);
      return;
    }

    const split = SPLIT.exec(line);
    if (split !== null) {
      const [, sym, ratioText] = split;
      const lots = holdings.get(sym);
      if (lots === undefined || lots.length === 0) {
        error(n, `not held ${sym}`);
        return;
      }
      const ratio = BigInt(ratioText);
      for (const lot of lots) lot.qty *= ratio;
      out.push(`${n}: SPLIT ${sym} ${ratio} held=${totalQty(lots)}`);
      return;
    }

    error(n, "bad line");
  });

  for (const sym of [...holdings.keys()].sort()) {
    const lots = holdings.get(sym)!;
    if (lots.length === 0) continue;
    const cost = lots.reduce((sum, lot) => sum + lot.cost, 0n);
    out.push(`HOLD ${sym} ${totalQty(lots)} cost=${money(cost)} lots=${lots.length}`);
  }
  out.push(`TOTAL gain=${money(totalGain)}`);
  process.stdout.write(out.map((l) => l + "\n").join(""));
  return failed ? 1 : 0;
}

process.exitCode = main();

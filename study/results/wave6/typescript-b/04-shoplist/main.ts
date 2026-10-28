import * as fs from "node:fs";

type Kind = "mass" | "volume" | "count";

interface Ingredient {
  name: string;
  qty: number; // in base units
  kind: Kind;
}

interface Recipe {
  serves: number;
  ingredients: Ingredient[];
}

class InputError extends Error {}

const HEADER_RE = /^\[([a-z][a-z0-9_-]{0,29})\] ([1-9][0-9]{0,2})$/;
const INGREDIENT_RE = /^([a-z][a-z0-9_-]{0,29}) ([1-9][0-9]{0,5})(?: (g|kg|ml|l))?$/;
const PLAN_RE = /^([a-z][a-z0-9_-]{0,29}) ([1-9][0-9]{0,2})$/;

/** Returns the significant lines of a file with their 1-based line numbers. */
function readLines(path: string): [number, string][] {
  let text: string;
  try {
    text = fs.readFileSync(path, "utf8");
  } catch (e) {
    throw new InputError(`cannot read ${path}: ${(e as Error).message}`);
  }
  const lines = text.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const result: [number, string][] = [];
  lines.forEach((raw, i) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (!/[^ ]/.test(line)) return;
    if (line.startsWith("#")) return;
    result.push([i + 1, line]);
  });
  return result;
}

function parseRecipes(path: string): Map<string, Recipe> {
  const recipes = new Map<string, Recipe>();
  let current: Recipe | null = null;
  for (const [no, line] of readLines(path)) {
    const where = `${path}:${no}`;
    const header = HEADER_RE.exec(line);
    if (header) {
      if (recipes.has(header[1])) throw new InputError(`${where}: recipe '${header[1]}' defined twice`);
      current = { serves: Number(header[2]), ingredients: [] };
      recipes.set(header[1], current);
      continue;
    }
    const ing = INGREDIENT_RE.exec(line);
    if (!ing) throw new InputError(`${where}: invalid line`);
    if (current === null) throw new InputError(`${where}: ingredient before the first recipe header`);
    const [, name, qtyText, unit] = ing;
    if (current.ingredients.some((x) => x.name === name)) {
      throw new InputError(`${where}: ingredient '${name}' repeated in recipe`);
    }
    let qty = Number(qtyText);
    let kind: Kind = "count";
    if (unit === "g" || unit === "kg") kind = "mass";
    if (unit === "ml" || unit === "l") kind = "volume";
    if (unit === "kg" || unit === "l") qty *= 1000;
    current.ingredients.push({ name, qty, kind });
  }
  return recipes;
}

function formatAmount(total: number, kind: Kind): string {
  if (kind === "count") return String(total);
  const [small, big] = kind === "mass" ? ["g", "kg"] : ["ml", "l"];
  if (total < 1000) return `${total} ${small}`;
  const whole = Math.floor(total / 1000);
  const frac = total % 1000;
  const fracText = frac === 0 ? "" : "." + String(frac).padStart(3, "0").replace(/0+$/, "");
  return `${whole}${fracText} ${big}`;
}

function run(recipesPath: string, planPath: string): string {
  const recipes = parseRecipes(recipesPath);
  const totals = new Map<string, { kind: Kind; amount: number }>();
  for (const [no, line] of readLines(planPath)) {
    const where = `${planPath}:${no}`;
    const m = PLAN_RE.exec(line);
    if (!m) throw new InputError(`${where}: invalid line`);
    const recipe = recipes.get(m[1]);
    if (!recipe) throw new InputError(`${where}: unknown recipe '${m[1]}'`);
    const servings = Number(m[2]);
    for (const ing of recipe.ingredients) {
      const amount = Math.ceil((ing.qty * servings) / recipe.serves);
      const entry = totals.get(ing.name);
      if (entry === undefined) {
        totals.set(ing.name, { kind: ing.kind, amount });
      } else if (entry.kind !== ing.kind) {
        throw new InputError(`ingredient '${ing.name}' used as both ${entry.kind} and ${ing.kind}`);
      } else {
        entry.amount += amount;
      }
    }
  }
  const names = [...totals.keys()].sort();
  return names.map((name) => {
    const { kind, amount } = totals.get(name)!;
    return `${name} ${formatAmount(amount, kind)}\n`;
  }).join("");
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    process.stderr.write("usage: shoplist RECIPES PLAN\n");
    return 2;
  }
  try {
    process.stdout.write(run(args[0], args[1]));
    return 0;
  } catch (e) {
    if (e instanceof InputError) {
      process.stderr.write(`shoplist: ${e.message}\n`);
      return 1;
    }
    throw e;
  }
}

process.exitCode = main();

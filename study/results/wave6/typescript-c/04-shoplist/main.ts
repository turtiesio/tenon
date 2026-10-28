import { readFileSync } from "node:fs";

type Kind = "count" | "mass" | "volume";

interface Ingredient {
  name: string;
  kind: Kind;
  qty: number; // in base units: grams, millilitres or a count
}

interface Recipe {
  serves: number;
  ingredients: Ingredient[];
}

class InputError extends Error {}

const NAME = "[a-z][a-z0-9_-]{0,29}";
const SERVES = "[1-9][0-9]{0,2}";
const HEADER = new RegExp(`^\\[(${NAME})\\] (${SERVES})$`);
const INGREDIENT = new RegExp(`^(${NAME}) ([1-9][0-9]{0,5})(?: (g|kg|ml|l))?$`);
const PLAN_LINE = new RegExp(`^(${NAME}) (${SERVES})$`);

const UNITS: Record<string, { kind: Kind; factor: number }> = {
  g: { kind: "mass", factor: 1 },
  kg: { kind: "mass", factor: 1000 },
  ml: { kind: "volume", factor: 1 },
  l: { kind: "volume", factor: 1000 },
};

/** Meaningful lines of a file: split on \n, strip one trailing \r, drop blanks and comments. */
function readLines(path: string): string[] {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();
  if (lines.length > 1000) throw new InputError(`${path}: too many lines`);
  return lines
    .map((line) => (line.endsWith("\r") ? line.slice(0, -1) : line))
    .filter((line) => !line.startsWith("#") && !/^ *$/.test(line));
}

function parseRecipes(path: string): Map<string, Recipe> {
  const recipes = new Map<string, Recipe>();
  let current: Recipe | null = null;
  for (const line of readLines(path)) {
    const header = HEADER.exec(line);
    if (header) {
      if (recipes.has(header[1])) throw new InputError(`${path}: duplicate recipe '${header[1]}'`);
      current = { serves: Number(header[2]), ingredients: [] };
      recipes.set(header[1], current);
      continue;
    }
    const item = INGREDIENT.exec(line);
    if (!item) throw new InputError(`${path}: invalid line '${line}'`);
    if (current === null) throw new InputError(`${path}: ingredient before first recipe`);
    const [, name, qty, unit] = item;
    if (current.ingredients.some((i) => i.name === name)) {
      throw new InputError(`${path}: duplicate ingredient '${name}'`);
    }
    const spec = unit === undefined ? { kind: "count" as Kind, factor: 1 } : UNITS[unit];
    current.ingredients.push({ name, kind: spec.kind, qty: Number(qty) * spec.factor });
  }
  return recipes;
}

function formatTotal(kind: Kind, total: number): string {
  if (kind === "count") return String(total);
  const small = kind === "mass" ? "g" : "ml";
  const big = kind === "mass" ? "kg" : "l";
  if (total < 1000) return `${total} ${small}`;
  const frac = String(total % 1000).padStart(3, "0").replace(/0+$/, "");
  return `${Math.floor(total / 1000)}${frac === "" ? "" : "." + frac} ${big}`;
}

function build(recipePath: string, planPath: string): string {
  const recipes = parseRecipes(recipePath);
  const totals = new Map<string, { kind: Kind; total: number }>();
  for (const line of readLines(planPath)) {
    const m = PLAN_LINE.exec(line);
    if (!m) throw new InputError(`${planPath}: invalid line '${line}'`);
    const recipe = recipes.get(m[1]);
    if (!recipe) throw new InputError(`${planPath}: unknown recipe '${m[1]}'`);
    const servings = Number(m[2]);
    for (const ing of recipe.ingredients) {
      const amount = Math.ceil((ing.qty * servings) / recipe.serves);
      const entry = totals.get(ing.name);
      if (!entry) {
        totals.set(ing.name, { kind: ing.kind, total: amount });
      } else if (entry.kind !== ing.kind) {
        throw new InputError(`ingredient '${ing.name}' used with different kinds`);
      } else {
        entry.total += amount;
      }
    }
  }
  const names = [...totals.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  return names.map((n) => `${n} ${formatTotal(totals.get(n)!.kind, totals.get(n)!.total)}\n`).join("");
}

function main(): number {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    process.stderr.write("usage: shoplist RECIPES PLAN\n");
    return 2;
  }
  try {
    process.stdout.write(build(args[0], args[1]));
    return 0;
  } catch (e) {
    process.stderr.write(`shoplist: ${(e as Error).message}\n`);
    return 1;
  }
}

process.exitCode = main();

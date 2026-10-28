import { readFileSync } from 'node:fs';
const args = process.argv.slice(2);
if (args.length !== 2) { console.error('Usage: shoplist RECIPES PLAN'); process.exit(2); }
type Kind = 'count' | 'mass' | 'volume';
type Ingredient = { name: string; quantity: number; kind: Kind };
type Recipe = { serves: number; ingredients: Map<string, Ingredient> };
function lines(path: string): string[] {
  return readFileSync(path, 'utf8').split('\n').map(s => s.replace(/\r$/, '')).filter(s => !/^ *$/.test(s) && !s.startsWith('#'));
}
try {
  const recipes = new Map<string, Recipe>();
  let current: Recipe | undefined;
  for (const line of lines(args[0])) {
    const header = /^\[([a-z][a-z0-9_-]{0,29})\] ([1-9][0-9]{0,2})$/.exec(line);
    if (header) {
      if (recipes.has(header[1])) throw new Error('Duplicate recipe');
      current = { serves: Number(header[2]), ingredients: new Map() };
      recipes.set(header[1], current);
      continue;
    }
    const item = /^([a-z][a-z0-9_-]{0,29}) ([1-9][0-9]{0,5})(?: (g|kg|ml|l))?$/.exec(line);
    if (!item || !current || current.ingredients.has(item[1])) throw new Error('Invalid ingredient');
    const unit = item[3];
    current.ingredients.set(item[1], { name: item[1], quantity: Number(item[2]) * (unit === 'kg' || unit === 'l' ? 1000 : 1), kind: !unit ? 'count' : unit === 'g' || unit === 'kg' ? 'mass' : 'volume' });
  }
  const totals = new Map<string, { quantity: number; kind: Kind }>();
  for (const line of lines(args[1])) {
    const entry = /^([a-z][a-z0-9_-]{0,29}) ([1-9][0-9]{0,2})$/.exec(line);
    const recipe = entry && recipes.get(entry[1]);
    if (!entry || !recipe) throw new Error('Invalid plan');
    for (const item of recipe.ingredients.values()) {
      const total = totals.get(item.name) ?? { quantity: 0, kind: item.kind };
      if (total.kind !== item.kind) throw new Error('Incompatible units');
      total.quantity += Math.ceil(item.quantity * Number(entry[2]) / recipe.serves);
      totals.set(item.name, total);
    }
  }
  const output: string[] = [];
  for (const name of [...totals.keys()].sort()) {
    const { quantity, kind } = totals.get(name)!;
    let amount = String(quantity);
    if (kind !== 'count') {
      if (quantity < 1000) amount += kind === 'mass' ? ' g' : ' ml';
      else {
        const remainder = quantity % 1000;
        amount = String(Math.floor(quantity / 1000)) + (remainder ? '.' + String(remainder).padStart(3, '0').replace(/0+$/, '') : '') + (kind === 'mass' ? ' kg' : ' l');
      }
    }
    output.push(`${name} ${amount}`);
  }
  if (output.length) console.log(output.join('\n'));
} catch (error) { console.error(String(error)); process.exitCode = 1; }

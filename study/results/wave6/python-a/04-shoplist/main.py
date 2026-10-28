import re
import sys

NAME = r"[a-z][a-z0-9_-]{0,29}"
HEADER_RE = re.compile(rf"\[({NAME})\] ([1-9][0-9]{{0,2}})")
INGREDIENT_RE = re.compile(rf"({NAME}) ([1-9][0-9]{{0,5}})(?: (g|kg|ml|l))?")
PLAN_RE = re.compile(rf"({NAME}) ([1-9][0-9]{{0,2}})")

# unit -> (kind, factor to base unit)
UNITS = {
    None: ("count", 1),
    "g": ("mass", 1),
    "kg": ("mass", 1000),
    "ml": ("volume", 1),
    "l": ("volume", 1000),
}


class InputError(Exception):
    pass


def read_lines(path):
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"{path}: {e}")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    result = []
    for lineno, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "" or line.startswith("#"):
            continue
        result.append((lineno, line))
    return result


def parse_recipes(path):
    """Return {recipe: (serves, {ingredient: (kind, base_quantity)})}."""
    recipes = {}
    current = None
    for lineno, line in read_lines(path):
        m = HEADER_RE.fullmatch(line)
        if m:
            name = m.group(1)
            if name in recipes:
                raise InputError(f"{path}:{lineno}: duplicate recipe {name}")
            current = {}
            recipes[name] = (int(m.group(2)), current)
            continue
        m = INGREDIENT_RE.fullmatch(line)
        if not m:
            raise InputError(f"{path}:{lineno}: invalid line")
        if current is None:
            raise InputError(f"{path}:{lineno}: ingredient before first recipe")
        name, qty, unit = m.group(1), int(m.group(2)), m.group(3)
        if name in current:
            raise InputError(f"{path}:{lineno}: duplicate ingredient {name}")
        kind, factor = UNITS[unit]
        current[name] = (kind, qty * factor)
    return recipes


def parse_plan(path, recipes):
    plan = []
    for lineno, line in read_lines(path):
        m = PLAN_RE.fullmatch(line)
        if not m:
            raise InputError(f"{path}:{lineno}: invalid line")
        if m.group(1) not in recipes:
            raise InputError(f"{path}:{lineno}: unknown recipe {m.group(1)}")
        plan.append((m.group(1), int(m.group(2))))
    return plan


def shopping_list(recipes, plan):
    kinds = {}
    totals = {}
    for recipe, servings in plan:
        serves, ingredients = recipes[recipe]
        for name, (kind, qty) in ingredients.items():
            if kinds.setdefault(name, kind) != kind:
                raise InputError(f"ingredient {name} used with different kinds")
            amount = -(-qty * servings // serves)
            totals[name] = totals.get(name, 0) + amount
    return kinds, totals


def format_amount(kind, total):
    if kind == "count":
        return str(total)
    small, big = ("g", "kg") if kind == "mass" else ("ml", "l")
    if total < 1000:
        return f"{total} {small}"
    whole, frac = divmod(total, 1000)
    text = str(whole)
    if frac:
        text += "." + f"{frac:03d}".rstrip("0")
    return f"{text} {big}"


def main(argv):
    if len(argv) != 2:
        print("usage: shoplist RECIPES PLAN", file=sys.stderr)
        return 2
    try:
        recipes = parse_recipes(argv[0])
        plan = parse_plan(argv[1], recipes)
        kinds, totals = shopping_list(recipes, plan)
    except InputError as e:
        print(f"shoplist: {e}", file=sys.stderr)
        return 1
    out = [f"{name} {format_amount(kinds[name], totals[name])}\n"
           for name in sorted(totals, key=lambda n: n.encode("utf-8"))]
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

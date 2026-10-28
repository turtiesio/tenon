"""shoplist: combined shopping list from recipes and a meal plan."""
import re
import sys

NAME = r"[a-z][a-z0-9_-]{0,29}"
HEADER_RE = re.compile(rf"\[({NAME})\] ([1-9][0-9]{{0,2}})")
INGREDIENT_RE = re.compile(rf"({NAME}) ([1-9][0-9]{{0,5}})(?: (g|kg|ml|l))?")
PLAN_RE = re.compile(rf"({NAME}) ([1-9][0-9]{{0,2}})")

# unit -> (kind, factor to base unit)
UNITS = {None: ("count", 1), "g": ("mass", 1), "kg": ("mass", 1000),
         "ml": ("volume", 1), "l": ("volume", 1000)}


class InputError(Exception):
    pass


def read_lines(path: str) -> list[tuple[int, str]]:
    """Return (line number, text) for each non-ignored line of the file."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"{path}: cannot read: {e}")
    lines = text.split("\n")
    if text.endswith("\n") or text == "":
        lines.pop()
    result = []
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "" or line.startswith("#"):
            continue
        result.append((number, line))
    return result


def parse_recipes(path: str) -> dict:
    """Return {recipe: (serves, {ingredient: (kind, base quantity)})}."""
    recipes = {}
    current = None
    for number, line in read_lines(path):
        if m := HEADER_RE.fullmatch(line):
            name = m[1]
            if name in recipes:
                raise InputError(f"{path}:{number}: recipe {name} defined twice")
            current = {}
            recipes[name] = (int(m[2]), current)
        elif m := INGREDIENT_RE.fullmatch(line):
            if current is None:
                raise InputError(f"{path}:{number}: ingredient before first recipe")
            name = m[1]
            if name in current:
                raise InputError(f"{path}:{number}: duplicate ingredient {name}")
            kind, factor = UNITS[m[3]]
            current[name] = (kind, int(m[2]) * factor)
        else:
            raise InputError(f"{path}:{number}: invalid line: {line!r}")
    return recipes


def parse_plan(path: str, recipes: dict) -> list[tuple[str, int]]:
    plan = []
    for number, line in read_lines(path):
        m = PLAN_RE.fullmatch(line)
        if not m:
            raise InputError(f"{path}:{number}: invalid line: {line!r}")
        if m[1] not in recipes:
            raise InputError(f"{path}:{number}: unknown recipe {m[1]}")
        plan.append((m[1], int(m[2])))
    return plan


def shopping_list(recipes: dict, plan: list[tuple[str, int]]) -> dict:
    """Return {ingredient: (kind, total base amount)}."""
    totals = {}
    for recipe, servings in plan:
        serves, ingredients = recipes[recipe]
        for name, (kind, qty) in ingredients.items():
            amount = -(-qty * servings // serves)  # ceiling division
            prev_kind, prev_total = totals.get(name, (kind, 0))
            if prev_kind != kind:
                raise InputError(f"ingredient {name} used as both {prev_kind} and {kind}")
            totals[name] = (kind, prev_total + amount)
    return totals


def format_amount(kind: str, total: int) -> str:
    if kind == "count":
        return str(total)
    small, large = ("g", "kg") if kind == "mass" else ("ml", "l")
    if total < 1000:
        return f"{total} {small}"
    whole, frac = divmod(total, 1000)
    number = f"{whole}.{frac:03d}".rstrip("0") if frac else str(whole)
    return f"{number} {large}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: shoplist RECIPES PLAN", file=sys.stderr)
        return 2
    try:
        recipes = parse_recipes(argv[0])
        plan = parse_plan(argv[1], recipes)
        totals = shopping_list(recipes, plan)
    except InputError as e:
        print(f"shoplist: {e}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(
        f"{name} {format_amount(*totals[name])}\n"
        for name in sorted(totals, key=lambda n: n.encode())
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

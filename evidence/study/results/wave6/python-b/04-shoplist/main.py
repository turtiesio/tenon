import re
import sys
from pathlib import Path

NAME = r'[a-z][a-z0-9_-]{0,29}'


def lines(path):
    for line in Path(path).read_bytes().decode('utf-8').split('\n'):
        if line.endswith('\r'):
            line = line[:-1]
        if not line.strip(' ') or line.startswith('#'):
            continue
        yield line


def shopping_list(recipe_path, plan_path):
    recipes = {}
    current = None
    for line in lines(recipe_path):
        header = re.fullmatch(r'\[(' + NAME + r')\] ([1-9][0-9]{0,2})', line)
        if header:
            name, serves = header.groups()
            if name in recipes:
                raise ValueError('duplicate recipe')
            current = {}
            recipes[name] = (int(serves), current)
            continue
        item = re.fullmatch('(' + NAME + r') ([1-9][0-9]{0,5})(?: (g|kg|ml|l))?', line)
        if item is None or current is None:
            raise ValueError('invalid ingredient')
        name, quantity, unit = item.groups()
        if name in current:
            raise ValueError('duplicate ingredient')
        kind = 'mass' if unit in ('g', 'kg') else 'volume' if unit in ('ml', 'l') else 'count'
        current[name] = (int(quantity) * (1000 if unit in ('kg', 'l') else 1), kind)
    totals = {}
    for line in lines(plan_path):
        match = re.fullmatch('(' + NAME + r') ([1-9][0-9]{0,2})', line)
        if match is None or match[1] not in recipes:
            raise ValueError('invalid plan')
        serves, ingredients = recipes[match[1]]
        servings = int(match[2])
        for name, (quantity, kind) in ingredients.items():
            previous, previous_kind = totals.get(name, (0, kind))
            if previous_kind != kind:
                raise ValueError('incompatible ingredient kinds')
            totals[name] = (previous + (quantity * servings + serves - 1) // serves, kind)
    output = []
    for name, (total, kind) in sorted(totals.items()):
        if kind == 'count':
            amount = str(total)
        elif total < 1000:
            amount = f'{total} ' + ('g' if kind == 'mass' else 'ml')
        else:
            number = str(total // 1000)
            if total % 1000:
                number += '.' + f'{total % 1000:03d}'.rstrip('0')
            amount = number + (' kg' if kind == 'mass' else ' l')
        output.append(f'{name} {amount}')
    return output


def main():
    if len(sys.argv) != 3:
        print('expected RECIPES PLAN', file=sys.stderr)
        return 2
    try:
        output = shopping_list(*sys.argv[1:])
    except (OSError, UnicodeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for line in output:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())

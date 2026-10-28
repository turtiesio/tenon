# Task 04: shoplist (shopping list from recipes and a meal plan)

## Goal

Write a program that reads a recipe file and a meal-plan file and prints the
combined shopping list. Each recipe lists its ingredients for a stated
number of servings; the plan says how many servings of which recipes will be
cooked. Quantities are scaled to the planned servings (rounding up), converted
to base units, summed per ingredient across the whole plan, and printed in a
normalized unit.

## Interface

```
shoplist RECIPES PLAN
```

- **Arguments.** Exactly two arguments: the path of the recipe file and the
  path of the plan file. Any other number of arguments is a usage error:
  print a message to stderr, print **nothing** on stdout, and exit `2`.
- **Files.** Both files are UTF-8 text. Lines are split on `\n`. If a file
  ends with `\n`, there is no extra empty line after it. A final line without
  `\n` is still a line. One trailing `\r` is removed from each line. In both
  files, a line that is empty or contains only spaces, and a line whose first
  character is `#`, is ignored.
- **Errors (exit 1).** If a file cannot be read, or either file is invalid
  (rules 1-3), print a message to stderr, print **nothing** on stdout, and
  exit `1`.
- **stdout.** The shopping list (rule 5).
- **Exit codes.** `0` success, `1` unreadable or invalid input, `2` usage
  error.

## Rules

A **name** matches `[a-z][a-z0-9_-]{0,29}`. Tokens on a line are separated
by exactly **one** space, with no leading or trailing spaces.

1. **Recipe file.** Every non-ignored line is one of:
   - a **header** `[<recipe>] <serves>`, where `<recipe>` is a name and
     `<serves>` matches `[1-9][0-9]{0,2}`. It starts a new recipe. Each
     recipe name appears in at most one header.
   - an **ingredient** `<ingredient> <qty>` or `<ingredient> <qty> <unit>`,
     where `<ingredient>` is a name, `<qty>` matches `[1-9][0-9]{0,5}` and
     `<unit>` is one of `g`, `kg`, `ml`, `l`. It belongs to the most recent
     header. An ingredient line before the first header is invalid. An
     ingredient may appear at most once in each recipe.

   A recipe may have no ingredients.
2. **Kinds and base units.** An ingredient line with `g` or `kg` is a
   **mass** in grams (1 kg = 1000 g). One with `ml` or `l` is a **volume** in
   millilitres (1 l = 1000 ml). One without a unit is a **count**.
3. **Plan file.** Every non-ignored line is `<recipe> <servings>`, where
   `<recipe>` names a recipe from the recipe file and `<servings>` matches
   `[1-9][0-9]{0,2}`. The same recipe may appear on several lines.
4. **Scaling and summing.** For each plan line and each ingredient of its
   recipe, the amount is Q × servings / serves, **rounded up** to a whole
   number, where Q is the ingredient's quantity in its base unit (grams,
   millilitres or a count). Round each plan line's amount separately, then
   add the amounts per ingredient name over all plan lines. If one
   ingredient name is used with two different kinds anywhere in the plan's
   recipes (for example `milk 2` and `milk 50 ml`), the input is invalid.
   Ingredients of recipes that are not in the plan are not checked for this.
5. **Output.** One line per ingredient that occurs in at least one planned
   recipe, sorted by ingredient name (byte order): the name, one space, and
   the total:
   - a count is printed as the integer, e.g. `egg 10`;
   - a mass below 1000 g is printed as `<n> g`; a volume below 1000 ml as
     `<n> ml`;
   - a mass of 1000 g or more is printed in `kg` and a volume of 1000 ml or
     more in `l`: the total div 1000, then, if the total mod 1000 is not
     zero, a `.` and the total mod 1000 written with 3 digits with trailing
     zeros removed. For example 2025 ml is `2.025 l`, 1500 g is `1.5 kg`, and
     3000 g is `3 kg`.

   Every line ends with `\n`. An empty plan gives empty output.
6. **Limits.** At most 1000 lines per file.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

In Examples 1-3 the working directory contains `recipes.txt`:
```
# weekly recipes
[pancakes] 4
flour 250 g
milk 1 l
egg 3
butter 30 g

[omelette] 2
egg 5
milk 50 ml
salt 2 g
[salad] 3
lettuce 1
olive-oil 45 ml
```

### Example 1: scaling, rounding up, merging units

`plan.txt`:
```
pancakes 6
omelette 1
salad 2
pancakes 2
```

cmd: `shoplist recipes.txt plan.txt`

stdout:
```
butter 60 g
egg 10
flour 500 g
lettuce 1
milk 2.025 l
olive-oil 30 ml
salt 1 g
```
exit: `0`

(Eggs: 3 × 6 / 4 = 4.5 → 5, 5 × 1 / 2 = 2.5 → 3, 3 × 2 / 4 = 1.5 → 2, total
10. Milk: 1500 + 25 + 500 = 2025 ml. Lettuce: 1 × 2 / 3 → 1. Salt: 2 × 1 / 2
= 1.)

### Example 2: whole kilograms and an empty plan

`plan.txt`:
```
pancakes 48
```

cmd: `shoplist recipes.txt plan.txt`

stdout:
```
butter 360 g
egg 36
flour 3 kg
milk 12 l
```
exit: `0`

With a `plan.txt` that contains only `# nothing this week\n`, the same cmd
gives stdout (empty) and exit `0`.

### Example 3: invalid plans

Each of these, with cmd `shoplist recipes.txt plan.txt`, gives stdout
(empty) and exit `1`:

- `plan.txt` is `pancakes 2\nwaffles 1\n` (no recipe `waffles`).
- `plan.txt` is `salad 0\n` (servings must be at least 1).
- `plan.txt` is `salad  2\n` (two spaces).

### Example 4: invalid recipe files

`plan.txt` is `soup 1\n` in each case. Each of these recipe files, with cmd
`shoplist r.txt plan.txt`, gives stdout (empty) and exit `1`:

- `r.txt` is `[soup] 2\nmilk 2\n[stew] 1\nmilk 50 ml\n[soup] 3\n` (recipe
  `soup` defined twice).
- `r.txt` is `salt 2 g\n[soup] 2\n` (ingredient before the first header).
- `r.txt` is `[soup] 2\nsalt 2 oz\n` (unknown unit).
- `r.txt` does not exist.

With `r.txt` being `[soup] 2\nmilk 2\n[stew] 1\nmilk 50 ml\n`, the same cmd
gives stdout `milk 1\n` and exit `0` (`stew` is not planned, so the two kinds
of `milk` never meet).

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`: cmd `shoplist`, cmd
`shoplist recipes.txt`, cmd `shoplist a b c`.

## Not required

- Fractional quantities, other units (cups, ounces), or unit conversion
  between mass and volume.
- Subtracting a pantry or grouping by aisle.
- Any particular stderr wording.

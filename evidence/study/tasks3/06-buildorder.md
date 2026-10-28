# Task 06: buildorder (dependency ordering from a rules file)

## Goal

Write a program that reads build rules of the form `target: dependencies`
and prints an order in which everything can be built, with every item after
all of its dependencies and ties broken by name, so the order is unique. It can
instead print the items grouped by level, and it can restrict the work to
what one or more chosen targets need. Dependency cycles are reported with a
deterministic list of the items that cannot be ordered.

## Interface

```
buildorder [-l] [-t NAME]...
```

- **Arguments** are processed left to right. `-l` selects level output
  (rule 6) and may be repeated. `-t NAME` (two arguments) selects a target
  (rule 4); the argument after `-t` is always NAME; `-t` may be repeated to
  select several targets. Any other argument, and `-t` without a following
  argument, is a usage error.
- **stdin.** The rules (rule 1). Lines are split on `\n`. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** The build order (rule 5), the levels (rule 6), or the cycle
  report (rule 7). Every line ends with `\n`.
- **Errors.** On a usage error or an input error, print a message to stderr,
  print **nothing** on stdout, and exit with the code below. Usage errors are
  detected before stdin is read. The whole input is checked before any output
  is written.
- **Exit codes.**
  - `0`: success.
  - `1`: a cycle among the selected items (rule 7).
  - `2`: usage error.
  - `3`: input error: a malformed line (rule 1), or a `-t` NAME that is not
    an item (rule 2).

## Rules

1. **Rule lines.** A line that is empty, contains only spaces, or whose first
   non-space character is `#` is ignored. Every other line must contain a `:`.
   Split it at the **first** `:`:
   - the part before it, with leading and trailing spaces removed, must be a
     single name: the *target*;
   - the part after it is split on runs of one or more spaces into zero or
     more names: the target's *dependencies*.

   A name matches `[A-Za-z0-9_./-]+`. A line breaks the rules if the target
   part is empty or is not exactly one valid name (for example `a b: c`), or
   if any dependency is not a valid name (a second `:` therefore makes the
   line malformed).
2. **Items.** The items are all names that appear anywhere, as a target or
   as a dependency. A name that is never a target has no dependencies. A
   target may appear on several lines; its dependencies are the union of all
   of them. Repeating a dependency has no extra effect. Names are
   case-sensitive.
3. **Self and cycles.** `a: a` makes `a` depend on itself, which is a cycle.
4. **Selection.** Without `-t`, all items are selected. With one or more
   `-t` NAMEs, the selected items are those NAMEs plus everything they depend
   on, directly or indirectly. Only selected items are ordered, leveled or
   reported. Dependencies among unselected items do not matter, even if they
   form a cycle.
5. **Build order (default).** Repeat until no selected item is left: among
   the selected items that are not yet printed and whose dependencies have
   all been printed, print the one that is **smallest in byte order** on its
   own line. (Upper-case letters sort before lower-case.)
6. **Levels (`-l`).** An item with no dependencies has level 0. Any other item
   has level 1 + the largest level of its dependencies. For every level from
   0 to the largest level, print one line `<level>: <names>`, where names are
   the selected items with that level, in byte order, separated by single
   spaces. (Every level in that range has at least one item.)
7. **Cycles.** If the procedure of rule 5 stops before every selected item
   has been printed, the selected items that were not printed are exactly
   those on a cycle or depending, directly or indirectly, on one. In that
   case print **only** one line: `CYCLE` followed by a space and the names of
   those items in byte order, separated by single spaces. Do not print a
   partial order or levels. Exit `1`. This applies with and without `-l`.
8. **Empty.** If there are no items, the output is empty and the exit code is
   `0`.
9. **Limits.** At most 10000 lines and 10000 items. Names are at most 64
   bytes.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: an order and its levels

stdin for both runs:
```
# build rules
app: lib util
lib: core
util: core
test: app
```

cmd: `buildorder` gives stdout:
```
core
lib
util
app
test
```
exit: `0`

cmd: `buildorder -l` gives stdout:
```
0: core
1: lib util
2: app
3: test
```
exit: `0`

### Example 2: merged rules and plain dependencies

cmd: `buildorder`

stdin:
```
b: a
  b :   c   a
c:
Z: b
```
stdout:
```
a
c
b
Z
```
exit: `0`

(`a` is never a target, so it has no dependencies. `b` depends on `a` and
`c`. When `b` is printed, only `Z` is left.)

### Example 3: a cycle, with and without selection

stdin for all three runs:
```
app: lib util
lib: core
util: core
test: app
x: y
y: x
z: x
```

- cmd: `buildorder` gives stdout `CYCLE x y z\n` and exit `1`.
- cmd: `buildorder -t app` gives stdout `core\nlib\nutil\napp\n` and exit
  `0` (the cycle is not selected).
- cmd: `buildorder -l -t z -t lib` gives stdout `CYCLE x y z\n` and exit `1`.

### Example 4: input errors

Each of these gives stdout (empty) and exit `3`:

- cmd: `buildorder` with stdin `lib core\n` (no `:`).
- cmd: `buildorder` with stdin `a b: c\n` (two names before `:`).
- cmd: `buildorder` with stdin `a: b:c\n` (a dependency containing `:`).
- cmd: `buildorder -t nope` with stdin `a: b\n` (`nope` is not an item).

### Example 5: usage errors and empty input

- cmd: `buildorder -x` gives stdout (empty) and exit `2`.
- cmd: `buildorder -t` gives stdout (empty) and exit `2`.
- cmd: `buildorder rules.txt` gives stdout (empty) and exit `2`.
- cmd: `buildorder -l` with stdin `# empty\n` gives stdout (empty) and exit
  `0`.

## Not required

- Running any build commands, file timestamps, or make-style variables.
- Reading rules from files given as arguments.
- Any particular stderr wording.

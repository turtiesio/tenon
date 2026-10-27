# Task 10: sand (falling-sand simulation)

## Goal

Write a deterministic simulation of sand grains falling on a rectangular
grid with rock and sand sources. In every tick each grain tries to fall
straight down, then diagonally down-left, then down-right; grains in the
bottom row fall out of the grid and are lost. Sources add a new grain below
themselves after the grains have moved. The simulation runs for a given
number of ticks or stops early as soon as a tick changes nothing, and then
prints the final grid and a summary line.

## Interface

```
sand TICKS
```

- **Arguments.** Exactly one argument, TICKS, matching `[0-9]{1,4}` (0 is
  allowed). A wrong argument count or a malformed TICKS is a usage error:
  print a message to stderr, print **nothing** on stdout, do not read stdin,
  and exit `2`.
- **stdin.** The grid, UTF-8 text. Lines are split on `\n`. If the input
  ends with `\n`, there is no extra empty line after it. A final line without
  `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** The final state (see "Output").
- **Exit codes.** `0` success, `1` invalid grid, `2` usage error.

## Input

Every line is one grid row, top row first. There must be 1 to 30 rows, all
of the same length, which must be 1 to 30 characters. Each character is one
of:

- `.` empty,
- `#` rock,
- `o` a sand grain,
- `S` a source (it never moves and acts like rock for grains).

Anything else (no rows, an empty row, rows of different lengths, more than
30 rows or columns, any other character) is an **invalid grid**: print a
message to stderr, print **nothing** on stdout, and exit `1`.

## Rules

Positions are (x, y): x is the column from 0 (left), y the row from 0 (top).
H is the number of rows and W the number of columns.

1. **Ticks.** The simulation runs ticks 1, 2, ..., TICKS. Each tick has two
   phases: grains move (rule 2), then sources emit (rule 3).
2. **Moving grains.** Visit the cells row by row from the **bottom** row
   (y = H − 1) up to the top row (y = 0), and within a row from left
   (x = 0) to right. Whenever the visited cell holds a grain:
   - If the grain is in the bottom row, it **falls out**: the cell becomes
     empty and the lost count increases by 1.
   - Otherwise it tries these targets in order and moves to the **first**
     one that is inside the grid and empty **at that moment**: (x, y + 1),
     then (x − 1, y + 1), then (x + 1, y + 1). If none is, it stays.

   A grain moves at most one row per tick. (A grain that moves lands in a
   row that has already been visited, so it is not visited again in the
   same tick.) A grain that moves earlier in a tick changes what later
   grains see.
3. **Sources.** After all grains have been visited, every source that is
   not in the bottom row and whose cell directly below, (x, y + 1), is empty
   puts a new grain in that cell. New grains do not move until the next
   tick.
4. **Early stop.** A tick **changes nothing** if no grain moved, no grain
   fell out, and no source emitted. When a tick changes nothing, the
   simulation stops after it (this tick is still counted).
5. **Limits.** At most 30 × 30 cells and 9999 ticks.

## Output

1. The final grid, one line per row, with the same characters as the input
   (`.`, `#`, `o`, `S`).
2. Then one summary line:

   ```
   ticks=<t> grains=<g> lost=<l> stable=<yes|no>
   ```
   - `<t>`: the number of ticks run (TICKS, or fewer after an early stop);
   - `<g>`: the number of grains on the final grid;
   - `<l>`: the number of grains that fell out;
   - `stable=yes` if the simulation stopped because the last tick run
     changed nothing, otherwise `stable=no` (also when TICKS is 0).

Every line ends with `\n`.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: a source above a rock

stdin for all runs:
```
..S..
.....
.....
..#..
.....
#...#
```

cmd: `sand 3` gives stdout:
```
..S..
..o..
..o..
.o#..
.....
#...#
ticks=3 grains=3 lost=0 stable=no
```
exit: `0`

cmd: `sand 5` gives stdout:
```
..S..
..o..
..o..
.o#..
.o...
#o..#
ticks=5 grains=5 lost=0 stable=no
```
exit: `0`

cmd: `sand 30` gives stdout:
```
..S..
..o..
..o..
.o#..
.o...
#o..#
ticks=30 grains=5 lost=25 stable=no
```
exit: `0`

(In tick 3, the grain at (2, 2) cannot fall onto the rock and slides to
(1, 3); then the grain at (2, 1) falls to (2, 2); then the source emits at
(2, 1). From tick 6 on, every tick one grain falls out of the bottom row at
(1, 5) and the column above it moves down by one.)

### Example 2: a pile settles

cmd: `sand 99`

stdin:
```
...o...
...o...
...o...
...o...
...o...
.......
#######
```
stdout:
```
.......
.......
.......
.......
...o...
.oooo..
#######
ticks=6 grains=5 lost=0 stable=yes
```
exit: `0`

With the same stdin, cmd `sand 3` gives stdout:
```
.......
.......
.......
...o...
...o...
..ooo..
#######
ticks=3 grains=5 lost=0 stable=no
```
exit: `0`

(Down-left is tried before down-right, so the pile grows to the left
first. Tick 6 changes nothing, so the run stops there.)

### Example 3: order within a row, falling out, zero ticks

stdin for all runs (no final newline after `#.#`):
```
o.o
#.#
```

- cmd: `sand 1` gives stdout `..o\n#o#\nticks=1 grains=2 lost=0 stable=no\n`
  and exit `0`. (The left grain is visited first and takes (1, 1); the
  right grain then finds it occupied.)
- cmd: `sand 9` gives stdout `...\n#.#\nticks=4 grains=0 lost=2 stable=yes\n`
  and exit `0`.
- cmd: `sand 0` gives stdout `o.o\n#.#\nticks=0 grains=2 lost=0 stable=no\n`
  and exit `0`.

With stdin `oS\n.#\n`, cmd `sand 5` gives stdout
`.S\n.#\nticks=3 grains=0 lost=1 stable=yes\n` and exit `0` (the source
sits on rock and never emits).

### Example 4: errors

Each of these gives stdout (empty) and exit `1` with cmd `sand 1`:

- stdin `...\n..\n` (rows of different lengths)
- stdin `.x.\n` (unknown character)
- empty stdin
- stdin of one row of 31 `.` characters followed by `\n`

Each of these gives stdout (empty) and exit `2`: cmd `sand`, cmd `sand -1`,
cmd `sand 10000`, cmd `sand 1 2`.

## Not required

- Water, other materials, or grains moving sideways without falling.
- Animation or printing intermediate states.
- Any particular stderr wording.

# Task 10: robots (warehouse robots on a grid)

## Goal

Write a deterministic simulation of robots moving on a rectangular grid
with walls and coins. Each robot repeats its own short program of moves.
Robots act one at a time in a fixed order every tick; a move into a wall,
off the grid, or into another robot is blocked and counted as a bump. A
robot that enters a coin cell collects the coin. After a given number of
ticks, print the final grid and each robot's statistics.

## Interface

```
robots TICKS
```

- **Arguments.** Exactly one argument, TICKS, matching `[0-9]{1,5}` (0 is
  allowed). A wrong argument count or a malformed TICKS is a usage error:
  message on stderr, exit `2`, stdout empty, stdin not read.
- **stdin.** The world (see "Input"), UTF-8 text. Lines are split on `\n`.
  If the input ends with `\n`, there is no extra empty line after it. A
  final line without `\n` is still a line. One trailing `\r` is removed from
  each line.
- **stdout.** The final state (see "Output").
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Input

1. **Grid.** The lines up to the first empty line (or up to the end of the
   input if there is no empty line) are the grid rows, top row first. There
   must be at least one row, and all rows must have the same length, at
   least 1 and at most 50 characters (at most 50 rows). Each character is
   one of:
   - `.` floor, `#` wall, `*` floor with a coin,
   - `A`-`Z` a robot standing on floor (no coin). Each letter appears at
     most once.
2. **Programs.** Every line after the first empty line is a program line
   `<letter>:<moves>`, where `<letter>` is a robot that is on the grid and
   `<moves>` is zero or more characters from `N`, `E`, `S`, `W`, `.` (at
   most 100). Each robot has at most one program line. A robot without a
   program line has an empty program.
3. Anything else is **invalid input** (a missing grid, rows of different
   lengths, an unknown character, a repeated robot letter, an empty line or
   malformed line among the programs, a program for a letter that is not on
   the grid, two programs for one robot): print a message to stderr, print
   **nothing** on stdout, and exit `1`.

## Rules

Positions are (x, y): x is the column from 0 (left), y the row from 0
(top). `N` is y − 1, `S` is y + 1, `E` is x + 1, `W` is x − 1.

1. **Ticks.** The simulation runs ticks t = 0, 1, ..., TICKS − 1. In each
   tick the robots act **one at a time in alphabetical order** of their
   letters. A robot that acts later in a tick sees the positions left by
   the robots that acted before it in the same tick.
2. **Instruction.** In tick t, a robot with the program m0..m(L−1) (L ≥ 1)
   executes m(t mod L), so programs repeat. A robot with an empty program
   does nothing.
3. **Moves.** `.` means wait (nothing happens, nothing is counted). For a
   direction, let the target be the neighbouring cell in that direction.
   - If the target is outside the grid, is a wall, or is occupied by
     another robot at that moment, the robot does not move and its
     **bumps** count increases by 1.
   - Otherwise the robot moves to the target and its **moves** count
     increases by 1. If the target holds a coin, the robot collects it: its
     **coins** count increases by 1 and the cell becomes plain floor.
4. **Limits.** At most 26 robots, so a run does at most 26 × 99999 robot
   actions.

## Output

1. The final grid, one line per row: walls `#`, coins that were not
   collected `*`, floor `.`, and each robot's letter at its final position.
2. Then one line per robot, in alphabetical order:
   `<letter> <x> <y> moves=<m> bumps=<b> coins=<c>`.

Every line ends with `\n`.

## Examples

Each line shown ends with `\n`.

### Example 1: walls, coins and bumps

cmd: `robots 4`

stdin:
```
#######
#A..*.#
#.##..#
#..*B.#
#######

A:EEEE
B:NNW.
```
stdout:
```
#######
#..AB.#
#.##..#
#..*..#
#######
A 3 1 moves=2 bumps=2 coins=0
B 4 1 moves=2 bumps=1 coins=1
```
exit: `0`

(Tick 1: A moves to (3,1), then B moves north onto the coin at (4,1).
Tick 2: A bumps into B, and B bumps into A. Tick 3: A bumps again; B waits.)

### Example 2: order within a tick

cmd: `robots 1`

stdin:
```
..BA.
.CD..

A:E
B:E
C:E
D:E
```
stdout:
```
...BA
.C.D.
A 4 0 moves=1 bumps=0 coins=0
B 3 0 moves=1 bumps=0 coins=0
C 1 1 moves=0 bumps=1 coins=0
D 3 1 moves=1 bumps=0 coins=0
```
exit: `0`

(A acts first and frees (3,0) for B. C acts before D, so D still blocks
it.)

### Example 3: repeating programs, the grid edge, no program

cmd: `robots 7`

stdin:
```
.*.
.A*
B.C

C:E
A:N.S
```
stdout:
```
.A.
..*
B.C
A 1 0 moves=5 bumps=0 coins=1
B 0 2 moves=0 bumps=0 coins=0
C 2 2 moves=0 bumps=7 coins=0
```
exit: `0`

(A executes N . S N . S N. C tries to leave the grid 7 times. B has no
program.)

With the same stdin, cmd `robots 0` prints the grid unchanged followed by
`A 1 1 moves=0 bumps=0 coins=0`, `B 0 2 moves=0 bumps=0 coins=0` and
`C 2 2 moves=0 bumps=0 coins=0`, and exits `0`.

### Example 4: errors

Each of these gives stdout (empty) and exit `1` with cmd `robots 1`:

- stdin `..\n.\n` (rows of different lengths)
- stdin `..BA.\n.AB..\n\nA:E\n` (robot `A` appears twice)
- stdin `A.\n\nB:E\n` (no robot `B`)
- stdin `A.\n\nA:X\n` (unknown move)
- stdin `A?\n` (unknown grid character)

Each of these gives stdout (empty) and exit `2`: cmd `robots`, cmd
`robots x`, cmd `robots 1 2`.

## Not required

- Simultaneous movement, pushing, or swapping places.
- Robots on coin cells at the start (the grid cannot express it).
- Any particular stderr wording.

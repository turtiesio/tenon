# Task 05: standings (league table from match results)

## Goal

Write a program that reads football (soccer) match results, one per line,
and prints the league table: games played, wins, draws, losses, goals,
goal difference, points and recent form for every team, sorted by a fixed
chain of tie-breakers, with shared positions for teams that are fully tied.
The point values for a win, a draw and a loss can be changed with an option.
Malformed input is rejected with the line number before anything is printed.

## Interface

```
standings [-p W,D,L]
```

- **Arguments.** Either none, or exactly the two arguments `-p` and a value
  `W,D,L`: three numbers separated by commas, each matching `[0-9]{1,2}`
  (for example `2,1,0`). Default: `3,1,0`. Anything else is a usage error:
  print a message to stderr, print nothing on stdout, exit `2`, and do not
  read stdin.
- **stdin.** Match results, one per line. Lines are split on `\n`. A final
  line without `\n` is still a line. One trailing `\r` is removed from each
  line. Lines that are empty, contain only spaces, or start with `#` are
  ignored.
- **stdout.** The table (rule 4). Every line ends with `\n`.
- **Invalid input (exit 1).** If any non-ignored line is not a valid result
  (rule 1), print a message to stderr that includes the 1-based line number,
  print **nothing** on stdout, and exit `1`. The whole input is checked
  before any output is written.
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Rules

1. **Result lines.** A result line consists of tokens separated by **single**
   spaces, with no leading or trailing spaces:

   ```
   <home team words> <hg>-<ag> <away team words>
   ```

   - Exactly one token is a score, matching `[0-9]{1,2}-[0-9]{1,2}`; `hg` is
     the home team's goals and `ag` the away team's goals (leading zeros
     allowed).
   - At least one token comes before the score and at least one after it.
     The tokens before it, joined by single spaces, are the home team name;
     the tokens after it are the away team name.
   - Every name token matches `[A-Za-z0-9.&']+`.
   - The two team names must differ.
   - Team names are case-sensitive: `Lions` and `lions` are two teams.
2. **Statistics.** For every team that appears in at least one result:
   P (played), W (won), D (drawn), L (lost), GF (goals for), GA (goals
   against), GD = GF − GA, and Pts = W×(win points) + D×(draw points) +
   L×(loss points). The home team wins if hg > ag, the away team wins if
   ag > hg, and both draw if hg = ag.
3. **Order.** Sort teams by Pts descending, then GD descending, then GF
   descending, then W descending, then by name ascending (byte order).
4. **Position.** A team's position is 1 + the number of teams with a better
   (Pts, GD, GF, W), compared in that order. Teams that are equal in all four
   share a position (so positions may go `1, 2, 2, 4`). The name only decides
   the order of printing.
5. **Form.** The results of the team's last (at most) 5 matches, in input
   order, oldest first, one letter each: `W`, `D` or `L`.
6. **Table format.** Let N be the length of the longest team name. Each team
   is printed as one line made by concatenating:
   - the position, right-aligned in a field of width 2, then `. `;
   - the name, left-aligned and padded with spaces to width N;
   - P, W, D and L, each right-aligned in a field of width 3;
   - the text `GF:GA` (for example `5:4`), right-aligned in a field of
     width 7;
   - GD, right-aligned in a field of width 4, written with a `+` if positive,
     a `-` if negative, and as `0` if zero;
   - Pts, right-aligned in a field of width 4;
   - one space, then the form.

   "Right-aligned in a field of width k" means padded on the left with spaces
   to k characters; a longer value is printed in full, without padding. There
   is no header line. With no results, the output is empty.
7. **Limits.** At most 10000 result lines and at most 99 teams.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: a small league

cmd: `standings`

stdin:
```
# Matchday 1
Lions 2-1 Tigers
Bears 0-0 Wolves
Old Boys 3-3 Lions

Tigers 1-0 Bears
Wolves 2-0 Old Boys
```
stdout:
```
 1. Wolves    2  1  1  0    2:0  +2   4 DW
 2. Lions     2  1  1  0    5:4  +1   4 WD
 3. Tigers    2  1  0  1    2:2   0   3 LW
 4. Bears     2  0  1  1    0:1  -1   1 DL
 5. Old Boys  2  0  1  1    3:5  -2   1 DL
```
exit: `0`

(Wolves and Lions both have 4 points; Wolves have the better goal
difference. N is 8, the length of `Old Boys`.)

### Example 2: other point values and shared positions

cmd: `standings -p 2,1,0`

stdin:
```
A 1-1 B
C 0-0 D
E 2-0 F
```
stdout:
```
 1. E  1  1  0  0    2:0  +2   2 W
 2. A  1  0  1  0    1:1   0   1 D
 2. B  1  0  1  0    1:1   0   1 D
 4. C  1  0  1  0    0:0   0   1 D
 4. D  1  0  1  0    0:0   0   1 D
 6. F  1  0  0  1    0:2  -2   0 L
```
exit: `0`

### Example 3: form keeps the last five matches

cmd: `standings`

stdin:
```
X 1-0 Y
Y 2-2 X
X 0-1 Y
Y 0-3 X
X 4-4 Y
X 1-0 Y
```
stdout:
```
 1. X  6  3  2  1   11:7  +4  11 DLWDW
 2. Y  6  1  2  3   7:11  -4   5 DWLDL
```
exit: `0`

(X's six results are W D L W D W; the oldest is dropped.)

### Example 4: invalid input

Each of these gives stdout (empty) and exit `1`:

- cmd: `standings` with stdin `Lions 2:1 Tigers\n` (no score token).
- cmd: `standings` with stdin `Lions 2-1 Tigers\nLions 1-1 Lions\n` (a team
  plays itself, on line 2).
- cmd: `standings` with stdin `Lions  2-1 Tigers\n` (two spaces).
- cmd: `standings` with stdin `2-1 Tigers\n` (no home team).
- cmd: `standings` with stdin `Lions 2-1 1-0 Tigers\n` (two score tokens).
- cmd: `standings` with stdin `Lions 100-1 Tigers\n` (a three-digit score).

### Example 5: usage errors and empty input

- cmd: `standings -p 3,1` gives stdout (empty) and exit `2`.
- cmd: `standings -p` gives stdout (empty) and exit `2`.
- cmd: `standings -x` gives stdout (empty) and exit `2`.
- cmd: `standings` with stdin `# nothing yet\n\n` gives stdout (empty) and
  exit `0`.

## Not required

- Head-to-head tie-breakers, deductions, forfeits, or extra time.
- Team names with characters outside the stated set.
- More than 99 teams.
- Any particular stderr wording.

# Task 08: sheet (spreadsheet cell service with formulas)

## Goal

Write an in-memory spreadsheet service driven by a line protocol on stdin and
stdout. Cells hold integers or formulas that add and subtract numbers, other
cells and rectangular `SUM` ranges. Values are always computed from the
current contents, so changing a cell changes every formula that depends on
it. A formula that would create a circular reference is rejected, and values
that grow too large are reported as overflow. Each input line is one command
and gets exactly one response line.

## Interface

```
sheet
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. Lines are split on `\n`. The last line may
  lack `\n`. One trailing `\r` is removed from each line.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit code.** `0` at end of input. All cells start empty.

## Cells and contents

- A **cell name** is one upper-case column letter `A`-`Z` followed by a row
  number 1-99 without leading zeros: it matches `[A-Z][1-9][0-9]?`. `A0`,
  `A01`, `A100` and `a1` are not cell names.
- A cell is either **empty** or holds **contents**, which are one of:
  - an **integer literal**: matches `-?[0-9]{1,9}` (for example `42`, `-7`,
    `007`);
  - a **formula**: `=`, then an optional `-`, then a *term*, then zero or more
    pairs of an operator (`+` or `-`) and a term, with no spaces anywhere. A
    term is one of:
    - a number matching `[0-9]{1,9}`;
    - a cell name;
    - `SUM(<cell>:<cell>)`: the sum of every cell in the rectangle with
      these two corners, in any order (`SUM(B3:A1)` covers the same six cells
      as `SUM(A1:B3)`).

  Examples: `=A1+A2`, `=-C1+100`, `=SUM(B1:B3)-1`, `=5`. Not formulas: `=`,
  `=A1+`, `=+A1`, `=A1*2`, `=--A1`, `=sum(A1:A2)`, `=SUM(A1)`.
- A formula **references** every cell it names, including every cell inside
  each of its `SUM` rectangles.

## Commands

Tokens are separated by **exactly one** space, with no leading or trailing
spaces. Command names are upper case.

| Command | Response |
|---|---|
| `SET <cell> <contents>` | `OK`, or `ERR cycle` (rule 2). The cell's contents are replaced. |
| `CLEAR <cell>` | `OK`. The cell becomes empty (also if it already was). |
| `GET <cell>` | The cell's value as a decimal integer (rule 1), or `ERR overflow` (rule 3). |
| `SHOW <cell>` | The cell's contents exactly as given in the last successful `SET`, or `EMPTY`. |

Any other line (unknown or lower-case command, wrong number of tokens, an
invalid cell name, contents that are neither an integer literal nor a valid
formula, an empty line) gets `ERR bad command` and changes nothing.

## Rules

1. **Values.** An empty cell has value 0. An integer literal has its numeric
   value (`007` is 7, `-0` is 0). A formula's value is computed from the
   **current** values of the cells it references: terms are added or
   subtracted left to right, a leading `-` negates the first term, and `SUM`
   adds the values of all cells in its rectangle. Values are printed with no
   leading zeros and a `-` if negative.
2. **Cycles.** `SET <cell> <formula>` is rejected with `ERR cycle`, and the
   cell keeps its old contents, if the new formula would make the cell
   depend on itself: that is, if the cell is among the cells the formula
   references, or if any referenced cell depends on it, directly or
   indirectly, through the formulas currently stored. Setting an integer
   literal never creates a cycle. A successful `SET` never leaves a cycle, so
   the sheet never contains one.
3. **Overflow.** A cell's value is *overflow* if any cell its formula
   references has an overflow value, or if the exact result of its formula has
   an absolute value greater than 10^12 (1000000000000). `GET` of such a cell
   responds `ERR overflow`. A later change can make the value valid again.
   (Within the limits below, intermediate sums of non-overflow values fit
   easily in a signed 64-bit integer.)
4. **Responses are exact strings.** The only error responses are
   `ERR bad command`, `ERR cycle` and `ERR overflow`.
5. **Limits.** At most 20000 commands, and each command line is at most 200
   bytes. All 26 × 99 cells may be used.

## Examples

Each line shown ends with `\n`. For every example, cmd is `sheet` and exit is
`0`, except where noted.

### Example 1: literals and a dependent formula

stdin:
```
SET A1 10
SET A2 32
SET A3 =A1+A2
GET A3
SET A1 -5
GET A3
SHOW A3
GET B7
SHOW B7
```
stdout:
```
OK
OK
OK
42
OK
27
=A1+A2
0
EMPTY
```

### Example 2: ranges and cycles

stdin:
```
SET B1 1
SET B2 2
SET B3 3
SET C1 =SUM(B3:B1)-1
GET C1
SET B2 =C1
GET B2
SET D1 =D1+1
SET D1 =-C1+100
GET D1
CLEAR B3
GET C1
GET D1
SHOW B3
```
stdout:
```
OK
OK
OK
OK
5
ERR cycle
2
ERR cycle
OK
95
OK
2
98
EMPTY
```

(`C1` references `B1`, `B2` and `B3`, so `B2` may not reference `C1`.)

### Example 3: overflow

stdin:
```
SET A1 999999999
SET A2 =A1+A1+A1+A1+A1+A1+A1+A1+A1+A1
SET A3 =A2+A2+A2+A2+A2+A2+A2+A2+A2+A2
SET A4 =A3+A3+A3+A3+A3+A3+A3+A3+A3+A3
GET A4
SET A5 =A4+A4
GET A5
SET A6 =A5-A5
GET A6
SET A5 0
GET A6
SHOW A5
```
stdout:
```
OK
OK
OK
OK
999999999000
OK
ERR overflow
OK
ERR overflow
OK
0
0
```

(`A6` is overflow while `A5` is, even though `A5-A5` would be 0.)

### Example 4: malformed commands

stdin:
```
SET a1 5
SET A100 1
SET A1 =A1+
SET A1 1+2
SET A1 = A2
GET
get A1
SET A1 =SUM(A1)
SHOW A1
```
stdout:
```
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
EMPTY
```

### Example 5: usage error

cmd: `sheet extra`

stdout: (empty)

exit: `2`

## Not required

- Multiplication, division, parentheses other than `SUM(...)`, or functions
  other than `SUM`.
- Text values, persistence, or printing several cells at once.
- Any particular stderr wording.

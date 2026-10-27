# Task 08: connect4 (Connect Four game server)

## Goal

Write a Connect Four referee driven by a line protocol on stdin and stdout.
Two players, `X` and `O`, take turns dropping a disc into one of 7 columns
of a 6-row board; the disc falls to the lowest free cell. The first player
to get four discs in a row (horizontally, vertically or diagonally) wins;
a full board without a winner is a draw. Moves can be undone. Each command
produces exactly one response line.

## Interface

```
connect4
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. A line ends with `\n` (one trailing `\r`
  is removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `2` usage error.

## The board

Columns are numbered 1 to 7 from left to right, rows 1 to 6 from bottom to
top. At startup the board is empty, no move has been made, and it is `X`'s
turn. The player to move is always `X` after an even number of moves and
`O` after an odd number of moves (counting the moves currently on the
board).

## Commands

The commands are exactly these lines (upper case, single spaces, no other
spaces):

| Command | Response |
|---|---|
| `DROP <c>` | `<c>` is one digit `1`-`7`. See rule 1. |
| `UNDO` | See rule 3. |
| `BOARD` | The board as one line (rule 4). |
| `STATUS` | `TURN X` or `TURN O` while the game is running, `WIN X` or `WIN O` after a win, `DRAW` after a draw. |
| `NEW` | Clear the board and the move history; it is `X`'s turn. Response `OK`. |

Any other line (unknown or lower-case command, `DROP 0`, `DROP 8`,
`DROP 01`, extra spaces or tokens, an empty line) gets `ERR bad command`
and changes nothing.

## Rules

1. **DROP.** If the game is over (won or drawn): `ERR game over`. If column
   c already holds 6 discs: `ERR column full`. Otherwise the player to move
   places a disc in the lowest free row r of column c, and the response is
   `PLAYED <player> <r>`, followed by ` WIN` if this move wins, or by
   ` DRAW` if it does not win and the board is now full (42 discs).
2. **Win.** A move wins if the new disc is part of a line of **at least**
   four discs of the same player that are adjacent horizontally,
   vertically, or along either diagonal. After a win or a draw, the game is
   over until `UNDO` or `NEW`.
3. **UNDO.** If no move is on the board: `ERR nothing to undo`. Otherwise
   remove the most recent disc (moves are undone in reverse order, back to
   the last `NEW` or startup), and respond `UNDONE <c>` with the column it
   was in. If the game was over, it is running again (the removed move was
   the one that ended it). The turn goes back to the player whose disc was
   removed.
4. **BOARD format.** Six strings of 7 characters, for rows 6 down to 1 (top
   row first), joined by `/`. Each character is `X`, `O`, or `.` for an
   empty cell, from column 1 to column 7.
5. **Limits.** At most 100000 commands.

## Examples

Each line shown ends with `\n`. For every example, cmd is `connect4` and
exit is `0`, except where noted.

### Example 1: a horizontal win, undo, and a new game

stdin:
```
DROP 4
DROP 4
DROP 3
DROP 3
DROP 5
DROP 5
STATUS
DROP 2
DROP 1
STATUS
BOARD
UNDO
STATUS
DROP 6
NEW
BOARD
UNDO
```
stdout:
```
PLAYED X 1
PLAYED O 2
PLAYED X 1
PLAYED O 2
PLAYED X 1
PLAYED O 2
TURN X
PLAYED X 1 WIN
ERR game over
WIN X
......./......./......./......./..OOO../.XXXX..
UNDONE 2
TURN X
PLAYED X 1 WIN
OK
......./......./......./......./......./.......
ERR nothing to undo
```

### Example 2: a diagonal win

stdin:
```
DROP 1
DROP 2
DROP 2
DROP 3
DROP 3
DROP 4
DROP 3
DROP 4
DROP 4
DROP 7
DROP 4
BOARD
STATUS
```
stdout:
```
PLAYED X 1
PLAYED O 1
PLAYED X 2
PLAYED O 1
PLAYED X 2
PLAYED O 1
PLAYED X 3
PLAYED O 2
PLAYED X 3
PLAYED O 1
PLAYED X 4 WIN
......./......./...X.../..XX.../.XXO.../XOOO..O
WIN X
```

### Example 3: a full column and malformed commands

stdin (line 13 is `DROP`, two spaces, `2`; line 15 is empty):
```
DROP 1
DROP 1
DROP 1
DROP 1
DROP 1
DROP 1
DROP 1
BOARD
DROP 0
DROP 8
drop 1
DROP 01
DROP  2
UNDO 1

STATUS
```
stdout:
```
PLAYED X 1
PLAYED O 2
PLAYED X 3
PLAYED O 4
PLAYED X 5
PLAYED O 6
ERR column full
O....../X....../O....../X....../O....../X......
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
TURN X
```

### Example 4: usage error

cmd: `connect4 7`

stdout: (empty)

exit: `2`

## Not required

- Board sizes other than 7×6.
- Playing moves for a computer opponent.
- Persistence or multiple concurrent games.
- Any particular stderr wording.

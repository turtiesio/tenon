# Task 07: leaderboard (game score ranking service)

## Goal

Write an in-memory leaderboard service driven by a line protocol on stdin
and stdout. Players gain or lose points, and clients ask for the top
players, a player's rank, or the players ranked around a given player.
Players with equal scores share a rank ("1, 2, 2, 4" ranking). Each command
produces exactly one response line.

## Interface

```
leaderboard
```

- **Arguments.** None. Any argument is a usage error: message on stderr,
  exit `2`, stdin not read, stdout empty.
- **stdin.** One command per line. A line ends with `\n` (one trailing `\r`
  is removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at end of input, `2` usage error.

## Commands

Tokens are separated by exactly one space. There are no leading or trailing
spaces, and command names are upper case.

```
SCORE <player> <points>
RANK <player>
TOP <k>
AROUND <player> <d>
REMOVE <player>
COUNT
```

- `<player>` matches `[a-z][a-z0-9_]{0,15}`.
- `<points>` matches `-?[0-9]{1,6}` (`-0` is zero).
- `<k>` matches `[1-9][0-9]{0,2}` (1 to 999).
- `<d>` matches `[0-9]{1,3}` (0 to 999; leading zeros allowed).

Any line that is not exactly one of these forms (unknown or lower-case
command, wrong token count, extra spaces, a malformed token, an empty line)
gets `ERR bad command` and changes nothing.

## Rules

1. **Players.** A player exists from their first `SCORE` until a `REMOVE`.
   A new player starts at 0 before the points are added. Totals may become
   negative. After `REMOVE`, a later `SCORE` creates the player again from
   0.
2. **Order.** The **leaderboard order** lists all existing players by total
   descending, then by name ascending (byte order).
3. **Rank.** A player's rank is 1 + the number of players with a strictly
   higher total. Players with equal totals have the same rank, and the next
   lower total skips ranks (totals 70, 50, 50, 20 have ranks 1, 2, 2, 4).
4. **Entries.** In `TOP` and `AROUND`, a player is written as
   `<rank>:<player>:<total>`, for example `2:ann:55` or `6:g:-3`.
5. **Responses.**

   | Command | Response |
   |---|---|
   | `SCORE p n` | Add n to p's total (creating p if needed): `TOTAL <new total>`. |
   | `RANK p` | `RANK <rank> <total>`, or `ERR unknown player`. |
   | `TOP k` | `TOP` followed by the first min(k, number of players) players of the leaderboard order as entries, each preceded by one space. Just `TOP` if there are no players. |
   | `AROUND p d` | If p does not exist: `ERR unknown player`. Otherwise let i be p's position in the leaderboard order (0-based). `AROUND` followed by the entries at positions max(0, i − d) to min(last, i + d), in order, each preceded by one space. |
   | `REMOVE p` | Remove p: `OK`, or `ERR unknown player`. |
   | `COUNT` | `COUNT <number of existing players>`. |

6. **Limits.** At most 20000 commands and 1000 existing players at any
   time. Totals stay within ±10^9.

## Examples

Each line shown ends with `\n`. For every example, cmd is `leaderboard` and
exit is `0`, except where noted.

### Example 1: shared ranks

stdin:
```
SCORE ann 50
SCORE bob 70
SCORE cy 50
SCORE dee 20
SCORE ann 5
TOP 3
RANK cy
RANK ann
SCORE ann -5
TOP 10
RANK dee
RANK zed
COUNT
```
stdout:
```
TOTAL 50
TOTAL 70
TOTAL 50
TOTAL 20
TOTAL 55
TOP 1:bob:70 2:ann:55 3:cy:50
RANK 3 50
RANK 2 55
TOTAL 50
TOP 1:bob:70 2:ann:50 2:cy:50 4:dee:20
RANK 4 20
ERR unknown player
COUNT 4
```

### Example 2: AROUND, REMOVE, zero and negative totals

stdin:
```
SCORE a 10
SCORE b 20
SCORE c 30
SCORE d 40
SCORE e 50
AROUND c 1
AROUND e 2
AROUND a 0
REMOVE c
AROUND b 1
REMOVE c
SCORE f 0
SCORE g -3
TOP 9
COUNT
```
stdout:
```
TOTAL 10
TOTAL 20
TOTAL 30
TOTAL 40
TOTAL 50
AROUND 2:d:40 3:c:30 4:b:20
AROUND 1:e:50 2:d:40 3:c:30
AROUND 5:a:10
OK
AROUND 2:d:40 3:b:20 4:a:10
ERR unknown player
TOTAL 0
TOTAL -3
TOP 1:e:50 2:d:40 3:b:20 4:a:10 5:f:0 6:g:-3
COUNT 6
```

### Example 3: malformed commands

stdin (line 10 is `COUNT` followed by a space, and line 11 is empty):
```
TOP 5
score a 1
SCORE A 1
SCORE a 1.5
SCORE a 1234567
SCORE a
TOP 0
TOP 1000
AROUND a
COUNT 

SCORE  a 1
SCORE a +1
RANK a b
SCORE a -0
TOP 1
```
stdout:
```
TOP
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
ERR bad command
TOTAL 0
TOP 1:a:0
```

### Example 4: usage error

cmd: `leaderboard x`

stdout: (empty)

exit: `2`

## Not required

- Persistence.
- Time-based or per-game leaderboards.
- Any particular stderr wording.

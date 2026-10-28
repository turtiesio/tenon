# Task 10: elevator (single-elevator simulation)

## Goal

Write a tick-by-tick simulation of one elevator serving passenger requests
in a building. Each request says when a passenger appears, on which floor,
and where they want to go. In every tick the elevator either stops to let
passengers out and in, moves one floor, or stays idle. It keeps going in its
current direction while there is something to do that way, and otherwise
turns around. The program prints when each passenger boarded and arrived,
and summary counters. The result is fully determined by the rules below.

## Interface

```
elevator FLOORS
```

- **Arguments.** Exactly one argument, FLOORS, matching `[0-9]{1,3}` with a
  value from 2 to 100. The floors are numbered 0 to FLOORS − 1. Anything else
  is a usage error: print a message to stderr, print nothing on stdout, exit
  `2`, and do not read stdin.
- **stdin.** The requests, one per line. Lines are split on `\n`. A final
  line without `\n` is still a line. One trailing `\r` is removed from each
  line. Lines that are empty or contain only spaces are ignored. Every other
  line must be exactly:

  ```
  <time> <from> <to>
  ```

  with single spaces and no leading or trailing spaces, where `<time>`
  matches `[0-9]{1,6}` and `<from>` and `<to>` match `[0-9]{1,3}` (leading
  zeros allowed).
- **Invalid input (exit 1).** If a line breaks this format, a floor is not
  smaller than FLOORS, `<from>` equals `<to>`, or a `<time>` is smaller than
  the `<time>` of the previous request, print a message to stderr, print
  **nothing** on stdout, and exit `1`. The whole input is checked before any
  output is written.
- **stdout.** The report (rule 6). Every line ends with `\n`.
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Rules

1. **Passengers.** Request number i (1-based, counting only non-ignored
   lines, in input order) is passenger i. Passenger i **appears** at tick
   `<time>`, waiting on floor `<from>`, and wants to go to floor `<to>`.
2. **State.** The elevator starts at tick 0 on floor 0 with direction
   *idle*. Its direction is one of *up*, *down* or *idle*. There is no
   capacity limit.
3. **A tick.** Ticks are numbered 0, 1, 2, .... In tick t, with the elevator
   on floor f:
   1. Every passenger whose `<time>` is t appears, waiting on its `<from>`
      floor.
   2. **Stop.** If some passenger on board has `<to>` = f, or some waiting
      passenger is on floor f, the elevator **stops** for this tick: first
      every passenger on board with `<to>` = f gets out (they **arrive** at
      tick t); then **every** passenger waiting on floor f gets in (they
      **board** at tick t), whatever their destination. The elevator does
      not move in this tick, and its direction does not change.
   3. **Move.** Otherwise, the **targets** are the `<to>` floors of all
      passengers on board and the floors of all waiting passengers.
      - If there are no targets, the direction becomes *idle* and the
        elevator stays on floor f.
      - Otherwise choose the direction: if it is *up* and some target is
        above f, keep *up*; if it is *down* and some target is below f, keep
        *down*; if it is *up* (with no target above), change to *down*; if it
        is *down* (with no target below), change to *up*; if it is *idle*,
        head for the **nearest** target floor (smallest distance from f),
        choosing *up* if a nearest target is above f (so a tie goes up), and
        *down* otherwise.
      - Then the elevator moves one floor in that direction. It is on the new
        floor at the start of tick t + 1. This counts as one **move**.

   Waiting passengers who appear in a later tick are not targets yet.
4. **End.** The simulation ends after the tick in which the last passenger
   arrives. With no requests, nothing is simulated.
5. **Counters.**
   - `moves`: the number of ticks in which the elevator moved.
   - `stops`: the number of ticks in which it stopped (rule 3.2).
   - `finish`: the tick in which the last passenger arrived (`0` with no
     requests).
   - `total_wait`: the sum over all passengers of (board tick − `<time>`).
6. **Report.** One line per passenger in passenger order:

   ```
   <i> board=<tick> arrive=<tick>
   ```

   then one last line:

   ```
   moves=<m> stops=<s> finish=<t> total_wait=<w>
   ```
7. **Limits.** At most 10000 requests. Times are at most 999999, and the
   simulation always ends within 2000000 ticks.

## Examples

Each line shown ends with `\n`.

### Example 1: one passenger

cmd: `elevator 5`

stdin:
```
0 0 3
```
stdout:
```
1 board=0 arrive=4
moves=3 stops=2 finish=4 total_wait=0
```
exit: `0`

(Tick 0: stop on floor 0, passenger 1 boards. Ticks 1-3: move to floor 3.
Tick 4: stop, passenger 1 arrives.)

### Example 2: picking up on the way, then turning around

cmd: `elevator 5`

stdin:
```
0 2 0
1 1 4
```
stdout:
```
1 board=3 arrive=11
2 board=1 arrive=6
moves=8 stops=4 finish=11 total_wait=3
```
exit: `0`

Step by step:

| Tick | Floor at start | Action |
|---|---|---|
| 0 | 0 | idle, nearest target 2: up, move to 1 |
| 1 | 1 | passenger 2 appears on floor 1: stop, 2 boards |
| 2 | 1 | targets 4 and 2, direction up: move to 2 |
| 3 | 2 | stop, 1 boards |
| 4, 5 | 2, 3 | targets 4 and 0, direction up: move to 3, then 4 |
| 6 | 4 | stop, 2 arrives |
| 7-10 | 4 ... 1 | no target above: turn down, move to 3, 2, 1, 0 |
| 11 | 0 | stop, 1 arrives |

### Example 3: several passengers in both directions

cmd: `elevator 6`

stdin:
```
0 3 1
0 1 3
2 0 4
5 4 0
```
stdout:
```
1 board=4 arrive=10
2 board=1 arrive=4
3 board=12 arrive=17
4 board=6 arrive=12
moves=12 stops=6 finish=17 total_wait=16
```
exit: `0`

(At tick 4 on floor 3, passenger 2 gets out and then passenger 1 gets in.
At tick 12 on floor 0, passenger 4 gets out and passenger 3 gets in.)

### Example 4: riding the wrong way, idle ticks and a tie

- cmd: `elevator 5` with stdin `0 4 0\n0 2 0\n` gives stdout
  `1 board=5 arrive=10\n2 board=2 arrive=10\nmoves=8 stops=3 finish=10 total_wait=7\n`
  and exit `0`. (Passenger 2 boards on floor 2 while the elevator is going
  up to fetch passenger 1; both arrive together.)
- cmd: `elevator 5` with stdin `0 0 2\n\n10 1 0\r\n10 3 4` (an empty line,
  a `\r`, and no final newline) gives stdout
  `1 board=0 arrive=3\n2 board=17 arrive=19\n3 board=11 arrive=13\nmoves=8 stops=6 finish=19 total_wait=8\n`
  and exit `0`. (The elevator is idle on floor 2 during ticks 4-9. At tick
  10 the targets 1 and 3 are equally near, so it goes up first.)
- cmd: `elevator 2` with empty stdin gives stdout
  `moves=0 stops=0 finish=0 total_wait=0\n` and exit `0`.

### Example 5: errors

Each of these gives stdout (empty):

- cmd: `elevator 2` with stdin `0 0 0\n` gives exit `1` (from = to).
- cmd: `elevator 2` with stdin `0 0 2\n` gives exit `1` (no floor 2).
- cmd: `elevator 2` with stdin `5 0 1\n4 1 0\n` gives exit `1` (time goes
  backwards).
- cmd: `elevator 2` with stdin `0 0  1\n` gives exit `1` (two spaces).
- cmd: `elevator 1` gives exit `2`.
- cmd: `elevator` gives exit `2`.
- cmd: `elevator 101` gives exit `2`.

## Not required

- Capacity limits, door timing, or several elevators.
- Passengers who refuse to board when the elevator goes the wrong way.
- Printing the elevator's position tick by tick.
- Any particular stderr wording.

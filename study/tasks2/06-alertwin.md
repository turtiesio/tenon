# Task 06: alertwin (sliding-window error alerting)

## Goal

Write a program that reads a stream of timestamped service events from
standard input and raises an alert whenever a service has too many errors
within a sliding time window, subject to a per-service cooldown. After the
stream ends, it prints a per-service summary. Timestamps are integers, and
all window arithmetic is exact.

## Interface

```
alertwin [-w WINDOW] [-t THRESHOLD] [-c COOLDOWN]
```

- **Options.** Each option is given as two separate arguments (the option,
  then its value). Options may appear in any order, and if one is repeated,
  the last one wins. Values must match `[0-9]{1,9}` (leading zeros allowed).

| Option | Meaning | Default | Allowed |
|---|---|---|---|
| `-w WINDOW` | window length in seconds | `60` | 1 .. 999999999 |
| `-t THRESHOLD` | errors in the window that trigger an alert | `3` | 1 .. 999999999 |
| `-c COOLDOWN` | minimum seconds between two alerts of one service | `300` | 0 .. 999999999 |

- **Usage errors (exit 2):** an unknown option, any non-option argument, an
  option without a value, or a value that is malformed or out of range.
  Nothing is printed on stdout.
- **stdin.** One event per line. Lines are split on `\n`. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
- **stdout.** Alert lines while reading, then the summary (formats below).
  Every line ends with `\n`.
- **stderr.** Usage messages. Not tested.
- **Exit codes.** `0` on success (bad input lines do not change this), `2` for
  a usage error.

## Input lines

A line that is empty or contains only spaces is ignored and not counted. Any
other line must be three tokens separated by single spaces, with no leading or
trailing spaces:

```
<ts> <service> <level>
```

- `<ts>` matches `[0-9]{1,12}` (seconds, leading zeros allowed);
- `<service>` matches `[a-z][a-z0-9-]{0,31}`;
- `<level>` is exactly `INFO`, `WARN` or `ERROR` (case-sensitive).

A line that breaks this format is **skipped**. A well-formed line whose `ts`
is **smaller** than the `ts` of the last accepted event (of any service) is
also **skipped** (out of order). Equal timestamps are fine. Every other line
is an **accepted** event. Skipped lines have no effect except on the
`skipped` count.

## Rules

1. **Window count.** When an accepted `ERROR` event of service S arrives at
   time `t`, its window count is the number of accepted `ERROR` events of S
   with timestamp `ts` such that `t - WINDOW < ts ≤ t`, including this event.
2. **Alert.** If the window count is at least THRESHOLD, an alert fires,
   unless S is in cooldown. S is in cooldown if S has fired an earlier alert at
   time `a` and `t - a < COOLDOWN`. When an alert fires, print immediately:

   ```
   ALERT <t> <service> <count>
   ```

   `<t>` is printed as a plain decimal integer without leading zeros.
3. **Only `ERROR`** events are counted in windows and can fire alerts. `WARN`
   and `INFO` events only make the service known and count in the summary.
4. **Summary.** After the end of input, print one line per service that has
   at least one accepted event, sorted by service name ascending (byte-wise):

   ```
   <service> errors=<e> warns=<w> alerts=<a> peak=<p>
   ```

   `e` and `w` count accepted `ERROR` and `WARN` events, `a` counts fired
   alerts, and `p` is the largest window count seen at any `ERROR` event of the
   service (0 if it had none). Then print one line `skipped=<s>`.
5. **Limits.** At most 200000 input lines. The program must finish within the
   10-second time limit at that size.

## Examples

Every line shown ends with `\n`.

### Example 1: defaults (window 60, threshold 3, cooldown 300)

cmd: `alertwin`

stdin:
```
100 api ERROR
110 db WARN
130 api ERROR
159 api ERROR
160 api ERROR
200 api ERROR
220 api ERROR
459 api ERROR
460 api ERROR
461 api ERROR
```
stdout:
```
ALERT 159 api 3
ALERT 461 api 3
api errors=9 warns=0 alerts=2 peak=3
db errors=0 warns=1 alerts=0 peak=0
skipped=0
```
exit: `0`

(At 159 the window (99, 159] holds 100, 130 and 159. At 160 and 200 the count
is 3 again, but 160 - 159 and 200 - 159 are below the cooldown. At 220 the
window (160, 220] holds only 200 and 220. At 461 the count is 3 and
461 - 159 = 302 ≥ 300.)

### Example 2: options, no cooldown, out-of-order and malformed lines

cmd: `alertwin -w 10 -t 2 -c 0`

stdin:
```
5 web ERROR
14 web ERROR
15 web ERROR
12 web ERROR
15 auth INFO
20 web error
24 web ERROR
x web ERROR
25 web ERROR
```
stdout:
```
ALERT 14 web 2
ALERT 15 web 2
ALERT 24 web 2
ALERT 25 web 2
auth errors=0 warns=0 alerts=0 peak=0
web errors=5 warns=0 alerts=4 peak=2
skipped=3
```
exit: `0`

(`12` is out of order after `15`. `error` in lowercase and `x` make two
malformed lines. At 25 the window (15, 25] holds 24 and 25, so the event at 15
no longer counts.)

### Example 3: empty input

cmd: `alertwin -t 1`

stdin: (empty)

stdout:
```
skipped=0
```
exit: `0`

### Example 4: usage errors

- cmd: `alertwin -w 0` gives stdout (empty) and exit `2`.
- cmd: `alertwin -t` gives stdout (empty) and exit `2`.
- cmd: `alertwin extra` gives stdout (empty) and exit `2`.
- cmd: `alertwin -x 5` gives stdout (empty) and exit `2`.

## Not required

- Unsorted input beyond skipping out-of-order lines.
- Resolve or recovery notifications.
- Any particular stderr wording.

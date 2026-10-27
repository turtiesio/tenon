# Task 04: timesheet (weekly hours from clock-in/clock-out punches)

## Goal

Write a program that reads time-clock punches for one week and prints a
report with each employee's worked time per day, weekly total, overtime and
number of anomalies. Punches may come in any order. They are paired IN to
OUT within each day; unmatched punches are anomalies and do not count.
Malformed lines are skipped and counted.

## Interface

```
timesheet
```

- **Arguments.** None. Any argument is a usage error: print a message to
  stderr, print nothing on stdout, exit `2`, and do not read stdin.
- **stdin.** Punches, one per line. Lines are split on `\n`. A final line
  without `\n` is still a line. One trailing `\r` is removed from each line.
  Lines that are empty or contain only spaces are ignored.
- **stdout.** The report (rule 5). Every line ends with `\n`.
- **Exit codes.** `0` success (also when lines were skipped), `2` usage
  error.

## Rules

1. **Punch lines.** A punch is exactly four tokens separated by **single**
   spaces, with no leading or trailing spaces:

   ```
   <name> <day> <HH>:<MM> <kind>
   ```

   - `<name>` matches `[a-z]{1,16}`.
   - `<day>` is one of `Mon Tue Wed Thu Fri Sat Sun` (exact case).
   - `<HH>` is two digits `00`-`23`, `<MM>` two digits `00`-`59`.
   - `<kind>` is `IN` or `OUT`.

   Every other non-ignored line is **skipped** and counted (rule 5). A
   skipped line has no other effect.
2. **Ordering.** For each employee and day, the punches are sorted by time.
   Punches with the same time keep their input order (a stable sort).
3. **Pairing.** For each employee and day, scan the sorted punches with a
   state that starts *closed*:
   - `IN` while closed: open a shift at this time.
   - `IN` while open: **anomaly**; the earlier open IN is discarded and a
     new shift is opened at this time.
   - `OUT` while open: the shift ends; its length (OUT time minus IN time, in
     minutes, possibly 0) is added to the day's minutes; the state becomes
     closed.
   - `OUT` while closed: **anomaly**; the punch is ignored.
   - If the state is open after the day's last punch: **anomaly**; the open
     IN is discarded.

   Shifts never span days; each day is paired separately.
4. **Totals.** An employee's weekly `total` is the sum of the day minutes.
   A day's overtime is `max(0, day minutes − 480)`, and the weekly
   `overtime` is the sum of the daily overtime. `anomalies` is the employee's
   anomaly count over the whole week.
5. **Report.** One line per employee who has at least one valid punch, sorted
   by name (byte order):

   ```
   <name>[ <day>=<time>]... total=<time> overtime=<time> anomalies=<n>
   ```

   - The `<day>=<time>` items appear for every day with **more than 0**
     minutes, in the order Mon, Tue, Wed, Thu, Fri, Sat, Sun.
   - A `<time>` of m minutes is written as `m / 60` (decimal, no leading
     zeros, `0` if zero), `:`, and `m % 60` as exactly two digits, for
     example `0:00`, `7:45`, `125:05`.

   After the employee lines, print one last line `skipped=<k>` with the number
   of skipped lines. This line is always printed.
6. **Limits.** At most 100000 lines.

## Examples

Each line shown ends with `\n`. For every example, cmd is `timesheet`.

### Example 1: a normal week

stdin:
```
ann Mon 09:00 IN
ann Mon 17:30 OUT
bob Mon 08:00 IN
bob Mon 12:00 OUT
ann Tue 08:15 IN
bob Mon 13:00 IN
ann Tue 18:00 OUT
bob Mon 16:45 OUT
```
stdout:
```
ann Mon=8:30 Tue=9:45 total=18:15 overtime=2:15 anomalies=0
bob Mon=7:45 total=7:45 overtime=0:00 anomalies=0
skipped=0
```
exit: `0`

(Ann's overtime is 0:30 on Monday plus 1:45 on Tuesday.)

### Example 2: unordered punches and anomalies

stdin:
```
cy Wed 13:00 OUT
cy Wed 08:00 IN
cy Wed 12:00 IN
cy Thu 09:00 IN
cy Thu 09:30 OUT
cy Thu 10:00 OUT
cy Fri 22:00 IN
```
stdout:
```
cy Wed=1:00 Thu=0:30 total=1:30 overtime=0:00 anomalies=3
skipped=0
```
exit: `0`

(Wednesday sorted is 08:00 IN, 12:00 IN, 13:00 OUT: the second IN is an
anomaly and the shift is 12:00-13:00. Thursday's 10:00 OUT is an anomaly.
Friday's IN is never closed, an anomaly, and Friday has 0 minutes so it is
not listed.)

### Example 3: skipped lines and zero-length shifts

stdin (the 7th line contains three spaces; the 8th line has two spaces
after `dee` and, like the 9th, ends with `\r\n`; the last line has no final
newline):
```
dee Sat 10:00 IN
dee Sat 10:00 OUT
Dee Sat 10:00 IN
dee sat 10:00 IN
dee Sat 24:00 OUT
dee Sat 9:00 IN
   
dee  Sun 10:00 IN
dee Sun 10:00 IN
dee Sun 23:59 OUT
```
stdout:
```
dee Sun=13:59 total=13:59 overtime=5:59 anomalies=0
skipped=5
```
exit: `0`

(The Saturday shift is 0 minutes long, so Saturday is not listed. The
skipped lines are `Dee ...`, `... sat ...`, `24:00`, `9:00` and the line with
two spaces; the line of spaces is ignored, not skipped.)

### Example 4: no punches

- stdin empty: stdout `skipped=0\n`, exit `0`.
- stdin `x\n`: stdout `skipped=1\n`, exit `0`.

### Example 5: usage error

cmd: `timesheet week.txt`

stdout: (empty)

exit: `2`

## Not required

- Shifts across midnight, breaks, or rounding of punch times.
- Dates, multiple weeks, or time zones.
- Pay rates or money.
- Any particular stderr wording.

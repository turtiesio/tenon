# Task 06: climate (monthly temperature summary per weather station)

## Goal

Write a program that reads daily temperature readings from weather stations
and prints, for every station and month (or year, with `-y`), the number of
days with a reading and the minimum, maximum and mean temperature. A station
may report the same day more than once; only its last reading for that day
counts. Malformed lines and impossible dates are skipped and counted. All
arithmetic is done exactly in tenths of a degree.

## Interface

```
climate [-y]
```

- **Arguments.** None, or exactly the one argument `-y` (group by year
  instead of by month). Anything else is a usage error: print a message to
  stderr, print **nothing** on stdout, do not read stdin, and exit `2`.
- **stdin.** UTF-8 text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **stdout.** The report (see "Output").
- **Exit codes.** `0` success (also when lines were skipped), `2` usage
  error.

## Rules

1. **Reading lines.** A reading is exactly three fields separated by `;`:
   `<station>;<date>;<temp>`.
   - `<station>`: 1 to 40 characters (code points), none of them `;`, not
     starting or ending with a space. It may contain inner spaces and
     non-ASCII characters. Station names are compared exactly (case
     matters).
   - `<date>`: `YYYY-MM-DD` with exactly 4, 2 and 2 digits, a real calendar
     date with year 0001-9999 (Gregorian leap years: divisible by 4 and not
     by 100, or divisible by 400).
   - `<temp>`: matches `-?[0-9]{1,2}\.[0-9]`, that is, an optional minus
     sign, one or two digits, a dot and exactly one digit (`-0.0` is
     allowed and means zero).
2. **Skipped lines.** An empty line is ignored and not counted. Any other
   line that is not a valid reading is **skipped** and counted.
3. **Duplicates.** If two or more valid readings have the same station and
   the same date, only the **last** one in the input is used. Each earlier
   one that is dropped this way counts as **replaced**.
4. **Groups.** The used readings are grouped by station and by month
   (`YYYY-MM`), or by station and year (`YYYY`) with `-y`.
5. **Statistics** per group, with temperatures as integers in tenths of a
   degree (`-3.5` is -35):
   - `days`: the number of used readings in the group;
   - `min`, `max`: the lowest and highest temperature;
   - `mean`: the sum divided by `days`, rounded to the nearest tenth, with
     an exact half rounded **away from zero** (−22.5 tenths becomes −23,
     36.5 becomes 37).
6. **Number format.** A value of t tenths is printed as: a `-` if t < 0,
   then |t| div 10, a `.`, and |t| mod 10. So -23 is `-2.3`, 5 is `0.5`, and
   zero is always `0.0` (never `-0.0`).

## Output

1. One line per group, sorted by station (comparing the UTF-8 bytes), then
   by period (as text):

   ```
   <station> <period> days=<n> min=<t> max=<t> mean=<t>
   ```
2. Then one last line:

   ```
   readings=<used> skipped=<skipped> replaced=<replaced>
   ```
   where `<used>` is the number of readings used after rule 3.

Every line ends with `\n`. Empty input prints only
`readings=0 skipped=0 replaced=0`.

## Examples

Each line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

In Examples 1 and 2, stdin is (UTF-8; there is one empty line):
```
Oslo;2024-01-30;-3.5
Oslo;2024-01-31;-0.5
Oslo;2024-02-01;1.0
Zürich;2024-02-29;4.2
Oslo;2024-01-30;-4.0
Bergen;2024-02-30;5.0
Bergen;2024-02-28;5.0
Bergen;2024-02-27;6.25
Bergen;2024-02-26;6.0

Oslo;2023-12-31;-10.1
Zürich;2024-02-28;3.1
Zürich;2024-03-01;12
Bergen;2024-02-25;5.0
Nuuk;2024-03-01;-0.1
Nuuk;2024-03-02;-0.0
Nuuk;2024-03-03;0.0
```

### Example 1: by month

cmd: `climate`

stdout:
```
Bergen 2024-02 days=3 min=5.0 max=6.0 mean=5.3
Nuuk 2024-03 days=3 min=-0.1 max=0.0 mean=0.0
Oslo 2023-12 days=1 min=-10.1 max=-10.1 mean=-10.1
Oslo 2024-01 days=2 min=-4.0 max=-0.5 mean=-2.3
Oslo 2024-02 days=1 min=1.0 max=1.0 mean=1.0
Zürich 2024-02 days=2 min=3.1 max=4.2 mean=3.7
readings=12 skipped=3 replaced=1
```
exit: `0`

(`Bergen;2024-02-30` is not a date, `6.25` has two decimals and `12` has
none: 3 skipped. The second `Oslo;2024-01-30` replaces the first, so Oslo's
January is −40 and −5, mean −22.5 tenths, rounded away from zero to −2.3.
Nuuk's mean is −1/3 tenth, which rounds to `0.0`. `Zürich` sorts last
because `ü` is not ASCII.)

### Example 2: by year

cmd: `climate -y` with the same stdin gives stdout:
```
Bergen 2024 days=3 min=5.0 max=6.0 mean=5.3
Nuuk 2024 days=3 min=-0.1 max=0.0 mean=0.0
Oslo 2023 days=1 min=-10.1 max=-10.1 mean=-10.1
Oslo 2024 days=3 min=-4.0 max=1.0 mean=-1.2
Zürich 2024 days=2 min=3.1 max=4.2 mean=3.7
readings=12 skipped=3 replaced=1
```
exit: `0`

### Example 3: edge cases of the line format

cmd: `climate`

stdin (the third line ends with `\r\n`):
```
 Lima;2024-05-01;18.0
Lima;2023-02-29;20.0
Lima;2000-02-29;-0.5
Lima;1900-02-29;20.0
Lima;2024-5-01;20.0
Lima;2024-05-01;+1.0
Lima;2024-05-01;100.0
Lima;2024-05-01;1.0;x
Lima;2000-02-29;0.4
```
stdout:
```
Lima 2000-02 days=1 min=0.4 max=0.4 mean=0.4
readings=1 skipped=7 replaced=1
```
exit: `0`

(Skipped: a leading space, 2023 and 1900 are not leap years, a one-digit
month, a `+` sign, three integer digits, and a fourth field.)

### Example 4: empty input and usage errors

- cmd: `climate` with empty stdin gives stdout
  `readings=0 skipped=0 replaced=0\n` and exit `0`.
- cmd: `climate -m` gives stdout (empty) and exit `2`.
- cmd: `climate -y -y` gives stdout (empty) and exit `2`.

## Not required

- Other temperature formats (no decimal point, two decimals, units).
- Medians or other statistics.
- Any particular stderr wording.

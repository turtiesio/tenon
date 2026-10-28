# Task 05: srtfix (shift and renumber SRT subtitles)

## Goal

Write a program that reads a subtitle file in the SRT format on stdin,
validates it, shifts every cue by a fixed number of milliseconds, drops
cues that end up entirely before time zero, sorts the cues by start time,
renumbers them from 1, and prints the result in a normalized SRT layout.

## Interface

```
srtfix OFFSET
```

- **Arguments.** Exactly one argument, OFFSET, matching `[+-]?[0-9]{1,9}`:
  a number of milliseconds (`+1500`, `1500` and `-250` are valid). Wrong
  argument count or a malformed OFFSET is a usage error: message on stderr,
  exit `2`, stdout empty, stdin not read.
- **stdin.** UTF-8 text. Lines are split on `\n`. If the input ends with
  `\n`, there is no extra empty line after it. A final line without `\n` is
  still a line. One trailing `\r` is removed from each line.
- **stdout.** The normalized subtitles (see "Output").
- **Exit codes.** `0` success, `1` invalid input, `2` usage error.

## Input format

- A **blank** line is a line that is empty or consists only of spaces and
  tabs. Blank lines separate **blocks**: a block is a maximal run of
  non-blank lines. Any number of blank lines may appear before, between and
  after blocks. Input with no blocks is valid and has no cues.
- Each block is one **cue** and must have at least 3 lines:
  1. the **index line**, matching `[0-9]{1,9}` exactly (its value is
     ignored);
  2. the **timing line**, exactly `<start> --> <end>` with single spaces
     around `-->`, where each time is `HH:MM:SS,mmm` matching
     `[0-9]{2}:[0-5][0-9]:[0-5][0-9],[0-9]{3}`. Its value in milliseconds
     is ((HH·60 + MM)·60 + SS)·1000 + mmm. The end must be **greater** than
     the start;
  3. one or more **text lines**, kept exactly as they are (after `\r`
     removal), including leading spaces.
- If any block breaks these rules, the input is **invalid**: print a message
  to stderr, print **nothing** on stdout, and exit `1`.

## Rules

1. **Shift.** Add OFFSET to the start and the end of every cue.
2. **Drop.** A cue whose shifted end is ≤ 0 is removed.
3. **Clamp.** A remaining cue whose shifted start is negative gets start 0.
4. **Sort.** Sort the remaining cues by start time, ascending. Cues with
   equal start times keep their input order. (End times do not matter for
   sorting.)
5. **Renumber.** The cues are numbered 1, 2, 3, ... in sorted order.
6. **Limits.** At most 10000 cues. Shifted times stay below 100 hours in
   tests.

## Output

For each cue in sorted order, print its number, then the timing line in the
same `HH:MM:SS,mmm --> HH:MM:SS,mmm` format (every field zero-padded to its
width), then its text lines, then one empty line. Every line ends with `\n`,
so the output of a non-empty result ends with `\n\n`. With no cues the
output is empty.

## Examples

Each line shown ends with `\n`.

### Example 1: a simple shift

cmd: `srtfix +1500`

stdin:
```
1
00:00:01,000 --> 00:00:03,500
Hello there.

2
00:00:04,000 --> 00:00:05,250
Line one
Line two
```
stdout (it ends with an empty line):
```
1
00:00:02,500 --> 00:00:05,000
Hello there.

2
00:00:05,500 --> 00:00:06,750
Line one
Line two

```
exit: `0`

### Example 2: shift back, drop, clamp, sort

cmd: `srtfix -1000`

stdin (line 4 is empty, line 5 is empty, line 13 is two spaces, and the
last line starts with two spaces):
```
7
00:00:02,000 --> 00:00:04,000
second


3
00:00:00,500 --> 00:00:01,200
first

5
00:00:00,100 --> 00:00:01,000
gone
  
9
00:01:00,000 --> 00:01:02,000
  third, indented
```
stdout (it ends with an empty line):
```
1
00:00:00,000 --> 00:00:00,200
first

2
00:00:01,000 --> 00:00:03,000
second

3
00:00:59,000 --> 00:01:01,000
  third, indented

```
exit: `0`

(`gone` ends at 0 after the shift and is dropped. `first` starts at −500
and is clamped to 0.)

### Example 3: equal start times and CRLF

- cmd: `srtfix 99999` with stdin
  `1\n00:00:05,000 --> 00:00:06,000\nlate\n\n2\n00:00:05,000 --> 00:00:05,001\nsame start\n`
  gives stdout
  `1\n00:01:44,999 --> 00:01:45,999\nlate\n\n2\n00:01:44,999 --> 00:01:45,000\nsame start\n\n`
  and exit `0`.
- cmd: `srtfix 0` with stdin
  `1\r\n00:59:59,999 --> 01:00:00,999\r\nA\r\n\r\n2\r\n00:00:01,000 --> 00:00:02,000\r\nB\r\n`
  gives stdout
  `1\n00:00:01,000 --> 00:00:02,000\nB\n\n2\n00:59:59,999 --> 01:00:00,999\nA\n\n`
  and exit `0`.

### Example 4: invalid input

Each of these, with cmd `srtfix 0`, gives stdout (empty) and exit `1`:

- stdin `1\n00:00:01,000 -> 00:00:02,000\nx\n` (bad arrow)
- stdin `1\n00:00:03,000 --> 00:00:02,000\nx\n` (end before start)
- stdin `1\n00:00:01,000 --> 00:00:02,000\n` (no text line)
- stdin `1\n00:00:61,000 --> 00:00:62,000\nx\n` (seconds out of range)

### Example 5: usage errors

Each of these gives stdout (empty) and exit `2`:

- cmd: `srtfix`
- cmd: `srtfix 1.5`
- cmd: `srtfix ++1`
- cmd: `srtfix 1 2`

## Not required

- Formatting tags (`<i>`), positions after the timing, or a byte order mark.
- Shifted times of 100 hours or more.
- Merging or trimming overlapping cues.
- Any particular stderr wording.

# Task 10: jobsched (worker-pool scheduler simulation)

## Goal

Simulate running a set of jobs with dependencies on a pool of N workers, in
discrete integer time. A job may start once all of its dependencies have
finished and a worker is free. Ready jobs are started by priority, and the
worker is chosen by a fixed rule. The program prints the full event trace and
the makespan, the time when the last job finishes. Every tie is broken by the
rules below, so the output is completely deterministic.

You may use real threads or tasks if you like, but the output must be
**exactly** the simulated trace defined here, and wall-clock time plays no
part. A plain event-driven simulation is fully acceptable.

## Interface

```
jobsched [-w N | --workers N | --workers=N] FILE
```

- **Arguments.**
  - Exactly one `FILE` is required, and `-` means standard input.
  - N is a decimal integer from 1 to 1000, digits only. The default is 1.
  - The option may come before or after `FILE`. If it is repeated, the last
    one wins.
- **stdout.** The trace (format below).
- **stderr.** Error messages. Not tested.
- **Exit codes.**
  - `0`: success.
  - `1`: `FILE` cannot be read, or the job file is invalid (see Validation).
    Nothing is printed to stdout.
  - `2`: usage error: no `FILE`, more than one `FILE`, an unknown option, or a
    missing or invalid N. Nothing is printed.

## Job file format

- UTF-8 text with lines separated by `\n`. A trailing `\r` is removed, and the
  last line may lack `\n`.
- Lines that are empty or whitespace-only, and lines whose first non-whitespace
  character is `#`, are ignored.
- Every other line defines one job as exactly **4 tokens**, separated by runs
  of spaces and/or tabs:

  ```
  <name> <duration> <priority> <deps>
  ```

  | Token | Must match |
  |---|---|
  | name | `[A-Za-z0-9_.-]{1,32}` |
  | duration | integer 1..1000000, `[0-9]+` |
  | priority | integer 0..1000, `[0-9]+` |
  | deps | `-` for no dependencies, or a comma-separated list of names with no spaces and no empty elements. A name repeated in the list counts once. |

## Validation (any failure: exit 1, nothing on stdout)

- a job line without exactly 4 tokens, or with any token that does not match;
- two jobs with the same name;
- a dependency that names no job in the file;
- a dependency cycle, including a job that depends on itself.

## Simulation rules

1. **Workers.** The workers are `w1` … `wN`, and all are free at time 0.
2. **Events.** Time starts at 0. At each event time `t`, do the following in
   order:
   1. **Finish** every job whose finish time is `t`: free its worker and mark
      the job finished.
   2. **Start** jobs. A job is *ready* if it has not started and all of its
      dependencies are finished. While some worker is free and some job is
      ready, start the ready job with the **highest priority**, breaking ties
      by **name** in ascending byte order, on the free worker with the
      **lowest number**. That job finishes at `t + duration`.
   3. Advance `t` to the next pending finish time.
3. **Reuse.** A worker freed at time `t` can start another job at the same
   time `t`.
4. **End.** The simulation ends when every job has finished. The makespan is
   the last finish time, or 0 if there are no jobs.

## Output format

- One line per event, ordered by time.
- Within a single time `t`, all `finish` lines come first, in ascending byte
  order of job name. They are followed by all `start` lines, in the order the
  jobs were started.
- Line formats:

  ```
  <t> finish <name> w<k>
  <t> start <name> w<k>
  ```

- A final line `done <makespan>` follows.
- Fields are separated by single spaces, every line ends with `\n`, and all
  numbers are plain decimal integers. All times stay below 2^53.

## Examples

Each line shown ends with `\n`. Examples 1 and 2 use this `jobs.txt`:

```
# name duration priority deps
fetch     3 0 -
configure 2 5 -
build     4 1 fetch,configure
test      2 0 build
docs      1 0 configure
```

### Example 1: two workers

cmd: `jobsched -w 2 jobs.txt`

stdout:
```
0 start configure w1
0 start fetch w2
2 finish configure w1
2 start docs w1
3 finish docs w1
3 finish fetch w2
3 start build w1
7 finish build w1
7 start test w1
9 finish test w1
done 9
```
exit: `0`

### Example 2: one worker (the default), priorities and name ties

cmd: `jobsched jobs.txt`

stdout:
```
0 start configure w1
2 finish configure w1
2 start docs w1
3 finish docs w1
3 start fetch w1
6 finish fetch w1
6 start build w1
10 finish build w1
10 start test w1
12 finish test w1
done 12
```
exit: `0`

### Example 3: more workers than ready jobs; stdin input

cmd: `jobsched --workers=3 -`

stdin:
```
b 2 0 -
a 2 0 -
c 1 9 a,b
d 5 0 -
e 1 0 d
```
stdout:
```
0 start a w1
0 start b w2
0 start d w3
2 finish a w1
2 finish b w2
2 start c w1
3 finish c w1
5 finish d w3
5 start e w1
6 finish e w1
done 6
```
exit: `0`

### Example 4: a cycle, and an empty file

- `cyc.txt`:

  ```
  a 1 0 b
  b 1 0 a
  ```

  cmd: `jobsched cyc.txt` gives stdout (empty) and exit `1`.
- `empty.txt` is zero bytes. cmd: `jobsched empty.txt` gives stdout
  `done 0` and exit `0`.

### Example 5: usage and validation errors

- cmd: `jobsched -w 0 jobs.txt` gives stdout (empty) and exit `2`.
- cmd: `jobsched -w 2` gives stdout (empty) and exit `2`.
- `bad.txt` contains `x 1 0 nosuchjob`. cmd: `jobsched bad.txt` gives stdout
  (empty) and exit `1`.

## Not required

- Running jobs for real, or using any clock.
- Preemption, or changing priorities at runtime.
- Any particular stderr wording, for example naming the jobs in a cycle.

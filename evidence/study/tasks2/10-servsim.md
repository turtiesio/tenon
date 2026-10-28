# Task 10: servsim (discrete-event simulation of a server pool)

## Goal

Write a discrete-event simulator for a pool of N identical servers sharing
one FIFO waiting queue. The input is a trace of requests (id, arrival time,
service duration). The program prints every start, completion and rejection
event in a fully specified order, then summary statistics. Everything happens
in simulated integer time: the output must be identical on every run.

## Interface

```
servsim [-q CAP] N
```

- **Arguments.** `N` is the number of servers and must match `[0-9]{1,4}`
  with value 1 .. 1000. `-q CAP` (two separate arguments) sets the queue
  capacity: CAP matches `[0-9]{1,7}` (0 is allowed). Without `-q`, the queue
  is unbounded. `-q` may come before or after `N`, and if it is repeated, the
  last one wins. Leading zeros are allowed.
- **Usage errors (exit 2):** a missing or extra positional argument, an
  unknown option, `-q` without a value, or a malformed or out-of-range value.
  Nothing is printed on stdout.
- **stdin.** The request trace, one request per line. Lines are split on
  `\n`. A final line without `\n` is still a line. One trailing `\r` is
  removed from each line. Lines that are empty or contain only spaces are
  ignored. Every other line must be exactly three tokens separated by single
  spaces, with no leading or trailing spaces:

  ```
  <id> <arrival> <duration>
  ```

  - `<id>` matches `[A-Za-z0-9_-]{1,16}` and is unique in the trace;
  - `<arrival>` matches `[0-9]{1,12}`;
  - `<duration>` matches `[0-9]{1,9}` and is at least 1.

  Arrival times must be **non-decreasing** in input order.
- **Invalid trace (exit 1).** If any line breaks these rules (malformed, a
  duplicate id, or an arrival smaller than the previous one), print a message
  to stderr, print **nothing** on stdout, and exit `1`. The whole input is
  validated before any output is written.
- **stdout.** The event log, then the summary (formats below). Every line ends
  with `\n`.
- **Exit codes.** `0` success, `1` invalid trace, `2` usage error.

## Simulation rules

Servers are numbered `1 .. N` and printed as `s1`, `s2`, and so on. A request
that starts at time `t` on a server finishes at `t + duration`, and the server
is busy during that interval.

Process time points in increasing order. At each time point `t`:

1. **Completions first.** Every server whose request finishes at `t`
   completes, in **increasing server number**. For each such server, in that
   order:
   - print `<t> done <id> s<k>`;
   - if the queue is not empty, the server immediately takes the request at
     the head of the queue and starts it at `t`: print
     `<t> start <id> s<k> wait=<w>`, where `w` = `t` minus the request's
     arrival time. Otherwise the server becomes idle.
2. **Then arrivals**, in input order, for every request whose arrival time is
   `t`:
   - if some server is idle, the request starts on the idle server with the
     **lowest number**: print `<t> start <id> s<k> wait=0`;
   - otherwise, if the queue holds fewer than CAP requests (always true when
     unbounded), the request joins the tail of the queue (nothing is printed);
   - otherwise the request is rejected: print `<t> reject <id>`.

A request that arrives at the same time as a completion therefore sees the
server already freed. Times are printed as plain decimal integers.

## Summary

After the last event, print:

```
served=<s> rejected=<r> max_wait=<mw> total_wait=<tw> makespan=<m>
```

- `served`: requests that started (all of them eventually finish);
- `rejected`: rejected requests;
- `max_wait`, `total_wait`: the maximum and the sum of `wait` over served
  requests (0 if none);
- `makespan`: the time of the last `done` event (0 if none).

Then, for every server `k` from 1 to N, one line:

```
s<k> busy=<b> served=<c>
```

where `b` is the sum of the durations of the requests the server ran, and `c`
is their number.

Limits: at most 100000 requests. All times fit in a signed 64-bit integer.

## Examples

Every line shown ends with `\n`. In `cmd`, arguments are separated by spaces.

### Example 1: two servers with queueing

cmd: `servsim 2`

stdin:
```
r1 0 5
r2 1 3
r3 2 4
r4 2 1
r5 6 2
```
stdout:
```
0 start r1 s1 wait=0
1 start r2 s2 wait=0
4 done r2 s2
4 start r3 s2 wait=2
5 done r1 s1
5 start r4 s1 wait=3
6 done r4 s1
6 start r5 s1 wait=0
8 done r5 s1
8 done r3 s2
served=5 rejected=0 max_wait=3 total_wait=5 makespan=8
s1 busy=8 served=3
s2 busy=7 served=2
```
exit: `0`

(At 6, `r4` completes before `r5` arrives, so `r5` finds `s1` idle. At 8 both
servers finish, and `s1` is reported first.)

### Example 2: a bounded queue rejects a request

cmd: `servsim -q 1 1`

stdin:
```
a 0 4
b 1 2
c 2 1
d 4 1
```
stdout:
```
0 start a s1 wait=0
2 reject c
4 done a s1
4 start b s1 wait=3
6 done b s1
6 start d s1 wait=2
7 done d s1
served=3 rejected=1 max_wait=3 total_wait=5 makespan=7
s1 busy=7 served=3
```
exit: `0`

(At 2 the queue already holds `b`. At 4, `s1` takes `b` from the queue
first, so `d` finds the queue empty and joins it.)

### Example 3: an arrival exactly at a completion

cmd: `servsim 1`

stdin:
```
x 0 3
y 3 2
```
stdout:
```
0 start x s1 wait=0
3 done x s1
3 start y s1 wait=0
5 done y s1
served=2 rejected=0 max_wait=0 total_wait=0 makespan=5
s1 busy=5 served=2
```
exit: `0`

### Example 4: empty input

cmd: `servsim 3`

stdin: (empty)

stdout:
```
served=0 rejected=0 max_wait=0 total_wait=0 makespan=0
s1 busy=0 served=0
s2 busy=0 served=0
s3 busy=0 served=0
```
exit: `0`

### Example 5: errors

- cmd: `servsim 0` gives stdout (empty) and exit `2`.
- cmd: `servsim` gives stdout (empty) and exit `2`.
- cmd: `servsim -q x 2` gives stdout (empty) and exit `2`.
- cmd: `servsim 2` with stdin `a 5 1\nb 3 1\n` (arrival goes backwards) gives
  stdout (empty) and exit `1`.
- cmd: `servsim 2` with stdin `a 0 1\na 1 1\n` (duplicate id) gives stdout
  (empty) and exit `1`.
- cmd: `servsim 2` with stdin `a 0 0\n` (zero duration) gives stdout (empty)
  and exit `1`.

## Not required

- Priorities, preemption, server failures, multiple queues.
- Real threads or real time. The simulation must not sleep.
- Any particular stderr wording.

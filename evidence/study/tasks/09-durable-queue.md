# Task 09: dq (durable job queue with atomic-rename snapshots)

## Goal

Write a persistent work-queue service driven by a line protocol on stdin and
stdout. Producers `PUT` jobs. Consumers `GET` them, and each delivery puts the
job **in flight**. Consumers then `ACK` (done) or `NACK` (return it to the
queue). Job state, and the number of times each job was delivered, survive
process kills.

- State is persisted by writing a **complete snapshot to a temporary file and
  atomically renaming it** over the previous snapshot.
- On restart, every job that was in flight goes back to the ready queue
  (at-least-once delivery).

## Interface

```
dq DIR
```

- **Arguments.** Exactly one argument, `DIR`. If there are no arguments or
  more than one, print a message to stderr and exit `2`.
- **Data directory.**
  - If `DIR` does not exist, create it. Only the last path component is
    created.
  - If it cannot be created, or `DIR` exists but is not a directory, print a
    message to stderr and exit `1`.
- **Files.**
  - The snapshot is `DIR/queue.snap`. Its content format is up to you.
  - Temporary files must be created in `DIR` with names starting with
    `queue.snap.tmp`.
  - At startup, **before** loading, delete or ignore every file in `DIR` whose
    name starts with `queue.snap.tmp`. Such files may be left over from a
    crash, may contain arbitrary bytes, and must not affect the state.
  - A missing `queue.snap` means empty state.
- **stdin.** One command per line. A line ends with `\n` (a trailing `\r` is
  removed), and the last line may lack `\n`.
- **stdout.** Exactly **one** response line per input line, terminated with
  `\n`. **Flush stdout after every response.**
- **Exit codes.** `0` at EOF, `1` if `DIR` is unusable, `2` for a usage error.

## Commands

Tokens are separated by exactly one space, and command names are uppercase.

- `<payload>` matches `[!-~]{1,64}` (printable ASCII, no spaces).
- `<id>` matches `[1-9][0-9]{0,15}`.

| Command | Response |
|---|---|
| `PUT <payload>` | `OK <id>`. Adds a new ready job and gives it the next id. |
| `GET` | `JOB <id> <attempt> <payload>` for the ready job with the **smallest id**, which becomes in flight. `EMPTY` if no job is ready. |
| `ACK <id>` | `OK` if job `<id>` is in flight. The job becomes acked: it is finished and gone for good. Otherwise `ERR not in flight`. |
| `NACK <id>` | `OK` if job `<id>` is in flight. The job becomes ready again. Otherwise `ERR not in flight`. |
| `STATS` | `ready=<r> inflight=<f> acked=<a> next=<n>` |

## Rules

1. **Malformed commands.** Any line that does not match one of the forms
   above gets `ERR bad command` and changes nothing. That includes a bad
   payload or id, the wrong token count, lowercase, and an empty line.
2. **Ids.** The first job gets id 1. Each accepted `PUT` gets the next integer.
   Ids are **never reused**, including across restarts. `next` in `STATS` is
   the id the next `PUT` will receive.
3. **Attempts.** A job's delivery count starts at 0. Each `GET` that delivers
   the job increments it, and the `JOB` response shows the new value. Delivery
   counts are persistent: a job delivered once before a crash is delivered
   with attempt `2` after the restart.
4. **ACK/NACK.** These apply only to jobs that are currently in flight. Ids
   that never existed, or whose jobs are ready or already acked, get
   `ERR not in flight`. `acked` in `STATS` is the total number of acked jobs
   ever, and it persists.
5. **Ready order.** `GET` always returns the ready job with the smallest id,
   whether it was never delivered, NACKed or recovered.
6. **Durability.** Before printing the response to a command that changes
   state (`PUT`, a `GET` that delivers a job, `ACK` and `NACK` that return
   `OK`), the new state must be persisted:
   1. write the full state to a new temporary file named `queue.snap.tmp…` in
      `DIR`;
   2. flush or close it;
   3. rename it to `queue.snap`.

   Commands that change nothing (`STATS`, `EMPTY`, errors) need not write.
7. **Recovery.** At startup, load `queue.snap`. Every job recorded as in
   flight becomes ready, keeping its attempt count. All ids, payloads, attempt
   counts, the acked total and `next` are restored exactly.
8. **Guarantee.** If the process is killed at any point, a later run satisfies
   all of the following:
   - every acknowledged `PUT` (an `OK <id>` was printed) exists exactly once,
     unless it was later acked;
   - every acknowledged `ACK` stays acked;
   - attempt counts are at least those last printed;
   - no id is issued twice.
9. **Limits.** At most 10000 commands per run, and at most 10000 jobs in
   total.

## Examples

Each line shown ends with `\n`. In every example the working directory starts
empty, except where noted.

### Example 1: a single run

cmd: `dq q`

stdin:
```
PUT email:1
PUT email:2
GET
GET
ACK 1
ACK 1
NACK 2
GET
STATS
GET
```
stdout:
```
OK 1
OK 2
JOB 1 1 email:1
JOB 2 1 email:2
OK
ERR not in flight
OK
JOB 2 2 email:2
ready=0 inflight=1 acked=1 next=3
EMPTY
```
exit: `0`

### Example 2: killed while a job is in flight

This is a multi-run test with two steps in one working directory.

**Step 1**: cmd `dq q`, killed right after its 3rd output line. Input is sent
one line at a time, so `ACK 1` is never sent.

stdin:
```
PUT a
PUT b
GET
ACK 1
```
stdout before the kill:
```
OK 1
OK 2
JOB 1 1 a
```

**Step 2**: cmd `dq q`.

stdin:
```
STATS
GET
ACK 1
GET
STATS
```
stdout:
```
ready=2 inflight=0 acked=0 next=3
JOB 1 2 a
OK
JOB 2 1 b
ready=0 inflight=1 acked=1 next=3
```
exit: `0`

### Example 3: a leftover temporary file is ignored

Working directory contains `q/queue.snap.tmp.123` with the content
`garbage!!`, and no `q/queue.snap`.

cmd: `dq q`

stdin:
```
STATS
PUT x
```
stdout:
```
ready=0 inflight=0 acked=0 next=1
OK 1
```
exit: `0`

### Example 4: jobs in flight at a normal exit are ready again after a restart, and ids keep growing

This is a multi-run test with two steps.

**Step 1**: cmd `dq q`.

stdin:
```
PUT p1
PUT p2
PUT p3
GET
GET
ACK 2
```
stdout:
```
OK 1
OK 2
OK 3
JOB 1 1 p1
JOB 2 1 p2
OK
```
exit: `0`

**Step 2**: cmd `dq q`.

stdin:
```
PUT p4
GET
GET
GET
GET
NACK 9
put p5
```
stdout:
```
OK 4
JOB 1 2 p1
JOB 3 1 p3
JOB 4 1 p4
EMPTY
ERR not in flight
ERR bad command
```
exit: `0`

### Example 5: usage errors

- cmd: `dq` gives stdout (empty) and exit `2`.
- cmd: `dq q extra` gives stdout (empty) and exit `2`.

## Not required

- Handling a corrupted `queue.snap`. Tests never write or modify it; only
  your program does.
- Surviving power loss (OS-level crashes). Surviving a SIGKILL of the process
  is required. `fsync` is optional.
- Concurrent processes on the same `DIR`.
- Lease timeouts, dead-letter queues and priorities.
- Any particular stderr wording.

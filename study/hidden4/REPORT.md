# Hidden acceptance tests: task set 4

Final reference result: **250/250 cases passed; 0 failed**, across **585 process
runs**. All ten tasks have 25 cases, within the requested 15–25 range.

- `01-hexdump`: 25 cases, 25 passed; silent control fails 25/25.
- `02-uniqx`: 25 cases, 25 passed; silent control fails 23/25.
- `03-icalc`: 25 cases, 25 passed; silent control fails 25/25.
- `04-timesheet`: 25 cases, 25 passed; silent control fails 25/25.
- `05-runoff`: 25 cases, 25 passed; silent control fails 25/25.
- `06-mdtoc`: 25 cases, 25 passed; silent control fails 22/25.
- `07-parking`: 25 cases, 25 passed; silent control fails 24/25.
- `08-pubsub`: 25 cases, 25 passed; silent control fails 24/25.
- `09-shorten`: 25 cases, 25 passed; silent control fails 24/25.
- `10-elevator`: 25 cases, 25 passed; silent control fails 25/25.

From `/Users/hwang/.t3/projects/tenon`, validate everything against the private
references with this exact command:

```sh
python3 -B study/hidden4/run.py all --json study/hidden4/reference-results.json -- python3 -B 'study/hidden4/ref/{task}.py'
```

The command exits 0. Its final line is `250/250 passed; 0 failed`.
The captured output is in `reference-validation.log`; lossless per-run stdout,
stderr, exit codes, timing, and pass/fail details are in `reference-results.json`.
No stderr text is compared.

`run.py` imports the original harness with bytecode writes disabled, changes
only its in-memory ROOT to `study/hidden4`, and calls its original main
function. `study/harness.py` is unchanged.

Fixture expectations are written independently in `build_cases.py`. It never
imports or executes a reference, and never uses reference output. Expected
bytes are literal worked results or closed-form constructions for simple
boundary inputs. The hex-line helper formats already-supplied hex fields,
ASCII and offsets; it does not select or process an input. The employee-line
helper formats already-worked day minutes, totals, overtime and anomalies.
The exhaustive byte alphabet, zero-ballot elimination sequence, repeated
commands, and identical passenger batches have simple closed-form answers.
No fixture helper implements a general election counter, calculator,
persistence service or elevator simulation. The ten private standard-library-only
references in `ref/NN-slug.py` were written from the frozen specs. No submitted
solution was read or scored.

Every numbered worked example is present as `example-N`. Examples with
several invocations use one multi-run case with a separate step per
invocation. Further cases cover each task's rules, applicable empty input,
malformed input, exact formatting, boundaries, usage errors, and every
specified exit code. Related malformed inputs are grouped into independent
runs within a case; a case passes only if every run passes.

Coverage includes:

- Hexdump: all 256 byte values, printable boundaries, widths 1 and 32,
  short-line padding, unaligned offsets, exact chunks, skip at/beyond EOF,
  zero length, maximum skip/length spellings, last repeated valid options,
  options after FILE, stdin/file selection, paths with spaces or dash prefixes,
  unreadable files/directories, usage precedence, and exactly 1 MiB of input.
- Uniqx: adjacency, original first-line representation, ASCII case folding,
  spaces/tabs in field skipping, retained following blanks, character skipping
  after fields, exhausted keys, counts, every selection combination, repeated
  flags/settings, strict usage, CRLF/final-line behavior, exactly one removed
  CR, empty lines, and exactly 1000000 input bytes.
- Icalc: precedence, left associativity, repeated unary minus, all quotient
  and remainder sign combinations, canonical zero, maximal tokens, definitions
  on either side of EXPR, name/value bounds, syntax before evaluation, left
  operand before right, intermediate overflow without cancellation, both
  range endpoints, error reasons, 50-deep parentheses, and a 1000-byte EXPR.
- Timesheet: chronological and stable equal-time sorting, replacement INs,
  unmatched OUTs and final INs, separate days, zero-length shifts, summed daily
  overtime and its threshold, weekly totals above 40 hours without daily
  overtime, all seven days and maximum daily spans, employee name/order,
  strict skipped-line grammar, ignored spaces versus tabs, final-line/CRLF
  handling, and 100000 punches.
- Runoff: immediate and transferred majorities, strict half versus majority,
  listing-order tie breaks, one elimination per round, partial rankings,
  exhaustion and its effect on the majority denominator before the last
  candidate, zero valid ballots, single and twenty candidates, name grammar
  and case distinctions, invalid headers/ballots, comments and spaces,
  final-line/CRLF handling, and 100000 ballots.
- Mdtoc: levels 1–6, indentation relative to the smallest listed level even
  when it occurs later, global slug reservations by unlisted headings,
  natural suffix collisions, fallback slugs, literal inline text, space
  trimming without merging, allowed punctuation, fence prefixes and unclosed
  blocks, non-heading grammar, level option grammar, and 1000000 input bytes.
- Parking: lowest free spot, multiple holes, duplicate versus FULL priority,
  clock checks before plate checks, clock advancement on every semantic
  failure, malformed commands preserving state, query behavior, reentry,
  grace/hour/day/cap boundaries, no fresh grace period for daily remainders,
  maximum time and large revenue, leading zeros, 1000 spots, 100000 commands,
  strict protocol, CRLF/final-line behavior, and lock-step flushing.
- Pubsub: exact, star, hash and star/hash matching including zero-segment
  hash suffixes, eight-segment/maximal-length tokens, one delivery per client
  under overlap, FIFO polling, independent mailboxes, oldest-message drops,
  persistent drop counts across polling/unsubscription, exact string UNSUB,
  resubscription without retention, implicit clients, strict token grammars,
  1000 clients, 100000 commands, and lock-step flushing.
- Shorten: duplicate URLs, hit increments, deletion and non-reused ids,
  canonical and missing codes, base-36 boundaries through `100`, URL length
  and punctuation, exact command syntax, directory/path behavior, normal and
  killed restarts, strict numbered journal recovery, valid-prefix record
  counts, truncation before new appends, 100000 planted records, and 10000
  commands in one run.
- Elevator: simultaneous passengers, several destinations, boarding in the
  opposite direction, arrivals and boardings sharing a stop, consecutive
  stops caused by new appearances, direction preservation and reversal,
  idle nearest-target and upward-tie choices, future requests excluded from
  targets, summed waits, passenger output order, leading zeros, atomic
  validation of late errors, maximum floors/time, and 10000 passengers.

Shorten has **20 multi-run cases** and **8 SIGKILL steps**. Kills follow
acknowledged PUT, GET and DEL, reads/errors, two successive restarts, and a
new append after recovering an invalid tail. Unsent trailing mutations
separate acknowledged state from future input. Restart queries verify links,
URLs, hits, next codes and record counts. Planted journals include torn first
and final records; numbering gaps, duplicates, zero/leading-zero/malformed
sequence numbers; malformed operation/field/URL/code/newline syntax; hits and
deletes of missing or deleted links; and valid-looking records after the
first invalid record. Append-and-restart sequences check that rejected tails
cannot reappear or block future replay. Parking and pubsub each have one
additional lock-step flush case, for **10 kill steps overall**.
Filesystem bytes are not compared by this harness; fixed-format journal
compatibility and restart-visible state are asserted through the specified
program interface.

The silent control prints nothing and exits 0:

```sh
python3 -B study/hidden4/run.py all --json study/hidden4/silent-results.json -- python3 -B study/hidden4/silent.py
```

It passes **8/250** and fails **242/250 (96.8%)**, failing at least 22 cases
in every task. Exit status 1 is expected. Its accidental passes are uniqx
empty input and both selection flags; mdtoc empty input, ordinary text and
all headings filtered; and empty runs of parking, pubsub and shorten.
Details are in `silent-results.json` and `silent-validation.log`.

Rebuild the fixture tree with:

```sh
python3 -B study/hidden4/build_cases.py
```

Audit structure, examples, Python source syntax, standard-library imports,
and input limits with:

```sh
python3 -B study/hidden4/audit.py
```

Final result: `AUDIT PASS: 250 cases; 585 process runs; 10 kill steps`.
The output is captured in `audit-validation.log`. Fixture regeneration is
byte-for-byte reproducible across **2190 fixture files**, including exact
paths and SHA-256 contents; its check is recorded in `rebuild-validation.log`.
The build count log is in `build-validation.log`.

Three ambiguity questions and chosen readings/exclusion boundaries are
recorded in `AMBIGUITIES.md`: superseded invalid option values, empty shorten
DIR, and internal journal I/O failures. Recovery timing and observation
boundaries are also stated. No expectation relies on a disputed reading.

Only files under `study/hidden4/` were created or modified. No commit, push,
or other Git state-changing command was run. No submitted solution or result
contents were read. The only result artifacts inspected were this suite's
own private-reference and silent-control validation outputs.

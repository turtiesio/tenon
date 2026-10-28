# Hidden acceptance tests: task set 6

Final reference result: **250/250 cases passed; 0 failed**, across **490 process
runs**. Every task has 25 cases, within the requested 15–25 range.

- `01-wcx`: 25 cases, 25 passed; silent control fails 25/25.
- `02-b64`: 25 cases, 25 passed; silent control fails 22/25.
- `03-hsize`: 25 cases, 25 passed; silent control fails 24/25.
- `04-shoplist`: 25 cases, 25 passed; silent control fails 23/25.
- `05-orgchart`: 25 cases, 25 passed; silent control fails 23/25.
- `06-climate`: 25 cases, 25 passed; silent control fails 25/25.
- `07-rooms`: 25 cases, 25 passed; silent control fails 24/25.
- `08-locks`: 25 cases, 25 passed; silent control fails 24/25.
- `09-helpdesk`: 25 cases, 25 passed; silent control fails 25/25.
- `10-sand`: 25 cases, 25 passed; silent control fails 25/25.

From `/Users/hwang/.t3/projects/tenon`, validate everything against the private
references with this exact command:

```sh
python3 -B study/hidden6/run.py all --json study/hidden6/reference-results.json -- python3 -B 'study/hidden6/ref/{task}.py'
```

The command exits 0. Its final line is `250/250 passed; 0 failed`.
Captured output is in `reference-validation.log`; lossless per-run stdout,
stderr, exit status, timing, kill metadata and pass/fail details are in
`reference-results.json`. Stderr text is never compared.

`run.py` imports the original harness with bytecode writes disabled, changes
only its in-memory ROOT to `study/hidden6`, and calls its original main
function. `study/harness.py` is unchanged. The layout is
`NN-slug/cases/<case-name>/`, with `steps` and step directories for multi-run
cases, and private launchable programs in `ref/NN-slug.py`.

Fixture expectations are written independently in `build_cases.py`. The
builder never reads, imports or executes a reference or submitted program,
and never uses reference output. Expected bytes are literal worked answers
or closed-form constructions for deliberately simple boundary inputs.
`lines` only adds LF delimiters to supplied text. Service helpers serialize
supplied command/response lists; they do not model service state. Shoplist's
helper writes supplied recipe/plan/answer strings; it performs no scaling or
aggregation. Limit cases use repeated identical data, simple chains/stars,
explicit unit values, consecutive one-minute bookings, or uniform source
columns with closed-form totals. There is no general task solver in the
fixture builder. Its only imports are pathlib and shutil.

The ten private references were independently implemented from the frozen
specs using only Python's standard library. `ref/common.py` shares only
I/O, exact regex matching, LF/CR handling and error reporting. No submitted
solution was read or scored.

All **44 numbered worked examples** appear as `example-N`. Examples with
several invocations are multi-run cases, with one step per invocation.
Alternative malformed files are supplied under distinct fixture paths so
that each invocation runs independently. A multi-run case passes only when
every step passes. The suite contains **66 multi-run cases** in total.
Additional cases cover exact output, each rule, applicable empty input,
malformed input, boundaries/limits, usage errors and every specified exit code.

Coverage includes:

- Wcx: default/selected/repeated/mixed options, fixed column order, newline
  byte counts, unterminated lines, all six ASCII whitespace characters,
  Unicode spaces remaining part of words, code points versus bytes,
  combining/astral characters, binary input without `-m`, CR as an ordinary
  byte, repeated files, file-order labels and spaces, total-dependent width,
  missing files/directories and continuation, zero totals, empty files and
  stdin, ignored stdin with file operands, strict options and usage atomicity.
- B64: all padding lengths, binary high bytes and alphabet endpoints,
  widths 0/1/2/3/4/16/76/9999, exact and short final lines, splitting padding
  across wrapped lines, leading-zero/repeated widths, decode ignoring a valid
  width, CR/LF removal anywhere, empty streams, strict alphabet/padding/length
  and zero unused bits, rejection after valid groups without partial stdout,
  argument errors, and 1000000-byte encode and decode inputs.
- Hsize: all five binary and decimal units, small integers without decimals,
  precision 0/1/2, half-up thresholds, promotion thresholds and every binary
  promotion level, fixed fractional zeros, maximum size and no unit above
  PiB/PB, leading zeros, options applying globally with mixed operands,
  repeated options, ignored stdin with operands, empty input, CRLF/final
  lines, bad lines continuing with `?`, exact grammars and 10000 stdin lines.
- Shoplist: counts/mass/volume, base-unit conversion before ceiling, separate
  rounding per plan line, repeated plan entries, merged compatible units,
  999/1000/1001 thresholds and fractional trailing-zero removal, ingredient
  ordering and name boundaries, empty recipes/files/plans, ignored comments
  and space-only lines, planned kind conflicts versus ignored unplanned
  conflicts, duplicate headers/ingredients, malformed headers/quantities/
  units/spacing/plans, unknown recipes and atomic errors, missing files and
  directories, CRLF/final lines, maximum quantity/servings, 1000 plan lines
  and 1000 recipe-file lines.
- Orgchart: forward managers, multiple roots, name/id sibling and root
  ordering, UTF-8 byte order, depth-first layout and subtree depth reset,
  report counts and salary aggregation above one employee's bound, comma
  grouping, zero/leading-zero/max salaries, preserved inner name whitespace,
  CRLF/final lines, header-only/blank employee lines, unknown selections,
  malformed records/ids/managers/names/salaries/headers, self and longer
  cycles including outside a selected subtree, duplicate ids, late atomic
  failure, 500 levels and 10000 employees.
- Climate: month/year groups, sorted stations and periods, exact case-sensitive
  names and UTF-8 order, 40-code-point names and inner spaces, repeated valid
  readings and last-wins values, invalid duplicates not replacing readings,
  min/max/mean, positive and negative halves away from zero, rounding near
  zero and canonical zero, temperature endpoints, Gregorian century leap
  rules and years 0001/9999, impossible/malformed dates, malformed station/
  temperature/field syntax, empty lines versus skipped lines, CRLF/final
  lines and one-CR removal, usage errors and 10000 repeated readings.
- Rooms: half-open adjacency, all-day and minute intervals, start-sorted
  schedules independent of ids, earliest-start conflict selection across
  several overlaps, syntax/time/room/conflict error priority, failed commands
  using no id, cancellation without id reuse, FIND's time/capacity/name
  priorities and non-mutation, exact workday boundaries, one-minute gaps,
  skipping several intervals, duration beyond the workday, name/number/id/
  time grammar, empty streams and lines, CRLF/final lines, 100 rooms and
  9899 simultaneous bookings in 10000 commands, and lock-step flushing.
- Locks: simultaneous shared holders, exclusive compatibility, no queue
  overtaking, FIFO shared batches stopping at an exclusive request, duplicate
  held/waiting errors and unsupported upgrade rejection, waiting clients
  unable to UNLOCK, cancellation of front/middle queued requests, pumping
  after cancellation without a release, DROP cancelling before releasing,
  resource-order grants and FIFO grant order, HELD excluding waits, sorted
  holder/resource lists, independent resources, release/drop/reacquisition,
  empty state/streams, exact command grammar, token bounds, CRLF/final lines,
  1000 clients, 1000 resources, 10000 commands and lock-step flushing.
- Helpdesk: sequential/numerically ordered tickets, assignment replacement
  and UNCHANGED, close/reopen preserving agents, closed tickets absent from
  queues, unassigned queues, title punctuation/inner spaces/length endpoints,
  exact token/id/spacing grammar, error priority and non-mutation, CRLF
  mutations and final lines followed by replay, independent/literal/spaced
  directories, normal and killed restarts, fixed-format planted journals,
  syntax and semantic journal rejection, torn OPEN/ASSIGN/CLOSE/REOPEN,
  truncation before later appends, invalid complete prefixes followed by
  valid-looking or torn tails, directory/journal errors, 10000 commands,
  100000 journal records/tickets and next-number recovery to T100000.
- Sand: zero ticks and leading-zero tick spelling, stable ticks counted even
  at the requested limit, straight/left/right priority, edge fallbacks,
  bottom-up vacated cells, left-to-right contention, bottom-row loss,
  grains moving only one row per tick, source emission after movement,
  multiple sources, blocked and bottom-row sources, sources acting as rock,
  piles settling and sustained flow, empty/rock/source-only grids, CRLF/final
  lines, invalid characters/empty/ragged/oversized rows, strict tick grammar,
  30×30 cells and 9999 ticks with exact grain/loss totals.

Helpdesk has **19 multi-run cases** and **7 SIGKILL steps**. Kills follow
OPEN, ASSIGN, CLOSE, REOPEN, reassignment, UNCHANGED, errors, SHOW and QUEUE.
One case has two successive kills; another kills after appending to a journal
that had a torn ASSIGN. Every killed helpdesk step has a trailing mutation
that the harness never sends. Restarts check titles, assignments, queues,
open/closed states, missing unsent tickets and next ids. Planted invalid
journals include skipped/repeated ticket numbers, missing-ticket mutations,
repeated assignments/closes, assigning closed tickets, reopening open tickets,
read-only commands masquerading as records, blank lines, malformed titles/
names/spacing and CRLF records. Complete invalid prefixes are checked twice
without intervening writes. Valid torn suffixes are followed by new appends
and further replay.

Rooms and Locks each add one lock-step flushing case, for **9 SIGKILL steps
overall**. Final journal bytes are not directly compared by the harness;
compatibility and recovery are observed through the specified interface.
`AMBIGUITIES.md` documents this boundary and the other chosen readings.

The silent control prints nothing and exits 0:

```sh
python3 -B study/hidden6/run.py all --json study/hidden6/silent-results.json -- python3 -B study/hidden6/silent.py
```

It passes **10/250** and fails **240/250 (96.0%)**, failing at least 22 cases
in every task. Exit status 1 is expected. Accidental passes are B64's empty
encode, empty decode and line-break-only decode; Hsize's empty stdin;
Shoplist's empty files and planned empty recipe; Orgchart's header-only and
blank-employee-line inputs; and the empty streams for Rooms and Locks.
Details are in `silent-results.json` and `silent-validation.log`.

Rebuild fixtures with:

```sh
python3 -B study/hidden6/build_cases.py
```

Audit structure, example names, exit-code coverage, input ceilings,
lock-step manifests, Python syntax/standard-library imports and validation
artifacts with:

```sh
python3 -B study/hidden6/audit.py
```

Final audit result:
`AUDIT PASS: 250 cases; 490 process runs; 44 numbered examples; 66 multi-run cases; 9 kill steps; 1981 fixture files`.
Output is captured in `audit-validation.log`. Regeneration is byte-for-byte
reproducible across **1981 fixture files**, including exact paths and SHA-256
contents; `rebuild-validation.log` records the check and
`fixture-manifest.sha256` contains all fixture hashes. Build counts are in
`build-validation.log`.

Ambiguities and chosen readings/exclusions are in `AMBIGUITIES.md`: repeated
options with an invalid earlier setting, empty DIR, complete invalid journals
with torn suffixes, journal versus command CR handling, tree domain limits,
scaling/validation scope and observational limits. Successful computations
remain within the frozen limits; explicitly defined malformed/oversized
inputs exercise their specified error rules. No excluded feature or stderr
wording is scored.

Only deliverable files under `study/hidden6/` were created or modified. No
commit, push or other Git state-changing command was run. No solution/result
directory or `/tmp/tenon-study*` was read. The only result artifacts inspected
were this suite's private-reference and silent-control validation outputs.

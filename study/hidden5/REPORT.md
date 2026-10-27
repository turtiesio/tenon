# Hidden acceptance tests: task set 5

Final reference result: **250/250 cases passed; 0 failed**, across **499 process
runs**. All ten tasks have 25 cases, within the requested 15–25 range.

- `01-seqx`: 25 cases, 25 passed; silent control fails 24/25.
- `02-trx`: 25 cases, 25 passed; silent control fails 24/25.
- `03-colalign`: 25 cases, 25 passed; silent control fails 24/25.
- `04-splitbill`: 25 cases, 25 passed; silent control fails 25/25.
- `05-srtfix`: 25 cases, 25 passed; silent control fails 20/25.
- `06-libfines`: 25 cases, 25 passed; silent control fails 25/25.
- `07-leaderboard`: 25 cases, 25 passed; silent control fails 24/25.
- `08-connect4`: 25 cases, 25 passed; silent control fails 24/25.
- `09-polls`: 25 cases, 25 passed; silent control fails 25/25.
- `10-robots`: 25 cases, 25 passed; silent control fails 25/25.

From `/Users/hwang/.t3/projects/tenon`, validate everything against the private
references with this exact command:

```sh
python3 -B study/hidden5/run.py all --json study/hidden5/reference-results.json -- python3 -B 'study/hidden5/ref/{task}.py'
```

The command exits 0. Its final line is `250/250 passed; 0 failed`.
Captured output is in `reference-validation.log`; lossless per-run stdout,
stderr, exit status, timing, kill metadata and pass/fail details are in
`reference-results.json`. No stderr text is compared.

`run.py` imports the original harness with bytecode writes disabled, changes
only its in-memory ROOT to `study/hidden5`, and calls its original main
function. `study/harness.py` is unchanged.

Fixture expectations are written independently in `build_cases.py`. It never
reads, imports or executes a reference or submitted program and never uses
reference output. Expected bytes are literal worked results or closed-form
constructions for deliberately simple boundary inputs. `cue` formats supplied
index, start/end strings and text; it performs no shifting, filtering or
sorting. `played` formats explicitly supplied landing rows with alternating
players and a supplied final suffix; it does not inspect columns, model a
board or detect wins. The full-board draw's column sequence, landing rows and
final board are explicit constants, constructed from alternating two-cell
stripes. Simple repeated inputs and zero/identical-score populations have
closed-form answers. No builder helper implements a general task solver.

The ten private references in `ref/NN-slug.py` were independently implemented
from the frozen specs using only Python's standard library. `ref/common.py`
shares only I/O, regex-validation and money-formatting primitives. No submitted
solution was read or scored.

All **44 numbered worked examples** appear as `example-N`. Examples containing
several invocations are multi-run cases, with one step per invocation. Related
malformed-input checks are also grouped into independent runs; a case passes
only if every run passes. Additional cases cover the rules, applicable empty
input, malformed input, exact output, boundaries/limits, usage errors and every
specified exit code.

Coverage includes:

- Seqx: default/explicit steps, equal endpoints, both wrong directions,
  non-divisible endpoints, canonical zero, leading zeros, width including
  signs and crossing zero, width computed after the limit, empty/literal/
  option-looking separators, mixed/repeated options, large signed values,
  ignored stdin, strict number/count grammar and 100000 printed values.
- Trx: both range passes, all supported escapes, literal/escaped/lone dashes,
  single-character ranges, `a-c-e`, reversed ranges and malformed escapes,
  duplicate source characters with last occurrence winning, short and long
  target lists, translation/deletion/squeezing combinations, identical-only
  squeezing, deletion joining runs, newline handling as an ordinary character,
  empty sets/streams, option termination and the transition to literal sets,
  every ASCII byte in stdin, and a 1000000-byte stream. Explicitly excluded
  combined options are not tested.
- Colalign: whitespace versus explicit separators, empty fields and lines,
  globally computed widths on ragged rows, left/right last-field padding,
  literal spaces, Unicode code-point widths and separators, empty and
  option-looking output separators, repeated settings, duplicate/outside
  column numbers, CRLF and exactly one removed CR, strict argument/list
  grammar, 10000 lines and 100 fields per line.
- Splitbill: payer included/excluded from participants, input-order remainder
  allocation including zero shares, transfer direction, zero balances,
  largest debtor/creditor selection and reselection, both tie-breaks,
  deterministic name ordering, comments/spaces/tabs, leading-zero amounts,
  CRLF/final lines, maximum amount and sums above one record's amount bound,
  duplicate participants, self-transfers, malformed records/names/amounts,
  atomic rejection after valid records, 50 participants, 1000 people and
  10000 lines.
- Srtfix: positive/negative/zero offsets, ignored indices, multiline and
  indented Unicode text, blank block separators, end exactly zero versus
  one millisecond remaining, clamping, stable ordering for original/clamped
  ties, overlapping cues, minute/hour carries and the sub-100-hour bound,
  CRLF/final lines and one-CR removal, malformed indices/times/arrows/spacing,
  equal/reversed times, absent or blank text, atomic validation of a late
  invalid block, offset grammar/bounds, empty input and 10000 cues.
- Libfines: matched versus skipped loans, members with on-time loans,
  late-count independence from zero rates/caps, cap thresholds, returned
  versus unreturned days, returns after TODAY, descending fine/name sorting,
  late-loan file order, case-sensitive ids, preserved title spaces/UTF-8,
  leading-zero numbers, CRLF/final lines, maximum day/rate/cap values,
  large aggregate fines, invalid fields/duplicates/day ordering (including
  malformed unknown-book loans), unreadable/missing files, usage before file
  access, ignored stdin, 10000 books and 100000 loans.
- Leaderboard: additions/losses/negative and zero totals, shared competition
  ranks and gaps, name tie-breaking, TOP cutting through a tie, AROUND by
  position rather than rank, clipping and d=0, removals and recreation from
  zero, rank recomputation, strict command/token/space grammar, CRLF/final
  lines, zero normalization, unknown players, ±1000000000 totals, 1000
  existing players, TOP 999/AROUND 999, 20000 commands and lock-step flushing.
- Connect4: horizontal, vertical and both diagonal directions, wins for
  both players, a five-disc bridge, gravity/board orientation, turn parity,
  full-column failures without turn changes, game-over error priority,
  undoing in reverse order and after a win/draw, replaying an undone move,
  NEW clearing history and wins, malformed commands without state changes,
  CRLF/final lines, a full-board draw and redrawing after undo, 100000
  commands and lock-step flushing.
- Polls: option order, 2–9 options, token length/alphabet boundaries,
  independent polls/voters, changed and unchanged votes, errors in the
  specified order, closed polls remaining readable, exact command grammar,
  CRLF/final lines, normal and killed restarts, fixed-format planted journals,
  complete invalid records (syntax and semantic replay errors), torn first/
  vote/close records, invalid prefixes followed by valid/torn tails,
  truncation before subsequent appends, directory paths/errors and an
  unusable journal, 10000 commands, 1000 polls and 100000 planted records.
- Robots: all directions, waits and empty/missing programs, repeated programs
  of different lengths, blocked instructions advancing the program counter,
  walls/edges/occupied targets, alphabetic order independent of grid/program
  order, moving into a cell freed earlier in a tick, a later robot vacating
  too late, coin contention and one-time collection, no robots, zero ticks,
  no program separator versus an empty program section, final-line/CRLF
  handling, malformed grid/programs and atomic validation, 100-character
  programs, 50×50 grids, 99999 ticks and all 26 robots.

Polls has **17 multi-run cases** and **6 SIGKILL steps**. Kills follow
acknowledged CREATE, first VOTEs, CHANGED, CLOSE, UNCHANGED, an error and a
RESULT; one case has two successive kills. Another kills after an append
following recovery of a torn CLOSE. Every killed poll run has a trailing
mutation that the harness never sends. Restarts check counts, option order,
open/closed state and absence of unsent polls/votes. Planted journals include
valid changed votes, closed polls, invalid repeated creates/closes, votes on
missing/closed polls, unknown options, unchanged votes, RESULT records,
blank records, malformed names/spacing/CRLF and invalid complete prefixes
followed by later valid-looking or torn data.

Leaderboard and Connect4 each add one lock-step flushing case, for **8 kill
steps overall**. Filesystem bytes are not compared by the unchanged harness;
fixed journal compatibility and restart-visible state are asserted through
the specified interface. `AMBIGUITIES.md` records the observation boundary.

The silent control prints nothing and exits 0:

```sh
python3 -B study/hidden5/run.py all --json study/hidden5/silent-results.json -- python3 -B study/hidden5/silent.py
```

It passes **10/250** and fails **240/250 (96.0%)**, failing at least 20 cases
in every task. Exit status 1 is expected. Accidental passes are Seqx's
wrong-direction negative-step case; empty streams for Trx, Colalign,
Leaderboard and Connect4; and Srtfix's empty input, blank-only input,
exact-zero-end drop, all-before-zero drop and maximum-offset empty input.
Details are in `silent-results.json` and `silent-validation.log`.

Rebuild fixtures with:

```sh
python3 -B study/hidden5/build_cases.py
```

Audit structure, example names, exit-code coverage, Python syntax and
standard-library imports, input limits and the draw's independent board
invariant with:

```sh
python3 -B study/hidden5/audit.py
```

Final audit result:
`AUDIT PASS: 250 cases; 499 process runs; 8 kill steps; 1945 fixture files`.
Output is captured in `audit-validation.log`. Fixture regeneration is
byte-for-byte reproducible across **1945 fixture files**, including exact
paths and SHA-256 contents. The check is recorded in `rebuild-validation.log`;
`fixture-manifest.sha256` lists all fixture hashes. Build counts are in
`build-validation.log`.

Ambiguities and chosen readings/exclusion boundaries are in `AMBIGUITIES.md`:
superseded invalid option values, edge-dash range interpretations, validation
of unmatched loans, empty DIR/journal failures, and invalid-prefix/torn-tail
recovery. The suite follows explicit validation requirements and excludes
combinations whose resolution is not stated. Every successful computation
and all fixture sizes stay within the frozen limits. Stderr is never scored.

Only deliverable files under `study/hidden5/` were created or modified. No
commit, push or other Git state-changing command was run. No solution/result
directory or `/tmp/tenon-study*` was read. The only result artifacts inspected
were this suite's private-reference and silent-control validation outputs.

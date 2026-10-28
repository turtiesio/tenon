# Hidden acceptance tests: task set 3

Final result: **250/250 cases passed; 0 failed**, across **607 process runs**.
All ten tasks have 25 cases, within the requested 15–25 range.

- `01-wrap`: 25 cases, 25 passed; silent control fails 23/25.
- `02-radix`: 25 cases, 25 passed; silent control fails 25/25.
- `03-globgrep`: 25 cases, 25 passed; silent control fails 25/25.
- `04-csvjoin`: 25 cases, 25 passed; silent control fails 25/25.
- `05-standings`: 25 cases, 25 passed; silent control fails 23/25.
- `06-buildorder`: 25 cases, 25 passed; silent control fails 25/25.
- `07-linebuf`: 25 cases, 25 passed; silent control fails 24/25.
- `08-sheet`: 25 cases, 25 passed; silent control fails 24/25.
- `09-todo`: 25 cases, 25 passed; silent control fails 24/25.
- `10-cachesim`: 25 cases, 25 passed; silent control fails 25/25.

From the repository root, validate everything against the private
references with this exact command:

```sh
python3 -B study/hidden3/run.py all --json study/hidden3/reference-results.json -- python3 -B 'study/hidden3/ref/{task}.py'
```

The command exits 0. Its final line is `250/250 passed; 0 failed`.
The captured output is in `reference-validation.log`; lossless per-run stdout,
stderr, exit codes, timing, and pass/fail details are in `reference-results.json`.
No stderr text is compared.

`run.py` imports the original harness with bytecode writes disabled, changes
only its in-memory ROOT to `study/hidden3`, and calls its original main
function. `study/harness.py` is unchanged.

Fixture expectations are written independently in `build_cases.py`. It never
imports or executes a reference, and never uses reference output. Expected
bytes are literal worked results or closed-form constructions for simple
boundary inputs. For standings, a formatting helper renders explicitly
supplied ranks/statistics; for cachesim, a helper renders explicitly supplied
hit labels and counters. Neither helper solves the corresponding task.
The ten private standard-library-only references in `ref/NN-slug.py` were
written from the frozen specs. No submitted solution was read or scored.

Every numbered worked example is present as `example-N`. Examples with
several invocations use one multi-run case with a separate step per
invocation. Further cases cover each task's rules, applicable empty input,
malformed input, exact formatting, boundaries, usage errors, and every
specified exit code. Related malformed inputs are grouped into independent
runs within a case; a case passes only if every run passes.

Coverage includes:

- Wrap: greedy breaks, paragraph normalization, first-line indent, overlong
  words, justification remainder placement, last-line behavior, atomic input
  rejection, width 1/1000, and exactly 1000000 input bytes.
- Radix: input/output bases 2–36, signs and negative zero, case, final option
  values, option-looking values, the signed-magnitude range endpoints,
  padding/grouping order, width/group 64, mixed valid/invalid values, and
  usage-error precedence.
- Globgrep: whole-line matching, escapes, special class characters, ranges,
  negation, ASCII case folding, inversion/count combinations, empty patterns
  and lines, CRLF/final-line behavior, invalid patterns, 40-byte patterns,
  and exactly 100000 input bytes.
- Csvjoin: strict quotes and quote termination, embedded CR/LF/commas/quotes,
  conditional output quoting, header validation/clashes, exact keys, duplicate
  key cross-products and order, left joins, key placement, empty records,
  complete-file validation, 10000 records, and a 1000000-byte file.
- Standings: all tie-breakers including W, shared competition positions, byte
  name order, form truncation, unusual points, valid name punctuation,
  strict line grammar, wide fields, 99 teams, and 10000 results.
- Buildorder: dynamic smallest-ready ordering, unions and duplicate edges,
  plain dependencies, multi-target closure, longest-path levels, self and
  disjoint cycles, downstream blocked items, unselected malformed input,
  64-byte names, a 10000-item chain, and a 10000-item wide level.
- Linebuf: exact prefixes and text spacing, numbering boundaries, insertion
  and range deletion, reversible edits, same-text replacement as a change,
  redo invalidation, errors/reads preserving history, substring search,
  1000-byte text, 10000 buffer lines, 30000 undo/redo/edit operations, and
  100000 commands.
- Sheet: literal/content spelling, formula grammar, dynamic dependencies,
  reversed/overlapping SUM rectangles, direct/transitive/range cycles,
  rejected SET preserving contents, inclusive ±10^12 overflow boundaries,
  permitted large intermediate sums, overflow propagation/recovery, all
  2574 cells, a deep chain, a full-sheet range, 200-byte commands, and
  20000 commands.
- Todo: ordering, exact text, leading-zero command ids, error preservation,
  normal restarts, ids after purge, strict snapshot validation, temporary
  file precedence/removal, 200-byte text, 10000 planted items, nine-digit
  persisted-counter boundaries, and 10000 commands in one run.
- Cachesim: L1/L2 LRU updates, L1 hits leaving L2 alone, non-inclusion,
  write allocation, dirty write hits, both write-back paths and their order,
  lookup counters excluding write-backs, no final flush, address echo,
  non-power-of-two sets, block/sets/ways limits, 32-bit addresses, complete
  trace validation, and 200000 accesses.

Todo has **19 multi-run cases** and **7 SIGKILL steps**. Kills follow
acknowledged ADD, DONE, PURGE, reads/errors, and two successive restarts;
unsent trailing mutations distinguish acknowledged state from future input.
Restart queries verify exact visible item ids, text, priorities, statuses,
ordering, counts and next id. Invalid snapshots cover headers, field grammar,
ASCII, final newline, duplicate/descending ids and ids not below next. An
invalid database is opened twice to check that startup does not repair or
remove it. Temporary files are deleted before invalid database loading, and
the deletion is observed by using the old temporary path as a new DIR.
The linebuf and sheet suites each have one further lock-step flush case,
for **9 kill steps overall**. Filesystem bytes are not compared by this
harness; strict snapshot loading and observable restart state are asserted
through the specified program interface.

The glob performance case uses a **39-byte pattern with 19 separated stars**,
`*a` repeated 19 times followed by `b`. One input line is 2000 `a` characters
and fails only at the final literal; another has a final `b` and matches.
The iterative private reference completes the case in about **0.02 seconds**.
The intentionally exponential `naive-glob.py` control fails with the original
harness's **10-second timeout**, rather than a recursion error. Reproduce:

```sh
python3 -B study/hidden3/check_backtracking.py
```

Its expected-timeout result is in `backtracking-validation.log` and
`backtracking-results.json`. This control supports only the star/literal
subset needed for that performance test; it is not a reference.

The silent control prints nothing and exits 0:

```sh
python3 -B study/hidden3/run.py all --json study/hidden3/wrong-results.json -- python3 -B study/hidden3/wrong.py
```

It passes **7/250** and fails **243/250 (97.2%)**, failing at least 23 cases
in every task. Exit status 1 is expected. The seven accidental passes are
empty-input/output cases. Details are in `wrong-results.json` and
`wrong-validation.log`.

Rebuild the fixture tree with:

```sh
python3 -B study/hidden3/build_cases.py
```

The structure, examples, source syntax, and input-limit audit is reproducible:

```sh
python3 -B study/hidden3/audit.py
```

Final result: `AUDIT PASS: 250 cases; 607 process runs; 9 kill steps`.
The output is captured in `audit-validation.log`. Fixture regeneration is
byte-for-byte reproducible; its check is recorded in `rebuild-validation.log`.

Five ambiguity questions and the chosen readings/exclusion boundaries are
recorded in `AMBIGUITIES.md`: superseded invalid option values, empty todo
DIR, todo counter exhaustion, internal storage failures, and adjacent glob
stars. No expectation depends on resolving an excluded question.

Only files under `study/hidden3/` were created or modified. No commit, push,
or other Git state-changing command was run. No submitted solution or result contents
were read.

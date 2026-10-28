# Hidden acceptance tests: task set 7

Final reference result: **250/250 cases passed; 0 failed**, across **511 process
runs**. Every task has 25 cases, within the requested 15–25 range.

- `01-numlines`: 25 cases, 25 passed; silent control fails 24/25.
- `02-checkdigit`: 25 cases, 25 passed; silent control fails 25/25.
- `03-detab`: 25 cases, 25 passed; silent control fails 24/25.
- `04-cidrmerge`: 25 cases, 25 passed; silent control fails 23/25.
- `05-reconcile`: 25 cases, 25 passed; silent control fails 25/25.
- `06-costbasis`: 25 cases, 25 passed; silent control fails 25/25.
- `07-vending`: 25 cases, 25 passed; silent control fails 24/25.
- `08-vfs`: 25 cases, 25 passed; silent control fails 24/25.
- `09-bookmarks`: 25 cases, 25 passed; silent control fails 25/25.
- `10-war`: 25 cases, 25 passed; silent control fails 25/25.

From `/Users/hwang/.t3/projects/tenon`, validate the private references with
this exact command:

```sh
python3 -B evidence/study/hidden7/run.py all --json evidence/study/hidden7/reference-results.json -- python3 -B 'evidence/study/hidden7/ref/{task}.py'
```

It exits 0; the final line is `250/250 passed; 0 failed`. The captured output
is in `reference-validation.log`. `reference-results.json` retains per-step
stdout/stderr as base64, exit status, timing, kill metadata and pass/fail
details. No stderr text is compared.

`run.py` imports the original `evidence/study/harness.py` with bytecode writes
disabled and sets its in-memory ROOT to `hidden7`. It also directs the
harness's temporary working directories into hidden7, keeping scratch runs
inside the authorized tree. It calls the original main function; the shared
harness is unchanged. The layout is `NN-slug/cases/<case-name>/`, with `steps`
and step subdirectories for multi-run cases, and ten private launchable
programs in `ref/NN-slug.py`.

Fixture expectations are independently written in `build_cases.py`. The
builder never reads, imports or executes a reference or submitted program,
and never derives expectations from program output. Answers are literal
worked results or closed-form constructions for deliberately simple limit
inputs. Helpers only serialize supplied arguments, files, commands and
responses, or append LF delimiters. There is no general task solver in the
builder. Its imports are only pathlib and shutil.

The references implement the frozen specs using Python's standard library
only. `ref/common.py` shares regex matching, byte-preserving LF/CR input,
error reporting, flushed output and integer-cent formatting. Task algorithms
and state live in their individual references. No author solution was read
or scored.

All **44 numbered worked examples** appear as `example-N`. Examples with
multiple invocations are multi-run cases. Files for alternative invalid
inputs are planted under distinct paths, so each invocation sees the
specified fixture. Every step must pass for its case to pass. There are
**59 multi-run cases** in total. Further cases cover each rule, applicable
empty input, malformed input, boundaries, limits, usage errors and every
specified exit code.

Coverage includes:

- Numlines: default non-empty numbering, all/none modes, no counter advance
  on blank unnumbered lines, CR and UTF-8 copying, absent final LF and empty
  input, right/left/zero alignment, negative zero and zero/negative steps,
  sign-aware zero padding, numbers wider than the field, width 20 and
  nine-digit arguments, empty and spaced separators, option-looking values,
  repeated/mixed options, files with spaced paths and ignored stdin,
  unreadable files/directories, strict syntax, atomic usage failure and
  100000 numbered lines.
- Checkdigit: Luhn parity and doubling/subtract-nine, minimum and maximum
  digit counts, zero and leading zeros, preserved grouping with hyphenated
  append, ISBN-10 check X and generated X, incorrect checks versus invalid
  syntax, X position/case restrictions, ISBN-13 prefixes 978/979, all
  make/check modes, argument order and duplicates, empty values, whitespace,
  signs, punctuation and non-ASCII digits, ignored stdin and usage errors.
- Detab: default/even/list stops, tabs exactly at stops, one-space fallback
  past the last explicit stop, stop 1 and stop 9999, UTF-8 code points and
  combining marks, CR columns, leading spaces/tabs and post-text tabs,
  preserved missing LF, repeated flags, concatenated files preserving both
  column and indentation state, skipped unreadable files/directories,
  ignored stdin, empty input, exact argument grammar, 10000 expanded
  characters and 100000 input lines.
- Cidrmerge: alignment and strict octet/prefix grammar, /0 and /32, both
  address endpoints, 2^32 range counts, overlapping/nested/duplicate blocks,
  bridging adjacency, gaps, cross-octet adjacency, numeric sorting,
  greedy decompositions that need multiple CIDRs, range output, ignored
  comments/blanks, bad-line continuation and all-bad input, one-CR removal,
  final unterminated input, usage errors and 100000 entries.
- Reconcile: default/zero/365-day windows, exact distance boundaries,
  Gregorian leap days and month/year crossings, year endpoints 1970/2099,
  nearest candidate and line-number ties, bank-file order and one-use ledger
  matches, a greedy choice that differs from maximum matching, output
  category ordering, cents and signed zero, large positive/negative totals,
  text length and preserved internal spaces, blank-line numbering, CRLF,
  final lines, repeated global options, invalid dates/amounts/text/fields,
  late atomic failures on either side, unreadable paths, usage grammar and
  10000-line files.
- Costbasis: FIFO within/across lots, whole-lot removal and partial residual
  cost, rounding below/at/above half, repeated residual rounding, splits of
  every lot and ratios 2/3/10, unknown/sold-out symbols, insufficient sales
  preserving state, buying again after a full sale, zero-cost shares,
  negative and cent gains, byte-sorted holdings and separate lot counts,
  line numbers across comments/blanks, CRLF/final lines, strict command,
  symbol, quantity, price and ratio syntax, usage errors, maximum quantity
  and price, and 10000 purchase lots.
- Vending: every denomination, escrow excluded from tubes, descending
  refund/change lists versus ascending all-tube output, exact sales and
  inserted coins reused as change, bounded greedy coin counts, greedy
  failure despite an alternative combination, full failure rollback,
  retained credit after errors/rejects, selection error priority, reload
  replacing stock, zero stock, independent slots, valid field endpoints,
  strict spacing/numbers/names/slots, CRLF/final lines, usage errors,
  lock-step flushing and 10000 commands accumulating 9989001 tube coins.
- Vfs: root and parent clamping, component-by-component walking, relative
  and absolute dot paths, missing intermediate components and file walks,
  byte-sorted listings and file listings, replacement text and preserved
  spaces, exact text/name bounds, hidden/dot-like names, recursive DU
  accounting, remove busy-before-not-empty priority, empty directory
  removal, source/destination move priorities, existing-directory targets,
  conflicts and cycles, renames and moves of the current directory and its
  ancestor, unchanged state on errors, strict grammar, CRLF/final lines,
  usage errors, lock-step flushing, a 200-character path and 10000 commands.
- Bookmarks: ordinary and compacted restarts, sorted names/tags, deletion
  and re-addition, unchanged operations/errors/reads not consuming numbers,
  sequence continuity across repeated compaction, name/tag/URL endpoints,
  literal `-`, empty stores and independent directories, command CRLF
  normalization, malformed command priority, SIGKILL durability, torn
  records with later appends and replay, valid snapshot-only state,
  snapshot/journal overlap and semantic skipping, stale snapshot.tmp
  contents, malformed snapshots and journal syntax, semantic replay errors,
  sequence gaps/repetition/start/end coverage, invalid complete prefixes
  with torn tails, unusable paths/files, 1000 bookmarks, 10000 commands and
  a 100000-record journal.
- War: pile order and bottom insertion, cyclic positions stopped by MAX,
  default 1000 and maximum 999999 rounds, repeated/mixed options and quiet
  mode, rank ordering, one/double/triple wars, exactly four cards available,
  incomplete initial and later wars, discarded piles and remaining-card
  wins/draws, wins taking priority at the round limit, CRLF/final lines,
  invalid deck contents/count/length, exact argument grammar, and 52-card
  decks. All outputs remain below 1 MB.

Bookmarks has **21 multi-run cases** and **8 SIGKILL steps**. Kills follow
ADD, DEL, TAG, UNTAG, COMPACT, UNCHANGED, errors, GET and FIND. One case has
two successive kills; another kills a new append after discarding a torn
TAG. Each kill step includes a trailing mutation that is never sent. Later
runs check tags, names, missing unsent additions, deleted names and sequence
numbers. Planted overlap models an interrupted COMPACT after snapshot rename
and before journal truncation. Final filesystem bytes are not compared
directly; recovery and fixed-format compatibility are observed through the
specified interface. Vending and Vfs each add one flushing kill, for **10
SIGKILL steps overall**.

The silent control prints nothing and exits 0:

```sh
python3 -B evidence/study/hidden7/run.py all --json evidence/study/hidden7/silent-results.json -- python3 -B evidence/study/hidden7/silent.py
```

It passes **6/250** and fails **244/250 (97.6%)**; exit status 1 is expected.
Its accidental passes are Numlines empty input, Detab empty input,
Cidrmerge empty input and ignored-only lines, Vending empty input and Vfs
empty input. It fails every case for Checkdigit, Reconcile, Costbasis,
Bookmarks and War. Details are in `silent-results.json` and
`silent-validation.log`.

Rebuild fixtures with:

```sh
python3 -B evidence/study/hidden7/build_cases.py
```

Audit fixture structure, argv round trips, all numbered examples, exit-code
coverage, size/count ceilings, kill manifests, Python syntax and
standard-library imports, the fixture manifest and the final validation
artifacts with:

```sh
python3 -B evidence/study/hidden7/audit.py
```

Final audit result:
`AUDIT PASS: 250 cases; 511 process runs; 44 numbered examples; 59 multi-run cases; 10 SIGKILL steps; 2020 fixture files`.
Its output is captured in `audit-validation.log`. Regeneration is
byte-for-byte reproducible across **2020 fixture files**; SHA-256 contents
and exact paths are in `fixture-manifest.sha256`, and the check is recorded
in `rebuild-validation.log`. Build counts are in `build-validation.log`.

`AMBIGUITIES.md` records chosen readings and exclusions, including earlier
invalid repeated options (not adjudicated), empty DIR (not scored), invalid
complete records before a torn suffix, command versus fixed-file CR handling,
skipping overlapped records, literal markers, path walking, input ceilings
and harness observation limits. No excluded feature or stderr wording is
scored.

All authored deliverables are under `evidence/study/hidden7/`. No commit,
push or Git state-changing command was run. No solution directory,
`evidence/study/results*` directory or `/tmp/tenon-study*` path was read.
Only the private-reference and silent-control results created for this
suite were inspected.

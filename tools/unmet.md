Milestone 1 (tenon.md §4), item by item:

- 10 real programs with differential and fuzz testing green: **met**
  (programs/: ledger, jobq, facts, kvhttp, mkplan, csvq, mdhtml, calc, and the
  self-hosted lexer/parser drivers; fuzzing 0 backend disagreements).
- Blind usability study at or below Python on line count and task time: **lines met,
  time not met.** Wave 5 (fresh task set 5, compiler 48f8391, notes off the
  clock; medians): hidden tests 100% in all three languages; lines without
  closer-only lines Tenon 801 / Python 920 / TypeScript 803; minutes 4.4 / 3.0 /
  3.6 (Tenon 1.47x, TypeScript 1.2x Python); compile errors 0 / 0 / 0. Per task:
  writing 16 s vs 13 s, iterating 6 s vs 4 s; a run costs the same now. Tenon time
  over waves: 1.7x, 1.46x, 1.69x, 1.47x Python. The remaining gap is mostly
  writing more tokens (1.36x Python; explicit types and braces) plus an
  outlier author whose own test harness hung. study/results/wave5/.
  Wave 6 (task set 6, compiler 03a418d with format specifiers and collection
  helpers): hidden tests 100% everywhere; lines 910 / 978 / 950; minutes 5.0 /
  3.4 / 3.7, again 1.47x Python, so library additions no longer move the time.
  User decision: the time target stays as written and is reported unmet; no
  design change is made to chase it.
  Earlier waves:
  Wave 2 (task set 2, hidden tests written by Codex, 3 authors per language from
  Claude Opus, Claude Sonnet and Codex in a Latin square, compiler frozen at f6b8396;
  medians): hidden tests ~100% in all three languages; Tenon 1610 lines / 14640
  tokens / 7.1 min vs Python 1240 / 9380 / 4.1 and TypeScript 1791 / 15000 / 4.7.
  Tenon is on par with TypeScript but 1.3x Python's lines and 1.7x its time.
  Main causes measured: braces (one extra line per block), and Python's `re`
  (used in 9 of 10 solutions by every Python author) for input validation.
  All solutions, logs and notes: study/results/wave2/.
  Wave 3 (fresh task set 3, hidden tests by Codex 250/250 against references,
  same Latin square, compiler frozen at 2174ddd): hidden tests 100% / 100% / 99%;
  Tenon 1612 lines / 13610 tokens / 7.0 min vs Python 1296 / 9470 / 4.8 and
  TypeScript 1511 / 14614 / 4.4 (medians). Lines: 1.24x Python, but closing-brace
  lines are 21% of Tenon's lines (0% of Python's); without them Tenon has fewer
  lines than Python (3303 vs 3445 summed over all authors). The line gap is the
  braces the user chose to keep. Time remains 1.46x Python: more tokens per
  solution (1.44x) and compile errors (median 11). Same model, Tenon vs Python
  lines: Opus 1.25x, Sonnet 1.24x, Codex 1.07x. study/results/wave3/.
- Performance within 1.5x of C on the program benchmarks: **met** (worst 1.39x,
  table above). The real-program benchmarks (calc 1.39x, mdhtml 1.24x) were
  rewritten to match the structure of their C and Rust counterparts: one output
  buffer passed down (`mut out: Str`), call parameters in parallel lists. The
  earlier string-returning and Map-environment versions ran at 1.85x and 1.62x;
  docs/reference.md (performance model) explains why.
- check --fast <= 60 s and landing <= 5 min over a week: met so far (~9 s, ~15 s),
  but less than a week of history exists.
- Self-hosted lexer, parser and checker agree with the bootstrap on the full corpus: **met** (tools/selfhost.sh).
- Approvals log and checker exist and refused a real weakening in a test: **met** (tools/approvals_test.sh).

Concurrency: a single-threaded event loop per thread (programs/chat), and isolated workers with channels on every core (tenonc only: docs/reference.md §18, programs/v2/scan; bench/v2 at 3.5-3.6x on 4 workers).

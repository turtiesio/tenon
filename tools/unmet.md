Milestone 1 (tenon.md §4), item by item:

- 10 real programs with differential and fuzz testing green: **met**
  (programs/: ledger, jobq, facts, kvhttp, mkplan, csvq, mdhtml, calc, and the
  self-hosted lexer/parser drivers; fuzzing 0 backend disagreements).
- Blind usability study at or below Python on line count and task time: **not met.**
  Wave 2 (task set 2, hidden tests written by Codex, 3 authors per language from
  Claude Opus, Claude Sonnet and Codex in a Latin square, compiler frozen at f6b8396;
  medians): hidden tests ~100% in all three languages; Tenon 1610 lines / 14640
  tokens / 7.1 min vs Python 1240 / 9380 / 4.1 and TypeScript 1791 / 15000 / 4.7.
  Tenon is on par with TypeScript but 1.3x Python's lines and 1.7x its time.
  Main causes measured: braces (one extra line per block), and Python's `re`
  (used in 9 of 10 solutions by every Python author) for input validation.
  All solutions, logs and notes: study/results/wave2/.
- Performance within 1.5x of C on the program benchmarks: **not met.**
  Microbenchmarks are within target (fib ~1.2x, trees ~0.7x, wordfreq ~1.3x), but
  benchmarks of real programs against hand-written C are not: calc ~1.8x (each
  call builds a Map environment, two mallocs, where C uses a stack array) and
  mdhtml ~1.9x after a size-class allocator (from 2.7x / 2.4x). The rest is
  reference-count traffic and per-call map environments; next: eliding retains
  of values that are only read, and stack allocation of small containers.
- check --fast <= 60 s and landing <= 5 min over a week: met so far (~9 s, ~15 s),
  but less than a week of history exists.
- Self-hosted lexer, parser and checker agree with the bootstrap on the full corpus: **met** (tools/selfhost.sh).
- Approvals log and checker exist and refused a real weakening in a test: **met** (tools/approvals_test.sh).

Not implemented: concurrency (servers handle one connection at a time) — model is a product decision.

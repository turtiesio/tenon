Milestone 1 (tenon.md §4), item by item:

- 10 real programs with differential and fuzz testing green: **met**
  (programs/: ledger, jobq, facts, kvhttp, mkplan, csvq, mdhtml, calc, and the
  self-hosted lexer/parser drivers; fuzzing 0 backend disagreements).
- Blind usability study at or below Python on line count and task time: **not met.**
  Wave 2 (task set 2, hidden tests written by Codex, 3 authors per language from
  Claude Opus, Claude Sonnet and Codex in a Latin square, compiler frozen at b5bd865;
  medians): hidden tests ~100% in all three languages; Tenon 1610 lines / 14640
  tokens / 7.1 min vs Python 1240 / 9380 / 4.1 and TypeScript 1791 / 15000 / 4.7.
  Tenon is on par with TypeScript but 1.3x Python's lines and 1.7x its time.
  Main causes measured: braces (one extra line per block), and Python's `re`
  (used in 9 of 10 solutions by every Python author) for input validation.
  All solutions, logs and notes: study/results/wave2/.
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

Concurrency: single-threaded event loop (user decision); see programs/chat. No multi-core parallelism.

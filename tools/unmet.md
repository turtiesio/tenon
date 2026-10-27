Milestone 1 (tenon.md §4), item by item:

- 10 real programs with differential and fuzz testing green: **met**
  (programs/: ledger, jobq, facts, kvhttp, mkplan, csvq, mdhtml, calc, and the
  self-hosted lexer/parser drivers; fuzzing 0 backend disagreements).
- Blind usability study at or below Python on line count and task time: **not met / not yet measured properly.**
  Wave 1 (1 author per language, task set 1): 100% hidden-test pass rate for
  all three languages; Tenon ~1.7x Python's tokens; task time invalid (fixed).
  Language changes since, driven by wave-1 notes: char literals, let-else,
  constants, mut parameters, Set, char-class helpers, find_from, Fs.rename.
  The full study (3 authors per language, 2 model families, task set 2) is next.
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

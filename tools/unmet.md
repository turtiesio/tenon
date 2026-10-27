Milestone 1 (tenon.md §4), item by item:

- 10 real programs with differential and fuzz testing green: **met**
  (programs/: ledger, jobq, facts, kvhttp, mkplan, csvq, mdhtml, calc, and the
  self-hosted lexer/parser drivers; fuzzing 0 backend disagreements).
- Blind usability study at or below Python on line count and task time: **lines met,
  time not met.** Wave 3, lines without closer-only lines (user decision, see
  docs/log.md): Tenon 1289, Python 1293, TypeScript 1241 (raw: 1612 / 1296 /
  1511). Time: Tenon 7.0 min, Python 4.8, TypeScript 4.4.
  Why time lags (same-model token diffs): Tenon's extra tokens are braces,
  `let`/`var`, parameter types, `->`/`=>` and `sys.console`, i.e. the explicit
  types, mutability and authority the language is built on. But TypeScript
  authors wrote more tokens than Tenon's (14614 vs 13610) and were faster
  (4.4 vs 7.0 min), and builds cost 0.25 s with similar run counts, so the gap is
  mostly unfamiliarity (lookups in docs, compile errors: median 11 vs 0 for
  Python). Levers in progress: if-let/while-let, hex literals, library gaps the
  authors hit (radix, Map.or_insert, split_once, path helpers), doc fixes, and a
  one-page quick start for Python/TypeScript programmers in the kit.
  Wave 2 (task set 2, hidden tests written by Codex, 3 authors per language from
  Claude Opus, Claude Sonnet and Codex in a Latin square, compiler frozen at b5bd865;
  medians): hidden tests ~100% in all three languages; Tenon 1610 lines / 14640
  tokens / 7.1 min vs Python 1240 / 9380 / 4.1 and TypeScript 1791 / 15000 / 4.7.
  Tenon is on par with TypeScript but 1.3x Python's lines and 1.7x its time.
  Main causes measured: braces (one extra line per block), and Python's `re`
  (used in 9 of 10 solutions by every Python author) for input validation.
  All solutions, logs and notes: study/results/wave2/.
  Wave 3 (fresh task set 3, hidden tests by Codex 250/250 against references,
  same Latin square, compiler frozen at 2749ba2): hidden tests 100% / 100% / 99%;
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

Concurrency: single-threaded event loop (user decision); see programs/chat. No multi-core parallelism.

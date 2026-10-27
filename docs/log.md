# Iteration log

Each entry: decision, rationale, measured effect. Reversals and mistakes included.

## 2026-10-27 — day 1: bootstrap

- **Bootstrap compiler in Rust, std only** (per tenon.md §2.6). Straight pipeline:
  `lexer → parser → check (+exhaust) → emit_c (+emit_body)`, plus `interp` as the
  reference semantics. No third-party crates.
- **Builtin API declared once, in Tenon** (`src/prelude.tn`): `extern fn` signatures
  are type-checked like any other function; each backend implements them by
  name. Non-primitive helpers (`map`, `filter`, `lines`, `unwrap_or`, ...) are
  ordinary Tenon. Replaces a hand-written builtin signature table in the checker
  (DRY: one source per fact).
- **No traits yet.** Every type derives equality, ordering, hashing and
  formatting structurally, so generic code needs no bounds. Maps are not
  ordered (trap if compared with `<`). Traits will be added only when a real
  program needs user-defined dispatch (no speculation).
- **Value semantics via refcounting + copy-on-write** in C; `Rc::make_mut` in the
  interpreter. Structs, tuples and non-recursive enums are by-value C structs;
  an enum is boxed only when it can contain itself.
- **Ownership protocol in the C emitter**: expressions yield owned temps or
  borrowed views; parameters are borrowed, results owned; storing retains.
  Borrowed operands are retained when a later sibling expression may mutate a
  local (assignment or `mut self` call), so C evaluation matches the
  interpreter's left-to-right semantics.
- **Statement separators**: newlines end statements (Go-style), except before
  `.`/`else` and inside `()`/`[]`. Measured effect on usability: TBD (study).
- **No shadowing** within a function: fewer subtle mistakes; cost is occasional
  renaming. Revisit with study data.
- **Mistake found by the corpus on day 1**: `tn_read_line` kept a stale index
  after compacting its buffer at EOF → infinite loop on a final line without a
  newline. Fixed; the test runner now kills tests after 20 s.

## 2026-10-27 — fuzzing, first program, linear types

- **Differential fuzzer** (`tools/fuzz.py`): random well-typed programs, interpreter
  vs C. First 100 programs found 3 bugs: user type names colliding with prelude
  type parameters, untyped `NULL` for empty map literals, `-2.abs()` parsing as
  `-(2.abs())`. Fix for the first: **type parameters are one capital letter plus
  optional digits**, and type names may not have that form. Simple, total, and it
  removes a class of ambiguity in owner arguments (`fn Map[K, V].x`).
- **Ledger** (first real program) found: assignments were not allowed as match
  arm bodies (`None => n += 1`); fixed. And in the program itself: recovery must
  rewrite the journal without the torn tail, or the next append is glued onto
  it. Unrecoverable records are archived (`journal.rejected`) before being dropped.
- **Linear/unique types** as a post-typecheck flow analysis (`src/linear.rs`, ~400
  lines): no runtime cost, no change to either backend. Base case for disposal:
  a type's own methods are exempt for `self`. Without modules this is a
  convention, not a guarantee — recorded as a known gap until modules exist.
- **Performance**: wordfreq 2.38x → 1.71x of C (string-identity hash memo, map
  last-hit cache, fused `for w in s.words()`, zero-copy `read_all`, in-place
  `lower`). Remaining gap is the two-level map layout plus two lookups per
  update in the idiomatic program. trees 2.55x → 1.35x (shared nullary variants,
  borrowed match bindings).

## 2026-10-27 — job queue, generic linear safety, modules

- **Job queue** (second program) uses `linear struct Claim`. It needed `map_err` on
  `Result[Option[Claim], _]`, which the first rule (no generic calls with linear
  type arguments) rejected. Replaced the rule with an analysis: a generic function
  accepts a linear argument for parameter P iff its body passes the linear check
  with P assumed linear (cached per function and parameter). `map_err` passes;
  `unwrap_or` is still rejected (it would drop the default).
- **Usability gap noted**: threading a linear value through an inspecting
  function (`let (c2, r) = run(c)`) is clumsy; an inspect-only parameter mode
  would remove it. Deferred until a second program needs it.
- **Modules** (trigger: the checksummed journal was duplicated verbatim in two
  programs). `import name`, `pub` items and fields, `module.item` access, methods
  only in the defining module. Extracted `std/journal.tn`; both programs shrank
  and their transcripts are unchanged. A test found derived formatting leaking
  private fields; foreign types now show private fields as `..`.

## 2026-10-28 — codecs, incident, landing path

- **Derived strict codec** (`encode`/`decode`), triggered by hand-written record
  encoders in three programs. Format = the literal syntax formatting already
  prints, so encoding is free in both backends; decoding is type-directed and
  canonical-only (re-encoding must reproduce the input). Forgery is prevented
  statically: no codec for capabilities, functions, linear/unique types, or types
  with fields the caller cannot see. The three programs lost ~60 lines.
- **Incident: red main.** The codec commit added a prelude `encode` that collided
  with the programs' own `encode`; the commit command piped `./check` through
  `tail`, which hid the failure. Fixed forward within minutes. Smallest fix for
  the class: `tools/land.sh` (the landing path that was missing): rebase on
  origin/main, `./check --fast`, push only on success. Cost: one 30-line script,
  no time added to landing beyond the check itself.
- **Papercut measured three times today**: `{` in string literals starts
  interpolation, so JSON/struct text in tests needs `\{`. Candidate fixes for the
  study to decide: raw strings, or interpolation only with a prefix. Kept for now.

## 2026-10-28 — study wave 1 (in progress), self-hosted parser

- **Study wave 1**: one author per language (Tenon: Claude Sonnet; Python: Claude
  Opus; TypeScript: Codex) against the frozen compiler of commit 3dc25e3. Python
  and TypeScript finished all 10 tasks quickly. The Tenon author's notes are the
  most valuable output so far: no character literals (magic byte numbers in 4 of 5
  tasks), undocumented details (args, ordering, split/lines, read_line, to_int,
  integer division, struct update), `while true` needing a dummy tail value, no
  `flush`. All fixed for wave 2: char literals `'a'` (Int code point, both
  lexers), `while true` without `break` diverges, `Console.flush`, ~20 doc
  clarifications. Deferred until more evidence: mutable parameters for plain
  functions, map entry/update APIs.
- **Self-hosted parser** (selfhost/parser.tn, ~700 lines) agreed with the
  bootstrap AST dump on all 118 files on its first run, including malformed
  inputs.
- **Red team**: Codex refused the security-flavoured brief (as tenon.md §2.4
  warns); reassigned to Claude Sonnet, framed as compiler QA.

## 2026-10-28 — programs 7-10, language batch from evidence, QA round 1

- **Workers** (Claude Sonnet, isolated worktrees, landing themselves) wrote mkplan,
  csvq, mdhtml and calc: 10 real programs. Their GAPS.md files plus the study notes
  drove one batch, each item with 2+ independent reports: constants, INT_MAX/MIN,
  checked arithmetic, sort_by_desc, `_` parameters, operator-leading continuation
  lines, let-else, char-class helpers, find_from, Fs.rename/is_dir, Set, and `mut`
  parameters (call site marked `f(mut x)`, no aliasing between mut arguments).
- **String building** was quadratic (`out += s` copied): 2.9 s -> 0.01 s for 200k
  appends by appending in place when the buffer is unshared (capacity in the
  string header). Value semantics preserved and tested (aliasing cases + ASan).
- **Performance target met** on all benchmarks after a one-lookup lowering of the
  counting idiom `m[k] = m.get_or(k, d) + x` (wordfreq 1.7x -> ~1.35x of C).
  Rust baselines added; Tenon beats idiomatic Box-based Rust on trees.
- **Self-hosted checker** (worker, Claude Opus) agrees with the bootstrap on all 154
  corpus files on first landing (49 accepted, 105 rejected, identical first
  diagnostics).
- **Mutation testing** first batch: 14/25 killed. Survivors became tests (UTF-8
  boundaries, byte bounds, or-pattern bindings, duplicate literal arms, exponents)
  and exposed that no test ran under sanitizers -> tools/asan.sh in the evidence loop.
- **QA round 1** (Claude Sonnet; Codex refused): 9 findings, all fixed the same
  day: Fs escape via NUL bytes (C truncation) and via symlinks under an attenuated
  root; ports silently reduced mod 65536; a match guard could consume a linear
  value; linear temporaries dropped after inspection; `..base` dropping a replaced
  linear field; structs with function fields and function map keys compared
  (backends disagreed); NaN map keys (backends disagreed; Float keys now rejected);
  native stack overflow releasing a 1M-node chain (bounded-depth release).
  Five new checker rules wait in tests/pending-reject/ until selfhost/ mirrors them.
- **Incident**: a landing raced an agent writing into the shared checkout
  (unstaged change during rebase). Fix: `rebase --autostash` in tools/land.sh.
- **Open product decision**: the concurrency model (see the final report).

## 2026-10-28 (later) — real-program benchmarks, allocator, QA round 2, study wave 2

- **Real-program benchmarks** (worker): calc and mdhtml against hand-written C,
  Rust and Python. Honest result: 3.1x and 2.4x of C, so the 1.5x target is not met
  on real programs (only on microbenchmarks). Then: small maps scan instead of
  hashing (calc 3.1 -> 2.6x); a 16-byte size-class allocator with free lists for
  blocks <= 512 bytes (calc 2.6 -> 1.8x, mdhtml 2.4 -> 1.9x, trees 0.53x);
  `s += a + b` lowered to in-place appends (mdhtml 1.8x). Remaining gap: reference
  counting traffic and a heap-allocated map per interpreted call (C: stack array).
- **Recursive-enum node reuse** made trees faster than C (0.7x): C mallocs and frees
  every node.
- **QA round 2** (the same agent re-attacking round-1 fixes): 15 more findings,
  including a high-severity one: a client generic wrapper (`struct Wrap[A]`) could
  drop or duplicate another module's linear value because methods of any generic
  type exempted `self`. Rule now: only types *declared* linear/unique decide how
  their values end. Also: Fs.write followed a symlink planted at the temp file;
  polymorphic recursion hung `tenon build`; map ordering, constant cycles and
  un-inferable lets moved from run time to compile time; traps in prelude code are
  reported at the user's call; the interpreter's equality short-circuited on Rc
  identity (NaN/functions equal to themselves) unlike C; native main now runs on a
  1 GB stack like the interpreter. All 24 repros re-verified on main.
- **The sanitizer loop paid off the same day**: tools/asan.sh caught an
  out-of-bounds read introduced by the symlink fix before it reached main.
- **Study wave 2** (task set 2, hidden tests by Codex, 3 authors per language in a
  Latin square of Claude Opus / Claude Sonnet / Codex, compiler frozen at f6b8396).
  Round 1: 100% hidden-test pass rate in all languages; Tenon ~1.6x Python's tokens
  and ~1.7x its time. Tenon authors' notes drove: while-true divergence bug with
  nested breaks, `()` pattern bug, Heap, List.filled/swap/sort_with,
  Option.and_then/is_some_and, rem/div_euclid, strip_prefix/suffix, is_digits,
  trim_chars. Structural costs remain: braces add ~1 line per block against Python,
  and Python's `re` compresses input validation.

## 2026-10-28 — product decisions (by the user)

- **Syntax: keep braces.** The line-count gap against Python is accepted as a cost;
  attack the remainder through the library (std/regex) and idioms.
- **Concurrency: single-threaded event loop** (readiness API over many connections).
  No data races by construction with non-atomic reference counts; deterministic
  event order; no multi-core speedup.

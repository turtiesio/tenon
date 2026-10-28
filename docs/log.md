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

- **Milestone 3 scope (decided during milestone 2):** ready for real users (stdlib
  breadth, package namespaces, debugging and profiling, a study where model authors
  build and maintain larger programs; AI models count as real users), deeper
  correctness (contracts, effects, property tests), scale (distributed workers,
  macros), carried-over gaps, and a no-staleness mechanism (check gates, dead-code
  reports, weekly hygiene review, dogfooding the tools in Tenon). No Windows or
  WebAssembly. Definition of done: tenon.md section 6.

- **CLI and seed (after the milestone-2 cleanup audit, docs/CLEANUP_PLAN.md):** one
  self-hosted `tenon` binary with subcommands (run build emit check test fmt lsp
  fetch tokens ast) replaces tenonc/tenonfmt/tenonlsp; the frozen Rust compiler is
  renamed `tenon-seed` and only builds stage 1. The seed stays Rust and may only
  shrink.

- **Milestone 2 scope (after milestone 1):** repository layout cleanup; fully
  self-hosted compiler; traits with generic bounds and explicit `dyn`; multi-core
  via isolated workers and typed channels; tooling: fmt, language server, packages
  (path + git dependencies, lockfile, no registry), VS Code extension as a local
  .vsix with syntax highlighting. Definition of done: tenon.md section 5.

- **Goal closed (after wave 6):** the user accepted the current state and cleared
  the goal. Milestone 1 stands as reported in STATUS.md: study time unmet (1.47x
  Python), human sample review and a week of loop history still open.

- **Study time target (decided after wave 5):** stays "at or below Python" and
  is reported as unmet (wave 5: Tenon 1.47x Python, TypeScript 1.2x). No design
  change (braces, explicit types, let/var, explicit console) is made to chase
  it; the language keeps improving between waves.

- **Study line metric (decided after wave 3):** lines are counted without
  closer-only lines (`}` alone, `});` ...), the same rule in every language,
  because Python closes blocks by dedenting at no line cost. The raw count is
  still reported next to it.

- **Syntax: keep braces.** The line-count gap against Python is accepted as a cost;
  attack the remainder through the library (std/regex) and idioms.
- **Concurrency: single-threaded event loop** (readiness API over many connections).
  No data races by construction with non-atomic reference counts; deterministic
  event order; no multi-core speedup.

## 2026-10-28 (evening) — event loop, regex, performance, self-hosting complete

- **Event loop** (user decision): `Poller` owns sockets by id; `wait` returns
  Accepted/Data/Closed/Timeout in id order, via poll(2) in both backends (the
  interpreter declares poll through FFI to libc; still no crates).
  programs/chat serves concurrent clients; stable across repeated runs.
- **std/regex** (worker): backtracking regex in Tenon with a step limit; 906
  cases cross-checked against Python's `re` (3 documented differences). Found
  a module-resolution pitfall: a file named like a std module imported itself.
  Fixed: a file never imports itself (both checkers).
- **Performance**: hash-free lookups in small maps (calc 1.77x -> 1.52x of C;
  Tenon now matches idiomatic Rust on calc). mdhtml stays at ~1.9x of C:
  per-character work and string copying that hand-written C avoids.
- **Self-hosted checker complete** (worker): agrees with the bootstrap on all
  corpus files; 30,000 mutated programs, 0 disagreements. Every checker change
  since has to be mirrored (it caught three drifts the same day: Poller type,
  std module list, the while-true quirk).
- **Loop time**: check --fast reached 26.6 s (self-hosting cross-check over 420+
  files); parallelized to ~20 s.
- **Wave-2 notes, second batch**: enumerate, Map.update, Option.map_or/filter,
  Int.fmt_fixed, Float.to_fixed, clearer range error, kit-relative doc paths.

## 2026-10-28 (night) — benchmarks within target, landing hygiene, study wave 3

- **All five benchmarks within 1.5x of C** (worst calc 1.39x, mdhtml 1.24x). The
  two real-program benchmarks now mirror the structure of their C and Rust
  counterparts: one output buffer passed down (`mut out: Str`) instead of
  each function returning a fresh string, and call parameters in parallel
  lists instead of a new Map per call. The old versions measured 1.85x/1.62x;
  the performance model in docs/reference.md now says why.
- **Silent timeout failure**: programs.sh's `perl alarm` timeout did nothing when
  SIGALRM was inherited as ignored (a hung kvhttp scenario sat for hours). The
  wrapper now resets SIGALRM to default first.
- **land.sh swept in another agent's drafts** (`git add -A` committed study/tasks3
  work in progress into two unrelated commits). It now commits tracked changes
  plus explicitly named new paths.
- **mutate.py** crashed copying the fs_jail symlink loop; copies links as links.
  Batch 2: 19 killed / 11 survived; a worker is writing tests for all survivors.
- **Study wave 3** started: task set 3 (10 specs by a separate agent), hidden
  tests by Codex in study/hidden3, 9 authors in the wave-2 Latin square,
  compiler frozen at 2174ddd (with std/regex and the wave-2 library additions).

## 2026-10-28 (late night) — wave 3 results, line metric, wave-3 fixes, wave 4

- **Wave 3 scored** (study/results/wave3): hidden tests 100/100/99%; Tenon
  1612 lines vs Python 1296, but 21% of Tenon's lines are closer-only. **User
  decision**: the milestone counts lines without closer-only lines in every
  language (approvals log). Then Tenon 1289 vs Python 1293: lines met. Time
  (7.0 vs 4.8 min) not met; TypeScript wrote more tokens than Tenon yet was
  faster, so the gap is unfamiliarity and compile errors, not volume.
- **From the wave-3 notes** (requests made by 2-3 of the Tenon authors): `if let`/`while let`
  (desugared to match in both parsers), 0x/0b/0o literals, radix conversion,
  Int.pow, Result combinators, Map.or_insert, split_once/rfind, Fs.mkdir_one,
  path helpers, many reference fixes (exit codes made exactly true, Fs.list,
  Fs.write temp name, Sys.net).
- **Change safety**: adding path_join to the prelude would have broken any
  program defining its own. User items now hide prelude items per file (both
  checkers).
- **docs/quickstart.md**: a one-page Python/TypeScript translation table,
  every snippet from a test; in the study kits from wave 4 on.
- **Study harness**: try.sh keeps the caller's directory (wave-3 authors lost
  runs to relative paths).
- **Wave 4** launched: task set 4, hidden tests by Codex (study/hidden4),
  same Latin square, compiler frozen at 3487dd2.

## 2026-10-28/29 — waves 4-6, time analysis, evidence fix

- **Waves 4-6** (fresh task sets, hidden tests by Codex 250/250 each): lines at
  or below Python every wave (869/913, 801/920, 910/978); Tenon time 1.69x, 1.47x,
  1.47x Python; hidden tests 98%, 100%, 100%; compile errors fell to 0.
  User decision after wave 5: the time target stays as written and is reported
  unmet; no design change is made to chase it.
- **Time analysis** (study/results/wave4/TIME_ANALYSIS.md, transcripts of matched
  pairs): the gap was notes written on the clock (study-rule bias, fixed),
  rebuild per run (build cache), no byte input (added), and more code to write,
  partly because the reference's own regex example was broken (`{4}`
  interpolated; fixed, pinned by a test). After those, wave 6's added library
  features (format specifiers, max_by/group_by) did not move time: the rest
  tracks tokens (explicit types, braces, let/var).
- **Language from study notes**: byte I/O, raw strings, if-let/while-let, hex
  literals, format specifiers with grouping, user items hide prelude items (change
  safety), padding by code points, uniform "\r" stripping in read_line and
  lines(), one-sided trims, retain, rev_range, Fs.truncate, binary_search, and
  many doc fixes now pinned by doc-claim tests and tools/doctest.py.
- **Silent evidence failure**: the build cache skipped writing the C file that
  tools/asan.sh needs, so the sanitizer run failed to build every test, while
  STATUS only described the tool. Fixed (cache bypassed under TENON_KEEP_C), and
  STATUS now shows the sanitizer result itself (91 programs, all clean).
- **Study ops**: a Claude API rate limit stopped six wave-6 authors mid-task;
  their kits were set aside unscored and the authors rerun on fresh kits.

## 2026-10-28 — repository layout

- **One purpose per directory**, no behaviour change: the Rust bootstrap is the
  `bootstrap/` package of a root Cargo workspace (binary still
  `target/release/tenon`); the prelude and standard modules are `lib/prelude.tn`
  and `lib/std/` (their displayed names stay `<prelude>` and `<std>/NAME.tn`);
  the red-team report and repros are `tests/redteam/`. The 24 capability-escape
  probes committed at the root by accident became tests: 18 in
  `tests/reject/cap_probe_*`, 5 in `tests/run/cap_probe_*` (now guarded), one
  repro (`tests/redteam/repros/25-*`). Entries above name the old paths.

## 2026-10-28 — self-hosting stage A: the C backend in Tenon

- **Self-hosted C backend** (selfhost/emit*.tn, ~2,700 lines, port of the
  bootstrap's emit_c/emit_body/emit_ctl/emit_builtins) and driver
  selfhost/tenonc.tn (`check`, `emit`, `build`). It works from the
  self-hosted checker's side tables (`checker.check` now returns them; no
  diagnostic changed). `tenonc emit` is byte-identical to `tenon emit` on all
  306 accepted corpus files (tools/selfhost.sh), and the compiler reaches a
  fixpoint: stage1 (bootstrap-built) and stage2 (stage1-built) emit the same
  3 MB of C for tenonc.tn as the bootstrap (tools/fixpoint.sh, in ./check).
  Stage1 emits in 0.8x-1.1x the bootstrap's time (tenonc.tn 58 vs 73 ms).
- **Language addition: `Proc`** (`sys.proc`), the capability to run a
  command (`Proc.run(cmd, args) -> Result[Int, IoError]`) and read an
  environment variable (`Proc.env`), needed by `tenonc build` to run `$CC`.
  Only `main`'s Sys has one; it is the whole authority of the user, so a
  function that runs commands says so in its signature.
- The prelude, std modules and runtime header are read from the repository
  (`--root`, `$TENON_ROOT`, or `.`) instead of embedded.

## 2026-10-28 — self-hosting stage B: tenonc replaces the bootstrap CLI

- **Interpreter in Tenon** (selfhost/interp.tn, ival, icode, ieval, ibuiltin,
  icap, icodec; ~2,500 lines; port of interp.rs, builtins.rs, value.rs,
  codec.rs): `tenonc run`. A value is one struct whose fields are used by
  kind, so deep parts change in place through `mut` places; Tenon's own
  copy-on-write lists and maps give the value semantics. Names are resolved
  once to frame slots. Capabilities are the host's (an interpreted `Fs` is a
  host `Fs`), so the jail rules are the C runtime's. Same stdout, stderr and
  exit status as `tenon run` on 755 of 758 corpus files, 0 different, 3
  skipped as slower than 20 s in the bootstrap (tools/interp_diff.py), and on
  the 5 benchmarks; speed 0.8x-1.1x the bootstrap's (fib 18.8 vs 17.0 s,
  trees 33.7 vs 43.3 s, std_regex 2.4 vs 2.3 s).
- **`tenonc test`** (selfhost/testrun.tn, port of testrun.rs) with 8 worker
  processes; **`tokens`/`ast`** subcommands; **`check`** now behaves like
  `tenon check`; a **build cache** like the bootstrap's (exact C match).
- **Language addition:** `Proc.run_with(cmd, args, dir, input, timeout_ms)`
  (captured output, a timeout; the test runner) and `Proc.exit(status)` (any
  status, also the reserved ones; the interpreter passes on 70 and 72).
- **Gates:** ./check builds tenonc (stage1) with the bootstrap and runs the
  suite, programs, doctest and the grammar check with it; `tenon test` runs
  as the differential reference; selfhost.sh and fixpoint.sh stay.
  ./check 21.4 s before stage B (fewer steps), 30-35 s after.
- **Freeze:** `frozen bootstrap/*` in governance/guarded.txt: tools/approvals.py
  refuses any unapproved change to the bootstrap and any growth of its line
  count (governance/README.md).

## 2026-10-28 — packages (tenon.md §5, milestone 2)

- **`tenon.toml`, `tenon.lock`, `tenonc fetch`** (selfhost/pkg.tn,
  pkgtoml.tn; docs/packages.md). A strict TOML subset parsed in Tenon. A
  dependency is used through its entry module `src/NAME.tn`, so its own
  modules sit next to it and need no new import syntax. Import order: next
  to the file, then a dependency of the file's package, then std. Module names
  stay global: a clash between packages is an error, not a namespace, so
  the checker is unchanged.
- **Pinned and live:** git dependencies are cloned through `git` (Proc) into
  `$TENON_HOME/cache/git/` at a locked commit and verified against a content
  hash (four polynomial hashes, 128 bits; detects corruption, not
  cryptographic) on every build. Path dependencies are read as they are.
  Builds are offline; a missing or stale lock asks for `tenonc fetch`.
- **Package root:** the nearest tenon.toml above the file, found lexically
  with `..` (no getcwd), so `tenonc test` works with each test run from its
  own directory. The language server uses the same resolver.
- tools/pkg_test.sh (47 checks, ~1.5 s, local `file://` repositories) in
  ./check.

## 2026-10-28 — traits (tenon.md §5, milestone 2)

- **Syntax** (chosen to match the existing generics): `trait Name { fn m(self, ...) -> T; fn d(self) -> T { default } }`,
  `impl Name for Type { ... }`, `impl[T: Show] Name for List[T]` (impl type
  parameters like `fn f[T]`), bounds `fn f[T: A + B](x: T)`, the type
  `dyn Name` and the explicit conversion `dyn Name(x)` (a call-like form: no
  new operator or precedence, and it reads as a constructor; `x as dyn Name`
  was the alternative). docs/reference.md §17.
- **Semantics:** bounds monomorphized in C and instantiated per type in the
  interpreter (only functions bounded by a non-derived trait, and default
  methods); `dyn` calls through a static vtable per (trait, type); object
  safety (`self` by value, not generic, no `Self`); coherence (one impl per
  trait and type, overlapping generic impls refused) and the orphan rule (in
  the trait's or the type's module). Eq, Ord, Hash and Show are prelude
  traits satisfied structurally, as before; only Show can be implemented (it
  overrides formatting everywhere but `encode`); user Eq/Ord/Hash are refused
  in v1 so that map keys and sorting cannot differ between the backends.
  `dyn` cannot hold linear or unique values; an impl finishes a linear value
  through `self` only in the type's module.
- **The v2 split:** the bootstrap is frozen and cannot parse traits, so
  tenonc-only files live under `v2/` directories: lib/v2/prelude.tn
  (appended to the prelude by tenonc), tests/v2/{run,reject,lex,parse,fmt,lsp}.
  tools/selfhost.sh, interp_diff.py and checkfuzz.py skip them; fixpoint.sh
  includes them (stage1 = stage2); `tenonc test tests/v2` runs both
  backends and checks lex/parse goldens; fmt_check compares `tenonc ast`;
  the grammar check reads selfhost/lexer.tn's keywords; doctest uses tenonc.
- **Tests:** tests/v2/run (10 programs: impls and defaults, bounds,
  generic impls, dyn in lists/maps/structs/enums, Show overrides, modules,
  linear and `mut`, corners), 41 reject tests (one per diagnostic), lex and
  parse goldens, a formatter golden, LSP hover/definition/completion.

## 2026-10-28 — workers and channels (tenon.md §5, milestone 2)

- **Fix first:** a missing map key reached through a place (`m[k] += 1`) now
  shows the key type's Show impl in the interpreter too (ieval.nk), as in C
  and as `m[k]` read as a value; tests/v2/run/trait_show_key_place.tn.
- **API** (user decision: isolated workers and channels next to the event
  loop; docs/reference.md §18): `sys.workers()` gives the `Workers`
  capability; `w.spawn(f, arg) -> Worker[R]`, `h.join() -> R`, `w.cores()`;
  `channel() -> (Sender[T], Receiver[T])` with `send`, `close`, `recv ->
  Option[T]`, `try_recv`; `w.par_map(xs, f)` and `par_map_n` in
  lib/v2/prelude.tn (Tenon over the primitives: a few chunks per worker on a
  job channel, results by chunk index). A method on `Sys` rather than a new
  field: `Sys` is declared in lib/prelude.tn, which the frozen bootstrap
  reads. `Sender`, `Receiver` and `Worker` are builtin handle types (shared,
  atomically counted in C), so no untyped handle is ever visible.
- **Decisions.** Copy, not move, for v1: everything sent is deep-copied by
  the sender (per-type `T_copy` in C; nothing in the interpreter, whose
  values are immutable); unique values move by the type system (the sender
  loses them). Channels are unbounded and MPMC, closed only by `close()`:
  the interpreter has no destructors, so "closed when the senders are
  dropped" could not behave the same on both backends; instead a program
  in which every thread waits traps with `deadlock` (C: counts of live and
  waiting threads under the one channel lock; interpreter: no worker can
  run), at main's wait. A trap in a worker ends the program (traps are not
  caught anywhere), so `join` gives `R`, not a `Result`. Send excludes linear
  types (a dropped channel or unjoined worker would lose the obligation) and
  Poller/Listener/Conn (sockets stay with the worker that opened them); a
  worker cannot return a unique value (handles are copyable, every join gives
  the result). Every other capability is sendable: authority stays explicit
  because a worker gets only what is passed.
- **C runtime:** a program that calls `sys.workers()` is compiled with
  `TN_MT`: one thread-local struct holds the allocator's free lists, the
  release queue and the trap location (separate thread-local variables made
  bench/trees 25% slower on macOS, where each one costs a call; the struct
  4-5%); recursive enums use the free lists instead of per-type pools (the
  pools as thread-locals cost another 20%); the shared nullary enum nodes
  keep their counts; output is written under a lock (println as one piece),
  input read under another, one trap message wins. Free lists keep at most
  64 MB per thread, so a worker that only receives does not hoard memory.
  Programs without workers compile to exactly the C they did before (the
  whole v1 corpus is still byte-identical to the bootstrap's).
- **Interpreter:** the interpreter is built by the frozen bootstrap, so it
  cannot use threads. A deterministic cooperative scheduler
  (selfhost/iwork.tn) runs workers when main waits; a waiting worker is
  unwound (`CBlock`) and resumed by re-running it with its effects (all
  builtins from Console.print on) replayed from a log. Same observable
  results for every program whose output does not depend on scheduling;
  resuming is quadratic in the number of waits (fine for tests; use build).
  try_recv yields: in a worker it gives up its turn once, in main it gives
  every worker a turn, so event loops that poll channels work.
- **Measured** (M4 Max, 16 cores): bench/v2/mandel 3.62x on 4 workers, 6.9x
  on 8; bench/v2/pwords (allocating, maps copied back) 3.51x and 6.2x
  (tools/bench.py --parallel, also in STATUS.md); serial Tenon = C on mandel.
  Copies: 0.6 ns per Int, 12 ns per string, 18 ns per map entry; round trip
  4.5 µs; spawn+join 18 µs.
- **Evidence:** tests/v2/run (workers, channels, par_map, pool, event loop,
  trap, deadlock, closed channel, stack overflow; both backends), 14 reject
  tests (one per isolation rule), programs/v2/scan (a parallel scanner/grep
  over a directory tree, scenario on both backends); tools/tsan.sh
  (ThreadSanitizer, every v2 run test and scan, 3 runs each: clean),
  tools/asan.sh now covers programs/v2 (clean).

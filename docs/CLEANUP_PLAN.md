# Cleanup plan (audit of 25f3385, 2026-10-28)

Read-only audit. Items are ranked by payoff / risk and grouped into batches;
each batch can be one landing. Effort: S (< 1 h), M (half a day), L (a day or
more). Items touching `selfhost/` drivers and interpreter modules,
`runtime/tenon.h` or `lib/v2` are marked **(after concurrency lands)**: the
workers/channels work is changing them now.

Hard constraint for every item: `./check` builds stage1 tenonc with the frozen
bootstrap, and the bootstrap embeds `lib/prelude.tn` and `lib/std/*.tn`
(`bootstrap/src/main.rs:26,40`). So `selfhost/*.tn`, `lib/prelude.tn` and
`lib/std` must stay inside what the bootstrap accepts, and no item may add an
`extern fn` the bootstrap does not have. Bootstrap findings are notes only:
changing it needs an approvals entry.

## 0. Measurements

### `./check` per step

These were measured in a clean clone of 25f3385 on a 16-core Mac at load
average 4-6, with an empty build cache.

| Step | Cold | Warm (rerun) | Notes |
|---|---|---|---|
| `cargo build --release` | 10.8 s | ~0 s | |
| bootstrap builds stage1 tenonc (`-O2`) | 26.6 s | 0 s on a cache hit | emit takes 0.13 s; `cc -O2` on 81k lines (4.9 MB) of C takes 12-24 s, depending on load; `-O0` takes 2 s |
| `tenonc test tests tests/v2` | 13.9 s | 3.0 s | the cold time is mostly C compiles of the tests |
| `tenon test tests` (bootstrap) | 13.0 s | 2.6 s | a second run of the same suite |
| `doctest.py` | 0.1 s | | |
| `vscode_grammar_check.py` | 1.1 s | | |
| `programs.sh` | 8.3 s | 3.5 s | |
| `cache_test.sh` | 0.6 s | | |
| `pkg_test.sh` | 2.2 s | | |
| `selfhost.sh` | 21.6 s | 4.1 s | |
| `fmt_check.sh` | 5.9 s | 1.5 s | the bootstrap also builds `tenonfmt` here |
| `lsp_test.py` | 4.1 s | 0.9 s | the bootstrap also builds `tenonlsp` here |
| `fixpoint.sh` | 14.5 s | 3.2 s | builds stage2 |
| `approvals_test.sh` | 8.4 s | 4.8 s | clones the whole repo (12.9k files, 123 MB `study/`) |
| **Total** | **~131 s** | **~30 s** with tenonc unchanged; **~55-70 s** after a selfhost edit | budget: 60 s |

`STATUS.md` reports 11.8 s, which is stale.

### Optimization level of stage1

Measured on warm caches:

| | Build | Suite | `selfhost.sh` | `fixpoint.sh` | Sum |
|---|---|---|---|---|---|
| `-O2` | 23.7 s | 3.0 s | 4.1 s | 3.2 s | ≈ 34 s |
| `-O0` | 2 s | 11.5 s | 7.8 s | 7.2 s | ≈ 28.5 s |
| `-O1` | 21.5 s | | | | no gain over `-O2` |

### Process mechanisms (tenon.md §2.3: at most ~5)

1. `check`, a 13-step pipeline.
2. `tools/land.sh`.
3. `.github/workflows` CI.
4. Governance: `approvals.py`, `guarded.txt`, `approvals.log` and `approvals_test.sh`.
5. The evidence loop, `tools/evidence.sh`, which runs `fuzz.py`, `asan.sh`, `mutate.py`, `bench.py` and `fmt_check --all`.
6. `tools/status.py` with `STATUS.md`, plus the hand-written `tools/unmet.md`.
7. Study tooling: `tools/study.py` and `study/harness.py`.
8. Orphan evidence tools that nothing runs: `tools/interp_diff.py` and `selfhost/checkfuzz.py`.

Counting each line as one mechanism gives about 8. Batches A and C bring the
count back to 5: check, land, CI, governance, evidence (with status inside
evidence). Study stays as product evidence.

### Files over ~1000 lines (tenon.md §2.3)

- `runtime/tenon.h`: 2511. tenon.md requires a single header, so state that reason in the header.
- `selfhost/ckinfer.tn`: 1231.
- `selfhost/parser.tn`: 1154.
- `docs/reference.md`: 1109.
- Frozen bootstrap, note only: `bootstrap/src/emit_body.rs` 1133, `check.rs` 1112, `interp.rs` 1070.
- Close to the limit: `ckenv.tn` 993 and `emitbody.tn` 984.
- The bootstrap is 10,420 lines in total, over its own ~10k cap (tenon.md §2.6). Note only: it may only shrink.

## Batch A: get `./check` back under 60 s (do first)

### A1. Move the bootstrap's `tenon test tests` out of `check`, into evidence. S, low risk. Done in f9523d2 (it runs in tools/evidence.sh).

- **Why:** it runs the v1 suite a second time (13 s cold, 2.6 s warm).
  - The bootstrap is frozen.
  - `selfhost.sh` already requires byte-identical C from both compilers on every accepted file.
  - `tenonc test` checks both of tenonc's backends against the goldens.
  - The only thing it still covers is the bootstrap interpreter, and `interp_diff.py` is the tool that measures that.
- **Evidence:** `check:19`.
- **Dependencies:** none. It unblocks D3, which folds `tests/v2`.

### A2. Make `approvals_test.sh` build a tiny fixture repo instead of cloning the whole tree. S, low risk. Done in f9523d2 (4.9 s -> 1.1 s).

- **Evidence:** `tools/approvals_test.sh:7` runs `git clone --depth 1` on all 12.9k files. The test needs only `tools/approvals.py`, `governance/*`, one `tests/reject` file and `bootstrap/src/diag.rs`, plus the line count of the frozen glob.
- **Saves:** 4-8 s.

### A3. Stage1 build time. M, low risk. Done in f9523d2: option 2 plus option 3; the seed builds stage0 at -O0, stage0 builds stage1 in 8 parallel units (stage1 2.9 s, was 14 s).

- **Option 1 (S):** build stage1 at `-O0` in `check:16`. Measured net gain is about 5 s when selfhost changed. The loss is about 13 s when only tests changed and the `-O2` stage1 would have been a cache hit.
- **Option 2 (M, recommended):** split the C into N translation units when `build` compiles, keeping `emit` output unchanged so that `selfhost.sh` and `fixpoint.sh` stay byte-for-byte. Then run `cc -O2` in parallel. With 81k lines across 5771 functions, 8 TUs should give about 3-4 s. This also speeds up every user build of a large program.
- **Option 3 (S, do in any case):** make `check` print the time of each step, so loop time is measured rather than guessed (tenon.md §2.1).
- The C time is spread across the file, not concentrated in a few functions. Compiling the largest function (`emitbi.extern_call`, 5727 C lines) with `optnone` saved only 0.5 s.
- **Evidence:** the measurements in section 0.

### A4. Merge `selfhost.sh` and `fixpoint.sh` into one parallel pass over the corpus. M, low risk. Done in f9523d2 (tools/selfhost.sh; fixpoint = stage0 vs stage1).

- **How:** one job per file runs bootstrap tokens/ast/check/emit, then stage1, then stage2 emit. Today both scripts walk the same corpus, and both run `stage1 check` and `emit` on the same files.
- **Evidence:** `tools/selfhost.sh:24-56` and `tools/fixpoint.sh:31-42` are near copies, each with its own `one()` and `xargs -P 8`.
- **Gains:** one script fewer and one stage1 pass fewer, about 2-3 s warm.

### A5. Build `fmt` and `lsp` once, with tenonc instead of the bootstrap. S, low risk. Folded into B1.

- **Evidence:**
  - `tools/fmt_check.sh:20` builds `tenonfmt` at `-O2` with the bootstrap.
  - `tools/lsp_test.py:466` builds `tenonlsp` with the bootstrap.
- Once B1 lands they are subcommands of the one binary `./check` already builds.

## Batch B: one CLI, consistent flags

### B1. One `tenon` binary with subcommands. M, medium risk. (after concurrency lands)

- **What:** one driver, `selfhost/tenon.tn`, built to `target/tenon`, merging `tenonc.tn`, `tenonfmt.tn` and `tenonlsp.tn`. The subcommands are `run build emit check test fmt lsp fetch tokens ast`.
- **Why:**
  - tenon.md §5 itself says `tenon fmt`.
  - There are three binaries with three message prefixes (`tenonc:`, `tenonfmt:`, and none for the LSP).
  - The three are built three times per check (A5).
  - No document tells a user how to get `tenonfmt` or `tenonlsp`. `reference.md:933`, `tenonfmt.tn:6`, `tenonlsp.tn:18` and `editors/vscode/README.md:39-40` give three different recipes, all through the bootstrap.
- **Migration:**
  - Rename everything in the same change, with no `tenonc` shim (tenon.md §2.3).
  - The VS Code setting `tenon.serverPath` defaults to `tenon lsp`.
  - The bootstrap keeps `target/release/tenon`. Rename its use in tools to `$SEED`, so no reader confuses the two.
- **Dependencies:** B2. Also update `editors/vscode/extension.js:33,73`.

### B2. Flags anywhere; drop positional ROOT. S, low risk. (after concurrency lands)

Current behaviour in `selfhost/tenonc.tn`:

- `run` takes `--root` only directly after `run` (`:228-229`).
- `build` and `emit` take FILE as `args[1]` (`:265,272`).
- `check` with two arguments treats the second as ROOT (`:134`), so `check f.tn X` silently changes the root.
- `tokens` and `ast` ignore `--root`.
- `tenonfmt --check` is accepted only first (`tenonfmt.tn:30`).

Fix: one argument parser for all subcommands, plus `--help`. The positional ROOT exists only for `selfhost/check.tn` compatibility, and that file is dead (C1).

### B3. `tenonc test` without `$TENONC` fails opaquely. S, low risk. (after concurrency lands)

- **Evidence:** `selfhost/testrun.tn:196`, `p.env("TENONC").unwrap_or("tenonc")`. `target/tenonc test tests` from the README fails with "FAIL a test worker did not finish" unless `tenonc` is on PATH (reproduced).
- **Fix:** default to the running executable's path, or fail with a clear message naming `$TENONC`.
- **Related clean-up:** `check:18` sets `TENON=` for tenonc, which never reads it. The scripts use both `$TENON` and `$TENONC` for the same binary (`doctest.py:26`, `vscode_grammar_check.py:35`, `programs.sh:7` versus `selfhost.sh`, `fixpoint.sh`, `pkg_test.sh`). Use one variable.

### B4. One table of environment variables and exit codes. S, low risk.

- **Variables:** `TENON_ROOT`, `TENON_CACHE`, `TENON_KEEP_C`, `TENON_HOME`, `CC`, `TENONC`. Each is documented in 3-6 places today: `tenonc.tn:20-28`, `SELFHOST.md:23,128-134`, `EMITTER_NOTES.md:34`, `reference.md:30-32`, `vscode/README.md:62`.
- **Already out of sync:** the cache default (`<tmp>` vs `$TMPDIR`), and which commands are package-aware (`reference.md:775` vs `packages.md:174`).
- **Exit codes:** 0 ok, 1 diagnostic, 2 usage or I/O, 70/72 traps.
- **Where:** `docs/tools.md` (see the target structure).

## Batch C: evidence that tests the compiler actually used

### C0. The evidence loop exercises the frozen seed, not tenonc. M, low risk. Highest-value non-time item. Done in 2c71f64.

- **Evidence:**
  - `tools/mutate.py:15` `TARGETS` lists only `bootstrap/src/*.rs` and `runtime/tenon.h`, and it rebuilds with cargo and runs `tenon test` (`:50-69`). Mutating a frozen file measures nothing that can change. It should mutate `selfhost/ck*.tn`, `emit*.tn` and `runtime/tenon.h`, rebuild stage1, and run `tenonc test`.
  - `tools/fuzz.py:10` and `tools/bench.py:8` use `target/release/tenon`. Benchmarks are valid while the C is byte-identical, but fuzzing should drive tenonc's two backends, and the bootstrap as a third opinion.
  - `tools/interp_diff.py` and `selfhost/checkfuzz.py` are run by nothing: neither `check` nor `tools/evidence.sh:15-21` calls them. Add both to `evidence.sh`.
- **Dependencies:** A1, since `tenon test` moves here.

### C1. Dead code and files. S, low risk. Done in f9523d2 (not done: examples/run lives only in the main checkout, untracked; the `pub` trimming).

- `selfhost/check.tn`: 28 lines. Nothing runs or imports it, and its own comment says "`tenonc check` does the same". Delete it, and fix the references in `CHECKER_NOTES.md:3,20`, `EMITTER_NOTES.md:19,36`, `SELFHOST.md:143` and the headers of `checker.tn:1` and `front.tn:1`.
- `selfhost/front.tn:73` `pub fn analyze`: no callers; the LSP uses `analyze_in`.
- `selfhost/json.tn:339` `Json.is_null`: unused.
- `examples/run/`: an empty, untracked directory. Remove it.
- Move `selfhost/checkfuzz.py` to `tools/`, because `selfhost/` holds compiler sources.
- About 45 `pub` functions are used only inside their own module; drop `pub` opportunistically.

### C2. `STATUS.md` is stale and `tools/status.py` has drifted. M, low risk. Done in 33cceb9 (STATUS.md regenerated in the commit after it, from a reduced evidence run: fuzz 200, mutate 15, checkfuzz 200, BENCH_RUNS=3, ASan, TSan, interp_diff).

- **Stale file:**
  - It was generated at `9fc4abb`, 23 commits ago, and reports check at 11.8 s against about 131 s measured cold.
  - The history entry `2026-10-27: 0.3s` is a failed run that was recorded anyway.
- **Generator drift, `tools/status.py`:**
  - The regex at `:33` (`(\d+) reject, (\d+) failed`) no longer matches tenonc's summary line (`195 reject, 10 lex/parse, 0 failed`). It silently picks up the bootstrap's line (100/154), so v2 is never counted.
  - The trusted base (`:43-48`) counts bootstrap Rust only. Programs are now compiled by tenonc, so the count should be `selfhost/{lexer,parser,front,checker,ck*,emit*,tenonc}.tn` + `runtime/tenon.h` + the prelude and std, with the bootstrap listed as the seed anchor.
  - The header says "Unmet goals (milestone 1)" (`:103`), with no milestone-2 section.
  - "Open regressions: None recorded" is hard-coded (`:101`).
  - `tools/unmet.md` is a hand-maintained section inside the "generated" file (tenon.md §3 calls for one generated status file). Move its content to `docs/log.md`, or into a milestone table that `status.py` reads.
- **Fix:** have `check` print a machine-readable summary line, which `status.py` parses.

### C3. One definition of the corpus and of parallelism. S, low risk. Done in f9523d2 and 2c71f64 (tools/corpus.py; testrun.tn WORKERS stays 8: the bootstrap-compiled driver has no core count).

- **Corpus:** `bootstrap lib tests programs selfhost bench study` is spelled out five times: `selfhost.sh:55`, `fixpoint.sh:41`, `fmt_check.sh:28`, `interp_diff.py:78` and `checkfuzz.py:15`. `bootstrap/` contains 0 `.tn` files. The `*/v2/*` exclusion is repeated in 7 files.
- **Parallelism:** the job count 8 is hard-coded in 7 places: `selfhost.sh`, `fixpoint.sh`, `fmt_check.sh`, `doctest.py`, `interp_diff.py`, `fuzz.py`, and `testrun.tn:27 WORKERS`. tenon.md §2.4 asks for one machine-wide slot pool, which does not exist.
- **Fix:** add `tools/corpus` (prints the file list, with `--no-v2`) and one `JOBS` default. The pool itself is a separate, small mechanism; propose it only if loop timing shows contention.

## Batch D: DRY inside the compiler (low risk, mostly S)

### D1. Path helpers: use the prelude's `path_join`, `path_parent` and `path_base` (`lib/prelude.tn:599-625`). S. (after concurrency lands, for `testrun` and `tenonc`)

- **Copies:**
  - `front.tn:42` `parent` and `:48` `pub join`. `join` is used 10× in `testrun.tn`, plus `tenonc.tn:114` and `tenonlsp.tn:38`.
  - `lspquery.tn:292` `join`.
  - `pkg.tn:69` `at`.
  - `testrun.tn:107` `split_path`.
- **Caution:** `front.parent("x")` returns `""` while `path_parent("x")` returns `"."`. Keep the `""` semantics at the module-lookup call site, or diagnostics change.

### D2. Hashes. S. (after concurrency lands, for `tenonc.tn`)

- `tenonc.tn:144` `hash_hex` and `pkg.tn:260` `hash_name` are the same loop with different seeds.
- `pkg.tn:239` `content_hash` is the same loop widened to 4 primes.
- **Fix:** keep one `hash_hex(s, k)` in `pkg.tn`, or a small `selfhost/hash.tn`. Changing a seed only renames cache entries.
- Do **not** change `content_hash`'s output: it is recorded in users' `tenon.lock`.

### D3. Lexer tables. S.

- `fmtlex.tn:16-29` copies `lexer.tn:19-29`, keywords and symbols; its own comment at `:15` admits it.
- `fmtlex.tn:31-33` and `lexer.tn:31-33` re-implement the prelude's `is_digit`, `is_alpha` and `is_alnum`.
- **Fix:** make `lexer.symbols` public and import both lists. The editor grammar check already derives its keywords from `lexer.tn` (`vscode_grammar_check.py:223`).
- The number and string scanning in `fmtlex.tn:71-166` is a second implementation, but `fmt.tn` cross-checks it against `lexer.tn`. Leave it.

### D4. Small duplicates. S.

- **Hex digit, five copies:** `testrun.tn:64`, `icodec.tn:199`, `lsppos.tn:138`, `json.tn:171` and `lexer.tn:180`. Use `Str.to_int_radix(16)` or `lexer.digit_value`.
- **Quoting:** `astdump.tn:21` `quote` is identical to `lexer.tn:394` `quoted`. `ival.tn:228` `quote` (21 lines) re-implements the runtime's string display.
- **The std module list** is a second copy of the bootstrap's `STD`: `front.tn:11` `std_modules()`. Derive it by listing `ROOT/lib/std/*.tn`.

### D5. Interpreter builtins are numbered by position. M, medium risk. (after concurrency lands; the concurrency builtins are being added here now)

- **Evidence:**
  - `ibuiltin.tn:14-25` `ext_names()`, `:28 FIRST_CAP = 58`, `:101-102` range tests (`id >= 15 and id < 38`).
  - `icap.tn` `id < 16 / < 23 / < 30` and arms `30 =>`…`35 =>`.
- One inserted name silently shifts every later id. `selfhost.sh:57-66` checks that every name exists, not the numbering.
- **Fix:** resolve by name once during lowering (`icode`) to a variant, or keep each id next to its name in one table. The C emitter already dispatches by name (`emitbi.tn:29`).

### D6. Long functions (tenon.md: none over ~80 lines without a stated reason). M, low risk.

- **The outlier:** `emitbi.tn:29` `extern_call`, 326 lines, which becomes 5727 lines of C. Split it by receiver (Str/List/Map/Option/Fs/Net/…) to mirror `ibuiltin`'s `str_op` and `icap`'s `fs_op`/`net_op`.
- **Others:**

| Function | Location | Lines |
|---|---|---|
| `Ck.expr_inner` | `ckinfer.tn:604` | 250 |
| `Walk.expr` | `cklin.tn:401` | 201 |
| `expr` | `emitbody.tn:529` | 164 |
| `Cx.expr` | `icode.tn:369` | 137 |
| `Env.declare_fns` | `ckenv.tn:678` | 115 |
| `Ck.stmt` | `ckinfer.tn:247` | 112 |
| `main` | `testrun.tn:173` | 110 |
| `ev_more` | `ieval.tn:468` | 107 |
| `call` | `ibuiltin.tn:99` | 102 |
| `Walk.stmt` | `cklin.tn:215` | 102 |
| `Parser.primary` | `parser.tn:871` | 100 |

- An expression-dispatch `match` is a fair "stated reason". Add a one-line reason to each one kept.
- **Split by file:**
  - `ckinfer.tn` (1231): patterns and calls into `ckcall.tn`.
  - `parser.tn` (1154): expressions into `parsexpr.tn`.
- **Share between interpreter and C runtime:** the trap message strings (about 15, copied between `runtime/tenon.h` and `ibuiltin.tn`/`ieval.tn`). Also reuse `ibuiltin.tn:61` `trap_oob` at `ieval.tn:216,651`. Format specs (`ival.tn:360-428` vs `tenon.h:519-606`) cannot be shared without a new extern, which the frozen bootstrap blocks; leave them.

### D7. Module headers and bootstrap framing. S, no risk. Headers: done in f9523d2 (the lists dropped); the "a port of" wording is not done.

- **Wrong `// module (imported by …)` headers:**
  - `lexer.tn:1` names `tokens.tn`, which does not exist.
  - `checker.tn:1` and `front.tn:1` name `check.tn`.
  - Also wrong: `parser.tn`, `json.tn`, `emitbi.tn`, `emitbody.tn`, `emittrait.tn`, `fmtlex.tn`.
- Either fix them or drop the lists, since import lines are the source of truth (DRY).
- 53 comments say "a port of `bootstrap/src/X.rs`". Reword them to "agrees with" where tenonc has since diverged (traits).

## Batch E: docs layout and accuracy

### E1. Docs restructure. M, low risk.

See the target structure below. Today:

- **Contributor notes live in `selfhost/`:** `SELFHOST.md` 144 lines, `CHECKER_NOTES.md` 134, `EMITTER_NOTES.md` 115. `EMITTER_NOTES.md:85-91` merely points to `SELFHOST.md`.
- **What `./check` runs** is described in `check:2-12`, twice in `SELFHOST.md` (`:86-99` and `:136-144`), in `log.md:341` and in `CHECKER_NOTES.md:85`.
- **The subcommand list** appears in 6 places, already out of sync (B2).

### E2. User docs say `tenon` (the bootstrap) where tenonc is meant. S.

- `reference.md:27-30,192` say `tenon run` and `tenon build`; `:976` and `:767` say "tenonc only".
- `tenon.md:247` says `tenon fmt`.
- `quickstart.md` never says how to run a program.
- B1 makes all of these true by renaming the binary.

### E3. `reference.md` is over 1000 lines. S.

- Move §16 Formatting (`:928-972`) and the CLI and cache text (`:27-32`) to `docs/tools.md`.
- Shrink the package paragraph in §13 (`:767-783`, which duplicates `packages.md`) to a link.
- Update §18 "Not yet implemented" when concurrency lands.

### E4. Stale facts. S.

- `CHECKER_NOTES.md:80` mentions `tests/pending/`, which does not exist.
- `SELFHOST.md:88` says the suite runs `tests`; it runs `tests tests/v2`.
- Check time is given three ways: `SELFHOST.md:103` (~30 s), `unmet.md` (~9 s) and `STATUS.md` (11.8 s).
- `unmet.md:3-5` program list omits `chat`.
- `log.md:394` says "10 programs" in `tests/v2/run`; there are 12.
- `SELFHOST.md:72-84` keeps a "known difference" that 25f3385 fixed.
- The README layout omits `tests/fmt`, `tests/lsp`, `target/`, `check` and `.evidence/`.
- `check:4-5` documents `--fast`, but the script ignores its argument. Either say so in the usage text or remove the flag everywhere.

### E5. `docs/log.md`. S.

- Missing entries for the formatter, the language server and VS Code.
- Headings are out of order: `:267` "10-28/29" comes before four later "10-28" entries.
- The traits entry has no measured effect.
- **Fix:** add the entries; from now on use a sequence number with each date.

## Batch F: the v1/v2 split and the bootstrap's remaining role (needs one product decision)

### F1. Keep `lib/v2` for now. It is required, not cosmetic.

The bootstrap compiles `lib/prelude.tn` into everything it builds (`include_str!`, `bootstrap/src/main.rs:26`), and it builds stage1. A trait in `lib/prelude.tn` would break the seed.

### F2. Fold `tests/v2` into `tests`. M, low risk. After A1, and after concurrency lands, since the concurrency tests are being added now.

- Once the bootstrap's `tenon test` has left `check`, only the cross-check scripts need to know which files are tenonc-only.
- Mark those files with a first-line directive (`// tenonc-only`), read by the corpus lister from C3. That replaces the `*/v2/*` path rule in 7 files.
- Merge the directory roles as well:
  - `tests/v2/lex` and `tests/v2/parse` have goldens.
  - `tests/lex` and `tests/parse` are compared only against the bootstrap.
  - Bless goldens for the old ones too, so all lex/parse tests run under `tenonc test`.

### F3. `tests/selfhost/` (221 checker cases) has no expectations. M, low risk.

- These cases are only compared with the bootstrap (`selfhost.sh`). If the bootstrap ever leaves the loop, they guard nothing.
- **Fix:** convert them to `tests/reject` files with `// error:` lines, generated once from current output. They then become guarded tests (`governance/guarded.txt`).

### F4. Product decision for the user: the seed's long-term form. L.

- **(a) Keep the Rust seed as is (recommended for now).**
  - Costs 10.4k frozen lines, an embedded live prelude, and the `v2/` split forever.
  - The bootstrap's interpreter, test runner and `astdump` (about 1.5k lines) could be deleted with approval if A1 and C0 stop using them. That shrinks the seed, which is the allowed direction.
- **(b) Replace the seed with a checked-in, generated `seed/tenonc.c`, regenerated at milestones, as Zig does.**
  - Removes Rust and the v1/v2 split entirely.
  - Costs a 4.9 MB generated artifact in git, and losing the independent second implementation, which is the cross-check.
- **(c) Pin a seed prelude copy inside `bootstrap/`.**
  - Needs one approved bootstrap change.
  - Frees `lib/prelude.tn` to use traits.

## Batch G: hygiene (S, no risk)

- `.gitignore` covers `target`, `.evidence`, `bench/out` and `.check.log`; no generated artifacts are committed outside `study/`.
- The large tracked files are all in `study/` (largest 11.6 MB). Leave them: published evidence.
- The root `Cargo.toml` is a one-member workspace. Leave it: the root layout is fine and moving it buys nothing.
- `tools/fmt_skip.txt` exempts 262 files. Most are legitimate (study, malformed inputs, guarded tests). Re-check after F2 and F3: guarded tests could be formatted with one approval entry, so that "the whole corpus formatted" (tenon.md §5) is true except for intentional inputs.
- Add the reason "single header by design (tenon.md §2.6)" to `runtime/tenon.h`. (after concurrency lands)

## Proposed target structure

### CLI

```
target/tenon            one self-hosted binary (selfhost/tenon.tn)
  tenon run FILE [ARGS]     tenon build FILE [-o OUT] [-O0]   tenon emit FILE
  tenon check FILE          tenon test [DIR...] [--bless]     tenon fetch [DIR]
  tenon fmt [--check] FILE...|-                               tenon lsp
  tenon tokens FILE         tenon ast FILE                    tenon --help
  common flags anywhere: --root DIR (else $TENON_ROOT, else the binary's repo)
  exit codes: 0 ok, 1 diagnostic/test failure, 2 usage/I-O, 70/72 traps
target/release/tenon    the frozen Rust seed (scripts call it $SEED); builds stage1 only
```

### Docs

```
README.md                what it is, install (build target/tenon), 5-line tour, layout
docs/quickstart.md       user: first program, run/build/test
docs/reference.md        user: the language only (< 1000 lines)
docs/tools.md            user: the CLI table above, env vars, cache, fmt rules, LSP/VS Code
docs/packages.md         user: tenon.toml, tenon.lock
docs/dev/compiler.md     contributor: SELFHOST + CHECKER_NOTES + EMITTER_NOTES merged
                         (module tables, fidelity rules, known differences)
docs/dev/testing.md      contributor: the one description of ./check, evidence and test dirs
docs/log.md              iteration log (append-only, numbered entries)
governance/README.md     unchanged
STATUS.md                generated only; unmet goals per milestone come from a data file
```

## Suggested order

1. A1, A2, A3 (timing lines), C1, D7, E4: one small landing that restores the budget headroom and removes dead weight.
2. C3, then A4, then C0, then C2.
3. D1-D4.
4. After concurrency lands: B1-B4, then E1-E3 (docs follow the CLI), then D5, D6, F2, F3.
5. F4: put it to the user as a batched question with recommendation (a).

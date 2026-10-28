# Testing, gates and evidence

Contributor notes: what `./check` runs, where the tests live, how to add
one, and what the slower evidence loop measures. How the compiler itself is
built is in [compiler.md](compiler.md); the user reference of `tenon` is
[docs/tools.md](../tools.md).

## Two loops

| Loop | Command | Budget (tenon.md §4, §5) | Who runs it |
|---|---|---|---|
| the gate | `./check` (`--fast` is accepted and means the same) | 60 s | every landing (`ops/repo/land.sh`), CI on Linux and macOS (`.github/workflows/ci.yml`) |
| landing | `ops/repo/land.sh "MESSAGE" [NEW_PATH...]` | 5 min | everyone at a machine; unattended agents land through pull requests that merge when CI passes ([automation.md](automation.md)) |
| evidence | `ops/evidence/evidence.sh` | none (asynchronous) | nightly on GitHub (`.github/workflows/nightly.yml`, [automation.md](automation.md)); locally in a dedicated clone (`$EVIDENCE_DIR`, default `~/.tenon-evidence`) |

The current time of each step is printed at the end of every `./check` and
recorded in [STATUS.md](../../STATUS.md) ("Loops"), which is generated
(`python3 ops/repo/status.py`); no other document gives the numbers.

## What `./check` runs

In this order; the first failure stops it and prints the table of times so
far. The binaries are passed to the tools as `$SEED`, `$TENON0` and
`$TENON` (`ops/corpus.py`).

| Step | What it checks |
|---|---|
| `cargo build --release` | the frozen seed, `target/release/tenon-seed` (`seed/`) |
| stage 0 | the seed builds `compiler/tenon.tn` with `-O0` into `target/tenon0` |
| stage 1 | stage 0 builds it at `-O2`, in parallel translation units, into `target/tenon`: the `tenon` every later step runs |
| `tenon test tests tests/v2` | every run test on both backends against its golden output, every reject test, the v2 lex/parse goldens (below) |
| `ops/gates/cli_test.sh` | usage text and exit statuses, flags in any position, `run` passing flags through, `ops/repo/install.sh` into a scratch prefix; that docs/tools.md shows the `tenon help` text word for word |
| `ops/gates/doctest.py` | every ` ```tenon ` block with `fn main` in README.md and docs/*.md compiles |
| `ops/gates/doclinks.tn` (run by `tenon run`) | every relative link and repository path in README.md and docs/**/*.md exists (below) |
| `ops/gates/vscode_grammar_check.py` | the VS Code grammar names the lexer's keywords and tokenizes the whole corpus without leaks |
| `ops/gates/programs.sh` | each real program's scenario (`programs/NAME/test.sh`) on the interpreter and the native build: both transcripts equal `expected.txt` |
| `ops/gates/cache_test.sh` | the build cache: hits only on identical C; `TENON_CACHE=off` and `TENON_KEEP_C` bypass it |
| `ops/gates/pkg_test.sh` | packages: fetch, lock, offline builds, stale or missing locks, a tampered cache, the error cases |
| `ops/gates/selfhost.sh` | the cross-check with the seed and the fixpoint (below) |
| `ops/gates/fmt_check.sh` | the corpus is formatted (except `ops/gates/fmt_skip.txt`), formatting is idempotent and keeps the syntax tree, the `tests/fmt` goldens |
| `ops/gates/lsp_test.py` | scripted language-server sessions on `tests/lsp` and `tests/v2/lsp`, the JSON tests, the VS Code client (with node) |
| `ops/gates/approvals_test.sh` | the approvals checker refuses real weakenings and changes to the frozen seed |

`ops/repo/land.sh` also runs `python3 ops/repo/approvals.py origin/main` before
the check (ops/governance/README.md); CI runs `ops/repo/approvals.py --pr` on pull
requests (automation.md).

### The cross-check and the fixpoint

`ops/gates/selfhost.sh` makes one parallel pass over the corpus. For every file
outside a `v2/` directory (the seed cannot read those), the seed and stage 1
must agree on `tokens` and `ast` (byte for byte), on `check` (the exit status
and the first line of the diagnostic), and, for every file the seed accepts,
on `emit` (byte-identical C). For every file stage 1 accepts, v2 included,
stage 0 and stage 1 must emit identical C: the fixpoint, which covers
`compiler/tenon.tn` itself. It also fails when the prelude has an
`extern fn` the interpreter does not know (a builtin added to the seed must
be added to the interpreter too). Disagreements are listed in compiler.md
("Known disagreements"); there are none.

## The corpus

The corpus is every `.tn` file under `lib`, `tests`, `programs`, `compiler`,
`bench` and `evidence/study` (`ops/corpus.py`; `--no-v2` leaves out files under a
`v2/` directory). The tools that read "the corpus" (selfhost.sh, fmt_check,
the grammar check, interp_diff, checkfuzz) all take it from there.

| Directory | What a file there is |
|---|---|
| `tests/run/` | a program; `NAME.out` holds its standard output, then `exit: N`, then each standard-error line as `stderr: LINE`; both backends must print it |
| `tests/reject/` | a program that must be rejected; its first line `// error: TEXT` is a substring of the expected diagnostic |
| `tests/lex/`, `tests/parse/` | malformed or tricky input, compared with the seed only (selfhost.sh) |
| `tests/selfhost/` | checker cases (one diagnostic each, or accepted tricky programs), compared with the seed only; `ckmod*.tn`, `ckbad*.tn`, `ckcycle.tn` and `ckmissingdep.tn` are modules imported by the `mod_*` cases |
| `tests/fmt/` | `NAME.in.tn` must format to `NAME.out.tn` |
| `tests/lsp/` | fixtures of `ops/gates/lsp_test.py` |
| `tests/redteam/` | red-team findings (`FINDINGS.md`) and their reproductions (`repros/`) |
| `tests/v2/` | the same roles (`run`, `reject`, `lex`, `parse`, `fmt`, `lsp`) for what only `tenon` understands (traits, workers) or where it deliberately differs from the frozen seed (a rule or a fix added after the seed froze, which the seed's checker or interpreter does not have: it would fail the cross-check or `ops/evidence/interp_diff.py`); `lex/NAME.tokens` and `parse/NAME.ast` are goldens of `tenon tokens` / `tenon ast` |
| `programs/NAME/` | a real program `NAME.tn`, its scenario `test.sh` (runs `$RUN`) and `expected.txt`; `programs/v2/` for those with workers |
| `bench/NAME/` | a benchmark in Tenon, C, Rust, Python and TypeScript (`ops/evidence/bench.py`); `bench/v2/` the parallel ones |

A run test may start with `// stdin: TEXT` (`\n` and `\xHH` escapes) and
`// args: A B C`; a file whose first line is `// module` is imported by
other tests and not run itself (docs/tools.md, `tenon test`).

## Adding a test

1. Write the program: `tests/run/NAME.tn`, or `tests/v2/run/NAME.tn` if it
   uses traits or workers, or if the seed behaves differently (the table above).
2. `target/tenon test tests --bless` (or `tests/v2`) writes the missing
   golden file `tests/run/NAME.out`. Read it: blessing records whatever the
   program printed.
3. `target/tenon test tests tests/v2` must pass; then land with
   `ops/repo/land.sh "MESSAGE" tests/run/NAME.tn tests/run/NAME.out` (new files
   are committed only when named).

A reject test needs no golden file: its first line is `// error: TEXT`. A
program scenario is blessed with `ops/gates/programs.sh --bless`; a formatter
golden is written by hand (`tests/fmt/NAME.in.tn`, `NAME.out.tn`). If a new
file is deliberately unformatted or unparsable, list it in
`ops/gates/fmt_skip.txt`.

## Guarded tests and approvals

The tests listed in `ops/governance/guarded.txt` (reject tests, trap tests,
capability probes, linear-type tests) carry the language's guarantees.
Deleting one, changing its `// error:` line or its golden output needs an
approval line in `ops/governance/approvals.log` in the same change, and so does
any change to the frozen seed (`seed/`), whose line count may only
shrink. `ops/repo/approvals.py` enforces this on every landing; the rules are
in [ops/governance/README.md](../../ops/governance/README.md).

## Doc checks

- `ops/gates/doctest.py [DOC...]`: whole programs in the user docs compile.
  A ` ```tenon-error ` block is a deliberate error example and is skipped;
  blocks without `fn main` are fragments.
- `ops/gates/doclinks.tn`: the docs name only paths that exist. It reads
  README.md and docs/**/*.md outside fenced code blocks and checks every
  relative link `[text](path)` (relative to the document) and every word
  with a `/` whose first component is a top-level entry of the repository
  (`compiler/tenon.tn`, `lib/prelude.tn:26`), in backticks or not. Globs
  (`tests/v2/run/workers_*.tn`) and placeholders (`programs/NAME/test.sh`)
  must match something. Exceptions, each with its reason, are in
  `ops/gates/doclinks_ignore.txt`: dated records (docs/log.md, the cleanup
  plan) and paths inside a study kit.
- `ops/gates/cli_test.sh` compares the usage text in docs/tools.md with
  `tenon help`.

## The evidence loop

`ops/evidence/evidence.sh` resets its clone to `origin/main`, builds as `./check`
does, and runs, each writing `.evidence/NAME.json` (`corpus.record`):

| Tool | Measures |
|---|---|
| `ops/evidence/fuzz.py N SEED` | random well-typed programs on both backends, the seed's interpreter as a third opinion |
| `ops/evidence/asan.sh` | every run test and the programs with a `sanitizer.args`, built with AddressSanitizer and UBSan |
| `ops/evidence/tsan.sh` | the programs with workers under ThreadSanitizer, several runs each |
| `ops/gates/fmt_check.sh --all` | meaning preserved on every file, not only the ones formatting changes |
| `tenon-seed test tests` | the seed's own run of the v1 suite (a reference for its interpreter) |
| `ops/evidence/interp_diff.py` | the seed's interpreter and `tenon run` on every corpus file: the same output, errors and exit status |
| `ops/evidence/checkfuzz.py N SEED` | token-level mutants of corpus programs: both checkers print the same first line, accepted mutants emit the same C (disagreements in `.evidence/checkfuzz/`) |
| `ops/evidence/mutate.py N SEED` | mutants of the trusted compile path and the runtime; survivors (the tests did not notice) become tasks |
| `ops/evidence/bench.py` | the benchmarks against C, Rust, Python and TypeScript (`--parallel`: the worker speedups) |

Each tool's whole output is kept in `.evidence/NAME.log`. The sizes come
from `FUZZ_N`, `CHECKFUZZ_N`, `MUTATE_N` and `BENCH_RUNS` (the nightly run
uses smaller ones). Then `ops/repo/status.py` regenerates STATUS.md from that
data (the only way it changes; the hand-written notes come from
`ops/repo/unmet.md`), appends the run to `.evidence/history.jsonl` (STATUS.md,
"Correctness over time"), writes the open regressions with stable keys to
`.evidence/regressions.json` (the nightly run keeps one issue per key), and
the result is landed with `ops/repo/land.sh` (`EVIDENCE_LAND=0`: not landed;
the nightly run opens a pull request instead).

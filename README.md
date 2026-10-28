# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. See [`tenon.md`](tenon.md) for the goals, [`docs/reference.md`](docs/reference.md)
for the language, [`STATUS.md`](STATUS.md) for measured results, and
[`docs/log.md`](docs/log.md) for decisions.
Editor support: [`editors/vscode`](editors/vscode) (VS Code syntax highlighting).

```sh
./check --fast                 # build + full differential test corpus (budget: 60 s)
target/tenonc run  prog.tn [args]    # reference interpreter (TENON_ROOT=. or --root)
target/tenonc build prog.tn -o prog  # native executable via C
```

`target/tenonc` is the self-hosted compiler (selfhost/tenonc.tn), built by
./check in two stages: the bootstrap builds it with -O0
(`target/release/tenon build selfhost/tenonc.tn -o target/tenonc0 -O0`), and
that builds the final one (`target/tenonc0 build selfhost/tenonc.tn -o
target/tenonc`, with TENON_ROOT=.). It has every subcommand of the bootstrap's `tenon` (run,
build, emit, check, test, tokens, ast; selfhost/SELFHOST.md). The Rust
bootstrap is a frozen seed: changing it needs an approvals entry and its line
count may only shrink (governance/README.md). New language features exist
only in tenonc (traits, docs/reference.md §17; workers and channels, §18); code that uses them lives
under a `v2/` directory (lib/v2, tests/v2), which the tools comparing tenonc
with the bootstrap skip.

## Layout

```
bootstrap/    the Rust bootstrap compiler and reference interpreter (Cargo package): a frozen seed
lib/          prelude.tn (the builtin API, in Tenon), std/ (standard modules), v2/prelude.tn (tenonc-only: traits, workers)
runtime/      tenon.h, the C runtime every native build includes
selfhost/     the compiler written in Tenon (tenonc: checker, C backend, interpreter, test runner), cross-checked against bootstrap/
tests/        run/ reject/ lex/ parse/ selfhost/ corpus; redteam/ findings and repros; v2/ (tenonc-only)
programs/     real programs with scenario tests (tools/programs.sh); v2/ (tenonc-only: scan, with workers)
bench/        benchmarks against C, Rust, Python, TypeScript (tools/bench.py); v2/ parallel ones (--parallel)
docs/         reference, quickstart, packages, decision log
editors/      editor support: vscode/ (syntax highlighting, no build step)
governance/   guarded tests and the append-only approvals log
tools/        landing, evidence, study and status tooling
study/        usability study: tasks, hidden tests, published results
```

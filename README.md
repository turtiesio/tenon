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
./check with the bootstrap (`target/release/tenon build selfhost/tenonc.tn -o
target/tenonc`). It has every subcommand of the bootstrap's `tenon` (run,
build, emit, check, test, tokens, ast; selfhost/SELFHOST.md). The Rust
bootstrap is a frozen seed: changing it needs an approvals entry and its line
count may only shrink (governance/README.md).

## Layout

```
bootstrap/    the Rust bootstrap compiler and reference interpreter (Cargo package): a frozen seed
lib/          prelude.tn (the builtin API, in Tenon) and std/ (standard modules)
runtime/      tenon.h, the C runtime every native build includes
selfhost/     the compiler written in Tenon (tenonc: checker, C backend, interpreter, test runner), cross-checked against bootstrap/
tests/        run/ reject/ lex/ parse/ selfhost/ corpus; redteam/ findings and repros
programs/     real programs with scenario tests (tools/programs.sh)
bench/        benchmarks against C, Rust, Python, TypeScript (tools/bench.py)
docs/         reference, quickstart, packages, decision log
editors/      editor support: vscode/ (syntax highlighting, no build step)
governance/   guarded tests and the append-only approvals log
tools/        landing, evidence, study and status tooling
study/        usability study: tasks, hidden tests, published results
```

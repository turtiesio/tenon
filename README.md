# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. See [`tenon.md`](tenon.md) for the goals, [`docs/reference.md`](docs/reference.md)
for the language, [`STATUS.md`](STATUS.md) for measured results, and
[`docs/log.md`](docs/log.md) for decisions.
Editor support: [`editors/vscode`](editors/vscode) (VS Code syntax highlighting).

```sh
./check --fast                 # build + full differential test corpus (budget: 60 s)
target/release/tenon run  prog.tn [args]    # reference interpreter
target/release/tenon build prog.tn -o prog  # native executable via C
```

## Layout

```
bootstrap/    the Rust bootstrap compiler and reference interpreter (Cargo package)
lib/          prelude.tn (the builtin API, in Tenon) and std/ (standard modules)
runtime/      tenon.h, the C runtime every native build includes
selfhost/     the compiler front end written in Tenon, cross-checked against bootstrap/
tests/        run/ reject/ lex/ parse/ selfhost/ corpus; redteam/ findings and repros
programs/     real programs with scenario tests (tools/programs.sh)
bench/        benchmarks against C, Rust, Python, TypeScript (tools/bench.py)
docs/         reference, quickstart, decision log
editors/      editor support: vscode/ (syntax highlighting, no build step)
governance/   guarded tests and the append-only approvals log
tools/        landing, evidence, study and status tooling
study/        usability study: tasks, hidden tests, published results
```

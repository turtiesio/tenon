# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. See [`tenon.md`](tenon.md) for the goals, [`docs/reference.md`](docs/reference.md)
for the language, [`STATUS.md`](STATUS.md) for measured results, and
[`docs/log.md`](docs/log.md) for decisions.
Editor support: [`editors/vscode`](editors/vscode) (VS Code syntax highlighting
and a client for `tenon lsp`). The command line: [`docs/tools.md`](docs/tools.md)
(every command, flag, environment variable and exit status).

```sh
./check --fast                     # build + full differential test corpus (budget: 60 s)
target/tenon run prog.tn [args]    # reference interpreter
target/tenon build prog.tn -o prog # native executable via C
target/tenon test tests tests/v2   # the test corpus, both backends
target/tenon fmt --check prog.tn   # formatter (and: check emit lsp fetch tokens ast; target/tenon help)
tools/install.sh                   # install tenon into ~/.local/bin (its lib/ and runtime/ in ~/.local/lib/tenon)
```

`tenon` is one self-hosted executable (selfhost/tenon.tn, written in Tenon)
with the subcommands run, build, emit, check, test, fmt, lsp, fetch, tokens
and ast. It finds the prelude, standard library and C runtime from its own
path, so no TENON_ROOT is needed (docs/tools.md). ./check builds it in two
stages: the frozen Rust seed builds stage 0 (`target/release/tenon-seed build
selfhost/tenon.tn -o target/tenon0 -O0`), and stage 0 builds the final one
(`target/tenon0 build selfhost/tenon.tn -o target/tenon`). The seed only
builds stage 0. It stays Rust, changing it needs an approvals entry, and its
line count may only shrink (governance/README.md). New language features
exist only in `tenon` (traits, docs/reference.md §17; workers and channels,
§18). Code that uses them lives under a `v2/` directory (lib/v2, tests/v2),
which the tools comparing `tenon` with the seed skip.

## Layout

```
bootstrap/    the Rust bootstrap compiler (Cargo package tenon-seed): a frozen seed that builds stage 0
lib/          prelude.tn (the builtin API, in Tenon), std/ (standard modules), v2/prelude.tn (traits, workers: not in the seed)
runtime/      tenon.h, the C runtime every native build includes
selfhost/     tenon, written in Tenon (checker, C backend, interpreter, test runner, formatter, language server, packages), cross-checked against bootstrap/
tests/        run/ reject/ lex/ parse/ selfhost/ corpus; redteam/ findings and repros; v2/ (not in the seed)
programs/     real programs with scenario tests (tools/programs.sh); v2/ (scan, with workers)
bench/        benchmarks against C, Rust, Python, TypeScript (tools/bench.py); v2/ parallel ones (--parallel)
docs/         reference, quickstart, tools (the command line), packages, decision log
editors/      editor support: vscode/ (syntax highlighting and a language-server client, no build step)
governance/   guarded tests and the append-only approvals log
tools/        install, landing, evidence, study and status tooling
study/        usability study: tasks, hidden tests, published results
```

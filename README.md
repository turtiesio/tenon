# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. [`tenon.md`](tenon.md) states the goals, [`STATUS.md`](STATUS.md)
the measured results (generated), and [`docs/log.md`](docs/log.md) the decisions.

## Using it

```sh
tools/install.sh                   # build tenon; install it into ~/.local/bin (its lib/ and runtime/ in ~/.local/lib/tenon)
tenon run prog.tn [args]           # the reference interpreter
tenon build prog.tn -o prog        # a native executable, through C
tenon test DIR                     # the tests in DIR/run and DIR/reject, on both backends
tenon fmt --check prog.tn          # the formatter; also check, emit, lsp, fetch, tokens, ast (tenon help)
```

- [docs/quickstart.md](docs/quickstart.md): a first program, and a translation table from Python and TypeScript.
- [docs/reference.md](docs/reference.md): the language.
- [docs/library.md](docs/library.md): the builtin API and the standard library.
- [docs/tools.md](docs/tools.md): every command, flag, environment variable and exit status of `tenon`; the formatter's rules; the language server and the VS Code extension ([editors/vscode](editors/vscode)).
- [docs/packages.md](docs/packages.md): `tenon.toml`, `tenon.lock`, dependencies.

## Working on it

```sh
./check                            # the gate: build, the whole test corpus on both backends, the cross-checks (budget: 60 s)
tools/land.sh "message" [NEW_PATH...]   # commit, rebase, pass ./check, push: the way to main (agents: pull requests)
```

`tenon` is one self-hosted executable, written in Tenon (`selfhost/`).
`./check` builds it in two stages: the frozen Rust seed
(`target/release/tenon-seed`) builds stage 0 (`target/tenon0`), and stage 0
builds `target/tenon`. The seed only builds stage 0; changing it needs an
approvals entry, and its line count may only shrink
([governance/README.md](governance/README.md)). Features the seed does not
have (traits, workers) are used only under `v2/` directories.

- [docs/dev/compiler.md](docs/dev/compiler.md): how the compiler, the interpreter and the test runner are built, and what keeps them identical to the seed.
- [docs/dev/testing.md](docs/dev/testing.md): what `./check` runs, the test directories, adding a test, guarded tests, the evidence loop.
- [docs/dev/automation.md](docs/dev/automation.md): what runs unattended on GitHub (nightly evidence, the weekly reviews, the fixer), the issue queue, and how agents' pull requests are guarded.
- [docs/dev/cleanup_plan.md](docs/dev/cleanup_plan.md): the cleanup audit and its batches.

## Layout

```
check         the gate (docs/dev/testing.md)
bootstrap/    the frozen Rust seed (Cargo package tenon-seed): builds stage 0 only
selfhost/     tenon, written in Tenon: checker, C backend, interpreter, test runner, formatter, language server, packages
lib/          prelude.tn (the builtin API, in Tenon), std/ (standard modules), v2/prelude.tn (traits, workers)
runtime/      tenon.h, the C runtime every native build includes
tests/        run/ reject/ (both backends), lex/ parse/ selfhost/ (against the seed), fmt/ lsp/ (tool fixtures), redteam/, v2/
programs/     real programs with scenario tests (tools/programs.sh); v2/ (scan, with workers)
bench/        benchmarks against C, Rust, Python, TypeScript (tools/bench.py); v2/ parallel ones
docs/         user docs (quickstart, reference, library, tools, packages), the decision log; dev/ for contributors
editors/      vscode/: syntax highlighting and a language-server client, no build step
governance/   guarded tests and the append-only approvals log
.github/      workflows/: CI, the nightly evidence run, the agent runs; agents/: their briefs (docs/dev/automation.md)
tools/        install, landing, the check's tools, evidence, study and status tooling
study/        usability study: tasks, hidden tests, published results
target/       built by ./check (not committed): tenon, tenon0, release/tenon-seed
.evidence/    written by tools/evidence.sh (not committed), read by tools/status.py
```

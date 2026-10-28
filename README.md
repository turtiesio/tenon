# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. [`tenon.md`](tenon.md) states the goals, [`STATUS.md`](STATUS.md)
the measured results (generated), and [`docs/log.md`](docs/log.md) the decisions.

## Using it

```sh
ops/repo/install.sh                   # build tenon; install it into ~/.local/bin (its lib/ and runtime/ in ~/.local/lib/tenon)
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
ops/repo/land.sh "message" [NEW_PATH...]   # commit, rebase, pass ./check, push: the way to main (agents: pull requests)
```

`tenon` is one self-hosted executable, written in Tenon (`compiler/`).
`./check` builds it in two stages: the frozen Rust seed
(`target/release/tenon-seed`) builds stage 0 (`target/tenon0`), and stage 0
builds `target/tenon`. The seed only builds stage 0; changing it needs an
approvals entry, and its line count may only shrink
([ops/governance/README.md](ops/governance/README.md)). Features the seed does not
have (traits, workers) are used only under `v2/` directories.

- [docs/dev/compiler.md](docs/dev/compiler.md): how the compiler, the interpreter and the test runner are built, and what keeps them identical to the seed.
- [docs/dev/testing.md](docs/dev/testing.md): what `./check` runs, the test directories, adding a test, guarded tests, the evidence loop.
- [docs/dev/automation.md](docs/dev/automation.md): what runs unattended on GitHub (nightly evidence, the weekly reviews, the fixer), the issue queue, and how agents' pull requests are guarded.
- [docs/dev/cleanup_plan.md](docs/dev/cleanup_plan.md): the cleanup audit and its batches.
- [formal/README.md](formal/README.md): Tenon Core in Lean 4: capability safety, obligation soundness and worker isolation proved; the core's evaluator run against `tenon run` on the corpus.

## Layout

```
check         the gate (docs/dev/testing.md): the one entry point
compiler/     tenon, written in Tenon: front end (lexer, parser, astdump, checker and ck*.tn, front.tn), C backend
              (emit*.tn), interpreter (interp.tn, i*.tn), test runner, formatter (fmt*.tn), language server (lsp*.tn,
              json.tn), packages (pkg*.tn); the command line is tenon.tn. One flat directory: the seed resolves
              `import name` only next to the importing file (docs/dev/compiler.md)
seed/         the frozen Rust seed (Cargo package tenon-seed): builds stage 0 only
Cargo.toml    the Cargo workspace whose one member is seed/ (and its Cargo.lock)
lib/          prelude.tn (the builtin API, in Tenon), std/ (standard modules), v2/prelude.tn (traits, workers)
runtime/      tenon.h, the C runtime every native build includes
tests/        run/ reject/ (both backends), lex/ parse/ selfhost/ (against the seed), fmt/ lsp/ (tool fixtures), redteam/, v2/
programs/     real programs with scenario tests (ops/gates/programs.sh); v2/ (scan, with workers)
bench/        benchmarks against C, Rust, Python, TypeScript (ops/evidence/bench.py; rules: bench/README.md); v2/ parallel ones
docs/         user docs (quickstart, reference, library, tools, packages), the decision log; dev/ for contributors
formal/       the formal track in Lean 4 (formal/README.md): the core calculus, its evaluator, the proofs, the translator
editors/      vscode/: syntax highlighting and a language-server client, no build step
ops/          the process, in one place (tenon.md §6); corpus.py: the corpus and the binaries, for every tool
  gates/        the steps of ./check, with the lists they read (fmt_skip.txt, doclinks_ignore.txt)
  evidence/     the evidence loop (evidence.sh): fuzzing, sanitizers, mutation testing, benchmarks
  repo/         landing (land.sh), the approvals checker, STATUS.md (status.py, unmet.md), install.sh, GitHub (gh.py)
  study/        study.py: usability-study kits and their scoring
  governance/   guarded tests, frozen and owner paths, the append-only approvals log
  agents/       the briefs of the unattended agents (docs/dev/automation.md)
evidence/     study/: the usability study as published (tasks, hidden tests, results)
.github/      workflows/: CI, the nightly evidence run, the agent runs (docs/dev/automation.md)
target/       built by ./check (not committed): tenon, tenon0, release/tenon-seed; check.log (ops/repo/land.sh)
.evidence/    written by ops/evidence/evidence.sh (not committed), read by ops/repo/status.py
```

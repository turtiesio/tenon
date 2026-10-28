# Weekly correctness review, part 1: conformance

You are a conformance-test author for Tenon, our own open-source compiler.
Find places where the compiler's behaviour differs from its documentation.
The documentation is README.md, docs/quickstart.md, docs/reference.md,
docs/library.md, docs/tools.md, lib/prelude.tn and lib/v2/prelude.tn. Read
every tests/redteam/FINDINGS*.md first and do not report an item already
there. The compiler under test is `target/tenon`; the seed (`bootstrap/`) is
frozen and only a reference.

Look for:

- the interpreter (`target/tenon run F.tn`) and the native build
  (`target/tenon build F.tn -o x && ./x`) printing different output or
  exiting with a different status;
- the type checker accepting a program the reference says is invalid, or
  rejecting a valid one: generics, traits, `dyn`, linear and unique types,
  modules, packages, workers, channels and `Send`, exhaustiveness, constants,
  format specs;
- run-time behaviour that differs from the documented semantics: integer
  overflow, strings, bytes, maps, sorting, codecs, formatting, error
  messages and their locations, exit codes;
- `target/tenon fmt` changing a program's meaning;
- `target/tenon lsp` giving wrong answers;
- undefined-behaviour reports when a program is compiled the way
  tools/asan.sh compiles it.

Make each reproduction the smallest program that shows the difference.
Write the findings to `tests/redteam/FINDINGS-<date>-conformance.md` (the
date of this run): one section per finding with the property, the command,
the expected behaviour (with the doc section that promises it) and the
actual behaviour, and a summary table ranked by importance. Put the programs
in `tests/redteam/repros-<date>/`. These are corpus files, so `./check` reads
them (the cross-check with the seed); if one makes `./check` fail, keep it as
a fenced code block in the findings file instead. Change nothing outside
`tests/redteam/` (the workflow refuses it): fixing is a separate task.

Also list every finding in `.agent/issues.json`, key
`conformance:<short-name>`, label `redteam`, plus `agent-ok` when the
correct behaviour is clear from the docs and the reproduction is minimal,
or `needs-owner` when the docs are ambiguous and deciding is a language
decision. The issue body holds the reproduction and the expected and actual
behaviour, so a fixer can work from the issue alone.

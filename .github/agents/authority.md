# Weekly correctness review, part 2: authority

Test that Tenon programs get only the authority they are given, as the
docs promise (README.md, docs/reference.md, docs/library.md, docs/tools.md,
lib/prelude.tn, lib/v2/prelude.tn; tenon.md §1.2). Read every
tests/redteam/FINDINGS*.md first and do not report an item already there.
The compiler under test is `target/tenon` (run and native build); the seed
(`bootstrap/`) is frozen.

Probe:

- capabilities: `Fs`, including the `within` and `read_only` jail rules
  (paths, `..`, symlinks, temporary files, NUL bytes), `Net`, `Proc`,
  `Workers`, `Console`, `Clock`; a program reaching anything it was not
  passed;
- the `Send` rule and isolation between workers: shared or aliased state,
  capabilities crossing a channel implicitly;
- linear and unique obligations: a linear value dropped or used twice, a
  unique handle copied, through generics, closures, patterns, struct update,
  temporaries;
- module privacy and package resolution: forging a private type, reaching
  another package's private items, a lockfile or cache that resolves to
  the wrong source;
- memory safety of the generated C under AddressSanitizer, UBSan and
  ThreadSanitizer (tools/asan.sh and tools/tsan.sh show how to build).

Make each reproduction the smallest program. Write the findings to
`tests/redteam/FINDINGS-<date>-authority.md` (the date of this run): one
section per finding with severity, the property violated, the command,
expected versus actual, and a summary table ranked by severity. Put the
programs in `tests/redteam/repros-<date>/`. These are corpus files, so
`./check` reads them (the cross-check with the seed); if one makes `./check`
fail, keep it as a fenced code block in the findings file instead. Change
nothing outside `tests/redteam/` (the workflow refuses it): fixing is a
separate task.

Also list every finding in `.agent/issues.json`, key
`authority:<short-name>`, label `redteam`, plus `agent-ok` for a clear bug
with a minimal reproduction, or `needs-owner` when the fix changes a rule
of the language. The issue body holds the reproduction and the expected and
actual behaviour, so a fixer can work from the issue alone.

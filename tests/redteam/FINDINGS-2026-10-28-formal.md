# Formal-track findings — 2026-10-28

First runs of the mechanized link (tenon.md §6, formal/README.md):
ops/gates/formal_diff.py runs every corpus program that `tenon check` accepts
through `tenon ast`, the Lean translator and the core's evaluator, and through
`tenon run`, and compares stdout and exit status; an accepted program on which
the core gets stuck is a disagreement with the checker.

| Run | Programs | Rejected | In the subset | Agree | Differ | Accepted but stuck |
|---|---|---|---|---|---|---|
| 2124131 | 804 | 407 | 257 | 253 | 0 | 4 |
| 0527096 | 816 | 421 | 254 | 254 | 0 | 0 |
| 2e44f37 + stage 2 (traits, impls, `dyn`, Float, sort_by, encode) | 818 | 421 | 295 | 295 | 0 | 0 |

No new finding. The four stuck programs of the first run were
repros-2026-10-28-authority/01a-01d, finding 1 of
FINDINGS-2026-10-28-authority.md, detected independently by the core
("stuck (linear): an argument obligation lost at an early exit"); after its
fix (06027af) the checker rejects them.

The stage-2 run (the translator widened to traits, impls with default
bodies, generic and Show impls, `dyn` values, `Float`, `sort_by`, `encode`
and more builtins) found no disagreement either: 40 more programs in the
subset, all agreeing with `tenon run`.

Reproduce: `./check && python3 ops/gates/formal_diff.py --list`.
Limits: no modules, `decode`, fs/net/proc/workers builtins in the subset;
stderr is not compared.

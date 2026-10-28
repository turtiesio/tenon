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

## Stage 3: the Lean checker against `tenon check`

The checker proved sound in Lean (formal/TenonCore/Check.lean,
`Theorems.check_sound`; a program it accepts is never stuck in the core,
`checked_program_never_stuck`) now runs on every corpus program, accepted or
rejected by `tenon check` (ops/gates/formal_diff.py, formal/README.md
"Differential testing"). Of 858 programs, 598 are in the checker's subset:

| Verdicts | Programs |
|---|---|
| both accept | 240 |
| both reject | 192 |
| tenon accepts, Lean rejects | 25 |
| tenon rejects, Lean accepts | 141 |

**The compiler unsound: none.** No program `tenon check` accepts gets stuck
in the core (325 run and agree with `tenon run`), and each of the 25 it
accepts and the Lean checker rejects is the model being too strict (type
inference 14, `dyn` types 5, linear or unique values passed by `ref`/`mut`
4, or-patterns binding names in different orders 1, polymorphic recursion 1,
which `tenon build` also rejects): formal/README.md, "What remains".

**The compiler too strict.** Of the 141 programs it rejects and the Lean
checker accepts, 140 break a rule the core's guarantees do not need, by
design of the language (exhaustiveness, naming, derived traits on functions
and capabilities, mutability and `mut` markers, trait declarations,
constants, `main`'s signature, modules, recursive types; the classes and
files are in `.evidence/formal_diff.json`). One is a rule the model shows
unnecessary and the reference does not state:

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | low | `'\|' patterns cannot bind linear values` rejects a `match` of a linear enum with an or-pattern (tests/selfhost/lin_or_pattern.tn: `match j { A(n) \| B(n) => {} }`); the core types it (`AltTy`) and runs it, discharging the obligation once; docs/reference.md §7 and §12 do not mention the rule. Either document the restriction or lift it. | open |

Reproduce: `./check && python3 ops/gates/formal_diff.py --list` (the
`LEAN-REJECTS` and `TENON-REJECTS` lines).

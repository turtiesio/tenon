# Self-hosted checker: notes

`selfhost/check.tn FILE [ROOT]` is a second, independent implementation of
the bootstrap's front end after parsing: module loading (bootstrap/src/main.rs
`front`), bootstrap/src/check.rs, bootstrap/src/check_expr.rs, bootstrap/src/exhaust.rs, bootstrap/src/linear.rs and
the Subst/unify code of bootstrap/src/types.rs. It prints `ok` or the first diagnostic
as `PATH:LINE:COL: error: MESSAGE`; `tenonc check FILE [ROOT]`
(selfhost/tenonc.tn) is the same. `tools/selfhost.sh` compares it with
`tenon check` on every `.tn` file in the corpus. `checker.check` returns the
side tables the C backend uses (`Checked`; see EMITTER_NOTES.md).

## Modules

| Module | Ports | Contents |
|---|---|---|
| `check.tn` | main.rs | driver: prints `ok` or the diagnostic |
| `front.tn` | main.rs `front` | reads the prelude and modules through `Fs`, parses, checks |
| `checker.tn` | check.rs `check` | the phases in the bootstrap's order; returns `Checked` |
| `ckast.tn` | ast.rs, check.rs `fix_paths`, `breaks` | checker syntax tree with file numbers and node ids |
| `cktypes.tn` | types.rs | `Ty`, substitution, unification (no rollback, as in the bootstrap) |
| `ckenv.tn` | check.rs `declare`, `resolve_type`, `lower_type`, ... | declarations, modules, privacy, `check_main` |
| `ckinfer.tn` | check.rs, check_expr.rs | function bodies |
| `ckexh.tn` | exhaust.rs | exhaustiveness and reachability |
| `cklin.tn` | linear.rs | linear/unique analysis, codec restrictions |

The parser (`parser.tn`) records the positions the checker reports: type
expressions, declarations, variants, parameters and imports.

## Fidelity rules that matter for exact messages

- Unification binds variables as it goes and never rolls back; a failed
  `unify` leaves partial bindings, and the message prints the resolved types
  afterwards. The argument order of every `unify` call follows the bootstrap.
- Diagnostics come from the first failing step in the bootstrap's order:
  type declarations (all structs, then all enums), recursion, kinds,
  function signatures, every function body in declaration order (prelude,
  main file, modules in load order), `main`, then the linear pass over all
  functions.
- Side tables are keyed by node id; the receiver invented by `fix_paths` for
  `Value.field` gets id `-1 - id` (the bootstrap uses `u32::MAX - id`).
- The linear pass's cache of "generic function accepts a linear argument"
  answers is shared across the whole pass, as the bootstrap's thread-local is.

- Hiding prelude items: a main-file item whose name the prelude also
  declares at top level gets the internal name `<main>.NAME`
  (`Env.internal`), and diagnostics print it that way. Unqualified variants
  of non-prelude enums hide prelude variants (`variant_by_name`). `panic`
  ends a `let ... else` block only when it resolves to the prelude's.

## Bootstrap quirks reproduced on purpose

- `check_recursion` reports at the default span, rendered `<prelude>:0:0`.
- `breaks` (does a `while true` body contain a `break`?) also finds a
  `break` belonging to a loop nested inside an `if` or a block, because
  `visit_stmt` descends into nested loop bodies.
- An `if` without `else` appends "('if' without 'else' must produce Unit)" to
  any "type mismatch" raised anywhere inside its block.

- `module.Type.Variant` used as a value (not called) is not rewritten by
  `fix_paths`, so it reports `unknown name 'module'`
  (tests/selfhost/mod_variant_member.tn); `module.Variant(..)` becomes a path
  call and reports `'module' has no member 'Variant'`
  (tests/selfhost/mod_module_variant_call.tn).
- `muts` (which parameters are `mut`) excludes `self`, but a method used as a
  function value (`Type.method(recv, ..)`) indexes it against the full
  parameter list including `self`; the self-hosted checker indexes the same way.
- A `ref`/`mut` parameter flag is looked up by parameter name in the linear
  pass, so `mut` parameters count as borrowed: consuming one reports the
  `'ref' parameter` message (tests/selfhost/lin_mut_param.tn).

- Rules added to the bootstrap from QA findings are implemented: round 1
  (commit 1b2420c: comparability through fields and payloads, Float/function
  map keys, linear temporaries, guards that consume, `..` dropping a replaced
  linear field) and round 2 (commit 6d7d6ce: ordering maps, un-inferable
  `let` types, constant cycles, `self` exemption only for linear/unique
  owners). `tools/selfhost.sh` no longer skips `tests/pending/`, so every case
  there is cross-checked and can move to `tests/reject/`.

## Testing

- `tools/selfhost.sh` (part of `./check --fast`, using `tenonc check`): every corpus file, including
  the extra cases in `tests/selfhost/` (one diagnostic per file, plus accepted
  programs with tricky constructs; `ckmod*.tn`, `ckbad*.tn`, `ckcycle.tn` and
  `ckmissingdep.tn` are modules imported by the `mod_*` cases).
- `selfhost/checkfuzz.py COUNT SEED [-v]`: differential mutation testing.
  Corpus programs (mostly ones the bootstrap accepts) get token-level
  mutations; both checkers must print the same first line (and accepted
  mutants must emit the same C). Disagreements are
  saved under `.evidence/checkfuzz/`.

## Known disagreements

None on the corpus. Files skipped by `tools/selfhost.sh` would be listed here
with a minimal reproduction.

# Self-hosted checker: notes

`selfhost/check.tn FILE [ROOT]` is a second, independent implementation of
the bootstrap's front end after parsing: module loading (src/main.rs
`front`), src/check.rs, src/check_expr.rs, src/exhaust.rs, src/linear.rs and
the Subst/unify code of src/types.rs. It prints `ok` or the first diagnostic
as `PATH:LINE:COL: error: MESSAGE`. `tools/selfhost.sh` compares it with
`tenon check` on every `.tn` file in the corpus.

## Modules

| Module | Ports | Contents |
|---|---|---|
| `check.tn` | main.rs `front` | driver: reads the prelude and modules through `Fs`, parses, reports |
| `checker.tn` | check.rs `check` | the phases in the bootstrap's order |
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

## Bootstrap quirks reproduced on purpose

- `check_recursion` reports at the default span, rendered `<prelude>:0:0`.
- `breaks` (does a `while true` body contain a `break`?) also finds a
  `break` belonging to a loop nested inside an `if` or a block, because
  `visit_stmt` descends into nested loop bodies.
- An `if` without `else` appends "('if' without 'else' must produce Unit)" to
  any "type mismatch" raised anywhere inside its block.

## Known disagreements

None on the corpus. Files skipped by `tools/selfhost.sh` would be listed here
with a minimal reproduction.

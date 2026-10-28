# Tenon Core: the formal track in Lean 4

tenon.md §6 ("Formal track"): a core calculus of Tenon with mechanized
proofs, and a mechanized link to the real compiler. This directory is a Lake
project (`lakefile.toml`, toolchain pinned in `lean-toolchain`:
`leanprover/lean4:v4.35.0`; no Mathlib, no other dependency).

| Part | Files | Status |
|---|---|---|
| Syntax, values, programs | `TenonCore/Syntax.lean`, `TenonCore/Value.lean` | done |
| Semantics: a total, computable definitional interpreter with fuel | `TenonCore/Eval.lean` | done |
| Builtins of the executable semantics (operators, formatting, `Str`/`List`/`Map`, console, `Fs` attenuation, stdin) | `TenonCore/Prims.lean` | done |
| Capability safety | `TenonCore/Capability.lean` (+ `Lemmas.lean`) | **proved** |
| Linear and unique soundness (conservation of obligations) | `TenonCore/LinearSafe.lean` (+ `Linear.lean`, `LinearLemmas.lean`) | **proved** |
| Worker isolation (heaps, channels, the `Send` rule) | `TenonCore/Workers.lean` | **proved** |
| Typing judgement (types, kinds, obligation tracking) | `TenonCore/Typing.lean` | defined |
| Type soundness, parametricity | `Todo/TypeSoundness.lean` | stated, proof TODO |
| The guarded theorem statements | `TenonCore/Theorems.lean` | guarded (ops/governance/guarded.txt) |
| Translator from `tenon ast` dumps to the core | `Front/Parse.lean`, `Front/Translate.lean` | done |
| Runner (`lake exe tenon-core`) | `Main.lean` | done |
| Differential test against `tenon run` | `../ops/gates/formal_diff.py` | 254 of 254 programs in the subset agree |

Every proof checks with no `sorry` and depends only on Lean's standard axioms
(`propext`, `Classical.choice`, `Quot.sound`); `../ops/gates/formal_check.sh`
enforces both on every `./check` (`Axioms.lean` is its audit).

## How to run

Install elan (`curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none`);
it installs the pinned toolchain on first use.

```sh
cd formal && lake build                  # the core, the proofs, the translator, tenon-core
ops/gates/formal_check.sh                # the gate: build, no sorry, the axiom audit
python3 ops/gates/formal_diff.py --list  # the differential test (needs target/tenon: ./check)
lake build Todo                          # the unfinished statements (uses sorry)
```

Run one program on the core by hand:

```sh
target/tenon ast lib/prelude.tn > /tmp/p1.ast; target/tenon ast lib/v2/prelude.tn > /tmp/p2.ast
target/tenon ast tests/run/enums.tn > /tmp/e.ast
formal/.lake/build/bin/tenon-core run /tmp/p1.ast /tmp/p2.ast -- /tmp/e.ast
```

## The model

Tenon Core is a first-order expression language with closures over one
program (`Prog`): declared structs and enums (`AdtDecl`), functions and
methods (`FnDecl`), and builtins (`Prog.prim`). The evaluator is
`Tenon.eval P n ρ st e`, a total function by structural recursion on the fuel
`n`, computable (`lake exe tenon-core` runs it).

- **Values** (`Val`): `Int` (unbounded in Lean, 64-bit overflow traps in the
  builtins), `Bool`, `Str`, `Unit`, tuples, lists, maps (entries in insertion
  order), values of declared types (`adt`: type, variant, obligation token,
  payload), closures (captured names and values, parameters, body), named
  functions as values, capabilities. All values are trees: Tenon's value
  semantics (copy on assignment; copy-on-write is an implementation detail)
  needs no heap in the sequential core.
- **Environments** (`Env`): variables in scope, each holding a value or
  *moved*. There is no shadowing (Tenon forbids it); `let` scopes are popped at
  their end.
- **Expressions** (`Expr`): literals; reading a *place* `x.f[i].0` (`place`);
  projecting a computed value (`proj`); tuples, lists; building a declared
  value (`con`); closures (`lam`, capturing the variables without obligations
  by value); `fnref`; calls of function values (`call`); method calls
  dispatched on the receiver's type head (`mcall`: a Tenon method, else a
  builtin); builtins (`prim`, whose place operands are inspected, not
  consumed); `let`/`var` (`letE`); assignment to a place (`assign`);
  sequencing; `if`; `match` with nested patterns, alternatives and guards;
  `while`; `return`, `break`, `continue`; `?` on `Option`/`Result` (`try`);
  and `unsup` (a construct the core does not model).
- **Results** (`Out`): a value, an early exit (`Ctl`: `ret`, `brk`, `cont`)
  or an error (`Err`): a trap (with the effects so far), *stuck* (a type error
  or a broken obligation rule), out of fuel, or unsupported.
- **State** (`St`): the effects performed (`Event`: the capability used, the
  operation, its text), the obligations minted, discharged (`burned`) and
  dropped, the next token, and the outside world's state (the stdin offset).
- **Capabilities** (`Cap`): a kind (`Console`, `Fs`, `Clock`, `Net`, `Proc`,
  `Workers`) and, for `Fs`, a jail (a root path) and a read-only flag. The
  attenuation order `c ≤ d` (`Cap.leb`) is decidable. No expression builds a
  capability: the only sources are the initial environment (`Sys`, the
  argument of `main`) and the builtins `Fs.within` and `Fs.read_only`.
- **Obligations**: a value of a `linear` or `unique` declared type carries a
  token (`Tok`), minted when it is built. Reading a whole variable that holds a
  token moves it (the variable becomes moved); a part cannot be moved out; a
  token is discharged by destructuring it with `match` or when a method of the
  type's own (`FnDecl.owner`) ends with its `self`; a unique value may be
  dropped (logged), a linear one may not; obligations cannot go to builtins.
- **`ref`/`mut` parameters**: copy-in/copy-out. A value with an obligation is
  moved out of its variable for the call and written back after it; one
  without is copied and written back to its place.
- **Traps**: integer overflow, division by zero, index out of bounds, missing
  map key, `panic`, `assert`, `unwrap` on `None`/`Err`, a `match` without a
  matching arm.
- **Workers** (`TenonCore/Workers.lean`): a separate small-step machine. Each
  heap cell (a buffer, a string, a socket) has an owning worker; channels
  carry `Msg`s, location-free trees; `send` and `spawn` make them with
  `Marshal`, the deep copy the `Send` rule allows (it has no case for a socket,
  a cell that is not sendable); `recv` rebuilds a message in fresh cells of the
  receiver; `send` with `move` takes a unique value from the sender. Local
  steps (`compute`, `write`, `alloc`) use only what the worker reaches.

### Semantics

A definitional interpreter (Amin and Rompf's style): every rule of the
language that the checker enforces statically is *also* checked dynamically,
as a stuck state, so a theorem about every run that is not stuck is a
theorem about the language's rules. `Stuck.type`: no such variable, field or
method, wrong value shape, wrong arity. `Stuck.linear`: an obligation copied,
dropped, overwritten, lost at an early exit, captured, passed to a builtin, or
a variable used after it was moved. Builtins are abstract: the evaluator's
monitor (`primApply`) refuses a builtin result that carries an obligation, or
authority that is not an attenuation of the builtin's arguments, so no
theorem depends on the builtins' code.

## Theorems

The statements are in `TenonCore/Theorems.lean` (guarded: changing or
removing one needs an owner approval, `../ops/governance/README.md`).

| Theorem | Statement | Proved in |
|---|---|---|
| `within_narrows`, `readOnly_narrows`, `attenuation_trans` | `c.within s ≤ c`; `c.readOnly ≤ c`; `≤` is transitive: attenuation only narrows | `Capability.lean` |
| `capability_safety` | for **any** program, expression and fuel: if every capability of the environment, and of every effect so far, is an attenuation of one in `A`, then so is every capability of the result, of the final environment, and of every effect performed (also on early exits and traps): nothing forges authority | `Capability.lean` (`capSafe`, induction on fuel over the 10 mutually recursive functions of the evaluator) |
| `no_authority_escalation` | a run started with capabilities `A` (its `Sys`) performs every effect through an attenuation of one of `A` | `Capability.lean` |
| `obligations_conserved` | for any program and expression, along an evaluation that ends with a value or an early exit: per token, held (result and environment) + discharged + dropped − minted is unchanged; only unique tokens are dropped; minted tokens are distinct | `LinearSafe.lean` (`linSafe`) |
| `obligations_exactly_once` | from a start holding no obligation, if the run ends with a value: every minted token occurs exactly once among the result, the final environment, the discharged and the dropped ones; no other token occurs anywhere (no forged or duplicated obligation, so no unique value duplicated); a linear token is never dropped | `LinearSafe.lean` |
| `linear_discharged_exactly_once` | a complete run (the result and final environment hold no obligation, as for `main` returning `Unit`, `Int` or a plain `Result`) discharged every linear value it created exactly once, on every path it took, early exits included | `LinearSafe.lean` |
| `step_isolated`, `run_isolated` | every step of the worker machine keeps the invariant "every cell a worker reaches exists and is owned by it"; every configuration reached from the start satisfies it | `Workers.lean` |
| `no_shared_cell` | in such a configuration no cell (buffer, string, socket) is reachable from two different workers: no shared mutable state, no data race | `Workers.lean` |
| `unchecked_sharing_breaks_isolation` | without the `Send` copy (giving another worker a pointer) the invariant breaks: the rule is necessary | `Workers.lean` |

What the obligation theorems mean: they hold for every program, typed or
not, because the semantics enforces the rules dynamically. That the type
system makes the dynamic checks unnecessary (a program `tenon check` accepts
never gets stuck) is `type_soundness`, stated in `Todo/TypeSoundness.lean`;
until it is proved, the differential test checks it empirically on the
corpus (below); its first run found the programs of an open finding that the
checker accepted and the semantics refused.

## Mapping from Tenon

How the translator (`Front/Translate.lean`) maps each construct; the
translator knows no types, so dispatch on types happens at run time on the
value (which agrees with static dispatch for well-typed programs).

| Tenon | Core |
|---|---|
| `let x = e` / `var x = e` | `letE x false/true e rest` |
| `let (a, b) = e`, `let P = e else { ... }` | `mtch e [(P, rest), (_, else)]` |
| `x`, `x.f`, `x.0`, `xs[i]`, `m[k]` (rooted at a variable) | `place x [fld f, tfld 0, idx i]` |
| `f().x` | `proj` |
| `x = e`, `x.f[i] = e`, `m[k] = e` (inserts) | `assign` |
| `x op= e` | `let t = e; x = x op t` (reference §6: the right side, then the current value) |
| `if`, `while`, `return`, `break`, `continue`, `e?` | `ite`, `while`, `ret`, `brk`, `cont`, `try` |
| `for i in a..b` | both ends once, then `while` with a hidden counter |
| `for x in xs`, `for (k, v) in m` | a snapshot (`%iter`), then `while` over its indices |
| `if let`, `while let` | `mtch` with a fallback arm (as the parser does) |
| `match` with `|`, guards, nested patterns | `mtch` with `Pat.alt`, guards, nested `Pat` (variants matched by name, following the value's type) |
| struct literal `S { f: e, ..base }`, shorthand | each field once in source order (hidden `let`s), then `con S 0 [fields in declaration order]` |
| enum variant `V(e)`, `T.V`, `V` as a function value | `con T tag [e]`; a closure building it |
| closures `fn(x) => e` | `lam` (captures by value the variables without obligations) |
| named function as a value, `Str.len` | `fnref` |
| `f(args)`, `mut x` arguments | `call (fnref f) args` (modes come from the callee at run time) |
| `x.m(args)`, `T.m(args)` | `mcall m x args` (receiver's type head), `call (fnref T.m)` |
| operators, `and`/`or`, `not`, `-x` | builtins `%add`...; `ite` (short circuit) |
| `"{e}"`, `"{e:SPEC}"` | `%show`, `%fmt`, `%concat` |
| `const` | a function of no argument, called at every use (reference §12) |
| `linear struct`, `unique struct`, enums | `AdtDecl.kind`; tokens minted by `con` |
| methods `fn T.m(self ...)` | `FnDecl` keyed `T.m`, `owner := T` (finishes its own `self`) |
| prelude functions | translated from `lib/prelude.tn` like the program; `extern fn`s are builtins |
| `unwrap`/`expect` | core definitions (they consume their receiver) |
| `main(sys: Sys)` | called with `Sys { console, fs, clock, net, proc, args }` of unattenuated capabilities |

### Not modeled (outside the subset)

A run that reaches one of these ends with `tenon-core: unsupported` and is
outside the differential subset: `Float` (its shortest round-trip printing is
not reimplemented), traits, impls and `dyn` (so `impl Show`), modules
(`import`), `encode`/`decode`, the file system, network and process builtins
(only `Fs.within`/`Fs.read_only` are modeled), workers and channels in the
sequential core (they are in the worker machine), `sort_by` and other
builtins that call closures, a few format specs (`.N` precision, `0` with
`,`), invalid UTF-8 on stdin. Abstracted: exhaustiveness of `match` (a
missing case traps), stack depth (the core has fuel; a deep recursion is
"out of fuel" or "ran out of stack", outside the subset), the order in which
the C backend frees values, scheduling (the worker machine is a relation:
every interleaving).

## Differential testing

`../ops/gates/formal_diff.py` runs every corpus program (a file with
`fn main`, `ops/corpus.py`) that `tenon check` accepts through `tenon ast`,
the translator and the core, and, when the core completes it, through
`tenon run`, and compares standard output and the exit status. A program the
checker accepts but on which the core gets stuck is reported too: the
checker accepted a program that breaks a rule. It runs in the evidence loop
(`../ops/evidence/evidence.sh`, nightly) and writes `.evidence/formal_diff.json`
(STATUS.md).

Coverage on 2026-10-28 at `0527096` (816 corpus programs): 421 are rejected
by `tenon check` (reject tests and their kin) and 29 do not parse; of the 366
accepted, **254 (69%) are in the core's subset**: 147 study programs, 58
`tests/run`, 20 `tests/selfhost`, 10 red-team repros, 8 `tests/fmt`, the
`calc`, `chat`, `csvq`, `mdhtml`, `mkplan` programs and others. Outside: 103
unsupported constructs (traits and impls 21, `Float` 8, fs/net/proc builtins,
modules, codec), 9 too slow or too deep for the core.

**Result: all 254 agree with `tenon run` (stdout and exit status); none
differs; none that `tenon check` accepts gets stuck in the core.** No new
finding.

The first run, a few hours earlier at `2124131`, before the fix of the
authority review's finding 1 (`06027af`; a linear value lost when a later
argument exits early, tests/redteam/FINDINGS-2026-10-28-authority.md), had 4
programs the checker accepted and the core refused: the four repros of that
finding, which the core's obligation checks detected independently
(`stuck (linear): an argument obligation lost at an early exit`). With the
fix the checker rejects them.

## Gate and times

`./check` runs `ops/gates/formal_check.sh` ("formal" in its table): 0.3-0.4 s warm
on the development machine (Apple M4 Max), about 4 s for a full rebuild of
`formal/` (the first build on a new machine also downloads the toolchain).
CI installs elan and caches the toolchain and the build (`.github/workflows/ci.yml`,
`nightly.yml`). The differential test takes about 22 s on 8 cores.

## What remains (TODO)

1. **Type soundness** (`Todo/TypeSoundness.lean`, `type_soundness`): a
   well-typed expression (`Typing.lean`: `HasTy`, with obligation tracking,
   `ProgOk`, `PrimsOk`) in a matching environment never gets stuck (neither
   `Stuck.type` nor `Stuck.linear`) and never reaches `unsup`; results have
   their types. Proof plan: induction on fuel over the 10 functions of the
   evaluator, as `capSafe` and `linSafe` do, with inversion of `HasTy`.
2. **Parametricity** (`typing_subst`): checking a generic function once types
   all its instances (`ProgOk` asks for every instance, as monomorphization does).
3. **The checker link**: compare `tenon check`'s verdicts with a checker for
   `HasTy` written and proved sound in Lean (tenon.md §6).
4. **Traits and coherence**, then effects and contracts as they are designed
   (tenon.md §6, milestone items 3-5).
5. Link the worker machine to the sequential core (a worker's local steps as
   core evaluations), and model `Fs` paths (the jail's `..` and symlink rules)
   beyond the attenuation order.
6. Widen the subset: `Float` printing, `impl Show`, modules, `sort_by`.

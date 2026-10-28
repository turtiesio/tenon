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
| Typing judgement (types, kinds, obligation tracking, early exits) | `TenonCore/Typing.lean` | defined |
| Type soundness | `TenonCore/TypeSafe*.lean` (+ `TypingLemmas.lean`, `TypingPaths.lean`) | **proved** |
| Parametricity (substitution lemma, checking a generic function once) | `TenonCore/Subst.lean`, `TenonCore/SubstTyping.lean` | **proved** |
| The hypotheses are satisfiable (a typed linear program) | `TenonCore/TypeExamples.lean` | **proved** |
| Traits and coherence (impls, generic impls with bounds, supertraits, `dyn`) | `TenonCore/Traits.lean` | **proved** |
| Milestone-3 item 3 specification (user `Eq`/`Ord`/`Hash`, sorting, maps) | `TenonCore/TypeGaps.lean` | **proved** (+ `TypeGapsStable.lean`) |
| The guarded theorem statements | `TenonCore/Theorems.lean` | guarded (ops/governance/guarded.txt) |
| Translator from `tenon ast` dumps to the core | `Front/Parse.lean`, `Front/Translate.lean` | done |
| Runner (`lake exe tenon-core`) | `Main.lean` | done |
| Differential test against `tenon run` | `../ops/gates/formal_diff.py` | 295 of 295 programs in the subset agree |

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
lake build Todo                          # unfinished statements (may use sorry; empty now)
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

### Static semantics (`TenonCore/Typing.lean`)

`HasTy P prim Δ Γ e t Γ'`: in program `P` with builtin signatures `prim`,
`e` has type `t` in context `Γ` and leaves `Γ'`. A context entry records a
variable's type, whether it is assignable, and whether it still holds its
value (`avail`, the checker's moved set, compiler/cklin.tn); `Γ'` says what
`e` moved. `Δ` (`Sig`) says where `e` is: the enclosing function's return
type and frame (its length and what its parameters must be at the end,
`FinFn`), the innermost loop's context, and whether an early exit is allowed
(`exitOk`). The rules, in short:

- **Kinds** (`Ty.kind`): a type is linear or unique if its declared type is or
  a component is (`Option[Claim]` is linear); a type parameter counts as
  linear (generic code may not copy or drop a `T`). Copyable values carry no
  obligation and non-linear ones no linear obligation (`ValTy.toks_allowed`,
  from `AdtsOk`: a field's kind is bounded by its type's).
- **Moves and copies**: reading a whole variable may move it (marking it
  unavailable); a copy (of a variable or a part `x.f[i]`) needs a copyable
  type. `let` scopes end with their linear variables consumed; assignment
  never overwrites a live linear value; both branches of an `if` and all arms
  of a `match` leave the same context; a loop body leaves the loop's context;
  `_` never drops a linear part; a guard only on a copyable value.
- **Temporaries and early exits** (`TailSig`): after a linear value is
  evaluated as an element or argument, the rest is typed with
  `Sig.noExit` (no `return`, `?`, `break` or `continue` escaping), since an exit
  would lose it (the shape of finding 1 of the authority review).
  `return`/`?` need the locals consumed and the frame finished (`RetOk`);
  `break`/`continue` the loop's locals consumed (`LoopOk`).
- **Calls**: by-value arguments; `ref`/`mut` arguments are places of a
  copyable type still in scope after the arguments (copied in and written
  back). Methods resolve on the receiver type's head, as the evaluator does on
  the value's head; a by-value `self` of the method's own linear type is
  discharged at the end (`SelfFin`). Builtins (`prim`) have abstract
  signatures; `PrimsOk` states what they must satisfy.
- **Closures** see only their parameters (the values they capture at run
  time are not used by the judgement), and their parameters are consumed.
- **Programs** (`ProgOk`): well-formed declarations (`AdtsOk`), the prelude's
  `Option`/`Result` (`StdOk`), and every function's body typed at every
  instance of its type parameters with its parameters finished at the end.

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
| `type_soundness` | for a well-typed program (`ProgOk`, `PrimsOk`), an expression with `HasTy P prim Δ Γ e t Γ'`, run with any fuel in an environment matching `Γ` (`EnvOk`): the run is never stuck (neither `Stuck.type` nor `Stuck.linear`) and never `unsup`; a value has type `t` and the final environment matches `Γ'`; a `return` happens only where `Δ.exitOk` and carries a value of `Δ.ret`; `break`/`continue` only in a loop. Traps and running out of fuel remain | `TypeSafe.lean`, `TypeSafeEval.lean`, `TypeSafeRest.lean` (`tySafe`: induction on fuel over the 10 functions of the evaluator, with inversion of the judgement) |
| `well_typed_never_stuck` | the same, as: `eval P n ρ st e` is never `.err (.stuck _ _)` nor `.err (.unsup _)` | `Theorems.lean` |
| `typing_subst` | typing is stable under substituting the type parameters (`HasTy Δ Γ e t Γ'` gives `HasTy Δ' (Γ.subst σ) e (t.subst σ) (Γ'.subst σ)`), for well-scoped declarations (`ProgScoped`) and parametric builtin signatures | `SubstTyping.lean` (`HasTy.subst`; `kind_subst_le`: substitution only lowers a kind) |
| `generic_check_once` | if every function body is typed once, at its own type parameters, the program is typed at every instance (`ProgOk`): checking a generic function once covers all its instances | `SubstTyping.lean` |
| `coherent_unique_impl` | coherent impls (no two of a trait overlap): at most one impl applies to a trait and type | `Traits.lean` (`impl_unique`) |
| `method_resolution` | for a type with an instance of a trait (a derivation through impls, generic impls with their bounds included), exactly one impl applies and the evaluator's `resolve` on any value of that head, in the program with the impls elaborated (`withImpls`: impl methods keyed `head.m`, default bodies copied), finds its method or the trait's default: method resolution is deterministic | `Traits.lean` |
| `bounded_call_resolves` | in a generic function with bounds, a call of a trait method on a value of a bounded type, at any type arguments satisfying the bounds (supertraits included), does not get stuck on method lookup | `Traits.lean` (`entails_sound`) |
| `dyn_dispatch` | a method call on a `dyn` value resolves to the impl of the value's type, with the trait method's parameters and the trait's signature at that type: `dyn` dispatch is type-safe | `Traits.lean` |
| `sort_unique`, `sort_sorted_perm` | with a user `Ord` that is a total order, every correct sort gives the same list (the two backends cannot disagree); a lawful `Ord` sorts; any comparator gives a permutation | `TypeGaps.lean` |
| `stable_sort_unique`, `sort_stable_equiv` | with a user `Ord` that is only a total preorder (distinct values may compare equal): two stable sorts give the same list; the model sort is stable; any two sorted permutations agree up to `equal` position by position | `TypeGapsStable.lean` |
| `maps_agree` | with lawful user `Eq`/`Ord`/`Hash` (and `Ord` consistent with `Eq`, `Hash` with `Eq`), the ordered map and the hashed map agree with the insertion-order map on every lookup | `TypeGaps.lean` |
| `unlawful_eq_map_provenance`, `user_impls_capability_safe` | an arbitrary (inconsistent) user `Eq` breaks only functional results: the map holds only inserted keys and values; whatever user impls do, they get no authority (`capability_safety` for the elaborated program; `obligations_conserved` likewise, `TypeGaps.user_impls_obligations_conserved`) | `TypeGaps.lean` |

What the obligation theorems mean: they hold for every program, typed or
not, because the semantics enforces the rules dynamically. `type_soundness`
says the type system makes those dynamic checks unnecessary: a well-typed
program never trips them, so with `obligations_exactly_once` every linear
value it creates is consumed exactly once. `TypeExamples.lean` shows the
hypotheses are satisfiable (a program with a linear enum, `ProgOk` and
`PrimsOk` proved, a typed expression creating and consuming a linear value,
which the evaluator completes). The theorem is about the core's judgement,
not yet about `tenon check` itself (TODO 1); the differential test checks the
link empirically on the corpus (below): no program `tenon check` accepts gets
stuck in the core; its first run found the programs of an open finding that
the checker accepted and the semantics refused.

The traits model (`Traits.lean`): a trait has type parameters, supertraits
and methods (signatures with `Ty.var 0` as `Self`, optional default bodies);
an impl gives a trait at some arguments for a type pattern over its own
parameters, with bounds; `Coherent` forbids two overlapping impls of a trait
(a unifier exists); `Holds` is the instance relation (derivation trees through
impls); `Entails` is what a set of bounds lets the checker derive. Two more
assumptions say what the head-keyed elaboration needs: `HeadCoherent` (method
keys are distinct, so two traits giving one type the same method name, or
impls of one trait for two instantiations of one head, are outside it) and
`NoInherent` (no type's own method shadows an impl method).

The item-3 specification (`TypeGaps.lean`; its header lists, per feature,
the theorem the implementation must satisfy): `UEq.Lawful` (an equivalence),
`UOrd.Lawful` (a total preorder) and `UOrd.TotalOrder`, `Consistent` (`Ord`'s
`equal` is `Eq`), `BucketLawful` (`a == b → hash a = hash b`); insertion sort
by a user comparator and maps keyed by user types (by `Eq` in insertion order,
ordered by `Ord`, hashed); with lawful impls lookup after insert returns the
value, keys are unique modulo `Eq`, the ordered map iterates in increasing
order; with arbitrary impls the operations terminate, return permutations,
and hold only inserted values; a bound `T: Ord` (or `Hash`) entails `T: Eq`
(`ord_bound_gives_eq`, `Traits.super_entails`).

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
| `impl Tr for T { fn m ... }` (also for `Int`, `List[T]`, tuples, function types) | `FnDecl` keyed `<head>.m` (`T.m`, `List.m`, `Tuple.m`, `Fn.m`), `owner := T` when the impl is in T's file; dispatch is `mcall` on the receiver value's head (`Traits.withImpls` is the model of this) |
| trait default bodies | copied into each impl that does not give the method |
| `impl[T: B] Tr for G[T]` | keyed on the head `G`; impls of one method for several instantiations of one head share a key and are `unsup` |
| `dyn Tr(e)` | `e` (dynamic dispatch on the value's head) |
| `impl Show for T` | its `to_str` is a `FnDecl` `%show#T#i`; with Show impls in the program, `"{e}"`, `x.to_str()` and `main`'s error go through a core function `%show` (the builtin `%showparts` names the impl to call or the text around the parts); for an impl on one instantiation (`Box[Int]`) or with bounds, the values decide which applies, and when they cannot tell (an empty list, `None`, a `dyn` hiding its type) the run is `unsup` |
| `Float` | `adt "Float" 0 none [int bits]`; arithmetic and `sqrt`/`floor`/`ceil`/`round` with Lean's `Float` (C doubles); reading, shortest round-trip printing, `to_fixed`, `%` and `to_int` exactly over `Nat` (`TenonCore/PrimFloat.lean`) |
| format specs | parsed as compiler/parser.tn does and padded as `ival.tn` does (`.N`, `0` with `,`) |
| `sort`, `sort_by(key)`, `sort_by_desc(key)` | the interpreter's bottom-up merge sort; for `sort_by` a core function computes the keys first, calling the closure element by element |
| `encode(x)` | the structural nested text |

### Not modeled (outside the subset)

A run that reaches one of these ends with `tenon-core: unsupported` and is
outside the differential subset: modules (`import`), `decode` (type-directed),
the file system, network and process builtins (only
`Fs.within`/`Fs.read_only` are modeled), workers and channels in the
sequential core (they are in the worker machine), invalid UTF-8 on stdin;
calls that need static types (`T.m()`, `Self.m()` without a receiver value);
a program where a type's own method and a trait method share a name (a direct
call takes the own method, a call through a bound or `dyn` the trait's; the
core cannot tell them apart); Show impls whose choice the values do not
decide. Abstracted: exhaustiveness of `match` (a
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

Coverage on 2026-10-28 at `2e44f37` with stage 2 (818 corpus programs): 421
are rejected by `tenon check` (reject tests and their kin) and 29 do not
parse; of the 368 accepted, **295 (80%) are in the core's subset** (stage 1:
254 of 366, 69%): 149 study programs, 78 `tests/run`, 20 `tests/selfhost`,
17 `tests/v2`, 13 red-team repros, 8 `tests/fmt`, the `calc`, `chat`, `csvq`,
`mdhtml`, `mkplan` programs and others. Outside: 63 unsupported constructs
(fs/net/proc/workers builtins 38, modules 20, Show impls the values do not
decide 2, invalid UTF-8 on stdin 2, a type's own method shadowing a trait
method 1), 10 too slow or too deep for the core.

**Result: all 295 agree with `tenon run` (stdout and exit status); none
differs; none that `tenon check` accepts gets stuck in the core.** No new
finding (tests/redteam/FINDINGS-2026-10-28-formal.md). Float printing was
also checked beyond the corpus: a throwaway stress program of 823 lines
(subnormals, overflow, rounding ties, `to_fixed`, `%`, `,` grouping,
`Str.to_float` edge cases) printed the same through both.

The first run, a few hours earlier at `2124131`, before the fix of the
authority review's finding 1 (`06027af`; a linear value lost when a later
argument exits early, tests/redteam/FINDINGS-2026-10-28-authority.md), had 4
programs the checker accepted and the core refused: the four repros of that
finding, which the core's obligation checks detected independently
(`stuck (linear): an argument obligation lost at an early exit`). With the
fix the checker rejects them.

## Gate and times

`./check` runs `ops/gates/formal_check.sh` ("formal" in its table): under 1 s
warm on the development machine (Apple M4 Max), about 9 s for a full rebuild
of `formal/` (the first build on a new machine also downloads the
toolchain). It requires at least the 27 statements of `Theorems.lean` in the
axiom audit. CI installs elan and caches the toolchain and the build
(`.github/workflows/ci.yml`, `nightly.yml`). The differential test takes
about 25 s on 8 cores.

## What remains (TODO)

1. **The checker link**: a checker for `HasTy` written and proved sound in
   Lean, its verdicts compared with `tenon check`'s on the corpus (tenon.md
   §6); and the translator's output typed, so `type_soundness` applies to the
   translated corpus programs (it needs the types `tenon ast` does not dump).
2. **Widen the typing judgement** to what the evaluator allows and the
   checker accepts: closures that use captured variables (the frame's
   captured slots typed by name, not position), `ref`/`mut` arguments of
   linear or unique types (moved in and written back) and `ref`/`mut`
   receivers on parts, map literals, builtins that call closures, workers.
   The current rules are sound but stricter than `tenon check` there.
3. **Traits in the typing judgement**: bounded type parameters and `dyn` types
   as `Ty`s, so `bounded_call_resolves` and `dyn_dispatch` feed
   `type_soundness` directly; impls for several instantiations of one head
   (monomorphized keys; `HeadCoherent` excludes them now); a unification-based
   overlap check proved sound against `Coherent`; the orphan rule; object
   safety.
4. **Item 3**: the connection of `resolve` to a full `eval` of a user
   comparator inside the builtin sort, and a proof that the backends' actual
   sort (the interpreter's bottom-up merge sort, `Prims.lean`) is a stable
   sorted permutation, so `stable_sort_unique` applies to it.
5. **Effects and contracts** (milestone items 4-5) as they are designed.
6. Link the worker machine to the sequential core (a worker's local steps as
   core evaluations), and model `Fs` paths (the jail's `..` and symlink rules)
   beyond the attenuation order.
7. Widen the subset: modules, `decode`, the fs/net/proc builtins (as effects
   on a modeled world), workers.

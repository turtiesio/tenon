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
| Typing judgement (types, kinds, obligation tracking, early exits; stage 2 and the loosened stage 3, `Ext`) | `TenonCore/Typing.lean` | defined |
| Type soundness (both judgements, one proof) | `TenonCore/TypeSafe*.lean` (+ `TypingLemmas.lean`, `TypingPaths.lean`) | **proved** |
| The checker: a decision procedure for the stage-3 judgement, executable | `TenonCore/Check.lean` (+ `CheckBase.lean`) | done |
| The checker is sound (`check_sound`, `checked_program_never_stuck`) | `TenonCore/CheckSound.lean` | **proved** |
| Coherence decided: the overlap check and the orphan rule | `TenonCore/TraitsCheck.lean` | **proved** |
| Parametricity (substitution lemma, checking a generic function once) | `TenonCore/Subst.lean`, `TenonCore/SubstTyping.lean` | **proved** |
| The hypotheses are satisfiable (a typed linear program) | `TenonCore/TypeExamples.lean` | **proved** |
| Traits and coherence (impls, generic impls with bounds, supertraits, `dyn`) | `TenonCore/Traits.lean` | **proved** |
| Milestone-3 item 3 specification (user `Eq`/`Ord`/`Hash`, sorting, maps) | `TenonCore/TypeGaps.lean` | **proved** (+ `TypeGapsStable.lean`) |
| Item 3 as implemented: the prelude's `Ord: Eq` and `Hash: Eq`, maps with Eq/Hash impls as `hget`/`hset`, `Ordering`, impls of one trait at two arguments | `TenonCore/TypeGapsLink.lean` | **proved** (instances) |
| The guarded theorem statements | `TenonCore/Theorems.lean` | guarded (ops/governance/guarded.txt) |
| Translator from `tenon ast` dumps to the core | `Front/Parse.lean`, `Front/Translate.lean` | done |
| The checker's driver: builtin signatures, the instances a program uses | `Front/Checker.lean` | done |
| Runner (`lake exe tenon-core run`, `... check`) | `Main.lean` | done |
| Differential test against `tenon run` | `../ops/gates/formal_diff.py` | 325 of 325 programs in the subset agree |
| The Lean checker against `tenon check` | `../ops/gates/formal_diff.py` | 432 of 598 verdicts agree; every disagreement classified (below) |

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

Run one program on the core, or ask the Lean checker, by hand:

```sh
target/tenon ast lib/prelude.tn > /tmp/p1.ast; target/tenon ast lib/v2/prelude.tn > /tmp/p2.ast
target/tenon ast tests/run/enums.tn > /tmp/e.ast
formal/.lake/build/bin/tenon-core run /tmp/p1.ast /tmp/p2.ast -- /tmp/e.ast
formal/.lake/build/bin/tenon-core check /tmp/p1.ast /tmp/p2.ast -- /tmp/e.ast   # accepted / rejected / unsupported
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
  by value; `clos`, capturing the listed variables, which the translator
  computes, each a value without obligations); `fnref`; calls of function values (`call`); method calls
  dispatched on the receiver's type head (`mcall`: a Tenon method, else a
  builtin); builtins (`prim`, whose place operands are inspected, not
  consumed); `let`/`var` (`letE`); assignment to a place (`assign`);
  sequencing; `if`; `match` with nested patterns, alternatives and guards;
  `while`; `return`, `break`, `continue`; `?` on `Option`/`Result` (`try`);
  a type annotation, a hint for the checker with no run-time effect (`ann`);
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
- **Closures** (`lam`) see only their parameters (the values they capture at
  run time are not used by the judgement), and their parameters are consumed.
- **Programs** (`ProgOk`): well-formed declarations (`AdtsOk`), the prelude's
  `Option`/`Result` (`StdOk`), and every function's body typed at every
  instance of its type parameters with its parameters finished at the end.

**Stage 3 (`Ext`).** The judgement is `HasTyX X P prim`, with `X : Ext`
saying what it allows beyond the rules above; `HasTy` (and `ValTy`, `EnvOk`,
`ProgOk`, `PrimsOk`, which the guarded statements use) is `Ext.strict`,
exactly the stage-2 judgement; `Ext.stage3 I` is the loosened one, which
`tenon check`'s programs need and the checker decides:

- **Closures capturing variables** (`HasTyX.clos`): the body is typed with
  the parameters, then the captured variables (`capCtx`: immutable copies of
  copyable values, the reference's "by value at creation"); the frame's end
  (`closSig`) finishes the parameters and drops the copies. A closure value
  (`ValTyX.closC`) carries its captured values typed.
- **Instances** (`I`): a call, a function value and a method call must use an
  instance in `I`, and `ProgOkX` asks only those instances to be well typed:
  the program is checked at the instances it uses, monomorphized as the C
  backend compiles it (reference §17). Bounded type parameters need nothing
  more: at an instance a bound's method resolves on the concrete type's head
  (`Traits.bounded_call_resolves` is why that is the impl's method).
- **Annotations** (`ann`) type as their expression; **direct calls of
  builtins** (`callPrim`, `Str.from_utf8(b)`) take their arguments as
  operands; a method call on a value whose head has no method of that name
  selects the builtin for every head (`PrimAt`: `x.to_str()`).

The one proof (`tySafe`, TypeSafe*.lean) is generic in `X`; `type_soundness`
is its `Ext.strict` instance and `type_soundness_full` its stage-3 instance.

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
| `type_soundness_full` | `type_soundness` for the stage-3 judgement (`Ext.stage3 I`: closures capturing variables, annotations, builtins called directly, functions at the instances `I`) | `TypeSafe*.lean` (the same proof, generic in `Ext`) |
| `check_sound` | a program the Lean checker accepts (`Check.checkAll`, with `keys` listing its declared types) is well typed: `ProgOkX` at the instances it found, with the builtins' signatures `E.prim`, and the call of its `main` is typed in the initial context | `CheckSound.lean` (induction on the checker's fuel over its 7 functions; each success of the checker gives the rule whose side conditions it checked) |
| `checked_program_never_stuck` | the theorem instance for a corpus program: if the checker accepts it and its builtins respect their signatures (`PrimsOkX`), its run from `main`, with any arguments and any fuel, is never stuck and never leaves the core | `Theorems.lean` (`check_sound` + `type_soundness_full`) |
| `overlap_check_sound` | the decidable overlap check (`coherentB`: two impls of a trait clash at some position of their type patterns) gives `Coherent` | `TraitsCheck.lean` (`clash_sound`) |
| `orphan_rule_coherent` | with every impl in the module of its trait or of its type's head (the orphan rule), each module's impls checked against those of the modules it sees, the whole program's impls are coherent | `TraitsCheck.lean` (`orphan_coherent`) |
| `unlawful_eq_map_provenance`, `user_impls_capability_safe` | an arbitrary (inconsistent) user `Eq` breaks only functional results: the map holds only inserted keys and values; whatever user impls do, they get no authority (`capability_safety` for the elaborated program; `obligations_conserved` likewise, `TypeGaps.user_impls_obligations_conserved`) | `TypeGaps.lean` |

What the obligation theorems mean: they hold for every program, typed or
not, because the semantics enforces the rules dynamically. `type_soundness`
says the type system makes those dynamic checks unnecessary: a well-typed
program never trips them, so with `obligations_exactly_once` every linear
value it creates is consumed exactly once. `TypeExamples.lean` shows the
hypotheses are satisfiable (a program with a linear enum, `ProgOk` and
`PrimsOk` proved, a typed expression creating and consuming a linear value,
which the evaluator completes). `check_sound` connects the judgement to
programs: a program the Lean checker accepts is well typed, so
`checked_program_never_stuck` applies to it; the differential test compares
the Lean checker's verdicts with `tenon check`'s on the corpus (below).

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

## The checker (`TenonCore/Check.lean`)

A decision procedure for the stage-3 judgement, executable
(`tenon-core check`). It checks one function instance at a time, at concrete
types: `chk` (expressions), with `chkList`, `chkArgs`, `chkOpnds`,
`chkPath` and `chkArms` for the judgement's other relations, by recursion on
fuel. Its result is a type and the context left, or "no value" (every path
exits early: such an expression has every type, as `return` does).

- **Inference is untrusted.** An expected type flows down (an annotation
  `ann`, a parameter's type, the other operand of `==`) and may have holes;
  type arguments of a generic call are found by matching the parameter types
  with the arguments' types (`matchT`); a closure's result type, if not
  expected, by checking its body once without it. The soundness proof uses
  none of this: only the checks (`req`) of the inferred types against the
  rules' side conditions. Inference is local: `let xs = []` with no
  annotation and no expected type, a closure whose parameters' types come
  from a later use, and `dyn` values are rejected (below).
- **Instances.** A call at an instance the checker was not given fails with
  `Err.need`; the driver (`Front/Checker.lean`) adds it and checks again, from
  `main` and every monomorphic function of the program file, until no
  instance is missing. Then `checkAll` checks everything again with that
  list, and that is the verdict `check_sound` is about.
- **Declarations**: `AdtsOk` (a field's kind bounded by its type's, decided
  with type parameters counted as copyable), `StdOk`, the prelude's `Sys`.
- **Builtins**: the relation `prim` is a table (`Front/Checker.lean`,
  `primB`): the operators and the translator's builtins by hand, the
  prelude's `extern fn`s with the signatures the prelude declares, only the
  builtins the model implements. `PrimsOkX` (they respect the table) is an
  assumption about Prims.lean, per run (the builtins see the run's standard
  input): it is what `checked_program_never_stuck` assumes, and what the
  differential run confirms. The table was audited for builtins that are
  stuck or unsupported on well-typed arguments: a bad Float literal and
  `Int.char` outside the code points now trap, a format spec is part of the
  builtin's name (`%fmt:SPEC`, so its signature depends on it, as in `tenon
  check`), `write_bytes` (invalid UTF-8 output is outside the model) is not
  in the table.
- **Coherence**: before the program is checked, its impls must be
  coherent and obey the orphan rule (`coherence`, the decidable checks of
  `TraitsCheck.lean`; the main file sees the prelude, the prelude itself).

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
| struct literal `S { f: e, ..base }`, shorthand | `con S 0 [fields]` when the fields are given in declaration order; else each field once in source order (hidden `let`s), then `con`; an unknown field is unsupported |
| enum variant `V(e)`, `T.V`, `V` as a function value | `con T tag [e]`; a closure building it |
| closures `fn(x) => e` | `clos caps [x] e`, `caps` the local variables `e` uses; with annotated parameters, inside `ann (fn(T) -> R)` (a missing part a hole, `?`) |
| `let x: T = e`, `let (a, b): T = e` | `letE x (ann T e)`, `mtch (ann T e)` |
| `var (a, b) = e` | the pattern binds hidden names, then `var` lets of the names |
| `panic(m)` | `mtch (panic m) []`: no arm, so any type (even linear, as in `Option[Claim].unwrap()`); it traps first |
| `while true { ... }` without `break` ending a block | followed by an unreachable `panic` (the block has the type the context needs) |
| named function as a value, `Str.len` | `fnref` |
| `f(args)`, `mut x` arguments | `call (fnref f) args` (modes come from the callee at run time) |
| `x.m(args)`, `T.m(args)` | `mcall m x args` (receiver's type head), `call (fnref T.m)` |
| operators, `and`/`or`, `not`, `-x` | builtins `%add`...; `ite` (short circuit) |
| `"{e}"`, `"{e:SPEC}"` | `%show`, `%fmt:SPEC`, `%concat` |
| `const` | a function of no argument, called at every use (reference §12) |
| `linear struct`, `unique struct`, enums | `AdtDecl.kind`; tokens minted by `con` |
| methods `fn T.m(self ...)` | `FnDecl` keyed `T.m`, `owner := T` (finishes its own `self`); its parameter types start with `self`'s |
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
checker accepted a program that breaks a rule. Every program, accepted or
not, also goes through the Lean checker (`tenon-core check`); its verdict is
compared with `tenon check`'s and each disagreement classified (the patterns
are in the script: `LEAN_CLASSES`, `TENON_CLASSES`); a program the Lean
checker accepts is run on the core, which must not get stuck. It runs in the evidence loop
(`../ops/evidence/evidence.sh`, nightly) and writes `.evidence/formal_diff.json`
(STATUS.md).

Coverage on 2026-10-28 with stage 3 (858 corpus programs): 286 are
rejected by `tenon check` and not run, 29 do not parse; of the others,
**325 are in the core's subset and all agree with `tenon run`** (stdout and
exit status); none that `tenon check` accepts gets stuck in the core.
Outside: 67 unsupported constructs (fs/net/proc/workers builtins, modules,
Show impls the values do not decide, invalid UTF-8 on stdin), 13 too slow or
too deep for the core, 2 whose `main` returns a value no exit status has (a
program tenon rejects for that).

**The checker comparison.** `formal_diff.py` also runs `tenon-core check`
on every program (accepted or rejected by `tenon check`, tests/reject and
tests/v2/reject included: 162 reject tests are in the checker's subset).
The Lean checker's subset is 598 of 858 programs (260 unsupported: the
modeled builtins, Show impls, modules, no `fn main`). Of these:

| | Programs |
|---|---|
| both accept | 240 |
| both reject | 192 |
| tenon accepts, Lean rejects | 25 |
| tenon rejects, Lean accepts | 141 |

*Tenon accepts, Lean rejects* (the model or the checker too strict; none
gets stuck in the core, so none is the compiler being unsound): type
inference 14 (`let xs = []` typed by a later use, closures whose parameter
types come from a later use, `None`/`Ok(v)` with no expected type), `dyn`
types 5 (not in the checker), `linear`/`unique` values passed by `ref`/`mut`
4 (`ref_params`, `lin_ref_ok`, `trait_ref_param`,
`unique_moved_then_reassigned`), or-patterns binding names in different
orders 1 (`char_bounds`: `Left(n, s) | Right(s, n)`), polymorphic recursion 1
(monomorphization does not end; `tenon build` rejects it too).

*Tenon rejects, Lean accepts* (a rule the core's guarantees do not need):
derived traits on functions, capabilities, `dyn` values and Float map keys
41, naming, duplicates and shadowing 29, exhaustiveness and pattern rules 20
(the core traps on a missing case), trait declarations and bounds 17 (the
checker checks impls for coherence and the orphan rule, not their
signatures against the trait, and generic code at its instances only),
mutability and `mut` markers 14 (the core copies `ref`/`mut` arguments in
and out, so aliasing cannot be observed), constants 8, `main`'s signature 3,
modules 2, recursive types 2, type errors in generic code that is never
instantiated 2, `dyn` holding linear or unique values 2, and one linearity
rule the model shows unnecessary: `'|' patterns cannot bind linear values`
(tests/selfhost/lin_or_pattern.tn; a finding of low severity,
tests/redteam/FINDINGS-2026-10-28-formal.md). The list of files with their
messages is in `.evidence/formal_diff.json` (`checker`).

**Typed translation.** Of the 381 programs the Lean checker accepts, 367 ran
on the core to the end or to a trap; 14 ran out of fuel or stack (no theorem
excludes it); none got stuck: what `checked_program_never_stuck` says of each
of them, confirmed by running.

The stage-2 coverage (at `2e44f37`, 818 programs) was 295 in the subset, all
agreeing; stage 1, 254.

## Gate and times

`./check` runs `ops/gates/formal_check.sh` ("formal" in its table): under 1 s
warm on the development machine (Apple M4 Max), about 14 s for a full rebuild
of `formal/` (the first build on a new machine also downloads the
toolchain). It requires at least the 32 statements of `Theorems.lean` in the
axiom audit. CI installs elan and caches the toolchain and the build
(`.github/workflows/ci.yml`, `nightly.yml`). The differential test, with the
checker comparison, takes about 25 s on 8 cores.

## What remains (TODO)

1. **Effects and contracts** (milestone items 4-5) as they are designed: the
   next specifications.
2. **The stage-3 judgement, further**: `linear`/`unique` values passed by
   `ref`/`mut` (the core moves them out for the call and writes them back; a
   sound rule must also keep a later argument from refilling the variable,
   which needs the judgement to track the names being restored); `dyn` as a
   type (a value packed with the trait's method table, `Traits.dyn_dispatch`);
   impls of one trait for several instantiations of one type (the checker
   knows the static type and could select the impl; the core's method keys
   are per head); or-patterns binding names in different orders.
3. **Inference**: a unification pass before the checker (its output would
   be annotations, `ann`, which the checker verifies), for the 14 programs
   above.
4. **The checker's trait checks**: impls against their trait's signatures,
   bounds at the definition of generic code (it is checked at its instances
   now), object safety.
5. **Item 3**: the connection of `resolve` to a full `eval` of a user
   comparator inside the builtin sort, and a proof that the backends' actual
   sort (the interpreter's bottom-up merge sort, `Prims.lean`) is a stable
   sorted permutation, so `stable_sort_unique` applies to it.
6. `PrimsOkX` for the builtins themselves (they are assumed to respect the
   signature table; the differential run checks it), and the `keys` of
   `check_sound` for the translator (they are its `HashMap`'s; Std's
   `mem_toList_iff_getElem?_eq_some`).
7. Link the worker machine to the sequential core (a worker's local steps as
   core evaluations), and model `Fs` paths (the jail's `..` and symlink rules)
   beyond the attenuation order.
8. Widen the subset: modules, `decode`, the fs/net/proc builtins (as effects
   on a modeled world), workers, Show impls in the checker.

/-
The guarantees, as theorem statements (formal/README.md, "Theorems").

This file is guarded (ops/governance/guarded.txt, `theorems` rule): changing
or removing a statement below needs an owner approval line in
ops/governance/approvals.log, like weakening a guarded test
(ops/repo/approvals.py). Proofs may change freely; new theorems may be added.
Each statement is proved from the development in the other modules.
-/
import TenonCore.Capability
import TenonCore.LinearSafe
import TenonCore.Workers
import TenonCore.TypeSafeRest
import TenonCore.SubstTyping
import TenonCore.TypeGaps
import TenonCore.TypeGapsStable
import TenonCore.CheckSound
import TenonCore.TraitsCheck

namespace Tenon.Theorems
open Tenon

/-! ## Capabilities (reference §10) -/

/-- Attenuation only narrows: `Fs.within` and `Fs.read_only` give a capability below the one they start from. -/
theorem within_narrows (c : Cap) (segs : List String) : c.within segs ≤ c := Cap.within_le c segs

theorem readOnly_narrows (c : Cap) : c.readOnly ≤ c := Cap.readOnly_le c

/-- The attenuation order is transitive (so attenuating twice still narrows). -/
theorem attenuation_trans {a b c : Cap} (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := Cap.le_trans h1 h2

/-- No forging: whatever an expression (of any program, typed or not) returns,
keeps in its environment, or uses for an effect, is an attenuation of a
capability it was given. -/
theorem capability_safety (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (st : St) (e : Expr)
    (hρ : ∀ c ∈ envCaps ρ, ∃ a ∈ A, c ≤ a) (hst : ∀ ev ∈ st.out, ∃ a ∈ A, ev.cap ≤ a) :
    match eval P n ρ st e with
    | .ok v ρ' st' =>
      (∀ c ∈ v.caps, ∃ a ∈ A, c ≤ a) ∧ (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧
      (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .ctl _ ρ' st' => (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧ (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  Tenon.capability_safety P A n ρ st e hρ hst

/-- A program started with the capabilities `A` (its `Sys`) performs every
effect through an attenuation of one of them. -/
theorem no_authority_escalation (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (e : Expr)
    (hρ : envCaps ρ ⊆ A) :
    match eval P n ρ {} e with
    | .ok _ _ st' | .ctl _ _ st' | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  Tenon.no_authority_escalation P A n ρ e hρ

/-! ## Obligations (reference §12) -/

/-- Conservation: along any evaluation that ends with a value or an early exit,
every token is held, discharged or dropped exactly as often as it was held
before or minted; only unique tokens are dropped; minted tokens are distinct. -/
theorem obligations_conserved (P : Prog) (n : Nat) (ρ : Env) (st : St) (e : Expr) (hs : StOk st) :
    match eval P n ρ st e with
    | .ok v ρ' st' => Bal v.toks ρ' st' [] ρ st ∧ StOk st'
    | .ctl c ρ' st' => Bal (ctlToks c) ρ' st' [] ρ st ∧ StOk st'
    | .err _ => True :=
  Tenon.obligations_conserved P n ρ st e hs

/-- Exactly once: from a start holding no obligation, every token minted occurs
exactly once among the result, the final environment, the discharged and the
dropped ones; no other token occurs; a linear token is never dropped. -/
theorem obligations_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') :
    (∀ t ∈ st'.minted, (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 1) ∧
    (∀ t, t ∉ st'.minted → (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 0) ∧
    (∀ t ∈ st'.minted, t.lin = true → st'.dropped.count t = 0 ∧
      st'.burned.count t + (v.toks ++ envToks ρ').count t = 1) :=
  Tenon.obligations_exactly_once P n ρ e v ρ' st' hρ h

/-- A complete program (result and final environment hold no obligation) has
discharged every linear value it created exactly once. -/
theorem linear_discharged_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') (hv : v.toks = []) (hρ' : envToks ρ' = []) :
    ∀ t ∈ st'.minted, t.lin = true → st'.burned.count t = 1 ∧ st'.dropped.count t = 0 :=
  Tenon.linear_discharged_exactly_once P n ρ e v ρ' st' hρ h hv hρ'

/-! ## Workers (reference §18) -/

/-- Every step of the worker machine keeps every worker's reachable cells its own. -/
theorem step_isolated {cfg cfg' : Workers.Cfg} (hi : Workers.Isolated cfg) (hs : Workers.Step cfg cfg') :
    Workers.Isolated cfg' :=
  Workers.step_isolated hi hs

/-- Every configuration a program reaches from its start is isolated. -/
theorem run_isolated (rs : List Workers.HV) (hrs : ∀ v ∈ rs, v.locs = []) {cfg' : Workers.Cfg}
    (hs : Workers.Steps ⟨fun _ => none, 0, fun w => if w = 0 then some rs else none, fun _ => []⟩ cfg') :
    Workers.Isolated cfg' :=
  Workers.run_isolated rs hrs hs

/-- No data races: in an isolated configuration no cell is reachable from two workers. -/
theorem no_shared_cell {cfg : Workers.Cfg} (hi : Workers.Isolated cfg) {w1 w2 : Nat} {rs1 rs2 : List Workers.HV}
    {l : Nat} (h1 : cfg.workers w1 = some rs1) (h2 : cfg.workers w2 = some rs2)
    (r1 : Workers.Reach cfg.heap rs1 l) (r2 : Workers.Reach cfg.heap rs2 l) : w1 = w2 :=
  Workers.no_shared_cell hi h1 h2 r1 r2

/-- The `Send` rule matters: handing another worker a pointer instead of a copy breaks isolation. -/
theorem unchecked_sharing_breaks_isolation :
    ∃ cfg : Workers.Cfg, Workers.Isolated cfg ∧
      ¬ Workers.Isolated ⟨cfg.heap, cfg.next, Workers.upd cfg.workers 1 (some [.ptr 0]), cfg.chans⟩ :=
  Workers.unchecked_sharing_breaks_isolation

/-! ## Types (reference §5, §12, §17; Typing.lean, TypeSafe*.lean, Subst*.lean) -/

/-- **Type soundness** (definitional-interpreter style, with fuel). A
well-typed expression of a well-typed program (its functions typed at every
instance, its builtins respecting their signatures), run in an environment
that matches its context, never gets stuck: neither a type error nor a broken
obligation rule (a linear value copied, dropped or used after a move), and it
never reaches a construct outside the core. A value it returns has its type
and the final environment matches the context the judgement leaves; an early
`return` carries a value of the function's return type and happens only where
the judgement allows one; `break`/`continue` happen only inside a loop.
Running out of fuel and traps remain possible. Together with
`obligations_exactly_once` this is reference §12's static guarantee (every
linear value consumed exactly once) for every program the type system accepts. -/
theorem type_soundness (P : Prog) (prim : PrimSig) (hP : ProgOk P prim) (hprim : PrimsOk P prim)
    (Δ : Sig) (Γ Γ' : Ctx) (e : Expr) (t : Ty) (h : HasTy P prim Δ Γ e t Γ')
    (ρ : Env) (hρ : EnvOk P prim ρ Γ)
    (hΔ : Δ.fr ≤ Γ.length ∧ ∀ Γl, Δ.loop = some Γl → Γl.length ≤ Γ.length) (n : Nat) (st : St) :
    match eval P n ρ st e with
    | .ok v ρ' _ => ValTy P prim v t ∧ EnvOk P prim ρ' Γ'
    | .ctl (.ret v) _ _ => Δ.exitOk = true ∧ ValTy P prim v Δ.ret
    | .ctl _ _ _ => Δ.loop.isSome = true
    | .err (.stuck _ _) => False
    | .err (.unsup _) => False
    | .err _ => True := by
  have := (tySafe hP hprim n).eval Δ Γ Γ' e t ρ st h hρ hΔ
  revert this
  cases eval P n ρ st e with
  | ok v ρ' st' => intro h; exact ⟨h.1, h.2.1⟩
  | ctl c ρ' st' =>
    cases c with
    | ret v => intro h; exact ⟨h.1, h.2.1⟩
    | brk => intro h; obtain ⟨Γl, hl, -⟩ := h; simp [hl]
    | cont => intro h; obtain ⟨Γl, hl, -⟩ := h; simp [hl]
  | err e => cases e <;> intro h <;> first | trivial | exact h

/-- A well-typed program never gets stuck and never leaves the core, whatever the fuel. -/
theorem well_typed_never_stuck (P : Prog) (prim : PrimSig) (hP : ProgOk P prim) (hprim : PrimsOk P prim)
    (Δ : Sig) (Γ Γ' : Ctx) (e : Expr) (t : Ty) (h : HasTy P prim Δ Γ e t Γ')
    (ρ : Env) (hρ : EnvOk P prim ρ Γ)
    (hΔ : Δ.fr ≤ Γ.length ∧ ∀ Γl, Δ.loop = some Γl → Γl.length ≤ Γ.length) (n : Nat) (st : St) :
    (∀ k w, eval P n ρ st e ≠ .err (.stuck k w)) ∧ (∀ w, eval P n ρ st e ≠ .err (.unsup w)) := by
  have h' := type_soundness P prim hP hprim Δ Γ Γ' e t h ρ hρ hΔ n st
  refine ⟨fun k w heq => ?_, fun w heq => ?_⟩ <;> rw [heq] at h' <;> exact h'

/-- **Parametricity of the checker** (the substitution lemma): typing is
stable under substituting type parameters, for a program whose declarations
are well scoped and whose builtin signatures are parametric. A type parameter
counts as linear (`Ty.kind`), so an instance is never more restricted than the
generic code. -/
theorem typing_subst (P : Prog) (prim : PrimSig) (σ : List Ty) (hsc : ProgScoped P)
    (hprim : ∀ p ts r, prim p ts r → prim p (substL σ ts) (r.subst σ))
    (Δ Δ' : Sig) (hΔ : Δ'.ret = Δ.ret.subst σ ∧ Δ'.exitOk = Δ.exitOk ∧ Δ'.loop = Δ.loop.map (Ctx.subst σ) ∧
      Δ'.fr = Δ.fr ∧ ∀ Γ, Δ.fin Γ → Δ'.fin (Γ.subst σ))
    (Γ Γ' : Ctx) (e : Expr) (t : Ty) (h : HasTy P prim Δ Γ e t Γ') :
    HasTy P prim Δ' (Γ.subst σ) e (t.subst σ) (Γ'.subst σ) :=
  HasTy.subst hsc hprim h hΔ

/-- **Checking a generic function once suffices**: if every function's body is
well typed at its own type parameters, the program is well typed at every
instance (`ProgOk`, what `type_soundness` assumes). -/
theorem generic_check_once (P : Prog) (prim : PrimSig) (hA : AdtsOk P) (hS : StdOk P) (hsc : ProgScoped P)
    (hprim : ∀ σ p ts r, prim p ts r → prim p (substL σ ts) (r.subst σ))
    (h : ∀ f d, P.fns f = some d → d.params.length = d.ptys.length ∧
      ∃ Γ', HasTy P prim (fnSig P d.owner d.params d.ret) (paramsCtx d.params d.ptys) d.body d.ret Γ' ∧
        FinFn P d.owner d.params Γ') :
    ProgOk P prim :=
  Tenon.generic_check_once P prim hA hS hsc hprim h

/-! ## Traits and coherence (Traits.lean) -/

/-- Coherence: at most one impl of a trait applies to a type (no overlap). -/
theorem coherent_unique_impl {E : Traits.TraitEnv} (hC : Traits.Coherent E) {a b : Traits.ImplDecl} {tr : String}
    {args : List Ty} {t : Ty} {σ1 σ2 : Nat → Ty} (ha : a ∈ E.impls) (hb : b ∈ E.impls)
    (hma : Traits.Matches a tr args t σ1) (hmb : Traits.Matches b tr args t σ2) : a = b :=
  Traits.impl_unique hC ha hb hma hmb

/-- Method resolution is deterministic: for a type with an instance of a trait,
exactly one impl applies, and the evaluator's lookup (`resolve` on a value's
head, in the program with the impls elaborated) finds its method or the
trait's default body. -/
theorem method_resolution {P : Prog} {E : Traits.TraitEnv} (hC : Traits.Coherent E) (hH : Traits.HeadCoherent E)
    (hN : Traits.NoInherent P E) (hI : Traits.ImplsOk E) {tr : String} {args : List Ty} {t : Ty}
    (h : Traits.Holds E tr args t) :
    ∃ im, (im ∈ E.impls ∧ ∃ σ, Traits.Matches im tr args t σ) ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Traits.Matches im' tr args t σ') → im' = im) ∧
      ∀ T tm, E.trait tr = some T → tm ∈ T.methods → ∃ b,
        (Traits.findBody im.methods tm.name = some b ∨
          (Traits.findBody im.methods tm.name = none ∧ tm.dflt = some b)) ∧
        ∀ v : Val, v.head = t.head → resolve (Traits.withImpls P E) v.head tm.name = .tenon (Traits.mkDecl im tm b) :=
  Traits.method_resolution hC hH hN hI h

/-- Bounded generics: a call of a trait method on a value of a type parameter
whose bound is satisfied (at the instance, by impl derivations, generic impls
with their own bounds included) does not get stuck on method lookup. -/
theorem bounded_call_resolves {P : Prog} {E : Traits.TraitEnv} {sup : Bool} {Γ : List Traits.Bound}
    (hC : Traits.Coherent E) (hH : Traits.HeadCoherent E) (hN : Traits.NoInherent P E) (hI : Traits.ImplsOk E)
    (hT : Traits.TraitsOk E) (hS : sup = true → Traits.SuperOk E) (ς : Nat → Ty)
    (hΓ : ∀ b ∈ Γ, Traits.Holds E b.trait (b.args.map (Traits.tsub ς)) (Traits.tsub ς b.ty))
    {tr : String} {args : List Ty} {t : Ty} {T : Traits.TraitDecl} {tm : Traits.TMethod}
    (he : Traits.Entails E sup Γ tr args t) (hTr : E.trait tr = some T) (htm : tm ∈ T.methods)
    (v : Val) (hv : v.head = (Traits.tsub ς t).head) :
    ∃ im b, im ∈ E.impls ∧ (∃ σ, Traits.Matches im tr (args.map (Traits.tsub ς)) (Traits.tsub ς t) σ) ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Traits.Matches im' tr (args.map (Traits.tsub ς)) (Traits.tsub ς t) σ') →
        im' = im) ∧
      resolve (Traits.withImpls P E) v.head tm.name = .tenon (Traits.mkDecl im tm b) :=
  Traits.bounded_call_resolves hC hH hN hI hT hS ς hΓ he hTr htm v hv

/-- `dyn` dispatch is type-safe: a method call on a `dyn` value resolves to the
impl of the value's type, whose parameters are the trait method's and whose
signature is the trait's at that type. -/
theorem dyn_dispatch {P Q : Prog} {prim : PrimSig} {E : Traits.TraitEnv} (hC : Traits.Coherent E)
    (hH : Traits.HeadCoherent E) (hN : Traits.NoInherent P E) (hI : Traits.ImplsOk E) (hT : Traits.TraitsOk E)
    {tr : String} {args : List Ty} {t : Ty} {T : Traits.TraitDecl} {tm : Traits.TMethod} {v : Val}
    (hv : ValTy Q prim v t) (h : Traits.Holds E tr args t) (hTr : E.trait tr = some T) (htm : tm ∈ T.methods) :
    ∃ im σ b, im ∈ E.impls ∧ Traits.Matches im tr args t σ ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Traits.Matches im' tr args t σ') → im' = im) ∧
      resolve (Traits.withImpls P E) (Traits.pack v).head tm.name = .tenon (Traits.mkDecl im tm b) ∧
      (Traits.mkDecl im tm b).params = tm.params ∧
      (Traits.mkDecl im tm b).ptys.map (Traits.tsub σ) = tm.ptys.map (Traits.tsub (Traits.selfArgs t args)) ∧
      Traits.tsub σ (Traits.mkDecl im tm b).ret = Traits.tsub (Traits.selfArgs t args) tm.ret :=
  Traits.dyn_dispatch hC hH hN hI hT hv h hTr htm

/-! ## Milestone 3, item 3: user Eq/Ord/Hash (TypeGaps.lean, the specification) -/

/-- With a user `Ord` that is a total order, every correct sort gives the same
list: the backends cannot disagree. -/
theorem sort_unique {α : Type} {O : TypeGaps.UOrd α} (hO : O.TotalOrder) (f : List α → List α)
    (hf : ∀ l, (f l).Perm l ∧ TypeGaps.Sorted O.cmp (f l)) (l : List α) : f l = TypeGaps.isort O.cmp l :=
  TypeGaps.sort_unique hO f hf l

/-- With a lawful user `Ord` the sort is sorted; with any comparator it is a permutation. -/
theorem sort_sorted_perm {α : Type} {O : TypeGaps.UOrd α} (hO : O.Lawful) (l : List α) :
    TypeGaps.Sorted O.cmp (TypeGaps.isort O.cmp l) ∧ (TypeGaps.isort O.cmp l).Perm l :=
  ⟨TypeGaps.isort_sorted hO l, TypeGaps.isort_perm O.cmp l⟩

/-- Lawful user `Eq`/`Ord`/`Hash`: the ordered and hashed maps agree with the Eq map on every lookup. -/
theorem maps_agree {α β : Type} {E : TypeGaps.UEq α} {O : TypeGaps.UOrd α} (hO : O.Lawful)
    (hc : TypeGaps.Consistent E O) (hE : E.Lawful) {bk : α → Nat} (hH : TypeGaps.BucketLawful E bk)
    (ops : List (α × β)) (j : α) :
    TypeGaps.oget O.cmp j (TypeGaps.obuild O.cmp [] ops) = TypeGaps.mget E.eq j (TypeGaps.mbuild E.eq [] ops) ∧
    TypeGaps.hget E.eq bk j (TypeGaps.hbuild E.eq bk (fun _ => []) ops) =
      TypeGaps.mget E.eq j (TypeGaps.mbuild E.eq [] ops) :=
  ⟨TypeGaps.omap_agrees hO hc ops [] [] (fun _ => by simp [TypeGaps.oget, TypeGaps.mget]) j,
   TypeGaps.hmap_agrees hE hH ops (fun _ => []) [] (fun _ => by simp [TypeGaps.hget, TypeGaps.mget]) j⟩

/-- With a user `Ord` that is only a total preorder (distinct values may compare
equal), stable sorting is well defined: two stable sorts give the same list. -/
theorem stable_sort_unique {α : Type} {O : TypeGaps.UOrd α} (hO : O.Lawful) (f g : List α → List α)
    (hf : ∀ l, (f l).Perm l ∧ TypeGaps.Sorted O.cmp (f l)) (hg : ∀ l, (g l).Perm l ∧ TypeGaps.Sorted O.cmp (g l))
    (sf : TypeGaps.Stable O.cmp f) (sg : TypeGaps.Stable O.cmp g) (l : List α) : f l = g l :=
  TypeGaps.stable_sort_unique hO f g hf hg sf sg l

/-- The model sort is stable, and any two sorted permutations agree up to the user's `equal`. -/
theorem sort_stable_equiv {α : Type} {O : TypeGaps.UOrd α} (hO : O.Lawful) :
    TypeGaps.Stable O.cmp (TypeGaps.isort O.cmp) ∧
    ∀ l1 l2 : List α, TypeGaps.Sorted O.cmp l1 → TypeGaps.Sorted O.cmp l2 → l1.Perm l2 →
      TypeGaps.LRel (fun a b => O.cmp a b = .eq) l1 l2 :=
  ⟨TypeGaps.isort_stable hO, fun _ _ h1 h2 hp => TypeGaps.sorted_perm_equiv hO h1 h2 hp⟩

/-- An unlawful user `Eq` breaks only functional results: the map holds only inserted keys and values. -/
theorem unlawful_eq_map_provenance {α β : Type} (eq : α → α → Bool) (ops : List (α × β)) :
    TypeGaps.Prov ops (TypeGaps.mbuild eq [] ops) :=
  TypeGaps.mbuild_prov eq ops ops [] (fun _ h => h) (by simp [TypeGaps.Prov])

/-- Whatever user impls do, they obtain no authority (capability safety holds for the elaborated program). -/
theorem user_impls_capability_safe (P : Prog) (E : Traits.TraitEnv) (A : List Cap) (n : Nat) (ρ : Env) (st : St)
    (e : Expr) (hρ : ∀ c ∈ envCaps ρ, ∃ a ∈ A, c ≤ a) (hst : ∀ ev ∈ st.out, ∃ a ∈ A, ev.cap ≤ a) :
    match eval (Traits.withImpls P E) n ρ st e with
    | .ok v ρ' st' =>
      (∀ c ∈ v.caps, ∃ a ∈ A, c ≤ a) ∧ (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧
      (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .ctl _ ρ' st' => (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧ (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  TypeGaps.user_impls_capability_safe P E A n ρ st e hρ hst

/-! ## Stage 3: the loosened judgement and the checker (Typing.lean `Ext.stage3`, Check.lean) -/

/-- **Type soundness, stage 3**: the guarantee of `type_soundness` for the
loosened judgement (`HasTyX (Ext.stage3 I)`: closures capturing variables by
value, annotations, direct calls of builtins, `x.to_str()`, functions used
at the instances `I` the program is checked at). A well-typed expression of
a program well typed at its instances, run in an environment matching its
context, is never stuck and never leaves the core. -/
theorem type_soundness_full (I : String → List Ty → Prop) (P : Prog) (prim : PrimSig)
    (hP : ProgOkX (Ext.stage3 I) P prim) (hprim : PrimsOkX (Ext.stage3 I) P prim)
    (Δ : Sig) (Γ Γ' : Ctx) (e : Expr) (t : Ty) (h : HasTyX (Ext.stage3 I) P prim Δ Γ e t Γ')
    (ρ : Env) (hρ : EnvOkX (Ext.stage3 I) P prim ρ Γ)
    (hΔ : Δ.fr ≤ Γ.length ∧ ∀ Γl, Δ.loop = some Γl → Γl.length ≤ Γ.length) (n : Nat) (st : St) :
    match eval P n ρ st e with
    | .ok v ρ' _ => ValTyX (Ext.stage3 I) P prim v t ∧ EnvOkX (Ext.stage3 I) P prim ρ' Γ'
    | .ctl (.ret v) _ _ => Δ.exitOk = true ∧ ValTyX (Ext.stage3 I) P prim v Δ.ret
    | .ctl _ _ _ => Δ.loop.isSome = true
    | .err (.stuck _ _) => False
    | .err (.unsup _) => False
    | .err _ => True := by
  have := (tySafe hP hprim n).eval Δ Γ Γ' e t ρ st h hρ hΔ
  revert this
  cases eval P n ρ st e with
  | ok v ρ' st' => intro h; exact ⟨h.1, h.2.1⟩
  | ctl c ρ' st' =>
    cases c with
    | ret v => intro h; exact ⟨h.1, h.2.1⟩
    | brk => intro h; obtain ⟨Γl, hl, -⟩ := h; simp [hl]
    | cont => intro h; obtain ⟨Γl, hl, -⟩ := h; simp [hl]
  | err e => cases e <;> intro h <;> first | trivial | exact h

theorem insts_decide (L : List (String × List Ty)) :
    (fun f σ => decide ((f, σ) ∈ L) = true) = (fun f σ => (f, σ) ∈ L) := by
  funext f σ; simp

/-- **The checker is sound** (`check_sound`, tenon.md §6): a program the Lean
checker accepts (`Check.checkAll`; `keys` list its declared types) is well
typed in the stage-3 judgement at the instances `L` (`ProgOkX`), with the
builtins' signatures `E.prim`, and so is the call of its `main` from the
initial environment. -/
theorem check_sound (E : Check.CEnv) (fuel : Nat) (keys : List (String × AdtDecl)) (L : List (String × List Ty))
    (main : String) (arity : Nat) (h : Check.checkAll E fuel keys L main arity = .ok ())
    (hk : ∀ s d, E.P.adts s = some d → (s, d) ∈ keys) :
    ProgOkX (Ext.stage3 fun f σ => (f, σ) ∈ L) E.P (fun p ts t => E.prim p ts t = true) ∧
    ∃ t Γ', HasTyX (Ext.stage3 fun f σ => (f, σ) ∈ L) E.P (fun p ts t => E.prim p ts t = true)
      Check.topSig Check.sysCtx (Check.mainCall main arity) t Γ' := by
  have := Check.checkAll_sound h hk
  simp only [Check.XE, Check.CEnv.withInsts, insts_decide] at this
  exact ⟨this.1, this.2.2⟩

/-- **A checked program is never stuck** (the theorem instance for a corpus
program): if the Lean checker accepts a translated program, and its builtins
respect their signatures (`PrimsOkX`, the assumption about the builtins'
implementations), then its run from `main` with any arguments, with any
fuel, never gets stuck (no type error, no broken obligation rule) and never
reaches a construct outside the core. ops/gates/formal_diff.py confirms it by
running every program the checker accepts. -/
theorem checked_program_never_stuck (E : Check.CEnv) (fuel : Nat) (keys : List (String × AdtDecl))
    (L : List (String × List Ty)) (main : String) (arity : Nat) (h : Check.checkAll E fuel keys L main arity = .ok ())
    (hk : ∀ s d, E.P.adts s = some d → (s, d) ∈ keys)
    (hprim : PrimsOkX (Ext.stage3 fun f σ => (f, σ) ∈ L) E.P (fun p ts t => E.prim p ts t = true))
    (args : List String) (n : Nat) :
    (∀ k w, eval E.P n [("%sys", some (Check.sysVal args))] {} (Check.mainCall main arity) ≠ .err (.stuck k w)) ∧
    (∀ w, eval E.P n [("%sys", some (Check.sysVal args))] {} (Check.mainCall main arity) ≠ .err (.unsup w)) := by
  have hc := Check.checkAll_sound h hk
  simp only [Check.XE, Check.CEnv.withInsts, insts_decide] at hc
  obtain ⟨hP, hsys, t, Γ', hm⟩ := hc
  have hρ := Check.sysOkB_envOk (X := Ext.stage3 fun f σ => (f, σ) ∈ L)
    (prim := fun p ts t => E.prim p ts t = true) hsys args
  have h' := type_soundness_full _ E.P _ hP hprim Check.topSig Check.sysCtx Γ' _ t hm _ hρ
    ⟨Nat.zero_le _, fun _ h => by cases h⟩ n {}
  refine ⟨fun k w heq => ?_, fun w heq => ?_⟩ <;> rw [heq] at h' <;> exact h'

/-- **The overlap check is sound**: impls the decidable check accepts are coherent (no two overlap). -/
theorem overlap_check_sound (E : Traits.TraitEnv) (h : Traits.coherentB E.impls = true) : Traits.Coherent E :=
  Traits.coherentB_sound h

/-- **The orphan rule makes coherence modular**: with every impl in the module
of its trait or of its type's head, and each module's impls checked (decidably,
`localB`) against the impls of the modules it sees, the whole program's impls
are coherent. -/
theorem orphan_rule_coherent (traits : List Traits.TraitDecl) (impls : List Traits.ModImpl)
    (traitMod typeMod : String → Option String) (sees : String → String → Bool)
    (hvar : ∀ mi ∈ impls, Traits.isVar mi.im.self = false)
    (horph : impls.all (fun mi => traitMod mi.im.trait == some mi.mod || typeMod mi.im.self.head == some mi.mod) = true)
    (hvis : ∀ mi ∈ impls, (∀ m, traitMod mi.im.trait = some m → sees mi.mod m = true) ∧
      (∀ m, typeMod mi.im.self.head = some m → sees mi.mod m = true))
    (hloc : Traits.localB sees impls = true) :
    Traits.Coherent ⟨traits, impls.map (·.im)⟩ :=
  Traits.orphan_coherent_decided traits impls traitMod typeMod sees hvar horph hvis hloc

end Tenon.Theorems

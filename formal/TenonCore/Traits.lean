/-
Traits and coherence in the core (tenon.md §6 "Formal track"; reference §17).

The model. A trait declares type parameters, supertraits and methods (a
signature and an optional default body, a core `Expr`). An impl gives a trait
(at type arguments) for a type pattern (a `Ty` whose `Ty.var i` are the impl's
type parameters), with bounds on its parameters and method bodies. In a trait's
signatures `Ty.var 0` is `Self` and `Ty.var (j+1)` the trait's `j`-th type
parameter (`selfArgs`).

Elaboration (`withImpls`) is what the translator does with impls: the method `m` of
an impl for a type of head `H` becomes the `FnDecl` keyed `H ++ "." ++ m` in
`Prog.fns` (the trait's default body when the impl lacks the method), which is
what the evaluator's `resolve` (Eval.lean) looks up on the receiver value's
head (`Val.head`). A type's own (inherent) method of that name wins
(`inherent_wins`). A `dyn Trait` value is the value itself (`pack`): a call on
it dispatches on the head of the value inside, at run time.

Coherence (`Coherent`): no two impls of one trait overlap (their type patterns
and trait arguments unify), so at most one impl applies to a trait and type.
The core dispatches on the head only, so elaboration is faithful when the
method keys of all impls are distinct (`HeadCoherent`: also no two traits give
one type a method of the same name, which the reference makes an ambiguous
call). Impls for different instantiations of one head (`impl Show for
Box[Int]` and `impl Show for Box[Str]`) are coherent but not head-coherent:
the C backend monomorphizes them under distinct names; the core's head-keyed
`Prog.fns` cannot, and such programs are outside this elaboration.

Main results: `impl_unique`, `method_resolution` (determinism and agreement of
the lookup with the impl), `entails_sound` and `bounded_call_resolves`
(bounded generics do not get stuck on method lookup), `super_entails`
(supertraits), `dyn_dispatch` (dyn calls resolve to the type's impl, at the
trait's signature instantiated at that type).
-/
import TenonCore.Typing

namespace Tenon.Traits
open Tenon

/-! ## Substitution by a function (composes without side conditions) -/

mutual
/-- Replace `Ty.var i` by `σ i`. -/
def tsub (σ : Nat → Ty) : Ty → Ty
  | .tup ts => .tup (tsubL σ ts)
  | .list t => .list (tsub σ t)
  | .map k v => .map (tsub σ k) (tsub σ v)
  | .adt s as => .adt s (tsubL σ as)
  | .fn ps r => .fn (tsubL σ ps) (tsub σ r)
  | .var i => σ i
  | .int => .int | .bool => .bool | .str => .str | .unit => .unit
  | .cap k => .cap k
def tsubL (σ : Nat → Ty) : List Ty → List Ty
  | [] => []
  | t :: ts => tsub σ t :: tsubL σ ts
end

mutual
/-- The type variables a type mentions. -/
def fv : Ty → List Nat
  | .tup ts => fvL ts
  | .list t => fv t
  | .map k v => fv k ++ fv v
  | .adt _ as => fvL as
  | .fn ps r => fvL ps ++ fv r
  | .var i => [i]
  | .int | .bool | .str | .unit | .cap _ => []
def fvL : List Ty → List Nat
  | [] => []
  | t :: ts => fv t ++ fvL ts
end

theorem tsubL_eq_map (σ : Nat → Ty) : ∀ ts, tsubL σ ts = ts.map (tsub σ)
  | [] => rfl
  | t :: ts => by simp only [tsubL, List.map, tsubL_eq_map σ ts]

mutual
theorem tsub_tsub (σ τ : Nat → Ty) : ∀ t, tsub σ (tsub τ t) = tsub (fun i => tsub σ (τ i)) t
  | .tup ts => by simp only [tsub]; rw [tsubL_tsubL σ τ ts]
  | .list t => by simp only [tsub]; rw [tsub_tsub σ τ t]
  | .map k v => by simp only [tsub]; rw [tsub_tsub σ τ k, tsub_tsub σ τ v]
  | .adt s as => by simp only [tsub]; rw [tsubL_tsubL σ τ as]
  | .fn ps r => by simp only [tsub]; rw [tsubL_tsubL σ τ ps, tsub_tsub σ τ r]
  | .var _ => rfl
  | .int | .bool | .str | .unit | .cap _ => rfl
theorem tsubL_tsubL (σ τ : Nat → Ty) : ∀ ts, tsubL σ (tsubL τ ts) = tsubL (fun i => tsub σ (τ i)) ts
  | [] => rfl
  | t :: ts => by simp only [tsubL]; rw [tsub_tsub σ τ t, tsubL_tsubL σ τ ts]
end

mutual
theorem tsub_congr (σ τ : Nat → Ty) : ∀ t, (∀ i ∈ fv t, σ i = τ i) → tsub σ t = tsub τ t
  | .tup ts, h => by simp only [tsub]; rw [tsubL_congr σ τ ts (by simpa [fv] using h)]
  | .list t, h => by simp only [tsub]; rw [tsub_congr σ τ t (by simpa [fv] using h)]
  | .map k v, h => by
    simp only [fv, List.mem_append] at h
    simp only [tsub]
    rw [tsub_congr σ τ k (fun i hi => h i (.inl hi)), tsub_congr σ τ v (fun i hi => h i (.inr hi))]
  | .adt s as, h => by simp only [tsub]; rw [tsubL_congr σ τ as (by simpa [fv] using h)]
  | .fn ps r, h => by
    simp only [fv, List.mem_append] at h
    simp only [tsub]
    rw [tsubL_congr σ τ ps (fun i hi => h i (.inl hi)), tsub_congr σ τ r (fun i hi => h i (.inr hi))]
  | .var i, h => h i (by simp [fv])
  | .int, _ | .bool, _ | .str, _ | .unit, _ | .cap _, _ => rfl
theorem tsubL_congr (σ τ : Nat → Ty) : ∀ ts, (∀ i ∈ fvL ts, σ i = τ i) → tsubL σ ts = tsubL τ ts
  | [], _ => rfl
  | t :: ts, h => by
    simp only [fvL, List.mem_append] at h
    simp only [tsubL]
    rw [tsub_congr σ τ t (fun i hi => h i (.inl hi)), tsubL_congr σ τ ts (fun i hi => h i (.inr hi))]
end

mutual
/-- The list substitution of Typing.lean (`Ty.subst`, used by `ValTy`) is `tsub`
of the function that leaves the variables beyond the list alone. -/
theorem subst_eq_tsub (σ : List Ty) : ∀ t, t.subst σ = tsub (fun i => σ[i]?.getD (.var i)) t
  | .tup ts => by simp only [Ty.subst, tsub]; rw [substL_eq_tsubL σ ts]
  | .list t => by simp only [Ty.subst, tsub]; rw [subst_eq_tsub σ t]
  | .map k v => by simp only [Ty.subst, tsub]; rw [subst_eq_tsub σ k, subst_eq_tsub σ v]
  | .adt s as => by simp only [Ty.subst, tsub]; rw [substL_eq_tsubL σ as]
  | .fn ps r => by simp only [Ty.subst, tsub]; rw [substL_eq_tsubL σ ps, subst_eq_tsub σ r]
  | .var _ => rfl
  | .int | .bool | .str | .unit | .cap _ => rfl
theorem substL_eq_tsubL (σ : List Ty) : ∀ ts, substL σ ts = tsubL (fun i => σ[i]?.getD (.var i)) ts
  | [] => rfl
  | t :: ts => by simp only [substL, tsubL]; rw [subst_eq_tsub σ t, substL_eq_tsubL σ ts]
end

/-- Is the type a bare type variable (a pattern that would match every type)? -/
def isVar : Ty → Bool
  | .var _ => true
  | _ => false

/-- Substitution keeps the head of a type that is not a variable. -/
theorem head_tsub (σ : Nat → Ty) : ∀ t, isVar t = false → (tsub σ t).head = t.head
  | .var _, h => by simp [isVar] at h
  | .tup _, _ | .list _, _ | .map _ _, _ | .adt _ _, _ | .fn _ _, _ => rfl
  | .int, _ | .bool, _ | .str, _ | .unit, _ | .cap _, _ => rfl

/-- A value of a type has that type's head: the head `resolve` dispatches on is
the head of the static type. -/
theorem ValTy.head_eq {P : Prog} {prim : PrimSig} {v : Val} {t : Ty} (h : ValTy P prim v t) : v.head = t.head := by
  cases h <;> rfl

/-- `Self` and the trait's type arguments as a substitution (`var 0` = Self). -/
def selfArgs (t : Ty) (args : List Ty) : Nat → Ty := fun i => (t :: args)[i]?.getD (.var i)

/-- Instantiating a signature at `Self := t` and then substituting is
instantiating it at the substituted `Self` and arguments (for a signature that
mentions only `Self` and the trait's parameters). -/
theorem selfArgs_comp (ς : Nat → Ty) (t : Ty) (args : List Ty) (a : Ty)
    (h : ∀ i ∈ fv a, i < args.length + 1) :
    tsub ς (tsub (selfArgs t args) a) = tsub (selfArgs (tsub ς t) (args.map (tsub ς))) a := by
  rw [tsub_tsub]
  apply tsub_congr
  intro i hi
  have hl := h i hi
  cases i with
  | zero => simp [selfArgs]
  | succ j =>
    have hj : j < args.length := by omega
    simp [selfArgs, List.getElem?_eq_getElem hj]

/-! ## Declarations -/

/-- A method of a trait. The types mention `Self` (`var 0`) and the trait's
type parameters (`var (j+1)`). -/
structure TMethod where
  name : String
  /-- The parameters with their modes, `self` first. -/
  params : List (String × Mode)
  /-- The types of the parameters after `self`. -/
  ptys : List Ty
  ret : Ty
  /-- A default body (it may call the trait's other methods on `self`). -/
  dflt : Option Expr := none

/-- A bound `ty: trait[args]`. -/
structure Bound where
  ty : Ty
  trait : String
  args : List Ty := []

structure TraitDecl where
  name : String
  tparams : Nat := 0
  /-- Supertraits with their arguments (in terms of `Self` and the trait's parameters). -/
  supers : List (String × List Ty) := []
  methods : List TMethod

/-- `impl[tparams: bounds] trait[targs] for self { methods }`. -/
structure ImplDecl where
  trait : String
  targs : List Ty := []
  tparams : Nat := 0
  self : Ty
  bounds : List Bound := []
  methods : List (String × Expr)
  /-- The owner given to the elaborated methods (the type's key when the impl
  is in the type's module: it may finish a linear `self`). -/
  owner : Option String := none

structure TraitEnv where
  traits : List TraitDecl
  impls : List ImplDecl

def TraitEnv.trait (E : TraitEnv) (n : String) : Option TraitDecl := E.traits.find? (·.name == n)

theorem TraitEnv.trait_mem {E : TraitEnv} {n : String} {T : TraitDecl} (h : E.trait n = some T) :
    T ∈ E.traits := List.mem_of_find?_eq_some h

/-! ## Instances and coherence -/

/-- The impl `im` applies to `trait[args]` for `t`, by the substitution `σ` of its parameters. -/
def Matches (im : ImplDecl) (tr : String) (args : List Ty) (t : Ty) (σ : Nat → Ty) : Prop :=
  im.trait = tr ∧ tsub σ im.self = t ∧ im.targs.map (tsub σ) = args

/-- Two impls overlap: some type and trait arguments are an instance of both
(their patterns unify once their parameters are renamed apart). -/
def Overlap (a b : ImplDecl) : Prop :=
  ∃ σ1 σ2, tsub σ1 a.self = tsub σ2 b.self ∧ a.targs.map (tsub σ1) = b.targs.map (tsub σ2)

/-- Coherence (reference §17): no two impls of one trait overlap (in
particular no type implements a trait twice). -/
def Coherent (E : TraitEnv) : Prop :=
  E.impls.Pairwise fun a b => a.trait = b.trait → ¬ Overlap a b

/-- The instance relation: `t` implements `tr[args]`, by a derivation tree
through impls (a generic impl applies where its own bounds hold). -/
inductive Holds (E : TraitEnv) : String → List Ty → Ty → Prop
  | impl {im : ImplDecl} {σ : Nat → Ty} {tr : String} {args : List Ty} {t : Ty} :
      im ∈ E.impls → Matches im tr args t σ →
      (∀ b ∈ im.bounds, Holds E b.trait (b.args.map (tsub σ)) (tsub σ b.ty)) →
      Holds E tr args t

/-- What a generic context with the bounds `Γ` entails (the checker's view
inside `fn f[T: A + B]` or an impl with bounds): an assumed bound, an impl
whose bounds are entailed, or (when `sup`) a supertrait of an entailed trait. -/
inductive Entails (E : TraitEnv) (sup : Bool) (Γ : List Bound) : String → List Ty → Ty → Prop
  | assume {b : Bound} : b ∈ Γ → Entails E sup Γ b.trait b.args b.ty
  | impl {im : ImplDecl} {σ : Nat → Ty} {tr : String} {args : List Ty} {t : Ty} :
      im ∈ E.impls → Matches im tr args t σ →
      (∀ b ∈ im.bounds, Entails E sup Γ b.trait (b.args.map (tsub σ)) (tsub σ b.ty)) →
      Entails E sup Γ tr args t
  | super {tr : String} {args : List Ty} {t : Ty} {T : TraitDecl} {s : String × List Ty} :
      sup = true → Entails E sup Γ tr args t → E.trait tr = some T → args.length = T.tparams →
      s ∈ T.supers → Entails E sup Γ s.1 (s.2.map (tsub (selfArgs t args))) t

/-- Traits are well formed: supertrait arguments and method signatures mention
only `Self` and the trait's parameters. -/
def TraitsOk (E : TraitEnv) : Prop :=
  ∀ T ∈ E.traits,
    (∀ s ∈ T.supers, ∀ a ∈ s.2, ∀ i ∈ fv a, i < T.tparams + 1) ∧
    ∀ tm ∈ T.methods, (∀ p ∈ tm.ptys, ∀ i ∈ fv p, i < T.tparams + 1) ∧ ∀ i ∈ fv tm.ret, i < T.tparams + 1

/-- The supertrait rule, semantically: whatever implements a trait implements
its supertraits (at the supertrait arguments instantiated at it). -/
def SuperOk (E : TraitEnv) : Prop :=
  ∀ tr args t T, Holds E tr args t → E.trait tr = some T → args.length = T.tparams →
    ∀ s ∈ T.supers, Holds E s.1 (s.2.map (tsub (selfArgs t args))) t

/-- The supertrait rule as the checker checks it, impl by impl: an impl of a
subtrait has the impls of its supertraits, derivable from its own bounds
(without going through supertraits, which keeps the check well founded). -/
def ImplSupersOk (E : TraitEnv) : Prop :=
  ∀ im ∈ E.impls, ∀ T, E.trait im.trait = some T → ∀ s ∈ T.supers,
    Entails E false im.bounds s.1 (s.2.map (tsub (selfArgs im.self im.targs))) im.self

/-! ## Elaboration into the core program -/

def findBody : List (String × Expr) → String → Option Expr
  | [], _ => none
  | (n, b) :: r, m => if n = m then some b else findBody r m

/-- The body an impl gives a trait method: its own, else the trait's default. -/
def implBody (im : ImplDecl) (tm : TMethod) : Option Expr := (findBody im.methods tm.name).or tm.dflt

/-- The core function of an impl's method: the trait's parameters and modes,
its signature instantiated at the impl's type pattern, generic in the impl's
type parameters. -/
def mkDecl (im : ImplDecl) (tm : TMethod) (b : Expr) : FnDecl where
  params := tm.params
  body := b
  owner := im.owner
  tparams := im.tparams
  ptys := tm.ptys.map (tsub (selfArgs im.self im.targs))
  ret := tsub (selfArgs im.self im.targs) tm.ret

/-- The key of a method of an impl: the head of its type, as `resolve` builds it. -/
def mkey (im : ImplDecl) (m : String) : String := im.self.head ++ "." ++ m

def implEntries (T : TraitDecl) (im : ImplDecl) : List (String × FnDecl) :=
  T.methods.filterMap fun tm => (implBody im tm).map fun b => (mkey im tm.name, mkDecl im tm b)

/-- The method table of all impls. -/
def table (E : TraitEnv) : List (String × FnDecl) :=
  E.impls.flatMap fun im => match E.trait im.trait with
    | some T => implEntries T im
    | none => []

def tfind : List (String × FnDecl) → String → Option FnDecl
  | [], _ => none
  | (k', d) :: r, k => if k' = k then some d else tfind r k

/-- The program with the impls' methods added (a type's own methods first). -/
def withImpls (P : Prog) (E : TraitEnv) : Prog :=
  { P with fns := fun k => (P.fns k).or (tfind (table E) k) }

/-- Head coherence: the method keys of all impls are distinct (a decidable check). -/
def HeadCoherent (E : TraitEnv) : Prop := ((table E).map (·.1)).Nodup

/-- No impl method is shadowed by a type's own method of the same name. -/
def NoInherent (P : Prog) (E : TraitEnv) : Prop := ∀ e ∈ table E, P.fns e.1 = none

/-- Impls are well formed: their trait exists, at its arity; the type pattern is
not a bare variable (the core dispatches on its head); every method has a body. -/
def ImplsOk (E : TraitEnv) : Prop :=
  ∀ im ∈ E.impls, ∃ T, E.trait im.trait = some T ∧ im.targs.length = T.tparams ∧
    isVar im.self = false ∧ ∀ tm ∈ T.methods, (implBody im tm).isSome

/-- A `dyn Trait` value is the value itself (reference §17: a `dyn` passed to
`dyn` again is unchanged); its methods are found on its head at run time. -/
def pack (v : Val) : Val := v

/-! ## Lemmas -/

theorem pairwise_mem {α} {R : α → α → Prop} :
    ∀ {l : List α}, l.Pairwise R → ∀ {a b}, a ∈ l → b ∈ l → a = b ∨ R a b ∨ R b a
  | [], _, _, _, ha, _ => by cases ha
  | x :: r, h, a, b, ha, hb => by
    rw [List.pairwise_cons] at h
    rcases List.mem_cons.1 ha with h1 | ha' <;> rcases List.mem_cons.1 hb with h2 | hb'
    · exact .inl (h1.trans h2.symm)
    · subst h1; exact .inr (.inl (h.1 _ hb'))
    · subst h2; exact .inr (.inr (h.1 _ ha'))
    · exact pairwise_mem h.2 ha' hb'

theorem tfind_of_mem : ∀ {l : List (String × FnDecl)} {k : String} {d : FnDecl},
    (l.map (·.1)).Nodup → (k, d) ∈ l → tfind l k = some d
  | [], _, _, _, h => by cases h
  | (k', d') :: r, k, d, hn, h => by
    simp only [List.map, List.nodup_cons] at hn
    rcases List.mem_cons.1 h with h | h
    · cases h; simp [tfind]
    · have hk : k' ≠ k := fun e => hn.1 (e ▸ List.mem_map_of_mem (f := (·.1)) h)
      simp [tfind, hk, tfind_of_mem hn.2 h]

theorem mem_table {E : TraitEnv} {im : ImplDecl} {T : TraitDecl} {tm : TMethod} {b : Expr}
    (him : im ∈ E.impls) (hT : E.trait im.trait = some T) (htm : tm ∈ T.methods)
    (hb : implBody im tm = some b) : (mkey im tm.name, mkDecl im tm b) ∈ table E := by
  unfold table
  rw [List.mem_flatMap]
  refine ⟨im, him, ?_⟩
  rw [hT]
  unfold implEntries
  rw [List.mem_filterMap]
  exact ⟨tm, htm, by simp [hb]⟩

/-- The body `implBody` picks is the impl's own method, or the trait's default when the impl lacks it. -/
theorem implBody_cases {im : ImplDecl} {tm : TMethod} {b : Expr} (h : implBody im tm = some b) :
    findBody im.methods tm.name = some b ∨ (findBody im.methods tm.name = none ∧ tm.dflt = some b) := by
  unfold implBody at h
  cases hf : findBody im.methods tm.name with
  | none => rw [hf] at h; exact .inr ⟨rfl, by simpa [Option.or] using h⟩
  | some b' => rw [hf] at h; simp [Option.or] at h; exact .inl (by rw [h])

theorem holds_inv {E : TraitEnv} {tr : String} {args : List Ty} {t : Ty} (h : Holds E tr args t) :
    ∃ im σ, im ∈ E.impls ∧ Matches im tr args t σ := by
  cases h with
  | impl him hm _ => exact ⟨_, _, him, hm⟩

/-! ## (1) Method resolution is deterministic -/

/-- **Unique impl.** Under coherence, at most one impl applies to a trait (at
given arguments) and a type. -/
theorem impl_unique {E : TraitEnv} (hC : Coherent E) {a b : ImplDecl} {tr : String} {args : List Ty}
    {t : Ty} {σ1 σ2 : Nat → Ty} (ha : a ∈ E.impls) (hb : b ∈ E.impls)
    (hma : Matches a tr args t σ1) (hmb : Matches b tr args t σ2) : a = b := by
  obtain ⟨ta, sa, aa⟩ := hma
  obtain ⟨tb, sb, ab⟩ := hmb
  rcases pairwise_mem hC ha hb with h | h | h
  · exact h
  · exact absurd ⟨σ1, σ2, sa.trans sb.symm, aa.trans ab.symm⟩ (h (ta.trans tb.symm))
  · exact absurd ⟨σ2, σ1, sb.trans sa.symm, ab.trans aa.symm⟩ (h (tb.trans ta.symm))

/-- The elaborated lookup of an impl's method: `resolve` on the impl type's
head finds the elaborated method (no type's own method shadows it). -/
theorem resolve_impl {P : Prog} {E : TraitEnv} (hH : HeadCoherent E) (hN : NoInherent P E)
    {im : ImplDecl} {T : TraitDecl} {tm : TMethod} {b : Expr}
    (him : im ∈ E.impls) (hT : E.trait im.trait = some T) (htm : tm ∈ T.methods)
    (hb : implBody im tm = some b) :
    resolve (withImpls P E) im.self.head tm.name = .tenon (mkDecl im tm b) := by
  have hm := mem_table him hT htm hb
  have h1 : P.fns (mkey im tm.name) = none := hN _ hm
  have h2 := tfind_of_mem hH hm
  unfold mkey at h1 h2
  simp [resolve, withImpls, h1, h2, Option.or]

/-- A type's own method wins over a trait's (reference §17, "Calling"). -/
theorem inherent_wins (P : Prog) (E : TraitEnv) {k : String} {d : FnDecl} (h : P.fns k = some d) :
    (withImpls P E).fns k = some d := by
  simp [withImpls, h, Option.or]

/-- **Method resolution is deterministic** (1). For a coherent, head-coherent,
well-formed set of impls, if `t` implements `tr[args]` then exactly one impl
applies, and for every method of the trait the elaborated program's lookup on
any value of head `t.head` returns that impl's method: its own body, or the
trait's default when it lacks the method. -/
theorem method_resolution {P : Prog} {E : TraitEnv} (hC : Coherent E) (hH : HeadCoherent E)
    (hN : NoInherent P E) (hI : ImplsOk E) {tr : String} {args : List Ty} {t : Ty}
    (h : Holds E tr args t) :
    ∃ im, (im ∈ E.impls ∧ ∃ σ, Matches im tr args t σ) ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Matches im' tr args t σ') → im' = im) ∧
      ∀ T tm, E.trait tr = some T → tm ∈ T.methods → ∃ b,
        (findBody im.methods tm.name = some b ∨ (findBody im.methods tm.name = none ∧ tm.dflt = some b)) ∧
        ∀ v : Val, v.head = t.head → resolve (withImpls P E) v.head tm.name = .tenon (mkDecl im tm b) := by
  obtain ⟨im, σ, him, hm⟩ := holds_inv h
  refine ⟨im, ⟨him, σ, hm⟩, fun im' him' ⟨σ', hm'⟩ => impl_unique hC him' him hm' hm, ?_⟩
  intro T tm hT htm
  obtain ⟨T', hT', _, hv, hall⟩ := hI im him
  rw [hm.1, hT] at hT'
  cases hT'
  obtain ⟨b, hb⟩ := Option.isSome_iff_exists.1 (hall tm htm)
  refine ⟨b, implBody_cases hb, fun v hvh => ?_⟩
  have hhead : t.head = im.self.head := by rw [← hm.2.1]; exact head_tsub σ _ hv
  rw [hvh, hhead]
  exact resolve_impl hH hN him (hm.1 ▸ hT) htm hb

/-! ## (2) Bounded generics -/

/-- **Soundness of entailment.** If the bounds `Γ` of a generic function hold
at its type arguments `ς` (each by an impl derivation), then everything the
checker derives from them inside the function holds at `ς`. With `sup` the
derivation may use supertraits, which needs the supertrait rule `SuperOk`. -/
theorem entails_sound {E : TraitEnv} {sup : Bool} {Γ : List Bound} (hS : sup = true → SuperOk E)
    (hT : TraitsOk E) (ς : Nat → Ty)
    (hΓ : ∀ b ∈ Γ, Holds E b.trait (b.args.map (tsub ς)) (tsub ς b.ty))
    {tr : String} {args : List Ty} {t : Ty} (h : Entails E sup Γ tr args t) :
    Holds E tr (args.map (tsub ς)) (tsub ς t) := by
  induction h with
  | assume hb => exact hΓ _ hb
  | @impl im σ tr args t him hm _ ih =>
    obtain ⟨htr, hs, ha⟩ := hm
    refine Holds.impl (σ := fun i => tsub ς (σ i)) him ⟨htr, ?_, ?_⟩ ?_
    · rw [← hs, tsub_tsub]
    · rw [← ha, List.map_map]; apply List.map_congr_left; intro x _; simp [tsub_tsub]
    · intro b hb
      have := ih b hb
      rw [List.map_map, tsub_tsub] at this
      have e : (tsub ς ∘ tsub σ) = tsub (fun i => tsub ς (σ i)) := by
        funext x; simp [tsub_tsub]
      rwa [e] at this
  | @super tr args t T s hsup _ hTr hlen hs ih =>
    have h1 := hS hsup tr _ _ T ih hTr (by simpa using hlen) s hs
    have hok := (hT T (TraitEnv.trait_mem hTr)).1 s hs
    rw [List.map_map]
    have e : s.2.map (tsub ς ∘ tsub (selfArgs t args)) =
        s.2.map (tsub (selfArgs (tsub ς t) (args.map (tsub ς)))) := by
      apply List.map_congr_left
      intro a ha
      exact selfArgs_comp ς t args a (fun i hi => hlen ▸ hok a ha i hi)
    rw [e]; exact h1

/-- The per-impl supertrait check gives the supertrait rule. -/
theorem superOk_of_impls {E : TraitEnv} (hT : TraitsOk E) (hI : ImplsOk E) (hIS : ImplSupersOk E) :
    SuperOk E := by
  intro tr args t T h hTr _ s hs
  cases h with
  | @impl im σ _ _ _ him hm hb =>
    obtain ⟨htr, hself, hargs⟩ := hm
    have hTr' : E.trait im.trait = some T := htr ▸ hTr
    have he := entails_sound (sup := false) (fun h => by cases h) hT σ hb (hIS im him T hTr' s hs)
    obtain ⟨T', hT', hlen, _, _⟩ := hI im him
    rw [hTr'] at hT'
    cases hT'
    have hok := (hT T (TraitEnv.trait_mem hTr)).1 s hs
    rw [List.map_map] at he
    have e : s.2.map (tsub σ ∘ tsub (selfArgs im.self im.targs)) = s.2.map (tsub (selfArgs t args)) := by
      apply List.map_congr_left
      intro a ha
      simp only [Function.comp]
      rw [selfArgs_comp σ im.self im.targs a (fun i hi => hlen ▸ hok a ha i hi), hself, hargs]
    rw [e, hself] at he
    exact he

/-- **Supertrait entailment.** A bound `T: Sub` entails `T: Super` for every
supertrait `Super` of `Sub`: whatever satisfies the subtrait satisfies the
supertrait (given the supertrait rule, e.g. by `superOk_of_impls`). -/
theorem super_entails {E : TraitEnv} (hS : SuperOk E) (hT : TraitsOk E) {Γ : List Bound}
    {tr : String} {args : List Ty} {t : Ty} {T : TraitDecl} {s : String × List Ty}
    (hTr : E.trait tr = some T) (hlen : args.length = T.tparams) (hs : s ∈ T.supers)
    (ς : Nat → Ty) (hΓ : ∀ b ∈ Γ, Holds E b.trait (b.args.map (tsub ς)) (tsub ς b.ty))
    (h : Entails E true Γ tr args t) :
    Holds E s.1 ((s.2.map (tsub (selfArgs t args))).map (tsub ς)) (tsub ς t) :=
  entails_sound (fun _ => hS) hT ς hΓ (.super rfl h hTr hlen hs)

/-- **Bounded generic calls do not get stuck on method lookup** (2). Inside a
generic function with bounds `Γ`, the checker accepts `x.m()` for `x : t` when
`Γ` entails `t: tr[args]` and `m` is a method of `tr`. At any type arguments `ς`
satisfying the bounds (each by a derivation through impls, generic impls with
their own bounds included), on any value whose head is that of the
instantiated type, `resolve` returns a Tenon function: the method of the one
impl that applies. -/
theorem bounded_call_resolves {P : Prog} {E : TraitEnv} {sup : Bool} {Γ : List Bound}
    (hC : Coherent E) (hH : HeadCoherent E) (hN : NoInherent P E) (hI : ImplsOk E)
    (hT : TraitsOk E) (hS : sup = true → SuperOk E) (ς : Nat → Ty)
    (hΓ : ∀ b ∈ Γ, Holds E b.trait (b.args.map (tsub ς)) (tsub ς b.ty))
    {tr : String} {args : List Ty} {t : Ty} {T : TraitDecl} {tm : TMethod}
    (he : Entails E sup Γ tr args t) (hTr : E.trait tr = some T) (htm : tm ∈ T.methods)
    (v : Val) (hv : v.head = (tsub ς t).head) :
    ∃ im b, im ∈ E.impls ∧ (∃ σ, Matches im tr (args.map (tsub ς)) (tsub ς t) σ) ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Matches im' tr (args.map (tsub ς)) (tsub ς t) σ') → im' = im) ∧
      resolve (withImpls P E) v.head tm.name = .tenon (mkDecl im tm b) := by
  obtain ⟨im, ⟨him, hm⟩, huniq, hres⟩ :=
    method_resolution (P := P) hC hH hN hI (entails_sound hS hT ς hΓ he)
  obtain ⟨b, _, hr⟩ := hres T tm hTr htm
  exact ⟨im, b, him, hm, huniq, hr v hv⟩

/-- The same, for a value typed by the static semantics (`ValTy`, Typing.lean). -/
theorem bounded_call_resolves_typed {P Q : Prog} {prim : PrimSig} {E : TraitEnv} {sup : Bool} {Γ : List Bound}
    (hC : Coherent E) (hH : HeadCoherent E) (hN : NoInherent P E) (hI : ImplsOk E)
    (hT : TraitsOk E) (hS : sup = true → SuperOk E) (ς : Nat → Ty)
    (hΓ : ∀ b ∈ Γ, Holds E b.trait (b.args.map (tsub ς)) (tsub ς b.ty))
    {tr : String} {args : List Ty} {t : Ty} {T : TraitDecl} {tm : TMethod}
    (he : Entails E sup Γ tr args t) (hTr : E.trait tr = some T) (htm : tm ∈ T.methods)
    (v : Val) (hv : ValTy Q prim v (tsub ς t)) :
    ∃ d, resolve (withImpls P E) v.head tm.name = .tenon d := by
  obtain ⟨im, b, _, _, _, h⟩ :=
    bounded_call_resolves (P := P) hC hH hN hI hT hS ς hΓ he hTr htm v (ValTy.head_eq hv)
  exact ⟨_, h⟩

/-! ## (3) dyn dispatch -/

/-- **dyn dispatch is type-safe** (3). Packing a value of a type `t` that
implements `tr[args]` into a `dyn` and calling a trait method `m` resolves, at
run time on the value's head, to the method of the one impl that applies to
`t`; its parameters and modes are the trait's, and its signature, at the impl
parameters that make the impl's pattern `t`, is the trait's signature
instantiated at `Self := t` and the trait arguments. -/
theorem dyn_dispatch {P Q : Prog} {prim : PrimSig} {E : TraitEnv} (hC : Coherent E) (hH : HeadCoherent E)
    (hN : NoInherent P E) (hI : ImplsOk E) (hT : TraitsOk E)
    {tr : String} {args : List Ty} {t : Ty} {T : TraitDecl} {tm : TMethod} {v : Val}
    (hv : ValTy Q prim v t) (h : Holds E tr args t) (hTr : E.trait tr = some T) (htm : tm ∈ T.methods) :
    ∃ im σ b, im ∈ E.impls ∧ Matches im tr args t σ ∧
      (∀ im', im' ∈ E.impls → (∃ σ', Matches im' tr args t σ') → im' = im) ∧
      resolve (withImpls P E) (pack v).head tm.name = .tenon (mkDecl im tm b) ∧
      (mkDecl im tm b).params = tm.params ∧
      (mkDecl im tm b).ptys.map (tsub σ) = tm.ptys.map (tsub (selfArgs t args)) ∧
      tsub σ (mkDecl im tm b).ret = tsub (selfArgs t args) tm.ret := by
  obtain ⟨im, ⟨him, σ, hm⟩, huniq, hres⟩ := method_resolution (P := P) hC hH hN hI h
  obtain ⟨b, _, hr⟩ := hres T tm hTr htm
  obtain ⟨T', hT', hlen, _, _⟩ := hI im him
  rw [hm.1, hTr] at hT'
  cases hT'
  have hok := (hT T (TraitEnv.trait_mem hTr)).2 tm htm
  refine ⟨im, σ, b, him, hm, huniq, hr v (ValTy.head_eq hv), rfl, ?_, ?_⟩
  · simp only [mkDecl, List.map_map]
    apply List.map_congr_left
    intro p hp
    simp only [Function.comp]
    rw [selfArgs_comp σ im.self im.targs p (fun i hi => hlen ▸ hok.1 p hp i hi), hm.2.1, hm.2.2]
  · simp only [mkDecl]
    rw [selfArgs_comp σ im.self im.targs tm.ret (fun i hi => hlen ▸ hok.2 i hi), hm.2.1, hm.2.2]

/-- `dyn Trait(x)` of a `dyn` value is unchanged. -/
theorem pack_pack (v : Val) : pack (pack v) = pack v := rfl

/-! ## A decidable sufficient condition for coherence -/

/-- Impls of one trait whose type patterns have distinct heads never overlap. -/
theorem coherent_of_heads {E : TraitEnv} (hv : ∀ im ∈ E.impls, isVar im.self = false)
    (hd : E.impls.Pairwise fun a b => a.trait = b.trait → a.self.head ≠ b.self.head) : Coherent E := by
  unfold Coherent
  have : ∀ l : List ImplDecl, l ⊆ E.impls →
      l.Pairwise (fun a b => a.trait = b.trait → a.self.head ≠ b.self.head) →
      l.Pairwise (fun a b => a.trait = b.trait → ¬ Overlap a b) := by
    intro l hl hp
    induction hp with
    | nil => exact .nil
    | @cons a l' hr _ ih =>
      refine .cons (fun b hb htr ⟨σ1, σ2, hs, _⟩ => hr b hb htr ?_) (ih fun x hx => hl (.tail _ hx))
      have ha := hv a (hl (.head _))
      have hb' := hv b (hl (.tail _ hb))
      rw [← head_tsub σ1 _ ha, ← head_tsub σ2 _ hb', hs]
  exact this _ (fun _ h => h) hd

/-! ## Elaboration changes only the functions -/

theorem withImpls_adts (P : Prog) (E : TraitEnv) : (withImpls P E).adts = P.adts := rfl
theorem withImpls_prim (P : Prog) (E : TraitEnv) : (withImpls P E).prim = P.prim := rfl

end Tenon.Traits

/-
The static semantics of Tenon Core: types, kinds, the typing judgement with
obligation tracking, value and environment typing, well-formed programs
(formal/README.md, "TODO: type soundness").

Only definitions: the soundness theorem that connects them to the evaluator
is stated in formal/Todo/TypeSoundness.lean (not built by the gate). The
judgement threads a context whose entries record whether a variable still
holds its value (`avail`), as the checker's moved-set does (compiler/cklin.tn).
-/
import TenonCore.Eval

namespace Tenon

/-! ## Types -/

mutual
/-- Substitute the type parameters (`Ty.var i` is the `i`-th of `σ`). -/
def Ty.subst (σ : List Ty) : Ty → Ty
  | .tup ts => .tup (substL σ ts)
  | .list t => .list (t.subst σ)
  | .map k v => .map (k.subst σ) (v.subst σ)
  | .adt s as => .adt s (substL σ as)
  | .fn ps r => .fn (substL σ ps) (r.subst σ)
  | .var i => σ[i]?.getD (.var i)
  | t => t
def substL (σ : List Ty) : List Ty → List Ty
  | [] => []
  | t :: ts => t.subst σ :: substL σ ts
end

def Kind.join : Kind → Kind → Kind
  | .linear, _ | _, .linear => .linear
  | .unique, _ | _, .unique => .unique
  | _, _ => .copy

mutual
/-- How a value of the type may be used: linear or unique if its declared type is,
or if a type argument is (`Option[Claim]` is linear). -/
def Ty.kind (P : Prog) : Ty → Kind
  | .tup ts => kindL P ts
  | .adt s as => Kind.join ((P.adts s).elim .copy (·.kind)) (kindL P as)
  | _ => .copy
def kindL (P : Prog) : List Ty → Kind
  | [] => .copy
  | t :: ts => Kind.join (t.kind P) (kindL P ts)
end

def Ty.copyable (P : Prog) (t : Ty) : Prop := t.kind P = .copy
def Ty.linear (P : Prog) (t : Ty) : Prop := t.kind P = .linear

instance (P : Prog) (t : Ty) : Decidable (t.copyable P) := inferInstanceAs (Decidable (_ = _))
instance (P : Prog) (t : Ty) : Decidable (t.linear P) := inferInstanceAs (Decidable (_ = _))

/-- The head that selects a type's methods, as `Val.head` does for values. -/
def Ty.head : Ty → String
  | .int => "Int" | .bool => "Bool" | .str => "Str" | .unit => "Unit"
  | .tup _ => "Tuple" | .list _ => "List" | .map _ _ => "Map"
  | .adt s _ => s | .fn _ _ => "Fn" | .var _ => "?"
  | .cap k => match k with
    | .console => "Console" | .fs => "Fs" | .clock => "Clock"
    | .net => "Net" | .proc => "Proc" | .workers => "Workers"

def Lit.ty : Lit → Ty
  | .int _ => .int | .bool _ => .bool | .str _ => .str | .unit => .unit

/-! ## Contexts -/

structure Entry where
  name : String
  ty : Ty
  mutable : Bool
  avail : Bool      -- false: moved out

abbrev Ctx := List Entry

def Ctx.find (Γ : Ctx) (x : String) : Option Entry := Γ.find? (·.name = x)

def Ctx.setAvail (Γ : Ctx) (x : String) (a : Bool) : Ctx :=
  Γ.map fun e => if e.name = x then { e with avail := a } else e

/-- No variable of the context still holds a linear value (all were consumed). -/
def Ctx.noLinear (P : Prog) (Γ : Ctx) : Prop := ∀ e ∈ Γ, e.avail = true → ¬ e.ty.linear P

/-- The static facts about where an expression is: the program, the type
builtins have, the enclosing function's return type and owner, and the
context length at the innermost loop. -/
structure Sig where
  P : Prog
  prim : String → List Ty → Ty → Prop   -- a builtin's signature at given argument types
  ret : Ty
  owner : Option String
  loop : Option Nat

/-! ## The judgement -/

mutual
/-- `HasTy Δ Γ e t Γ'`: `e` has type `t` in `Γ`, leaving `Γ'` (what it moved). -/
inductive HasTy : Sig → Ctx → Expr → Ty → Ctx → Prop
  | lit {Δ Γ l} : HasTy Δ Γ (.lit l) l.ty Γ
  /-- A whole variable: a copy, or a move of an obligation. -/
  | var {Δ Γ x e} : Γ.find x = some e → e.avail = true →
      HasTy Δ Γ (.place x []) e.ty (if e.ty.copyable Δ.P then Γ else Γ.setAvail x false)
  /-- A part of a variable: only a copy. -/
  | part {Δ Γ x ps e t Γ'} : Γ.find x = some e → e.avail = true → ps ≠ [] → PathTy Δ Γ e.ty ps t Γ' →
      t.copyable Δ.P → HasTy Δ Γ (.place x ps) t Γ'
  | proj {Δ Γ e ps t0 t Γ1 Γ2} : HasTy Δ Γ e t0 Γ1 → t0.copyable Δ.P → PathTy Δ Γ1 t0 ps t Γ2 →
      HasTy Δ Γ (.proj e ps) t Γ2
  | tup {Δ Γ es ts Γ'} : ListTy Δ Γ es ts Γ' → HasTy Δ Γ (.seq .tup es) (.tup ts) Γ'
  | list {Δ Γ es t Γ'} : ListTy Δ Γ es (es.map fun _ => t) Γ' → t.copyable Δ.P → HasTy Δ Γ (.seq .list es) (.list t) Γ'
  | con {Δ Γ s} {tag : Nat} {es d name ts args Γ'} : Δ.P.adts s = some d → d.variants[tag]? = some (name, ts) →
      args.length = d.tparams → ListTy Δ Γ es (substL args ts) Γ' → HasTy Δ Γ (.con s tag es) (.adt s args) Γ'
  /-- A closure sees the variables without obligations, by value; it cannot assign them. -/
  | lam {Δ Γ ps body ts r} : ps.length = ts.length →
      HasTy { Δ with ret := r, loop := none }
        ((ps.zip ts).map (fun (x, t) => ⟨x, t, false, true⟩) ++
          (Γ.filter (fun e => e.avail && decide (e.ty.copyable Δ.P))).map ({ · with mutable := false })) body r
        ((ps.zip ts).map (fun (x, t) => ⟨x, t, false, true⟩) ++
          (Γ.filter (fun e => e.avail && decide (e.ty.copyable Δ.P))).map ({ · with mutable := false })) →
      HasTy Δ Γ (.lam ps body) (.fn ts r) Γ
  | fnref {Δ Γ f d σ} : Δ.P.fns f = some d → (∀ p ∈ d.params, p.2 = .val) → σ.length = d.tparams →
      HasTy Δ Γ (.fnref f) (.fn (substL σ d.ptys) (d.ret.subst σ)) Γ
  /-- A call of a function value: every argument by value. -/
  | callv {Δ Γ f args ts r Γ1 Γ2} : HasTy Δ Γ f (.fn ts r) Γ1 → ArgsTy Δ Γ1 (args.map fun _ => .val) args ts Γ2 →
      HasTy Δ Γ (.call f args) r Γ2
  /-- A direct call: arguments by the parameters' modes. -/
  | call {Δ Γ f d σ args Γ'} : Δ.P.fns f = some d → σ.length = d.tparams →
      ArgsTy Δ Γ (d.params.map (·.2)) args (substL σ d.ptys) Γ' → HasTy Δ Γ (.call (.fnref f) args) (d.ret.subst σ) Γ'
  | mcall {Δ Γ m recv args t0 d σ Γ1 Γ'} : HasTy Δ Γ recv t0 Γ1 → Δ.P.fns (t0.head ++ "." ++ m) = some d →
      σ.length = d.tparams → ArgsTy Δ Γ (d.params.map (·.2)) (recv :: args) (substL σ d.ptys) Γ' →
      HasTy Δ Γ (.mcall m recv args) (d.ret.subst σ) Γ'
  | prim {Δ Γ p args ts t Γ'} : Δ.prim p ts t → OpndsTy Δ Γ args ts Γ' → t.copyable Δ.P → HasTy Δ Γ (.prim p args) t Γ'
  /-- No shadowing; a linear variable must be consumed by the end of its scope. -/
  | letE {Δ Γ x mu e body t t' Γ1 a Γ2} : Γ.find x = none → HasTy Δ Γ e t Γ1 →
      HasTy Δ (⟨x, t, mu, true⟩ :: Γ1) body t' (⟨x, t, mu, a⟩ :: Γ2) → (a = true → ¬ t.linear Δ.P) →
      HasTy Δ Γ (.letE x mu e body) t' Γ2
  /-- Assignment: never over a live linear value; a moved unique variable may get a new one. -/
  | assign {Δ Γ x e t en Γ1} : Γ.find x = some en → en.mutable = true → en.ty = t → HasTy Δ Γ e t Γ1 →
      ¬ (en.avail = true ∧ t.linear Δ.P) → HasTy Δ Γ (.assign x [] e) .unit (Γ1.setAvail x true)
  | assignPart {Δ Γ x ps e t en Γ1 Γ2} : Γ.find x = some en → en.mutable = true → en.avail = true → ps ≠ [] →
      PathTy Δ Γ en.ty ps t Γ1 → HasTy Δ Γ1 e t Γ2 → t.copyable Δ.P → HasTy Δ Γ (.assign x ps e) .unit Γ2
  | seqE {Δ Γ e1 e2 t1 t Γ1 Γ2} : HasTy Δ Γ e1 t1 Γ1 → ¬ t1.linear Δ.P → HasTy Δ Γ1 e2 t Γ2 →
      HasTy Δ Γ (.seqE e1 e2) t Γ2
  /-- Both branches leave the same context (every path consumes the same obligations). -/
  | ite {Δ Γ c a b t Γ1 Γ2} : HasTy Δ Γ c .bool Γ1 → HasTy Δ Γ1 a t Γ2 → HasTy Δ Γ1 b t Γ2 →
      HasTy Δ Γ (.ite c a b) t Γ2
  | mtch {Δ Γ e arms t0 t Γ1 Γ2} : HasTy Δ Γ e t0 Γ1 → ArmsTy Δ Γ1 t0 arms t Γ2 → HasTy Δ Γ (.mtch e arms) t Γ2
  /-- A loop cannot consume what it did not create. -/
  | while {Δ Γ c body t Γ1} : HasTy Δ Γ c .bool Γ → HasTy { Δ with loop := some Γ.length } Γ body t Γ1 →
      Γ1 = Γ → ¬ t.linear Δ.P → HasTy Δ Γ (.while c body) .unit Γ
  /-- An early exit: every obligation must be consumed first; it has any type. -/
  | ret {Δ Γ e Γ1 t Γ'} : HasTy Δ Γ e Δ.ret Γ1 → Γ1.noLinear Δ.P → HasTy Δ Γ (.ret e) t Γ'
  | brk {Δ Γ k t Γ'} : Δ.loop = some k → Ctx.noLinear Δ.P (Γ.take (Γ.length - k)) → HasTy Δ Γ .brk t Γ'
  | cont {Δ Γ k t Γ'} : Δ.loop = some k → Ctx.noLinear Δ.P (Γ.take (Γ.length - k)) → HasTy Δ Γ .cont t Γ'
  | tryOpt {Δ Γ e t t' Γ1} : HasTy Δ Γ e (.adt "Option" [t]) Γ1 → Δ.ret = .adt "Option" [t'] →
      Γ1.noLinear Δ.P → HasTy Δ Γ (.try e) t Γ1
  | tryRes {Δ Γ e t t' er Γ1} : HasTy Δ Γ e (.adt "Result" [t, er]) Γ1 → Δ.ret = .adt "Result" [t', er] →
      Γ1.noLinear Δ.P → HasTy Δ Γ (.try e) t Γ1

inductive ListTy : Sig → Ctx → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : ListTy Δ Γ [] [] Γ
  | cons {Δ Γ e es t ts Γ1 Γ2} : HasTy Δ Γ e t Γ1 → ListTy Δ Γ1 es ts Γ2 → ListTy Δ Γ (e :: es) (t :: ts) Γ2

/-- Arguments by mode: a `ref`/`mut` argument is a whole variable (or a part without obligations), kept by the caller. -/
inductive ArgsTy : Sig → Ctx → List Mode → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : ArgsTy Δ Γ [] [] [] Γ
  | val {Δ Γ e es ms t ts Γ1 Γ2} : HasTy Δ Γ e t Γ1 → ArgsTy Δ Γ1 ms es ts Γ2 →
      ArgsTy Δ Γ (.val :: ms) (e :: es) (t :: ts) Γ2
  | ref {Δ Γ x en es ms ts Γ2} : Γ.find x = some en → en.avail = true → ArgsTy Δ Γ ms es ts Γ2 →
      ArgsTy Δ Γ (.ref :: ms) (.place x [] :: es) (en.ty :: ts) Γ2
  | mut {Δ Γ x en es ms ts Γ2} : Γ.find x = some en → en.avail = true → en.mutable = true →
      ArgsTy Δ Γ ms es ts Γ2 → ArgsTy Δ Γ (.mut :: ms) (.place x [] :: es) (en.ty :: ts) Γ2

/-- A builtin's operands: places are inspected; other values have no obligation. -/
inductive OpndsTy : Sig → Ctx → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : OpndsTy Δ Γ [] [] Γ
  | place {Δ Γ x ps en t es ts Γ1 Γ2} : Γ.find x = some en → en.avail = true → PathTy Δ Γ en.ty ps t Γ1 →
      OpndsTy Δ Γ1 es ts Γ2 → OpndsTy Δ Γ (.place x ps :: es) (t :: ts) Γ2
  | val {Δ Γ e t es ts Γ1 Γ2} : (∀ x ps, e ≠ .place x ps) → HasTy Δ Γ e t Γ1 → t.copyable Δ.P →
      OpndsTy Δ Γ1 es ts Γ2 → OpndsTy Δ Γ (e :: es) (t :: ts) Γ2

/-- The type at the end of a path (index expressions are typed and may not move obligations). -/
inductive PathTy : Sig → Ctx → Ty → List PStep → Ty → Ctx → Prop
  | nil {Δ Γ t} : PathTy Δ Γ t [] t Γ
  | fld {Δ Γ s args f ps d i ft t Γ'} : Δ.P.adts s = some d → d.isStruct = true → idxOf f d.fields = some i →
      (d.variants.head?.map (·.2)).bind (·[i]?) = some ft → PathTy Δ Γ (ft.subst args) ps t Γ' →
      PathTy Δ Γ (.adt s args) (.fld f :: ps) t Γ'
  | tfld {Δ Γ ts i ps ti t Γ'} : ts[i]? = some ti → PathTy Δ Γ ti ps t Γ' →
      PathTy Δ Γ (.tup ts) (.tfld i :: ps) t Γ'
  | idxList {Δ Γ e el ps t Γ1 Γ2} : HasTy Δ Γ e .int Γ1 → PathTy Δ Γ1 el ps t Γ2 →
      PathTy Δ Γ (.list el) (.idx e :: ps) t Γ2
  | idxMap {Δ Γ e k v ps t Γ1 Γ2} : HasTy Δ Γ e k Γ1 → k.copyable Δ.P → PathTy Δ Γ1 v ps t Γ2 →
      PathTy Δ Γ (.map k v) (.idx e :: ps) t Γ2

/-- Arms: the patterns fit the matched type, guards only on values without
obligations, the names a pattern binds are consumed (if linear) by the end of
the arm, and every arm leaves the same context. -/
inductive ArmsTy : Sig → Ctx → Ty → List (Pat × Option Expr × Expr) → Ty → Ctx → Prop
  | nil {Δ Γ t0 t Γ'} : ArmsTy Δ Γ t0 [] t Γ'
  | cons {Δ Γ t0 p g body arms t bs Γ' Γb} : PatTy Δ.P p t0 bs →
      (g.isSome → t0.copyable Δ.P) →
      (∀ ge, g = some ge → HasTy Δ (bs.map (fun (x, t) => ⟨x, t, false, true⟩) ++ Γ) ge .bool
        (bs.map (fun (x, t) => ⟨x, t, false, true⟩) ++ Γ)) →
      HasTy Δ (bs.map (fun (x, t) => ⟨x, t, false, true⟩) ++ Γ) body t (Γb ++ Γ') → Γb.length = bs.length →
      Ctx.noLinear Δ.P Γb → ArmsTy Δ Γ t0 arms t Γ' → ArmsTy Δ Γ t0 ((p, g, body) :: arms) t Γ'

/-- A pattern against a type, and the names it binds; `_` cannot drop a linear part. -/
inductive PatTy : Prog → Pat → Ty → List (String × Ty) → Prop
  | wild {P t} : ¬ t.linear P → PatTy P .wild t []
  | bind {P x t} : PatTy P (.bind x) t [(x, t)]
  | lit {P l} : PatTy P (.lit l) l.ty []
  | tup {P ps ts bs} : PatsTy P ps ts bs → PatTy P (.tup ps) (.tup ts) bs
  | con {P c ps s args d} {tag : Nat} {ts bs} : P.adts s = some d → d.isStruct = false → d.variants[tag]? = some (c, ts) →
      PatsTy P ps (substL args ts) bs → PatTy P (.con c ps) (.adt s args) bs
  | alt {P ps t bs} : (∀ p ∈ ps, PatTy P p t bs) → ps ≠ [] → PatTy P (.alt ps) t bs

inductive PatsTy : Prog → List Pat → List Ty → List (String × Ty) → Prop
  | nil {P} : PatsTy P [] [] []
  | cons {P p ps t ts b bs} : PatTy P p t b → PatsTy P ps ts bs → PatsTy P (p :: ps) (t :: ts) (b ++ bs)
end

/-! ## Values and environments -/

/-- A value of a type. Tokens match kinds: a value of a linear (unique)
declared type carries a linear (unique) token, others carry none. -/
inductive ValTy (P : Prog) : Val → Ty → Prop
  | int {i} : ValTy P (.int i) .int
  | bool {b} : ValTy P (.bool b) .bool
  | str {s} : ValTy P (.str s) .str
  | unit : ValTy P .unit .unit
  | tup {vs ts} : vs.length = ts.length → (∀ p ∈ vs.zip ts, ValTy P p.1 p.2) → ValTy P (.seq .tup vs) (.tup ts)
  | list {vs t} : (∀ v ∈ vs, ValTy P v t) → ValTy P (.seq .list vs) (.list t)
  | map {kvs k v} : (∀ e ∈ kvs, (entryKV e).isSome) →
      (∀ e ∈ kvs, ∀ a b, entryKV e = some (a, b) → ValTy P a k) →
      (∀ e ∈ kvs, ∀ a b, entryKV e = some (a, b) → ValTy P b v) →
      ValTy P (.seq .map kvs) (.map k v)
  | adt {s} {tag : Nat} {tok vs d name ts args} : P.adts s = some d → d.variants[tag]? = some (name, ts) →
      vs.length = ts.length → (∀ p ∈ vs.zip (substL args ts), ValTy P p.1 p.2) →
      (match d.kind, tok with
       | .copy, none => True
       | .linear, some t => t.lin = true
       | .unique, some t => t.lin = false
       | _, _ => False) →
      ValTy P (.adt s tag tok vs) (.adt s args)
  | fn {f d σ} : P.fns f = some d → (∀ p ∈ d.params, p.2 = .val) → σ.length = d.tparams →
      ValTy P (.fn f) (.fn (substL σ d.ptys) (d.ret.subst σ))
  | cap {c} : ValTy P (.cap c) (.cap c.kind)

/-- The runtime environment matches the context, entry by entry: a variable
that is available holds a value of its type; a moved one holds nothing (or a
value without obligations, which is never used again). -/
def EnvOk (P : Prog) : Env → Ctx → Prop
  | [], [] => True
  | (x, s) :: ρ, e :: Γ => x = e.name ∧ EnvOk P ρ Γ ∧
      (e.avail = true → ∃ v, s = some v ∧ ValTy P v e.ty) ∧
      (e.avail = false → ∀ v, s = some v → v.toks = [])
  | _, _ => False

/-! ## Programs -/

/-- Every function is well typed at every instance of its type parameters
(generic code is checked at the types it is used with: monomorphization,
reference §17); its by-value parameters hold no obligation at its end, except
`self` in a method of its own type. -/
def ProgOk (P : Prog) (prim : String → List Ty → Ty → Prop) : Prop :=
  ∀ f d, P.fns f = some d → d.params.length = d.ptys.length →
    ∀ σ : List Ty, σ.length = d.tparams →
      ∃ Γ', HasTy ⟨P, prim, d.ret.subst σ, d.owner, none⟩
        ((d.params.zip (substL σ d.ptys)).map fun (p, t) => ⟨p.1, t, p.2 == .mut, true⟩) d.body (d.ret.subst σ) Γ' ∧
        ∀ e ∈ Γ', e.avail = true → e.ty.linear P → e.name = "self" ∧ d.owner.isSome

/-- The builtins respect their signatures: on arguments of the signature's
types they return a value of its type without obligations, or trap. -/
def PrimsOk (P : Prog) (prim : String → List Ty → Ty → Prop) : Prop :=
  ∀ p ts t, prim p ts t → ∃ pf, P.prim p = some pf ∧ ∀ vs w, vs.length = ts.length →
    (∀ q ∈ vs.zip ts, ValTy P q.1 q.2) →
    match pf vs w with
    | .ok v self _ _ => ValTy P v t ∧ (∀ s, self = some s → ∃ t0 ∈ ts.head?, ValTy P s t0)
    | .trap _ => True
    | _ => False

end Tenon

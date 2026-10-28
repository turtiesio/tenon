/-
The static semantics of Tenon Core (formal/README.md, "Type soundness"):
types, kinds, the typing judgement with obligation tracking, value and
environment typing, well-formed programs and builtins.

The judgement `HasTy P prim Δ Γ e t Γ'` threads a context whose entries
record whether a variable still holds its value (`avail`), as the checker's
moved-set does (compiler/cklin.tn). `Δ` (`Sig`) says where the expression
is: the enclosing function's return type and frame, whether an early exit is
allowed here (`exitOk`, false while a linear temporary is held: a `return`
then would lose it), and the context of the innermost loop.

TypeSafe.lean proves the judgement sound for the evaluator (Eval.lean): a
well-typed expression never gets stuck (neither a type error nor a broken
obligation rule) and never reaches a construct outside the core;
Subst.lean proves it stable under substituting type parameters.
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

def Kind.rank : Kind → Nat
  | .copy => 0 | .unique => 1 | .linear => 2

/-- `a` is at most as restrictive as `b` (copy ≤ unique ≤ linear). -/
def Kind.le (a b : Kind) : Prop := a.rank ≤ b.rank

mutual
/-- How a value of the type may be used: linear or unique if its declared type
is, or if a component is (`Option[Claim]` is linear). A type parameter counts
as linear: generic code may not copy or drop a `T` (it may be instantiated by
a linear type), which makes typing stable under substitution (Subst.lean). -/
def Ty.kind (P : Prog) : Ty → Kind
  | .tup ts => kindL P ts
  | .list t => t.kind P
  | .map k v => Kind.join (k.kind P) (v.kind P)
  | .adt s as => Kind.join ((P.adts s).elim .copy (·.kind)) (kindL P as)
  | .var _ => .linear
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

def Ty.isVar : Ty → Bool
  | .var _ => true
  | _ => false

def Lit.ty : Lit → Ty
  | .int _ => .int | .bool _ => .bool | .str _ => .str | .unit => .unit

/-! ## Contexts -/

structure Entry where
  name : String
  ty : Ty
  mutable : Bool
  avail : Bool      -- false: moved out

abbrev Ctx := List Entry

/-- The innermost entry of a name (as `lookup` finds the innermost slot). -/
def Ctx.find : Ctx → String → Option Entry
  | [], _ => none
  | e :: Γ, x => if e.name = x then some e else Ctx.find Γ x

/-- Mark the innermost entry of `x` (as `update` changes the innermost slot). -/
def Ctx.setAvail : Ctx → String → Bool → Ctx
  | [], _, _ => []
  | e :: Γ, x, a => if e.name = x then { e with avail := a } :: Γ else e :: Ctx.setAvail Γ x a

/-- `x` is in scope and still holds its value. -/
def Ctx.Avail (Γ : Ctx) (x : String) : Prop := ∃ e, Γ.find x = some e ∧ e.avail = true

/-- `x` is in scope at type `T` and still holds its value. -/
def Ctx.AvailAt (Γ : Ctx) (x : String) (T : Ty) : Prop := ∃ e, Γ.find x = some e ∧ e.avail = true ∧ e.ty = T

/-- No variable of the context still holds a linear value (all were consumed). -/
def Ctx.noLinear (P : Prog) (Γ : Ctx) : Prop := ∀ e ∈ Γ, e.avail = true → ¬ e.ty.linear P

/-- The same variables with the same types (only availability differs). -/
def Entry.key (e : Entry) : String × Ty × Bool := (e.name, e.ty, e.mutable)
def Shape (Γ' Γ : Ctx) : Prop := Γ'.map Entry.key = Γ.map Entry.key

/-- The context of a frame: the parameters (a `mut` one is assignable). -/
def paramsCtx : List (String × Mode) → List Ty → Ctx
  | p :: ps, t :: ts => ⟨p.1, t, p.2 == .mut, true⟩ :: paramsCtx ps ts
  | _, _ => []

/-- The names a pattern binds, as context entries. -/
def bindCtx (bs : List (String × Ty)) : Ctx := bs.map fun b => ⟨b.1, b.2, false, true⟩

/-! ## Frames -/

/-- `self`, by value, in a method of its own linear or unique type: the method's
end discharges it (`endParam`), provided its fields hold no linear value. -/
def SelfFin (P : Prog) (owner : Option String) (p : String) (t : Ty) : Prop :=
  p = "self" ∧ ∃ o d args, owner = some o ∧ t = .adt o args ∧ P.adts o = some d ∧ d.kind ≠ .copy ∧
    ∀ v ∈ d.variants, ∀ ft ∈ v.2, ¬ (ft.subst args).linear P

/-- What a parameter must be at the end of its function: a by-value one holds
no linear value (or is a discharged `self`); a `ref`/`mut` one still holds its value
(it is written back). -/
def FinEntry (P : Prog) (owner : Option String) (p : String × Mode) (e : Entry) : Prop :=
  match p.2 with
  | .val => e.avail = true → ¬ e.ty.linear P ∨ SelfFin P owner p.1 e.ty
  | _ => e.avail = true

def FinFn (P : Prog) (owner : Option String) : List (String × Mode) → Ctx → Prop
  | [], [] => True
  | p :: ps, e :: Γ => FinEntry P owner p e ∧ FinFn P owner ps Γ
  | _, _ => False

/-- Where an expression is: the enclosing function's return type, whether an
early exit may happen here, the innermost loop's context, and the frame (its
length and the condition its parameters must meet at the end). -/
structure Sig where
  ret : Ty
  exitOk : Bool
  loop : Option Ctx
  fr : Nat
  fin : Ctx → Prop

/-- While a linear temporary is held, nothing may exit early (it would be lost). -/
def Sig.noExit (Δ : Sig) : Sig := { Δ with exitOk := false, loop := none }

def Sig.withLoop (Δ : Sig) (Γ : Ctx) : Sig := { Δ with loop := some Γ }

/-- The body of a function or closure. -/
def fnSig (P : Prog) (owner : Option String) (ps : List (String × Mode)) (r : Ty) : Sig :=
  ⟨r, true, none, ps.length, FinFn P owner ps⟩

/-- At a `return`: the locals hold no linear value and the frame is finished. -/
def RetOk (P : Prog) (Δ : Sig) (Γ : Ctx) : Prop :=
  Ctx.noLinear P (Γ.take (Γ.length - Δ.fr)) ∧ Δ.fin (Γ.drop (Γ.length - Δ.fr))

/-- At a `break`/`continue`: the loop's locals hold no linear value and the
loop's context is as the loop requires. -/
def LoopOk (P : Prog) (Γl Γ : Ctx) : Prop :=
  Ctx.noLinear P (Γ.take (Γ.length - Γl.length)) ∧ Γ.drop (Γ.length - Γl.length) = Γl

/-- A builtin's signature at given argument types. -/
abbrev PrimSig := String → List Ty → Ty → Prop

/-! ## Patterns -/

mutual
/-- A pattern against a type, and the names it binds; `_` cannot drop a linear part. -/
inductive PatTy (P : Prog) : Pat → Ty → List (String × Ty) → Prop
  | wild {t} : ¬ t.linear P → PatTy P .wild t []
  | bind {x t} : PatTy P (.bind x) t [(x, t)]
  | lit {l} : PatTy P (.lit l) l.ty []
  | tup {ps ts bs} : PatsTy P ps ts bs → PatTy P (.tup ps) (.tup ts) bs
  | con {c ps s args d} {tag : Nat} {ts bs} : P.adts s = some d → d.isStruct = false →
      d.variants[tag]? = some (c, ts) → args.length = d.tparams → PatsTy P ps (substL args ts) bs →
      PatTy P (.con c ps) (.adt s args) bs
  | alt {ps t bs} : AltTy P ps t bs → PatTy P (.alt ps) t bs

inductive PatsTy (P : Prog) : List Pat → List Ty → List (String × Ty) → Prop
  | nil : PatsTy P [] [] []
  | cons {p ps t ts b bs} : PatTy P p t b → PatsTy P ps ts bs → PatsTy P (p :: ps) (t :: ts) (b ++ bs)

/-- Alternatives bind the same names at the same types. -/
inductive AltTy (P : Prog) : List Pat → Ty → List (String × Ty) → Prop
  | one {p t bs} : PatTy P p t bs → AltTy P [p] t bs
  | cons {p ps t bs} : PatTy P p t bs → AltTy P ps t bs → AltTy P (p :: ps) t bs
end

/-! ## The judgement -/

/-- What the judgement allows beyond the stage-2 rules (formal/README.md,
"Static semantics"). `full` enables the stage-3 rules: closures that capture
variables (`clos`), annotations (`ann`) and direct calls of builtins
(`callPrim`). `inst` is the set of function instances the program is checked
at: a call, a function value and a method call must use one of them (the
instances a monomorphizing checker visits, as the compiler compiles generic
code per type). The stage-2 judgement, which the guarded theorem statements
use (`HasTy`, `ValTy`, `ProgOk`, ... below), is `Ext.strict`: no stage-3 rule,
every instance. -/
structure Ext where
  full : Bool
  inst : String → List Ty → Prop

def Ext.strict : Ext := ⟨false, fun _ _ => True⟩

/-- The context of a closure's captured variables (immutable copies). -/
def capCtx (caps : List String) (cts : List Ty) : Ctx :=
  (caps.zip cts).map fun c => ⟨c.1, c.2, false, true⟩

/-- The captured variables are in scope, hold their values, at these types. -/
inductive CapsTy (Γ : Ctx) : List String → List Ty → Prop
  | nil : CapsTy Γ [] []
  | cons {x xs t ts} : Γ.AvailAt x t → CapsTy Γ xs ts → CapsTy Γ (x :: xs) (t :: ts)

/-- The body of a closure with `nc` captured variables below its parameters:
at the end its parameters are finished (the captured copies are dropped). -/
def closSig (P : Prog) (ps : List String) (nc : Nat) (r : Ty) : Sig :=
  ⟨r, true, none, ps.length + nc, fun Γ => FinFn P none (ps.map (·, Mode.val)) (Γ.take ps.length)⟩

/-- The builtin a method call on a value of head `h` selects (as `resolve` does): the
builtin `h.m`, or (stage 3) the one for every head, `*.m` (`x.to_str()`). -/
def PrimAt (X : Ext) (P : Prog) (prim : PrimSig) (h m : String) (ts : List Ty) (t : Ty) : Prop :=
  prim (h ++ "." ++ m) ts t ∨ (X.full = true ∧ P.prim (h ++ "." ++ m) = none ∧ prim ("*." ++ m) ts t)

/-- The tail of a sequence after a value of type `t` is held: early exits are
allowed only if `t` is not linear. -/
def TailSig (P : Prog) (Δ Δ' : Sig) (t : Ty) : Prop := (Δ' = Δ ∧ ¬ t.linear P) ∨ Δ' = Δ.noExit

mutual
/-- `HasTyX X P prim Δ Γ e t Γ'`: `e` has type `t` in `Γ`, leaving `Γ'` (what it moved). -/
inductive HasTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → Expr → Ty → Ctx → Prop
  | lit {Δ Γ l} : HasTyX X P prim Δ Γ (.lit l) l.ty Γ
  /-- A whole variable, moved (always allowed; needed for an obligation). -/
  | move {Δ Γ x en} : Γ.find x = some en → en.avail = true →
      HasTyX X P prim Δ Γ (.place x []) en.ty (Γ.setAvail x false)
  /-- A copy of a variable or of a part of it (the index expressions are evaluated first). -/
  | copy {Δ Γ x ps en t Γ'} : Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t Γ' →
      Γ'.Avail x → t.copyable P → HasTyX X P prim Δ Γ (.place x ps) t Γ'
  | proj {Δ Γ e ps t0 t Γ1 Γ2} : HasTyX X P prim Δ Γ e t0 Γ1 → t0.copyable P → PathTyX X P prim Δ Γ1 t0 ps t Γ2 →
      HasTyX X P prim Δ Γ (.proj e ps) t Γ2
  | tup {Δ Γ es ts Γ'} : ListTyX X P prim Δ Γ es ts Γ' → HasTyX X P prim Δ Γ (.seq .tup es) (.tup ts) Γ'
  | list {Δ Γ es t Γ'} : ListTyX X P prim Δ Γ es (es.map fun _ => t) Γ' → t.copyable P →
      HasTyX X P prim Δ Γ (.seq .list es) (.list t) Γ'
  | con {Δ Γ s} {tag : Nat} {es d name ts args Γ'} : P.adts s = some d → d.variants[tag]? = some (name, ts) →
      args.length = d.tparams → ListTyX X P prim Δ Γ es (substL args ts) Γ' → HasTyX X P prim Δ Γ (.con s tag es) (.adt s args) Γ'
  /-- A closure: its body sees its parameters (the values it captures at run time are not used). -/
  | lam {Δ Γ ps body ts r Γb} : ps.length = ts.length →
      HasTyX X P prim (fnSig P none (ps.map (·, Mode.val)) r) (paramsCtx (ps.map (·, Mode.val)) ts) body r Γb →
      FinFn P none (ps.map (·, Mode.val)) Γb → HasTyX X P prim Δ Γ (.lam ps body) (.fn ts r) Γ
  | fnref {Δ Γ f d σ} : P.fns f = some d → (∀ p ∈ d.params, p.2 = .val) → σ.length = d.tparams → X.inst f σ →
      HasTyX X P prim Δ Γ (.fnref f) (.fn (substL σ d.ptys) (d.ret.subst σ)) Γ
  /-- A call of a function value: every argument by value. -/
  | callv {Δ Γ f args ts r Γ1 Γ2} : HasTyX X P prim Δ Γ f (.fn ts r) Γ1 →
      ArgsTyX X P prim Δ Γ1 (args.map fun _ => .val) args ts Γ2 → HasTyX X P prim Δ Γ (.call f args) r Γ2
  /-- A direct call: arguments by the parameters' modes. -/
  | call {Δ Γ f d σ args Γ'} : P.fns f = some d → σ.length = d.tparams → X.inst f σ →
      ArgsTyX X P prim Δ Γ (d.params.map (·.2)) args (substL σ d.ptys) Γ' →
      HasTyX X P prim Δ Γ (.call (.fnref f) args) (d.ret.subst σ) Γ'
  /-- A method of the receiver's type, the receiver a place. -/
  | mcallP {Δ Δ' Γ m x ps en t0 d σ p0 m0 prest pt0 ptrest args Γ1 Γr Γ2} :
      Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t0 Γ1 → Γ1.Avail x →
      t0.isVar = false → P.fns (t0.head ++ "." ++ m) = some d → σ.length = d.tparams →
      X.inst (t0.head ++ "." ++ m) σ → d.params = (p0, m0) :: prest → d.ptys = pt0 :: ptrest → pt0.subst σ = t0 →
      (m0 = .val → (ps = [] ∧ Γr = Γ1.setAvail x false) ∨ (Γr = Γ1 ∧ t0.copyable P)) →
      (m0 ≠ .val → Γr = Γ1 ∧ t0.copyable P ∧ Γ2.AvailAt x en.ty) →
      TailSig P Δ Δ' t0 →
      ArgsTyX X P prim Δ' Γr (prest.map (·.2)) args (substL σ ptrest) Γ2 →
      HasTyX X P prim Δ Γ (.mcall m (.place x ps) args) (d.ret.subst σ) Γ2
  /-- A method of the receiver's type, the receiver a computed value (by value). -/
  | mcallV {Δ Δ' Γ m recv t0 d σ p0 prest pt0 ptrest args Γ1 Γ2} :
      (∀ x ps, recv ≠ .place x ps) → HasTyX X P prim Δ Γ recv t0 Γ1 →
      t0.isVar = false → P.fns (t0.head ++ "." ++ m) = some d → σ.length = d.tparams →
      X.inst (t0.head ++ "." ++ m) σ → d.params = (p0, .val) :: prest → d.ptys = pt0 :: ptrest → pt0.subst σ = t0 →
      TailSig P Δ Δ' t0 → ArgsTyX X P prim Δ' Γ1 (prest.map (·.2)) args (substL σ ptrest) Γ2 →
      HasTyX X P prim Δ Γ (.mcall m recv args) (d.ret.subst σ) Γ2
  /-- A builtin method, the receiver a place (it may give the receiver a new value). -/
  | mprimP {Δ Γ m x ps en t0 ts t args Γ1 Γ2} :
      Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t0 Γ1 → Γ1.Avail x →
      t0.isVar = false → P.fns (t0.head ++ "." ++ m) = none → PrimAt X P prim t0.head m (t0 :: ts) t →
      OpndsTyX X P prim Δ Γ1 args ts Γ2 → Γ2.AvailAt x en.ty → t.copyable P →
      HasTyX X P prim Δ Γ (.mcall m (.place x ps) args) t Γ2
  /-- A builtin method, the receiver a computed value without obligations. -/
  | mprimV {Δ Γ m recv t0 ts t args Γ1 Γ2} :
      (∀ x ps, recv ≠ .place x ps) → HasTyX X P prim Δ Γ recv t0 Γ1 → t0.copyable P →
      t0.isVar = false → P.fns (t0.head ++ "." ++ m) = none → PrimAt X P prim t0.head m (t0 :: ts) t →
      OpndsTyX X P prim Δ Γ1 args ts Γ2 → t.copyable P →
      HasTyX X P prim Δ Γ (.mcall m recv args) t Γ2
  | prim {Δ Γ p args ts t Γ'} : prim p ts t → OpndsTyX X P prim Δ Γ args ts Γ' → t.copyable P →
      HasTyX X P prim Δ Γ (.prim p args) t Γ'
  /-- A linear variable must be consumed by the end of its scope. -/
  | letE {Δ Γ x mu e body t t' Γ1 a Γ2} : HasTyX X P prim Δ Γ e t Γ1 →
      HasTyX X P prim Δ (⟨x, t, mu, true⟩ :: Γ1) body t' (⟨x, t, mu, a⟩ :: Γ2) → (a = true → ¬ t.linear P) →
      HasTyX X P prim Δ Γ (.letE x mu e body) t' Γ2
  /-- Assignment of a whole variable: never over a live linear value. -/
  | assign {Δ Γ x e en Γ1} : Γ.find x = some en → en.mutable = true → HasTyX X P prim Δ Γ e en.ty Γ1 →
      (∀ en1, Γ1.find x = some en1 → en1.avail = true → ¬ en.ty.linear P) →
      HasTyX X P prim Δ Γ (.assign x [] e) .unit (Γ1.setAvail x true)
  /-- Assignment to a part (or a whole variable) of a copyable type. -/
  | assignPart {Δ Γ x ps e t en Γ1 Γ2} : Γ.find x = some en → en.mutable = true → en.avail = true →
      PathTyX X P prim Δ Γ en.ty ps t Γ1 → HasTyX X P prim Δ Γ1 e t Γ2 → Γ2.Avail x → t.copyable P →
      HasTyX X P prim Δ Γ (.assign x ps e) .unit Γ2
  | seqE {Δ Γ e1 e2 t1 t Γ1 Γ2} : HasTyX X P prim Δ Γ e1 t1 Γ1 → ¬ t1.linear P → HasTyX X P prim Δ Γ1 e2 t Γ2 →
      HasTyX X P prim Δ Γ (.seqE e1 e2) t Γ2
  /-- Both branches leave the same context (every path consumes the same obligations). -/
  | ite {Δ Γ c a b t Γ1 Γ2} : HasTyX X P prim Δ Γ c .bool Γ1 → HasTyX X P prim Δ Γ1 a t Γ2 → HasTyX X P prim Δ Γ1 b t Γ2 →
      HasTyX X P prim Δ Γ (.ite c a b) t Γ2
  | mtch {Δ Γ e arms t0 t Γ1 Γ2} : HasTyX X P prim Δ Γ e t0 Γ1 → ArmsTyX X P prim Δ Γ1 t0 arms t Γ2 →
      HasTyX X P prim Δ Γ (.mtch e arms) t Γ2
  /-- A loop cannot consume what it did not create. -/
  | while {Δ Γ c body t} : HasTyX X P prim Δ Γ c .bool Γ → HasTyX X P prim (Δ.withLoop Γ) Γ body t Γ →
      ¬ t.linear P → HasTyX X P prim Δ Γ (.while c body) .unit Γ
  /-- An early exit: the locals are consumed and the frame is finished; it has any type. -/
  | ret {Δ Γ e Γ1 t Γ'} : Δ.exitOk = true → HasTyX X P prim Δ Γ e Δ.ret Γ1 → RetOk P Δ Γ1 →
      HasTyX X P prim Δ Γ (.ret e) t Γ'
  | brk {Δ Γ Γl t Γ'} : Δ.loop = some Γl → LoopOk P Γl Γ → HasTyX X P prim Δ Γ .brk t Γ'
  | cont {Δ Γ Γl t Γ'} : Δ.loop = some Γl → LoopOk P Γl Γ → HasTyX X P prim Δ Γ .cont t Γ'
  | tryOpt {Δ Γ e t t' Γ1} : Δ.exitOk = true → HasTyX X P prim Δ Γ e (.adt "Option" [t]) Γ1 →
      Δ.ret = .adt "Option" [t'] → RetOk P Δ Γ1 → HasTyX X P prim Δ Γ (.try e) t Γ1
  | tryRes {Δ Γ e t t' er Γ1} : Δ.exitOk = true → HasTyX X P prim Δ Γ e (.adt "Result" [t, er]) Γ1 →
      Δ.ret = .adt "Result" [t', er] → RetOk P Δ Γ1 → HasTyX X P prim Δ Γ (.try e) t Γ1
  /-- A closure capturing variables by value (copies of copyable values), stage 3. -/
  | clos {Δ Γ caps ps body ts r cts Γb} : X.full = true → ps.length = ts.length → CapsTy Γ caps cts →
      (∀ t ∈ cts, t.copyable P) →
      HasTyX X P prim (closSig P ps cts.length r) (paramsCtx (ps.map (·, Mode.val)) ts ++ capCtx caps cts) body r Γb →
      FinFn P none (ps.map (·, Mode.val)) (Γb.take ps.length) →
      HasTyX X P prim Δ Γ (.clos caps ps body) (.fn ts r) Γ
  /-- An annotation is a hint for the checker: it types as its expression. -/
  | ann {Δ Γ t0 e t Γ'} : X.full = true → HasTyX X P prim Δ Γ e t Γ' → HasTyX X P prim Δ Γ (.ann t0 e) t Γ'
  /-- A direct call of a builtin (`Str.from_utf8(b)`): its arguments are operands. -/
  | callPrim {Δ Γ f args ts t Γ'} : X.full = true → P.fns f = none → prim f ts t →
      OpndsTyX X P prim Δ Γ args ts Γ' → t.copyable P → HasTyX X P prim Δ Γ (.call (.fnref f) args) t Γ'

inductive ListTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : ListTyX X P prim Δ Γ [] [] Γ
  | cons {Δ Δ' Γ e es t ts Γ1 Γ2} : HasTyX X P prim Δ Γ e t Γ1 → TailSig P Δ Δ' t →
      ListTyX X P prim Δ' Γ1 es ts Γ2 → ListTyX X P prim Δ Γ (e :: es) (t :: ts) Γ2

/-- Arguments by mode: a `ref`/`mut` argument is a place of a copyable type,
copied in and written back, so it must still be in scope after the arguments. -/
inductive ArgsTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → List Mode → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : ArgsTyX X P prim Δ Γ [] [] [] Γ
  | val {Δ Δ' Γ e es ms t ts Γ1 Γ2} : HasTyX X P prim Δ Γ e t Γ1 → TailSig P Δ Δ' t →
      ArgsTyX X P prim Δ' Γ1 ms es ts Γ2 → ArgsTyX X P prim Δ Γ (.val :: ms) (e :: es) (t :: ts) Γ2
  | byRef {Δ Γ m x ps en t es ms ts Γ1 Γ2} : m ≠ .val → Γ.find x = some en → en.avail = true →
      (m = .mut → en.mutable = true) → PathTyX X P prim Δ Γ en.ty ps t Γ1 → Γ1.Avail x → t.copyable P →
      ArgsTyX X P prim Δ Γ1 ms es ts Γ2 → Γ2.AvailAt x en.ty →
      ArgsTyX X P prim Δ Γ (m :: ms) (.place x ps :: es) (t :: ts) Γ2

/-- A builtin's operands: places are inspected (and still in scope when the builtin
runs: it may give its first operand a new value); other values have no obligation. -/
inductive OpndsTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → List Expr → List Ty → Ctx → Prop
  | nil {Δ Γ} : OpndsTyX X P prim Δ Γ [] [] Γ
  | place {Δ Γ x ps en t es ts Γ1 Γ2} : Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t Γ1 →
      Γ1.Avail x → OpndsTyX X P prim Δ Γ1 es ts Γ2 → Γ2.AvailAt x en.ty → OpndsTyX X P prim Δ Γ (.place x ps :: es) (t :: ts) Γ2
  | val {Δ Γ e t es ts Γ1 Γ2} : (∀ x ps, e ≠ .place x ps) → HasTyX X P prim Δ Γ e t Γ1 → t.copyable P →
      OpndsTyX X P prim Δ Γ1 es ts Γ2 → OpndsTyX X P prim Δ Γ (e :: es) (t :: ts) Γ2

/-- The type at the end of a path (index expressions are typed and may not move obligations). -/
inductive PathTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → Ty → List PStep → Ty → Ctx → Prop
  | nil {Δ Γ t} : PathTyX X P prim Δ Γ t [] t Γ
  | fld {Δ Γ s args f ps d i ft t Γ'} : P.adts s = some d → d.isStruct = true → idxOf f d.fields = some i →
      (d.variants.head?.map (·.2)).bind (·[i]?) = some ft → args.length = d.tparams →
      PathTyX X P prim Δ Γ (ft.subst args) ps t Γ' →
      PathTyX X P prim Δ Γ (.adt s args) (.fld f :: ps) t Γ'
  | tfld {Δ Γ ts i ps ti t Γ'} : ts[i]? = some ti → PathTyX X P prim Δ Γ ti ps t Γ' →
      PathTyX X P prim Δ Γ (.tup ts) (.tfld i :: ps) t Γ'
  | idxList {Δ Γ e el ps t Γ1 Γ2} : HasTyX X P prim Δ Γ e .int Γ1 → PathTyX X P prim Δ Γ1 el ps t Γ2 →
      PathTyX X P prim Δ Γ (.list el) (.idx e :: ps) t Γ2
  | idxMap {Δ Γ e k v ps t Γ1 Γ2} : HasTyX X P prim Δ Γ e k Γ1 → k.copyable P → PathTyX X P prim Δ Γ1 v ps t Γ2 →
      PathTyX X P prim Δ Γ (.map k v) (.idx e :: ps) t Γ2

/-- Arms: the patterns fit the matched type, guards only on values without
obligations (and leave the context as it is), the names a pattern binds are
consumed (if linear) by the end of the arm, and every arm leaves the same context. -/
inductive ArmsTyX (X : Ext) (P : Prog) (prim : PrimSig) : Sig → Ctx → Ty → List (Pat × Option Expr × Expr) → Ty → Ctx → Prop
  | nil {Δ Γ t0 t Γ'} : ArmsTyX X P prim Δ Γ t0 [] t Γ'
  | cons {Δ Γ t0 p g body arms t bs Γ' Γb} : PatTy P p t0 bs →
      (g.isSome → t0.copyable P) →
      (∀ ge, g = some ge → HasTyX X P prim Δ (bindCtx bs ++ Γ) ge .bool (bindCtx bs ++ Γ)) →
      HasTyX X P prim Δ (bindCtx bs ++ Γ) body t (Γb ++ Γ') → Γb.length = bs.length →
      Ctx.noLinear P Γb → ArmsTyX X P prim Δ Γ t0 arms t Γ' → ArmsTyX X P prim Δ Γ t0 ((p, g, body) :: arms) t Γ'
end

/-! ## Values and environments -/

/-- The obligation token a value of a declared type of kind `k` carries. -/
def TokOk : Kind → Option Tok → Prop
  | .copy, none => True
  | .linear, some t => t.lin = true
  | .unique, some t => t.lin = false
  | _, _ => False

/-- A value of a type. Tokens match kinds: a value of a linear (unique)
declared type carries a linear (unique) token, others carry none; a closure
captured no obligation and its body has its type. -/
inductive ValTyX (X : Ext) (P : Prog) (prim : PrimSig) : Val → Ty → Prop
  | int {i} : ValTyX X P prim (.int i) .int
  | bool {b} : ValTyX X P prim (.bool b) .bool
  | str {s} : ValTyX X P prim (.str s) .str
  | unit : ValTyX X P prim .unit .unit
  | tup {vs ts} : vs.length = ts.length → (∀ p ∈ vs.zip ts, ValTyX X P prim p.1 p.2) →
      ValTyX X P prim (.seq .tup vs) (.tup ts)
  | list {vs t} : (∀ v ∈ vs, ValTyX X P prim v t) → ValTyX X P prim (.seq .list vs) (.list t)
  | map {kvs k v} : (∀ e ∈ kvs, (entryKV e).isSome) →
      (∀ e ∈ kvs, ∀ a b, entryKV e = some (a, b) → ValTyX X P prim a k) →
      (∀ e ∈ kvs, ∀ a b, entryKV e = some (a, b) → ValTyX X P prim b v) →
      ValTyX X P prim (.seq .map kvs) (.map k v)
  | adt {s} {tag : Nat} {tok vs d name ts args} : P.adts s = some d → d.variants[tag]? = some (name, ts) →
      args.length = d.tparams → vs.length = ts.length → (∀ p ∈ vs.zip (substL args ts), ValTyX X P prim p.1 p.2) →
      TokOk d.kind tok → ValTyX X P prim (.adt s tag tok vs) (.adt s args)
  | fn {f d σ} : P.fns f = some d → (∀ p ∈ d.params, p.2 = .val) → σ.length = d.tparams → X.inst f σ →
      ValTyX X P prim (.fn f) (.fn (substL σ d.ptys) (d.ret.subst σ))
  | clo {names cvs ps body ts r Γb} : names.length = cvs.length → toksL cvs = [] → ps.length = ts.length →
      HasTyX X P prim (fnSig P none (ps.map (·, Mode.val)) r) (paramsCtx (ps.map (·, Mode.val)) ts) body r Γb →
      FinFn P none (ps.map (·, Mode.val)) Γb →
      ValTyX X P prim (.clo names cvs ps body) (.fn ts r)
  | cap {c} : ValTyX X P prim (.cap c) (.cap c.kind)
  /-- A closure with captured values of copyable types (stage 3). -/
  | closC {names cvs ps body ts r cts Γb} : X.full = true → names.length = cvs.length → toksL cvs = [] →
      ps.length = ts.length → cvs.length = cts.length → (∀ q ∈ cvs.zip cts, ValTyX X P prim q.1 q.2) →
      (∀ t ∈ cts, t.copyable P) →
      HasTyX X P prim (closSig P ps cts.length r) (paramsCtx (ps.map (·, Mode.val)) ts ++ capCtx names cts) body r Γb →
      FinFn P none (ps.map (·, Mode.val)) (Γb.take ps.length) →
      ValTyX X P prim (.clo names cvs ps body) (.fn ts r)

/-- A slot matches its entry: an available variable holds a value of its type;
a moved one holds nothing or a value without obligations (never used again). -/
def SlotOkX (X : Ext) (P : Prog) (prim : PrimSig) (e : Entry) (s : Option Val) : Prop :=
  (e.avail = true → ∃ v, s = some v ∧ ValTyX X P prim v e.ty) ∧ (e.avail = false → ∀ v, s = some v → v.toks = [])

/-- The runtime environment matches the context entry by entry; below the
context it may hold more slots without obligations (what a closure captured). -/
def EnvOkX (X : Ext) (P : Prog) (prim : PrimSig) : Env → Ctx → Prop
  | ρ, [] => ∀ p ∈ ρ, ∀ v, p.2 = some v → v.toks = []
  | [], _ :: _ => False
  | (x, s) :: ρ, e :: Γ => x = e.name ∧ SlotOkX X P prim e s ∧ EnvOkX X P prim ρ Γ

/-! ## Programs -/

/-- Declared types are well formed: a struct has one variant and a name per
field, an enum's variant names are distinct, and a field's kind is bounded by
its type's (a copy struct holds no obligation, whatever its type arguments). -/
def AdtsOk (P : Prog) : Prop :=
  ∀ s d, P.adts s = some d →
    (d.isStruct = true → ∃ nm ts, d.variants = [(nm, ts)] ∧ d.fields.length = ts.length) ∧
    (d.isStruct = false → (d.variants.map (·.1)).Nodup) ∧
    ∀ args : List Ty, args.length = d.tparams → ∀ v ∈ d.variants, ∀ ft ∈ v.2,
      Kind.le ((ft.subst args).kind P) (Kind.join d.kind (kindL P args))

/-- `Option` and `Result` are the prelude's (`?` relies on their shape). -/
def StdOk (P : Prog) : Prop :=
  (∃ d, P.adts "Option" = some d ∧ d.kind = .copy ∧ d.isStruct = false ∧ d.tparams = 1 ∧
    d.variants = [("Some", [.var 0]), ("None", [])]) ∧
  (∃ d, P.adts "Result" = some d ∧ d.kind = .copy ∧ d.isStruct = false ∧ d.tparams = 2 ∧
    d.variants = [("Ok", [.var 0]), ("Err", [.var 1])])

/-- Every function is well typed at every instance of its type parameters
(generic code is checked at the types it is used with: monomorphization,
reference §17; Subst.lean shows that checking it once suffices), and its
parameters are finished at its end. -/
def ProgOkX (X : Ext) (P : Prog) (prim : PrimSig) : Prop :=
  AdtsOk P ∧ StdOk P ∧
  ∀ f d, P.fns f = some d → ∀ σ : List Ty, σ.length = d.tparams → X.inst f σ →
    d.params.length = d.ptys.length ∧
      ∃ Γ', HasTyX X P prim (fnSig P d.owner d.params (d.ret.subst σ)) (paramsCtx d.params (substL σ d.ptys))
        d.body (d.ret.subst σ) Γ' ∧ FinFn P d.owner d.params Γ'

/-- One builtin respects a signature: on arguments of its types it returns a
value of the result type, authority only from its arguments, and a new
receiver value only for a copyable receiver; or it traps. -/
def PfOkX (X : Ext) (P : Prog) (prim : PrimSig) (pf : List Val → Nat → PrimRes) (ts : List Ty) (t : Ty) : Prop :=
  ∀ vs w, vs.length = ts.length → (∀ q ∈ vs.zip ts, ValTyX X P prim q.1 q.2) →
    match pf vs w with
    | .ok v self evs _ => ValTyX X P prim v t ∧
        granted (v.caps ++ (self.map Val.caps).getD [] ++ evs.map (·.cap)) (capsL vs) = true ∧
        ∀ s, self = some s → ∃ t0, ts.head? = some t0 ∧ ValTyX X P prim s t0 ∧ t0.copyable P
    | .trap _ => True
    | _ => False

/-- The builtins respect their signatures. -/
def PrimsOkX (X : Ext) (P : Prog) (prim : PrimSig) : Prop :=
  ∀ p ts t, prim p ts t → ∃ pf, P.prim p = some pf ∧ PfOkX X P prim pf ts t

/-! ## The stage-2 judgement (the guarded statements, Theorems.lean) -/

abbrev HasTy (P : Prog) (prim : PrimSig) := HasTyX Ext.strict P prim
abbrev ListTy (P : Prog) (prim : PrimSig) := ListTyX Ext.strict P prim
abbrev ArgsTy (P : Prog) (prim : PrimSig) := ArgsTyX Ext.strict P prim
abbrev OpndsTy (P : Prog) (prim : PrimSig) := OpndsTyX Ext.strict P prim
abbrev PathTy (P : Prog) (prim : PrimSig) := PathTyX Ext.strict P prim
abbrev ArmsTy (P : Prog) (prim : PrimSig) := ArmsTyX Ext.strict P prim
abbrev ValTy (P : Prog) (prim : PrimSig) := ValTyX Ext.strict P prim
abbrev SlotOk (P : Prog) (prim : PrimSig) := SlotOkX Ext.strict P prim
abbrev EnvOk (P : Prog) (prim : PrimSig) := EnvOkX Ext.strict P prim
abbrev ProgOk (P : Prog) (prim : PrimSig) := ProgOkX Ext.strict P prim
abbrev PfOk (P : Prog) (prim : PrimSig) := PfOkX Ext.strict P prim
abbrev PrimsOk (P : Prog) (prim : PrimSig) := PrimsOkX Ext.strict P prim

/-- The stage-3 judgement: the loosened rules, at the instances `I` (TenonCore/Check.lean computes them). -/
def Ext.stage3 (I : String → List Ty → Prop) : Ext := ⟨true, I⟩

end Tenon

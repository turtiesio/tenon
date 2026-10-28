/-
The checker (tenon.md §6, formal/README.md "The checker"): a decision
procedure for the stage-3 typing judgement (`HasTyX (Ext.stage3 I)`,
Typing.lean), executable, proved sound in CheckSound.lean
(`check_sound`: a program it accepts is well typed, `ProgOkX`, so
`type_soundness_full` applies to it).

It checks one function instance at a time, at concrete types (the
instances, `inst`, are the monomorphized ones: a call at a new instance
fails with `Err.need`, and the driver adds the instance and checks again).
Types are inferred bidirectionally: an expected type flows down (from an
annotation `Expr.ann`, a parameter type, the other operand of `==`), may
contain holes (`Ty.hole`, an unknown part), and the type arguments of a
generic call are found by matching (`matchT`). Inference is untrusted: what
the soundness proof uses are the checks (`req`) of the results against the
rules' side conditions.
-/
import TenonCore.CheckBase

namespace Tenon.Check
open Tenon

/-! ## The checker's monad and environment -/

/-- Why the checker rejects: a message, or an instance it needs (the driver adds it). -/
inductive Err where
  | msg (s : String)
  | need (f : String) (σ : List Ty)
  deriving Inhabited

abbrev CM := Except Err

def fail (s : String) : CM α := .error (.msg s)
def req (c : Bool) (s : String) : CM Unit := if c then pure () else fail s
def getO (o : Option α) (s : String) : CM α := match o with
  | some a => pure a
  | none => fail s

/-- What the checker knows: the program, the builtins' signatures (`prim`, the
relation of the judgement; `primRes`/`opHint` infer a result and suggest an
operand's type, untrusted), the instances (`inst`), the instance being
checked (`σ`, for annotations, which mention the function's type parameters). -/
structure CEnv where
  P : Prog
  prim : String → List Ty → Ty → Bool
  primRes : String → List Ty → Option Ty → Option Ty
  opHint : String → List Ty → Option Ty
  inst : String → List Ty → Bool
  σ : List Ty := []

/-- The result: a value of a type and the context left, or no value (an early
exit on every path: typable at every type and context). -/
inductive R where
  | ty (t : Ty) (Γ : Ctx)
  | div

/-! ## Inference helpers (untrusted) -/

/-- An unknown part of an expected type. -/
def _root_.Tenon.Ty.hole : Ty := .adt "?" []

mutual
def _root_.Tenon.Ty.hasHole : Ty → Bool
  | .adt "?" [] => true
  | .tup ts => holesL ts
  | .list t => t.hasHole
  | .map k v => k.hasHole || v.hasHole
  | .adt _ as => holesL as
  | .fn ps r => holesL ps || r.hasHole
  | _ => false
def holesL : List Ty → Bool
  | [] => false
  | t :: ts => t.hasHole || holesL ts
end

/-- Substitute what is known of the type arguments; the rest are holes. -/
partial def substP (σp : List (Option Ty)) : Ty → Ty
  | .var i => match σp[i]? with
    | some (some t) => t
    | _ => Ty.hole
  | .tup ts => .tup (ts.map (substP σp))
  | .list t => .list (substP σp t)
  | .map k v => .map (substP σp k) (substP σp v)
  | .adt s as => .adt s (as.map (substP σp))
  | .fn ps r => .fn (ps.map (substP σp)) (substP σp r)
  | t => t

/-- First-order matching of a signature's type against a type (holes match nothing). -/
partial def matchT (pat t : Ty) (σp : List (Option Ty)) : List (Option Ty) :=
  match pat, t with
  | .var i, t => if t.hasHole then σp else match σp[i]? with
    | some none => σp.set i (some t)
    | _ => σp
  | .tup ps, .tup ts => matchL ps ts σp
  | .list p, .list t => matchT p t σp
  | .map pk pv, .map k v => matchT pv v (matchT pk k σp)
  | .adt s ps, .adt s' ts => if s == s' then matchL ps ts σp else σp
  | .fn ps pr, .fn ts r => matchT pr r (matchL ps ts σp)
  | _, _ => σp
where
  matchL : List Ty → List Ty → List (Option Ty) → List (Option Ty)
    | p :: ps, t :: ts, σp => matchL ps ts (matchT p t σp)
    | _, _, σp => σp

def allSome : List (Option Ty) → Option (List Ty)
  | [] => some []
  | some t :: r => (allSome r).map (t :: ·)
  | none :: _ => none

def initσ (n : Nat) (pat : Ty) (exp : Option Ty) : List (Option Ty) :=
  let σ0 := List.replicate n none
  match exp with
  | some t => matchT pat t σ0
  | none => σ0

/-- The parameter types (and the result, if known) an expected function type gives a closure. -/
def expFn (exp : Option Ty) (k : Nat) : CM (List Ty × Option Ty) :=
  match exp with
  | some (.fn ts r) =>
    if ts.length = k ∧ holesL ts = false then pure (ts, if r.hasHole then none else some r)
    else fail "cannot infer the parameter types of a closure"
  | _ => fail "cannot infer the parameter types of a closure"

/-! ## Decidable side conditions -/

def availB (Γ : Ctx) (x : String) : Bool := match Γ.find x with
  | some e => e.avail
  | none => false

def availAtB (Γ : Ctx) (x : String) (T : Ty) : Bool := match Γ.find x with
  | some e => e.avail && e.ty == T
  | none => false

/-- The tail of a sequence after a value of type `t` (`TailSig`). -/
def tailSig (P : Prog) (Δ : Sig) (t : Ty) : Sig := if t.linear P then Δ.noExit else Δ

/-- The types of the variables a closure captures (in scope, holding copyable values). -/
def capTys (P : Prog) (Γ : Ctx) : List String → Option (List Ty)
  | [] => some []
  | x :: xs => match Γ.find x, capTys P Γ xs with
    | some e, some ts => if e.avail && decide (e.ty.copyable P) then some (e.ty :: ts) else none
    | _, _ => none

/-- The end of a closure's frame: its parameters finished (`closSig`). -/
def closFin (P : Prog) (ps : List String) (Γ : Ctx) : Bool :=
  finFnB P none (ps.map (·, Mode.val)) (Γ.take ps.length)

def joinR : R → R → CM R
  | .ty t Γ, .ty t' Γ' => do req (t == t' && Γ == Γ') "the branches have different types or consume different values"; pure (.ty t Γ)
  | .ty t Γ, .div | .div, .ty t Γ => pure (.ty t Γ)
  | .div, .div => pure .div

/-- A result's type and context (an early exit: `Unit` and the context, for dead code after it). -/
def R.tyOr : R → Ctx → Ty × Ctx
  | .ty t Γ', _ => (t, Γ')
  | .div, Γ => (.unit, Γ)

def firstTy : List (Option (Ty × Ctx)) → Option (Ty × Ctx)
  | [] => none
  | some r :: _ => some r
  | none :: rs => firstTy rs

/-- An arm's result: its type and the context below the names its pattern bound
(which must not hold linear values), or `none` for an early exit. -/
def armRes (P : Prog) (k : Nat) : R → Option (Ty × Ctx)
  | .ty t Γr => if k ≤ Γr.length ∧ noLinearB P (Γr.take k) = true then some (t, Γr.drop k) else none
  | .div => none

/-- The value `e?` gives, in a function returning `r` (`Option` or `Result`, the same error type). -/
def tryTy : Ty → Ty → Option Ty
  | .adt s [t], .adt s' [_] => if s = "Option" ∧ s' = "Option" then some t else none
  | .adt s [t, er], .adt s' [_, er'] => if s = "Result" ∧ s' = "Result" ∧ er = er' then some t else none
  | _, _ => none

/-- An annotation (without holes) is the value's type. -/
def annOk (t : Ty) : R → Bool
  | .ty t' _ => t.hasHole || t' == t
  | .div => true

def reqInst (E : CEnv) (f : String) (σ : List Ty) : CM Unit :=
  if E.inst f σ then pure () else .error (.need f σ)

/-! ## The checker -/

section
variable (E : CEnv)

mutual
def chk : Nat → Sig → (Ctx → Bool) → Ctx → Expr → Option Ty → CM R
  | 0, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, e, exp => match e with
    | .lit l => pure (.ty l.ty Γ)
    | .place x [] => do
      let en ← getO (Γ.find x) s!"unbound {x}"
      req en.avail s!"'{x}' was already used"
      pure (if decide (en.ty.copyable E.P) then .ty en.ty Γ else .ty en.ty (Γ.setAvail x false))
    | .place x ps => do
      let en ← getO (Γ.find x) s!"unbound {x}"
      req en.avail s!"'{x}' was already used"
      let (t, Γ') ← chkPath n Δ fb Γ en.ty ps
      req (availB Γ' x) s!"'{x}' was moved in its own index"
      req (decide (t.copyable E.P)) s!"a part of '{x}' cannot be moved out (not copyable)"
      pure (.ty t Γ')
    | .proj e ps => do
      let (t0, Γ1) ← chkV n Δ fb Γ e none
      req (decide (t0.copyable E.P)) "a part of a value with obligations"
      let (t, Γ2) ← chkPath n Δ fb Γ1 t0 ps
      pure (.ty t Γ2)
    | .seq .tup es => do
      let hints := match exp with
        | some (.tup ts) => ts.map some
        | _ => []
      let (ts, Γ') ← chkList n Δ fb Γ es hints false
      pure (.ty (.tup ts) Γ')
    | .seq .list es => do
      let el : Option Ty := match exp with
        | some (.list t) => if t.hasHole then none else some t
        | _ => none
      let (ts, Γ') ← chkList n Δ fb Γ es (es.map fun _ => el) true
      let t ← getO (el.or ts.head?) "cannot infer the element type of []"
      req (ts == es.map fun _ => t) "list elements of different types"
      req (decide (t.copyable E.P)) "a list cannot hold linear or unique values"
      pure (.ty (.list t) Γ')
    | .seq .map _ => fail "map value"
    | .con s tag es => do
      let d ← getO (E.P.adts s) s!"unknown type {s}"
      let v ← getO d.variants[tag]? "unknown variant"
      let σ0 := initσ d.tparams (.adt s (List.range d.tparams |>.map Ty.var)) exp
      let (pts, Γ') ← chkList n Δ fb Γ es (v.2.map fun t => some (substP σ0 t)) false
      let σp := matchT.matchL v.2 pts σ0
      let args ← getO (allSome σp) s!"cannot infer the type arguments of {v.1}"
      req (args.length == d.tparams) "type arguments"
      req (pts == substL args v.2) s!"the payload of {v.1} has the wrong type"
      pure (.ty (.adt s args) Γ')
    | .lam ps body => do
      let (ts, r?) ← expFn exp ps.length
      let pms := ps.map (·, Mode.val)
      let pc := paramsCtx pms ts
      let r ← (match r? with
        | some r => pure r
        | none => match chkV n ⟨Ty.hole, false, none, ps.length, fun _ => True⟩ (fun _ => true) pc body none with
          | .ok (r, _) => pure r
          | .error (.need f σ) => .error (.need f σ)
          | .error (.msg _) => fail "cannot infer the result type of a closure (annotate it)")
      let (r', Γb) ← chkV n (fnSig E.P none pms r) (finFnB E.P none pms) pc body (some r)
      req (r' == r && finFnB E.P none pms Γb && ps.length == ts.length) "closure"
      pure (.ty (.fn ts r) Γ)
    | .clos caps ps body => do
      let (ts, r?) ← expFn exp ps.length
      let cts ← getO (capTys E.P Γ caps) "a closure captures a moved variable or one with obligations"
      let pc := paramsCtx (ps.map (·, Mode.val)) ts ++ capCtx caps cts
      let r ← (match r? with
        | some r => pure r
        | none => match chkV n ⟨Ty.hole, false, none, ps.length + cts.length, fun _ => True⟩ (fun _ => true) pc body none with
          | .ok (r, _) => pure r
          | .error (.need f σ) => .error (.need f σ)
          | .error (.msg _) => fail "cannot infer the result type of a closure (annotate it)")
      let (r', Γb) ← chkV n (closSig E.P ps cts.length r) (closFin E.P ps) pc body (some r)
      req (r' == r && closFin E.P ps Γb && ps.length == ts.length) "closure"
      pure (.ty (.fn ts r) Γ)
    | .fnref f => do
      let d ← getO (E.P.fns f) s!"function {f} (a builtin cannot be a value)"
      req (d.params.all (·.2 == Mode.val)) "a function with ref or mut parameters cannot be a value"
      let σ0 := initσ d.tparams (.fn d.ptys d.ret) exp
      let σ ← getO (allSome σ0) s!"cannot infer the type arguments of {f}"
      req (σ.length == d.tparams) "type arguments"
      reqInst E f σ
      pure (.ty (.fn (substL σ d.ptys) (d.ret.subst σ)) Γ)
    | .call (.fnref f) args => match E.P.fns f with
        | some d => do
          let σ0 := initσ d.tparams d.ret exp
          let (ts, Γ', σp) ← chkArgs n Δ fb Γ (d.params.map (·.2)) args d.ptys σ0
          let σ ← getO (allSome σp) s!"cannot infer the type arguments of {f}"
          req (σ.length == d.tparams) "type arguments"
          reqInst E f σ
          req (ts == substL σ d.ptys) s!"the arguments of {f} have the wrong types"
          pure (.ty (d.ret.subst σ) Γ')
        | none => do
          let (ts, Γ') ← chkOpnds n Δ fb Γ args f []
          let t ← getO (E.primRes f ts exp) s!"builtin {f} at these types"
          req (E.prim f ts t) s!"builtin {f} at these types"
          req (decide (t.copyable E.P)) "builtin result"
          pure (.ty t Γ')
    | .call fe args => do
        let (ft, Γ1) ← chkV n Δ fb Γ fe none
        match ft with
        | .fn ts r => do
          let (ts', Γ2, _) ← chkArgs n Δ fb Γ1 (args.map fun _ => Mode.val) args ts []
          req (ts' == ts) "the arguments have the wrong types"
          pure (.ty r Γ2)
        | _ => fail "not a function"
    | .mcall m (.place x ps) args => do
        let en ← getO (Γ.find x) s!"unbound {x}"
        req en.avail s!"'{x}' was already used"
        let (t0, Γ1) ← chkPath n Δ fb Γ en.ty ps
        req (availB Γ1 x && !t0.isVar) "receiver"
        match E.P.fns (t0.head ++ "." ++ m) with
        | some d => match d.params, d.ptys with
          | (_, m0) :: prest, pt0 :: ptrest => do
            let σ0 := matchT pt0 t0 (initσ d.tparams d.ret exp)
            let Γr ← (if m0 == .val then
                (if ps.isEmpty && !decide (t0.copyable E.P) then pure (Γ1.setAvail x false)
                 else do req (decide (t0.copyable E.P)) "a part with obligations cannot be passed by value"; pure Γ1)
              else do req (decide (t0.copyable E.P)) "a ref or mut receiver with obligations"; pure Γ1)
            let (ts, Γ2, σp) ← chkArgs n (tailSig E.P Δ t0) fb Γr (prest.map (·.2)) args ptrest σ0
            let σ ← getO (allSome σp) s!"cannot infer the type arguments of {t0.head}.{m}"
            req (σ.length == d.tparams) "type arguments"
            reqInst E (t0.head ++ "." ++ m) σ
            req (pt0.subst σ == t0 && ts == substL σ ptrest) s!"the arguments of {t0.head}.{m} have the wrong types"
            req (m0 == .val || availAtB Γ2 x en.ty) s!"'{x}' was moved during the call"
            pure (.ty (d.ret.subst σ) Γ2)
          | _, _ => fail s!"method {t0.head}.{m} without self"
        | none => do
          let (ts, Γ2) ← chkOpnds n Δ fb Γ1 args (t0.head ++ "." ++ m) [t0]
          let pk := if (E.P.prim (t0.head ++ "." ++ m)).isSome then t0.head ++ "." ++ m else "*." ++ m
          let t ← getO (E.primRes pk (t0 :: ts) exp) s!"no method {t0.head}.{m} at these types"
          req (E.prim pk (t0 :: ts) t) s!"no method {t0.head}.{m} at these types"
          req (availAtB Γ2 x en.ty && decide (t.copyable E.P)) "builtin method"
          pure (.ty t Γ2)
    | .mcall m recv args => do
        let (t0, Γ1) ← chkV n Δ fb Γ recv none
        req (!t0.isVar) "receiver"
        match E.P.fns (t0.head ++ "." ++ m) with
        | some d => match d.params, d.ptys with
          | (_, .val) :: prest, pt0 :: ptrest => do
            let σ0 := matchT pt0 t0 (initσ d.tparams d.ret exp)
            let (ts, Γ2, σp) ← chkArgs n (tailSig E.P Δ t0) fb Γ1 (prest.map (·.2)) args ptrest σ0
            let σ ← getO (allSome σp) s!"cannot infer the type arguments of {t0.head}.{m}"
            req (σ.length == d.tparams) "type arguments"
            reqInst E (t0.head ++ "." ++ m) σ
            req (pt0.subst σ == t0 && ts == substL σ ptrest) s!"the arguments of {t0.head}.{m} have the wrong types"
            pure (.ty (d.ret.subst σ) Γ2)
          | _, _ => fail s!"method {t0.head}.{m}: a ref or mut receiver must be a place"
        | none => do
          req (decide (t0.copyable E.P)) "an obligation passed to a builtin"
          let (ts, Γ2) ← chkOpnds n Δ fb Γ1 args (t0.head ++ "." ++ m) [t0]
          let pk := if (E.P.prim (t0.head ++ "." ++ m)).isSome then t0.head ++ "." ++ m else "*." ++ m
          let t ← getO (E.primRes pk (t0 :: ts) exp) s!"no method {t0.head}.{m} at these types"
          req (E.prim pk (t0 :: ts) t && decide (t.copyable E.P)) s!"no method {t0.head}.{m} at these types"
          pure (.ty t Γ2)
    | .prim p args => do
      let (ts, Γ') ← chkOpnds n Δ fb Γ args p []
      let t ← getO (E.primRes p ts exp) s!"builtin {p} at these types"
      req (E.prim p ts t && decide (t.copyable E.P)) s!"builtin {p} at these types"
      pure (.ty t Γ')
    | .letE x mu e body => do
      let r1 ← chk n Δ fb Γ e none
      let r2 ← chk n Δ fb (⟨x, (r1.tyOr Γ).1, mu, true⟩ :: (r1.tyOr Γ).2) body exp
      match r2 with
      | .div => pure .div
      | .ty t' (e0 :: Γ2) => do
          req (e0.name == x && e0.ty == (r1.tyOr Γ).1 && e0.mutable == mu) "scope"
          req (!e0.avail || !decide ((r1.tyOr Γ).1.linear E.P)) s!"'{x}' is linear and not consumed"
          pure (.ty t' Γ2)
      | .ty _ [] => fail "scope"
    | .assign x [] e => do
        let en ← getO (Γ.find x) s!"unbound {x}"
        req en.mutable s!"'{x}' is not mutable"
        let (t, Γ1) ← chkV n Δ fb Γ e (some en.ty)
        req (t == en.ty) s!"assignment to '{x}' of the wrong type"
        req (match Γ1.find x with
          | some en1 => !en1.avail || !decide (en.ty.linear E.P)
          | none => true) s!"'{x}' holds an obligation and cannot be overwritten"
        pure (.ty .unit (Γ1.setAvail x true))
    | .assign x ps e => do
        let en ← getO (Γ.find x) s!"unbound {x}"
        req (en.mutable && en.avail) s!"'{x}' is not mutable or was moved"
        let (t, Γ1) ← chkPath n Δ fb Γ en.ty ps
        let (t', Γ2) ← chkV n Δ fb Γ1 e (some t)
        req (t' == t && availB Γ2 x && decide (t.copyable E.P)) s!"assignment to a part of '{x}'"
        pure (.ty .unit Γ2)
    | .seqE e1 e2 => do
      let r1 ← chk n Δ fb Γ e1 none
      match r1 with
      | .ty t1 Γ1 => do
        req (!decide (t1.linear E.P)) "a linear value is dropped"
        chk n Δ fb Γ1 e2 exp
      | .div => chk n Δ fb Γ e2 exp
    | .ite c a b => do
      let (tc, Γ1) ← chkV n Δ fb Γ c (some .bool)
      req (tc == .bool) "condition is not a Bool"
      let ra ← chk n Δ fb Γ1 a exp
      let exp' := match ra with
        | .ty t _ => some t
        | .div => exp
      let rb ← chk n Δ fb Γ1 b exp'
      joinR ra rb
    | .mtch e arms => do
      let (t0, Γ1) ← chkV n Δ fb Γ e none
      let rs ← chkArms n Δ fb Γ1 t0 arms exp
      match firstTy rs with
      | some (t, Γ2) => do
        req (rs.all fun r => match r with
          | some tc => tc == (t, Γ2)
          | none => true) "the arms have different types or consume different values"
        pure (.ty t Γ2)
      | none => pure .div
    | .while c body => do
      let (tc, Γ1) ← chkV n Δ fb Γ c (some .bool)
      req (tc == .bool && Γ1 == Γ) "loop condition"
      let rb ← chk n (Δ.withLoop Γ) fb Γ body (some .unit)
      match rb with
      | .ty t Γb => do
        req (Γb == Γ && !decide (t.linear E.P)) "a loop cannot consume what it did not create"
        pure (.ty .unit Γ)
      | .div => pure (.ty .unit Γ)
    | .ret e => do
      req Δ.exitOk "return while a linear value is held"
      let (t, Γ1) ← chkV n Δ fb Γ e (some Δ.ret)
      req (t == Δ.ret) "return type"
      req (retOkB E.P Δ.fr fb Γ1) "return leaves a linear value or an unfinished parameter"
      pure .div
    | .brk => match Δ.loop with
      | some Γl => do req (loopOkB E.P Γl Γ) "break leaves a linear value"; pure .div
      | none => fail "break outside a loop"
    | .cont => match Δ.loop with
      | some Γl => do req (loopOkB E.P Γl Γ) "continue leaves a linear value"; pure .div
      | none => fail "continue outside a loop"
    | .try e => do
      req Δ.exitOk "? while a linear value is held"
      let (t0, Γ1) ← chkV n Δ fb Γ e none
      req (retOkB E.P Δ.fr fb Γ1) "? leaves a linear value or an unfinished parameter"
      let t ← getO (tryTy t0 Δ.ret) "? on this type"
      pure (.ty t Γ1)
    | .ann t e => do
      let r ← chk n Δ fb Γ e (some (t.subst E.σ))
      req (annOk (t.subst E.σ) r) "the value does not have the annotated type"
      pure r
    | .unsup why => fail s!"unsupported: {why}"

def chkV : Nat → Sig → (Ctx → Bool) → Ctx → Expr → Option Ty → CM (Ty × Ctx)
  | 0, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, e, exp => do
    match ← chk (n + 1) Δ fb Γ e exp with
    | .ty t Γ' => pure (t, Γ')
    | .div => fail "an early exit where a value is needed"

def chkList : Nat → Sig → (Ctx → Bool) → Ctx → List Expr → List (Option Ty) → Bool → CM (List Ty × Ctx)
  | 0, _, _, _, _, _, _ => fail "out of fuel"
  | _ + 1, _, _, Γ, [], _, _ => pure ([], Γ)
  | n + 1, Δ, fb, Γ, e :: es, hints, same => do
    let (t, Γ1) ← chkV n Δ fb Γ e hints.head?.join
    let hints' := if same then es.map fun _ => some t else hints.tail
    let (ts, Γ2) ← chkList n (tailSig E.P Δ t) fb Γ1 es hints' same
    pure (t :: ts, Γ2)

def chkArgs : Nat → Sig → (Ctx → Bool) → Ctx → List Mode → List Expr → List Ty → List (Option Ty) →
    CM (List Ty × Ctx × List (Option Ty))
  | 0, _, _, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, ms, es, pats, σp => match ms, es with
    | [], [] => pure ([], Γ, σp)
    | .val :: ms, e :: es => do
      let (t, Γ1) ← chkV n Δ fb Γ e (some (substP σp (pats.head?.getD Ty.hole)))
      let (ts, Γ2, σp') ← chkArgs n (tailSig E.P Δ t) fb Γ1 ms es pats.tail (matchT (pats.head?.getD Ty.hole) t σp)
      pure (t :: ts, Γ2, σp')
    | m :: ms, .place x ps :: es => do
      let en ← getO (Γ.find x) s!"unbound {x}"
      req (en.avail && (m != .mut || en.mutable)) s!"'{x}' cannot be passed by ref or mut"
      let (t, Γ1) ← chkPath n Δ fb Γ en.ty ps
      req (availB Γ1 x && decide (t.copyable E.P)) s!"a value with obligations passed by ref or mut ('{x}')"
      let (ts, Γ2, σp') ← chkArgs n Δ fb Γ1 ms es pats.tail (matchT (pats.head?.getD Ty.hole) t σp)
      req (availAtB Γ2 x en.ty) s!"'{x}' was moved during the call"
      pure (t :: ts, Γ2, σp')
    | _, _ => fail "wrong number of arguments or a ref or mut argument that is not a place"

def chkOpnds : Nat → Sig → (Ctx → Bool) → Ctx → List Expr → String → List Ty → CM (List Ty × Ctx)
  | 0, _, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, es, p, pre => match es with
    | [] => pure ([], Γ)
    | .place x ps :: es => do
      let en ← getO (Γ.find x) s!"unbound {x}"
      req en.avail s!"'{x}' was already used"
      let (t, Γ1) ← chkPath n Δ fb Γ en.ty ps
      req (availB Γ1 x) s!"'{x}' was moved"
      let (ts, Γ2) ← chkOpnds n Δ fb Γ1 es p (pre ++ [t])
      req (availAtB Γ2 x en.ty) s!"'{x}' was moved by a later operand"
      pure (t :: ts, Γ2)
    | e :: es => do
      let (t, Γ1) ← chkV n Δ fb Γ e (E.opHint p pre)
      req (decide (t.copyable E.P)) "an obligation passed to a builtin"
      let (ts, Γ2) ← chkOpnds n Δ fb Γ1 es p (pre ++ [t])
      pure (t :: ts, Γ2)

def chkPath : Nat → Sig → (Ctx → Bool) → Ctx → Ty → List PStep → CM (Ty × Ctx)
  | 0, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, T, ps => match ps, T with
    | [], T => pure (T, Γ)
    | .fld f :: ps, .adt s args => do
      let d ← getO (E.P.adts s) s!"unknown type {s}"
      let i ← getO (if d.isStruct then idxOf f d.fields else none) s!"no field {f}"
      let ft ← getO ((d.variants.head?.map (·.2)).bind (·[i]?)) s!"no field {f}"
      req (args.length == d.tparams) "type arguments"
      chkPath n Δ fb Γ (ft.subst args) ps
    | .tfld i :: ps, .tup ts => do
      let ti ← getO ts[i]? "tuple field"
      chkPath n Δ fb Γ ti ps
    | .idx e :: ps, .list el => do
      let (ti, Γ1) ← chkV n Δ fb Γ e (some .int)
      req (ti == .int) "index is not an Int"
      chkPath n Δ fb Γ1 el ps
    | .idx e :: ps, .map k v => do
      let (tk, Γ1) ← chkV n Δ fb Γ e (some k)
      req (tk == k && decide (k.copyable E.P)) "key of the wrong type"
      chkPath n Δ fb Γ1 v ps
    | _, _ => fail "no such field, or an index of a value that is not a list or map"

def chkArms : Nat → Sig → (Ctx → Bool) → Ctx → Ty → List (Pat × Option Expr × Expr) → Option Ty →
    CM (List (Option (Ty × Ctx)))
  | 0, _, _, _, _, _, _ => fail "out of fuel"
  | n + 1, Δ, fb, Γ, t0, arms, exp => match arms with
    | [] => pure []
    | (p, g, body) :: arms => do
    let bs ← getO (patTy E.P 64 p t0) "the pattern does not fit the value"
    req (g.isNone || decide (t0.copyable E.P)) "a guard on a value with obligations"
    let tg ← (match g with
      | some ge => chkV n Δ fb (bindCtx bs ++ Γ) ge (some .bool)
      | none => pure (.bool, bindCtx bs ++ Γ))
    req (tg.1 == .bool && tg.2 == bindCtx bs ++ Γ) "guard"
    let rb ← chk n Δ fb (bindCtx bs ++ Γ) body exp
    let r := armRes E.P bs.length rb
    req (r.isSome || rb matches .div) "a linear value bound by a pattern is not consumed"
    let rs ← chkArms n Δ fb Γ t0 arms ((r.map (·.1)).or exp)
    pure (r :: rs)
end

end

/-! ## Instances and programs -/

/-- Check one function instance (`ProgOkX`'s condition for `f` at `σ`). -/
def chkFn (E : CEnv) (fuel : Nat) (d : FnDecl) (σ : List Ty) : CM Unit := do
  req (d.params.length == d.ptys.length && σ.length == d.tparams) "the declaration's parameter types"
  let r := d.ret.subst σ
  let Γ0 := paramsCtx d.params (substL σ d.ptys)
  match ← chk { E with σ := σ } fuel (fnSig E.P d.owner d.params r) (finFnB E.P d.owner d.params) Γ0 d.body (some r) with
  | .ty t Γ' => req (t == r && finFnB E.P d.owner d.params Γ') "the body's type, or a parameter not finished"
  | .div => pure ()

/-- The instances `L` as the checker's instance set. -/
def CEnv.withInsts (E : CEnv) (L : List (String × List Ty)) : CEnv := { E with inst := fun f σ => decide ((f, σ) ∈ L) }

def chkInsts (E : CEnv) (fuel : Nat) : List (String × List Ty) → CM Unit
  | [] => pure ()
  | (f, σ) :: L => do
    let d ← getO (E.P.fns f) s!"no function {f}"
    chkFn E fuel d σ
    chkInsts E fuel L

/-- The capabilities a run starts with (Main.lean): `Sys` with unattenuated capabilities and the arguments. -/
def sysVal (args : List String) : Val :=
  .adt "Sys" 0 none [.cap ⟨.console, none, false⟩, .cap ⟨.fs, none, false⟩, .cap ⟨.clock, none, false⟩,
    .cap ⟨.net, none, false⟩, .cap ⟨.proc, none, false⟩, .seq .list (args.map .str)]

def sysTys : List Ty := [.cap .console, .cap .fs, .cap .clock, .cap .net, .cap .proc, .list .str]

/-- `Sys` is the prelude's struct of capabilities. -/
def sysOkB (P : Prog) : Bool := match P.adts "Sys" with
  | some d => d.tparams == 0 && d.kind == .copy && (match d.variants with
    | [(_, ts)] => ts == sysTys
    | _ => false)
  | none => false

/-- The call of `main` with `sys` (Main.lean runs it). -/
def mainCall (main : String) (arity : Nat) : Expr :=
  .call (.fnref main) (if arity = 0 then [] else [.place "%sys" []])
def sysCtx : Ctx := [⟨"%sys", .adt "Sys" [], false, true⟩]
def topSig : Sig := ⟨.unit, false, none, 0, fun _ => True⟩

/-- **The checker**: the declared types are well formed (over `keys`, which list
the program's declarations), every instance in `L` is well typed with the
instances `L`, and so is the call of `main`. -/
def checkAll (E : CEnv) (fuel : Nat) (keys : List (String × AdtDecl)) (L : List (String × List Ty))
    (main : String) (arity : Nat) : CM Unit := do
  let E := E.withInsts L
  req (keys.all fun sd => adtOkB E.P sd.2) "a declared type is not well formed"
  req (stdOkB E.P) "Option and Result are not the prelude's"
  req (sysOkB E.P) "Sys is not the prelude's"
  chkInsts E fuel L
  let _ ← chk E fuel topSig (fun _ => true) sysCtx (mainCall main arity) none
  pure ()

end Tenon.Check

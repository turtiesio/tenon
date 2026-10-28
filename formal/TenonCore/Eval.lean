/-
The core's semantics: a definitional interpreter with fuel (formal/README.md,
"Semantics"). It is total and computable: the same function the theorems are
about is the one `lake exe tenon-core` runs on translated corpus programs.

Fuel bounds the depth of the evaluation (and the number of loop
iterations); running out is `Err.timeout`, which no theorem excludes.
Every rule of the language that the checker enforces statically is also
checked here dynamically, as a stuck state: `Stuck.type` (a type error) or
`Stuck.linear` (an obligation copied, dropped or used after a move).
-/
import TenonCore.Value

namespace Tenon

/-- Go on with the value; early exits and errors pass through. -/
def Out.bind (r : Out α) (k : α → Env → St → Out β) : Out β :=
  match r with
  | .ok a ρ st => k a ρ st
  | .ctl c ρ st => .ctl c ρ st
  | .err e => .err e

def stuckT (why : String) : Out α := .err (.stuck .type why)
def stuckL (why : String) : Out α := .err (.stuck .linear why)

def pathErr (st : St) : PErr → Out α
  | .trap msg => .err (.trap msg st)
  | .stuck why => stuckT why

/-- Where a `ref`/`mut` argument goes back to after the call. -/
inductive WB where
  | none                                 -- a by-value argument
  | moved (x : String)                   -- an obligation moved out of `x` for the call
  | place (x : String) (ss : List Step)  -- a value without obligations, copied in and out

structure ArgV where
  v : Val
  wb : WB

section
variable (P : Prog)

/-- Read the value at a place without moving it (inspection: fields, `==`,
formatting, builtins, dispatch). -/
def peek (ρ : Env) (st : St) (x : String) (ss : List Step) : Out Val :=
  match lookup ρ x with
  | some (some v0) => match getPath P v0 ss with
    | .ok v => .ok v ρ st
    | .error e => pathErr st e
  | some none => stuckL s!"'{x}' was already used"
  | none => stuckT s!"unbound {x}"

/-- Read a place by value: a value with obligations is moved out of a whole
variable (which becomes moved); it cannot be moved out of a part. -/
def readPlace (ρ : Env) (st : St) (x : String) (ss : List Step) : Out Val :=
  match peek P ρ st x ss with
  | .ok v ρ1 st1 =>
    if v.toks = [] then .ok v ρ1 st1
    else if ss = [] then .ok v (update ρ1 x none) st1
    else stuckL s!"an obligation cannot be moved out of a part of '{x}'"
  | r => r

/-- Pass a place to a parameter of mode `m`. -/
def placeArg (ρ : Env) (st : St) (m : Mode) (x : String) (ss : List Step) : Out ArgV :=
  match m with
  | .val => match readPlace P ρ st x ss with
    | .ok v ρ1 st1 => .ok ⟨v, .none⟩ ρ1 st1
    | .ctl c ρ1 st1 => .ctl c ρ1 st1
    | .err e => .err e
  | _ => match peek P ρ st x ss with
    | .ok v ρ1 st1 =>
      if v.toks = [] then .ok ⟨v, .place x ss⟩ ρ1 st1
      else if ss = [] then .ok ⟨v, .moved x⟩ (update ρ1 x none) st1
      else stuckL s!"an obligation in a part of '{x}' cannot be passed by ref or mut"
    | .ctl c ρ1 st1 => .ctl c ρ1 st1
    | .err e => .err e

/-- Undo an evaluated argument when a later argument exits early. -/
def unwindArg (a : ArgV) (ρ : Env) (st : St) : Option (Env × St) :=
  match a.wb with
  | .moved x => match lookup ρ x with
    | some none => some (update ρ x (some a.v), st)
    | _ => none
  | _ => (discard a.v st).map (ρ, ·)

/-- Write a `ref`/`mut` parameter's final value back to the caller. -/
def writeBack (ρ : Env) (st : St) (wb : WB) (v : Val) : Out Unit :=
  match wb with
  | .none => match discard v st with
    | some st' => .ok () ρ st'
    | none => stuckL "a parameter still holds an obligation"
  | .moved x => match lookup ρ x with
    | some none => .ok () (update ρ x (some v)) st
    | _ => stuckL s!"'{x}' changed during the call"
  | .place x ss => match lookup ρ x with
    | some (some v0) => match getPath P v0 ss with
      | .ok old =>
        if old.toks = [] then
          match setPath P v0 ss v with
          | .ok v1 => .ok () (update ρ x (some v1)) st
          | .error e => pathErr st e
        else stuckL "write-back over an obligation"
      | .error e => pathErr st e
    | _ => stuckL s!"'{x}' was moved during the call"

/-- The end of a by-value parameter: a method of the type finishes its own
`self` (the obligation is discharged); anything else is dropped. -/
def endParam (owner : Option String) (isSelf : Bool) (slot : Option Val) (st : St) : Option St :=
  match owner, isSelf, slot with
  | some o, true, some (.adt s _ (some t) vs) =>
    if o = s then discardAll vs { st with burned := t :: st.burned } else discardSlot slot st
  | _, _, _ => discardSlot slot st

/-- After the body: end the parameters (writing `ref`/`mut` ones back), drop the captured values. -/
def endFrame (owner : Option String) :
    List (String × Mode) → List ArgV → Env → Env → St → Out Unit
  | [], [], rest, ρc, st => match discardAll (rest.filterMap (·.2)) st with
    | some st' => .ok () ρc st'
    | none => stuckL "a captured obligation"
  | (p, m) :: ps, a :: as, (_, slot) :: fr, ρc, st =>
    match m with
    | .val => match endParam owner (p = "self") slot st with
      | some st' => endFrame owner ps as fr ρc st'
      | none => stuckL s!"parameter '{p}' still holds an obligation"
    | _ => match slot with
      | some v => match writeBack P ρc st a.wb v with
        | .ok _ ρc' st' => endFrame owner ps as fr ρc' st'
        | .ctl c ρ' st' => .ctl c ρ' st'
        | .err e => .err e
      | none => stuckL s!"'{p}' was moved out of a ref or mut parameter"
  | _, _, _, _, _ => stuckT "frame shape"

def afterCall (owner : Option String) (ps : List (String × Mode)) (as : List ArgV)
    (ρc : Env) : Out Val → Out Val
  | .ok v fr st => match endFrame P owner ps as fr ρc st with
    | .ok _ ρ' st' => .ok v ρ' st'
    | .ctl c ρ' st' => .ctl c ρ' st'
    | .err e => .err e
  | .ctl (.ret v) fr st => match endFrame P owner ps as fr ρc st with
    | .ok _ ρ' st' => .ok v ρ' st'
    | .ctl c ρ' st' => .ctl c ρ' st'
    | .err e => .err e
  | .ctl _ _ _ => stuckT "break or continue outside a loop"
  | .err e => .err e

def frameOf (ps : List (String × Mode)) (as : List ArgV) (names : List String) (cvs : List Val) : Env :=
  (ps.zip as).map (fun (p, a) => (p.1, some a.v)) ++ (names.zip cvs).map (fun (x, v) => (x, some v))

/-- End a scope of `k` variables (a `let`, the names of a pattern). -/
def popEnv (k : Nat) (ρ : Env) (st : St) : Out Unit :=
  if k ≤ ρ.length then
    match discardAll ((ρ.take k).filterMap (·.2)) st with
    | some st' => .ok () (ρ.drop k) st'
    | none => stuckL "a variable still holds an obligation at the end of its scope"
  else stuckT "scope"

def popScope (k : Nat) : Out Val → Out Val
  | .ok v ρ st => (popEnv k ρ st).bind fun _ ρ' st' => .ok v ρ' st'
  | .ctl c ρ st => (popEnv k ρ st).bind fun _ ρ' st' => .ctl c ρ' st'
  | .err e => .err e

/-- Every capability in `cs` is an attenuation of one in `gs`. -/
def granted (cs gs : List Cap) : Bool := cs.all fun c => gs.any fun d => Cap.leb c d

/-- Call a builtin. Its arguments are inspected; it can return no obligation and no
authority beyond its arguments' (a reference monitor: the builtins are
abstract, Capability.lean),
and a new value for its receiver must hold the same obligations as the old one. -/
def primApply (ρ : Env) (st : St) (pf : List Val → Nat → PrimRes) (vs : List Val)
    (selfPlace : Option (String × List Step)) : Out Val :=
  match pf vs st.world with
  | .ok v self evs w =>
    if !(granted (v.caps ++ (self.map Val.caps).getD [] ++ evs.map (·.cap)) (capsL vs)) then
      stuckT "a builtin returned authority it was not given"
    else if v.toks = [] then
      let st' := { st with out := evs.reverse ++ st.out, world := w }
      match self, selfPlace with
      | none, _ => .ok v ρ st'
      | some w, some (x, ss) => match lookup ρ x with
        | some (some v0) => match getPath P v0 ss with
          | .ok old =>
            if old.toks = w.toks then
              match setPath P v0 ss w with
              | .ok v1 => .ok v (update ρ x (some v1)) st'
              | .error e => pathErr st' e
            else stuckL "a builtin changed the obligations of its receiver"
          | .error e => pathErr st' e
        | _ => stuckT "receiver"
      | some w, none => if w.toks = [] then .ok v ρ st' else stuckL "builtin receiver"
    else stuckL "a builtin returned an obligation"
  | .trap msg => .err (.trap msg st)
  | .stuck why => stuckT why
  | .unsup why => .err (.unsup why)

def mint (st : St) (k : Kind) : Option Tok × St :=
  match k with
  | .copy => (none, st)
  | .linear => (some ⟨st.next, true⟩, { st with next := st.next + 1, minted := ⟨st.next, true⟩ :: st.minted })
  | .unique => (some ⟨st.next, false⟩, { st with next := st.next + 1, minted := ⟨st.next, false⟩ :: st.minted })

def capture (ρ : Env) : List (String × Val) :=
  ρ.filterMap fun (x, s) => match s with
    | some v => if v.toks = [] then some (x, v) else none
    | none => none

/-- The values of the variables a `clos` captures: each must hold a value
without obligations (`none`: a variable is unbound, moved or holds one). -/
def captureNames (ρ : Env) : List String → Option (List Val)
  | [] => some []
  | x :: xs => match lookup ρ x, captureNames ρ xs with
    | some (some v), some vs => if v.toks = [] then some (v :: vs) else none
    | _, _ => none

def pushBinds (bs : List (String × Val)) (ρ : Env) : Env :=
  bs.map (fun (x, v) => (x, some v)) ++ ρ

def tryVal : Val → Option (Sum Val Val)   -- inl: go on with it; inr: return it
  | .adt "Option" 0 none [x] => some (.inl x)
  | .adt "Option" 1 none [] => some (.inr (.adt "Option" 1 none []))
  | .adt "Result" 0 none [x] => some (.inl x)
  | .adt "Result" 1 none [e] => some (.inr (.adt "Result" 1 none [e]))
  | _ => none

/-- The function a method call selects: a Tenon function, else a builtin. -/
inductive Target where
  | tenon (d : FnDecl)
  | prim (pf : List Val → Nat → PrimRes)
  | none

def resolve (head m : String) : Target :=
  match P.fns (head ++ "." ++ m) with
  | some d => .tenon d
  | none => match P.prim (head ++ "." ++ m) with
    | some pf => .prim pf
    | none => match P.prim ("*." ++ m) with
      | some pf => .prim pf
      | none => .none

/-- `x.path = v`: the value it replaces is dropped (refused for an obligation). -/
def assignAt (ρ : Env) (st : St) (x : String) (ss : List Step) (v : Val) : Out Val :=
  match lookup ρ x, ss with
  | some none, [] => .ok .unit (update ρ x (some v)) st
  | some (some old), [] => match discard old st with
    | some st1 => .ok .unit (update ρ x (some v)) st1
    | none => stuckL s!"'{x}' holds an obligation and cannot be overwritten"
  | some (some v0), _ => match oldAt P v0 ss with
    | .ok old => match discardSlot old st with
      | some st1 => match setPath P v0 ss v with
        | .ok v1 => .ok .unit (update ρ x (some v1)) st1
        | .error pe => pathErr st1 pe
      | none => stuckL "an obligation cannot be overwritten"
    | .error pe => pathErr st pe
  | some none, _ => stuckL s!"'{x}' was already used"
  | none, _ => stuckT s!"unbound {x}"

/-- Undo the evaluated arguments (newest last) when a later one exits early. -/
def unwindArgs : List ArgV → Env → St → Option (Env × St)
  | [], ρ, st => some (ρ, st)
  | a :: as, ρ, st => match unwindArg a ρ st with
    | some (ρ1, st1) => unwindArgs as ρ1 st1
    | none => none

mutual
def eval : Nat → Env → St → Expr → Out Val
  | 0, _, _, _ => .err .timeout
  | n + 1, ρ, st, e => match e with
    | .lit l => .ok l.val ρ st
    | .place x ps => (evalSteps n ρ st ps).bind fun ss ρ1 st1 => readPlace P ρ1 st1 x ss
    | .proj e ps => (eval n ρ st e).bind fun v ρ1 st1 =>
      if v.toks = [] then
        (evalSteps n ρ1 st1 ps).bind fun ss ρ2 st2 => match getPath P v ss with
          | .ok w => .ok w ρ2 st2
          | .error pe => pathErr st2 pe
      else stuckL "a part of an obligation cannot be taken"
    | .seq k es => (evalList n ρ st es).bind fun vs ρ1 st1 => .ok (.seq k vs) ρ1 st1
    | .con s tag es => (evalList n ρ st es).bind fun vs ρ1 st1 => match P.adts s with
      | some d => .ok (.adt s tag (mint st1 d.kind).1 vs) ρ1 (mint st1 d.kind).2
      | none => stuckT s!"unknown type {s}"
    | .lam ps body =>
      let cs := capture ρ
      .ok (.clo (cs.map (·.1)) (cs.map (·.2)) ps body) ρ st
    | .clos caps ps body => match captureNames ρ caps with
      | some vs => .ok (.clo caps vs ps body) ρ st
      | none => stuckL "a closure captures a moved variable or an obligation"
    | .ann _ e => eval n ρ st e
    | .fnref f => .ok (.fn f) ρ st
    | .call f args => (eval n ρ st f).bind fun fv ρ1 st1 => match fv with
      | .fn name => match P.fns name with
        | some d => callWith n ρ1 st1 d.owner d.params [] [] d.body [] args
        | none => match P.prim name with
          | some pf => primCall n ρ1 st1 pf none args
          | none => .err (.unsup s!"function {name}")
      | .clo names cvs ps body => callWith n ρ1 st1 none (ps.map (·, Mode.val)) names cvs body [] args
      | _ => stuckT "not a function"
    | .mcall m recv args => match recv with
      | .place x ps => (evalSteps n ρ st ps).bind fun ss ρ1 st1 =>
        (peek P ρ1 st1 x ss).bind fun v0 _ _ => match resolve P v0.head m with
          | .tenon d => match d.params with
            | (_, m0) :: _ => (placeArg P ρ1 st1 m0 x ss).bind fun a0 ρ2 st2 =>
              callWith n ρ2 st2 d.owner d.params [] [] d.body [a0] args
            | [] => stuckT "method without self"
          | .prim pf => primCall n ρ1 st1 pf (some (.inl (x, ss))) args
          | .none => stuckT s!"no method {m}"
      | _ => (eval n ρ st recv).bind fun v0 ρ1 st1 => match resolve P v0.head m with
        | .tenon d => match d.params with
          | (_, .val) :: _ => callWith n ρ1 st1 d.owner d.params [] [] d.body [⟨v0, .none⟩] args
          | _ => stuckT "a ref or mut receiver must be a place"
        | .prim pf =>
          if v0.toks = [] then primCall n ρ1 st1 pf (some (.inr v0)) args
          else stuckL "an obligation passed to a builtin"
        | .none => stuckT s!"no method {m}"
    | .prim p args => match P.prim p with
      | some pf => primCall n ρ st pf none args
      | none => .err (.unsup s!"builtin {p}")
    | .letE x _ e body => (eval n ρ st e).bind fun v ρ1 st1 =>
      popScope 1 (eval n ((x, some v) :: ρ1) st1 body)
    | .assign x ps e => (evalSteps n ρ st ps).bind fun ss ρ1 st1 =>
      (eval n ρ1 st1 e).bind fun v ρ2 st2 => assignAt P ρ2 st2 x ss v
    | .seqE e1 e2 => (eval n ρ st e1).bind fun v ρ1 st1 => match discard v st1 with
      | some st2 => eval n ρ1 st2 e2
      | none => stuckL "an obligation is dropped"
    | .ite c t f => (eval n ρ st c).bind fun cv ρ1 st1 => match cv with
      | .bool b => eval n ρ1 st1 (if b then t else f)
      | _ => stuckT "condition is not a Bool"
    | .mtch e arms => (eval n ρ st e).bind fun v ρ1 st1 => evalArms n ρ1 st1 v arms
    | .while c body => (eval n ρ st c).bind fun cv ρ1 st1 => match cv with
      | .bool false => .ok .unit ρ1 st1
      | .bool true => match eval n ρ1 st1 body with
        | .ok v ρ2 st2 => match discard v st2 with
          | some st3 => eval n ρ2 st3 (.while c body)
          | none => stuckL "an obligation is dropped"
        | .ctl .cont ρ2 st2 => eval n ρ2 st2 (.while c body)
        | .ctl .brk ρ2 st2 => .ok .unit ρ2 st2
        | .ctl (.ret v) ρ2 st2 => .ctl (.ret v) ρ2 st2
        | .err e => .err e
      | _ => stuckT "condition is not a Bool"
    | .ret e => (eval n ρ st e).bind fun v ρ1 st1 => .ctl (.ret v) ρ1 st1
    | .brk => .ctl .brk ρ st
    | .cont => .ctl .cont ρ st
    | .try e => (eval n ρ st e).bind fun v ρ1 st1 => match tryVal v with
      | some (.inl x) => .ok x ρ1 st1
      | some (.inr r) => .ctl (.ret r) ρ1 st1
      | none => stuckT "? on a value that is not an Option or Result"
    | .unsup why => .err (.unsup why)

def evalList : Nat → Env → St → List Expr → Out (List Val)
  | 0, _, _, _ => .err .timeout
  | _ + 1, ρ, st, [] => .ok [] ρ st
  | n + 1, ρ, st, e :: es => (eval n ρ st e).bind fun v ρ1 st1 =>
    match evalList n ρ1 st1 es with
    | .ok vs ρ2 st2 => .ok (v :: vs) ρ2 st2
    | .ctl c ρ2 st2 => match discard v st2 with
      | some st3 => .ctl c ρ2 st3
      | none => stuckL "an obligation lost at an early exit"
    | .err e => .err e

def evalSteps : Nat → Env → St → List PStep → Out (List Step)
  | 0, _, _, _ => .err .timeout
  | _ + 1, ρ, st, [] => .ok [] ρ st
  | n + 1, ρ, st, .fld f :: ss => (evalSteps n ρ st ss).bind fun ss' ρ1 st1 => .ok (.fld f :: ss') ρ1 st1
  | n + 1, ρ, st, .tfld i :: ss => (evalSteps n ρ st ss).bind fun ss' ρ1 st1 => .ok (.tfld i :: ss') ρ1 st1
  | n + 1, ρ, st, .idx e :: ss => (eval n ρ st e).bind fun k ρ1 st1 =>
    if k.toks = [] then (evalSteps n ρ1 st1 ss).bind fun ss' ρ2 st2 => .ok (.idx k :: ss') ρ2 st2
    else stuckL "an obligation as an index"

def evalArg : Nat → Env → St → Mode → Expr → Out ArgV
  | 0, _, _, _, _ => .err .timeout
  | n + 1, ρ, st, .val, e => (eval n ρ st e).bind fun v ρ1 st1 => .ok ⟨v, .none⟩ ρ1 st1
  | n + 1, ρ, st, m, .place x ps => (evalSteps n ρ st ps).bind fun ss ρ1 st1 => placeArg P ρ1 st1 m x ss
  | _ + 1, _, _, _, _ => stuckT "a ref or mut argument must be a place"

def evalArgs : Nat → Env → St → List Mode → List Expr → Out (List ArgV)
  | 0, _, _, _, _ => .err .timeout
  | _ + 1, ρ, st, [], [] => .ok [] ρ st
  | n + 1, ρ, st, m :: ms, e :: es => (evalArg n ρ st m e).bind fun a ρ1 st1 =>
    match evalArgs n ρ1 st1 ms es with
    | .ok as ρ2 st2 => .ok (a :: as) ρ2 st2
    | .ctl c ρ2 st2 => match unwindArg a ρ2 st2 with
      | some (ρ3, st3) => .ctl c ρ3 st3
      | none => stuckL "an argument obligation lost at an early exit"
    | .err e => .err e
  | _ + 1, _, _, _, _ => stuckT "wrong number of arguments"

/-- A builtin's operand: a place is inspected; any other value must hold no obligation. -/
def evalOpnd : Nat → Env → St → Expr → Out (Val × Option (String × List Step))
  | 0, _, _, _ => .err .timeout
  | n + 1, ρ, st, .place x ps => (evalSteps n ρ st ps).bind fun ss ρ1 st1 =>
    (peek P ρ1 st1 x ss).bind fun v ρ2 st2 => .ok (v, some (x, ss)) ρ2 st2
  | n + 1, ρ, st, e => (eval n ρ st e).bind fun v ρ1 st1 =>
    if v.toks = [] then .ok (v, none) ρ1 st1 else stuckL "an obligation passed to a builtin"

def evalOpnds : Nat → Env → St → List Expr → Out (List (Val × Option (String × List Step)))
  | 0, _, _, _ => .err .timeout
  | _ + 1, ρ, st, [] => .ok [] ρ st
  | n + 1, ρ, st, e :: es => (evalOpnd n ρ st e).bind fun o ρ1 st1 =>
    (evalOpnds n ρ1 st1 es).bind fun os ρ2 st2 => .ok (o :: os) ρ2 st2

def evalArms : Nat → Env → St → Val → List (Pat × Option Expr × Expr) → Out Val
  | 0, _, _, _, _ => .err .timeout
  | _ + 1, _, st, _, [] => .err (.trap "no arm matches" st)
  | n + 1, ρ, st, v, (p, g, body) :: arms => match matchPat P p v with
    | .fail => evalArms n ρ st v arms
    | .stuck => stuckT "pattern does not fit the value"
    | .ok bs burn drop => match g with
      | none => match discardAll drop { st with burned := burn ++ st.burned } with
        | some st1 => popScope bs.length (eval n (pushBinds bs ρ) st1 body)
        | none => stuckL "a pattern drops an obligation"
      | some ge =>
        if v.toks = [] then
          match eval n (pushBinds bs ρ) st ge with
          | .ok (.bool true) ρ1 st1 => popScope bs.length (eval n ρ1 st1 body)
          | .ok (.bool false) ρ1 st1 =>
            (popEnv bs.length ρ1 st1).bind fun _ ρ2 st2 => evalArms n ρ2 st2 v arms
          | .ok _ _ _ => stuckT "guard is not a Bool"
          | .ctl c ρ1 st1 => popScope bs.length (.ctl c ρ1 st1)
          | .err e => .err e
        else stuckL "a guard on a value with obligations"

/-- Call a Tenon function or closure: `pre` are the arguments already
evaluated (a method's receiver), `args` the rest. -/
def callWith : Nat → Env → St → Option String → List (String × Mode) → List String → List Val →
    Expr → List ArgV → List Expr → Out Val
  | 0, _, _, _, _, _, _, _, _, _ => .err .timeout
  | n + 1, ρ, st, owner, ps, names, cvs, body, pre, args =>
    if names.length = cvs.length ∧ toksL cvs = [] then
      match evalArgs n ρ st ((ps.drop pre.length).map (·.2)) args with
      | .ok as ρ1 st1 =>
        if (pre ++ as).length = ps.length then
          afterCall P owner ps (pre ++ as) ρ1 (eval n (frameOf ps (pre ++ as) names cvs) st1 body)
        else stuckT "arity"
      | .ctl c ρ1 st1 => match unwindArgs pre ρ1 st1 with
        | some (ρ2, st2) => .ctl c ρ2 st2
        | none => stuckL "an argument obligation lost at an early exit"
      | .err e => .err e
    else stuckT "a closure that captured an obligation"

/-- Call a builtin: the receiver (a place, re-read after the arguments, or a
value), then the operands. Without a receiver, a first operand that is a
place takes the builtin's new receiver value. -/
def primCall : Nat → Env → St → (List Val → Nat → PrimRes) →
    Option (Sum (String × List Step) Val) → List Expr → Out Val
  | 0, _, _, _, _, _ => .err .timeout
  | n + 1, ρ, st, pf, recv, args => (evalOpnds n ρ st args).bind fun os ρ1 st1 =>
    match recv with
    | none => primApply P ρ1 st1 pf (os.map (·.1)) (os.head?.bind (·.2))
    | some (.inl (x, ss)) => (peek P ρ1 st1 x ss).bind fun v1 ρ2 st2 =>
      primApply P ρ2 st2 pf (v1 :: os.map (·.1)) (some (x, ss))
    | some (.inr v0) => primApply P ρ1 st1 pf (v0 :: os.map (·.1)) none
end

end

/-! ## Running a program -/

/-- How a run ends: the process's view (formal/README.md, "Differential testing"). -/
structure Outcome where
  out : List Event
  status : Nat
  stderr : String

end Tenon

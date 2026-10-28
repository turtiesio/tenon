/-
Operations on values that the evaluator and the proofs share: the
obligation tokens and capabilities a value holds, environments, paths
(reading and writing `x.f[i].0`), and pattern matching.
-/
import TenonCore.Syntax

namespace Tenon

/-! ## Tokens and capabilities held by a value -/

mutual
def Val.toks : Val → List Tok
  | .seq _ vs => toksL vs
  | .adt _ _ t vs => t.toList ++ toksL vs
  | .clo _ vs _ _ => toksL vs
  | _ => []
def toksL : List Val → List Tok
  | [] => []
  | v :: vs => v.toks ++ toksL vs
end

mutual
def Val.caps : Val → List Cap
  | .cap c => [c]
  | .seq _ vs => capsL vs
  | .adt _ _ _ vs => capsL vs
  | .clo _ vs _ _ => capsL vs
  | _ => []
def capsL : List Val → List Cap
  | [] => []
  | v :: vs => v.caps ++ capsL vs
end

/-- The tokens of an environment's live (not moved) slots. -/
def envToks : Env → List Tok
  | [] => []
  | (_, some v) :: ρ => v.toks ++ envToks ρ
  | (_, none) :: ρ => envToks ρ

def envCaps : Env → List Cap
  | [] => []
  | (_, some v) :: ρ => v.caps ++ envCaps ρ
  | (_, none) :: ρ => envCaps ρ

/-- Does the value hold a linear obligation? -/
def Val.hasLin (v : Val) : Bool := v.toks.any (·.lin)

/-- Drop a value: refused (`none`) if it holds a linear obligation; its unique
values are recorded as dropped. -/
def discard (v : Val) (st : St) : Option St :=
  if v.hasLin then none else some { st with dropped := v.toks ++ st.dropped }

def discardSlot : Option Val → St → Option St
  | none, st => some st
  | some v, st => discard v st

def discardAll : List Val → St → Option St
  | [], st => some st
  | v :: vs, st => match discard v st with
    | some st' => discardAll vs st'
    | none => none

/-! ## Environments -/

def lookup : Env → String → Option (Option Val)
  | [], _ => none
  | (y, s) :: ρ, x => if y = x then some s else lookup ρ x

def update : Env → String → Option Val → Env
  | [], _, _ => []
  | (y, s) :: ρ, x, s' => if y = x then (y, s') :: ρ else (y, s) :: update ρ x s'

/-! ## Paths -/

/-- A resolved place step (index expressions evaluated). -/
inductive Step where
  | fld (f : String) | tfld (i : Nat) | idx (k : Val)

inductive PErr where
  | trap (msg : String) | stuck (why : String)

def idxOf (x : String) : List String → Option Nat
  | [] => none
  | y :: ys => if y = x then some 0 else (idxOf x ys).map (· + 1)

/-- Structural equality on values (functions and capabilities are never equal). -/
partial def Val.beq : Val → Val → Bool
  | .int a, .int b => a == b
  | .bool a, .bool b => a == b
  | .str a, .str b => a == b
  | .unit, .unit => true
  | .seq .map as, .seq .map bs =>
    as.length == bs.length && as.all (fun a => match a with
      | .seq .tup [k, v] => bs.any (fun b => match b with
        | .seq .tup [k', v'] => Val.beq k k' && Val.beq v v'
        | _ => false)
      | _ => false)
  | .seq k as, .seq k' bs => k == k' && as.length == bs.length && (as.zip bs).all (fun (a, b) => Val.beq a b)
  | .adt s t _ as, .adt s' t' _ bs =>
    s == s' && t == t' && as.length == bs.length && (as.zip bs).all (fun (a, b) => Val.beq a b)
  | _, _ => false

/-- A map entry `(key, value)`. -/
def entryKV : Val → Option (Val × Val)
  | .seq .tup [k, v] => some (k, v)
  | _ => none

/-- The value of key `k` in a map's entries. -/
def mapGet (k : Val) : List Val → Option Val
  | [] => none
  | e :: r => match entryKV e with
    | some (k', v) => if Val.beq k k' then some v else mapGet k r
    | none => mapGet k r

/-- Replace the value of key `k`, or append the entry. -/
def mapSet (k w : Val) : List Val → List Val
  | [] => [.seq .tup [k, w]]
  | e :: r => match entryKV e with
    | some (k', _) => if Val.beq k k' then .seq .tup [k', w] :: r else e :: mapSet k w r
    | none => e :: mapSet k w r

def fieldIdx (P : Prog) (s f : String) : Option Nat :=
  match P.adts s with
  | some d => if d.isStruct then idxOf f d.fields else none
  | none => none

def getStep (P : Prog) : Val → Step → Except PErr Val
  | .adt s _ _ vs, .fld f => match fieldIdx P s f with
    | some i => match vs[i]? with
      | some v => .ok v
      | none => .error (.stuck "field")
    | none => .error (.stuck s!"no field {f}")
  | .seq .tup vs, .tfld i => match vs[i]? with
    | some v => .ok v
    | none => .error (.stuck "tuple field")
  | .seq .list vs, .idx (.int i) =>
    if h : 0 ≤ i ∧ i.toNat < vs.length then .ok vs[i.toNat] else .error (.trap "index out of bounds")
  | .seq .map kvs, .idx k => match mapGet k kvs with
    | some v => .ok v
    | none => .error (.trap "key not found")
  | _, _ => .error (.stuck "not a place")

def getPath (P : Prog) (v : Val) : List Step → Except PErr Val
  | [] => .ok v
  | s :: ss => match getStep P v s with
    | .ok w => getPath P w ss
    | .error e => .error e

def setStep (P : Prog) : Val → Step → Val → Except PErr Val
  | .adt s t tok vs, .fld f, w => match fieldIdx P s f with
    | some i => if i < vs.length then .ok (.adt s t tok (vs.set i w)) else .error (.stuck "field")
    | none => .error (.stuck s!"no field {f}")
  | .seq .tup vs, .tfld i, w =>
    if i < vs.length then .ok (.seq .tup (vs.set i w)) else .error (.stuck "tuple field")
  | .seq .list vs, .idx (.int i), w =>
    if 0 ≤ i ∧ i.toNat < vs.length then .ok (.seq .list (vs.set i.toNat w))
    else .error (.trap "index out of bounds")
  | .seq .map kvs, .idx k, w => .ok (.seq .map (mapSet k w kvs))
  | _, _, _ => .error (.stuck "not a place")

/-- Write `w` at the path; a map entry is inserted by the last step only. -/
def setPath (P : Prog) (v : Val) : List Step → Val → Except PErr Val
  | [], w => .ok w
  | [s], w => setStep P v s w
  | s :: ss, w => match getStep P v s with
    | .ok c => match setPath P c ss w with
      | .ok c' => setStep P v s c'
      | .error e => .error e
    | .error e => .error e

/-- The value an assignment to the path replaces (`none`: a new map entry). -/
def oldAt (P : Prog) (v : Val) : List Step → Except PErr (Option Val)
  | [] => .ok (some v)
  | [s] => match v, s with
    | .seq .map kvs, .idx k => .ok (mapGet k kvs)
    | _, _ => (getStep P v s).map some
  | s :: ss => match getStep P v s with
    | .ok w => oldAt P w ss
    | .error e => .error e

/-! ## Patterns -/

inductive MR where
  | fail
  | ok (binds : List (String × Val)) (burn : List Tok) (drop : List Val)
  | stuck

def litMatch : Lit → Val → MR
  | .int a, .int b => if a = b then .ok [] [] [] else .fail
  | .bool a, .bool b => if a = b then .ok [] [] [] else .fail
  | .str a, .str b => if a = b then .ok [] [] [] else .fail
  | .unit, .unit => .ok [] [] []
  | _, _ => .stuck

def variantName (P : Prog) (s : String) (tag : Nat) : Option String :=
  match P.adts s with
  | some d => if d.isStruct then none else (d.variants[tag]?).map (·.1)
  | none => none

mutual
def matchPat (P : Prog) : Pat → Val → MR
  | .wild, v => .ok [] [] [v]
  | .bind x, v => .ok [(x, v)] [] []
  | .lit l, v => litMatch l v
  | .tup ps, .seq .tup vs => matchList P ps vs
  | .tup _, _ => .stuck
  | .con c ps, .adt s tag tok vs => match variantName P s tag with
    | some name =>
      if name = c then
        match matchList P ps vs with
        | .ok b u d => .ok b (tok.toList ++ u) d
        | r => r
      else .fail
    | none => .stuck
  | .con _ _, _ => .stuck
  | .alt ps, v => matchAlt P ps v
def matchList (P : Prog) : List Pat → List Val → MR
  | [], [] => .ok [] [] []
  | p :: ps, v :: vs => match matchPat P p v with
    | .ok b1 u1 d1 => match matchList P ps vs with
      | .ok b2 u2 d2 => .ok (b1 ++ b2) (u1 ++ u2) (d1 ++ d2)
      | r => r
    | r => r
  | _, _ => .stuck
def matchAlt (P : Prog) : List Pat → Val → MR
  | [], _ => .fail
  | p :: ps, v => match matchPat P p v with
    | .fail => matchAlt P ps v
    | r => r
end

/-- The head of a value's type, which selects its methods (`Str.len`, `Point.norm`). -/
def Val.head : Val → String
  | .int _ => "Int"
  | .bool _ => "Bool"
  | .str _ => "Str"
  | .unit => "Unit"
  | .seq .tup _ => "Tuple"
  | .seq .list _ => "List"
  | .seq .map _ => "Map"
  | .adt s _ _ _ => s
  | .clo .. => "Fn"
  | .fn _ => "Fn"
  | .cap c => match c.kind with
    | .console => "Console" | .fs => "Fs" | .clock => "Clock"
    | .net => "Net" | .proc => "Proc" | .workers => "Workers"

end Tenon

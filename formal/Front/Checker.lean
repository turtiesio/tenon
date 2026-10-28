/-
The checker's driver (not part of the proofs): the builtins' signatures,
type inference hints for them, and the worklist that finds the function
instances a program uses. The verdict is the proved checker's
(TenonCore/Check.lean, `checkAll`): whatever the driver computes, a program is
accepted only if `checkAll` accepts it (TenonCore/CheckSound.lean).
-/
import Front.Translate
import TenonCore.Check

namespace Front
open Tenon Tenon.Check

def fltT : Ty := .adt "Float" []

def isList : Ty → Bool
  | .list _ => true
  | _ => false

/-- Values the interpreter's comparison orders (no maps, functions or capabilities inside). -/
def ordT (P : Prog) : Nat → Ty → Bool
  | 0, _ => false
  | _ + 1, .int | _ + 1, .bool | _ + 1, .str | _ + 1, .unit => true
  | n + 1, .tup ts => ts.attach.all fun ⟨t, _⟩ => ordT P n t
  | n + 1, .list t => ordT P n t
  | n + 1, .adt s as => match P.adts s with
    | some d => d.variants.all fun v => v.2.all fun ft => ordT P n (ft.subst as)
    | none => false
  | _ + 1, _ => false

/-- The type arguments that make a signature's parameters the given types. -/
def sigσ (sg : ExtSig) (ts : List Ty) (exp : Option Ty) : List (Option Ty) :=
  let σ0 := List.replicate sg.tparams none
  let σ1 := matchT.matchL sg.ptys ts σ0
  match exp with
  | some t => matchT sg.ret t σ1
  | none => σ1

def sigMatch (sg : ExtSig) (ts : List Ty) (t : Ty) : Bool :=
  match allSome (sigσ sg ts (some t)) with
  | some σ => σ.length == sg.tparams && ts == substL σ sg.ptys && t == sg.ret.subst σ
  | none => false

/-- The builtins the model implements (the others are `unsup` in Prims.lean). -/
def modeled (adts : Prims.Adts) (p : String) : Bool :=
  (Prims.pureTable adts p).isSome || (Prims.stdinPrim [] p).isSome

/-- `"{e:SPEC}"` at a type: the checks of `fmtSpec` (Prims.lean) that would otherwise be stuck. -/
def fmtOk (spec : String) (t : Ty) : Bool :=
  match Prims.parseSpec spec with
  | none => false
  | some sp =>
    if t == .int then sp.prec.isNone && !(sp.comma && sp.radix.isSome)
    else if t == .str || t == .bool then !(sp.zero || sp.comma || sp.radix.isSome || sp.prec.isSome)
    else if t == fltT then sp.radix.isNone
    else false

/-- **The builtin signatures** (the relation `prim` of the judgement; `PrimsOkX`
is the assumption that the builtins respect it). Operators and the
translator's builtins are listed here; the prelude's `extern fn`s have the
signatures the prelude declares. -/
def primB (P : Prog) (sigs : List (String × ExtSig)) (p : String) (ts : List Ty) (t : Ty) : Bool :=
  if p.startsWith "%fmt:" then (match ts with
    | [a] => t == .str && fmtOk (p.drop 5).toString a
    | _ => false) else
  modeled P.adts p && match p, ts with
  | "%add", [a, b] => a == b && t == a && (a == .int || a == fltT || a == .str || isList a)
  | "%sub", [a, b] | "%mul", [a, b] | "%div", [a, b] | "%rem", [a, b] => a == b && t == a && (a == .int || a == fltT)
  | "%neg", [a] => t == a && (a == .int || a == fltT)
  | "%not", [a] => a == .bool && t == .bool
  | "%eq", [a, b] | "%ne", [a, b] => a == b && t == .bool
  | "%lt", [a, b] | "%le", [a, b] | "%gt", [a, b] | "%ge", [a, b] => a == b && t == .bool && ordT P 32 a
  | "%float", [a] => a == .str && t == fltT
  | "%show", [_] | "*.to_str", [_] | "encode", [_] => t == .str
  | "%fmt", _ => false
  | "%concat", ts => ts.all (· == .str) && t == .str
  | "%map", ts => match t with
    | .map k v => ts.all (· == .tup [k, v]) && decide (k.copyable P) && decide (v.copyable P)
    | _ => false
  | "%index", [c, k] => (c == .list t && k == .int) || c == .map k t
  | "%iter", [c] => match c, t with
    | .list a, .list b => a == b
    | .map k v, .list e => e == .tup [k, v]
    | .adt "Set" [a], .list b => a == b
    | _, _ => false
  | "%sortby", [a, b, c] => match a, b with
    | .list _, .list _ => c == .bool && t == a
    | _, _ => false
  | "Console.write_bytes", _ => false
  | "panic", [a] => a == .str
  | "assert", [a] => a == .bool && t == .unit
  | _, _ => match sigs.lookup p with
    | some sg => sigMatch sg ts t
    | none => false

/-- The result type of a builtin (inference; `primB` checks it). -/
def primRes (sigs : List (String × ExtSig)) (p : String) (ts : List Ty) (exp : Option Ty) : Option Ty :=
  if p.startsWith "%fmt:" then some .str else
  match p, ts with
  | "%add", a :: _ | "%sub", a :: _ | "%mul", a :: _ | "%div", a :: _ | "%rem", a :: _ | "%neg", a :: _ => some a
  | "%not", _ | "%eq", _ | "%ne", _ | "%lt", _ | "%le", _ | "%gt", _ | "%ge", _ => some .bool
  | "%float", _ => some fltT
  | "%show", _ | "*.to_str", _ | "encode", _ | "%concat", _ => some .str
  | "%map", .tup [k, v] :: _ => some (.map k v)
  | "%map", [] => exp
  | "%index", [.list t, _] => some t
  | "%index", [.map _ v, _] => some v
  | "%iter", [.list a] => some (.list a)
  | "%iter", [.map k v] => some (.list (.tup [k, v]))
  | "%iter", [.adt "Set" [a]] => some (.list a)
  | "%sortby", a :: _ => some a
  | "panic", _ => some (match exp with
    | some t => if t.hasHole then .unit else t
    | none => .unit)
  | "assert", _ => some .unit
  | _, _ => match sigs.lookup p with
    | some sg => (allSome (sigσ sg ts exp)).map fun σ => sg.ret.subst σ
    | none => none

/-- The type an operand is expected to have, given the operands before it. -/
def opHint (sigs : List (String × ExtSig)) (p : String) (pre : List Ty) : Option Ty :=
  match p, pre with
  | "%concat", _ => some .str
  | "assert", [] => some .bool
  | "panic", [] => some .str
  | "%index", [.list _] => some .int
  | "%index", [.map k _] => some k
  | "%add", [a] | "%sub", [a] | "%mul", [a] | "%div", [a] | "%rem", [a] | "%eq", [a] | "%ne", [a]
  | "%lt", [a] | "%le", [a] | "%gt", [a] | "%ge", [a] => some a
  | _, _ => match sigs.lookup p with
    | some sg => (sg.ptys[pre.length]?).map (substP (matchT.matchL sg.ptys pre (List.replicate sg.tparams none)))
    | none => none

def checkFuel : Nat := 100000

def env (tp : Program) : CEnv :=
  { P := tp.prog, prim := primB tp.prog tp.sigs, primRes := primRes tp.sigs, opHint := opHint tp.sigs,
    inst := fun _ _ => false }

def showInst (f : String) (σ : List Ty) : String :=
  if σ.isEmpty then f else s!"{f}[{", ".intercalate (σ.map fun t => reprStr t)}]"

/-- The coherence and orphan checks (TenonCore/TraitsCheck.lean, `orphan_coherent_decided`):
the main file sees the prelude and itself, the prelude only itself. -/
def coherence (tp : Program) : Option String :=
  let traitMod (t : String) := tp.traitMods.lookup t
  let typeMod (h : String) := tp.typeMods.lookup h
  let sees (m m' : String) : Bool := m == "main" || m' == "prelude"
  match tp.impls.find? fun mi => !(traitMod mi.im.trait == some mi.mod || typeMod mi.im.self.head == some mi.mod) with
  | some mi => some s!"orphan impl {mi.im.trait} for {reprStr mi.im.self} (neither the trait nor the type is the file's)"
  | none => if Traits.localB sees tp.impls then none else some "two impls of a trait overlap"

/-- Find the instances `main` uses (a worklist), then ask the proved checker. -/
def checkProgram (tp : Program) (limit : Nat := 4000) : Except String (List (String × List Ty)) := do
  let some main := tp.main | throw "unsupported: no main"
  if let some why := coherence tp then throw why
  let E := env tp
  -- main, then every monomorphic function of the program file (generic ones at the instances used)
  let roots : List (String × List Ty) := tp.roots.filterMap fun f => (tp.prog.fns f).bind fun d =>
    if d.tparams == 0 then some (f, []) else none
  let roots := (main, []) :: roots.filter (·.1 != main)
  let mut known : Array (String × List Ty) := roots.toArray
  let mut queue : List (String × List Ty) := roots
  let mut steps := 0
  -- the call of main first (it may need nothing but main), then the queue
  let mut mainDone := false
  while (!mainDone || !queue.isEmpty) && steps < limit do
    steps := steps + 1
    let L := known.toList
    let r : CM Unit ← if !mainDone then
        pure (do let _ ← chk (E.withInsts L) checkFuel topSig (fun _ => true) sysCtx (mainCall main tp.mainArity) none)
      else match queue with
        | (f, σ) :: _ => match tp.prog.fns f with
          | some d => pure (chkFn (E.withInsts L) checkFuel d σ)
          | none => throw s!"no function {f}"
        | [] => pure (pure ())
    match r with
    | .ok () => if !mainDone then mainDone := true else queue := queue.tail
    | .error (.need g τ) =>
      if known.contains (g, τ) then throw s!"checker: instance {showInst g τ} loops"
      known := known.push (g, τ)
      queue := queue ++ [(g, τ)]
    | .error (.msg m) =>
      let where_ := if !mainDone then "main's call" else match queue with
        | (f, σ) :: _ => showInst f σ
        | [] => "?"
      -- a builtin the model does not implement (fs, net, proc, workers): outside the subset
      let named := (m.splitOn " ").filter fun w =>
        (tp.sigs.lookup w).isSome && (!modeled tp.prog.adts w || w == "Console.write_bytes")
      if let some b := named.head? then throw s!"unsupported: builtin {b} ({where_})"
      if (m.splitOn "%show").length > 1 then throw s!"unsupported: Show impls ({where_})"
      throw s!"{where_}: {m}"
  unless queue.isEmpty do throw s!"too many instances (more than {limit} checks)"
  let L := known.toList
  match checkAll E checkFuel tp.adtList L main tp.mainArity with
  | .ok () => return L
  | .error (.msg m) => throw m
  | .error (.need g τ) => throw s!"instance {showInst g τ} missing"

end Front

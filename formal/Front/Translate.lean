/-
From the surface syntax (`tenon ast`) of the prelude and one program to a
core program (formal/README.md, "Mapping"). The translator knows no types:
method calls dispatch on the receiver's value at run time, patterns match
variants by name, and a construct outside the core becomes `Expr.unsup`,
which makes the run "out of the subset" if it is reached.
-/
import Front.Parse
import TenonCore.Prims
import Std.Data.HashMap

namespace Front
open Tenon

/-- The builtin types: they have no declaring module, their methods are keyed by name. -/
def builtinTypes : List String :=
  ["Int", "Float", "Bool", "Str", "Unit", "List", "Map", "Console", "Fs", "Clock", "Net", "Proc",
   "Workers", "Listener", "Conn", "Poller", "Sender", "Receiver", "Worker"]

/-- What a file can name (reference §13: a file's own items hide the prelude's). -/
structure Scope where
  types : Std.HashMap String String := {}                 -- type name → key
  variants : Std.HashMap String (List (String × Nat)) := {} -- variant name → (enum key, tag)
  fns : Std.HashMap String (String × Bool) := {}          -- free function or constant → (key, is a constant)
  externs : Std.HashMap String String := {}               -- free extern → builtin name

structure Ctx where
  scope : Scope
  adts : Std.HashMap String AdtDecl
  tparams : List String := []

abbrev TM := StateM Nat

def fresh (base : String) : TM String := do
  let n ← get
  set (n + 1)
  return s!"%{base}{n}"

def Ctx.tyKey (c : Ctx) (n : String) : String :=
  if builtinTypes.contains n then n else (c.scope.types.get? n).getD n

partial def Ctx.ty (c : Ctx) : STy → Ty
  | .named "Int" [] => .int
  | .named "Bool" [] => .bool
  | .named "Str" [] => .str
  | .named "Unit" [] => .unit
  | .named "List" [t] => .list (c.ty t)
  | .named "Map" [k, v] => .map (c.ty k) (c.ty v)
  | .named "Console" [] => .cap .console
  | .named "Fs" [] => .cap .fs
  | .named "Clock" [] => .cap .clock
  | .named "Net" [] => .cap .net
  | .named "Proc" [] => .cap .proc
  | .named "Workers" [] => .cap .workers
  | .named n as => match c.tparams.idxOf? n with
    | some i => if as.isEmpty then .var i else .adt (c.tyKey n) (as.map c.ty)
    | none => .adt (c.tyKey n) (as.map c.ty)
  | .fn ps r => .fn (ps.map c.ty) (c.ty r)
  | .tup [] => .unit
  | .tup ts => .tup (ts.map c.ty)

def binop : String → Option String
  | "Add" => some "%add" | "Sub" => some "%sub" | "Mul" => some "%mul"
  | "Div" => some "%div" | "Rem" => some "%rem"
  | "Eq" => some "%eq" | "Ne" => some "%ne" | "Lt" => some "%lt"
  | "Le" => some "%le" | "Gt" => some "%gt" | "Ge" => some "%ge"
  | _ => none

def unitE : Expr := .lit .unit

partial def tPat : SPat → Pat
  | .wild => .wild
  | .bind x => .bind x
  | .int i => .lit (.int i)
  | .str s => .lit (.str s)
  | .bool b => .lit (.bool b)
  | .tup [] => .lit .unit
  | .tup ps => .tup (ps.map tPat)
  | .variant _ v ps => .con v (ps.map tPat)
  | .alt ps => .alt (ps.map tPat)

partial def patNames : SPat → List String
  | .bind x => [x]
  | .tup ps | .variant _ _ ps => ps.flatMap patNames
  | .alt (p :: _) => patNames p
  | _ => []

/-- A variant used as a value: a unit variant, or a function building one. -/
def Ctx.variantValue (c : Ctx) (k : String) (tag : Nat) : Expr :=
  let arity := match c.adts.get? k with
    | some d => ((d.variants[tag]?).map (·.2.length)).getD 0
    | none => 0
  if arity = 0 then .con k tag []
  else
    let xs := (List.range arity).map (s!"%v{·}")
    .lam xs (.con k tag (xs.map (.place · [])))

def Ctx.isType (c : Ctx) (t : String) : Bool := builtinTypes.contains t || c.scope.types.contains t

def Ctx.variant (c : Ctx) (v : String) : Option (String × Nat) :=
  match c.scope.variants.get? v with
  | some [kt] => some kt
  | _ => none

/-- `T.v` where `T` is an enum. -/
def Ctx.qvariant (c : Ctx) (t v : String) : Option (String × Nat) :=
  let k := c.tyKey t
  match c.adts.get? k with
  | some d => if d.isStruct then none else ((d.variants.map (·.1)).idxOf? v).map (k, ·)
  | none => none

mutual
partial def tE (c : Ctx) (ls : List String) : SExpr → TM Expr
  | .int i => pure (.lit (.int i))
  | .float _ => pure (.unsup "Float")
  | .bool b => pure (.lit (.bool b))
  | .unit => pure unitE
  | .str segs => do
    let parts ← segs.mapM fun s => match s with
      | .lit l => pure (Expr.lit (.str l))
      | .expr e => do return .prim "%show" [← tE c ls e]
      | .fmt e spec => do return .prim "%fmt" [← tE c ls e, .lit (.str spec)]
    match parts with
    | [Expr.lit (.str l)] => pure (.lit (.str l))
    | [] => pure (.lit (.str ""))
    | _ => pure (.prim "%concat" parts)
  | .name n => pure (tName c ls n)
  | .path t m => pure (match c.qvariant t m with
    | some (k, tag) => c.variantValue k tag
    | none =>
      let key := c.tyKey t ++ "." ++ m
      .fnref key)
  | e@(.field b f) => do
    match ← tPlace c ls e with
    | some (x, ps) => pure (.place x ps)
    | none => return .proj (← tE c ls b) [.fld f]
  | e@(.tfield b i) => do
    match ← tPlace c ls e with
    | some (x, ps) => pure (.place x ps)
    | none => return .proj (← tE c ls b) [.tfld i]
  | e@(.index a b) => do
    match ← tPlace c ls e with
    | some (x, ps) => pure (.place x ps)
    | none => return .prim "%index" [← tE c ls a, ← tE c ls b]
  | .call f args => do
    let as ← args.mapM (tE c ls)
    match f with
    | .name n =>
      if ls.contains n then return .call (.place n []) as
      match c.scope.fns.get? n with
      | some (k, true) => return .call (.call (.fnref k) []) as
      | some (k, false) => return .call (.fnref k) as
      | none => match c.variant n with
        | some (k, tag) => return .con k tag as
        | none => match c.scope.externs.get? n with
          | some p => return .prim p as
          | none => return .unsup s!"function {n}"
    | .path t m => match c.qvariant t m with
      | some (k, tag) => return .con k tag as
      | none =>
        if c.isType t then return .call (.fnref (c.tyKey t ++ "." ++ m)) as
        else return .mcall m (tName c ls t) as
    | _ => return .call (← tE c ls f) as
  | .method r m args => do
    let as ← args.mapM (tE c ls)
    return .mcall m (← tE c ls r) as
  | .unary "neg" e => do return .prim "%neg" [← tE c ls e]
  | .unary _ e => do return .prim "%not" [← tE c ls e]
  | .binary "And" l r => do return .ite (← tE c ls l) (← tE c ls r) (.lit (.bool false))
  | .binary "Or" l r => do return .ite (← tE c ls l) (.lit (.bool true)) (← tE c ls r)
  | .binary op l r => do
    match binop op with
    | some p => return .prim p [← tE c ls l, ← tE c ls r]
    | none => return .unsup s!"operator {op}"
  | .ite cond t e => do
    let e' ← match e with
      | some x => tE c ls x
      | none => pure unitE
    return .ite (← tE c ls cond) (← tBlock c ls t) e'
  | .mtch s arms => do
    let as ← arms.mapM fun a => match a with
      | .arm p g b => do
        let ls' := ls ++ patNames p
        let g' ← match g with
          | some x => pure (some (← tE c ls' x))
          | none => pure none
        return (tPat p, g', ← tE c ls' b)
      | .fallback b => do return (Pat.wild, none, ← tE c ls b)
    return .mtch (← tE c ls s) as
  | .block b => tBlock c ls b
  | .list es => do return .seq .list (← es.mapM (tE c ls))
  | .tuple es => do return .seq .tup (← es.mapM (tE c ls))
  | .map kvs => do
    let es ← kvs.mapM fun (k, v) => do return Expr.seq .tup [← tE c ls k, ← tE c ls v]
    return .prim "%map" es
  | .new n fs base => tNew c ls n fs base
  | .try e => do return .try (← tE c ls e)
  | .mutarg e => tE c ls e
  | .lambda ps _ body => do
    let names := ps.map (·.1)
    return .lam names (← tE c (ls ++ names) body)
  | .dyn _ _ => pure (.unsup "dyn")

partial def tName (c : Ctx) (ls : List String) (n : String) : Expr :=
  if ls.contains n then .place n []
  else match c.scope.fns.get? n with
    | some (k, true) => .call (.fnref k) []
    | some (k, false) => .fnref k
    | none => match c.variant n with
      | some (k, tag) => c.variantValue k tag
      | none => match c.scope.externs.get? n with
        | some p => .fnref p
        | none => .unsup s!"name {n}"

/-- A place (`x`, `x.f`, `x[i]`, `x.0`) rooted at a local variable. -/
partial def tPlace (c : Ctx) (ls : List String) : SExpr → TM (Option (String × List PStep))
  | .name n => pure (if ls.contains n then some (n, []) else none)
  | .field b f => do return (← tPlace c ls b).map fun (x, ps) => (x, ps ++ [.fld f])
  | .tfield b i => do return (← tPlace c ls b).map fun (x, ps) => (x, ps ++ [.tfld i])
  | .index a b => do
    match ← tPlace c ls a with
    | some (x, ps) => return some (x, ps ++ [.idx (← tE c ls b)])
    | none => return none
  | _ => pure none

partial def tNew (c : Ctx) (ls : List String) (n : String) (fs : List (String × SExpr))
    (base : Option SExpr) : TM Expr := do
  let k := c.tyKey n
  match c.adts.get? k with
  | none => return .unsup s!"struct {n}"
  | some d =>
    -- the fields in source order, then the base, each bound once
    let mut binds : List (String × Expr) := []
    let mut names : List (String × String) := []
    for (f, e) in fs do
      let t ← fresh "f"
      binds := binds ++ [(t, ← tE c ls e)]
      names := names ++ [(f, t)]
    let bname ← fresh "base"
    let mut args : List Expr := []
    for f in d.fields do
      match names.lookup f with
      | some t => args := args ++ [.place t []]
      | none => match base with
        | some _ => args := args ++ [.place bname [.fld f]]
        | none => return .unsup s!"field {f} missing"
    let mut body : Expr := .con k 0 args
    if let some b := base then
      body := .letE bname false (← tE c ls b) body
    for (t, e) in binds.reverse do
      body := .letE t false e body
    return body

partial def tBlock (c : Ctx) (ls : List String) : List SStmt → TM Expr
  | [] => pure unitE
  | [.expr e] => tE c ls e
  | s :: rest => tStmt c ls s rest

partial def tStmt (c : Ctx) (ls : List String) (s : SStmt) (rest : List SStmt) : TM Expr := do
  match s with
  | .letS (.bind x) mutable _ v none => return .letE x mutable (← tE c ls v) (← tBlock c (ls ++ [x]) rest)
  | .letS p _ _ v els => do
    let body ← tBlock c (ls ++ patNames p) rest
    let arms := match els with
      | none => pure [(tPat p, none, body)]
      | some b => do return [(tPat p, none, body), (Pat.wild, none, ← tBlock c ls b)]
    return .mtch (← tE c ls v) (← arms)
  | .expr e => return .seqE (← tE c ls e) (← tBlock c ls rest)
  | .assign op t v => do
    match ← tPlace c ls t with
    | some (x, ps) =>
      let v' ← tE c ls v
      let a : Expr ← match op, op.bind binop with
        | none, _ => pure (.assign x ps v')
        | some _, some p => do
          -- reference §6: the right-hand side, then the target's current value
          let t ← fresh "rhs"
          pure (.letE t false v' (.assign x ps (.prim p [.place x ps, .place t []])))
        | some _, none => pure (.unsup "assignment operator")
      return .seqE a (← tBlock c ls rest)
    | none => return .unsup "assignment to this target"
  | .whileS cond b => return .seqE (.while (← tE c ls cond) (← tBlock c ls b)) (← tBlock c ls rest)
  | .forRange p a b body => do
    let lo ← fresh "lo"
    let hi ← fresh "hi"
    let i ← fresh "i"
    let x ← match p with
      | .bind x => pure x
      | _ => fresh "_"
    let body' ← tBlock c (ls ++ [x]) body
    let step : Expr := .assign i [] (.prim "%add" [.place i [], .lit (.int 1)])
    let loop : Expr := .while (.prim "%lt" [.place i [], .place hi []])
      (.letE x false (.place i []) (.seqE step body'))
    let e := Expr.letE lo false (← tE c ls a) (.letE hi false (← tE c ls b) (.letE i true (.place lo []) loop))
    return .seqE e (← tBlock c ls rest)
  | .forEach p coll body => do
    let xs ← fresh "xs"
    let n ← fresh "n"
    let i ← fresh "i"
    let body' ← tBlock c (ls ++ patNames p) body
    let step : Expr := .assign i [] (.prim "%add" [.place i [], .lit (.int 1)])
    let loop : Expr := .while (.prim "%lt" [.place i [], .place n []])
      (.mtch (.place xs [.idx (.place i [])]) [(tPat p, none, .seqE step body')])
    let e := Expr.letE xs false (.prim "%iter" [← tE c ls coll])
      (.letE n false (.prim "List.len" [.place xs []]) (.letE i true (.lit (.int 0)) loop))
    return .seqE e (← tBlock c ls rest)
  | .ret v => do
    let v' ← match v with
      | some x => tE c ls x
      | none => pure unitE
    return .seqE (.ret v') (← tBlock c ls rest)
  | .brk => return .seqE .brk (← tBlock c ls rest)
  | .cont => return .seqE .cont (← tBlock c ls rest)
end

/-! ## Programs -/

def kindOf : String → Kind
  | "linear" => .linear
  | "unique" => .unique
  | _ => .copy

structure Program where
  prog : Prog
  main : Option String
  mainArity : Nat
  /-- Constructs the program uses that the core does not model (top level). -/
  unsupported : List String

/-- Core definitions of the prelude externs that consume their receiver. -/
def coreExterns : List (String × FnDecl) :=
  let unwrap (ok bad : String) (badPs : List Pat) (msg : Expr) : Expr :=
    .mtch (.place "self" []) [(.con ok [.bind "%x"], none, .place "%x" []), (.con bad badPs, none, msg)]
  [("Option.unwrap", { params := [("self", .val)], body := unwrap "Some" "None" [] (.prim "panic" [.lit (.str "unwrap on None")]) }),
   ("Option.expect", { params := [("self", .val), ("msg", .val)], body := unwrap "Some" "None" [] (.prim "panic" [.place "msg" []]) }),
   ("Result.unwrap", { params := [("self", .val)], body := unwrap "Ok" "Err" [.wild] (.prim "panic" [.lit (.str "unwrap on Err")]) }),
   ("Result.expect", { params := [("self", .val), ("msg", .val)], body := unwrap "Ok" "Err" [.wild] (.prim "panic" [.place "msg" []]) })]

def declare (sc : Scope) (pfx : String) (items : List SItem) (hide : Scope) : Scope := Id.run do
  let mut sc := sc
  let mut own : Std.HashMap String (List (String × Nat)) := {}
  for it in items do
    match it with
    | .struct s =>
      let k := if hide.types.contains s.name then "<main>." ++ s.name else s.name
      sc := { sc with types := sc.types.insert s.name k }
    | .enum e =>
      let k := if hide.types.contains e.name then "<main>." ++ e.name else e.name
      sc := { sc with types := sc.types.insert e.name k }
      for (v, i) in e.variants.zipIdx do
        own := own.insert v.1 ((own.getD v.1 []) ++ [(k, i)])
    | .fn f =>
      if f.owner.isNone then
        if f.isExtern then sc := { sc with externs := sc.externs.insert f.name f.name }
        else sc := { sc with fns := sc.fns.insert f.name (pfx ++ f.name, f.isConst) }
    | _ => pure ()
  -- a file's own variants hide the prelude's
  for (v, ks) in own.toList do
    sc := { sc with variants := sc.variants.insert v ks }
  return sc

def adtDecls (sc : Scope) (items : List SItem) (adts : Std.HashMap String AdtDecl) : Std.HashMap String AdtDecl := Id.run do
  let mut adts := adts
  for it in items do
    match it with
    | .struct s =>
      let c : Ctx := { scope := sc, adts, tparams := s.tparams }
      adts := adts.insert (c.tyKey s.name)
        { name := s.name, isStruct := true, kind := kindOf s.kind, tparams := s.tparams.length,
          fields := s.fields.map (·.1), variants := [(s.name, s.fields.map (c.ty ·.2))] }
    | .enum e =>
      let c : Ctx := { scope := sc, adts, tparams := e.tparams }
      adts := adts.insert (c.tyKey e.name)
        { name := e.name, isStruct := false, kind := kindOf e.kind, tparams := e.tparams.length,
          variants := e.variants.map fun (v, ts) => (v, ts.map c.ty) }
    | _ => pure ()
  return adts

def fnDecls (c0 : Ctx) (pfx : String) (items : List SItem) : TM (List (String × FnDecl) × List String) := do
  let mut out : List (String × FnDecl) := []
  let mut bad : List String := []
  for it in items do
    match it with
    | .fn f =>
      match f.body with
      | none => pure ()
      | some b =>
        let ownerTps := match f.owner with
          | some (.named _ as) => as.filterMap fun t => match t with | .named n [] => some n | _ => none
          | _ => []
        let c := { c0 with tparams := ownerTps ++ f.tparams }
        let (key, owner) := match f.owner with
          | some (.named n _) =>
            let k := c.tyKey n
            (k ++ "." ++ f.name, if builtinTypes.contains n then none else some k)
          | some _ => ("%bad." ++ f.name, none)
          | none => (pfx ++ f.name, none)
        let selfP := match f.selfKind with
          | "self" => [("self", Mode.val)]
          | "mut-self" => [("self", Mode.mut)]
          | "ref-self" => [("self", Mode.ref)]
          | _ => []
        let ps := selfP ++ f.params.map fun p => (p.name, if p.byMut then Mode.mut else if p.byRef then Mode.ref else Mode.val)
        let body ← tBlock c (ps.map (·.1)) b
        let d : FnDecl := {
          params := ps
          body := body
          owner := owner
          tparams := c.tparams.length
          ptys := f.params.map (fun p => c.ty p.ty)
          ret := (f.ret.map c.ty).getD .unit }
        out := out ++ [(key, d)]
    | .bad line msg => bad := bad ++ [s!"{msg}: {line.take 60}"]
    | .other line => if pfx == "m:" then bad := bad ++ [s!"{(line.splitOn " ").headD "item"} (traits and impls)"]
    | .imp n => bad := bad ++ [s!"import {n}"]
    | _ => pure ()
  return (out, bad)

def externNames (items : List SItem) (sc : Scope) : List String :=
  items.filterMap fun it => match it with
    | .fn f => if !f.isExtern then none else match f.owner with
      | some (.named n _) => some ((({ scope := sc, adts := {} } : Ctx).tyKey n) ++ "." ++ f.name)
      | some _ => none
      | none => some f.name
    | _ => none

def translate (prelude prog : List SItem) (input : List UInt8) : Program :=
  let psc := declare {} "p:" prelude {}
  let msc := declare psc "m:" prog psc
  let adts := adtDecls psc prelude {}
  let adts := adtDecls msc prog adts
  let ((pfns, _), n) := (fnDecls { scope := psc, adts } "p:" prelude).run 0
  let ((mfns, bad), _) := (fnDecls { scope := msc, adts } "m:" prog).run n
  let fns : Std.HashMap String FnDecl := Std.HashMap.ofList (pfns ++ coreExterns ++ mfns)
  let main : Option SFn := prog.findSome? fun it => match it with
    | .fn f => if f.name == "main" && f.owner.isNone && f.body.isSome then some f else none
    | _ => none
  { prog := { fns := fns.get?, adts := adts.get?, prim := Prims.table adts.get? (externNames prelude psc) input },
    main := main.map fun _ => "m:main",
    mainArity := (main.map (·.params.length)).getD 0,
    unsupported := bad }

end Front

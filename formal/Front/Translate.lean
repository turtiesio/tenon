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
  /-- The program has Show impls: formatting goes through `%show` (Prims.lean, "Show impls"). -/
  shows : Bool := false

/-- The state: a counter for hidden names, and whether a `dyn` value is built. -/
abbrev TM := StateM (Nat × Bool)

def fresh (base : String) : TM String := do
  let (n, d) ← get
  set (n + 1, d)
  return s!"%{base}{n}"

/-- A place whose index steps have no effect (it can be read twice). -/
def purePlace : Expr → Bool
  | .place _ ps => ps.all fun st => match st with
    | .idx (.place _ []) | .idx (.lit _) => true
    | .idx _ => false
    | _ => true
  | _ => false

/-- `"{p}"` when the program has Show impls: the builtin text, unless the
value contains a type with a Show impl; then the core function `%show`. -/
def showAt (p : Expr) (s : String) (top : Bool) : Expr :=
  .mtch (.prim "%showq" [p, .lit (.bool top)])
    [(.con "Ok" [.bind s], none, .place s []), (.wild, none, .call (.fnref "%show") [p, .lit (.bool top)])]

def showE (x : Expr) : TM Expr := do
  let s ← fresh "s"
  if purePlace x then return showAt x s true
  let t ← fresh "t"
  return .letE t false x (showAt (.place t []) s true)

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
  | .float s => pure (.prim "%float" [.lit (.str s)])
  | .bool b => pure (.lit (.bool b))
  | .unit => pure unitE
  | .str segs => do
    let parts ← segs.mapM fun s => match s with
      | .lit l => pure (Expr.lit (.str l))
      | .expr e => do
        if c.shows then showE (← tE c ls e) else return .prim "%show" [← tE c ls e]
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
  | .dyn _ e => do
    -- a `dyn` value is the value: methods dispatch on its head at run time
    modify fun (n, _) => (n, true)
    tE c ls e

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
  /-- Formatting goes through `%show` (the program has Show impls). -/
  shows : Bool := false

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

/-- A function or method body (`f`'s parameters; `c` has its type parameters). -/
def declOf (c : Ctx) (f : SFn) (b : List SStmt) (owner : Option String) : TM FnDecl := do
  let selfP := match f.selfKind with
    | "self" => [("self", Mode.val)]
    | "mut-self" => [("self", Mode.mut)]
    | "ref-self" => [("self", Mode.ref)]
    | _ => []
  let ps := selfP ++ f.params.map fun p => (p.name, if p.byMut then Mode.mut else if p.byRef then Mode.ref else Mode.val)
  let body ← tBlock c (ps.map (·.1)) b
  return {
    params := ps
    body := body
    owner := owner
    tparams := c.tparams.length
    ptys := f.params.map (fun p => c.ty p.ty)
    ret := (f.ret.map c.ty).getD .unit }

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
        out := out ++ [(key, ← declOf c f b owner)]
    | .bad line msg => bad := bad ++ [s!"{msg}: {line.take 60}"]
    | .imp n => bad := bad ++ [s!"import {n}"]
    | _ => pure ()
  return (out, bad)

/-! ## Traits and impls (reference §17)

An impl's methods become methods of the target type's head (`Square.area`,
`List.describe`, `Tuple.m`, `Fn.m`), with the trait's default bodies for the
methods the impl does not give: a call dispatches on the receiver's value,
which is what static dispatch and a `dyn` table select for a well-typed
program. The type's own methods win (reference §17, "Calling"). Two impls of
one trait for instantiations of one type (`Option[Int]`, `Option[Str]`)
would share a key: their methods are unsupported. A Show impl's `to_str` is
a function the formatting calls (`%show`, Prims.lean "Show impls"). -/

def targetKey (c : Ctx) (tps : List String) : STy → Option (String × List STy)
  | .named n as =>
    if tps.contains n || n.startsWith "dyn " then none else some (c.tyKey n, as)
  | .tup [] => some ("Unit", [])
  | .tup ts => some ("Tuple", ts)
  | .fn .. => some ("Fn", [])

/-- The impl's parameters as markers (`.adt "%tp<i>" []`) for `ShowImpl.args`. -/
partial def markTy : Ty → Ty
  | .var i => .adt s!"%tp{i}" []
  | .tup ts => .tup (ts.map markTy)
  | .list t => .list (markTy t)
  | .map k v => .map (markTy k) (markTy v)
  | .adt n ts => .adt n (ts.map markTy)
  | .fn ps r => .fn (ps.map markTy) (markTy r)
  | t => t

structure Impls where
  fns : List (String × FnDecl) := []
  shows : List Prims.ShowImpl := []
  bad : List String := []

/-- The impls of `items` (`own`: the types this file declares, whose impls finish
a linear `self`; `taken`: keys of the types' own methods). -/
def implDecls (c0 : Ctx) (items : List SItem) (traits : Std.HashMap String (List SFn))
    (own : List String) (taken : String → Bool) (acc : Impls) : TM Impls := do
  let mut acc := acc
  for it in items do
    match it with
    | .impl tps tr target ms =>
      let names := tps.map (·.1)
      match targetKey c0 names target, traits.get? tr with
      | some (k, as), some tms =>
        let c := { c0 with tparams := names }
        let owner := match target with
          | .named n _ => if own.contains n then some k else none
          | _ => none
        let defaults := tms.filter fun m => m.body.isSome && !ms.any (·.name == m.name)
        for m in ms ++ defaults do
          let some b := m.body | continue
          let cm := { c with tparams := names ++ m.tparams }
          let d ← declOf cm m b owner
          if tr == "Show" && m.name == "to_str" then
            let fk := s!"%show#{k}#{acc.shows.length}"
            acc := { acc with fns := acc.fns ++ [(fk, d)],
                              shows := acc.shows ++ [{ key := k, fn := fk, bounds := tps.map (·.2),
                                                       args := as.map fun a => markTy (c.ty a) }] }
          else
            let key := k ++ "." ++ m.name
            -- the type's own method wins on a direct call, the trait's through a
            -- bound or `dyn` (static types decide): outside the subset
            if taken key then
              acc := { acc with bad := acc.bad ++ [s!"{key}: a type's own method and a trait method of one name"] }
              continue
            if acc.fns.any (·.1 == key) then
              let u : FnDecl := { d with body := .unsup s!"impls of {key} for several instantiations" }
              acc := { acc with fns := (acc.fns.filter (·.1 != key)) ++ [(key, u)] }
            else acc := { acc with fns := acc.fns ++ [(key, d)] }
      | none, _ => acc := { acc with bad := acc.bad ++ [s!"impl {tr} for this type"] }
      | _, none => acc := { acc with bad := acc.bad ++ [s!"trait {tr}"] }
    | _ => pure ()
  return acc

def traitsOf (items : List SItem) (m : Std.HashMap String (List SFn)) : Std.HashMap String (List SFn) :=
  items.foldl (fun m it => match it with | .trait n ms => m.insert n ms | _ => m) m

def ownTypes (items : List SItem) : List String :=
  items.filterMap fun it => match it with
    | .struct s => some s.name
    | .enum e => some e.name
    | _ => none

/-- `%show(ref x, top)`: the text of `x` when it contains a type with a Show impl. -/
def showWalker : FnDecl :=
  let p (x : String) : Expr := .place x []
  let i1 : Expr := .prim "%add" [p "%i", .lit (.int 1)]
  let loop : Expr :=
    .letE "%acc" true (.place "%seps" [.idx (.lit (.int 0))])
      (.letE "%i" true (.lit (.int 0))
        (.seqE (.while (.prim "%lt" [p "%i", .prim "List.len" [p "%kids"]])
            (.seqE (.assign "%acc" [] (.prim "%concat" [p "%acc",
                      .call (.fnref "%show") [.place "%kids" [.idx (p "%i")], .lit (.bool false)],
                      .place "%seps" [.idx i1]]))
              (.assign "%i" [] i1)))
          (p "%acc")))
  { params := [("x", .ref), ("top", .val)],
    body := .mtch (.prim "%showparts" [p "x", p "top"])
      [(.con "Ok" [.bind "%f"], none, .call (p "%f") [p "x"]),
       (.con "Err" [.tup [.bind "%seps", .bind "%kids"]], none, loop)] }

/-- `x.to_str()` when the program has Show impls (for the heads that can contain one). -/
def toStrDecl : FnDecl :=
  { params := [("self", .val)], body := showAt (.place "self" []) "%s" true, ret := .str }

/-- `xs.sort_by(key)`, `xs.sort_by_desc(key)` (compiler/ieval.tn: the keys first,
element by element, then the interpreter's merge sort). -/
def sortByDecl (desc : Bool) : FnDecl :=
  let p (x : String) : Expr := .place x []
  let i1 : Expr := .prim "%add" [p "%i", .lit (.int 1)]
  { params := [("self", .mut), ("key", .val)],
    body :=
      .letE "%ks" true (.seq .list [])
        (.letE "%i" true (.lit (.int 0))
          (.seqE (.while (.prim "%lt" [p "%i", .prim "List.len" [p "self"]])
              (.seqE (.mcall "push" (p "%ks") [.call (p "key") [.place "self" [.idx (p "%i")]]])
                (.assign "%i" [] i1)))
            (.assign "self" [] (.prim "%sortby" [p "self", p "%ks", .lit (.bool desc)])))) }

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
  let isShow (it : SItem) := match it with | .impl _ "Show" _ _ => true | _ => false
  let shows := prelude.any isShow || prog.any isShow
  let ((pfns, _), n) := (fnDecls { scope := psc, adts, shows } "p:" prelude).run (0, false)
  let ((mfns, bad), n) := (fnDecls { scope := msc, adts, shows } "m:" prog).run n
  let externs := externNames prelude psc
  let base : Std.HashMap String FnDecl :=
    Std.HashMap.ofList (pfns ++ coreExterns ++ [("List.sort_by", sortByDecl false), ("List.sort_by_desc", sortByDecl true)] ++ mfns)
  let taken (k : String) : Bool :=
    base.contains k || externs.contains k || (Prims.pureTable adts.get? k).isSome
  let ptraits := traitsOf prelude {}
  let mtraits := traitsOf prog ptraits
  let (im, n) := (implDecls { scope := psc, adts, shows } prelude ptraits (ownTypes prelude) taken {}).run n
  let (im, (_, hasDyn)) := (implDecls { scope := msc, adts, shows } prog mtraits (ownTypes prog) taken im).run n
  let fns := im.fns.foldl (fun m (k, d) => m.insert k d) base
  let fns := if !shows then fns else
    let heads := ["List", "Map", "Tuple"] ++ adts.toList.map (·.1)
    let fns := fns.insert "%show" showWalker
    heads.foldl (fun m h => if m.contains (h ++ ".to_str") then m else m.insert (h ++ ".to_str") toStrDecl) fns
  let main : Option SFn := prog.findSome? fun it => match it with
    | .fn f => if f.name == "main" && f.owner.isNone && f.body.isSome then some f else none
    | _ => none
  { prog := { fns := fns.get?, adts := adts.get?, prim := Prims.table adts.get? externs input im.shows hasDyn },
    main := main.map fun _ => "m:main",
    mainArity := (main.map (·.params.length)).getD 0,
    unsupported := bad ++ im.bad,
    shows := shows }

end Front

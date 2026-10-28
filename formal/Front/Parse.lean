/-
A reader for the dump of `tenon ast FILE` (compiler/astdump.tn): one
top-level item per line, S-expressions whose types are printed as Tenon
source (`Map[K, V]`, `fn(Int) -> Int`). Not part of the proofs.
-/
import Front.Ast

namespace Front

abbrev PM := ReaderT (Array Char) (StateT Nat (Except String))

def peekC : PM (Option Char) := do
  let s ← read
  return s[← get]?

def peekAt (k : Nat) : PM (Option Char) := do
  let s ← read
  return s[(← get) + k]?

def fail (msg : String) : PM α := do
  let s ← read
  let i ← get
  let ctx := String.ofList ((s.toList.drop i).take 40)
  throw s!"{msg} at {i}: {ctx}"

def nextC : PM Char := do
  match ← peekC with
  | some c => modify (· + 1); return c
  | none => fail "unexpected end"

def tryLit (lit : String) : PM Bool := do
  let s ← read
  let i ← get
  let cs := lit.toList
  let ok := (List.range cs.length).all fun k => s[i + k]? == cs[k]?
  if ok then set (i + cs.length)
  return ok

def lookLit (lit : String) : PM Bool := do
  let s ← read
  let i ← get
  let cs := lit.toList
  return (List.range cs.length).all fun k => s[i + k]? == cs[k]?

def expect (lit : String) : PM Unit := do
  unless ← tryLit lit do fail s!"expected '{lit}'"

def isIdent (c : Char) : Bool := c.isAlphanum || c == '_'

partial def takeWhileP (p : Char → Bool) (acc : String := "") : PM String := do
  match ← peekC with
  | some c => if p c then do let _ ← nextC; takeWhileP p (acc.push c) else return acc
  | none => return acc

def ident : PM String := do
  let s ← takeWhileP isIdent
  if s.isEmpty then fail "expected a name"
  return s

/-- A name that may be qualified by modules (`journal.Loaded`). -/
def qident : PM String := takeWhileP fun c => isIdent c || c == '.'

/-- An atom: up to a space or a closing parenthesis. -/
def atom : PM String := takeWhileP fun c => c != ' ' && c != ')' && c != '('

def intLit : PM Int := do
  let s ← atom
  match s.toInt? with
  | some i => return i
  | none => fail s!"bad integer {s}"

def hexVal (s : String) : Nat :=
  s.foldl (fun n c =>
    let d := if c.isDigit then c.toNat - '0'.toNat
      else if 'a' ≤ c && c ≤ 'f' then c.toNat - 'a'.toNat + 10
      else if 'A' ≤ c && c ≤ 'F' then c.toNat - 'A'.toNat + 10 else 0
    n * 16 + d) 0

/-- A string as `lexer.quoted` prints it (runtime/tenon.h `tn_Str_show`). -/
partial def strLit : PM String := do
  expect "\""
  let rec go (acc : String) : PM String := do
    let c ← nextC
    if c == '"' then return acc
    if c == '\\' then
      let e ← nextC
      match e with
      | 'n' => go (acc.push '\n')
      | 't' => go (acc.push '\t')
      | 'r' => go (acc.push '\r')
      | '0' => go (acc.push (Char.ofNat 0))
      | 'u' =>
        expect "{"
        let h ← takeWhileP (· != '}')
        expect "}"
        go (acc.push (Char.ofNat (hexVal h)))
      | c' => go (acc.push c')
    else go (acc.push c)
  go ""

/-! ## Types -/

mutual
partial def pTy : PM STy := do
  if ← tryLit "fn(" then
    let ps ← pTys ')'
    expect ")"
    expect " -> "
    let r ← pTy
    return .fn ps r
  if (← peekC) == some '(' then
    let _ ← nextC
    let ts ← pTys ')'
    expect ")"
    return .tup ts
  let n ← qident
  if n.isEmpty then fail "expected a type"
  if n == "dyn" then
    expect " "
    let t ← qident
    return .named ("dyn " ++ t) []
  if (← peekC) == some '[' then
    let _ ← nextC
    let as ← pTys ']'
    expect "]"
    return .named n as
  return .named n []

partial def pTys (close : Char) : PM (List STy) := do
  if (← peekC) == some close then return []
  let t ← pTy
  let mut ts := #[t]
  repeat
    if !(← tryLit ", ") then break
    ts := ts.push (← pTy)
  return ts.toList
end

/-! ## Patterns and expressions -/

def pos : PM Unit := do
  expect "@"
  let _ ← takeWhileP fun c => c.isDigit || c == ':'
  expect " "

partial def pPat : PM SPat := do
  expect "("
  pos
  let head ← atom
  let p ← (match head with
    | "_" => pure SPat.wild
    | "bind" => do expect " "; return .bind (← ident)
    | "int" => do expect " "; return .int (← intLit)
    | "str" => do expect " "; return .str (← strLit)
    | "bool" => do expect " "; return .bool ((← atom) == "true")
    | "tuple" => do return .tup (← pPats)
    | "variant" => do
      expect " "
      let n ← qident
      let ps ← pPats
      match n.splitOn "." with
      | [q, v] => return .variant (some q) v ps
      | _ => return .variant none n ps
    | "or" => do return .alt (← pPats)
    | h => fail s!"pattern {h}")
  expect ")"
  return p
where
  pPats : PM (List SPat) := do
    let mut ps := #[]
    repeat
      if !((← peekC) == some ' ') then break
      let _ ← nextC
      ps := ps.push (← pPat)
    return ps.toList

mutual
partial def pExpr : PM SExpr := do
  expect "("
  pos
  if (← peekC) == some '(' then
    let b ← pBlock
    expect ")"
    return .block b
  let head ← atom
  let e ← (match head with
    | "int" => do expect " "; return .int (← intLit)
    | "float" => do expect " "; return .float (← atom)
    | "bool" => do expect " "; return .bool ((← atom) == "true")
    | "str" => do return .str (← pSegs)
    | "unit" => pure SExpr.unit
    | "name" => do expect " "; return .name (← qident)
    | "path" => do
      expect " "
      let t ← pTyText
      expect " "
      return .path t (← ident)
    | "field" => do
      expect " "
      let b ← pExpr
      expect " "
      return .field b (← ident)
    | "tfield" => do
      expect " "
      let b ← pExpr
      expect " "
      return .tfield b (← intLit).toNat
    | "index" => do
      expect " "
      let a ← pExpr
      expect " "
      return .index a (← pExpr)
    | "call" => do
      expect " "
      let f ← pExpr
      return .call f (← pExprs)
    | "method" => do
      expect " "
      let r ← pExpr
      expect " "
      let m ← ident
      return .method r m (← pExprs)
    | "neg" => do expect " "; return .unary "neg" (← pExpr)
    | "not" => do expect " "; return .unary "not" (← pExpr)
    | "if" => do
      expect " "
      let c ← pExpr
      expect " "
      let t ← pBlock
      if (← peekC) == some ' ' then
        let _ ← nextC
        return .ite c t (some (← pExpr))
      return .ite c t none
    | "match" => do
      expect " "
      let s ← pExpr
      let mut arms := #[]
      repeat
        if !((← peekC) == some ' ') then break
        let _ ← nextC
        arms := arms.push (← pArm)
      return .mtch s arms.toList
    | "list" => do return .list (← pExprs)
    | "tuple" => do return .tuple (← pExprs)
    | "map" => do
      let mut kvs := #[]
      repeat
        if !((← peekC) == some ' ') then break
        let _ ← nextC
        expect "("
        let k ← pExpr
        expect " "
        let v ← pExpr
        expect ")"
        kvs := kvs.push (k, v)
      return .map kvs.toList
    | "new" => do
      expect " "
      let n ← qident
      let mut fs := #[]
      let mut base := none
      repeat
        if !((← peekC) == some ' ') then break
        let _ ← nextC
        expect "("
        if ← tryLit "base " then
          base := some (← pExpr)
        else
          let f ← ident
          expect " "
          fs := fs.push (f, ← pExpr)
        expect ")"
      return .new n fs.toList base
    | "try" => do expect " "; return .try (← pExpr)
    | "mutarg" => do expect " "; return .mutarg (← pExpr)
    | "lambda" => do
      expect " ("
      let mut ps := #[]
      repeat
        if !((← peekC) != some ')') then break
        let x ← ident
        let t ← if ← tryLit ": " then pure (some (← pTy)) else pure none
        ps := ps.push (x, t)
        let _ ← tryLit ", "
      expect ")"
      let r ← if ← tryLit " -> " then pure (some (← pTy)) else pure none
      expect " "
      return .lambda ps.toList r (← pExpr)
    | "dyn" => do
      expect " "
      let t ← qident
      expect " "
      return .dyn t (← pExpr)
    | op =>
      if (op.toList.head?.map Char.isUpper).getD false then do
        expect " "
        let l ← pExpr
        expect " "
        return .binary op l (← pExpr)
      else fail s!"expression {op}")
  expect ")"
  return e

/-- The type text of a `path` (`List`, `Option`, `Pair[Int, Str]`). -/
partial def pTyText : PM String := do
  let n ← qident
  if (← peekC) == some '[' then
    let t ← pTy  -- only to skip it
    let _ := t
    return n
  return n

partial def pExprs : PM (List SExpr) := do
  let mut es := #[]
  repeat
    if !((← peekC) == some ' ') then break
    let _ ← nextC
    es := es.push (← pExpr)
  return es.toList

partial def pSegs : PM (List SSeg) := do
  let mut segs := #[]
  repeat
    if !((← peekC) == some ' ') then break
    let _ ← nextC
    if (← peekC) == some '"' then
      segs := segs.push (.lit (← strLit))
    else if ← tryLit "(fmt " then
      let e ← pExpr
      expect " "
      let spec ← strLit
      expect ")"
      segs := segs.push (.fmt e spec)
    else
      segs := segs.push (.expr (← pExpr))
  return segs.toList

partial def pArm : PM SArm := do
  if ← tryLit "(else " then
    let b ← pExpr
    expect ")"
    return .fallback b
  expect "(arm "
  let p ← pPat
  expect " "
  if ← tryLit "(guard " then
    let g ← pExpr
    expect ") "
    let b ← pExpr
    expect ")"
    return .arm p (some g) b
  let b ← pExpr
  expect ")"
  return .arm p none b

partial def pBlock : PM (List SStmt) := do
  expect "(block"
  let mut ss := #[]
  repeat
    if !((← peekC) == some ' ') then break
    let _ ← nextC
    ss := ss.push (← pStmt)
  expect ")"
  return ss.toList

partial def pStmt : PM SStmt := do
  expect "("
  pos
  let head ← atom
  let s ← (match head with
    | "let" => do
      expect " "
      let mutable ← tryLit "var "
      let p ← pPat
      let t ← if ← tryLit " : " then pure (some (← pTy)) else pure none
      expect " "
      let v ← pExpr
      let els ← if ← tryLit " (else " then do
          let b ← pBlock
          expect ")"
          pure (some b)
        else pure none
      return .letS p mutable t v els
    | "expr" => do expect " "; return .expr (← pExpr)
    | "assign" => do
      expect " "
      let op ← if (← peekC) == some '(' then pure none else do
        let o ← atom
        expect " "
        pure (some o)
      let t ← pExpr
      expect " "
      return .assign op t (← pExpr)
    | "while" => do
      expect " "
      let c ← pExpr
      expect " "
      return .whileS c (← pBlock)
    | "for" => do
      expect " "
      let p ← pPat
      expect " "
      if ← tryLit "(range " then
        let a ← pExpr
        expect " "
        let b ← pExpr
        expect ") "
        return .forRange p a b (← pBlock)
      expect "(each "
      let e ← pExpr
      expect ") "
      return .forEach p e (← pBlock)
    | "return" => do
      if (← peekC) == some ' ' then
        let _ ← nextC
        return .ret (some (← pExpr))
      return .ret none
    | "break" => pure SStmt.brk
    | "continue" => pure SStmt.cont
    | h => fail s!"statement {h}")
  expect ")"
  return s
end

/-! ## Items -/

def trimS (s : String) : String :=
  String.ofList ((s.toList.dropWhile (· == ' ')).reverse.dropWhile (· == ' ')).reverse

def tparamsOf (raw : String) : List String :=
  (raw.splitOn ", ").map fun p => trimS ((p.splitOn ":").headD p)

/-- `Owner.name[tps]` or `name[tps]` (the owner may have type arguments). -/
def pFnName : PM (Option STy × String × List String) := do
  let n ← ident
  let raw ← if (← peekC) == some '[' then do
      let _ ← nextC
      let r ← takeWhileP (· != ']')
      expect "]"
      pure (some r)
    else pure none
  if ← tryLit "." then
    let owner : STy ← match raw with
      | some r => match (pTys ']').run (r ++ "]").toList.toArray |>.run 0 with
        | .ok (as, _) => pure (.named n as)
        | .error _ => pure (.named n [])
      | none => pure (.named n [])
    let m ← ident
    let tps ← if (← peekC) == some '[' then do
        let _ ← nextC
        let r ← takeWhileP (· != ']')
        expect "]"
        pure (tparamsOf r)
      else pure []
    return (some owner, m, tps)
  return (none, n, (raw.map tparamsOf).getD [])

def pKind : PM String := do
  if ← tryLit " linear" then return "linear"
  if ← tryLit " unique" then return "unique"
  return ""

def pFn : PM SFn := do
  let isConst ← if ← tryLit "(const" then pure true else do expect "(fn"; pure false
  let pub ← tryLit " pub"
  expect " "
  let (owner, name, tps) ← pFnName
  let selfKind ← if ← tryLit " mut-self" then pure "mut-self"
    else if ← tryLit " ref-self" then pure "ref-self"
    else if ← tryLit " self" then pure "self" else pure ""
  let mut ps := #[]
  repeat
    if (← lookLit " (block (") || (← lookLit " (block)") then break  -- the body
    if !(← tryLit " (") then break
    let x ← ident
    let r ← tryLit " ref"
    let m ← tryLit " mut"
    expect " "
    let t ← pTy
    expect ")"
    ps := ps.push { name := x, byRef := r, byMut := m, ty := t }
  let ret ← if ← tryLit " -> " then pure (some (← pTy)) else pure none
  let (body, ext) ← if ← tryLit " extern" then pure (none, true)
    else if ← tryLit " " then pure (some (← pBlock), false)
    else pure (none, false)
  expect ")"
  return { isConst, pub, owner, name, tparams := tps, selfKind, params := ps.toList, ret, body, isExtern := ext }

def pItem : PM SItem := do
  if ← tryLit "(import " then
    let n ← qident
    return .imp n
  if ← tryLit "(struct" then
    let _ ← tryLit " pub"
    let k ← pKind
    expect " "
    let (_, n, tps) ← pFnName
    let mut fs := #[]
    repeat
      if !(← tryLit " (") then break
      let _ ← tryLit "pub "
      let f ← ident
      expect " "
      let t ← pTy
      expect ")"
      fs := fs.push (f, t)
    expect ")"
    return .struct { kind := k, name := n, tparams := tps, fields := fs.toList }
  if ← tryLit "(enum" then
    let _ ← tryLit " pub"
    let k ← pKind
    expect " "
    let (_, n, tps) ← pFnName
    let mut vs := #[]
    repeat
      if !(← tryLit " (") then break
      let v ← ident
      let mut ts := #[]
      repeat
        if !(← tryLit " ") then break
        ts := ts.push (← pTy)
      expect ")"
      vs := vs.push (v, ts.toList)
    expect ")"
    return .enum { kind := k, name := n, tparams := tps, variants := vs.toList }
  return .fn (← pFn)

/-- `T: Show + Eq, U` (the bounds of type parameters). -/
def boundsOf (raw : String) : List (String × List String) :=
  (raw.splitOn ", ").map fun p => match p.splitOn ": " with
    | [n, bs] => (trimS n, (bs.splitOn " + ").map trimS)
    | _ => (trimS p, [])

def pMethods : PM (List SFn) := do
  let mut ms := #[]
  repeat
    if !(← lookLit " (fn") && !(← lookLit " (const") then break
    expect " "
    ms := ms.push (← pFn)
  return ms.toList

def pTraitImpl : PM SItem := do
  if ← tryLit "(trait" then
    let _ ← tryLit " pub"
    expect " "
    let n ← qident
    let ms ← pMethods
    expect ")"
    return .trait n ms
  expect "(impl"
  let tps ← if (← peekC) == some '[' then do
      let _ ← nextC
      let r ← takeWhileP (· != ']')
      expect "]"
      pure (boundsOf r)
    else pure []
  expect " "
  let tr ← qident
  expect " for "
  let target ← pTy
  let ms ← pMethods
  expect ")"
  return .impl tps tr target ms

def parseLine (line : String) : SItem :=
  if line.startsWith "(trait" || line.startsWith "(impl" then
    match (pTraitImpl.run line.toList.toArray).run 0 with
    | .ok (it, _) => it
    | .error msg => .bad line msg
  else match (pItem.run line.toList.toArray).run 0 with
    | .ok (it, _) => it
    | .error msg => .bad line msg

def parseDump (text : String) : List SItem :=
  ((text.splitOn "\n").filter (· ≠ "")).map parseLine

end Front

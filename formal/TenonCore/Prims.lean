/-
The concrete builtins of the executable semantics: the `extern fn`s of
lib/prelude.tn the core models, the operators and formatting (reference §8).
They are ordinary Lean functions on values; the evaluator treats them as
abstract operations behind a monitor (Eval.lean `primApply`), so no theorem
depends on their code. Their behaviour is what the differential test
(ops/gates/formal_diff.py) compares with `tenon run`.
-/
import TenonCore.Eval
import TenonCore.PrimFloat

namespace Tenon.Prims
open Tenon

abbrev Adts := String → Option AdtDecl

/-- A result before the world is threaded in (`table` sets it). -/
def ok3 (v : Val) (self : Option Val) (evs : List Event) : PrimRes := .ok v self evs 0

def MIN64 : Int := -9223372036854775808
def MAX64 : Int := 9223372036854775807

def int64 (i : Int) : PrimRes :=
  if MIN64 ≤ i ∧ i ≤ MAX64 then ok3 (.int i) none [] else .trap "integer overflow"

def some' (v : Val) : Val := .adt "Option" 0 none [v]
def none' : Val := .adt "Option" 1 none []
def ret (v : Val) : PrimRes := ok3 v none []
def strs (xs : List String) : Val := .seq .list (xs.map .str)

/-! ## Float (PrimFloat.lean): `.adt "Float" 0 none [.int bits]` -/

def flt (b : UInt64) : Val := .adt "Float" 0 none [.int b.toNat]
def fltF (f : Float) : Val := flt f.toBits
def asFlt : Val → Option UInt64
  | .adt "Float" 0 none [.int b] => some (UInt64.ofNat b.toNat)
  | _ => none

/-- Equality (compiler/ival.tn `eq`): `Val.beq`, with IEEE equality on floats. -/
partial def veq : Val → Val → Bool
  | .adt "Float" 0 none [.int a], .adt "Float" 0 none [.int b] =>
    Flt.toF (UInt64.ofNat a.toNat) == Flt.toF (UInt64.ofNat b.toNat)
  | .seq .map as, .seq .map bs =>
    as.length == bs.length && as.all (fun a => match a with
      | .seq .tup [k, v] => bs.any (fun b => match b with
        | .seq .tup [k', v'] => Val.beq k k' && veq v v'
        | _ => false)
      | _ => false)
  | .seq k as, .seq k' bs => k == k' && as.length == bs.length && (as.zip bs).all (fun (a, b) => veq a b)
  | .adt s t _ as, .adt s' t' _ bs =>
    s == s' && t == t' && as.length == bs.length && (as.zip bs).all (fun (a, b) => veq a b)
  | a, b => Val.beq a b

/-! ## Bytes of strings -/

def bytesOf (s : String) : List UInt8 := s.toUTF8.toList
def ofBytes (b : List UInt8) : Option String := String.fromUTF8? ⟨b.toArray⟩
def blen (s : String) : Nat := s.utf8ByteSize

def isCont (b : UInt8) : Bool := b &&& 0xC0 == 0x80
def boundary (b : List UInt8) (i : Nat) : Bool :=
  i == 0 || i == b.length || (match b[i]? with | some x => !isCont x | none => false)

def sliceB (b : List UInt8) (a e : Nat) : List UInt8 := (b.drop a).take (e - a)

/-- The first byte offset at or after `from` where `sub` occurs. -/
partial def findB (b sub : List UInt8) (start : Nat) : Option Nat :=
  if start + sub.length > b.length then none
  else if (b.drop start).take sub.length == sub then some start
  else findB b sub (start + 1)

partial def splitB (b sep : List UInt8) (start : Nat) (acc : List (List UInt8)) : List (List UInt8) :=
  match findB b sep start with
  | some i => splitB b sep (i + sep.length) (sliceB b start i :: acc)
  | none => (sliceB b start b.length :: acc).reverse

def str! (b : List UInt8) : String := (ofBytes b).getD ""

/-- UTF-8 decoding with each maximal invalid subpart replaced by U+FFFD
(runtime/tenon.h `tn_utf8_lossy`); `true` when the bytes were valid. -/
def utf8Lossy (s : Array UInt8) : List UInt8 × Bool := Id.run do
  let n := s.size
  let mut out : Array UInt8 := #[]
  let mut ok := true
  let mut i := 0
  let fffd : Array UInt8 := #[0xEF, 0xBF, 0xBD]
  while i < n do
    let c := s[i]!
    if c < 0x80 then
      out := out.push c
      i := i + 1
      continue
    let (need, lo, hi) : Nat × UInt8 × UInt8 :=
      if 0xC2 ≤ c && c ≤ 0xDF then (1, 0x80, 0xBF)
      else if c == 0xE0 then (2, 0xA0, 0xBF)
      else if 0xE1 ≤ c && c ≤ 0xEC then (2, 0x80, 0xBF)
      else if c == 0xED then (2, 0x80, 0x9F)
      else if 0xEE ≤ c && c ≤ 0xEF then (2, 0x80, 0xBF)
      else if c == 0xF0 then (3, 0x90, 0xBF)
      else if 0xF1 ≤ c && c ≤ 0xF3 then (3, 0x80, 0xBF)
      else if c == 0xF4 then (3, 0x80, 0x8F)
      else (0, 0, 0)
    if need == 0 then
      out := out ++ fffd
      ok := false
      i := i + 1
      continue
    let mut j := i + 1
    let mut got := 0
    while got < need && j < n do
      let d := s[j]!
      if (if got == 0 then d < lo || d > hi else d < 0x80 || d > 0xBF) then break
      j := j + 1
      got := got + 1
    if got != need then
      out := out ++ fffd
      ok := false
    else out := out ++ s.extract i j
    i := j
  return (out.toList, ok)

def isSpaceW (c : UInt8) : Bool := c == 32 || c == 9 || c == 10 || c == 13
def isSpaceT (c : UInt8) : Bool := isSpaceW c || c == 12

def wordsB (b : List UInt8) : List String :=
  let rec go (rest : List UInt8) (cur : List UInt8) (acc : List String) : List String :=
    match rest with
    | [] => (if cur.isEmpty then acc else str! cur.reverse :: acc).reverse
    | c :: r =>
      if isSpaceW c then go r [] (if cur.isEmpty then acc else str! cur.reverse :: acc)
      else go r (c :: cur) acc
  go b [] []

def linesOf (s : String) : List String :=
  let parts := s.splitOn "\n"
  let parts := if s.endsWith "\n" then parts.dropLast else parts
  let parts := if s.isEmpty then [] else parts
  parts.map fun l => if l.endsWith "\r" then String.ofList (l.toList.dropLast) else l

def trimB (b : List UInt8) (front back : Bool) : List UInt8 :=
  let b := if front then b.dropWhile isSpaceT else b
  if back then (b.reverse.dropWhile isSpaceT).reverse else b

def toIntS (s : String) : Option Int :=
  let cs := s.toList
  let (neg, ds) := match cs with
    | '-' :: r => (true, r)
    | '+' :: r => (false, r)
    | r => (false, r)
  if ds.isEmpty || !ds.all Char.isDigit then none
  else
    let v : Int := ds.foldl (fun n c => n * 10 + (c.toNat - '0'.toNat)) 0
    let v := if neg then -v else v
    if MIN64 ≤ v ∧ v ≤ MAX64 then some v else none

def upperA (s : String) : String := s.map fun c => if 'a' ≤ c && c ≤ 'z' then c.toUpper else c
def lowerA (s : String) : String := s.map fun c => if 'A' ≤ c && c ≤ 'Z' then c.toLower else c

/-! ## Formatting (reference §8; compiler/ival.tn `show`) -/

def hexDigits (n : Nat) : String := String.ofList (Nat.toDigits 16 n)

def quote (s : String) : String :=
  "\"" ++ String.join (s.toList.map fun c =>
    if c == '"' then "\\\"" else if c == '\\' then "\\\\"
    else if c == '\n' then "\\n" else if c == '\t' then "\\t" else if c == '\r' then "\\r"
    else if c.toNat < 0x20 then "\\u{" ++ hexDigits c.toNat ++ "}"
    else c.toString) ++ "\""

def capName (c : Cap) : String :=
  match c.kind with
  | .console => "<Console>" | .fs => "<Fs>" | .clock => "<Clock>"
  | .net => "<Net>" | .proc => "<Proc>" | .workers => "<Workers>"

partial def showV (adts : Adts) (top : Bool) : Val → String
  | .adt "Float" 0 none [.int b] => Flt.text (UInt64.ofNat b.toNat)
  | .int i => toString i
  | .bool b => if b then "true" else "false"
  | .str s => if top then s else quote s
  | .unit => "()"
  | .seq .list vs => "[" ++ ", ".intercalate (vs.map (showV adts false)) ++ "]"
  | .seq .tup vs => "(" ++ ", ".intercalate (vs.map (showV adts false)) ++ ")"
  | .seq .map kvs =>
    if kvs.isEmpty then "[:]"
    else "[" ++ ", ".intercalate (kvs.map fun e => match e with
      | .seq .tup [k, v] => showV adts false k ++ ": " ++ showV adts false v
      | _ => "?") ++ "]"
  | .adt s tag _ vs => match adts s with
    | some d =>
      if d.isStruct then
        if vs.isEmpty then d.name ++ " {}"
        else d.name ++ " { " ++ ", ".intercalate ((d.fields.zip vs).map fun (f, v) => f ++ ": " ++ showV adts false v) ++ " }"
      else
        let vn := ((d.variants[tag]?).map (·.1)).getD "?"
        if vs.isEmpty then vn else vn ++ "(" ++ ", ".intercalate (vs.map (showV adts false)) ++ ")"
    | none => "?"
  | .clo .. => "<fn>"
  | .fn _ => "<fn>"
  | .cap c => capName c

/-- The derived ordering (compiler/ival.tn `cmp`); `none` for maps and functions. -/
partial def cmp : Val → Val → Option Ordering
  | .adt "Float" 0 none [.int a], .adt "Float" 0 none [.int b] =>
    let x := Flt.toF (UInt64.ofNat a.toNat)
    let y := Flt.toF (UInt64.ofNat b.toNat)
    some (if x < y then .lt else if x > y then .gt else .eq)
  | .int a, .int b => some (compare a b)
  | .bool a, .bool b => some (compare a b)
  | .str a, .str b => some (compare a b)
  | .unit, .unit => some .eq
  | .seq .list as, .seq .list bs => cmpL as bs
  | .seq .tup as, .seq .tup bs => cmpL as bs
  | .adt _ t _ as, .adt _ t' _ bs => if t < t' then some .lt else if t > t' then some .gt else cmpL as bs
  | _, _ => none
where
  cmpL : List Val → List Val → Option Ordering
    | [], [] => some .eq
    | [], _ => some .lt
    | _, [] => some .gt
    | a :: as, b :: bs => match cmp a b with
      | some .eq => cmpL as bs
      | r => r

/-! ## Format specs (reference §8, "Format specs") -/

structure Spec where
  fill : Char := ' '
  align : Option Char := none
  zero : Bool := false
  width : Nat := 0
  comma : Bool := false
  prec : Option Nat := none
  radix : Option Char := none

/-- compiler/parser.tn `parse_spec`. -/
def parseSpec (s : String) : Option Spec := Id.run do
  let cs := s.toList
  if cs.isEmpty then return none
  let isAlign (c : Char) := c == '<' || c == '>' || c == '^'
  let mut sp : Spec := {}
  let mut i := 0
  if cs.length ≥ 2 && isAlign (cs.getD 1 ' ') then
    sp := { sp with fill := cs.getD 0 ' ', align := some (cs.getD 1 ' ') }
    i := 2
  else if isAlign (cs.getD 0 ' ') then
    sp := { sp with align := some (cs.getD 0 ' ') }
    i := 1
  if i + 1 < cs.length && cs.getD i ' ' == '0' && (cs.getD (i + 1) ' ').isDigit then
    sp := { sp with zero := true }
    i := i + 1
  let ds := (cs.drop i).takeWhile Char.isDigit
  i := i + ds.length
  if ds.length > 3 then return none
  if sp.align.isSome && ds.isEmpty then return none
  if sp.zero && sp.align.isSome then return none
  sp := { sp with width := (String.ofList ds).toNat?.getD 0 }
  if cs.getD i ' ' == ',' then
    sp := { sp with comma := true }
    i := i + 1
  if cs.getD i ' ' == '.' then
    let ps := (cs.drop (i + 1)).takeWhile Char.isDigit
    i := i + 1 + ps.length
    if ps.isEmpty || ps.length > 3 then return none
    let pv := (String.ofList ps).toNat!
    if pv > 100 then return none
    sp := { sp with prec := some pv }
  match cs[i]? with
  | some r => if r == 'x' || r == 'X' || r == 'b' || r == 'o' then
      sp := { sp with radix := some r }
      i := i + 1
  | none => pure ()
  if sp.comma && sp.radix.isSome then return none
  if i < cs.length then return none
  return some sp

/-- `,` grouping (compiler/ival.tn `group_digits`): the digits after the sign;
with `0` the padding zeros are digits too. -/
def groupDigits (sp : Spec) (body : String) : String :=
  let cs := body.toList
  let (sign, rest) := match cs with
    | '-' :: r => ("-", r)
    | r => ("", r)
  let ip := rest.takeWhile Char.isDigit
  let n := ip.length
  if n == 0 then body else
  let tail := rest.drop n
  let k := if sp.zero then
      let rec grow (k fuel : Nat) : Nat :=
        match fuel with
        | 0 => k
        | f + 1 => if sign.length + k + (k - 1) / 3 + tail.length < sp.width then grow (k + 1) f else k
      grow n (sp.width + 1)
    else n
  let digits := List.replicate (k - n) '0' ++ ip
  let out := (digits.zipIdx.map fun (c, i) => if i > 0 && (k - i) % 3 == 0 then [',', c] else [c]).flatten
  sign ++ String.ofList out ++ String.ofList tail

/-- Padding (compiler/ival.tn `pad`). -/
def padI (sp : Spec) (body0 : String) (numeric : Bool) : String :=
  let body := if sp.comma then groupDigits sp body0 else body0
  let n := body.length
  if n ≥ sp.width then body
  else
    let k := sp.width - n
    if sp.zero then
      if body.startsWith "-" then "-" ++ String.ofList (List.replicate k '0') ++ String.ofList (body.toList.drop 1)
      else String.ofList (List.replicate k '0') ++ body
    else
      let pad (m : Nat) := String.ofList (List.replicate m sp.fill)
      let al := sp.align.getD (if numeric then '>' else '<')
      let left := if al == '<' then 0 else if al == '^' then k / 2 else k
      pad left ++ body ++ pad (k - left)

def fmtSpec (adts : Adts) (v : Val) (spec : String) : PrimRes :=
  match parseSpec spec with
  | none => .stuck "bad format spec"
  | some sp =>
    match v with
    | .int i =>
      if sp.prec.isSome then .stuck "precision on Int" else
      if sp.comma && sp.radix.isSome then .stuck "comma with radix" else
      let a := i.natAbs
      let digits := match sp.radix with
        | some 'x' => hexDigits a
        | some 'X' => (hexDigits a).toUpper
        | some 'b' => String.ofList (Nat.toDigits 2 a)
        | some 'o' => String.ofList (Nat.toDigits 8 a)
        | _ => toString a
      ret (.str (padI sp ((if i < 0 then "-" else "") ++ digits) true))
    | .str s =>
      if sp.zero || sp.comma || sp.radix.isSome || sp.prec.isSome then .stuck "spec on Str" else ret (.str (padI sp s false))
    | .bool _ =>
      if sp.zero || sp.comma || sp.radix.isSome || sp.prec.isSome then .stuck "spec on Bool"
      else ret (.str (padI sp (showV adts true v) false))
    | _ => match asFlt v with
      | some b =>
        if sp.radix.isSome then .stuck "radix on Float" else
        let t := match sp.prec with
          | some d => Flt.fixed b (min d 100)
          | none => Flt.text b
        ret (.str (padI sp t true))
      | none => .unsup "format spec on this value"

/-! ## Show impls (reference §17): formatting that calls Tenon code

A builtin cannot call a Tenon function, so a value that contains a value of a
type with a Show impl is formatted by a core function (`%show`, Translate.lean)
that asks `%showparts` for the pieces: the impl to call on the value itself,
or the text around its parts. Which impl applies to a value is decided on the
value (the core has no static types): an impl for one instantiation
(`Box[Int]`) or with bounds (`impl[T: Hash]`) applies when the values inside
show it; when they do not tell (an empty list, `None`, a `dyn` value hiding
its type) the run is outside the subset. -/

structure ShowImpl where
  key : String              -- the type's key
  fn : String               -- the FnDecl of its `to_str`
  bounds : List (List String) -- the bounds of each of the impl's type parameters
  args : List Ty            -- the target's type arguments; parameter i is `.adt "%tp<i>" []`

inductive Tri where
  | yes | no | unk
  deriving BEq, Inhabited

def Tri.and : Tri → Tri → Tri
  | .no, _ => .no
  | _, .no => .no
  | .unk, _ => .unk
  | _, .unk => .unk
  | _, _ => .yes

def Tri.all (xs : List Tri) : Tri := xs.foldl Tri.and .yes

def markOf : Ty → Option Nat
  | .adt n [] => if n.startsWith "%tp" then (String.ofList (n.toList.drop 3)).toNat? else none
  | _ => none

partial def substTy (as : List Ty) : Ty → Ty
  | .var i => as.getD i (.var i)
  | .tup ts => .tup (ts.map (substTy as))
  | .list t => .list (substTy as t)
  | .map k v => .map (substTy as k) (substTy as v)
  | .adt n ts => .adt n (ts.map (substTy as))
  | .fn ps r => .fn (ps.map (substTy as)) (substTy as r)
  | t => t

partial def varsOf : Ty → List Nat
  | .var i => [i]
  | .tup ts | .adt _ ts => ts.flatMap varsOf
  | .list t => varsOf t
  | .map k v => varsOf k ++ varsOf v
  | .fn ps r => ps.flatMap varsOf ++ varsOf r
  | _ => []

/-- Any instantiation of the impl's parameters fits (only parameters at the leaves). -/
partial def openTy (t : Ty) : Bool :=
  (markOf t).isSome || match t with
    | .tup ts => ts.all openTy
    | .list e => openTy e
    | .map k v => openTy k && openTy v
    | _ => false

def entries (kvs : List Val) : List (Val × Val) :=
  kvs.filterMap fun e => match e with | .seq .tup [k, v] => some (k, v) | _ => none

/-- Does the value have the type `t` (its parameters bound to the values found)? -/
partial def matchV (adts : Adts) (v : Val) (t : Ty) : Tri × List (Nat × Val) :=
  match markOf t with
  | some i => (.yes, [(i, v)])
  | none =>
    let all (rs : List (Tri × List (Nat × Val))) := (Tri.all (rs.map (·.1)), rs.flatMap (·.2))
    let leaf (b : Bool) : Tri × List (Nat × Val) := (if b then .yes else .no, [])
    match t, v with
    | .int, _ => leaf (match v with | .int _ => true | _ => false)
    | .bool, _ => leaf (match v with | .bool _ => true | _ => false)
    | .str, _ => leaf (match v with | .str _ => true | _ => false)
    | .unit, _ => leaf (match v with | .unit => true | _ => false)
    | .list e, .seq .list vs => if vs.isEmpty then (if openTy e then .yes else .unk, []) else all (vs.map (matchV adts · e))
    | .list _, _ => leaf false
    | .map kt vt, .seq .map kvs =>
      if kvs.isEmpty then (if openTy kt && openTy vt then .yes else .unk, [])
      else all ((entries kvs).flatMap fun (k, x) => [matchV adts k kt, matchV adts x vt])
    | .map .., _ => leaf false
    | .tup ts, .seq .tup vs => if ts.length == vs.length then all ((vs.zip ts).map fun (x, u) => matchV adts x u) else leaf false
    | .tup _, _ => leaf false
    | .fn .., .clo .. => (if openTy t then .yes else .unk, [])
    | .fn .., .fn _ => (if openTy t then .yes else .unk, [])
    | .fn .., _ => leaf false
    | .cap k, .cap c => leaf (c.kind == k)
    | .cap _, _ => leaf false
    | .adt "Float" [], _ => leaf (asFlt v).isSome
    | .adt n as, .adt s tag _ vs =>
      if n.startsWith "dyn " then (.unk, []) else
      if n != s then leaf false else
      match adts n with
      | some d => match d.variants[tag]? with
        | some (_, fts) =>
          let seen := fts.flatMap varsOf
          let hidden := ((List.range as.length).filter fun i => !seen.contains i).all fun i => openTy (as.getD i .unit)
          let r := all ((vs.zip fts).filterMap fun (x, ft) =>
            if (varsOf ft).isEmpty then none else some (matchV adts x (substTy as ft)))
          (if hidden then r.1 else Tri.and r.1 .unk, r.2)
        | none => (.unk, [])
      | none => (.unk, [])
    | .adt n _, _ => if n.startsWith "dyn " then (.unk, []) else leaf false
    | _, _ => (.unk, [])

mutual
/-- The impl of `to_str` that applies to the value, if any. -/
partial def implFor (adts : Adts) (shows : List ShowImpl) (hasDyn : Bool) (v : Val) : Tri × Option String :=
  match v with
  | .adt k _ _ _ =>
    let rs := (shows.filter (·.key == k)).map fun im =>
      let marks := im.args.filterMap markOf
      let distinct := marks.eraseDups.length == marks.length
      let simple := marks.length == im.args.length && distinct && im.bounds.all (·.isEmpty)
      if simple then (Tri.yes, im.fn)
      -- a `dyn` value hides its static type: a concrete argument cannot be told
      else if !distinct || (hasDyn && marks.length != im.args.length) then (.unk, im.fn)
      else
        let (t, bs) := matchV adts v (.adt k im.args)
        let bt := im.bounds.zipIdx.map fun (b, i) =>
          if b.isEmpty then Tri.yes else
          let xs := bs.filterMap fun (j, x) => if j == i then some x else none
          if xs.isEmpty then .unk else
          let r := Tri.all (xs.flatMap fun x => b.map fun bn => boundV adts shows hasDyn bn x)
          -- with `dyn` values, a part may be a `dyn`: Show holds for it, the others do not
          if !hasDyn then r
          else if b.all (· == "Show") then (if r == .no then .unk else r)
          else (if r == .yes then .unk else r)
        (Tri.and t (Tri.all bt), im.fn)
    match rs.find? (·.1 == .yes) with
    | some (_, f) => (.yes, some f)
    | none => if rs.any (·.1 == .unk) then (.unk, none) else (.no, none)
  | _ => (.no, none)

/-- A derived trait (reference §17, "Derived traits") on a value whose type the value shows. -/
partial def boundV (adts : Adts) (shows : List ShowImpl) (hasDyn : Bool) (b : String) (x : Val) : Tri :=
  if b != "Show" && b != "Eq" && b != "Ord" && b != "Hash" then .unk else
  let sub := boundV adts shows hasDyn b
  let walk : Tri := match x with
    | .clo .. | .fn _ | .cap _ => .no
    | .seq .list vs => if vs.isEmpty then .unk else Tri.all (vs.map sub)
    | .seq .tup vs => Tri.all (vs.map sub)
    | .seq .map kvs => if b == "Ord" then .no else if kvs.isEmpty then .unk
      else Tri.all ((entries kvs).flatMap fun (k, w) => [sub k, sub w])
    | .adt "Float" 0 none [_] => if b == "Hash" then .no else .yes
    | .adt k tag _ vs => match adts k with
      | some d => match d.variants[tag]? with
        | some (_, fts) =>
          let seen := fts.flatMap varsOf
          let shown := (List.range d.tparams).all fun i => seen.contains i
          Tri.and (if shown then .yes else .unk) (Tri.all (vs.map sub))
        | none => .unk
      | none => .unk
    | _ => .yes
  if b == "Show" then
    match implFor adts shows hasDyn x with
    | (.yes, _) => .yes
    | (.unk, _) => .unk
    | _ => walk
  else walk
end

/-- Does the value contain a value of a type with a Show impl? -/
partial def needsWalk (shows : List ShowImpl) : Val → Bool
  | .adt k _ _ vs => shows.any (·.key == k) || vs.any (needsWalk shows)
  | .seq _ vs => vs.any (needsWalk shows)
  | _ => false

def okV (v : Val) : Val := .adt "Result" 0 none [v]
def errV (v : Val) : Val := .adt "Result" 1 none [v]

/-- `%showparts v top`: `Ok(f)`: call the impl `f` on `v`; `Err((seps, kids))`:
the text is `seps[0] kids[0] seps[1] ... seps[n]`, the kids formatted nested. -/
def showParts (adts : Adts) (shows : List ShowImpl) (hasDyn : Bool) (v : Val) (top : Bool) : PrimRes :=
  let plain := ret (errV (.seq .tup [strs [showV adts top v], .seq .list []]))
  let parts (seps : List String) (kids : List Val) : PrimRes :=
    if (toksL kids).isEmpty then ret (errV (.seq .tup [strs seps, .seq .list kids]))
    else .unsup "formatting through a Show impl a value with obligations"
  let around (o c : String) (vs : List Val) : List String :=
    o :: ((List.range vs.length).map fun i => if i + 1 == vs.length then c else ", ")
  if !needsWalk shows v then plain else
  match implFor adts shows hasDyn v with
  | (.yes, some f) => ret (okV (.fn f))
  | (.unk, _) => .unsup "a Show impl whose use depends on a type the values do not show"
  | _ => match v with
    | .seq .list vs => parts (around "[" "]" vs) vs
    | .seq .tup vs => parts (around "(" ")" vs) vs
    | .seq .map kvs =>
      let es := entries kvs
      let seps := "[" :: ((List.range es.length).flatMap fun i => [": ", if i + 1 == es.length then "]" else ", "])
      parts seps (es.flatMap fun (k, x) => [k, x])
    | .adt k tag _ vs => match adts k with
      | some d =>
        if vs.isEmpty then plain
        else if d.isStruct then
          let fs := d.fields
          let seps := (d.name ++ " { " ++ fs.headD "" ++ ": ") ::
            ((List.range vs.length).map fun i => if i + 1 == vs.length then " }" else ", " ++ fs.getD (i + 1) "" ++ ": ")
          parts seps vs
        else parts (around (((d.variants[tag]?).map (·.1)).getD "?" ++ "(") ")" vs) vs
      | none => plain
    | _ => plain

/-! ## Sorting (compiler/ibuiltin.tn `sorted_order`, ival.tn `cmp`) -/

def c3 [LT α] [DecidableRel (α := α) (· < ·)] (x y : α) : Int := if x < y then -1 else if y < x then 1 else 0

/-- The interpreter's derived ordering: -1, 0, 1; `none` when maps are compared. -/
partial def icmp (adts : Adts) (a b : Val) : Option Int :=
  match asFlt a, asFlt b with
  | some x, some y => let x := Flt.toF x; let y := Flt.toF y; some (if x < y then -1 else if x > y then 1 else 0)
  | some _, _ => some 0
  | _, some _ => some 0
  | none, none => match a, b with
    | .int x, .int y => some (c3 x y)
    | .bool x, .bool y => some (c3 x.toNat y.toNat)
    | .str x, .str y => some (c3 x y)
    | .seq .list xs, .seq .list ys => lex xs ys true
    | .seq .tup xs, .seq .tup ys => lex xs ys true
    | .seq .map _, .seq .map _ => none
    | .adt k t _ xs, .adt _ t' _ ys =>
      if ((adts k).map (·.isStruct)).getD false then lex xs ys true
      else if t != t' then some (if t < t' then -1 else 1) else lex xs ys false
    | _, _ => some 0
where
  lex : List Val → List Val → Bool → Option Int
    | x :: xs, y :: ys, len => match icmp adts x y with
      | some 0 => lex xs ys len
      | r => r
    | [], [], _ => some 0
    | [], _ :: _, len => some (if len then -1 else 0)
    | _ :: _, [], len => some (if len then 1 else 0)

/-- The stable bottom-up merge sort of the interpreter: the order of the
indices, and whether maps were compared (a trap). -/
def sortedOrder (adts : Adts) (keys : Array Val) (desc : Bool) : Array Nat × Bool := Id.run do
  let n := keys.size
  let mut idx : Array Nat := Array.range n
  let mut width := 1
  let mut bad := false
  while width < n do
    let mut out : Array Nat := #[]
    let mut lo := 0
    while lo < n do
      let mid := min (lo + width) n
      let hi := min (lo + 2 * width) n
      let mut i := lo
      let mut j := mid
      while i < mid || j < hi do
        let mut takeLeft : Bool := decide (j ≥ hi)
        if !takeLeft && i < mid then
          let c := icmp adts keys[idx[j]!]! keys[idx[i]!]!
          if c.isNone then bad := true
          let c := c.getD 0
          takeLeft := if desc then decide (c ≤ 0) else decide (c ≥ 0)
        if takeLeft then
          out := out.push idx[i]!
          i := i + 1
        else
          out := out.push idx[j]!
          j := j + 1
      lo := hi
    idx := out
    width := width * 2
  return (idx, bad)

def sortBy (adts : Adts) (vs keys : List Val) (desc : Bool) : PrimRes :=
  let (order, bad) := sortedOrder adts keys.toArray desc
  if bad then .trap "maps are not ordered"
  else ret (.seq .list (order.toList.map fun i => vs.getD i .unit))

/-! ## The table -/

def listOf : Val → Option (List Val)
  | .seq .list vs => some vs
  | _ => none

def pureTable (adts : Adts) (name : String) (shows : List ShowImpl := []) (hasDyn : Bool := false) :
    Option (List Val → PrimRes) :=
  -- `"{e:SPEC}"`: the spec is part of the name (its signature depends on it, Front/Checker.lean)
  if name.startsWith "%fmt:" then some fun
    | [v] => fmtSpec adts v (name.drop 5).toString
    | _ => .stuck "fmt"
  else
  match name with
  | "%showq" => some fun
    | [v, .bool top] => ret (if needsWalk shows v then errV .unit else okV (.str (showV adts top v)))
    | _ => .stuck "show"
  | "%showparts" => some fun
    | [v, .bool top] => showParts adts shows hasDyn v top
    | _ => .stuck "show"
  | "%sortby" => some fun
    | [.seq .list vs, .seq .list ks, .bool desc] =>
      if (toksL vs).isEmpty then sortBy adts vs ks desc else .unsup "sort_by of values with obligations"
    | _ => .stuck "sort_by"
  | "%add" => some fun
    | [.int a, .int b] => int64 (a + b)
    | [.str a, .str b] => ret (.str (a ++ b))
    | [.seq .list a, .seq .list b] => ret (.seq .list (a ++ b))
    | vs => farith (· + ·) "+" vs
  | "%sub" => some fun | [.int a, .int b] => int64 (a - b) | vs => farith (· - ·) "-" vs
  | "%mul" => some fun | [.int a, .int b] => int64 (a * b) | vs => farith (· * ·) "*" vs
  | "%div" => some fun
    | [.int a, .int b] => if b = 0 then .trap "division by zero" else int64 (a.tdiv b)
    | vs => farith (· / ·) "/" vs
  | "%rem" => some fun
    | [.int a, .int b] => if b = 0 then .trap "division by zero"
        else if a = MIN64 ∧ b = -1 then .trap "integer overflow" else int64 (a.tmod b)
    | [a, b] => match asFlt a, asFlt b with
      | some x, some y => ret (flt (Flt.fmod x y))
      | _, _ => .stuck "%"
    | _ => .stuck "%"
  | "%neg" => some fun
    | [.int a] => int64 (-a)
    | [a] => match asFlt a with
      | some x => ret (flt (UInt64.ofNat ((x.toNat + 2 ^ 63) % 2 ^ 64)))
      | none => .stuck "-"
    | _ => .stuck "-"
  | "%not" => some fun | [.bool b] => ret (.bool !b) | _ => .stuck "not"
  | "%eq" => some fun | [a, b] => ret (.bool (veq a b)) | _ => .stuck "=="
  | "%ne" => some fun | [a, b] => ret (.bool !(veq a b)) | _ => .stuck "!="
  | "%lt" => some (ord (· < ·) fun o => o == .lt)
  | "%le" => some (ord (· ≤ ·) fun o => o != .gt)
  | "%gt" => some (ord (· > ·) fun o => o == .gt)
  | "%ge" => some (ord (· ≥ ·) fun o => o != .lt)
  | "%float" => some fun
    | [.str t] => match Flt.parse t with
      | some b => ret (flt b)
      | none => .trap "invalid Float literal"
    | _ => .stuck "float literal"
  | "%show" => some fun | [v] => ret (.str (showV adts true v)) | _ => .stuck "show"
  | "encode" => some fun | [v] => ret (.str (showV adts false v)) | _ => .stuck "encode"
  | "*.to_str" => some fun | [v] => ret (.str (showV adts true v)) | _ => .stuck "to_str"
  | "%concat" => some fun vs =>
    if vs.all (fun v => match v with | .str _ => true | _ => false)
    then ret (.str (String.join (vs.map fun v => match v with | .str s => s | _ => "")))
    else .stuck "concat"
  | "%fmt" => some fun | [v, .str spec] => fmtSpec adts v spec | _ => .stuck "fmt"
  | "%map" => some fun vs => ret (.seq .map (vs.foldl (fun m e => match e with
      | .seq .tup [k, v] => mapSet k v m
      | _ => m) []))
  | "%index" => some fun
    | [c, k] => match getStep { fns := fun _ => none, adts, prim := fun _ => none } c (.idx k) with
      | .ok v => ret v
      | .error (.trap m) => .trap m
      | .error (.stuck m) => .stuck m
    | _ => .stuck "index"
  | "%iter" => some fun
    | [.seq .list vs] => ret (.seq .list vs)
    | [.seq .map kvs] => ret (.seq .list kvs)
    | [.adt "Set" 0 none [.seq .map kvs]] => ret (.seq .list (kvs.filterMap fun e => match e with
        | .seq .tup [k, _] => some k
        | _ => none))
    | _ => .unsup "for over this value"
  | "panic" => some fun | [.str m] => .trap m | _ => .stuck "panic"
  | "assert" => some fun | [.bool b] => if b then ret .unit else .trap "assertion failed" | _ => .stuck "assert"
  -- capabilities
  | "Console.println" => some (out "println" "\n")
  | "Console.print" => some (out "print" "")
  | "Console.eprintln" => some (out "eprintln" "\n")
  | "Console.flush" => some fun
    | [.cap c] => if c.kind = .console then ret .unit else .stuck "flush"
    | _ => .stuck "flush"
  | "Console.write_bytes" => some fun
    | [.cap c, .seq .list xs] =>
      if c.kind ≠ .console then .stuck "write_bytes" else
      match (xs.zipIdx.find? fun (x, _) => match x with | .int i => i < 0 ∨ i > 255 | _ => true) with
      | some (.int v, i) => .trap s!"byte {v} at index {i} is not in 0..255"
      | some _ => .stuck "write_bytes"
      | none => match ofBytes (xs.map fun x => match x with | .int i => i.toNat.toUInt8 | _ => 0) with
        | some t => ok3 .unit none [{ cap := c, op := "print", arg := t }]
        | none => .unsup "invalid UTF-8 written to standard output"
    | _ => .stuck "write_bytes"
  | "Str.from_utf8" => some fun
    | [.seq .list xs] =>
      if !xs.all (fun x => match x with | .int i => 0 ≤ i ∧ i ≤ 255 | _ => false) then ret none'
      else
        let (bs, ok) := utf8Lossy (xs.map fun x => match x with | .int i => i.toNat.toUInt8 | _ => 0).toArray
        ret (if ok then some' (.str (str! bs)) else none')
    | _ => .stuck "from_utf8"
  | "Str.from_utf8_lossy" => some fun
    | [.seq .list xs] =>
      match (xs.zipIdx.find? fun (x, _) => match x with | .int i => i < 0 ∨ i > 255 | _ => true) with
      | some (.int v, i) => .trap s!"byte {v} at index {i} is not in 0..255"
      | some _ => .stuck "from_utf8_lossy"
      | none => ret (.str (str! (utf8Lossy (xs.map fun x => match x with | .int i => i.toNat.toUInt8 | _ => 0).toArray).1))
    | _ => .stuck "from_utf8_lossy"
  | "Fs.within" => some fun
    | [.cap c, .str d] => if c.kind = .fs then ret (.cap (c.within ((d.splitOn "/").filter (· ≠ "")))) else .stuck "within"
    | _ => .stuck "within"
  | "Fs.read_only" => some fun
    | [.cap c] => if c.kind = .fs then ret (.cap c.readOnly) else .stuck "read_only"
    | _ => .stuck "read_only"
  -- Int
  | "Int.checked_add" => some (checked fun a b => some (a + b))
  | "Int.checked_sub" => some (checked fun a b => some (a - b))
  | "Int.checked_mul" => some (checked fun a b => some (a * b))
  | "Int.checked_div" => some (checked fun a b => if b = 0 then none else some (a.tdiv b))
  | "Int.char" => some fun
    | [.int i] => if 0 ≤ i ∧ i < 0x110000 ∧ ¬(0xD800 ≤ i ∧ i < 0xE000) then ret (.str (Char.ofNat i.toNat).toString)
        else .trap "Int.char outside the code points"
    | _ => .stuck "char"
  -- Float
  | "Int.to_float" => some fun | [.int i] => ret (flt (Flt.ofInt i)) | _ => .stuck "to_float"
  | "Float.to_int" => some fun
    | [v] => match asFlt v with
      | some x => match Flt.toInt x with
        | some i => ret (.int i)
        | none => .trap "float to int conversion out of range"
      | none => .stuck "to_int"
    | _ => .stuck "to_int"
  | "Float.sqrt" => some (fl1 Float.sqrt)
  | "Float.floor" => some (fl1 Float.floor)
  | "Float.ceil" => some (fl1 Float.ceil)
  | "Float.round" => some (fl1 Float.round)
  | "Float.to_fixed" => some fun
    | [v, .int d] => match asFlt v with
      | some x => ret (.str (Flt.fixed x (if d < 0 then 0 else min d.toNat 100)))
      | none => .stuck "to_fixed"
    | _ => .stuck "to_fixed"
  | "Str.to_float" => some (strFn fun s => (Flt.parse s).elim none' (fun b => some' (flt b)))
  -- Str
  | "Str.len" => some fun | [.str s] => ret (.int (blen s)) | _ => .stuck "len"
  | "Str.byte" => some fun
    | [.str s, .int i] => match (bytesOf s)[i.toNat]? with
      | some b => if 0 ≤ i then ret (.int b.toNat) else .trap "index out of bounds"
      | none => .trap "index out of bounds"
    | _ => .stuck "byte"
  | "Str.slice" => some fun
    | [.str s, .int a, .int b] =>
      let bs := bytesOf s
      if a < 0 ∨ b < a ∨ b > bs.length then .trap "slice out of bounds"
      else if !(boundary bs a.toNat && boundary bs b.toNat) then .trap "slice not on a character boundary"
      else ret (.str (str! (sliceB bs a.toNat b.toNat)))
    | _ => .stuck "slice"
  | "Str.find" => some fun
    | [.str s, .str t] => ret ((findB (bytesOf s) (bytesOf t) 0).elim none' (fun i => some' (.int i)))
    | _ => .stuck "find"
  | "Str.find_from" => some fun
    | [.str s, .str t, .int f] =>
      if f < 0 ∨ f > blen s then .trap "index out of bounds"
      else ret ((findB (bytesOf s) (bytesOf t) f.toNat).elim none' (fun i => some' (.int i)))
    | _ => .stuck "find_from"
  | "Str.split" => some fun
    | [.str s, .str sep] => if sep.isEmpty then .trap "split with an empty separator"
        else ret (strs ((splitB (bytesOf s) (bytesOf sep) 0 []).map str!))
    | _ => .stuck "split"
  | "Str.trim" => some (strFn fun s => .str (str! (trimB (bytesOf s) true true)))
  | "Str.trim_start" => some (strFn fun s => .str (str! (trimB (bytesOf s) true false)))
  | "Str.trim_end" => some (strFn fun s => .str (str! (trimB (bytesOf s) false true)))
  | "Str.starts_with" => some fun | [.str s, .str p] => ret (.bool (s.startsWith p)) | _ => .stuck "starts_with"
  | "Str.ends_with" => some fun | [.str s, .str p] => ret (.bool (s.endsWith p)) | _ => .stuck "ends_with"
  | "Str.to_int" => some (strFn fun s => (toIntS s).elim none' (fun i => some' (.int i)))
  | "Str.upper" => some (strFn fun s => .str (upperA s))
  | "Str.lower" => some (strFn fun s => .str (lowerA s))
  | "Str.replace" => some fun
    | [.str s, .str a, .str b] => if a.isEmpty then .trap "replace with an empty pattern" else ret (.str (s.replace a b))
    | _ => .stuck "replace"
  | "Str.chars" => some (strFn fun s => strs (s.toList.map Char.toString))
  | "Str.char_count" => some (strFn fun s => .int s.length)
  | "Str.bytes" => some (strFn fun s => .seq .list ((bytesOf s).map fun b => .int b.toNat))
  | "Str.lines" => some (strFn fun s => strs (linesOf s))
  | "Str.words" => some (strFn fun s => strs (wordsB (bytesOf s)))
  -- List
  | "List.len" => some fun | [.seq .list vs] => ret (.int vs.length) | _ => .stuck "len"
  | "List.push" => some fun | [.seq .list vs, x] => ok3 .unit (some (.seq .list (vs ++ [x]))) [] | _ => .stuck "push"
  | "List.pop" => some fun
    | [.seq .list vs] => match vs.getLast? with
      | some x => ok3 (some' x) (some (.seq .list vs.dropLast)) []
      | none => ok3 none' (some (.seq .list vs)) []
    | _ => .stuck "pop"
  | "List.insert" => some fun
    | [.seq .list vs, .int i, x] =>
      if 0 ≤ i ∧ i ≤ vs.length then ok3 .unit (some (.seq .list (vs.take i.toNat ++ x :: vs.drop i.toNat))) []
      else .trap "index out of bounds"
    | _ => .stuck "insert"
  | "List.remove" => some fun
    | [.seq .list vs, .int i] => match vs[i.toNat]? with
      | some x => if 0 ≤ i then ok3 x (some (.seq .list (vs.eraseIdx i.toNat))) [] else .trap "index out of bounds"
      | none => .trap "index out of bounds"
    | _ => .stuck "remove"
  | "List.clear" => some fun | [.seq .list _] => ok3 .unit (some (.seq .list [])) [] | _ => .stuck "clear"
  | "List.slice" => some fun
    | [.seq .list vs, .int a, .int b] =>
      if a < 0 ∨ b < a ∨ b > vs.length then .trap "slice out of bounds"
      else ret (.seq .list ((vs.drop a.toNat).take (b.toNat - a.toNat)))
    | _ => .stuck "slice"
  | "List.sort" => some fun
    | [.seq .list vs] => match sortBy adts vs vs false with
      | .ok v _ _ _ => ok3 .unit (some v) []
      | r => r
    | _ => .stuck "sort"
  | "List.reverse" => some fun | [.seq .list vs] => ok3 .unit (some (.seq .list vs.reverse)) [] | _ => .stuck "reverse"
  | "List.join" => some fun
    | [.seq .list vs, .str sep] =>
      if vs.all (fun v => match v with | .str _ => true | _ => false)
      then ret (.str (sep.intercalate (vs.map fun v => match v with | .str s => s | _ => "")))
      else .stuck "join"
    | _ => .stuck "join"
  -- Map
  | "Map.len" => some fun | [.seq .map kvs] => ret (.int kvs.length) | _ => .stuck "len"
  | "Map.get" => some fun | [.seq .map kvs, k] => ret ((mapGet k kvs).elim none' some') | _ => .stuck "get"
  | "Map.insert" => some fun | [.seq .map kvs, k, v] => ok3 .unit (some (.seq .map (mapSet k v kvs))) [] | _ => .stuck "insert"
  | "Map.remove" => some fun
    | [.seq .map kvs, k] => match mapGet k kvs with
      | some v => ok3 (some' v) (some (.seq .map (kvs.filter fun e => match e with
          | .seq .tup [k', _] => !(Val.beq k k')
          | _ => true))) []
      | none => ok3 none' (some (.seq .map kvs)) []
    | _ => .stuck "remove"
  | "Map.keys" => some fun
    | [.seq .map kvs] => ret (.seq .list (kvs.filterMap fun e => match e with | .seq .tup [k, _] => some k | _ => none))
    | _ => .stuck "keys"
  | "Map.values" => some fun
    | [.seq .map kvs] => ret (.seq .list (kvs.filterMap fun e => match e with | .seq .tup [_, v] => some v | _ => none))
    | _ => .stuck "values"
  | _ => none
where
  farith (f : Float → Float → Float) (op : String) : List Val → PrimRes
    | [a, b] => match asFlt a, asFlt b with
      | some x, some y => ret (fltF (f (Flt.toF x) (Flt.toF y)))
      | _, _ => .stuck op
    | _ => .stuck op
  ord (fl : Float → Float → Bool) (f : Ordering → Bool) : List Val → PrimRes
    | [a, b] => match asFlt a, asFlt b with
      | some x, some y => ret (.bool (fl (Flt.toF x) (Flt.toF y)))
      | _, _ => match cmp a b with
        | some o => ret (.bool (f o))
        | none => .unsup "comparison of values without an order"
    | _ => .stuck "comparison"
  out (op nl : String) : List Val → PrimRes
    | [.cap c, .str s] => if c.kind = .console then ok3 .unit none [{ cap := c, op, arg := s ++ nl }] else .stuck op
    | _ => .stuck op
  checked (f : Int → Int → Option Int) : List Val → PrimRes
    | [.int a, .int b] => match f a b with
      | some r => ret (if MIN64 ≤ r ∧ r ≤ MAX64 then some' (.int r) else none')
      | none => ret none'
    | _ => .stuck "checked"
  fl1 (f : Float → Float) : List Val → PrimRes
    | [v] => match asFlt v with
      | some x => ret (fltF (f (Flt.toF x)))
      | none => .stuck "Float method"
    | _ => .stuck "Float method"
  strFn (f : String → Val) : List Val → PrimRes
    | [.str s] => ret (f s)
    | _ => .stuck "Str method"

/-! ## Standard input (the world's state is the offset of the next unread byte) -/

def readLine (inp : List UInt8) (w : Nat) : PrimRes :=
  if w ≥ inp.length then .ok none' none [] w
  else
    let rest := inp.drop w
    let line := rest.takeWhile (· != 10)
    let next := w + line.length + (if line.length < rest.length then 1 else 0)
    let line := if line.getLast? == some 13 then line.dropLast else line
    match ofBytes line with
    | some s => .ok (some' (.str s)) none [] next
    | none => .unsup "invalid UTF-8 on standard input"

def stdinPrim (inp : List UInt8) : String → Option (List Val → Nat → PrimRes)
  | "Console.read_line" => some fun vs w => match vs with
    | [.cap c] => if c.kind = .console then readLine inp w else .stuck "read_line"
    | _ => .stuck "read_line"
  | "Console.read_all" => some fun vs w => match vs with
    | [.cap c] => if c.kind = .console then
        match ofBytes (inp.drop w) with
        | some s => .ok (.str s) none [] inp.length
        | none => .unsup "invalid UTF-8 on standard input"
      else .stuck "read_all"
    | _ => .stuck "read_all"
  | "Console.read_all_bytes" => some fun vs w => match vs with
    | [.cap c] => if c.kind = .console then
        .ok (.seq .list ((inp.drop w).map fun b => .int b.toNat)) none [] inp.length
      else .stuck "read_all_bytes"
    | _ => .stuck "read_all_bytes"
  | "Console.read_bytes" => some fun vs w => match vs with
    | [.cap c, .int n] => if c.kind = .console then
        let k := if n ≤ 0 then 0 else n.toNat
        let bs := (inp.drop w).take k
        .ok (.seq .list (bs.map fun b => .int b.toNat)) none [] (w + bs.length)
      else .stuck "read_bytes"
    | _ => .stuck "read_bytes"
  | _ => none

/-- The builtins of one run: `externs` are the prelude's `extern fn` names
(those the model does not cover are `unsup`), `input` is standard input. -/
def table (adts : Adts) (externs : List String) (input : List UInt8) (shows : List ShowImpl)
    (hasDyn : Bool) (name : String) : Option (List Val → Nat → PrimRes) :=
  match stdinPrim input name with
  | some f => some f
  | none => match pureTable adts name shows hasDyn with
    | some f => some fun vs w => match f vs with
      | .ok v s e _ => .ok v s e w
      | r => r
    | none => if externs.contains name then some fun _ _ => .unsup s!"builtin {name}" else none

end Tenon.Prims

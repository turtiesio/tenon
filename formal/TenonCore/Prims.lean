/-
The concrete builtins of the executable semantics: the `extern fn`s of
lib/prelude.tn the core models, the operators and formatting (reference §8).
They are ordinary Lean functions on values; the evaluator treats them as
abstract operations behind a monitor (Eval.lean `primApply`), so no theorem
depends on their code. Their behaviour is what the differential test
(ops/gates/formal_diff.py) compares with `tenon run`.
-/
import TenonCore.Eval

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

def parseSpec (s : String) : Option Spec := Id.run do
  let mut cs := s.toList
  let mut sp : Spec := {}
  let isAlign (c : Char) := c == '<' || c == '>' || c == '^'
  match cs with
  | f :: a :: r =>
    if isAlign a then sp := { sp with fill := f, align := some a }; cs := r
    else if isAlign f then sp := { sp with align := some f }; cs := a :: r
  | [a] => if isAlign a then return none
  | [] => return none
  if cs.head? == some '0' then sp := { sp with zero := true }; cs := cs.tail
  let ds := cs.takeWhile Char.isDigit
  if ds.length > 3 then return none
  if !ds.isEmpty then sp := { sp with width := (String.ofList ds).toNat! }
  cs := cs.drop ds.length
  if cs.head? == some ',' then sp := { sp with comma := true }; cs := cs.tail
  if cs.head? == some '.' then
    let ps := cs.tail.takeWhile Char.isDigit
    if ps.isEmpty then return none
    sp := { sp with prec := some (String.ofList ps).toNat! }
    cs := cs.tail.drop ps.length
  match cs with
  | [] => pure ()
  | [r] => if r == 'x' || r == 'X' || r == 'b' || r == 'o' then sp := { sp with radix := some r } else return none
  | _ => return none
  if sp.align.isSome && sp.zero then return none
  if sp.align.isSome && ds.isEmpty then return none
  return some sp

def group3 (ds : String) : String :=
  let cs := ds.toList.reverse
  let rec go : List Char → Nat → List Char
    | [], _ => []
    | c :: r, k => if k > 0 && k % 3 == 0 then c :: ',' :: go r (k + 1) else c :: go r (k + 1)
  String.ofList (go cs 0).reverse

def padTo (sp : Spec) (defAlign : Char) (t : String) : String :=
  let n := t.length
  if n ≥ sp.width then t
  else
    let k := sp.width - n
    let pad (m : Nat) := String.ofList (List.replicate m sp.fill)
    match sp.align.getD defAlign with
    | '<' => t ++ pad k
    | '^' => pad (k / 2) ++ t ++ pad (k - k / 2)
    | _ => pad k ++ t

def fmtSpec (adts : Adts) (v : Val) (spec : String) : PrimRes :=
  match parseSpec spec with
  | none => .stuck "bad format spec"
  | some sp =>
    if sp.prec.isSome then .unsup "format precision" else
    match v with
    | .int i =>
      let neg := i < 0
      let a := i.natAbs
      let digits := match sp.radix with
        | some 'x' => hexDigits a
        | some 'X' => (hexDigits a).toUpper
        | some 'b' => String.ofList (Nat.toDigits 2 a)
        | some 'o' => String.ofList (Nat.toDigits 8 a)
        | _ => toString a
      if sp.comma && sp.radix.isSome then .stuck "comma with radix" else
      if sp.zero && sp.comma then .unsup "zero padding with separators" else
      let digits := if sp.comma then group3 digits else digits
      let sign := if neg then "-" else ""
      if sp.zero then
        let n := sign.length + digits.length
        let zs := if n < sp.width then String.ofList (List.replicate (sp.width - n) '0') else ""
        ret (.str (sign ++ zs ++ digits))
      else ret (.str (padTo sp '>' (sign ++ digits)))
    | .str s =>
      if sp.zero || sp.comma || sp.radix.isSome then .stuck "spec on Str" else ret (.str (padTo sp '<' s))
    | .bool _ =>
      if sp.zero || sp.comma || sp.radix.isSome then .stuck "spec on Bool" else ret (.str (padTo sp '<' (showV adts true v)))
    | _ => .unsup "format spec on this value"

/-! ## The table -/

def listOf : Val → Option (List Val)
  | .seq .list vs => some vs
  | _ => none

def pureTable (adts : Adts) (name : String) : Option (List Val → PrimRes) :=
  match name with
  | "%add" => some fun
    | [.int a, .int b] => int64 (a + b)
    | [.str a, .str b] => ret (.str (a ++ b))
    | [.seq .list a, .seq .list b] => ret (.seq .list (a ++ b))
    | _ => .stuck "+"
  | "%sub" => some fun | [.int a, .int b] => int64 (a - b) | _ => .stuck "-"
  | "%mul" => some fun | [.int a, .int b] => int64 (a * b) | _ => .stuck "*"
  | "%div" => some fun
    | [.int a, .int b] => if b = 0 then .trap "division by zero" else int64 (a.tdiv b)
    | _ => .stuck "/"
  | "%rem" => some fun
    | [.int a, .int b] => if b = 0 then .trap "division by zero"
        else if a = MIN64 ∧ b = -1 then .trap "integer overflow" else int64 (a.tmod b)
    | _ => .stuck "%"
  | "%neg" => some fun | [.int a] => int64 (-a) | _ => .stuck "-"
  | "%not" => some fun | [.bool b] => ret (.bool !b) | _ => .stuck "not"
  | "%eq" => some fun | [a, b] => ret (.bool (Val.beq a b)) | _ => .stuck "=="
  | "%ne" => some fun | [a, b] => ret (.bool !(Val.beq a b)) | _ => .stuck "!="
  | "%lt" => some (ord fun o => o == .lt)
  | "%le" => some (ord fun o => o != .gt)
  | "%gt" => some (ord fun o => o == .gt)
  | "%ge" => some (ord fun o => o != .lt)
  | "%show" => some fun | [v] => ret (.str (showV adts true v)) | _ => .stuck "show"
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
        else .unsup "Int.char outside the code points"
    | _ => .stuck "char"
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
    | [.seq .list vs] =>
      if vs.all (fun a => vs.all fun b => (cmp a b).isSome) then
        ok3 .unit (some (.seq .list (vs.mergeSort fun a b => cmp a b != some .gt))) []
      else .unsup "sort of values without an order"
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
  ord (f : Ordering → Bool) : List Val → PrimRes
    | [a, b] => match cmp a b with
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
  | _ => none

/-- The builtins of one run: `externs` are the prelude's `extern fn` names
(those the model does not cover are `unsup`), `input` is standard input. -/
def table (adts : Adts) (externs : List String) (input : List UInt8) (name : String) :
    Option (List Val → Nat → PrimRes) :=
  match stdinPrim input name with
  | some f => some f
  | none => match pureTable adts name with
    | some f => some fun vs w => match f vs with
      | .ok v s e _ => .ok v s e w
      | r => r
    | none => if externs.contains name then some fun _ _ => .unsup s!"builtin {name}" else none

end Tenon.Prims

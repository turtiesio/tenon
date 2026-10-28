/-
`Float` for the builtins (Prims.lean): a 64-bit IEEE value is the value
`.adt "Float" 0 none [.int bits]` (its head is `Float`). Arithmetic and
`sqrt`/`floor`/`ceil`/`round` use Lean's `Float` (the C double operations
the runtime uses); the decimal conversions are exact over `Nat`: reading
(`strtod`: the nearest double, ties to even), the shortest round-trip text
(runtime/tenon.h `tn_Float_show`: the first of `%.0e` ... `%.16e` that reads
back as the same number) and `to_fixed` (`%.*f`). Not part of the proofs.
-/
namespace Tenon.Flt

/-- A double: `fin neg m e` is `(-1)^neg * m * 2^e`. -/
inductive Dec where
  | fin (neg : Bool) (m : Nat) (e : Int)
  | inf (neg : Bool)
  | nan

def decode (b : UInt64) : Dec :=
  let n := b.toNat
  let neg := n / 2 ^ 63 == 1
  let E : Nat := (n / 2 ^ 52) % 2048
  let f := n % 2 ^ 52
  if E == 2047 then (if f == 0 then .inf neg else .nan)
  else if E == 0 then .fin neg f (-1074)
  else .fin neg (f + 2 ^ 52) ((E : Int) - 1075)

def signBit (neg : Bool) : Nat := if neg then 2 ^ 63 else 0

def pow2 (e : Int) : Nat × Nat := if e ≥ 0 then (2 ^ e.toNat, 1) else (1, 2 ^ (-e).toNat)

/-- `a / b` rounded to the nearest integer, ties to even. -/
def divRound (a b : Nat) : Nat :=
  let q := a / b
  let r := a % b
  if 2 * r > b || (2 * r == b && q % 2 == 1) then q + 1 else q

/-- The double nearest to `num / den` (ties to even), with the sign `neg`. -/
def ofRat (neg : Bool) (num den : Nat) : UInt64 :=
  if num == 0 || den == 0 then UInt64.ofNat (signBit neg) else
  let scaled (e : Int) : Nat × Nat :=
    if e ≤ 0 then (num * 2 ^ (-e).toNat, den) else (num, den * 2 ^ e.toNat)
  let e0 : Int := (Nat.log2 num : Int) - (Nat.log2 den : Int) - 52
  let fl (e : Int) : Nat := let (a, b) := scaled e; a / b
  let e1 := if fl e0 < 2 ^ 52 then e0 - 1 else if fl e0 ≥ 2 ^ 53 then e0 + 1 else e0
  let e := if e1 < -1074 then -1074 else e1
  let (a, b) := scaled e
  let q := divRound a b
  let (q, e) := if q == 2 ^ 53 then (2 ^ 52, e + 1) else (q, e)
  if q < 2 ^ 52 then UInt64.ofNat (signBit neg + q)
  else
    let E := e + 1075
    if E ≥ 2047 then UInt64.ofNat (signBit neg + 2047 * 2 ^ 52)
    else UInt64.ofNat (signBit neg + E.toNat * 2 ^ 52 + (q - 2 ^ 52))

def ofInt (i : Int) : UInt64 := ofRat (i < 0) i.natAbs 1

def nanBits : UInt64 := 0x7FF8000000000000
def infBits (neg : Bool) : UInt64 := UInt64.ofNat (signBit neg + 2047 * 2 ^ 52)

def ndigits (n : Nat) : Nat := (Nat.toDigits 10 n).length

/-- `D * 10^k` as a fraction. -/
def decRat (d : Nat) (k : Int) : Nat × Nat := if k ≥ 0 then (d * 10 ^ k.toNat, 1) else (d, 10 ^ (-k).toNat)

/-- `num / den > 0` rounded to `p ≥ 1` significant digits (ties to even): the
digits `D` (`10^(p-1) ≤ D < 10^p`) and the decimal exponent of the first. -/
def roundSig (num den p : Nat) : Nat × Int :=
  -- k = floor(log10(num / den))
  let k0 : Int := (ndigits num : Int) - (ndigits den : Int)
  let ge (k : Int) : Bool := -- num / den ≥ 10^k
    if k ≥ 0 then num ≥ den * 10 ^ k.toNat else num * 10 ^ (-k).toNat ≥ den
  let k := if ge k0 then k0 else k0 - 1
  let s : Int := (p : Int) - 1 - k
  let d := if s ≥ 0 then divRound (num * 10 ^ s.toNat) den else divRound num (den * 10 ^ (-s).toNat)
  if d == 10 ^ p then (10 ^ (p - 1), k + 1) else (d, k)

def stripZeros (ds : List Char) : List Char :=
  let r := (ds.reverse.dropWhile (· == '0')).reverse
  if r.isEmpty then ['0'] else r

/-- The text of `tenon run` (runtime/tenon.h `tn_Float_show`). -/
def text (b : UInt64) : String :=
  match decode b with
  | .nan => "nan"
  | .inf neg => if neg then "-inf" else "inf"
  | .fin neg m e =>
    let sign := if neg then "-" else ""
    let abits := UInt64.ofNat (b.toNat % 2 ^ 63)
    let (ds, k) : List Char × Int :=
      if m == 0 then (['0'], 0) else
      let (num, den) := pow2 e
      let num := m * num
      let rec find (p : Nat) (fuel : Nat) : Nat × Int :=
        let (d, k) := roundSig num den p
        match fuel with
        | 0 => (d, k)
        | f + 1 =>
          let (a, c) := decRat d (k - (p - 1 : Nat))
          if ofRat false a c == abits then (d, k) else find (p + 1) f
      let (d, k) := find 1 16
      (stripZeros (Nat.toDigits 10 d), k)
    let nd := ds.length
    let body :=
      if -5 ≤ k ∧ k < 16 then
        if k ≥ 0 then
          let ip := (List.range (k.toNat + 1)).map fun i => ds.getD i '0'
          let fp := if nd > k.toNat + 1 then ds.drop (k.toNat + 1) else ['0']
          String.ofList ip ++ "." ++ String.ofList fp
        else "0." ++ String.ofList (List.replicate ((-k).toNat - 1) '0') ++ String.ofList ds
      else
        String.ofList [ds.headD '0'] ++ (if nd > 1 then "." ++ String.ofList ds.tail else "") ++ "e" ++ toString k
    sign ++ body

/-- `%.*f` with `d` decimals (`Float.to_fixed`, format precision). -/
def fixed (b : UInt64) (d : Nat) : String :=
  match decode b with
  | .nan => "nan"
  | .inf neg => if neg then "-inf" else "inf"
  | .fin neg m e =>
    let (num, den) := pow2 e
    let v := divRound (m * num * 10 ^ d) den
    let ip := v / 10 ^ d
    let fp := v % 10 ^ d
    let fs := toString fp
    (if neg then "-" else "") ++ toString ip ++
      (if d == 0 then "" else "." ++ String.ofList (List.replicate (d - fs.length) '0') ++ fs)

/-- `Str.to_float` and literals (runtime/tenon.h `tn_str_to_float`, then `strtod`). -/
def parse (s : String) : Option UInt64 :=
  let cs := s.toList
  let (neg, rest) := match cs with
    | '-' :: r => (true, r)
    | '+' :: r => (false, r)
    | r => (false, r)
  let low := String.ofList (rest.map Char.toLower)
  if rest.length ≤ 8 && (low == "inf" || low == "infinity") then some (infBits neg)
  else if rest.length ≤ 8 && low == "nan" then some nanBits
  else
    let ip := rest.takeWhile Char.isDigit
    let r1 := rest.drop ip.length
    let (fp, r2) := match r1 with
      | '.' :: r => (r.takeWhile Char.isDigit, r.drop (r.takeWhile Char.isDigit).length)
      | r => ([], r)
    if ip.isEmpty && fp.isEmpty then none else
    let ex : Option Int := match r2 with
      | [] => some 0
      | c :: r =>
        if c != 'e' && c != 'E' then none else
        let (en, ds) := match r with
          | '-' :: q => (true, q)
          | '+' :: q => (false, q)
          | q => (false, q)
        if ds.isEmpty || !ds.all Char.isDigit then none
        else
          let v : Nat := ds.foldl (fun n c => n * 10 + (c.toNat - '0'.toNat)) 0
          some (if en then -(v : Int) else v)
    match ex with
    | none => none
    | some x =>
      let mant : Nat := (ip ++ fp).foldl (fun n c => n * 10 + (c.toNat - '0'.toNat)) 0
      let k : Int := x - fp.length
      -- exponents far outside the range: 0 or infinity (avoid huge powers)
      if mant == 0 then some (ofRat neg 0 1)
      else if k > 400 then some (infBits neg)
      else if k < -400 - (ndigits mant : Int) then some (ofRat neg 0 1)
      else
        let (a, c) := decRat mant k
        some (ofRat neg a c)

def toF (b : UInt64) : Float := Float.ofBits b
def ofF (f : Float) : UInt64 := f.toBits

def isNan (b : UInt64) : Bool := match decode b with | .nan => true | _ => false

/-- `Float.to_int`: truncation; `none` outside the range of Int. -/
def toInt (b : UInt64) : Option Int :=
  match decode b with
  | .fin neg m e =>
    let (num, den) := pow2 e
    let t : Int := (m * num / den : Nat)
    let t := if neg then -t else t
    -- in range iff -2^63 ≤ x < 2^63
    if neg then (if m * num ≤ 2 ^ 63 * den then some t else none)
    else (if m * num < 2 ^ 63 * den then some t else none)
  | _ => none

/-- `fmod` (C), exact: `x - trunc(x / y) * y`, with the sign of `x`. -/
def fmod (x y : UInt64) : UInt64 :=
  match decode x, decode y with
  | .fin nx mx ex, .fin _ my ey =>
    if my == 0 then nanBits
    else if mx == 0 then x
    else
      let (a1, b1) := pow2 ex
      let (a2, b2) := pow2 ey
      -- |x| = mx*a1/b1, |y| = my*a2/b2; over the common denominator b1*b2
      let X := mx * a1 * b2
      let Y := my * a2 * b1
      let r := X % Y
      ofRat nx r (b1 * b2)
  | .fin _ _ _, .inf _ => x
  | _, _ => nanBits

end Tenon.Flt

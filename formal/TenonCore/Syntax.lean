/-
Tenon Core: syntax, values and programs (formal/README.md, "The model").

The core is a first-order expression language with closures, mutable
local variables (no shadowing), places (`x.f[i].0`), pattern matching,
early exits, traps, capabilities and obligations (linear and unique values).
Everything is a value: there is no heap in the sequential core (Tenon's
lists, maps and strings have value semantics; copy-on-write is an
implementation detail). The worker model (Workers.lean) adds heaps.
-/
namespace Tenon

/-! ## Capabilities -/

/-- The capability kinds: the components of `Sys` (reference §10) and `Workers` (§18). -/
inductive CapK where
  | console | fs | clock | net | proc | workers
  deriving DecidableEq, Repr, Inhabited

/-- A capability value. For `Fs`, `jail` is the confinement root (`none`: the
unattenuated `sys.fs`; `some r`: only paths under the segments `r`) and `ro`
says read-only. The other kinds have no attenuation. -/
structure Cap where
  kind : CapK
  jail : Option (List String) := none
  ro : Bool := false
  deriving DecidableEq, Repr, Inhabited

/-- Attenuation order: `c ≤ d` when `c` grants at most what `d` grants: the
same kind, read-only if `d` is, and (for `Fs`) confined at or below `d`'s root. -/
def Cap.leb (c d : Cap) : Bool :=
  c.kind == d.kind && (!d.ro || c.ro) &&
  (match d.jail, c.jail with
   | none, _ => true
   | some r, some r' => r.isPrefixOf r'
   | some _, none => false)

def Cap.le (c d : Cap) : Prop := Cap.leb c d = true

instance : LE Cap := ⟨Cap.le⟩

instance (c d : Cap) : Decidable (c ≤ d) := inferInstanceAs (Decidable (Cap.leb c d = true))

/-- `Fs.within(dir)`: confine to `dir` (its segments), below the current root. -/
def Cap.within (c : Cap) (segs : List String) : Cap :=
  { c with jail := some ((c.jail.getD []) ++ segs) }

/-- `Fs.read_only()`. -/
def Cap.readOnly (c : Cap) : Cap := { c with ro := true }

/-! ## Obligations -/

/-- The identity of one linear or unique value (minted when it is built). -/
structure Tok where
  id : Nat
  lin : Bool   -- true: linear (must be consumed); false: unique (may be dropped)
  deriving DecidableEq, Repr, Inhabited

/-- How a declared type may be used (reference §12). -/
inductive Kind where
  | copy | linear | unique
  deriving DecidableEq, Repr, Inhabited

/-- How a parameter receives its argument (reference §6, §12). -/
inductive Mode where
  | val | ref | mut
  deriving DecidableEq, Repr, Inhabited

/-! ## Types (used by the typing judgement, Typing.lean) -/

inductive Ty where
  | int | bool | str | unit
  | tup (ts : List Ty)
  | list (t : Ty)
  | map (k v : Ty)
  | adt (name : String) (args : List Ty)
  | fn (ps : List Ty) (r : Ty)
  | cap (k : CapK)
  | var (i : Nat)
  deriving Repr, Inhabited

/-! ## Syntax -/

inductive Lit where
  | int (i : Int) | bool (b : Bool) | str (s : String) | unit
  deriving DecidableEq, Repr, Inhabited

/-- Patterns (reference §7). `con v ps` matches a variant by name, following
the matched value's type (the variant names of its enum). -/
inductive Pat where
  | wild
  | bind (x : String)
  | lit (l : Lit)
  | tup (ps : List Pat)
  | con (v : String) (ps : List Pat)
  | alt (ps : List Pat)
  deriving Repr, Inhabited

inductive SeqK where
  | tup | list | map
  deriving DecidableEq, Repr, Inhabited

mutual
/-- A step of a place: a struct field, a tuple field, or an index (list or map). -/
inductive PStep where
  | fld (f : String)
  | tfld (i : Nat)
  | idx (e : Expr)

inductive Expr where
  | lit (l : Lit)
  /-- Read a place by value: a copy, or a move of a whole variable that holds an obligation. -/
  | place (x : String) (ps : List PStep)
  /-- Project a computed value (`f().x`). -/
  | proj (e : Expr) (ps : List PStep)
  | seq (k : SeqK) (es : List Expr)
  /-- Build a value of a declared struct or enum: its key, the variant, the payload. -/
  | con (s : String) (tag : Nat) (es : List Expr)
  /-- A closure; captures the variables without obligations by value. -/
  | lam (ps : List String) (body : Expr)
  | fnref (f : String)
  | call (f : Expr) (args : List Expr)
  /-- `recv.m(args)`: the method of the receiver's type (dispatch on its head). -/
  | mcall (m : String) (recv : Expr) (args : List Expr)
  /-- A builtin operation; place operands are inspected, not consumed. -/
  | prim (p : String) (args : List Expr)
  | letE (x : String) (mutable : Bool) (e body : Expr)
  | assign (x : String) (ps : List PStep) (e : Expr)
  | seqE (e1 e2 : Expr)
  | ite (c t f : Expr)
  /-- Arms: pattern, optional guard, body; the first that matches is taken. -/
  | mtch (e : Expr) (arms : List (Pat × Option Expr × Expr))
  | while (c body : Expr)
  | ret (e : Expr)
  | brk
  | cont
  /-- `e?` on an `Option` or `Result`. -/
  | try (e : Expr)
  /-- A closure that captures the listed variables by value (the variables its
  body uses, which the translator computes); each must hold a value without
  obligations. Typed by `HasTyX.clos` (Typing.lean). -/
  | clos (caps : List String) (ps : List String) (body : Expr)
  /-- A type annotation (`let x: T = e`, a closure's parameter types): a hint
  for the checker (TenonCore/Check.lean), with no run-time effect. -/
  | ann (t : Ty) (e : Expr)
  /-- A construct of Tenon the core does not model (the translator's fallback). -/
  | unsup (why : String)
end

instance : Inhabited Expr := ⟨.lit .unit⟩

/-! ## Values -/

inductive Val where
  | int (i : Int)
  | bool (b : Bool)
  | str (s : String)
  | unit
  /-- Tuples, lists and maps (a map is a list of `(key, value)` tuples in insertion order). -/
  | seq (k : SeqK) (vs : List Val)
  /-- A value of a declared type: key, variant, its obligation token (linear/unique types), payload. -/
  | adt (s : String) (tag : Nat) (tok : Option Tok) (vs : List Val)
  /-- A closure: captured names and values, parameters, body. -/
  | clo (names : List String) (vs : List Val) (ps : List String) (body : Expr)
  /-- A named function (or builtin) used as a value. -/
  | fn (f : String)
  | cap (c : Cap)
  deriving Inhabited

def Lit.val : Lit → Val
  | .int i => .int i
  | .bool b => .bool b
  | .str s => .str s
  | .unit => .unit

/-! ## Programs -/

/-- A declared struct or enum. A struct has one variant (tag 0) and field names. -/
structure AdtDecl where
  name : String                         -- as formatting shows it
  isStruct : Bool
  kind : Kind
  tparams : Nat := 0
  fields : List String := []            -- struct field names
  variants : List (String × List Ty)    -- variant names and payload types (struct: one)
  deriving Inhabited

/-- A function or method. `owner`: the type whose method it is; a by-value
`self` of that type is finished (its obligation discharged) when the method ends. -/
structure FnDecl where
  params : List (String × Mode)
  body : Expr
  owner : Option String := none
  tparams : Nat := 0
  ptys : List Ty := []
  ret : Ty := .unit
  deriving Inhabited

/-- An effect on the outside world, with the capability that performed it. -/
structure Event where
  cap : Cap
  op : String
  arg : String
  deriving Inhabited

/-- What a builtin returns: a value, optionally a new value for its receiver
place (`xs.push(x)`), its effects and the world's new state. -/
inductive PrimRes where
  | ok (v : Val) (self : Option Val) (evs : List Event) (w : Nat)
  | trap (msg : String)
  | stuck (why : String)
  | unsup (why : String)   -- a case the model's builtin does not cover

structure Prog where
  fns : String → Option FnDecl
  adts : String → Option AdtDecl
  /-- Builtins; the `Nat` is the outside world's state they may read and
  advance (the position in standard input). -/
  prim : String → Option (List Val → Nat → PrimRes)

/-! ## Evaluation results -/

abbrev Env := List (String × Option Val)   -- `none`: moved

structure St where
  next : Nat := 0              -- the next token
  minted : List Tok := []      -- obligations created, newest first
  out : List Event := []       -- effects, newest first
  burned : List Tok := []      -- obligations discharged, newest first
  dropped : List Tok := []     -- unique values dropped, newest first
  world : Nat := 0             -- the outside world's state (Prog.prim)
  deriving Inhabited

inductive Ctl where
  | ret (v : Val) | brk | cont

/-- Why evaluation cannot go on: a type error, or an obligation rule broken. -/
inductive Stuck where
  | type | linear
  deriving DecidableEq, Repr

inductive Err where
  | trap (msg : String) (st : St)
  | stuck (k : Stuck) (why : String)
  | timeout
  | unsup (why : String)

inductive Out (α : Type) where
  | ok (a : α) (ρ : Env) (st : St)
  | ctl (c : Ctl) (ρ : Env) (st : St)
  | err (e : Err)

end Tenon

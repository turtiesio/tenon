/-
The surface syntax tree as `tenon ast FILE` prints it (compiler/astdump.tn).
Positions are kept only for messages.
-/
namespace Front

inductive STy where
  | named (n : String) (args : List STy)
  | fn (ps : List STy) (r : STy)
  | tup (ts : List STy)
  deriving Repr, Inhabited

inductive SPat where
  | wild
  | bind (x : String)
  | int (i : Int)
  | str (s : String)
  | bool (b : Bool)
  | tup (ps : List SPat)
  | variant (q : Option String) (v : String) (ps : List SPat)
  | alt (ps : List SPat)
  deriving Repr, Inhabited

mutual
inductive SExpr where
  | int (i : Int)
  | float (s : String)
  | bool (b : Bool)
  | str (segs : List SSeg)
  | unit
  | name (n : String)
  | path (t m : String)
  | field (e : SExpr) (f : String)
  | tfield (e : SExpr) (i : Nat)
  | index (a b : SExpr)
  | call (f : SExpr) (args : List SExpr)
  | method (r : SExpr) (m : String) (args : List SExpr)
  | unary (op : String) (e : SExpr)
  | binary (op : String) (l r : SExpr)
  | ite (c : SExpr) (t : List SStmt) (e : Option SExpr)
  | mtch (s : SExpr) (arms : List SArm)
  | block (b : List SStmt)
  | list (es : List SExpr)
  | map (kvs : List (SExpr × SExpr))
  | tuple (es : List SExpr)
  | new (n : String) (fs : List (String × SExpr)) (base : Option SExpr)
  | try (e : SExpr)
  | mutarg (e : SExpr)
  | lambda (ps : List (String × Option STy)) (r : Option STy) (body : SExpr)
  | dyn (t : String) (e : SExpr)

inductive SSeg where
  | lit (s : String)
  | expr (e : SExpr)
  | fmt (e : SExpr) (spec : String)

inductive SArm where
  | arm (p : SPat) (guard : Option SExpr) (body : SExpr)
  | fallback (body : SExpr)

inductive SStmt where
  | letS (p : SPat) (mutable : Bool) (ty : Option STy) (v : SExpr) (els : Option (List SStmt))
  | expr (e : SExpr)
  | assign (op : Option String) (t v : SExpr)
  | whileS (c : SExpr) (b : List SStmt)
  | forRange (p : SPat) (a b : SExpr) (body : List SStmt)
  | forEach (p : SPat) (e : SExpr) (body : List SStmt)
  | ret (v : Option SExpr)
  | brk
  | cont
end

instance : Inhabited SExpr := ⟨.unit⟩

structure SParam where
  name : String
  byRef : Bool
  byMut : Bool
  ty : STy
  deriving Inhabited

structure SFn where
  isConst : Bool
  pub : Bool
  owner : Option STy
  name : String
  tparams : List String
  selfKind : String          -- "", "self", "mut-self", "ref-self"
  params : List SParam
  ret : Option STy
  body : Option (List SStmt) -- none: extern (or a trait method without a default)
  isExtern : Bool
  deriving Inhabited

structure SStruct where
  kind : String              -- "", "linear", "unique"
  name : String
  tparams : List String
  fields : List (String × STy)
  deriving Inhabited

structure SEnum where
  kind : String
  name : String
  tparams : List String
  variants : List (String × List STy)
  deriving Inhabited

inductive SItem where
  | imp (name : String)
  | struct (s : SStruct)
  | enum (e : SEnum)
  | fn (f : SFn)
  | other (what : String)    -- traits, impls: not translated
  | bad (line : String) (msg : String)
  deriving Inhabited

end Front

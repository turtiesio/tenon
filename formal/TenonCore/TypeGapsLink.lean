/-
# Link: milestone-3 item 3 as implemented

What the compiler does for user `Eq`/`Ord`/`Hash` impls, trait type
parameters and supertraits (docs/reference.md §17; compiler/ckdecl.tn,
compiler/iuser.tn, runtime/tenon.h `TN_MAP_FUNCS_U`), as instances of the
specification in TypeGaps.lean and Traits.lean:

* `preludeEnv`: the traits of lib/v2/prelude.tn, `Eq`, `Ord: Eq` and
  `Hash: Eq`, each with its one method. Under the supertrait rule (the
  checker checks it impl by impl, `ImplSupersOk`), a bound `T: Ord` or
  `T: Hash` gives `T: Eq` (`prelude_ord_gives_eq`, `prelude_hash_gives_eq`),
  which is why the checker closes every bound under its supertraits
  (compiler/ckdecl.tn `lower_bounds`).
* Maps keyed by a type with Eq or Hash impls are `hset`/`hget` with the
  64-bit hash as the bucket function (`userGet`): a lookup compares the key
  with the entries of its hash in insertion order, `eq key entry`, and the
  first equal one is the key's; an insertion replaces that entry's value in
  place or appends. So with lawful impls a lookup finds what an Eq-keyed map
  finds (`user_map_agrees`), and with any impls every value a map holds was
  inserted (`user_map_prov`).
* `cmp` returns the prelude's `Ordering` (tags 0, 1, 2: Less, Equal,
  Greater, `decOrdering`); sorting with any user `cmp` gives a permutation or
  a trap (`user_cmp_sort_perm`).
* Trait type parameters: `impl Into[Int] for Cel` and `impl Into[Str] for
  Cel` do not overlap, so a program with both is coherent
  (`into_impls_coherent`). The checker resolves each call to one of them
  statically (by the expected type); the core's elaboration `withImpls`
  keys methods by the type's head, so it does not run such programs yet
  (they are outside formal_diff's subset).
-/
import TenonCore.TypeGaps

namespace Tenon.TypeGaps.Link
open Tenon Tenon.Traits

/-- `fn name(self, other: Self) -> ret`. -/
def binMethod (n : String) (ret : Ty) : TMethod :=
  { name := n, params := [("self", .val), ("other", .val)], ptys := [.var 0], ret }

def eqTrait : TraitDecl := { name := "Eq", methods := [binMethod "eq" .bool] }

def ordTrait : TraitDecl :=
  { name := "Ord", supers := [("Eq", [])], methods := [binMethod "cmp" (.adt "Ordering" [])] }

def hashTrait : TraitDecl :=
  { name := "Hash", supers := [("Eq", [])], methods := [{ name := "hash", params := [("self", .val)], ptys := [], ret := .int }] }

/-- The prelude's derived traits with a program's impls. -/
def preludeEnv (impls : List ImplDecl) : TraitEnv := { traits := [eqTrait, ordTrait, hashTrait], impls }

theorem prelude_ord (impls : List ImplDecl) : (preludeEnv impls).trait "Ord" = some ordTrait := by
  simp [TraitEnv.trait, preludeEnv, eqTrait, ordTrait]

theorem prelude_hash (impls : List ImplDecl) : (preludeEnv impls).trait "Hash" = some hashTrait := by
  simp [TraitEnv.trait, preludeEnv, eqTrait, ordTrait, hashTrait]

/-- A bound `T: Ord` gives `T: Eq` (Ord's supertrait), whatever the program's impls. -/
theorem prelude_ord_gives_eq (impls : List ImplDecl) (hS : SuperOk (preludeEnv impls)) {t : Ty}
    (h : Holds (preludeEnv impls) "Ord" [] t) : Holds (preludeEnv impls) "Eq" [] t :=
  ord_bound_gives_eq hS (prelude_ord impls) rfl (by simp [ordTrait]) h

/-- A bound `T: Hash` gives `T: Eq` (Hash's supertrait). -/
theorem prelude_hash_gives_eq (impls : List ImplDecl) (hS : SuperOk (preludeEnv impls)) {t : Ty}
    (h : Holds (preludeEnv impls) "Hash" [] t) : Holds (preludeEnv impls) "Eq" [] t :=
  hash_bound_gives_eq hS (prelude_hash impls) rfl (by simp [hashTrait]) h

/-! ## Maps with Eq and Hash impls -/

variable {α β : Type}

/-- A lookup in a map keyed by a type with Eq or Hash impls: the entries whose
(64-bit) hash is the key's, in insertion order, `eq key entry`. -/
def userGet (eq : α → α → Bool) (h : α → Nat) (k : α) (B : Buckets α β) : Option β := hget eq h k B

/-- **Lawful impls**: the map answers every lookup as the Eq-keyed map does. -/
theorem user_map_agrees {E : UEq α} (hE : E.Lawful) {h : α → Nat} (hH : BucketLawful E h)
    (ops : List (α × β)) (j : α) :
    userGet E.eq h j (hbuild E.eq h (fun _ => []) ops) = mget E.eq j (mbuild E.eq [] ops) :=
  hmap_agrees hE hH ops (fun _ => []) [] (fun _ => rfl) j

/-- **Any impls**: every key and value the map holds was inserted. -/
theorem user_map_prov (eq : α → α → Bool) (h : α → Nat) (ops : List (α × β)) (i : Nat) :
    Prov ops (hbuild eq h (fun _ => []) ops i) :=
  hbuild_prov eq h ops ops (fun _ => []) (fun _ hk => hk) (fun _ e he => by cases he) i

/-! ## Sorting with a user `cmp` -/

/-- The prelude's `Ordering` (`enum Ordering { Less, Equal, Greater }`). -/
def decOrdering : Val → Option Ordering
  | .adt "Ordering" 0 none [] => some .lt
  | .adt "Ordering" 1 none [] => some .eq
  | .adt "Ordering" 2 none [] => some .gt
  | _ => none

/-- **Any user `cmp`** (any body, any impls): the sort traps or returns a permutation. -/
theorem user_cmp_sort_perm (P : Prog) (E : TraitEnv) (n : Nat) (f : String) (l r : List Val)
    (h : isortM (coreCmp (withImpls P E) n f decOrdering) l = some r) : r.Perm l :=
  user_sort_perm P E n f decOrdering l r h

/-! ## Trait type parameters: one trait at two arguments for one type -/

def intoTrait : TraitDecl :=
  { name := "Into", tparams := 1, methods := [{ name := "into", params := [("self", .val)], ptys := [], ret := .var 1 }] }

def intoInt : ImplDecl := { trait := "Into", targs := [.int], self := .adt "Cel" [], methods := [("into", .unsup "")] }

def intoStr : ImplDecl := { trait := "Into", targs := [.str], self := .adt "Cel" [], methods := [("into", .unsup "")] }

theorem into_no_overlap : ¬ Overlap intoInt intoStr := by
  rintro ⟨σ1, σ2, -, h⟩
  simp [intoInt, intoStr, tsub] at h

/-- `impl Into[Int] for Cel` and `impl Into[Str] for Cel` are coherent. -/
theorem into_impls_coherent : Coherent { traits := [intoTrait], impls := [intoInt, intoStr] } := by
  refine List.Pairwise.cons ?_ (List.Pairwise.cons (fun _ hb => by cases hb) .nil)
  intro b hb _
  rcases List.mem_singleton.1 hb with rfl
  exact into_no_overlap

end Tenon.TypeGaps.Link

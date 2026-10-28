/-
TODO (formal/README.md, "What remains"): the parts of the item-3 specification
(TenonCore/TypeGaps.lean) that are stated but not proved yet. Not built by the gate.
-/
import TenonCore.TypeGaps

namespace Tenon.Todo
open Tenon Tenon.TypeGaps

/-- Sorted permutations of each other agree up to Eq, for a total preorder
(`TypeGaps.sorted_unique` proves equality for a total order). -/
theorem sorted_perm_equiv {α : Type} {O : UOrd α} (hO : O.Lawful) {l1 l2 : List α}
    (h1 : Sorted O.cmp l1) (h2 : Sorted O.cmp l2) (hp : l1.Perm l2) :
    LRel (fun a b => O.cmp a b = .eq) l1 l2 := sorry

/-- A sort is stable when it keeps the input order of equivalent elements. -/
def Stable {α : Type} (cmp : α → α → Ordering) (f : List α → List α) : Prop :=
  ∀ l x, (f l).filter (fun y => cmp x y == .eq) = l.filter (fun y => cmp x y == .eq)

/-- `isort` is stable. -/
theorem isort_stable {α : Type} {O : UOrd α} (hO : O.Lawful) : Stable O.cmp (isort O.cmp) := sorry

/-- Stable sorts are unique for a total preorder: two backends that both sort
stably (sorted, permutation, stable) agree exactly, even when the user's Ord
calls distinct values equal. -/
theorem stable_sort_unique {α : Type} {O : UOrd α} (hO : O.Lawful) (f g : List α → List α)
    (hf : ∀ l, (f l).Perm l ∧ Sorted O.cmp (f l)) (hg : ∀ l, (g l).Perm l ∧ Sorted O.cmp (g l))
    (sf : Stable O.cmp f) (sg : Stable O.cmp g) (l : List α) : f l = g l := sorry

end Tenon.Todo

/-
Item 3 (TypeGaps.lean), stable sorting: with a user `Ord` that is only a
total preorder (it may call distinct values equal), sorting is still
well defined when it is stable. `isort` is stable (`isort_stable`), stable
sorts are unique (`stable_sort_unique`: two backends that sort stably agree
exactly), and any two sorted permutations agree up to the user's `equal`
(`sorted_perm_equiv`).
-/
import TenonCore.TypeGaps

namespace Tenon.TypeGaps

variable {α : Type}

/-- A sort is stable when it keeps the input order of equivalent elements. -/
def Stable (cmp : α → α → Ordering) (f : List α → List α) : Prop :=
  ∀ l x, (f l).filter (fun y => cmp x y == .eq) = l.filter (fun y => cmp x y == .eq)

section
variable {O : UOrd α} (hO : O.Lawful)
include hO

theorem UOrd.eq_symm {a b : α} (h : O.cmp a b = .eq) : O.cmp b a = .eq := by
  rw [hO.antisymm a b, h]; rfl

theorem UOrd.eq_of_le_le {a b : α} (h1 : le O.cmp a b) (h2 : le O.cmp b a) : O.cmp a b = .eq := by
  unfold le at h1 h2; rw [hO.antisymm a b] at h2
  cases h : O.cmp a b <;> simp_all [Ordering.swap]

/-- Inserting keeps every class's subsequence, with the new element first. -/
theorem ins_filter (x c : α) : ∀ l : List α,
    (ins O.cmp x l).filter (fun y => O.cmp c y == .eq) = (x :: l).filter (fun y => O.cmp c y == .eq)
  | [] => rfl
  | y :: ys => by
    unfold ins
    split
    · rename_i hgt
      have ih := ins_filter x c ys
      by_cases hy : O.cmp c y = .eq
      · have hx : O.cmp c x ≠ .eq := fun hx => by
          have := UOrd.eq_trans hO (UOrd.eq_symm hO hx) hy
          rw [this] at hgt; cases hgt
        simp only [List.filter_cons, hy, hx, beq_self_eq_true, ite_true, beq_iff_eq, ite_false,
          reduceCtorEq] at ih ⊢
        rw [ih]
      · by_cases hx : O.cmp c x = .eq
        · simp only [List.filter_cons, hy, hx, beq_self_eq_true, ite_true, beq_iff_eq, ite_false] at ih ⊢
          exact ih
        · simp only [List.filter_cons, hy, hx, beq_iff_eq, ite_false] at ih ⊢
          exact ih
    · rfl

/-- **Insertion sort is stable.** -/
theorem isort_stable : Stable O.cmp (isort O.cmp) := by
  intro l c
  induction l with
  | nil => rfl
  | cons x xs ih =>
    simp only [isort]
    rw [ins_filter hO x c]
    simp only [List.filter_cons]
    split <;> simp_all

theorem sorted_head_le {a : α} {l : List α} (h : Sorted O.cmp (a :: l)) {b : α} (hb : b ∈ a :: l) :
    le O.cmp a b := by
  rcases List.mem_cons.1 hb with rfl | hb
  · exact UOrd.le_refl hO _
  · exact (List.pairwise_cons.1 h).1 b hb

/-- Sorted permutations with the same subsequence in every class are equal. -/
theorem sorted_eq_of_filters : ∀ (a b : List α), Sorted O.cmp a → Sorted O.cmp b → a.Perm b →
    (∀ c, a.filter (fun y => O.cmp c y == .eq) = b.filter (fun y => O.cmp c y == .eq)) → a = b
  | [], b, _, _, hp, _ => (List.Perm.nil_eq hp).symm ▸ rfl
  | _ :: _, [], _, _, hp, _ => absurd hp.length_eq (by simp)
  | a0 :: a', b0 :: b', ha, hb, hp, hf => by
    have h1 : le O.cmp b0 a0 := sorted_head_le hO hb (hp.subset (List.mem_cons_self))
    have h2 : le O.cmp a0 b0 := sorted_head_le hO ha (hp.symm.subset (List.mem_cons_self))
    have hab : O.cmp a0 b0 = .eq := UOrd.eq_of_le_le hO h2 h1
    have h0 := hf a0
    simp only [List.filter_cons, hO.refl a0, hab, beq_self_eq_true, ite_true, List.cons.injEq] at h0
    obtain ⟨rfl, -⟩ := h0
    have hp' : a'.Perm b' := List.Perm.cons_inv hp
    refine congrArg _ (sorted_eq_of_filters a' b' (List.pairwise_cons.1 ha).2 (List.pairwise_cons.1 hb).2 hp' ?_)
    intro c
    have := hf c
    simp only [List.filter_cons] at this
    split at this
    · exact (List.cons.inj this).2
    · exact this

/-- **Stable sorts are unique** for a total preorder: two backends that both
sort stably (a sorted permutation that keeps the input order of equivalent
elements) give the same list, even when the user's `Ord` calls distinct
values equal. -/
theorem stable_sort_unique (f g : List α → List α)
    (hf : ∀ l, (f l).Perm l ∧ Sorted O.cmp (f l)) (hg : ∀ l, (g l).Perm l ∧ Sorted O.cmp (g l))
    (sf : Stable O.cmp f) (sg : Stable O.cmp g) (l : List α) : f l = g l :=
  sorted_eq_of_filters hO _ _ (hf l).2 (hg l).2 ((hf l).1.trans (hg l).1.symm)
    (fun c => (sf l c).trans (sg l c).symm)

theorem LRel.eq_refl : ∀ l : List α, LRel (fun a b => O.cmp a b = .eq) l l
  | [] => .nil
  | a :: l => .cons (hO.refl a) (LRel.eq_refl l)

theorem LRel.eq_trans : ∀ {l1 l2 l3 : List α}, LRel (fun a b => O.cmp a b = .eq) l1 l2 →
    LRel (fun a b => O.cmp a b = .eq) l2 l3 → LRel (fun a b => O.cmp a b = .eq) l1 l3
  | _, _, _, .nil, .nil => .nil
  | _, _, _, .cons h1 r1, .cons h2 r2 => .cons (UOrd.eq_trans hO h1 h2) (LRel.eq_trans r1 r2)

/-- Moving an element past equivalent ones keeps the list equivalent position by position. -/
theorem LRel.move {a : α} : ∀ (u w : List α) (b : α), O.cmp b a = .eq → (∀ y ∈ u, O.cmp y a = .eq) →
    LRel (fun a b => O.cmp a b = .eq) (b :: (u ++ w)) (u ++ a :: w)
  | [], w, b, hb, _ => .cons hb (LRel.eq_refl hO w)
  | x :: u, w, b, hb, hu => by
    have hx := hu x (by simp)
    exact .cons (UOrd.eq_trans hO hb (UOrd.eq_symm hO hx)) (LRel.move u w x hx (fun y hy => hu y (by simp [hy])))

/-- **Sorted permutations agree up to the user's `equal`**, for a total preorder:
whatever (correct) sort a backend uses, position by position the results are
equivalent. -/
theorem sorted_perm_equiv : ∀ {l1 l2 : List α}, Sorted O.cmp l1 → Sorted O.cmp l2 → l1.Perm l2 →
    LRel (fun a b => O.cmp a b = .eq) l1 l2
  | [], l2, _, _, hp => by have := (List.Perm.nil_eq hp).symm; subst this; exact .nil
  | a :: l1', l2, h1, h2, hp => by
    obtain ⟨u, w, rfl⟩ := List.append_of_mem (hp.subset (List.mem_cons_self))
    have hmin : ∀ x ∈ u ++ a :: w, le O.cmp a x := fun x hx => sorted_head_le hO h1 (hp.symm.subset hx)
    have hu : ∀ y ∈ u, O.cmp y a = .eq := by
      intro y hy
      have hle : le O.cmp y a := (List.pairwise_append.1 h2).2.2 y hy a (by simp)
      exact UOrd.eq_of_le_le hO hle (hmin y (by simp [hy]))
    have hp' : l1'.Perm (u ++ w) := List.Perm.cons_inv (hp.trans List.perm_middle)
    have hs : Sorted O.cmp (u ++ w) := ((List.Sublist.refl u).append (List.sublist_cons_self a w)) |>
      fun hsub => List.Pairwise.sublist hsub h2
    have ih := sorted_perm_equiv (List.pairwise_cons.1 h1).2 hs hp'
    exact LRel.eq_trans hO (.cons (hO.refl a) ih) (LRel.move hO u w a (hO.refl a) hu)

/-- And so every stable sort is `isort`. -/
theorem stable_sort_eq_isort (f : List α → List α) (hf : ∀ l, (f l).Perm l ∧ Sorted O.cmp (f l))
    (sf : Stable O.cmp f) (l : List α) : f l = isort O.cmp l :=
  stable_sort_unique hO f (isort O.cmp) hf (fun l => ⟨isort_perm _ l, isort_sorted hO l⟩) sf (isort_stable hO) l

end

end Tenon.TypeGaps

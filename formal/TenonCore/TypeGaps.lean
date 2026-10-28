/-
# Spec: milestone-3 item 3, "type-system gaps" (tenon.md §6)

The Lean specification item 3's implementation must pass before it lands:
user `Eq`/`Ord`/`Hash` impls used consistently by maps and sorting in both
backends, trait type parameters and supertraits. Each feature and the
theorem it must satisfy:

* **User impls are ordinary core functions.** An impl's methods elaborate to
  `Prog.fns` entries (`Traits.withImpls`), so every guarantee proved for all
  programs holds whatever their bodies do: `user_impls_capability_safe`,
  `user_impls_obligations_conserved`, and `user_impl_no_effects` (a user
  `eq`/`cmp`/`hash` on capability-free values performs no effect).
* **Laws** (the user's obligation, not checkable by the compiler): `UEq.Lawful`
  (an equivalence), `UOrd.Lawful` (a total preorder: `cmp a a = .eq`,
  `cmp b a = (cmp a b).swap`, transitivity of `≤`; totality is built in since
  `cmp` returns one of three results, `UOrd.total`), `UOrd.TotalOrder` (also
  antisymmetric w.r.t. `=`), `Consistent` (`cmp a b = .eq ↔ a == b`; then Eq
  is lawful: `eqLawful_of_ord`), `BucketLawful` (`a == b → hash a = hash b`,
  for the bucket function `hash a % n` of either backend).
* **Sorting with a user comparator** (`isort`, insertion sort; a backend may
  use another algorithm if it meets the same theorems): for any comparator,
  lawful or not, the result is a permutation (`isort_perm`), and with one that
  fails (a trap or timeout of the user's `cmp`) the sort fails or returns a
  permutation (`isortM_perm`, `user_sort_perm` for a core function as the
  comparator). With a lawful comparator it is sorted (`isort_sorted`),
  idempotent (`isort_idem`), maps Eq-equivalent inputs to Eq-equivalent
  outputs (`isort_congr`), and with a total order every correct sort gives the
  same list (`sort_unique`): the interpreter and C backend cannot disagree.
* **Maps keyed by user types** (`mset`/`mget`: by Eq, insertion order;
  `oset`/`oget`: ordered by Ord; `hset`/`hget`: hashed buckets by Eq):
  with lawful impls, lookup after insert returns the inserted value
  (`mget_mset_self`, `oget_oset_self`), other keys are unaffected
  (`mget_mset_other`, `oget_oset_other`), keys are unique modulo Eq
  (`mbuild_unique`, `obuild_sorted_unique`, `hbuild_unique`), the ordered
  map iterates in strictly increasing key order (`obuild_sorted_unique`), and
  the three maps agree on every lookup (`omap_agrees`, `hmap_agrees`). With
  arbitrary (unlawful) impls they still terminate (Lean functions are total),
  every value they hold or return was inserted, and they hold at most one entry
  per insertion (`mbuild_prov`, `mget_prov`, `obuild_prov`, `hbuild_prov`,
  `mbuild_length`, `obuild_length`): a broken impl breaks functional results
  only, never memory or capability safety.
* **Trait type parameters and supertraits**: modelled in Traits.lean
  (`TraitDecl.tparams`, `TraitDecl.supers`, `Holds`, `Entails`). The rules: an
  impl of a subtrait requires impls of its supertraits (`Traits.SuperOk`,
  checked per impl as `Traits.ImplSupersOk`: `Traits.superOk_of_impls`); a
  bound `T: Sub` entails `T: Super` (`Traits.super_entails`; for the prelude,
  `ord_bound_gives_eq`, `hash_bound_gives_eq`).

Stated but not proved (formal/Todo/TypeGaps.lean): uniqueness of sorted
permutations up to Eq for a total preorder and uniqueness of a stable sort.
-/
import TenonCore.Traits
import TenonCore.Capability
import TenonCore.LinearSafe

namespace Tenon.TypeGaps
open Tenon Tenon.Traits

variable {α β : Type}

/-! ## User impls and their laws -/

/-- A user `Eq` impl: `fn eq(self, other: Self) -> Bool`. -/
structure UEq (α : Type) where
  eq : α → α → Bool

/-- A user `Ord` impl: `fn cmp(self, other: Self) -> Ordering` (less, equal, greater). -/
structure UOrd (α : Type) where
  cmp : α → α → Ordering

structure UEq.Lawful (E : UEq α) : Prop where
  refl : ∀ a, E.eq a a = true
  symm : ∀ a b, E.eq a b = true → E.eq b a = true
  trans : ∀ a b c, E.eq a b = true → E.eq b c = true → E.eq a c = true

/-- `a ≤ b` for a comparator. -/
def le (cmp : α → α → Ordering) (a b : α) : Prop := cmp a b ≠ .gt

/-- A total preorder. -/
structure UOrd.Lawful (O : UOrd α) : Prop where
  refl : ∀ a, O.cmp a a = .eq
  antisymm : ∀ a b, O.cmp b a = (O.cmp a b).swap
  trans : ∀ a b c, le O.cmp a b → le O.cmp b c → le O.cmp a c

/-- A total order: a total preorder whose `.eq` is equality. -/
structure UOrd.TotalOrder (O : UOrd α) : Prop extends O.Lawful where
  eq_of_cmp : ∀ a b, O.cmp a b = .eq → a = b

/-- Eq and Ord agree: `cmp` says equal exactly when `eq` does. -/
def Consistent (E : UEq α) (O : UOrd α) : Prop := ∀ a b, O.cmp a b = .eq ↔ E.eq a b = true

/-- The Hash law for a bucket function (`hash a % n`): equal keys share a bucket. -/
def BucketLawful (E : UEq α) (bk : α → Nat) : Prop := ∀ a b, E.eq a b = true → bk a = bk b

section Ord
variable {O : UOrd α} (hO : O.Lawful)
include hO

theorem UOrd.ne_lt_iff (a b : α) : O.cmp a b ≠ .lt ↔ le O.cmp b a := by
  unfold le; rw [hO.antisymm a b]; cases O.cmp a b <;> simp [Ordering.swap]

/-- Totality. -/
theorem UOrd.total (a b : α) : le O.cmp a b ∨ le O.cmp b a := by
  unfold le; rw [hO.antisymm a b]; cases O.cmp a b <;> simp [Ordering.swap]

theorem UOrd.le_refl (a : α) : le O.cmp a a := by unfold le; rw [hO.refl]; simp

theorem UOrd.le_of_eq {a b : α} (h : O.cmp a b = .eq) : le O.cmp a b ∧ le O.cmp b a := by
  refine ⟨by unfold le; rw [h]; simp, ?_⟩
  unfold le; rw [hO.antisymm a b, h]; simp [Ordering.swap]

/-- `cmp` is determined by `≤` both ways. -/
theorem UOrd.cmp_eq {a b c d : α} (h1 : le O.cmp a b ↔ le O.cmp c d) (h2 : le O.cmp b a ↔ le O.cmp d c) :
    O.cmp a b = O.cmp c d := by
  rw [← UOrd.ne_lt_iff hO, ← UOrd.ne_lt_iff hO] at h2
  unfold le at h1
  cases hx : O.cmp a b <;> cases hy : O.cmp c d <;> simp_all

/-- Equivalent elements compare alike. -/
theorem UOrd.cmp_congr {a a' b b' : α} (ha : O.cmp a a' = .eq) (hb : O.cmp b b' = .eq) :
    O.cmp a b = O.cmp a' b' := by
  have ha' := UOrd.le_of_eq hO ha
  have hb' := UOrd.le_of_eq hO hb
  apply UOrd.cmp_eq hO
  · exact ⟨fun h => hO.trans _ _ _ ha'.2 (hO.trans _ _ _ h hb'.1),
      fun h => hO.trans _ _ _ ha'.1 (hO.trans _ _ _ h hb'.2)⟩
  · exact ⟨fun h => hO.trans _ _ _ hb'.2 (hO.trans _ _ _ h ha'.1),
      fun h => hO.trans _ _ _ hb'.1 (hO.trans _ _ _ h ha'.2)⟩

theorem UOrd.eq_trans {a b c : α} (h1 : O.cmp a b = .eq) (h2 : O.cmp b c = .eq) : O.cmp a c = .eq := by
  rw [← UOrd.cmp_congr hO (hO.refl a) h2]; exact h1

theorem UOrd.lt_trans {a b c : α} (h1 : O.cmp a b = .lt) (h2 : O.cmp b c = .lt) : O.cmp a c = .lt := by
  have hac : le O.cmp a c := hO.trans _ _ _ (by unfold le; rw [h1]; simp) (by unfold le; rw [h2]; simp)
  have hca : ¬ le O.cmp c a := fun h => by
    have hcb := hO.trans _ _ _ h (show le O.cmp a b by unfold le; rw [h1]; simp)
    rw [← UOrd.ne_lt_iff hO] at hcb; exact hcb h2
  rw [← UOrd.ne_lt_iff hO] at hca
  unfold le at hac
  cases h : O.cmp a c <;> simp_all

end Ord

/-- With a lawful Ord, a consistent Eq is lawful. -/
theorem eqLawful_of_ord {E : UEq α} {O : UOrd α} (hO : O.Lawful) (hc : Consistent E O) : E.Lawful where
  refl a := (hc a a).1 (hO.refl a)
  symm a b h := (hc b a).1 (by rw [hO.antisymm a b, (hc a b).2 h]; rfl)
  trans a b c h1 h2 := (hc a c).1 (UOrd.eq_trans hO ((hc a b).2 h1) ((hc b c).2 h2))

/-! ## Sorting with a user comparator -/

def ins (cmp : α → α → Ordering) (x : α) : List α → List α
  | [] => [x]
  | y :: ys => if cmp x y = .gt then y :: ins cmp x ys else x :: y :: ys

/-- Insertion sort by a user comparator (stable: an element goes after the ones it is not below). -/
def isort (cmp : α → α → Ordering) : List α → List α
  | [] => []
  | x :: xs => ins cmp x (isort cmp xs)

def Sorted (cmp : α → α → Ordering) (l : List α) : Prop := l.Pairwise (le cmp)

theorem ins_perm (cmp : α → α → Ordering) (x : α) : ∀ l, (ins cmp x l).Perm (x :: l)
  | [] => .refl _
  | y :: ys => by
    unfold ins; split
    · exact ((ins_perm cmp x ys).cons y).trans (.swap x y ys)
    · exact .refl _

/-- **Any comparator, lawful or not: the sort returns a permutation of its input.** -/
theorem isort_perm (cmp : α → α → Ordering) : ∀ l, (isort cmp l).Perm l
  | [] => .refl _
  | x :: xs => (ins_perm cmp x _).trans ((isort_perm cmp xs).cons x)

theorem ins_sorted {O : UOrd α} (hO : O.Lawful) (x : α) :
    ∀ l, Sorted O.cmp l → Sorted O.cmp (ins O.cmp x l)
  | [], _ => List.pairwise_singleton _ _
  | y :: ys, h => by
    rw [Sorted, List.pairwise_cons] at h
    unfold ins; split
    · rename_i hgt
      refine List.pairwise_cons.2 ⟨fun z hz => ?_, ins_sorted hO x ys h.2⟩
      rcases List.mem_cons.1 ((ins_perm _ x ys).mem_iff.1 hz) with rfl | hz
      · unfold le; rw [hO.antisymm z y, hgt]; simp [Ordering.swap]
      · exact h.1 z hz
    · rename_i hng
      refine List.pairwise_cons.2 ⟨fun z hz => ?_, List.pairwise_cons.2 h⟩
      rcases List.mem_cons.1 hz with rfl | hz
      · exact hng
      · exact hO.trans _ _ _ hng (h.1 z hz)

/-- **With a lawful comparator the result is sorted.** -/
theorem isort_sorted {O : UOrd α} (hO : O.Lawful) : ∀ l, Sorted O.cmp (isort O.cmp l)
  | [] => .nil
  | x :: xs => ins_sorted hO x _ (isort_sorted hO xs)

/-- A sorted list is left as it is (for any comparator). -/
theorem isort_of_sorted (cmp : α → α → Ordering) : ∀ l, Sorted cmp l → isort cmp l = l
  | [], _ => rfl
  | x :: xs, h => by
    rw [Sorted, List.pairwise_cons] at h
    simp only [isort, isort_of_sorted cmp xs h.2]
    cases xs with
    | nil => rfl
    | cons y ys =>
      have hy : cmp x y ≠ .gt := h.1 y (.head _)
      simp [ins, hy]

/-- Sorting is idempotent. -/
theorem isort_idem {O : UOrd α} (hO : O.Lawful) (l : List α) :
    isort O.cmp (isort O.cmp l) = isort O.cmp l :=
  isort_of_sorted _ _ (isort_sorted hO l)

/-- With a total order, sorted permutations of each other are equal. -/
theorem sorted_unique {O : UOrd α} (hO : O.TotalOrder) :
    ∀ {l1 l2 : List α}, Sorted O.cmp l1 → Sorted O.cmp l2 → l1.Perm l2 → l1 = l2
  | [], _, _, _, hp => hp.nil_eq
  | a :: t1, [], _, _, hp => absurd hp.length_eq (by simp)
  | a :: t1, b :: t2, h1, h2, hp => by
    rw [Sorted, List.pairwise_cons] at h1 h2
    have hba : le O.cmp b a := by
      rcases List.mem_cons.1 (hp.mem_iff.1 (.head _)) with e | e
      · rw [e]; exact UOrd.le_refl hO.toLawful b
      · exact h2.1 a e
    have hab : le O.cmp a b := by
      rcases List.mem_cons.1 (hp.mem_iff.2 (.head _)) with e | e
      · rw [e]; exact UOrd.le_refl hO.toLawful a
      · exact h1.1 b e
    have e : a = b := by
      apply hO.eq_of_cmp
      rw [← UOrd.ne_lt_iff hO.toLawful] at hba
      unfold le at hab
      cases h : O.cmp a b <;> simp_all
    subst e
    rw [sorted_unique hO h1.2 h2.2 hp.cons_inv]

/-- **Sorting is well defined.** With a total order, any sort that returns a
sorted permutation (whatever its algorithm: the interpreter's or the C
runtime's) returns exactly `isort`'s result. -/
theorem sort_unique {O : UOrd α} (hO : O.TotalOrder) (f : List α → List α)
    (hf : ∀ l, (f l).Perm l ∧ Sorted O.cmp (f l)) (l : List α) : f l = isort O.cmp l :=
  sorted_unique hO (hf l).2 (isort_sorted hO.toLawful l) ((hf l).1.trans (isort_perm _ l).symm)

/-- Two lists related elementwise. -/
inductive LRel (R : α → α → Prop) : List α → List α → Prop
  | nil : LRel R [] []
  | cons {a b l l'} : R a b → LRel R l l' → LRel R (a :: l) (b :: l')

theorem ins_congr {O : UOrd α} (hO : O.Lawful) {x x' : α} (hx : O.cmp x x' = .eq) :
    ∀ {l l'}, LRel (fun a b => O.cmp a b = .eq) l l' →
      LRel (fun a b => O.cmp a b = .eq) (ins O.cmp x l) (ins O.cmp x' l')
  | _, _, .nil => .cons hx .nil
  | _, _, .cons (a := y) (b := y') hy hr => by
    simp only [ins, UOrd.cmp_congr hO hx hy]
    split
    · exact .cons hy (ins_congr hO hx hr)
    · exact .cons hx (.cons hy hr)

/-- **Equal-modulo-Eq inputs sort to equal-modulo-Eq outputs** (lawful comparator). -/
theorem isort_congr {O : UOrd α} (hO : O.Lawful) :
    ∀ {l l'}, LRel (fun a b => O.cmp a b = .eq) l l' →
      LRel (fun a b => O.cmp a b = .eq) (isort O.cmp l) (isort O.cmp l')
  | _, _, .nil => .nil
  | _, _, .cons h hr => ins_congr hO h (isort_congr hO hr)

/-! ### A comparator that may fail (a trap or timeout of the user's `cmp`) -/

def insM (cmp : α → α → Option Ordering) (x : α) : List α → Option (List α)
  | [] => some [x]
  | y :: ys => match cmp x y with
    | none => none
    | some .gt => (insM cmp x ys).map (y :: ·)
    | some _ => some (x :: y :: ys)

def isortM (cmp : α → α → Option Ordering) : List α → Option (List α)
  | [] => some []
  | x :: xs => (isortM cmp xs).bind (insM cmp x)

theorem insM_perm (cmp : α → α → Option Ordering) (x : α) :
    ∀ l r, insM cmp x l = some r → r.Perm (x :: l)
  | [], r, h => by simp [insM] at h; subst h; exact .refl _
  | y :: ys, r, h => by
    unfold insM at h
    split at h
    · cases h
    · obtain ⟨r', h', rfl⟩ := Option.map_eq_some_iff.1 h
      exact ((insM_perm cmp x ys r' h').cons y).trans (.swap x y ys)
    · cases h; exact .refl _

/-- **A failing comparator: the sort fails or returns a permutation.** -/
theorem isortM_perm (cmp : α → α → Option Ordering) : ∀ l r, isortM cmp l = some r → r.Perm l
  | [], r, h => by simp [isortM] at h; subst h; exact .refl _
  | x :: xs, r, h => by
    simp only [isortM, Option.bind_eq_some_iff] at h
    obtain ⟨s, hs, hr⟩ := h
    exact (insM_perm cmp x s r hr).trans ((isortM_perm cmp xs s hs).cons x)

/-- A comparator that never fails sorts like `isort`. -/
theorem isortM_some (cmp : α → α → Ordering) : ∀ l, isortM (fun a b => some (cmp a b)) l = some (isort cmp l)
  | [] => rfl
  | x :: xs => by
    simp only [isortM, isortM_some cmp xs, Option.bind_some, isort]
    generalize isort cmp xs = s
    induction s with
    | nil => rfl
    | cons y ys ih =>
      simp only [insM, ins]
      cases h : cmp x y <;> simp [ih]

/-! ## Maps keyed by user types -/

/-- Insert by a user Eq (as `Value.mapSet`: an equal key keeps its entry and place). -/
def mset (eq : α → α → Bool) (k : α) (v : β) : List (α × β) → List (α × β)
  | [] => [(k, v)]
  | (k', v') :: r => if eq k k' then (k', v) :: r else (k', v') :: mset eq k v r

def mget (eq : α → α → Bool) (k : α) : List (α × β) → Option β
  | [] => none
  | (k', v') :: r => if eq k k' then some v' else mget eq k r

def mbuild (eq : α → α → Bool) (M : List (α × β)) (ops : List (α × β)) : List (α × β) :=
  ops.foldl (fun m kv => mset eq kv.1 kv.2 m) M

def KeysUnique (eq : α → α → Bool) (m : List (α × β)) : Prop := m.Pairwise fun a b => eq a.1 b.1 = false

/-- Every value held or returned comes from an inserted pair, and every key too. -/
def Prov (S M : List (α × β)) : Prop := ∀ e ∈ M, (∃ k0, (k0, e.2) ∈ S) ∧ ∃ v0, (e.1, v0) ∈ S

theorem mem_mset (eq : α → α → Bool) (k : α) (v : β) :
    ∀ (m : List (α × β)) e, e ∈ mset eq k v m → e = (k, v) ∨ ((∃ w, (e.1, w) ∈ m) ∧ e.2 = v) ∨ e ∈ m
  | [], e, h => by simp [mset] at h; exact .inl h
  | (k', v') :: r, e, h => by
    unfold mset at h
    split at h
    · rcases List.mem_cons.1 h with rfl | h
      · exact .inr (.inl ⟨⟨v', .head _⟩, rfl⟩)
      · exact .inr (.inr (.tail _ h))
    · rcases List.mem_cons.1 h with rfl | h
      · exact .inr (.inr (.head _))
      · rcases mem_mset eq k v r e h with h | ⟨⟨w, hw⟩, h2⟩ | h
        · exact .inl h
        · exact .inr (.inl ⟨⟨w, .tail _ hw⟩, h2⟩)
        · exact .inr (.inr (.tail _ h))

theorem mset_length (eq : α → α → Bool) (k : α) (v : β) :
    ∀ m : List (α × β), (mset eq k v m).length ≤ m.length + 1
  | [] => by simp [mset]
  | (k', v') :: r => by
    unfold mset; split
    · simp
    · simp only [List.length_cons]; have := mset_length eq k v r; omega

/-- **Lookup after insert returns the inserted value** (a reflexive Eq). -/
theorem mget_mset_self (eq : α → α → Bool) (k : α) (v : β) (hr : eq k k = true) :
    ∀ m : List (α × β), mget eq k (mset eq k v m) = some v
  | [] => by simp [mset, mget, hr]
  | (k', v') :: r => by
    cases h : eq k k' <;> simp [mset, mget, h, mget_mset_self eq k v hr r]

/-- **Insert leaves the other keys alone** (lawful Eq). -/
theorem mget_mset_other {E : UEq α} (hE : E.Lawful) (j k : α) (v : β) (hjk : E.eq j k = false) :
    ∀ m : List (α × β), mget E.eq j (mset E.eq k v m) = mget E.eq j m
  | [] => by simp [mset, mget, hjk]
  | (k', v') :: r => by
    cases h : E.eq k k'
    · cases h2 : E.eq j k' <;> simp [mset, mget, h, h2, mget_mset_other hE j k v hjk r]
    · have h2 : E.eq j k' = false := by
        cases h3 : E.eq j k'
        · rfl
        · rw [hE.trans _ _ _ h3 (hE.symm _ _ h)] at hjk; cases hjk
      simp [mset, mget, h, h2]

theorem mget_congr {E : UEq α} (hE : E.Lawful) {j k : α} (hjk : E.eq j k = true) :
    ∀ m : List (α × β), mget E.eq j m = mget E.eq k m
  | [] => rfl
  | (k', v') :: r => by
    have e : E.eq j k' = E.eq k k' := by
      cases h1 : E.eq j k' <;> cases h2 : E.eq k k'
      · rfl
      · rw [hE.trans _ _ _ hjk h2] at h1; cases h1
      · rw [hE.trans _ _ _ (hE.symm _ _ hjk) h1] at h2; cases h2
      · rfl
    simp [mget, e, mget_congr hE hjk r]

theorem mset_unique {E : UEq α} (hE : E.Lawful) (k : α) (v : β) :
    ∀ m : List (α × β), KeysUnique E.eq m → KeysUnique E.eq (mset E.eq k v m)
  | [], _ => List.pairwise_singleton _ _
  | (k', v') :: r, h => by
    rw [KeysUnique, List.pairwise_cons] at h
    unfold mset; split
    · exact List.pairwise_cons.2 ⟨h.1, h.2⟩
    · rename_i hne
      refine List.pairwise_cons.2 ⟨fun e he => ?_, mset_unique hE k v r h.2⟩
      rcases mem_mset E.eq k v r e he with rfl | ⟨⟨w, hw⟩, _⟩ | he
      · cases h3 : E.eq k' k
        · rfl
        · exact absurd (hE.symm _ _ h3) hne
      · exact h.1 (e.1, w) hw
      · exact h.1 _ he

/-- **Keys are unique modulo the user Eq** (lawful Eq). -/
theorem mbuild_unique {E : UEq α} (hE : E.Lawful) :
    ∀ (ops M : List (α × β)), KeysUnique E.eq M → KeysUnique E.eq (mbuild E.eq M ops)
  | [], _, h => h
  | (k, v) :: ops, M, h => mbuild_unique hE ops _ (mset_unique hE k v M h)

theorem mset_prov (eq : α → α → Bool) {S M : List (α × β)} {k : α} {v : β} (hS : (k, v) ∈ S)
    (hM : Prov S M) : Prov S (mset eq k v M) := by
  intro e he
  rcases mem_mset eq k v M e he with rfl | ⟨⟨w, hw⟩, h2⟩ | he
  · exact ⟨⟨k, hS⟩, ⟨v, hS⟩⟩
  · exact ⟨⟨k, h2 ▸ hS⟩, (hM _ hw).2.elim fun v0 h => ⟨v0, h⟩⟩
  · exact hM e he

/-- **Any Eq, lawful or not: every key and value the map holds was inserted.** -/
theorem mbuild_prov (eq : α → α → Bool) (S : List (α × β)) :
    ∀ ops M, (∀ kv ∈ ops, kv ∈ S) → Prov S M → Prov S (mbuild eq M ops)
  | [], _, _, h => h
  | (_k, _v) :: ops, _, hops, h =>
    mbuild_prov eq S ops _ (fun kv hkv => hops kv (.tail _ hkv)) (mset_prov eq (hops _ (.head _)) h)

theorem mget_mem (eq : α → α → Bool) (k : α) :
    ∀ (m : List (α × β)) v, mget eq k m = some v → ∃ k', (k', v) ∈ m
  | [], _, h => by cases h
  | (k', v') :: r, v, h => by
    unfold mget at h; split at h
    · cases h; exact ⟨k', .head _⟩
    · obtain ⟨k'', h'⟩ := mget_mem eq k r v h; exact ⟨k'', .tail _ h'⟩

/-- **Any Eq: a looked-up value was inserted.** -/
theorem mget_prov (eq : α → α → Bool) (ops : List (α × β)) (k : α) (v : β)
    (h : mget eq k (mbuild eq [] ops) = some v) : ∃ k0, (k0, v) ∈ ops := by
  obtain ⟨k', hm⟩ := mget_mem eq k _ v h
  exact (mbuild_prov eq ops ops [] (fun _ h => h) (fun _ h => by cases h) _ hm).1

/-- **Any Eq: at most one entry per insertion** (nothing is duplicated). -/
theorem mbuild_length (eq : α → α → Bool) :
    ∀ (ops M : List (α × β)), (mbuild eq M ops).length ≤ M.length + ops.length
  | [], _ => by simp [mbuild]
  | (k, v) :: ops, M => by
    have h1 := mbuild_length eq ops (mset eq k v M)
    have h2 := mset_length eq k v M
    simp only [mbuild, List.foldl_cons, List.length_cons] at h1 ⊢
    omega

/-! ### The ordered map (by a user Ord) -/

def oset (cmp : α → α → Ordering) (k : α) (v : β) : List (α × β) → List (α × β)
  | [] => [(k, v)]
  | (k', v') :: r => match cmp k k' with
    | .lt => (k, v) :: (k', v') :: r
    | .eq => (k', v) :: r
    | .gt => (k', v') :: oset cmp k v r

def oget (cmp : α → α → Ordering) (k : α) : List (α × β) → Option β
  | [] => none
  | (k', v') :: r => match cmp k k' with
    | .lt => none
    | .eq => some v'
    | .gt => oget cmp k r

def obuild (cmp : α → α → Ordering) (M : List (α × β)) (ops : List (α × β)) : List (α × β) :=
  ops.foldl (fun m kv => oset cmp kv.1 kv.2 m) M

theorem mem_oset (cmp : α → α → Ordering) (k : α) (v : β) :
    ∀ (m : List (α × β)) e, e ∈ oset cmp k v m → e = (k, v) ∨ ((∃ w, (e.1, w) ∈ m) ∧ e.2 = v) ∨ e ∈ m
  | [], e, h => by simp [oset] at h; exact .inl h
  | (k', v') :: r, e, h => by
    unfold oset at h
    split at h
    · rcases List.mem_cons.1 h with rfl | h
      · exact .inl rfl
      · exact .inr (.inr h)
    · rcases List.mem_cons.1 h with rfl | h
      · exact .inr (.inl ⟨⟨v', .head _⟩, rfl⟩)
      · exact .inr (.inr (.tail _ h))
    · rcases List.mem_cons.1 h with rfl | h
      · exact .inr (.inr (.head _))
      · rcases mem_oset cmp k v r e h with h | ⟨⟨w, hw⟩, h2⟩ | h
        · exact .inl h
        · exact .inr (.inl ⟨⟨w, .tail _ hw⟩, h2⟩)
        · exact .inr (.inr (.tail _ h))

theorem oset_length (cmp : α → α → Ordering) (k : α) (v : β) :
    ∀ m : List (α × β), (oset cmp k v m).length ≤ m.length + 1
  | [] => by simp [oset]
  | (k', v') :: r => by
    unfold oset; split
    · simp
    · simp
    · simp only [List.length_cons]; have := oset_length cmp k v r; omega

/-- Strictly increasing keys. -/
def StrictSorted (cmp : α → α → Ordering) (m : List (α × β)) : Prop := m.Pairwise fun a b => cmp a.1 b.1 = .lt

theorem oset_sorted {O : UOrd α} (hO : O.Lawful) (k : α) (v : β) :
    ∀ m : List (α × β), StrictSorted O.cmp m → StrictSorted O.cmp (oset O.cmp k v m)
  | [], _ => List.pairwise_singleton _ _
  | (k', v') :: r, h => by
    rw [StrictSorted, List.pairwise_cons] at h
    unfold oset; split
    · rename_i hlt
      refine List.pairwise_cons.2 ⟨fun e he => ?_, List.pairwise_cons.2 h⟩
      rcases List.mem_cons.1 he with rfl | he
      · exact hlt
      · exact UOrd.lt_trans hO hlt (h.1 e he)
    · exact List.pairwise_cons.2 ⟨h.1, h.2⟩
    · rename_i hgt
      refine List.pairwise_cons.2 ⟨fun e he => ?_, oset_sorted hO k v r h.2⟩
      rcases mem_oset O.cmp k v r e he with rfl | ⟨⟨w, hw⟩, _⟩ | he
      · rw [hO.antisymm k k', hgt]; rfl
      · exact h.1 (e.1, w) hw
      · exact h.1 _ he

theorem oget_oset_self {O : UOrd α} (hO : O.Lawful) (k : α) (v : β) :
    ∀ m : List (α × β), oget O.cmp k (oset O.cmp k v m) = some v
  | [] => by simp [oset, oget, hO.refl]
  | (k', v') :: r => by
    cases h : O.cmp k k' <;> simp [oset, oget, h, hO.refl, oget_oset_self hO k v r]

theorem oget_oset_other {O : UOrd α} (hO : O.Lawful) (j k : α) (v : β) (hjk : O.cmp j k ≠ .eq) :
    ∀ m : List (α × β), oget O.cmp j (oset O.cmp k v m) = oget O.cmp j m
  | [] => by cases h : O.cmp j k <;> simp_all [oset, oget]
  | (k', v') :: r => by
    cases h : O.cmp k k'
    · -- (k, v) goes before k'
      cases h2 : O.cmp j k
      · simp [oset, oget, h, h2, UOrd.lt_trans hO h2 h]
      · exact absurd h2 hjk
      · simp [oset, oget, h, h2]
    · -- k' is replaced: j is not equivalent to k'
      have h2 : O.cmp j k' ≠ .eq := fun e =>
        hjk (UOrd.eq_trans hO e (by rw [hO.antisymm k k', h]; rfl))
      cases h3 : O.cmp j k' <;> simp_all [oset, oget]
    · cases h3 : O.cmp j k' <;> simp [oset, oget, h, h3, oget_oset_other hO j k v hjk r]

theorem oget_congr {O : UOrd α} (hO : O.Lawful) {j k : α} (hjk : O.cmp j k = .eq) :
    ∀ m : List (α × β), oget O.cmp j m = oget O.cmp k m
  | [] => rfl
  | (k', v') :: r => by
    simp only [oget, UOrd.cmp_congr hO hjk (hO.refl k'), oget_congr hO hjk r]

/-- **The ordered map: lookup after insert, and its iteration order** (lawful
Ord): entries are in strictly increasing key order, so keys are unique
modulo Eq (for a consistent Eq). -/
theorem obuild_sorted_unique {E : UEq α} {O : UOrd α} (hO : O.Lawful) (hc : Consistent E O) :
    ∀ (ops M : List (α × β)), StrictSorted O.cmp M →
      StrictSorted O.cmp (obuild O.cmp M ops) ∧ KeysUnique E.eq (obuild O.cmp M ops)
  | [], M, h => ⟨h, h.imp fun {a b} hab => by
      cases e : E.eq a.1 b.1
      · rfl
      · rw [(hc _ _).2 e] at hab; cases hab⟩
  | (k, v) :: ops, M, h => obuild_sorted_unique hO hc ops _ (oset_sorted hO k v M h)

theorem oset_prov (cmp : α → α → Ordering) {S M : List (α × β)} {k : α} {v : β} (hS : (k, v) ∈ S)
    (hM : Prov S M) : Prov S (oset cmp k v M) := by
  intro e he
  rcases mem_oset cmp k v M e he with rfl | ⟨⟨w, hw⟩, h2⟩ | he
  · exact ⟨⟨k, hS⟩, ⟨v, hS⟩⟩
  · exact ⟨⟨k, h2 ▸ hS⟩, (hM _ hw).2.elim fun v0 h => ⟨v0, h⟩⟩
  · exact hM e he

/-- **Any Ord: every key and value the ordered map holds was inserted.** -/
theorem obuild_prov (cmp : α → α → Ordering) (S : List (α × β)) :
    ∀ ops M, (∀ kv ∈ ops, kv ∈ S) → Prov S M → Prov S (obuild cmp M ops)
  | [], _, _, h => h
  | (_k, _v) :: ops, _, hops, h =>
    obuild_prov cmp S ops _ (fun kv hkv => hops kv (.tail _ hkv)) (oset_prov cmp (hops _ (.head _)) h)

/-- **Any Ord: at most one entry per insertion.** -/
theorem obuild_length (cmp : α → α → Ordering) :
    ∀ (ops M : List (α × β)), (obuild cmp M ops).length ≤ M.length + ops.length
  | [], _ => by simp [obuild]
  | (k, v) :: ops, M => by
    have h1 := obuild_length cmp ops (oset cmp k v M)
    have h2 := oset_length cmp k v M
    simp only [obuild, List.foldl_cons, List.length_cons] at h1 ⊢
    omega

/-- **The ordered map and the Eq map agree on every lookup** (lawful Ord, consistent Eq). -/
theorem omap_agrees {E : UEq α} {O : UOrd α} (hO : O.Lawful) (hc : Consistent E O) :
    ∀ (ops OM EM : List (α × β)), (∀ j, oget O.cmp j OM = mget E.eq j EM) →
      ∀ j, oget O.cmp j (obuild O.cmp OM ops) = mget E.eq j (mbuild E.eq EM ops)
  | [], _, _, h => h
  | (k, v) :: ops, OM, EM, h => by
    have hE := eqLawful_of_ord hO hc
    apply omap_agrees hO hc ops
    intro j
    by_cases hjk : O.cmp j k = .eq
    · rw [oget_congr hO hjk, oget_oset_self hO, mget_congr hE ((hc j k).1 hjk),
        mget_mset_self _ _ _ (hE.refl k)]
    · have : E.eq j k = false := by
        cases e : E.eq j k
        · rfl
        · exact absurd ((hc j k).2 e) hjk
      rw [oget_oset_other hO j k v hjk, mget_mset_other hE j k v this, h j]

/-! ### The hashed map (buckets by a user Hash, entries by a user Eq) -/

abbrev Buckets (α β : Type) := Nat → List (α × β)

def hset (eq : α → α → Bool) (bk : α → Nat) (k : α) (v : β) (B : Buckets α β) : Buckets α β :=
  fun i => if i = bk k then mset eq k v (B i) else B i

def hget (eq : α → α → Bool) (bk : α → Nat) (k : α) (B : Buckets α β) : Option β := mget eq k (B (bk k))

def hbuild (eq : α → α → Bool) (bk : α → Nat) (B : Buckets α β) (ops : List (α × β)) : Buckets α β :=
  ops.foldl (fun b kv => hset eq bk kv.1 kv.2 b) B

/-- **The hashed map and the Eq map agree on every lookup** (lawful Eq and Hash). -/
theorem hmap_agrees {E : UEq α} (hE : E.Lawful) {bk : α → Nat} (hH : BucketLawful E bk) :
    ∀ (ops : List (α × β)) (B : Buckets α β) (M : List (α × β)), (∀ j, hget E.eq bk j B = mget E.eq j M) →
      ∀ j, hget E.eq bk j (hbuild E.eq bk B ops) = mget E.eq j (mbuild E.eq M ops)
  | [], _, _, h => h
  | (k, v) :: ops, B, M, h => by
    apply hmap_agrees hE hH ops
    intro j
    simp only [hget, hset]
    cases hjk : E.eq j k
    · rw [mget_mset_other hE j k v hjk]
      split
      · rw [mget_mset_other hE j k v hjk]; exact h j
      · exact h j
    · simp only [hH j k hjk, ↓reduceIte]
      rw [mget_congr hE hjk, mget_mset_self _ _ _ (hE.refl k),
        mget_congr hE hjk, mget_mset_self _ _ _ (hE.refl k)]

/-- The bucket invariant: each bucket has unique keys, all of which belong to it. -/
def BucketsOk (eq : α → α → Bool) (bk : α → Nat) (B : Buckets α β) : Prop :=
  ∀ i, KeysUnique eq (B i) ∧ ∀ e ∈ B i, bk e.1 = i

theorem hbuild_ok {E : UEq α} (hE : E.Lawful) (bk : α → Nat) :
    ∀ (ops : List (α × β)) B, BucketsOk E.eq bk B → BucketsOk E.eq bk (hbuild E.eq bk B ops)
  | [], _, h => h
  | (k, v) :: ops, B, h => by
    apply hbuild_ok hE bk ops
    intro i
    simp only [hset]
    split
    · rename_i hi
      refine ⟨mset_unique hE k v _ (h i).1, fun e he => ?_⟩
      rcases mem_mset E.eq k v _ e he with rfl | ⟨⟨w, hw⟩, _⟩ | he
      · exact hi.symm
      · exact (h i).2 (e.1, w) hw
      · exact (h i).2 _ he
    · exact h i

/-- **Keys of the hashed map are unique modulo Eq**, across all buckets (lawful Eq and Hash). -/
theorem hbuild_unique {E : UEq α} (hE : E.Lawful) {bk : α → Nat} (hH : BucketLawful E bk)
    (ops : List (α × β)) {i j : Nat} {e1 e2 : α × β}
    (h1 : e1 ∈ hbuild E.eq bk (fun _ => []) ops i) (h2 : e2 ∈ hbuild E.eq bk (fun _ => []) ops j)
    (he : E.eq e1.1 e2.1 = true) : i = j := by
  have hok := hbuild_ok hE bk ops (fun _ => []) (fun _ => ⟨.nil, fun _ h => by cases h⟩)
  rw [← (hok i).2 e1 h1, ← (hok j).2 e2 h2]
  exact hH _ _ he

/-- **Any Eq and Hash: every key and value the hashed map holds was inserted.** -/
theorem hbuild_prov (eq : α → α → Bool) (bk : α → Nat) (S : List (α × β)) :
    ∀ ops (B : Buckets α β), (∀ kv ∈ ops, kv ∈ S) → (∀ i, Prov S (B i)) →
      ∀ i, Prov S (hbuild eq bk B ops i)
  | [], _, _, h => h
  | (k, v) :: ops, B, hops, h => by
    apply hbuild_prov eq bk S ops _ (fun kv hkv => hops kv (.tail _ hkv))
    intro i
    simp only [hset]
    split
    · exact mset_prov eq (hops _ (.head _)) (h i)
    · exact h i

/-! ## User impls are core functions: the guarded theorems apply -/

/-- Call a two-argument core function (a user `eq` or `cmp` method) on two values. -/
def coreCall2 (P : Prog) (n : Nat) (f : String) (a b : Val) : Out Val :=
  eval P n [("a", some a), ("b", some b)] {} (.call (.fnref f) [.place "a" [], .place "b" []])

/-- A user comparator run in the core: the result decoded (`dec`, the
representation of Ordering item 3 picks), a trap, a stuck state or running
out of fuel give `none`. -/
def coreCmp (P : Prog) (n : Nat) (f : String) (dec : Val → Option Ordering) (a b : Val) : Option Ordering :=
  match coreCall2 P n f a b with
  | .ok v _ _ => dec v
  | _ => none

/-- **Sorting with an arbitrary user `cmp` body** (any impls, any fuel): the
sort fails or returns a permutation of its input. -/
theorem user_sort_perm (P : Prog) (E : TraitEnv) (n : Nat) (f : String) (dec : Val → Option Ordering)
    (l r : List Val) (h : isortM (coreCmp (withImpls P E) n f dec) l = some r) : r.Perm l :=
  isortM_perm _ l r h

/-- **A user impl obtains no authority**: whatever the bodies of the impls of
`E`, on arguments without capabilities a call of a user `eq`/`cmp`/`hash`
performs no effect. -/
theorem user_impl_no_effects (P : Prog) (E : TraitEnv) (n : Nat) (f : String) (a b : Val)
    (ha : a.caps = []) (hb : b.caps = []) :
    match coreCall2 (withImpls P E) n f a b with
    | .ok _ _ st' | .ctl _ _ st' | .err (.trap _ st') => st'.out = []
    | .err _ => True := by
  have h := Tenon.no_authority_escalation (withImpls P E) [] n [("a", some a), ("b", some b)]
    (.call (.fnref f) [.place "a" [], .place "b" []]) (by simp [envCaps, ha, hb])
  unfold coreCall2
  revert h
  generalize eval (withImpls P E) n _ {} _ = r
  intro h
  have nil : ∀ l : List Event, (∀ ev ∈ l, ∃ c ∈ ([] : List Cap), ev.cap ≤ c) → l = [] := by
    intro l hl
    cases l with
    | nil => rfl
    | cons ev _ => obtain ⟨_, hc, _⟩ := hl ev (.head _); cases hc
  rcases r with ⟨_, _, st⟩ | ⟨_, _, st⟩ | ⟨_ | _ | _ | _⟩ <;> first | exact nil _ h | trivial

/-- **Capability safety for programs with arbitrary user impls**: the guarded
theorem, for the program the impls elaborate to. -/
theorem user_impls_capability_safe (P : Prog) (E : TraitEnv) (A : List Cap) (n : Nat) (ρ : Env) (st : St)
    (e : Expr) (hρ : ∀ c ∈ envCaps ρ, ∃ a ∈ A, c ≤ a) (hst : ∀ ev ∈ st.out, ∃ a ∈ A, ev.cap ≤ a) :
    match eval (withImpls P E) n ρ st e with
    | .ok v ρ' st' =>
      (∀ c ∈ v.caps, ∃ a ∈ A, c ≤ a) ∧ (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧
      (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .ctl _ ρ' st' => (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧ (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  Tenon.capability_safety (withImpls P E) A n ρ st e hρ hst

/-- **Obligation conservation for programs with arbitrary user impls.** -/
theorem user_impls_obligations_conserved (P : Prog) (E : TraitEnv) (n : Nat) (ρ : Env) (st : St)
    (e : Expr) (hs : StOk st) :
    match eval (withImpls P E) n ρ st e with
    | .ok v ρ' st' => Bal v.toks ρ' st' [] ρ st ∧ StOk st'
    | .ctl c ρ' st' => Bal (ctlToks c) ρ' st' [] ρ st ∧ StOk st'
    | .err _ => True :=
  Tenon.obligations_conserved (withImpls P E) n ρ st e hs

/-! ## Supertraits of the prelude: `Ord: Eq`, `Hash: Eq` -/

/-- A bound `T: Ord` gives `T: Eq` at every instantiation (`Ord`'s supertrait). -/
theorem ord_bound_gives_eq {E : TraitEnv} (hS : SuperOk E) {T : TraitDecl}
    (hTr : E.trait "Ord" = some T) (hlen : T.tparams = 0) (hs : ("Eq", []) ∈ T.supers)
    {t : Ty} (h : Holds E "Ord" [] t) : Holds E "Eq" [] t := by
  simpa using hS "Ord" [] t T h hTr hlen.symm _ hs

/-- A bound `T: Hash` gives `T: Eq` (`Hash`'s supertrait). -/
theorem hash_bound_gives_eq {E : TraitEnv} (hS : SuperOk E) {T : TraitDecl}
    (hTr : E.trait "Hash" = some T) (hlen : T.tparams = 0) (hs : ("Eq", []) ∈ T.supers)
    {t : Ty} (h : Holds E "Hash" [] t) : Holds E "Eq" [] t := by
  simpa using hS "Hash" [] t T h hTr hlen.symm _ hs

end Tenon.TypeGaps

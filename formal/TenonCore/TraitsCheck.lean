/-
Coherence, decided (tenon.md §6; reference §17): a decidable overlap check
for impls, proved sound against `Traits.Coherent`, and the orphan rule, with
the theorem that makes coherence modular: if every impl is in the module of
its trait or of its type's head, and each module checks its impls against
the impls of the modules it sees (its trait's and its type's, at least),
then the impls of the whole program are coherent (`orphan_coherent`).

The overlap check is first-order: two impl patterns (renamed apart) cannot
overlap when they clash, a position where both have different type
constructors (`clash`). It is sound (`clash_sound`: a clash means no
instance of one is an instance of the other) and conservative: two patterns
that repeat a type variable (`Pair[T, T]` against `Pair[Int, Str]`) are
reported as overlapping although no type is an instance of both.
-/
import TenonCore.Traits

namespace Tenon.Traits
open Tenon

/-! ## Clashes -/

mutual
/-- The two patterns have different type constructors at some position (variables match anything). -/
def clash : Ty → Ty → Bool
  | .var _, _ | _, .var _ => false
  | .int, .int | .bool, .bool | .str, .str | .unit, .unit => false
  | .tup as, .tup bs => clashL as bs
  | .list a, .list b => clash a b
  | .map k v, .map k' v' => clash k k' || clash v v'
  | .adt s as, .adt t bs => s != t || clashL as bs
  | .fn ps r, .fn qs q => clashL ps qs || clash r q
  | .cap k, .cap k' => k != k'
  | _, _ => true
def clashL : List Ty → List Ty → Bool
  | [], [] => false
  | a :: as, b :: bs => clash a b || clashL as bs
  | _, _ => true
end

mutual
theorem clash_sound : ∀ (a b : Ty), clash a b = true → ∀ σ1 σ2, tsub σ1 a ≠ tsub σ2 b
  | .var _, _, h, _, _ => by simp [clash] at h
  | .int, .var _, h, _, _ | .bool, .var _, h, _, _ | .str, .var _, h, _, _ | .unit, .var _, h, _, _
  | .tup _, .var _, h, _, _ | .list _, .var _, h, _, _ | .map _ _, .var _, h, _, _ | .adt _ _, .var _, h, _, _
  | .fn _ _, .var _, h, _, _ | .cap _, .var _, h, _, _ => by simp [clash] at h
  | .tup as, .tup bs, h, σ1, σ2 => by
    simp only [clash] at h
    intro he; simp only [tsub, Ty.tup.injEq] at he
    exact clashL_sound as bs h σ1 σ2 he
  | .list a, .list b, h, σ1, σ2 => by
    simp only [clash] at h
    intro he; simp only [tsub, Ty.list.injEq] at he
    exact clash_sound a b h σ1 σ2 he
  | .map k v, .map k' v', h, σ1, σ2 => by
    simp only [clash, Bool.or_eq_true] at h
    intro he; simp only [tsub, Ty.map.injEq] at he
    rcases h with h | h
    · exact clash_sound k k' h σ1 σ2 he.1
    · exact clash_sound v v' h σ1 σ2 he.2
  | .adt s as, .adt t bs, h, σ1, σ2 => by
    simp only [clash, Bool.or_eq_true, bne_iff_ne, ne_eq] at h
    intro he; simp only [tsub, Ty.adt.injEq] at he
    rcases h with h | h
    · exact h he.1
    · exact clashL_sound as bs h σ1 σ2 he.2
  | .fn ps r, .fn qs q, h, σ1, σ2 => by
    simp only [clash, Bool.or_eq_true] at h
    intro he; simp only [tsub, Ty.fn.injEq] at he
    rcases h with h | h
    · exact clashL_sound ps qs h σ1 σ2 he.1
    · exact clash_sound r q h σ1 σ2 he.2
  | .cap k, .cap k', h, σ1, σ2 => by
    simp only [clash, bne_iff_ne, ne_eq] at h
    intro he; simp only [tsub, Ty.cap.injEq] at he
    exact h he
  | .int, .int, h, _, _ | .bool, .bool, h, _, _ | .str, .str, h, _, _ | .unit, .unit, h, _, _ => by
    simp [clash] at h
  | .int, .bool, _, _, _ | .int, .str, _, _, _ | .int, .unit, _, _, _ | .int, .tup _, _, _, _
  | .int, .list _, _, _, _ | .int, .map _ _, _, _, _ | .int, .adt _ _, _, _, _ | .int, .fn _ _, _, _, _
  | .int, .cap _, _, _, _ => by simp [tsub]
  | .bool, .int, _, _, _ | .bool, .str, _, _, _ | .bool, .unit, _, _, _ | .bool, .tup _, _, _, _
  | .bool, .list _, _, _, _ | .bool, .map _ _, _, _, _ | .bool, .adt _ _, _, _, _ | .bool, .fn _ _, _, _, _
  | .bool, .cap _, _, _, _ => by simp [tsub]
  | .str, .int, _, _, _ | .str, .bool, _, _, _ | .str, .unit, _, _, _ | .str, .tup _, _, _, _
  | .str, .list _, _, _, _ | .str, .map _ _, _, _, _ | .str, .adt _ _, _, _, _ | .str, .fn _ _, _, _, _
  | .str, .cap _, _, _, _ => by simp [tsub]
  | .unit, .int, _, _, _ | .unit, .bool, _, _, _ | .unit, .str, _, _, _ | .unit, .tup _, _, _, _
  | .unit, .list _, _, _, _ | .unit, .map _ _, _, _, _ | .unit, .adt _ _, _, _, _ | .unit, .fn _ _, _, _, _
  | .unit, .cap _, _, _, _ => by simp [tsub]
  | .tup _, .int, _, _, _ | .tup _, .bool, _, _, _ | .tup _, .str, _, _, _ | .tup _, .unit, _, _, _
  | .tup _, .list _, _, _, _ | .tup _, .map _ _, _, _, _ | .tup _, .adt _ _, _, _, _ | .tup _, .fn _ _, _, _, _
  | .tup _, .cap _, _, _, _ => by simp [tsub]
  | .list _, .int, _, _, _ | .list _, .bool, _, _, _ | .list _, .str, _, _, _ | .list _, .unit, _, _, _
  | .list _, .tup _, _, _, _ | .list _, .map _ _, _, _, _ | .list _, .adt _ _, _, _, _ | .list _, .fn _ _, _, _, _
  | .list _, .cap _, _, _, _ => by simp [tsub]
  | .map _ _, .int, _, _, _ | .map _ _, .bool, _, _, _ | .map _ _, .str, _, _, _ | .map _ _, .unit, _, _, _
  | .map _ _, .tup _, _, _, _ | .map _ _, .list _, _, _, _ | .map _ _, .adt _ _, _, _, _
  | .map _ _, .fn _ _, _, _, _ | .map _ _, .cap _, _, _, _ => by simp [tsub]
  | .adt _ _, .int, _, _, _ | .adt _ _, .bool, _, _, _ | .adt _ _, .str, _, _, _ | .adt _ _, .unit, _, _, _
  | .adt _ _, .tup _, _, _, _ | .adt _ _, .list _, _, _, _ | .adt _ _, .map _ _, _, _, _
  | .adt _ _, .fn _ _, _, _, _ | .adt _ _, .cap _, _, _, _ => by simp [tsub]
  | .fn _ _, .int, _, _, _ | .fn _ _, .bool, _, _, _ | .fn _ _, .str, _, _, _ | .fn _ _, .unit, _, _, _
  | .fn _ _, .tup _, _, _, _ | .fn _ _, .list _, _, _, _ | .fn _ _, .map _ _, _, _, _
  | .fn _ _, .adt _ _, _, _, _ | .fn _ _, .cap _, _, _, _ => by simp [tsub]
  | .cap _, .int, _, _, _ | .cap _, .bool, _, _, _ | .cap _, .str, _, _, _ | .cap _, .unit, _, _, _
  | .cap _, .tup _, _, _, _ | .cap _, .list _, _, _, _ | .cap _, .map _ _, _, _, _
  | .cap _, .adt _ _, _, _, _ | .cap _, .fn _ _, _, _, _ => by simp [tsub]
theorem clashL_sound : ∀ (as bs : List Ty), clashL as bs = true → ∀ σ1 σ2, tsubL σ1 as ≠ tsubL σ2 bs
  | [], [], h, _, _ => by simp [clashL] at h
  | a :: as, b :: bs, h, σ1, σ2 => by
    simp only [clashL, Bool.or_eq_true] at h
    intro he; simp only [tsubL, List.cons.injEq] at he
    rcases h with h | h
    · exact clash_sound a b h σ1 σ2 he.1
    · exact clashL_sound as bs h σ1 σ2 he.2
  | [], _ :: _, _, _, _ | _ :: _, [], _, _, _ => by simp [tsubL]
end

/-! ## The overlap check -/

/-- Two impls cannot overlap: their type patterns or their trait arguments clash. -/
def disjointB (a b : ImplDecl) : Bool := clash a.self b.self || clashL a.targs b.targs

theorem disjointB_sound {a b : ImplDecl} (h : disjointB a b = true) : ¬ Overlap a b := by
  rintro ⟨σ1, σ2, h1, h2⟩
  simp only [disjointB, Bool.or_eq_true] at h
  rcases h with h | h
  · exact clash_sound _ _ h σ1 σ2 h1
  · apply clashL_sound _ _ h σ1 σ2
    rw [tsubL_eq_map, tsubL_eq_map]; exact h2

/-- **The overlap check**, decidable: every two impls of one trait are disjoint. -/
def coherentB : List ImplDecl → Bool
  | [] => true
  | a :: rest => rest.all (fun b => a.trait != b.trait || disjointB a b) && coherentB rest

theorem coherentB_sound {E : TraitEnv} (h : coherentB E.impls = true) : Coherent E := by
  unfold Coherent
  generalize E.impls = l at h
  induction l with
  | nil => exact .nil
  | cons a rest ih =>
    simp only [coherentB, Bool.and_eq_true, List.all_eq_true, Bool.or_eq_true, bne_iff_ne, ne_eq] at h
    refine .cons (fun b hb ht => ?_) (ih h.2)
    rcases h.1 b hb with h1 | h1
    · exact (h1 ht).elim
    · exact disjointB_sound h1

/-! ## The orphan rule -/

/-- An impl and the module it is written in. -/
structure ModImpl where
  mod : String
  im : ImplDecl

/-- The orphan rule: an impl is in the module of its trait or of its type's head. -/
def orphanOk (traitMod typeMod : String → Option String) (mi : ModImpl) : Prop :=
  traitMod mi.im.trait = some mi.mod ∨ typeMod mi.im.self.head = some mi.mod

theorem overlap_symm {a b : ImplDecl} (h : Overlap a b) : Overlap b a := by
  obtain ⟨σ1, σ2, h1, h2⟩ := h
  exact ⟨σ2, σ1, h1.symm, h2.symm⟩

theorem overlap_head {a b : ImplDecl} (ha : isVar a.self = false) (hb : isVar b.self = false) (h : Overlap a b) :
    a.self.head = b.self.head := by
  obtain ⟨σ1, σ2, h1, -⟩ := h
  rw [← head_tsub σ1 a.self ha, ← head_tsub σ2 b.self hb, h1]

/-- **Coherence is modular under the orphan rule**: if no impl's type is a bare
variable, every impl obeys the orphan rule, every module sees the modules of
the traits and types of its impls, and every module checked its impls against
the impls of the modules it sees (`hloc`, which `disjointB` decides), then no
two impls of the program overlap: `Coherent`. -/
theorem orphan_coherent (traits : List TraitDecl) (impls : List ModImpl) (traitMod typeMod : String → Option String)
    (sees : String → String → Prop)
    (hvar : ∀ mi ∈ impls, isVar mi.im.self = false)
    (horph : ∀ mi ∈ impls, orphanOk traitMod typeMod mi)
    (hvis : ∀ mi ∈ impls, (∀ m, traitMod mi.im.trait = some m → sees mi.mod m) ∧
      (∀ m, typeMod mi.im.self.head = some m → sees mi.mod m))
    (hloc : ∀ (i j : Nat) (hi : i < impls.length) (hj : j < impls.length), i ≠ j →
      sees impls[i].mod impls[j].mod → impls[i].im.trait = impls[j].im.trait → ¬ Overlap impls[i].im impls[j].im) :
    Coherent ⟨traits, impls.map (·.im)⟩ := by
  unfold Coherent
  simp only
  rw [List.pairwise_iff_getElem]
  intro i j hi hj hij ht hov
  simp only [List.length_map] at hi hj
  simp only [List.getElem_map] at ht hov
  have mi := List.getElem_mem hi
  have mj := List.getElem_mem hj
  have hh := overlap_head (hvar _ mi) (hvar _ mj) hov
  -- the second impl's module sees the first's
  have hs : sees impls[j].mod impls[i].mod := by
    rcases horph _ mi with h | h
    · exact (hvis _ mj).1 _ (by rw [← ht]; exact h)
    · exact (hvis _ mj).2 _ (by rw [← hh]; exact h)
  exact hloc j i hj hi (by omega) hs ht.symm (overlap_symm hov)

/-- The local check of one module, decidable: each of its impls against every
other impl of a module it sees. -/
def localB (sees : String → String → Bool) (impls : List ModImpl) : Bool :=
  (List.range impls.length).all fun i => (List.range impls.length).all fun j =>
    match impls[i]?, impls[j]? with
    | some a, some b => i == j || !sees a.mod b.mod || a.im.trait != b.im.trait || disjointB a.im b.im
    | _, _ => true

theorem localB_sound {sees : String → String → Bool} {impls : List ModImpl} (h : localB sees impls = true) :
    ∀ (i j : Nat) (hi : i < impls.length) (hj : j < impls.length), i ≠ j →
      sees impls[i].mod impls[j].mod = true → impls[i].im.trait = impls[j].im.trait → ¬ Overlap impls[i].im impls[j].im := by
  intro i j hi hj hij hs ht
  have := List.all_eq_true.1 (List.all_eq_true.1 h i (List.mem_range.2 hi)) j (List.mem_range.2 hj)
  simp only [List.getElem?_eq_getElem hi, List.getElem?_eq_getElem hj, Bool.or_eq_true, beq_iff_eq,
    Bool.not_eq_true', bne_iff_ne, ne_eq] at this
  rcases this with ((h1 | h1) | h1) | h1
  · exact (hij h1).elim
  · rw [hs] at h1; cases h1
  · exact (h1 ht).elim
  · exact disjointB_sound h1

/-- The decided form: the orphan rule (decided) and the local checks give coherence. -/
theorem orphan_coherent_decided (traits : List TraitDecl) (impls : List ModImpl) (traitMod typeMod : String → Option String)
    (sees : String → String → Bool)
    (hvar : ∀ mi ∈ impls, isVar mi.im.self = false)
    (horph : impls.all (fun mi => traitMod mi.im.trait == some mi.mod || typeMod mi.im.self.head == some mi.mod) = true)
    (hvis : ∀ mi ∈ impls, (∀ m, traitMod mi.im.trait = some m → sees mi.mod m = true) ∧
      (∀ m, typeMod mi.im.self.head = some m → sees mi.mod m = true))
    (hloc : localB sees impls = true) :
    Coherent ⟨traits, impls.map (·.im)⟩ :=
  orphan_coherent traits impls traitMod typeMod (fun a b => sees a b = true) hvar
    (fun mi hm => by
      have := List.all_eq_true.1 horph mi hm
      simp only [Bool.or_eq_true, beq_iff_eq] at this
      exact this)
    hvis (localB_sound hloc)

end Tenon.Traits

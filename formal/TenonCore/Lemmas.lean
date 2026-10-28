/-
Facts about values, environments, paths and patterns shared by the proofs.
-/
import TenonCore.Eval

namespace Tenon

/-! ## Lists of capabilities and tokens -/

theorem mem_capsL {c : Cap} : ∀ {vs : List Val}, c ∈ capsL vs ↔ ∃ v ∈ vs, c ∈ v.caps
  | [] => by simp [capsL]
  | v :: vs => by simp [capsL, mem_capsL]

theorem capsL_append (a b : List Val) : capsL (a ++ b) = capsL a ++ capsL b := by
  induction a with
  | nil => simp [capsL]
  | cons v vs ih => simp [capsL, ih]

theorem sub_app {α} {a b c d : List α} (h1 : a ⊆ c) (h2 : b ⊆ d) : a ++ b ⊆ c ++ d := by
  intro x hx
  simp only [List.mem_append] at hx ⊢
  rcases hx with h | h
  · exact Or.inl (h1 h)
  · exact Or.inr (h2 h)

theorem caps_sub_capsL {v : Val} {vs : List Val} (h : v ∈ vs) : v.caps ⊆ capsL vs :=
  fun _ hc => mem_capsL.2 ⟨v, h, hc⟩

theorem capsL_sub {vs ws : List Val} (h : ∀ v ∈ vs, v.caps ⊆ capsL ws) : capsL vs ⊆ capsL ws := by
  intro c hc
  obtain ⟨v, hv, hcv⟩ := mem_capsL.1 hc
  exact h v hv hcv

theorem capsL_set (vs : List Val) (i : Nat) (w : Val) : capsL (vs.set i w) ⊆ capsL vs ++ w.caps := by
  intro c hc
  obtain ⟨v, hv, hcv⟩ := mem_capsL.1 hc
  rcases List.mem_or_eq_of_mem_set hv with h | h
  · exact List.mem_append_left _ (mem_capsL.2 ⟨v, h, hcv⟩)
  · subst h; exact List.mem_append_right _ hcv

theorem caps_getElem? {vs : List Val} {i : Nat} {v : Val} (h : vs[i]? = some v) : v.caps ⊆ capsL vs :=
  caps_sub_capsL (List.mem_of_getElem? h)

/-! ## Environments -/

theorem envCaps_cons_some (x : String) (v : Val) (ρ : Env) : envCaps ((x, some v) :: ρ) = v.caps ++ envCaps ρ := rfl
theorem envCaps_cons_none (x : String) (ρ : Env) : envCaps ((x, none) :: ρ) = envCaps ρ := rfl

def slotCaps : Option Val → List Cap
  | some v => v.caps
  | none => []

theorem envCaps_cons (x : String) (s : Option Val) (ρ : Env) : envCaps ((x, s) :: ρ) = slotCaps s ++ envCaps ρ := by
  cases s <;> rfl

theorem envCaps_append (a b : Env) : envCaps (a ++ b) = envCaps a ++ envCaps b := by
  induction a with
  | nil => rfl
  | cons p a ih => obtain ⟨x, s⟩ := p; simp [envCaps_cons, ih]

theorem lookup_caps : ∀ {ρ : Env} {x : String} {v : Val}, lookup ρ x = some (some v) → v.caps ⊆ envCaps ρ
  | [], _, _, h => by simp [lookup] at h
  | (y, s) :: ρ, x, v, h => by
    simp only [lookup] at h
    split at h
    · cases h; simp [envCaps_cons, slotCaps]
    · rw [envCaps_cons]; exact List.subset_append_of_subset_right _ (lookup_caps h)

theorem update_caps : ∀ (ρ : Env) (x : String) (s : Option Val), envCaps (update ρ x s) ⊆ envCaps ρ ++ slotCaps s
  | [], _, _ => by simp [update, envCaps]
  | (y, t) :: ρ, x, s => by
    have ih := update_caps ρ x s
    simp only [update]
    split
    · rw [envCaps_cons, envCaps_cons]; grind
    · rw [envCaps_cons, envCaps_cons]; grind

theorem drop_caps : ∀ (k : Nat) (ρ : Env), envCaps (ρ.drop k) ⊆ envCaps ρ
  | 0, _ => fun _ h => h
  | _ + 1, [] => fun _ h => h
  | k + 1, (x, s) :: ρ => by
    simp only [List.drop_succ_cons]
    rw [envCaps_cons]
    exact List.subset_append_of_subset_right _ (drop_caps k ρ)

theorem pushBinds_caps (bs : List (String × Val)) (ρ : Env) :
    envCaps (pushBinds bs ρ) = capsL (bs.map (·.2)) ++ envCaps ρ := by
  induction bs with
  | nil => simp [pushBinds, capsL]
  | cons b bs ih =>
    obtain ⟨x, v⟩ := b
    simp only [pushBinds, List.map_cons, List.cons_append] at ih ⊢
    rw [envCaps_cons, ih]
    simp [slotCaps, capsL]

theorem capture_caps : ∀ (ρ : Env), capsL ((capture ρ).map (·.2)) ⊆ envCaps ρ
  | [] => by simp [capture, capsL]
  | (x, s) :: ρ => by
    have ih := capture_caps ρ
    unfold capture at ih ⊢
    cases s with
    | none => simp only [List.filterMap_cons]; rw [envCaps_cons]; grind
    | some v =>
      rw [envCaps_cons]
      by_cases hv : v.toks = []
      · simp only [List.filterMap_cons, hv, if_true, List.map_cons, capsL, slotCaps]; grind
      · simp only [List.filterMap_cons, hv, if_false, slotCaps]; grind

/-! ## Paths -/

theorem entryKV_caps {e k v : Val} (h : entryKV e = some (k, v)) : k.caps ++ v.caps ⊆ e.caps := by
  unfold entryKV at h
  split at h
  · cases h; simp [Val.caps, capsL]
  · cases h

theorem mapGet_caps (k : Val) : ∀ {kvs : List Val} {v : Val}, mapGet k kvs = some v → v.caps ⊆ capsL kvs
  | [], _, h => by simp [mapGet] at h
  | e :: r, v, h => by
    have ih := @mapGet_caps k r v
    simp only [mapGet] at h
    simp only [capsL]
    split at h
    · rename_i k' w he
      have := entryKV_caps he
      split at h
      · cases h; grind
      · grind
    · grind

theorem mapSet_caps (k w : Val) : ∀ (kvs : List Val), capsL (mapSet k w kvs) ⊆ capsL kvs ++ k.caps ++ w.caps
  | [] => by simp [mapSet, capsL, Val.caps]
  | e :: r => by
    have ih := mapSet_caps k w r
    simp only [mapSet]
    split
    · rename_i k' w' he
      have := entryKV_caps he
      split
      · simp only [capsL, Val.caps]; grind
      · simp only [capsL]; grind
    · simp only [capsL]; grind

theorem getStep_caps (P : Prog) {v w : Val} {s : Step} (h : getStep P v s = .ok w) : w.caps ⊆ v.caps := by
  unfold getStep at h
  split at h <;> (repeat' split at h) <;> simp only [Except.ok.injEq, reduceCtorEq] at h <;> subst h <;>
    simp only [Val.caps] <;>
    first
    | exact caps_getElem? (by assumption)
    | exact caps_sub_capsL (List.getElem_mem _)
    | exact mapGet_caps _ (by assumption)

theorem getPath_caps (P : Prog) : ∀ {v w : Val} {ss : List Step}, getPath P v ss = .ok w → w.caps ⊆ v.caps
  | v, w, [], h => by simp only [getPath, Except.ok.injEq] at h; subst h; exact fun _ h => h
  | v, w, s :: ss, h => by
    simp only [getPath] at h
    split at h
    · exact List.Subset.trans (getPath_caps P h) (getStep_caps P (by assumption))
    · cases h

def stepCaps : Step → List Cap
  | .idx k => k.caps
  | _ => []

def stepsCaps : List Step → List Cap
  | [] => []
  | s :: ss => stepCaps s ++ stepsCaps ss

theorem setStep_caps (P : Prog) {v w r : Val} {s : Step} (h : setStep P v s w = .ok r) :
    r.caps ⊆ v.caps ++ w.caps ++ stepCaps s := by
  have hs := capsL_set
  have hm := mapSet_caps
  unfold setStep at h
  split at h <;> (repeat' split at h) <;> simp only [Except.ok.injEq, reduceCtorEq] at h <;> subst h <;>
    simp only [Val.caps, stepCaps] <;> grind

theorem setPath_caps (P : Prog) : ∀ {v w r : Val} {ss : List Step}, setPath P v ss w = .ok r →
    r.caps ⊆ v.caps ++ w.caps ++ stepsCaps ss
  | v, w, r, [], h => by
    simp only [setPath, Except.ok.injEq] at h; subst h; intro c hc; simp [hc]
  | v, w, r, [s], h => by
    simp only [setPath] at h
    have := setStep_caps P h
    simp only [stepsCaps]; grind
  | v, w, r, s :: s2 :: ss, h => by
    simp only [setPath] at h
    split at h
    · rename_i c hc
      split at h
      · rename_i c' hc'
        have h1 := setStep_caps P h
        have h2 := setPath_caps P hc'
        have h3 := getStep_caps P hc
        simp only [stepsCaps] at h2 ⊢
        intro x hx
        have a := h1 hx
        simp only [List.mem_append] at a ⊢
        rcases a with (a | a) | a
        · exact Or.inl (Or.inl a)
        · have b := h2 a
          simp only [List.mem_append] at b
          rcases b with (b | b) | b
          · exact Or.inl (Or.inl (h3 b))
          · exact Or.inl (Or.inr b)
          · exact Or.inr (Or.inr b)
        · exact Or.inr (Or.inl a)
      · cases h
    · cases h

theorem oldAt_caps (P : Prog) : ∀ {v : Val} {ss : List Step} {w : Val}, oldAt P v ss = .ok (some w) → w.caps ⊆ v.caps
  | v, [], w, h => by simp only [oldAt, Except.ok.injEq, Option.some.injEq] at h; subst h; exact fun _ h => h
  | v, [s], w, h => by
    simp only [oldAt] at h
    split at h
    · simp only [Except.ok.injEq] at h; simp only [Val.caps]; exact mapGet_caps _ h
    · cases hg : getStep P v s with
      | ok u => rw [hg] at h; simp only [Except.map, Except.ok.injEq, Option.some.injEq] at h; subst h; exact getStep_caps P hg
      | error e => rw [hg] at h; cases h
  | v, s :: s2 :: ss, w, h => by
    simp only [oldAt] at h
    split at h
    · exact List.Subset.trans (oldAt_caps P h) (getStep_caps P (by assumption))
    · cases h

/-! ## Patterns -/

mutual
theorem matchPat_caps (P : Prog) : ∀ (p : Pat) (v : Val) {bs bu dr}, matchPat P p v = .ok bs bu dr →
    capsL (bs.map (·.2)) ⊆ v.caps
  | .wild, v, bs, bu, dr, h => by simp [matchPat] at h; obtain ⟨rfl, -, -⟩ := h; simp [capsL]
  | .bind x, v, bs, bu, dr, h => by simp [matchPat] at h; obtain ⟨rfl, -, -⟩ := h; simp [capsL]
  | .lit l, v, bs, bu, dr, h => by
    simp only [matchPat] at h
    unfold litMatch at h
    split at h <;> (try split at h) <;> simp_all [capsL]
  | .tup ps, .seq .tup vs, bs, bu, dr, h => by
    simp only [matchPat] at h
    simp only [Val.caps]; exact matchList_caps P ps vs h
  | .tup _, .int _, _, _, _, h | .tup _, .bool _, _, _, _, h | .tup _, .str _, _, _, _, h
  | .tup _, .unit, _, _, _, h | .tup _, .seq .list _, _, _, _, h | .tup _, .seq .map _, _, _, _, h
  | .tup _, .adt .., _, _, _, h | .tup _, .clo .., _, _, _, h | .tup _, .fn _, _, _, _, h
  | .tup _, .cap _, _, _, _, h => by simp [matchPat] at h
  | .con c ps, .adt s tag tok vs, bs, bu, dr, h => by
    simp only [matchPat] at h
    split at h
    · split at h
      · split at h
        · cases h; simp only [Val.caps]; exact matchList_caps P ps vs (by assumption)
        · simp_all
      · cases h
    · cases h
  | .con _ _, .int _, _, _, _, h | .con _ _, .bool _, _, _, _, h | .con _ _, .str _, _, _, _, h
  | .con _ _, .unit, _, _, _, h | .con _ _, .seq _ _, _, _, _, h
  | .con _ _, .clo .., _, _, _, h | .con _ _, .fn _, _, _, _, h
  | .con _ _, .cap _, _, _, _, h => by simp [matchPat] at h
  | .alt ps, v, bs, bu, dr, h => by
    simp only [matchPat] at h
    exact matchAlt_caps P ps v h
theorem matchList_caps (P : Prog) : ∀ (ps : List Pat) (vs : List Val) {bs bu dr}, matchList P ps vs = .ok bs bu dr →
    capsL (bs.map (·.2)) ⊆ capsL vs
  | [], [], bs, bu, dr, h => by simp [matchList] at h; obtain ⟨rfl, -, -⟩ := h; simp [capsL]
  | p :: ps, v :: vs, bs, bu, dr, h => by
    simp only [matchList] at h
    split at h
    · rename_i b1 u1 d1 h1
      split at h
      · rename_i b2 u2 d2 h2
        cases h
        simp only [List.map_append, capsL_append, capsL]
        exact sub_app (matchPat_caps P p v h1) (matchList_caps P ps vs h2)
      · simp_all
    · simp_all
  | [], _ :: _, _, _, _, h | _ :: _, [], _, _, _, h => by simp [matchList] at h
theorem matchAlt_caps (P : Prog) : ∀ (ps : List Pat) (v : Val) {bs bu dr}, matchAlt P ps v = .ok bs bu dr →
    capsL (bs.map (·.2)) ⊆ v.caps
  | [], v, _, _, _, h => by simp [matchAlt] at h
  | p :: ps, v, bs, bu, dr, h => by
    simp only [matchAlt] at h
    split at h
    · exact matchAlt_caps P ps v h
    · exact matchPat_caps P p v (by assumption)
end

end Tenon

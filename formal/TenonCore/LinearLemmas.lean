/-
Token accounting for the helpers of the evaluator (used by Linear.lean).
Counts per token (`List.count`) turn every fact into linear arithmetic.
-/
import TenonCore.Eval

namespace Tenon

/-! ## Counting tokens -/

theorem toksL_append (a b : List Val) : toksL (a ++ b) = toksL a ++ toksL b := by
  induction a with
  | nil => simp [toksL]
  | cons v vs ih => simp [toksL, ih]

theorem count_toksL_set (t : Tok) : ∀ (vs : List Val) (i : Nat) (w : Val) (h : i < vs.length),
    (toksL (vs.set i w)).count t + (vs[i]).toks.count t = (toksL vs).count t + w.toks.count t
  | [], _, _, h => by simp at h
  | v :: vs, 0, w, _ => by simp [toksL, List.count_append]; omega
  | v :: vs, i + 1, w, h => by
    have := count_toksL_set t vs i w (by simpa using h)
    simp [toksL, List.count_append]; omega

def slotToks : Option Val → List Tok
  | some v => v.toks
  | none => []

theorem envToks_cons (x : String) (s : Option Val) (ρ : Env) : envToks ((x, s) :: ρ) = slotToks s ++ envToks ρ := by
  cases s <;> rfl

theorem envToks_append (a b : Env) : envToks (a ++ b) = envToks a ++ envToks b := by
  induction a with
  | nil => rfl
  | cons p a ih => obtain ⟨x, s⟩ := p; simp [envToks_cons, ih]

theorem update_toks (t : Tok) : ∀ {ρ : Env} {x : String} {s : Option Val} (s' : Option Val), lookup ρ x = some s →
    (envToks (update ρ x s')).count t + (slotToks s).count t = (envToks ρ).count t + (slotToks s').count t
  | [], _, _, _, h => by simp [lookup] at h
  | (y, u) :: ρ, x, s, s', h => by
    simp only [lookup] at h
    simp only [update]
    split
    · rename_i hy; simp only [hy, ite_true, Option.some.injEq] at h; subst h
      simp [envToks_cons, List.count_append]; omega
    · rename_i hy; simp only [hy, ite_false] at h
      have := update_toks t s' h
      simp [envToks_cons, List.count_append]; omega

theorem lookup_toks (t : Tok) {ρ : Env} {x : String} {v : Val} (h : lookup ρ x = some (some v)) :
    v.toks.count t ≤ (envToks ρ).count t := by
  have := update_toks t none h
  simp [slotToks] at this; omega

/-! ## Paths -/

theorem entryKV_toks {e k v : Val} (h : entryKV e = some (k, v)) : e.toks = k.toks ++ v.toks := by
  unfold entryKV at h
  split at h
  · simp only [Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h; simp [Val.toks, toksL]
  · cases h

theorem mapSet_get_toks (t : Tok) (k w : Val) : ∀ (kvs : List Val) {old : Val}, mapGet k kvs = some old →
    (toksL (mapSet k w kvs)).count t + old.toks.count t = (toksL kvs).count t + w.toks.count t
  | [], _, h => by simp [mapGet] at h
  | e :: r, old, h => by
    simp only [mapGet] at h
    simp only [mapSet]
    cases he : entryKV e with
    | none =>
      simp only [he] at h ⊢
      have := mapSet_get_toks t k w r h
      simp [toksL, List.count_append]; omega
    | some kv =>
      obtain ⟨k', v⟩ := kv
      simp only [he] at h ⊢
      by_cases hb : Val.beq k k' = true
      · simp only [hb, ite_true, Option.some.injEq] at h ⊢; subst h
        simp [toksL, Val.toks, entryKV_toks he, List.count_append]; omega
      · simp only [hb] at h ⊢
        have := mapSet_get_toks t k w r h
        simp [toksL, List.count_append]; omega

theorem mapSet_new_toks (t : Tok) (k w : Val) : ∀ (kvs : List Val), mapGet k kvs = none →
    (toksL (mapSet k w kvs)).count t = (toksL kvs).count t + k.toks.count t + w.toks.count t
  | [], _ => by simp [mapSet, toksL, Val.toks, List.count_append]
  | e :: r, h => by
    simp only [mapGet] at h
    simp only [mapSet]
    cases he : entryKV e with
    | none =>
      simp only [he] at h ⊢
      have := mapSet_new_toks t k w r h
      simp [toksL, List.count_append]; omega
    | some kv =>
      obtain ⟨k', v⟩ := kv
      simp only [he] at h ⊢
      by_cases hb : Val.beq k k' = true
      · simp [hb] at h
      · simp only [hb] at h ⊢
        have := mapSet_new_toks t k w r h
        simp [toksL, List.count_append]; omega

theorem getElem?_some {vs : List Val} {i : Nat} {c : Val} (h : vs[i]? = some c) : ∃ hi : i < vs.length, vs[i] = c := by
  simpa [List.getElem?_eq_some_iff] using h

theorem step_toks (t : Tok) (P : Prog) {v c c' r : Val} {s : Step} (hg : getStep P v s = .ok c)
    (hs : setStep P v s c' = .ok r) : r.toks.count t + c.toks.count t = v.toks.count t + c'.toks.count t := by
  cases s with
  | fld f =>
    cases v with
    | adt s0 t0 tok vs =>
      simp only [getStep] at hg
      simp only [setStep] at hs
      cases hfi : fieldIdx P s0 f with
      | none => simp [hfi] at hg
      | some i =>
        simp only [hfi] at hg hs
        cases hv : vs[i]? with
        | none => simp [hv] at hg
        | some c0 =>
          simp only [hv, Except.ok.injEq] at hg; subst hg
          obtain ⟨hlt, hv'⟩ := getElem?_some hv
          simp only [hlt, ite_true, Except.ok.injEq] at hs; subst hs
          have := count_toksL_set t vs i c' hlt
          rw [hv'] at this
          simp [Val.toks, List.count_append]; omega
    | _ => simp [getStep] at hg
  | tfld i =>
    cases v with
    | seq k vs =>
      cases k with
      | tup =>
        simp only [getStep] at hg
        simp only [setStep] at hs
        cases hv : vs[i]? with
        | none => simp [hv] at hg
        | some c0 =>
          simp only [hv, Except.ok.injEq] at hg; subst hg
          obtain ⟨hlt, hv'⟩ := getElem?_some hv
          simp only [hlt, ite_true, Except.ok.injEq] at hs; subst hs
          have := count_toksL_set t vs i c' hlt
          rw [hv'] at this
          simp [Val.toks]; omega
      | _ => simp [getStep] at hg
    | _ => simp [getStep] at hg
  | idx key =>
    cases v with
    | seq k vs =>
      cases k with
      | list =>
        cases key with
        | int i =>
          simp only [getStep] at hg
          simp only [setStep] at hs
          by_cases hb : 0 ≤ i ∧ i.toNat < vs.length
          · rw [dif_pos hb] at hg; simp only [Except.ok.injEq] at hg; subst hg
            simp only [hb, and_self, ite_true, Except.ok.injEq] at hs; subst hs
            have := count_toksL_set t vs i.toNat c' hb.2
            simp [Val.toks]; omega
          · simp [hb] at hg
        | _ => simp [getStep] at hg
      | map =>
        simp only [getStep] at hg
        simp only [setStep, Except.ok.injEq] at hs; subst hs
        cases hm : mapGet key vs with
        | none => simp [hm] at hg
        | some c0 =>
          simp only [hm, Except.ok.injEq] at hg; subst hg
          have := mapSet_get_toks t key c' vs hm
          simp [Val.toks]; omega
      | tup => simp [getStep] at hg
    | _ => simp [getStep] at hg

theorem getPath_cons (P : Prog) (v : Val) (s : Step) (ss : List Step) :
    getPath P v (s :: ss) = match getStep P v s with
      | .ok w => getPath P w ss
      | .error e => .error e := rfl

theorem setPath_cons2 (P : Prog) (v w : Val) (s s2 : Step) (ss : List Step) :
    setPath P v (s :: s2 :: ss) w = match getStep P v s with
      | .ok c => match setPath P c (s2 :: ss) w with
        | .ok c' => setStep P v s c'
        | .error e => .error e
      | .error e => .error e := rfl

theorem oldAt_cons2 (P : Prog) (v : Val) (s s2 : Step) (ss : List Step) :
    oldAt P v (s :: s2 :: ss) = match getStep P v s with
      | .ok w => oldAt P w (s2 :: ss)
      | .error e => .error e := rfl

theorem path_toks (t : Tok) (P : Prog) : ∀ {v old w r : Val} {ss : List Step}, getPath P v ss = .ok old →
    setPath P v ss w = .ok r → r.toks.count t + old.toks.count t = v.toks.count t + w.toks.count t
  | v, old, w, r, [], hg, hs => by
    simp only [getPath, Except.ok.injEq] at hg; simp only [setPath, Except.ok.injEq] at hs
    subst hg; subst hs; omega
  | v, old, w, r, [s], hg, hs => by
    rw [getPath_cons] at hg
    cases hc : getStep P v s with
    | ok c =>
      rw [hc] at hg; simp only [getPath, Except.ok.injEq] at hg; subst hg
      simp only [setPath] at hs
      exact step_toks t P hc hs
    | error e => rw [hc] at hg; cases hg
  | v, old, w, r, s :: s2 :: ss, hg, hs => by
    rw [getPath_cons] at hg
    rw [setPath_cons2] at hs
    cases hc : getStep P v s with
    | ok c =>
      rw [hc] at hg hs
      dsimp only at hg hs
      cases hc' : setPath P c (s2 :: ss) w with
      | ok c' =>
        rw [hc'] at hs; dsimp only at hs
        have h1 := path_toks t P hg hc'
        have h2 := step_toks t P hc hs
        omega
      | error e => rw [hc'] at hs; cases hs
    | error e => rw [hc] at hg; cases hg

def stepsToks : List Step → List Tok
  | [] => []
  | .idx k :: ss => k.toks ++ stepsToks ss
  | _ :: ss => stepsToks ss

/-- An assignment replaces what `oldAt` names (or adds a map entry whose key holds no token). -/
theorem assign_toks (t : Tok) (P : Prog) : ∀ {v w r : Val} {o : Option Val} {ss : List Step},
    stepsToks ss = [] → oldAt P v ss = .ok o → setPath P v ss w = .ok r →
    r.toks.count t + (slotToks o).count t = v.toks.count t + w.toks.count t
  | v, w, r, o, [], _, ho, hs => by
    simp only [oldAt, Except.ok.injEq] at ho; simp only [setPath, Except.ok.injEq] at hs
    subst ho; subst hs; simp [slotToks]; omega
  | v, w, r, o, [s], hk, ho, hs => by
    simp only [setPath] at hs
    cases s with
    | idx key =>
      simp only [stepsToks, List.append_nil] at hk
      cases v with
      | seq k vs =>
        cases k with
        | map =>
          simp only [oldAt, Except.ok.injEq] at ho
          simp only [setStep, Except.ok.injEq] at hs; subst hs
          cases hm : mapGet key vs with
          | none =>
            rw [hm] at ho; subst ho
            have := mapSet_new_toks t key w vs hm
            simp [Val.toks, slotToks, hk] at this ⊢; omega
          | some old =>
            rw [hm] at ho; subst ho
            have := mapSet_get_toks t key w vs hm
            simp [Val.toks, slotToks]; omega
        | list =>
          simp only [oldAt] at ho
          cases hg : getStep P (.seq .list vs) (.idx key) with
          | ok c =>
            rw [hg] at ho; simp only [Except.map, Except.ok.injEq] at ho; subst ho
            have := step_toks t P hg hs
            simp [slotToks]; omega
          | error e => rw [hg] at ho; cases ho
        | tup => simp [oldAt, getStep, Except.map] at ho
      | _ => simp [oldAt, getStep, Except.map] at ho
    | fld f =>
      simp only [oldAt] at ho
      cases hg : getStep P v (.fld f) with
      | ok c =>
        rw [hg] at ho; simp only [Except.map, Except.ok.injEq] at ho; subst ho
        have := step_toks t P hg hs
        simp [slotToks]; omega
      | error e => rw [hg] at ho; cases ho
    | tfld i =>
      simp only [oldAt] at ho
      cases hg : getStep P v (.tfld i) with
      | ok c =>
        rw [hg] at ho; simp only [Except.map, Except.ok.injEq] at ho; subst ho
        have := step_toks t P hg hs
        simp [slotToks]; omega
      | error e => rw [hg] at ho; cases ho
  | v, w, r, o, s :: s2 :: ss, hk, ho, hs => by
    rw [oldAt_cons2] at ho
    rw [setPath_cons2] at hs
    cases hc : getStep P v s with
    | ok c =>
      rw [hc] at ho hs
      dsimp only at ho hs
      cases hc' : setPath P c (s2 :: ss) w with
      | ok c' =>
        rw [hc'] at hs; dsimp only at hs
        have hk' : stepsToks (s2 :: ss) = [] := by
          cases s <;> simp_all [stepsToks]
        have h1 := assign_toks t P hk' ho hc'
        have h2 := step_toks t P hc hs
        omega
      | error e => rw [hc'] at hs; cases hs
    | error e => rw [hc] at ho; cases ho

/-! ## Patterns -/

mutual
theorem matchPat_toks (t : Tok) (P : Prog) : ∀ (p : Pat) (v : Val) {bs bu dr}, matchPat P p v = .ok bs bu dr →
    v.toks.count t = (toksL (bs.map (·.2))).count t + bu.count t + (toksL dr).count t
  | .wild, v, bs, bu, dr, h => by
    simp [matchPat] at h; obtain ⟨rfl, rfl, rfl⟩ := h; simp [toksL]
  | .bind x, v, bs, bu, dr, h => by
    simp [matchPat] at h; obtain ⟨rfl, rfl, rfl⟩ := h; simp [toksL]
  | .lit l, v, bs, bu, dr, h => by
    simp only [matchPat] at h
    unfold litMatch at h
    split at h <;> (try split at h) <;> simp_all [toksL, Val.toks]
  | .tup ps, .seq .tup vs, bs, bu, dr, h => by
    simp only [matchPat] at h
    simp only [Val.toks]; exact matchList_toks t P ps vs h
  | .tup _, .int _, _, _, _, h | .tup _, .bool _, _, _, _, h | .tup _, .str _, _, _, _, h
  | .tup _, .unit, _, _, _, h | .tup _, .seq .list _, _, _, _, h | .tup _, .seq .map _, _, _, _, h
  | .tup _, .adt .., _, _, _, h | .tup _, .clo .., _, _, _, h | .tup _, .fn _, _, _, _, h
  | .tup _, .cap _, _, _, _, h => by simp [matchPat] at h
  | .con c ps, .adt s tag tok vs, bs, bu, dr, h => by
    simp only [matchPat] at h
    split at h
    · split at h
      · split at h
        · rename_i b u d hm
          simp only [MR.ok.injEq] at h; obtain ⟨rfl, rfl, rfl⟩ := h
          have := matchList_toks t P ps vs hm
          simp only [Val.toks, List.count_append]; omega
        · simp_all
      · cases h
    · cases h
  | .con _ _, .int _, _, _, _, h | .con _ _, .bool _, _, _, _, h | .con _ _, .str _, _, _, _, h
  | .con _ _, .unit, _, _, _, h | .con _ _, .seq _ _, _, _, _, h
  | .con _ _, .clo .., _, _, _, h | .con _ _, .fn _, _, _, _, h
  | .con _ _, .cap _, _, _, _, h => by simp [matchPat] at h
  | .alt ps, v, bs, bu, dr, h => by
    simp only [matchPat] at h
    exact matchAlt_toks t P ps v h
theorem matchList_toks (t : Tok) (P : Prog) : ∀ (ps : List Pat) (vs : List Val) {bs bu dr},
    matchList P ps vs = .ok bs bu dr →
    (toksL vs).count t = (toksL (bs.map (·.2))).count t + bu.count t + (toksL dr).count t
  | [], [], bs, bu, dr, h => by simp [matchList] at h; obtain ⟨rfl, rfl, rfl⟩ := h; simp [toksL]
  | p :: ps, v :: vs, bs, bu, dr, h => by
    simp only [matchList] at h
    split at h
    · rename_i b1 u1 d1 h1
      split at h
      · rename_i b2 u2 d2 h2
        simp only [MR.ok.injEq] at h; obtain ⟨rfl, rfl, rfl⟩ := h
        have e1 := matchPat_toks t P p v h1
        have e2 := matchList_toks t P ps vs h2
        simp only [List.map_append, toksL_append, toksL, List.count_append]; omega
      · simp_all
    · simp_all
  | [], _ :: _, _, _, _, h | _ :: _, [], _, _, _, h => by simp [matchList] at h
theorem matchAlt_toks (t : Tok) (P : Prog) : ∀ (ps : List Pat) (v : Val) {bs bu dr}, matchAlt P ps v = .ok bs bu dr →
    v.toks.count t = (toksL (bs.map (·.2))).count t + bu.count t + (toksL dr).count t
  | [], v, _, _, _, h => by simp [matchAlt] at h
  | p :: ps, v, bs, bu, dr, h => by
    simp only [matchAlt] at h
    split at h
    · exact matchAlt_toks t P ps v h
    · exact matchPat_toks t P p v (by assumption)
end

/-! ## Environments built and taken apart by the evaluator -/

theorem pushBinds_toks (bs : List (String × Val)) (ρ : Env) :
    envToks (pushBinds bs ρ) = toksL (bs.map (·.2)) ++ envToks ρ := by
  induction bs with
  | nil => simp [pushBinds, toksL]
  | cons b bs ih =>
    obtain ⟨x, v⟩ := b
    simp only [pushBinds, List.map_cons, List.cons_append] at ih ⊢
    rw [envToks_cons, ih]
    simp [slotToks, toksL]

theorem capture_toks : ∀ (ρ : Env), toksL ((capture ρ).map (·.2)) = []
  | [] => by simp [capture, toksL]
  | (x, s) :: ρ => by
    have ih := capture_toks ρ
    unfold capture at ih ⊢
    cases s with
    | none => simpa using ih
    | some v =>
      by_cases hv : v.toks = []
      · simp only [List.filterMap_cons, hv, ite_true, List.map_cons, toksL]; simp [hv, ih]
      · simp only [List.filterMap_cons, hv, ite_false]; exact ih

theorem filterMap_slots_toks : ∀ (ρ : Env), toksL (ρ.filterMap (·.2)) = envToks ρ
  | [] => by simp [toksL, envToks]
  | (x, s) :: ρ => by
    have ih := filterMap_slots_toks ρ
    cases s with
    | none => simpa [envToks] using ih
    | some v => simp [toksL, envToks, ih]

theorem take_drop_toks (k : Nat) (ρ : Env) : envToks ρ = envToks (ρ.take k) ++ envToks (ρ.drop k) := by
  rw [← envToks_append, List.take_append_drop]

def argsToks : List ArgV → List Tok
  | [] => []
  | a :: as => a.v.toks ++ argsToks as

theorem argsToks_append (a b : List ArgV) : argsToks (a ++ b) = argsToks a ++ argsToks b := by
  induction a with
  | nil => rfl
  | cons x a ih => simp [argsToks, ih]

theorem captured_toks : ∀ (names : List String) (cvs : List Val),
    envToks ((names.zip cvs).map (fun (x, v) => (x, some v))) = toksL (cvs.take names.length)
  | [], _ => by simp [envToks, toksL]
  | _ :: _, [] => by simp [envToks, toksL]
  | x :: names, v :: cvs => by
    have ih := captured_toks names cvs
    simp only [List.zip_cons_cons, List.map_cons, List.length_cons, List.take_succ_cons]
    rw [envToks_cons, ih]
    simp [slotToks, toksL]

theorem frameOf_toks (names : List String) (cvs : List Val) (hn : names.length = cvs.length) :
    ∀ (ps : List (String × Mode)) (as : List ArgV), as.length = ps.length →
    envToks (frameOf ps as names cvs) = argsToks as ++ toksL cvs
  | [], [], _ => by
    simp only [frameOf, List.zip_nil_left, List.map_nil, List.nil_append, argsToks]
    rw [captured_toks, hn, List.take_length]
  | p :: ps, a :: as, h => by
    have ih := frameOf_toks names cvs hn ps as (by simpa using h)
    simp only [frameOf] at ih ⊢
    simp only [List.zip_cons_cons, List.map_cons, List.cons_append]
    rw [envToks_cons, ih]
    simp [slotToks, argsToks]
  | [], _ :: _, h | _ :: _, [], h => by simp at h

end Tenon

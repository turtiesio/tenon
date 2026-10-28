/-
Typed values under the evaluator's helpers (TypeSafe.lean): paths, map
entries, patterns, heads and minting never get stuck on well-typed values.
-/
import TenonCore.TypingLemmas

namespace Tenon

/-! ## Resolved paths -/

/-- One resolved step at a type, and the type it reaches. -/
inductive StepTy (X : Ext) (P : Prog) (prim : PrimSig) : Ty → Step → Ty → Prop
  | fld {s args f d i ft} : P.adts s = some d → d.isStruct = true → idxOf f d.fields = some i →
      (d.variants.head?.map (·.2)).bind (·[i]?) = some ft → StepTy X P prim (.adt s args) (.fld f) (ft.subst args)
  | tfld {ts i ti} : ts[i]? = some ti → StepTy X P prim (.tup ts) (.tfld i) ti
  | idxList {el k} : StepTy X P prim (.list el) (.idx (.int k)) el
  | idxMap {kt vt k} : ValTyX X P prim k kt → StepTy X P prim (.map kt vt) (.idx k) vt

inductive StepsTy (X : Ext) (P : Prog) (prim : PrimSig) : Ty → List Step → Ty → Prop
  | nil {t} : StepsTy X P prim t [] t
  | cons {T s T' ss t} : StepTy X P prim T s T' → StepsTy X P prim T' ss t → StepsTy X P prim T (s :: ss) t

section
variable {X : Ext} {P : Prog} {prim : PrimSig}

theorem idxOf_lt : ∀ {x : String} {l : List String} {i : Nat}, idxOf x l = some i → i < l.length
  | _, [], _, h => by simp [idxOf] at h
  | x, y :: l, i, h => by
    simp only [idxOf] at h
    split at h
    · simp at h; subst h; simp
    · cases hi : idxOf x l with
      | none => rw [hi] at h; simp at h
      | some j => rw [hi] at h; simp at h; subst h; have := idxOf_lt hi; simp; omega

theorem mem_zip_getElem : ∀ {α β} {as : List α} {bs : List β} {i : Nat} {a : α} {b : β},
    as[i]? = some a → bs[i]? = some b → (a, b) ∈ as.zip bs
  | _, _, [], _, _, _, _, h, _ => by simp at h
  | _, _, _ :: _, [], _, _, _, _, h => by simp at h
  | _, _, x :: as, y :: bs, 0, a, b, h1, h2 => by simp at h1 h2; subst h1; subst h2; simp
  | _, _, x :: as, y :: bs, i + 1, a, b, h1, h2 => by
    simp at h1 h2; exact List.mem_cons_of_mem _ (mem_zip_getElem h1 h2)

theorem mem_zip_set : ∀ {α β} {as : List α} {bs : List β} {i : Nat} {w : α} {p : α × β},
    p ∈ (as.set i w).zip bs → p ∈ as.zip bs ∨ (p.1 = w ∧ bs[i]? = some p.2)
  | _, _, [], _, _, _, _, h => by simp at h
  | _, _, _ :: _, [], _, _, _, h => by simp at h
  | _, _, x :: as, y :: bs, 0, w, p, h => by
    simp only [List.set_cons_zero, List.zip_cons_cons, List.mem_cons] at h
    rcases h with rfl | h
    · exact Or.inr ⟨rfl, rfl⟩
    · exact Or.inl (List.mem_cons_of_mem _ h)
  | _, _, x :: as, y :: bs, i + 1, w, p, h => by
    simp only [List.set_cons_succ, List.zip_cons_cons, List.mem_cons] at h
    rcases h with rfl | h
    · exact Or.inl (by simp)
    · rcases mem_zip_set h with h | h
      · exact Or.inl (List.mem_cons_of_mem _ h)
      · exact Or.inr (by simpa using h)

theorem substL_getElem? (σ : List Ty) : ∀ {ts : List Ty} {i : Nat} {t : Ty}, ts[i]? = some t →
    (substL σ ts)[i]? = some (t.subst σ)
  | [], _, _, h => by simp at h
  | t :: ts, 0, u, h => by simp at h; subst h; rfl
  | t :: ts, i + 1, u, h => by simp at h; simp only [substL, List.getElem?_cons_succ]; exact substL_getElem? σ h

theorem ValTyX.zip_get {vs : List Val} {ts : List Ty} (h : ∀ p ∈ vs.zip ts, ValTyX X P prim p.1 p.2)
    {i : Nat} {v : Val} {t : Ty} (hv : vs[i]? = some v) (ht : ts[i]? = some t) : ValTyX X P prim v t :=
  h (v, t) (mem_zip_getElem hv ht)

theorem ValTyX.zip_set {vs : List Val} {ts : List Ty} (h : ∀ p ∈ vs.zip ts, ValTyX X P prim p.1 p.2)
    {i : Nat} {w : Val} {t : Ty} (ht : ts[i]? = some t) (hw : ValTyX X P prim w t) :
    ∀ p ∈ (vs.set i w).zip ts, ValTyX X P prim p.1 p.2 := by
  intro p hp
  rcases mem_zip_set hp with hp | ⟨h1, h2⟩
  · exact h p hp
  · rw [ht] at h2; simp only [Option.some.injEq] at h2; rw [h1, ← h2]; exact hw

/-- The struct case of a value: its only variant, the field's index in range. -/
theorem struct_inv (hA : AdtsOk P) {s : String} {d : AdtDecl} (hd : P.adts s = some d) (hs : d.isStruct = true)
    {tag : Nat} {name : String} {ts : List Ty} (hv : d.variants[tag]? = some (name, ts)) :
    tag = 0 ∧ d.fields.length = ts.length ∧ d.variants.head?.map (·.2) = some ts := by
  obtain ⟨nm, ts', hvs, hf⟩ := (hA s d hd).1 hs
  rw [hvs] at hv
  cases tag with
  | zero => simp at hv; obtain ⟨-, rfl⟩ := hv; exact ⟨rfl, hf, by simp [hvs]⟩
  | succ k => simp at hv

theorem mapGet_ty {vt : Ty} {k : Val} : ∀ {kvs : List Val},
    (∀ e ∈ kvs, ∀ a b, entryKV e = some (a, b) → ValTyX X P prim b vt) → ∀ {w}, mapGet k kvs = some w → ValTyX X P prim w vt
  | [], _, _, h => by simp [mapGet] at h
  | e :: kvs, hb, w, h => by
    simp only [mapGet] at h
    split at h
    · rename_i k' v he
      split at h
      · simp at h; subst h; exact hb e (by simp) k' _ he
      · exact mapGet_ty (fun e' he' => hb e' (by simp [he'])) h
    · exact mapGet_ty (fun e' he' => hb e' (by simp [he'])) h

theorem mapSet_mem (k w : Val) : ∀ {kvs : List Val} {e : Val}, e ∈ mapSet k w kvs →
    e ∈ kvs ∨ e = .seq .tup [k, w] ∨ ∃ e0 ∈ kvs, ∃ k' v', entryKV e0 = some (k', v') ∧ e = .seq .tup [k', w]
  | [], e, h => by simp [mapSet] at h; exact Or.inr (Or.inl h)
  | e1 :: kvs, e, h => by
    simp only [mapSet] at h
    split at h
    · rename_i k' v' he
      split at h
      · simp only [List.mem_cons] at h
        rcases h with rfl | h
        · exact Or.inr (Or.inr ⟨e1, by simp, k', v', he, rfl⟩)
        · exact Or.inl (by simp [h])
      · simp only [List.mem_cons] at h
        rcases h with rfl | h
        · exact Or.inl (by simp)
        · rcases mapSet_mem k w h with h | h | ⟨e0, h0, h⟩
          · exact Or.inl (by simp [h])
          · exact Or.inr (Or.inl h)
          · exact Or.inr (Or.inr ⟨e0, by simp [h0], h⟩)
    · simp only [List.mem_cons] at h
      rcases h with rfl | h
      · exact Or.inl (by simp)
      · rcases mapSet_mem k w h with h | h | ⟨e0, h0, h⟩
        · exact Or.inl (by simp [h])
        · exact Or.inr (Or.inl h)
        · exact Or.inr (Or.inr ⟨e0, by simp [h0], h⟩)

theorem ValTyX.mapSet {kvs : List Val} {kt vt : Ty} (h : ValTyX X P prim (.seq .map kvs) (.map kt vt))
    {k w : Val} (hk : ValTyX X P prim k kt) (hw : ValTyX X P prim w vt) :
    ValTyX X P prim (.seq .map (Tenon.mapSet k w kvs)) (.map kt vt) := by
  cases h with
  | map hs ha hb =>
    refine .map ?_ ?_ ?_
    · intro e he
      rcases mapSet_mem k w he with h | rfl | ⟨e0, -, k', v', -, rfl⟩
      · exact hs e h
      · rfl
      · rfl
    · intro e he a b hab
      rcases mapSet_mem k w he with h | rfl | ⟨e0, h0, k', v', he0, rfl⟩
      · exact ha e h a b hab
      · simp [entryKV] at hab; rw [← hab.1]; exact hk
      · simp [entryKV] at hab; rw [← hab.1]; exact ha e0 h0 k' v' he0
    · intro e he a b hab
      rcases mapSet_mem k w he with h | rfl | ⟨e0, h0, k', v', he0, rfl⟩
      · exact hb e h a b hab
      · simp [entryKV] at hab; rw [← hab.2]; exact hw
      · simp [entryKV] at hab; rw [← hab.2]; exact hw

/-- A step can trap (an index out of bounds, a missing key) but never gets stuck. -/
def PathOk {α : Type} (Q : α → Prop) : Except PErr α → Prop
  | .ok a => Q a
  | .error (.trap _) => True
  | .error (.stuck _) => False

theorem PathOk.map_some {α : Type} {Q : α → Prop} {r : Except PErr α} (h : PathOk Q r) :
    PathOk (fun o => ∀ w, o = some w → Q w) (r.map some) := by
  cases r with
  | ok a => intro w hw; simp at hw; subst hw; exact h
  | error e => cases e <;> simp_all [PathOk, Except.map]

theorem getStep_ty (hA : AdtsOk P) {T T' : Ty} {s : Step} (hs : StepTy X P prim T s T') {v : Val}
    (hv : ValTyX X P prim v T) : PathOk (ValTyX X P prim · T') (getStep P v s) := by
  cases hs with
  | @fld s0 args f d i ft hd hst hi hft =>
    cases hv with
    | @adt _ tag tok vs d' name ts _ hd' hvar ha hl hvs htok =>
      rw [hd] at hd'; cases hd'
      obtain ⟨rfl, hfl, hts⟩ := struct_inv hA hd hst hvar
      rw [hts] at hft; simp only [Option.bind_some] at hft
      have hil := idxOf_lt hi
      have hvi : vs[i]? = some vs[i] := List.getElem?_eq_getElem (by omega)
      simp only [getStep, fieldIdx, hd, hst, ite_true, hi, hvi, PathOk]
      exact ValTyX.zip_get hvs hvi (substL_getElem? args hft)
  | @tfld ts i ti hti =>
    cases hv with
    | tup hl hvs =>
      rename_i vs
      have hil : i < vs.length := by have := (List.getElem?_eq_some_iff.1 hti).1; omega
      have hvi : vs[i]? = some vs[i] := List.getElem?_eq_getElem hil
      simp only [getStep, hvi, PathOk]
      exact ValTyX.zip_get hvs hvi hti
  | @idxList el k =>
    cases hv with
    | list hvs =>
      simp only [getStep]
      split
      · exact hvs _ (List.getElem_mem _)
      · trivial
  | @idxMap kt vt k hk =>
    cases hv with
    | map hs ha hb =>
      simp only [getStep]
      split
      · rename_i w hw; exact mapGet_ty hb hw
      · trivial

theorem getPath_ty (hA : AdtsOk P) {T t : Ty} {ss : List Step} (hs : StepsTy X P prim T ss t) :
    ∀ {v : Val}, ValTyX X P prim v T → PathOk (ValTyX X P prim · t) (getPath P v ss) := by
  induction hs with
  | nil => intro v hv; exact hv
  | @cons T s T' ss t h1 _ ih =>
    intro v hv
    rw [getPath_cons]
    have := getStep_ty hA h1 hv
    revert this
    cases getStep P v s with
    | ok w => intro hw; exact ih hw
    | error e => cases e <;> simp [PathOk]

theorem setStep_ty (hA : AdtsOk P) {T T' : Ty} {s : Step} (hs : StepTy X P prim T s T') {v w : Val}
    (hv : ValTyX X P prim v T) (hw : ValTyX X P prim w T') : PathOk (ValTyX X P prim · T) (setStep P v s w) := by
  cases hs with
  | @fld s0 args f d i ft hd hst hi hft =>
    cases hv with
    | @adt _ tag tok vs d' name ts _ hd' hvar ha hl hvs htok =>
      rw [hd] at hd'; cases hd'
      obtain ⟨rfl, hfl, hts⟩ := struct_inv hA hd hst hvar
      rw [hts] at hft; simp only [Option.bind_some] at hft
      have hil := idxOf_lt hi
      simp only [setStep, fieldIdx, hd, hst, ite_true, hi, show i < vs.length by omega, PathOk]
      exact .adt hd hvar ha (by simp [hl]) (ValTyX.zip_set hvs (substL_getElem? args hft) hw) htok
  | @tfld ts i ti hti =>
    cases hv with
    | tup hl hvs =>
      rename_i vs
      have hil : i < vs.length := by have := (List.getElem?_eq_some_iff.1 hti).1; omega
      simp only [setStep, hil, ite_true, PathOk]
      exact .tup (by simp [hl]) (ValTyX.zip_set hvs hti hw)
  | @idxList el k =>
    cases hv with
    | list hvs =>
      simp only [setStep]
      split
      · refine .list fun x hx => ?_
        rcases List.mem_or_eq_of_mem_set hx with h | rfl
        · exact hvs x h
        · exact hw
      · trivial
  | @idxMap kt vt k hk =>
    cases hv with
    | map hs ha hb =>
      simp only [setStep, PathOk]
      exact ValTyX.mapSet (.map hs ha hb) hk hw

theorem setPath_ty (hA : AdtsOk P) {T t : Ty} {ss : List Step} (hs : StepsTy X P prim T ss t) :
    ∀ {v w : Val}, ValTyX X P prim v T → ValTyX X P prim w t → PathOk (ValTyX X P prim · T) (setPath P v ss w) := by
  induction hs with
  | nil => intro v w _ hw; exact hw
  | @cons T s T' ss t h1 h2 ih =>
    intro v w hv hw
    cases ss with
    | nil => cases h2; exact setStep_ty hA h1 hv hw
    | cons s2 ss =>
      rw [setPath_cons2]
      have hg := getStep_ty hA h1 hv
      split
      · rename_i c hc
        rw [hc] at hg
        have hc' := ih hg hw
        split
        · rename_i c' hc2; rw [hc2] at hc'; exact setStep_ty hA h1 hv hc'
        · rename_i e hc2; rw [hc2] at hc'; cases e <;> simp_all [PathOk]
      · rename_i e hc; rw [hc] at hg; cases e <;> simp_all [PathOk]

theorem oldAt_ty (hA : AdtsOk P) {T t : Ty} {ss : List Step} (hs : StepsTy X P prim T ss t) :
    ∀ {v : Val}, ValTyX X P prim v T → PathOk (fun o => ∀ w, o = some w → ValTyX X P prim w t) (oldAt P v ss) := by
  induction hs with
  | nil => intro v hv w hw; simp [oldAt] at hw; subst hw; exact hv
  | @cons T s T' ss t h1 h2 ih =>
    intro v hv
    cases ss with
    | nil =>
      cases h2
      have hg := getStep_ty hA h1 hv
      cases h1 with
      | idxMap hk =>
        cases hv with
        | map hs ha hb => simp only [oldAt, PathOk]; intro w hw; exact mapGet_ty hb hw
      | fld => cases hv; exact hg.map_some
      | tfld => cases hv; exact hg.map_some
      | idxList => cases hv; exact hg.map_some
    | cons s2 ss =>
      rw [oldAt_cons2]
      have hg := getStep_ty hA h1 hv
      revert hg
      cases getStep P v s with
      | ok c => intro hc; exact ih hc
      | error e => cases e <;> simp [PathOk]

/-! ## Patterns -/

/-- The names and values a match binds, against the names and types the pattern's typing gives. -/
inductive BindsTy (X : Ext) (P : Prog) (prim : PrimSig) : List (String × Val) → List (String × Ty) → Prop
  | nil : BindsTy X P prim [] []
  | cons {x v t bs ts} : ValTyX X P prim v t → BindsTy X P prim bs ts → BindsTy X P prim ((x, v) :: bs) ((x, t) :: ts)

theorem BindsTy.append {a b : List (String × Val)} {c d : List (String × Ty)} (h1 : BindsTy X P prim a c)
    (h2 : BindsTy X P prim b d) : BindsTy X P prim (a ++ b) (c ++ d) := by
  induction h1 with
  | nil => exact h2
  | cons hv _ ih => exact .cons hv ih

theorem BindsTy.length {a : List (String × Val)} {c : List (String × Ty)} (h : BindsTy X P prim a c) :
    a.length = c.length := by
  induction h with
  | nil => rfl
  | cons _ _ ih => simp [ih]

/-- The pushed bindings match the context of the bound names. -/
theorem BindsTy.envOk {bs : List (String × Val)} {ts : List (String × Ty)} (h : BindsTy X P prim bs ts)
    {ρ : Env} {Γ : Ctx} (hρ : EnvOkX X P prim ρ Γ) : EnvOkX X P prim (pushBinds bs ρ) (bindCtx ts ++ Γ) := by
  induction h with
  | nil => exact hρ
  | cons hv _ ih => exact ⟨rfl, ⟨fun _ => ⟨_, rfl, hv⟩, fun h => by simp at h⟩, ih⟩

/-- A typed match fails or binds typed values, dropping only values without linear obligations. -/
def MatchOk (X : Ext) (P : Prog) (prim : PrimSig) (r : MR) (bs : List (String × Ty)) : Prop :=
  r = .fail ∨ ∃ b u d, r = .ok b u d ∧ BindsTy X P prim b bs ∧ ∀ w ∈ d, w.hasLin = false

theorem nodup_fst_idx {α β} [DecidableEq α] : ∀ {l : List (α × β)} {i j : Nat} {c : α} {a b : β},
    (l.map Prod.fst).Nodup → l[i]? = some (c, a) → l[j]? = some (c, b) → i = j
  | [], _, _, _, _, _, _, h, _ => by simp at h
  | x :: l, 0, 0, _, _, _, _, _, _ => rfl
  | x :: l, 0, j + 1, c, a, b, hn, hi, hj => by
    simp at hi hj; subst hi
    simp only [List.map_cons, List.nodup_cons] at hn
    exact absurd (List.mem_map.2 ⟨_, List.mem_of_getElem? hj, rfl⟩) hn.1
  | x :: l, i + 1, 0, c, a, b, hn, hi, hj => by
    simp at hi hj; subst hj
    simp only [List.map_cons, List.nodup_cons] at hn
    exact absurd (List.mem_map.2 ⟨_, List.mem_of_getElem? hi, rfl⟩) hn.1
  | x :: l, i + 1, j + 1, c, a, b, hn, hi, hj => by
    simp at hi hj
    simp only [List.map_cons, List.nodup_cons] at hn
    rw [nodup_fst_idx hn.2 hi hj]

mutual
theorem matchPat_ty (hA : AdtsOk P) : ∀ {p : Pat} {t : Ty} {bs : List (String × Ty)}, PatTy P p t bs →
    ∀ {v : Val}, ValTyX X P prim v t → MatchOk X P prim (matchPat P p v) bs
  | _, _, _, .wild hl, v, hv => Or.inr ⟨[], [], [v], by simp [matchPat], .nil, by simpa using hv.noLin hA hl⟩
  | _, _, _, .bind, v, hv => Or.inr ⟨_, [], [], by simp [matchPat], .cons hv .nil, by simp⟩
  | _, _, _, @PatTy.lit _ l, v, hv => by
    simp only [matchPat]
    cases l with
    | int a => cases hv; simp only [litMatch]; split
               · exact Or.inr ⟨[], [], [], rfl, .nil, by simp⟩
               · exact Or.inl rfl
    | bool a => cases hv; simp only [litMatch]; split
                · exact Or.inr ⟨[], [], [], rfl, .nil, by simp⟩
                · exact Or.inl rfl
    | str a => cases hv; simp only [litMatch]; split
               · exact Or.inr ⟨[], [], [], rfl, .nil, by simp⟩
               · exact Or.inl rfl
    | unit => cases hv; exact Or.inr ⟨[], [], [], rfl, .nil, by simp⟩
  | _, _, _, .tup hps, v, hv => by
    cases hv with
    | tup hl hvs => simp only [matchPat]; exact matchList_ty hA hps hl hvs
  | _, _, _, @PatTy.con _ c ps s args d tag ts bs hd hs hvar _ hps, v, hv => by
    cases hv with
    | @adt _ tag' tok vs d' name' ts' _ hd' hvar' ha hl hvs htok =>
      rw [hd] at hd'; cases hd'
      have hvn : variantName P s tag' = some name' := by simp [variantName, hd, hs, hvar']
      simp only [matchPat, hvn]
      split
      · rename_i heq
        subst heq
        have htag := nodup_fst_idx ((hA s d hd).2.1 hs) hvar' hvar
        subst htag
        rw [hvar] at hvar'; simp only [Option.some.injEq, Prod.mk.injEq] at hvar'; obtain ⟨-, rfl⟩ := hvar'
        rcases matchList_ty hA hps (by rw [substL_length]; exact hl) hvs with h | ⟨b, u, dr, h, hb, hdr⟩
        · rw [h]; exact Or.inl rfl
        · rw [h]; exact Or.inr ⟨b, _, dr, rfl, hb, hdr⟩
      · exact Or.inl rfl
  | _, _, _, .alt halt, v, hv => by simp only [matchPat]; exact matchAlt_ty hA halt hv

theorem matchList_ty (hA : AdtsOk P) : ∀ {ps : List Pat} {ts : List Ty} {bs : List (String × Ty)}, PatsTy P ps ts bs →
    ∀ {vs : List Val}, vs.length = ts.length → (∀ q ∈ vs.zip ts, ValTyX X P prim q.1 q.2) →
    MatchOk X P prim (matchList P ps vs) bs
  | _, _, _, .nil, [], _, _ => Or.inr ⟨[], [], [], by simp [matchList], .nil, by simp⟩
  | _, _, _, .nil, _ :: _, hl, _ => by simp at hl
  | _, _, _, .cons _ _, [], hl, _ => by simp at hl
  | _, _, _, .cons hp hps, v :: vs, hl, hvs => by
    simp only [matchList]
    rcases matchPat_ty hA hp (hvs (v, _) (by simp)) with h | ⟨b1, u1, d1, h, hb1, hd1⟩
    · rw [h]; exact Or.inl rfl
    · rw [h]
      rcases matchList_ty hA hps (by simpa using hl) (fun q hq => hvs q (by simp [hq])) with
        h2 | ⟨b2, u2, d2, h2, hb2, hd2⟩
      · rw [h2]; exact Or.inl rfl
      · rw [h2]
        refine Or.inr ⟨_, _, _, rfl, hb1.append hb2, ?_⟩
        intro w hw; rcases List.mem_append.1 hw with hw | hw
        · exact hd1 w hw
        · exact hd2 w hw

theorem matchAlt_ty (hA : AdtsOk P) : ∀ {ps : List Pat} {t : Ty} {bs : List (String × Ty)}, AltTy P ps t bs →
    ∀ {v : Val}, ValTyX X P prim v t → MatchOk X P prim (matchAlt P ps v) bs
  | _, _, _, .one hp, v, hv => by
    simp only [matchAlt]
    rcases matchPat_ty hA hp hv with h | ⟨b, u, d, h, hb, hd⟩
    · rw [h]; exact Or.inl (by simp [matchAlt])
    · rw [h]; exact Or.inr ⟨b, u, d, rfl, hb, hd⟩
  | _, _, _, .cons hp hps, v, hv => by
    simp only [matchAlt]
    rcases matchPat_ty hA hp hv with h | ⟨b, u, d, h, hb, hd⟩
    · rw [h]; exact matchAlt_ty hA hps hv
    · rw [h]; exact Or.inr ⟨b, u, d, rfl, hb, hd⟩
end

/-! ## Heads, minting, `?` -/

theorem ValTyX.head {v : Val} {t : Ty} (h : ValTyX X P prim v t) : v.head = t.head := by
  cases h <;> rfl

theorem mint_tok (st : St) (k : Kind) : TokOk k (mint st k).1 := by
  cases k <;> simp [mint, TokOk]

theorem TokOk.copy {tok : Option Tok} (h : TokOk .copy tok) : tok = none := by
  cases tok <;> simp_all [TokOk]

theorem tryVal_opt (hS : StdOk P) {v : Val} {t : Ty} (hv : ValTyX X P prim v (.adt "Option" [t])) :
    (∃ x, tryVal v = some (.inl x) ∧ ValTyX X P prim x t) ∨ tryVal v = some (.inr (.adt "Option" 1 none [])) := by
  obtain ⟨⟨d, hd, hk, -, -, hvs⟩, -⟩ := hS
  cases hv with
  | @adt _ tag tok vs d' name ts _ hd' hvar ha hl hpay htok =>
    rw [hd] at hd'; cases hd'
    rw [hk] at htok; have := htok.copy; subst this
    rw [hvs] at hvar
    match tag, hvar with
    | 0, hvar =>
      simp at hvar; obtain ⟨-, rfl⟩ := hvar
      match vs, hl with
      | [x], _ =>
        left; exact ⟨x, rfl, hpay (x, t) (by simp [substL, Ty.subst])⟩
    | 1, hvar =>
      simp at hvar; obtain ⟨-, rfl⟩ := hvar
      match vs, hl with
      | [], _ => right; rfl

theorem tryVal_res (hS : StdOk P) {v : Val} {t er : Ty} (hv : ValTyX X P prim v (.adt "Result" [t, er])) :
    (∃ x, tryVal v = some (.inl x) ∧ ValTyX X P prim x t) ∨
    ∃ e, tryVal v = some (.inr (.adt "Result" 1 none [e])) ∧ ValTyX X P prim e er := by
  obtain ⟨-, ⟨d, hd, hk, -, -, hvs⟩⟩ := hS
  cases hv with
  | @adt _ tag tok vs d' name ts _ hd' hvar ha hl hpay htok =>
    rw [hd] at hd'; cases hd'
    rw [hk] at htok; have := htok.copy; subst this
    rw [hvs] at hvar
    match tag, hvar with
    | 0, hvar =>
      simp at hvar; obtain ⟨-, rfl⟩ := hvar
      match vs, hl with
      | [x], _ => left; exact ⟨x, rfl, hpay (x, t) (by simp [substL, Ty.subst])⟩
    | 1, hvar =>
      simp at hvar; obtain ⟨-, rfl⟩ := hvar
      match vs, hl with
      | [e], _ => right; exact ⟨e, rfl, hpay (e, er) (by simp [substL, Ty.subst])⟩

theorem ValTyX.none_opt (hS : StdOk P) (t : Ty) : ValTyX X P prim (.adt "Option" 1 none []) (.adt "Option" [t]) := by
  obtain ⟨⟨d, hd, hk, -, hp, hvs⟩, -⟩ := hS
  exact .adt hd (by rw [hvs]; rfl) (by simp [hp]) (by rfl) (by simp) (by rw [hk]; trivial)

theorem ValTyX.err_res (hS : StdOk P) (t : Ty) {e : Val} {er : Ty} (he : ValTyX X P prim e er) :
    ValTyX X P prim (.adt "Result" 1 none [e]) (.adt "Result" [t, er]) := by
  obtain ⟨-, ⟨d, hd, hk, -, hp, hvs⟩⟩ := hS
  refine .adt hd (by rw [hvs]; rfl) (by simp [hp]) (by rfl) ?_ (by rw [hk]; trivial)
  intro q hq; simp [substL, Ty.subst] at hq; subst hq; exact he

end

end Tenon

/-
Linear and unique soundness (formal/README.md, "Theorems").

Every linear or unique value carries a token, minted when it is built
(`mint`). The evaluator never copies a value that holds a token (a read
moves it out of its variable), refuses to drop a linear one (`discard`), and
logs every token it discharges (`burned`: destructured by `match`, or a
type's own method finishing its `self`) or drops (`dropped`: unique values
only). The theorem is a conservation law: along any evaluation that does not
get stuck or trap, every token is, at the end, in exactly one place — the
result, the environment, the burned log or the dropped log — and only tokens
that were minted appear (no forging). Early exits (`return`, `break`,
`continue`, `?`) are included: they are ordinary results here.

Together with `Nodup` of the minted log, a program whose run ends (with any
value) has discharged each linear obligation it created exactly once, never
dropped one, and never duplicated a unique value (`obligations_exactly_once`).
This file: the invariant and the helpers' lemmas; LinearSafe.lean: the
induction over the evaluator and the theorems.
That well-typed programs never get stuck on these checks is the job of the
type system (Typing.lean); the corpus programs `tenon check` accepts are
also run on this semantics (ops/gates/formal_diff.py).
-/
import TenonCore.LinearLemmas

namespace Tenon

/-! ## The invariant -/

/-- The balance of a step from `(X in hand, ρ, st)` to `(R in hand, ρ', st')`: per token,
what is held plus what is logged changes only by what was minted. -/
def Bal (R : List Tok) (ρ' : Env) (st' : St) (X : List Tok) (ρ : Env) (st : St) : Prop :=
  ∀ t, R.count t + (envToks ρ').count t + st'.burned.count t + st'.dropped.count t + st.minted.count t =
       X.count t + (envToks ρ).count t + st.burned.count t + st.dropped.count t + st'.minted.count t

/-- Only unique values are dropped; minted tokens are distinct and below `next`. -/
def StOk (st : St) : Prop :=
  (∀ t ∈ st.dropped, t.lin = false) ∧ st.minted.Nodup ∧ ∀ t ∈ st.minted, t.id < st.next

def ctlToks : Ctl → List Tok
  | .ret v => v.toks
  | _ => []

def OutT {α : Type} (X : List Tok) (ρ : Env) (st : St) (f : α → List Tok) : Out α → Prop
  | .ok a ρ' st' => Bal (f a) ρ' st' X ρ st ∧ StOk st'
  | .ctl c ρ' st' => Bal (ctlToks c) ρ' st' X ρ st ∧ StOk st'
  | .err _ => True

theorem Bal.refl (X : List Tok) (ρ : Env) (st : St) : Bal X ρ st X ρ st := fun _ => by omega

theorem Bal.trans {R Y X : List Tok} {ρ2 ρ1 ρ : Env} {st2 st1 st : St}
    (h2 : Bal R ρ2 st2 Y ρ1 st1) (h1 : Bal Y ρ1 st1 X ρ st) : Bal R ρ2 st2 X ρ st := by
  intro t; have a := h2 t; have b := h1 t; omega

theorem OutT.weaken {α : Type} {f : α → List Tok} {r : Out α} {Y X : List Tok} {ρ1 ρ : Env} {st1 st : St}
    (h : OutT Y ρ1 st1 f r) (hb : Bal Y ρ1 st1 X ρ st) : OutT X ρ st f r := by
  cases r with
  | ok a ρ' st' => exact ⟨h.1.trans hb, h.2⟩
  | ctl c ρ' st' => exact ⟨h.1.trans hb, h.2⟩
  | err e => trivial

theorem OutT.bind {α β : Type} {f : α → List Tok} {g : β → List Tok} {X : List Tok} {ρ : Env} {st : St}
    {r : Out α} {k : α → Env → St → Out β} (h : OutT X ρ st f r)
    (hk : ∀ a ρ1 st1, r = .ok a ρ1 st1 → Bal (f a) ρ1 st1 X ρ st → StOk st1 → OutT (f a) ρ1 st1 g (k a ρ1 st1)) :
    OutT X ρ st g (r.bind k) := by
  cases r with
  | ok a ρ1 st1 => exact (hk a ρ1 st1 rfl h.1 h.2).weaken h.1
  | ctl c ρ' st' => exact h
  | err e => trivial

theorem OutT.ctl' {α β : Type} {f : α → List Tok} {g : β → List Tok} {X : List Tok} {ρ : Env} {st : St}
    {c : Ctl} {ρ' : Env} {st' : St} (h : OutT X ρ st f (.ctl c ρ' st')) : OutT X ρ st g (.ctl c ρ' st') := h

theorem OutT.stuck {α : Type} {f : α → List Tok} {X : List Tok} {ρ : Env} {st : St} (k : Stuck) (w : String) :
    OutT X ρ st f (.err (.stuck k w)) := trivial

/-! ## Logs -/

theorem discard_spec {v : Val} {st st' : St} (h : discard v st = some st') :
    st'.burned = st.burned ∧ st'.minted = st.minted ∧ st'.next = st.next ∧ st'.dropped = v.toks ++ st.dropped ∧
    (∀ t ∈ v.toks, t.lin = false) := by
  unfold discard at h
  split at h
  · cases h
  · rename_i hl
    simp only [Option.some.injEq] at h; subst h
    refine ⟨rfl, rfl, rfl, rfl, ?_⟩
    intro t ht
    simp only [Val.hasLin, List.any_eq_true, not_exists, not_and, Bool.not_eq_true] at hl
    exact hl t ht

theorem StOk.discard {v : Val} {st st' : St} (h : discard v st = some st') (hs : StOk st) : StOk st' := by
  obtain ⟨hb, hm, hn, hd, hl⟩ := discard_spec h
  obtain ⟨h1, h2, h3⟩ := hs
  refine ⟨?_, by rw [hm]; exact h2, by rw [hm, hn]; exact h3⟩
  intro t ht
  rw [hd] at ht
  rcases List.mem_append.1 ht with h | h
  · exact hl t h
  · exact h1 t h

theorem discard_bal {v : Val} {st st' : St} (h : discard v st = some st') (ρ : Env) :
    Bal [] ρ st' v.toks ρ st := by
  obtain ⟨hb, hm, -, hd, -⟩ := discard_spec h
  intro t; rw [hb, hm, hd]; simp [List.count_append]; omega

theorem discardAll_spec : ∀ {vs : List Val} {st st' : St}, discardAll vs st = some st' →
    st'.burned = st.burned ∧ st'.minted = st.minted ∧ st'.next = st.next ∧
    (∀ t, st'.dropped.count t = (toksL vs).count t + st.dropped.count t) ∧ (StOk st → StOk st')
  | [], st, st', h => by
    simp only [discardAll, Option.some.injEq] at h; subst h
    exact ⟨rfl, rfl, rfl, fun t => by simp [toksL], id⟩
  | v :: vs, st, st', h => by
    simp only [discardAll] at h
    split at h
    · rename_i st1 h1
      obtain ⟨b1, m1, n1, d1, -⟩ := discard_spec h1
      obtain ⟨b2, m2, n2, d2, o2⟩ := discardAll_spec h
      refine ⟨b2.trans b1, m2.trans m1, n2.trans n1, fun t => ?_, fun hs => o2 (StOk.discard h1 hs)⟩
      rw [d2, d1]; simp [toksL, List.count_append]; omega
    · cases h

theorem discardSlot_spec {s : Option Val} {st st' : St} (h : discardSlot s st = some st') :
    st'.burned = st.burned ∧ st'.minted = st.minted ∧ st'.next = st.next ∧
    (∀ t, st'.dropped.count t = (slotToks s).count t + st.dropped.count t) ∧ (StOk st → StOk st') := by
  cases s with
  | none => simp only [discardSlot, Option.some.injEq] at h; subst h; exact ⟨rfl, rfl, rfl, fun t => by simp [slotToks], id⟩
  | some v =>
    simp only [discardSlot] at h
    obtain ⟨b, m, n, d, -⟩ := discard_spec h
    exact ⟨b, m, n, fun t => by rw [d]; simp [slotToks, List.count_append], StOk.discard h⟩

/-! ## The helpers of the evaluator -/

variable (P : Prog)

theorem peek_spec {ρ : Env} {st : St} {x : String} {ss : List Step} :
    (∃ v v0, peek P ρ st x ss = .ok v ρ st ∧ lookup ρ x = some (some v0) ∧ getPath P v0 ss = .ok v) ∨
    (∃ e, peek P ρ st x ss = .err e) := by
  unfold peek
  split
  · rename_i v0 hl
    split
    · rename_i v hv; exact Or.inl ⟨v, v0, rfl, hl, hv⟩
    · rename_i pe _
      cases pe <;> exact Or.inr ⟨_, rfl⟩
  · exact Or.inr ⟨_, rfl⟩
  · exact Or.inr ⟨_, rfl⟩

theorem readPlace_T {ρ : Env} {st : St} {x : String} {ss : List Step} (hs : StOk st) :
    OutT [] ρ st Val.toks (readPlace P ρ st x ss) := by
  unfold readPlace
  rcases peek_spec P (ρ := ρ) (st := st) (x := x) (ss := ss) with ⟨v, v0, hp, hl, hg⟩ | ⟨e, hp⟩
  · rw [hp]
    dsimp only
    split
    · rename_i h0; exact ⟨fun t => by simp [h0], hs⟩
    · split
      · rename_i _ hss
        subst hss
        simp only [getPath, Except.ok.injEq] at hg; subst hg
        refine ⟨fun t => ?_, hs⟩
        have := update_toks t none hl
        simp [slotToks] at this ⊢; omega
      · trivial
  · rw [hp]; trivial

theorem placeArg_T {ρ : Env} {st : St} {m : Mode} {x : String} {ss : List Step} (hs : StOk st) :
    OutT [] ρ st (·.v.toks) (placeArg P ρ st m x ss) := by
  unfold placeArg
  split
  · have h := readPlace_T P (x := x) (ss := ss) (ρ := ρ) hs
    split
    · rename_i v ρ1 st1 heq; rw [heq] at h; exact h
    · rename_i c ρ1 st1 heq; rw [heq] at h; exact h
    · trivial
  · rcases peek_spec P (ρ := ρ) (st := st) (x := x) (ss := ss) with ⟨v, v0, hp, hl, hg⟩ | ⟨e, hp⟩
    · rw [hp]
      dsimp only
      split
      · rename_i h0; exact ⟨fun t => by simp [h0], hs⟩
      · split
        · rename_i _ hss
          subst hss
          simp only [getPath, Except.ok.injEq] at hg; subst hg
          refine ⟨fun t => ?_, hs⟩
          have := update_toks t none hl
          simp [slotToks] at this ⊢; omega
        · trivial
    · rw [hp]; trivial

theorem unwindArg_T {a : ArgV} {ρ ρ' : Env} {st st' : St} (h : unwindArg a ρ st = some (ρ', st')) (hs : StOk st) :
    Bal [] ρ' st' a.v.toks ρ st ∧ StOk st' := by
  unfold unwindArg at h
  split at h
  · rename_i x _
    split at h
    · rename_i hl
      simp only [Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
      refine ⟨fun t => ?_, hs⟩
      have := update_toks t (some a.v) hl
      simp [slotToks] at this ⊢; omega
    · cases h
  · cases hd : discard a.v st with
    | none => simp [hd] at h
    | some st1 =>
      simp only [hd, Option.map_some, Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
      exact ⟨discard_bal hd ρ, StOk.discard hd hs⟩

theorem unwindArgs_T : ∀ {as : List ArgV} {ρ ρ' : Env} {st st' : St}, unwindArgs as ρ st = some (ρ', st') →
    StOk st → Bal [] ρ' st' (argsToks as) ρ st ∧ StOk st'
  | [], ρ, ρ', st, st', h, hs => by
    simp only [unwindArgs, Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
    exact ⟨Bal.refl _ _ _, hs⟩
  | a :: as, ρ, ρ', st, st', h, hs => by
    simp only [unwindArgs] at h
    split at h
    · rename_i ρ1 st1 h1
      obtain ⟨b1, s1⟩ := unwindArg_T h1 hs
      obtain ⟨b2, s2⟩ := unwindArgs_T h s1
      refine ⟨fun t => ?_, s2⟩
      have x1 := b1 t; have x2 := b2 t
      simp [argsToks, List.count_append] at x1 x2 ⊢; omega
    · cases h

theorem writeBack_T {ρ : Env} {st : St} {wb : WB} {v : Val} (hs : StOk st) :
    OutT v.toks ρ st (fun _ => []) (writeBack P ρ st wb v) := by
  unfold writeBack
  split
  · split
    · rename_i st' h; exact ⟨discard_bal h ρ, StOk.discard h hs⟩
    · trivial
  · rename_i x
    split
    · rename_i hl
      refine ⟨fun t => ?_, hs⟩
      have := update_toks t (some v) hl
      simp [slotToks] at this ⊢; omega
    · trivial
  · rename_i x ss
    split
    · rename_i v0 hl
      split
      · rename_i old hold
        split
        · rename_i h0
          split
          · rename_i v1 hv1
            refine ⟨fun t => ?_, hs⟩
            have e1 := path_toks t P hold hv1
            have e2 := update_toks t (some v1) hl
            rw [h0] at e1
            simp [slotToks] at e1 e2 ⊢; omega
          · rename_i pe _; cases pe <;> trivial
        · trivial
      · rename_i pe _; cases pe <;> trivial
    · trivial

theorem writeBack_ne_ctl {ρ : Env} {st : St} {wb : WB} {v : Val} {c : Ctl} {ρ' : Env} {st' : St} :
    writeBack P ρ st wb v ≠ .ctl c ρ' st' := by
  unfold writeBack
  split
  · split <;> simp [stuckL]
  · split <;> simp [stuckL]
  · split
    · split
      · split
        · split
          · simp
          · rename_i pe _; cases pe <;> simp [pathErr, stuckT]
        · simp [stuckL]
      · rename_i pe _; cases pe <;> simp [pathErr, stuckT]
    · simp [stuckL]

theorem endFrame_ne_ctl (owner : Option String) : ∀ (ps : List (String × Mode)) (as : List ArgV) (fr ρc : Env) (st : St)
    {c : Ctl} {ρ' : Env} {st' : St}, endFrame P owner ps as fr ρc st ≠ .ctl c ρ' st'
  | [], [], rest, ρc, st, c, ρ', st' => by unfold endFrame; split <;> simp [stuckL]
  | (p, m) :: ps, a :: as, (y, slot) :: fr, ρc, st, c, ρ', st' => by
    unfold endFrame
    split
    · split
      · exact endFrame_ne_ctl owner ps as fr ρc _
      · simp [stuckL]
    · split
      · split
        · exact endFrame_ne_ctl owner ps as fr _ _
        · rename_i heq; exact absurd heq (writeBack_ne_ctl P)
        · simp
      · simp [stuckL]
  | [], _ :: _, _, _, _, _, _, _ | _ :: _, [], _, _, _, _, _, _
  | _ :: _, _ :: _, [], _, _, _, _, _ => by unfold endFrame; simp [stuckT]

theorem endParam_spec {o : Option String} {b : Bool} {s : Option Val} {st st' : St}
    (h : endParam o b s st = some st') (hs : StOk st) :
    st'.minted = st.minted ∧ StOk st' ∧
    ∀ t, st'.burned.count t + st'.dropped.count t = st.burned.count t + st.dropped.count t + (slotToks s).count t := by
  unfold endParam at h
  split at h
  · rename_i o' s' tag tk vs
    split at h
    · obtain ⟨b1, m1, n1, d1, o1⟩ := discardAll_spec h
      have hs' : StOk { st with burned := tk :: st.burned } := hs
      refine ⟨m1, o1 hs', fun t => ?_⟩
      rw [b1, d1 t]
      simp [slotToks, Val.toks, List.count_cons]; omega
    · obtain ⟨b1, m1, n1, d1, o1⟩ := discardSlot_spec h
      exact ⟨m1, o1 hs, fun t => by rw [b1, d1 t]; omega⟩
  · obtain ⟨b1, m1, n1, d1, o1⟩ := discardSlot_spec h
    exact ⟨m1, o1 hs, fun t => by rw [b1, d1 t]; omega⟩

theorem endFrame_T (owner : Option String) : ∀ (ps : List (String × Mode)) (as : List ArgV) (fr ρc : Env) (st : St),
    StOk st → OutT (envToks fr) ρc st (fun _ => []) (endFrame P owner ps as fr ρc st)
  | [], [], rest, ρc, st, hs => by
    unfold endFrame
    split
    · rename_i st' h
      obtain ⟨b1, m1, n1, d1, o1⟩ := discardAll_spec h
      refine ⟨fun t => ?_, o1 hs⟩
      rw [b1, m1, d1 t, filterMap_slots_toks]; simp only [List.count_nil]; omega
    · trivial
  | (p, m) :: ps, a :: as, (y, slot) :: fr, ρc, st, hs => by
    unfold endFrame
    split
    · split
      · rename_i st' h
        obtain ⟨m1, s1, e1⟩ := endParam_spec h hs
        have ih := endFrame_T owner ps as fr ρc st' s1
        refine ih.weaken (fun t => ?_)
        have := e1 t
        rw [envToks_cons, m1]; simp [List.count_append]; omega
      · trivial
    · split
      · rename_i v
        have hw := writeBack_T P (wb := a.wb) (ρ := ρc) (v := v) hs
        split
        · rename_i ρc' st' heq
          rw [heq] at hw
          have ih := endFrame_T owner ps as fr ρc' st' hw.2
          refine ih.weaken (fun t => ?_)
          have := hw.1 t
          rw [envToks_cons]; simp [slotToks, List.count_append] at this ⊢; omega
        · rename_i heq; exact absurd heq (writeBack_ne_ctl P)
        · trivial
      · trivial
  | [], _ :: _, _, _, _, _ | _ :: _, [], _, _, _, _
  | _ :: _, _ :: _, [], _, _, _ => by unfold endFrame; trivial

theorem afterCall_T {owner : Option String} {ps : List (String × Mode)} {as : List ArgV} {ρc fr0 : Env}
    {st0 : St} {r : Out Val} (hr : OutT [] fr0 st0 Val.toks r) :
    OutT (envToks fr0) ρc st0 Val.toks (afterCall P owner ps as ρc r) := by
  unfold afterCall
  split
  · rename_i v fr st
    obtain ⟨hb, hs⟩ := hr
    have he := endFrame_T P owner ps as fr ρc st hs
    split
    · rename_i ρ' st' heq
      rw [heq] at he
      refine ⟨fun t => ?_, he.2⟩
      have a := hb t; have b := he.1 t
      simp at a b ⊢; omega
    · rename_i heq; exact absurd heq (endFrame_ne_ctl P owner ps as _ ρc _)
    · trivial
  · rename_i v fr st
    obtain ⟨hb, hs⟩ := hr
    have he := endFrame_T P owner ps as fr ρc st hs
    split
    · rename_i ρ' st' heq
      rw [heq] at he
      refine ⟨fun t => ?_, he.2⟩
      have a := hb t; have b := he.1 t
      simp [ctlToks] at a b ⊢; omega
    · rename_i heq; exact absurd heq (endFrame_ne_ctl P owner ps as _ ρc _)
    · trivial
  · trivial
  · trivial

theorem popEnv_T {k : Nat} {ρ : Env} {st : St} (hs : StOk st) : OutT [] ρ st (fun _ => []) (popEnv k ρ st) := by
  unfold popEnv
  split
  · split
    · rename_i st' h
      obtain ⟨b1, m1, n1, d1, o1⟩ := discardAll_spec h
      refine ⟨fun t => ?_, o1 hs⟩
      have := congrArg (List.count t) (take_drop_toks k ρ)
      rw [b1, m1, d1 t, filterMap_slots_toks]
      simp [List.count_append] at this ⊢; omega
    · trivial
  · trivial

theorem popEnv_ne_ctl {k : Nat} {ρ : Env} {st : St} {c : Ctl} {ρ' : Env} {st' : St} :
    popEnv k ρ st ≠ .ctl c ρ' st' := by
  unfold popEnv
  split
  · split <;> simp [stuckL]
  · simp [stuckT]

theorem popScope_T {k : Nat} {X : List Tok} {ρ : Env} {st : St} {r : Out Val} (hr : OutT X ρ st Val.toks r) :
    OutT X ρ st Val.toks (popScope k r) := by
  unfold popScope
  split
  · rename_i v ρ1 st1
    obtain ⟨hb, hs⟩ := hr
    have hp := popEnv_T (k := k) (ρ := ρ1) hs
    cases hq : popEnv k ρ1 st1 with
    | ok u ρ' st' =>
      rw [hq] at hp
      simp only [Out.bind]
      refine ⟨fun t => ?_, hp.2⟩
      have a := hb t; have b := hp.1 t
      simp only [List.count_nil] at a b ⊢; omega
    | ctl c ρ' st' => exact absurd hq popEnv_ne_ctl
    | err e => simp [Out.bind, OutT]
  · rename_i c ρ1 st1
    obtain ⟨hb, hs⟩ := hr
    have hp := popEnv_T (k := k) (ρ := ρ1) hs
    cases hq : popEnv k ρ1 st1 with
    | ok u ρ' st' =>
      rw [hq] at hp
      simp only [Out.bind]
      refine ⟨fun t => ?_, hp.2⟩
      have a := hb t; have b := hp.1 t
      simp only [List.count_nil] at a b ⊢; omega
    | ctl c ρ' st' => exact absurd hq popEnv_ne_ctl
    | err e => simp [Out.bind, OutT]
  · trivial

theorem toks_le_of_mem (t : Tok) : ∀ {v : Val} {vs : List Val}, v ∈ vs → v.toks.count t ≤ (toksL vs).count t
  | v, [], h => by simp at h
  | v, w :: vs, h => by
    simp only [List.mem_cons] at h
    simp only [toksL, List.count_append]
    rcases h with rfl | h
    · omega
    · have := toks_le_of_mem t h; omega

theorem mapGet_le (t : Tok) (k : Val) : ∀ {kvs : List Val} {v : Val}, mapGet k kvs = some v →
    v.toks.count t ≤ (toksL kvs).count t
  | [], _, h => by simp [mapGet] at h
  | e :: r, v, h => by
    simp only [mapGet] at h
    simp only [toksL, List.count_append]
    cases he : entryKV e with
    | none => simp only [he] at h; have := mapGet_le t k h; omega
    | some kv =>
      obtain ⟨k', w⟩ := kv
      simp only [he] at h
      have hev := entryKV_toks he
      by_cases hb : Val.beq k k' = true
      · simp only [hb, ite_true, Option.some.injEq] at h; subst h
        rw [hev]; simp [List.count_append]; omega
      · simp only [hb] at h; have := mapGet_le t k h; omega

theorem getStep_le (t : Tok) (P : Prog) {v w : Val} {s : Step} (h : getStep P v s = .ok w) :
    w.toks.count t ≤ v.toks.count t := by
  cases s with
  | fld f =>
    cases v with
    | adt s0 t0 tok vs =>
      simp only [getStep] at h
      cases hfi : fieldIdx P s0 f with
      | none => simp [hfi] at h
      | some i =>
        simp only [hfi] at h
        cases hv : vs[i]? with
        | none => simp [hv] at h
        | some c0 =>
          simp only [hv, Except.ok.injEq] at h; subst h
          have := toks_le_of_mem t (List.mem_of_getElem? hv)
          simp [Val.toks, List.count_append]; omega
    | _ => simp [getStep] at h
  | tfld i =>
    cases v with
    | seq k vs =>
      cases k with
      | tup =>
        simp only [getStep] at h
        cases hv : vs[i]? with
        | none => simp [hv] at h
        | some c0 =>
          simp only [hv, Except.ok.injEq] at h; subst h
          have := toks_le_of_mem t (List.mem_of_getElem? hv)
          simp [Val.toks]; omega
      | _ => simp [getStep] at h
    | _ => simp [getStep] at h
  | idx key =>
    cases v with
    | seq k vs =>
      cases k with
      | list =>
        cases key with
        | int i =>
          simp only [getStep] at h
          by_cases hb : 0 ≤ i ∧ i.toNat < vs.length
          · rw [dif_pos hb] at h; simp only [Except.ok.injEq] at h; subst h
            have := toks_le_of_mem t (List.getElem_mem hb.2)
            simp [Val.toks]; omega
          · rw [dif_neg hb] at h; cases h
        | _ => simp [getStep] at h
      | map =>
        simp only [getStep] at h
        cases hm : mapGet key vs with
        | none => simp [hm] at h
        | some c0 =>
          simp only [hm, Except.ok.injEq] at h; subst h
          have := mapGet_le t key hm
          simp [Val.toks]; omega
      | tup => simp [getStep] at h
    | _ => simp [getStep] at h

theorem getPath_le (t : Tok) (P : Prog) : ∀ {v w : Val} {ss : List Step}, getPath P v ss = .ok w →
    w.toks.count t ≤ v.toks.count t
  | v, w, [], h => by simp only [getPath, Except.ok.injEq] at h; subst h; omega
  | v, w, s :: ss, h => by
    rw [getPath_cons] at h
    cases hc : getStep P v s with
    | ok c => rw [hc] at h; have := getPath_le t P h; have := getStep_le t P hc; omega
    | error e => rw [hc] at h; cases h

theorem tryVal_toks {v : Val} {r : Sum Val Val} (h : tryVal v = some r) :
    (match r with | .inl x => x.toks | .inr x => x.toks) = v.toks := by
  unfold tryVal at h
  split at h <;> simp only [Option.some.injEq, reduceCtorEq] at h <;> subst h <;> simp [Val.toks, toksL]

theorem mint_spec (st : St) (k : Kind) :
    (mint st k).2.burned = st.burned ∧ (mint st k).2.dropped = st.dropped ∧
    (mint st k).2.minted = (mint st k).1.toList ++ st.minted ∧ (StOk st → StOk (mint st k).2) := by
  cases k with
  | copy => exact ⟨rfl, rfl, rfl, id⟩
  | linear =>
    refine ⟨rfl, rfl, rfl, fun ⟨h1, h2, h3⟩ => ⟨h1, ?_, ?_⟩⟩
    · simp only [mint]
      refine List.nodup_cons.2 ⟨fun hm => ?_, h2⟩
      have := h3 _ hm; simp at this
    · intro t ht; simp only [mint, List.mem_cons] at ht
      rcases ht with rfl | ht
      · simp [mint]
      · have := h3 t ht; simp only [mint]; omega
  | unique =>
    refine ⟨rfl, rfl, rfl, fun ⟨h1, h2, h3⟩ => ⟨h1, ?_, ?_⟩⟩
    · simp only [mint]
      refine List.nodup_cons.2 ⟨fun hm => ?_, h2⟩
      have := h3 _ hm; simp at this
    · intro t ht; simp only [mint, List.mem_cons] at ht
      rcases ht with rfl | ht
      · simp [mint]
      · have := h3 t ht; simp only [mint]; omega

theorem primApply_T {ρ : Env} {st : St} {pf : List Val → Nat → PrimRes} {vs : List Val}
    {sp : Option (String × List Step)} (hs : StOk st) : OutT [] ρ st Val.toks (primApply P ρ st pf vs sp) := by
  unfold primApply
  split
  · rename_i v self evs w heq
    split
    · trivial
    · split
      · rename_i hv
        have hs' : StOk { st with out := evs.reverse ++ st.out, world := w } := hs
        split
        · exact ⟨fun t => by simp [hv], hs'⟩
        · rename_i w' x ss
          split
          · rename_i v0 hl
            split
            · rename_i old hold
              split
              · rename_i heqt
                split
                · rename_i v1 hv1
                  refine ⟨fun t => ?_, hs'⟩
                  have e1 := path_toks t P hold hv1
                  have e2 := update_toks t (some v1) hl
                  rw [heqt] at e1
                  simp [slotToks, hv] at e1 e2 ⊢; omega
                · rename_i pe _; cases pe <;> trivial
              · trivial
            · rename_i pe _; cases pe <;> trivial
          · trivial
        · split
          · exact ⟨fun t => by simp [hv], hs'⟩
          · trivial
      · trivial
  · trivial
  · trivial
  · trivial

theorem assignAt_T {ρ : Env} {st : St} {x : String} {ss : List Step} {v : Val} (hk : stepsToks ss = [])
    (hs : StOk st) : OutT v.toks ρ st Val.toks (assignAt P ρ st x ss v) := by
  unfold assignAt
  split
  · rename_i hl
    refine ⟨fun t => ?_, hs⟩
    have := update_toks t (some v) hl
    simp [slotToks, Val.toks] at this ⊢; omega
  · rename_i old hl
    split
    · rename_i st1 h
      obtain ⟨b1, m1, n1, d1, -⟩ := discard_spec h
      refine ⟨fun t => ?_, StOk.discard h hs⟩
      have := update_toks t (some v) hl
      rw [b1, m1, d1]
      simp [slotToks, Val.toks, List.count_append] at this ⊢; omega
    · trivial
  · rename_i v0 _ hl _
    split
    · rename_i o ho
      split
      · rename_i st1 h
        obtain ⟨b1, m1, n1, d1, o1⟩ := discardSlot_spec h
        split
        · rename_i v1 hv1
          refine ⟨fun t => ?_, o1 hs⟩
          have e1 := assign_toks t P hk ho hv1
          have e2 := update_toks t (some v1) hl
          rw [b1, m1, d1 t]
          simp [slotToks, Val.toks] at e1 e2 ⊢; omega
        · rename_i pe _; cases pe <;> trivial
      · trivial
    · rename_i pe _; cases pe <;> trivial
  · trivial
  · trivial

theorem Out.bind_ok {α β : Type} {r : Out α} {k : α → Env → St → Out β} {b : β} {ρ' : Env} {st' : St}
    (h : r.bind k = .ok b ρ' st') : ∃ a ρ1 st1, r = .ok a ρ1 st1 ∧ k a ρ1 st1 = .ok b ρ' st' := by
  cases r with
  | ok a ρ1 st1 => exact ⟨a, ρ1, st1, rfl, h⟩
  | ctl c _ _ => simp [Out.bind] at h
  | err e => simp [Out.bind] at h

/-- Index keys hold no tokens (`evalSteps` checks them). -/
theorem evalSteps_toks : ∀ (n : Nat) (ρ : Env) (st : St) (ps : List PStep) {ss : List Step} {ρ' : Env} {st' : St},
    evalSteps P n ρ st ps = .ok ss ρ' st' → stepsToks ss = []
  | 0, _, _, _, _, _, _, h => by simp [evalSteps] at h
  | n + 1, ρ, st, [], ss, ρ', st', h => by simp only [evalSteps, Out.ok.injEq] at h; obtain ⟨rfl, -, -⟩ := h; rfl
  | n + 1, ρ, st, .fld f :: ps, ss, ρ', st', h => by
    simp only [evalSteps] at h
    obtain ⟨ss', ρ1, st1, h1, h2⟩ := Out.bind_ok h
    simp only [Out.ok.injEq] at h2; obtain ⟨rfl, -, -⟩ := h2
    simp only [stepsToks]; exact evalSteps_toks n ρ st ps h1
  | n + 1, ρ, st, .tfld i :: ps, ss, ρ', st', h => by
    simp only [evalSteps] at h
    obtain ⟨ss', ρ1, st1, h1, h2⟩ := Out.bind_ok h
    simp only [Out.ok.injEq] at h2; obtain ⟨rfl, -, -⟩ := h2
    simp only [stepsToks]; exact evalSteps_toks n ρ st ps h1
  | n + 1, ρ, st, .idx e :: ps, ss, ρ', st', h => by
    simp only [evalSteps] at h
    obtain ⟨k, ρ1, st1, h1, h2⟩ := Out.bind_ok h
    split at h2
    · rename_i hk
      obtain ⟨ss', ρ2, st2, h3, h4⟩ := Out.bind_ok h2
      simp only [Out.ok.injEq] at h4; obtain ⟨rfl, -, -⟩ := h4
      simp only [stepsToks, hk, List.nil_append]; exact evalSteps_toks n ρ1 st1 ps h3
    · simp [stuckL] at h2

end Tenon

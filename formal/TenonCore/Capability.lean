/-
Capability safety (formal/README.md, "Theorems"): whatever a computation
returns, keeps in its environment, or uses for an effect, is an attenuation
of a capability it was given. There is no way to forge one (no expression
builds a capability), and the only operations that make capabilities from
capabilities, `Fs.within` and `Fs.read_only`, only narrow (`within_le`,
`readOnly_le`).

The theorem holds for every program and every expression, typed or not:
it is a property of the semantics. Builtins are abstract; the evaluator's
monitor (`primApply`, `granted`) refuses a builtin result that is not an
attenuation of the builtin's arguments.
-/
import TenonCore.Lemmas

namespace Tenon

/-! ## The attenuation order -/

theorem Cap.leb_refl (c : Cap) : Cap.leb c c = true := by
  unfold Cap.leb
  cases c with
  | mk k j r =>
    cases j <;> cases r <;> simp [List.isPrefixOf_iff_prefix]

theorem Cap.le_refl (c : Cap) : c ≤ c := Cap.leb_refl c

theorem Cap.leb_trans {a b c : Cap} (h1 : Cap.leb a b = true) (h2 : Cap.leb b c = true) : Cap.leb a c = true := by
  obtain ⟨ka, ja, ra⟩ := a
  obtain ⟨kb, jb, rb⟩ := b
  obtain ⟨kc, jc, rc⟩ := c
  unfold Cap.leb at *
  simp only [Bool.and_eq_true, beq_iff_eq, Bool.or_eq_true, Bool.not_eq_eq_eq_not, Bool.not_true] at h1 h2 ⊢
  obtain ⟨⟨hk1, hr1⟩, hj1⟩ := h1
  obtain ⟨⟨hk2, hr2⟩, hj2⟩ := h2
  refine ⟨⟨hk1.trans hk2, ?_⟩, ?_⟩
  · cases ra <;> cases rb <;> cases rc <;> simp_all
  · cases jc with
    | none => simp
    | some r =>
      cases jb with
      | none => simp at hj2
      | some r' =>
        cases ja with
        | none => simp at hj1
        | some r'' =>
          simp only [List.isPrefixOf_iff_prefix] at hj1 hj2 ⊢
          exact hj2.trans hj1

theorem Cap.le_trans {a b c : Cap} (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := Cap.leb_trans h1 h2

/-- `Fs.within` only narrows. -/
theorem Cap.within_le (c : Cap) (segs : List String) : c.within segs ≤ c := by
  show Cap.leb _ _ = true
  obtain ⟨k, j, r⟩ := c
  unfold Cap.leb Cap.within
  cases j <;> cases r <;> simp [List.isPrefixOf_iff_prefix]

/-- `Fs.read_only` only narrows. -/
theorem Cap.readOnly_le (c : Cap) : c.readOnly ≤ c := by
  show Cap.leb _ _ = true
  obtain ⟨k, j, r⟩ := c
  unfold Cap.leb Cap.readOnly
  cases j <;> cases r <;> simp [List.isPrefixOf_iff_prefix]

/-- A read-only capability stays read-only under any attenuation. -/
theorem Cap.le_readOnly {c d : Cap} (h : c ≤ d) (hd : d.ro = true) : c.ro = true := by
  obtain ⟨k, j, r⟩ := c
  obtain ⟨k', j', r'⟩ := d
  simp only at hd
  subst hd
  have h' : Cap.leb _ _ = true := h
  unfold Cap.leb at h'
  simp only [Bool.and_eq_true, Bool.or_eq_true, Bool.not_true, Bool.false_or] at h'
  exact h'.1.2

/-! ## Bounded authority -/

section
variable (A : List Cap)

/-- Every capability in `cs` is an attenuation of one in `A`. -/
def Bnd (cs : List Cap) : Prop := ∀ c ∈ cs, ∃ a ∈ A, c ≤ a

variable {A}

theorem Bnd.mono {cs ds : List Cap} (h : cs ⊆ ds) (hd : Bnd A ds) : Bnd A cs := fun c hc => hd c (h hc)

theorem Bnd.append {xs ys : List Cap} : Bnd A (xs ++ ys) ↔ Bnd A xs ∧ Bnd A ys := by
  unfold Bnd
  simp only [List.mem_append]
  constructor
  · intro h; exact ⟨fun c hc => h c (Or.inl hc), fun c hc => h c (Or.inr hc)⟩
  · rintro ⟨h1, h2⟩ c (hc | hc)
    · exact h1 c hc
    · exact h2 c hc

theorem Bnd.nil : Bnd A [] := by simp [Bnd]

theorem Bnd.of_granted {cs gs : List Cap} (hg : granted cs gs = true) (hb : Bnd A gs) : Bnd A cs := by
  intro c hc
  unfold granted at hg
  simp only [List.all_eq_true, List.any_eq_true] at hg
  obtain ⟨d, hd, hcd⟩ := hg c hc
  obtain ⟨a, ha, hda⟩ := hb d hd
  exact ⟨a, ha, Cap.leb_trans hcd hda⟩

variable (A)

def StB (st : St) : Prop := Bnd A (st.out.map (·.cap))

def CtlB : Ctl → Prop
  | .ret v => Bnd A v.caps
  | _ => True

/-- What the theorem says about a result: the value (through `f`), the
environment and the effects so far are within `A`. -/
def OutB {α : Type} (f : α → List Cap) : Out α → Prop
  | .ok a ρ st => Bnd A (f a) ∧ Bnd A (envCaps ρ) ∧ StB A st
  | .ctl c ρ st => CtlB A c ∧ Bnd A (envCaps ρ) ∧ StB A st
  | .err (.trap _ st) => StB A st
  | .err _ => True

variable {A}

theorem OutB.err {α β : Type} {f : α → List Cap} {g : β → List Cap} {e : Err}
    (h : OutB A f (.err e)) : OutB A g (.err e) := by
  cases e <;> exact h

theorem OutB.ctl {α β : Type} {f : α → List Cap} {g : β → List Cap} {c : Ctl} {ρ : Env} {st : St}
    (h : OutB A f (.ctl c ρ st)) : OutB A g (.ctl c ρ st) := h

theorem OutB.bind {α β : Type} {f : α → List Cap} {g : β → List Cap} {r : Out α} {k : α → Env → St → Out β}
    (h : OutB A f r) (hk : ∀ a ρ st, Bnd A (f a) → Bnd A (envCaps ρ) → StB A st → OutB A g (k a ρ st)) :
    OutB A g (r.bind k) := by
  cases r with
  | ok a ρ st => exact hk a ρ st h.1 h.2.1 h.2.2
  | ctl c ρ st => exact h
  | err e => exact OutB.err h

theorem OutB.stuckT {α} {f : α → List Cap} (w : String) : OutB A f (stuckT w) := trivial
theorem OutB.stuckL {α} {f : α → List Cap} (w : String) : OutB A f (stuckL w) := trivial

theorem OutB.pathErr {α} {f : α → List Cap} {st : St} (pe : PErr) (h : StB A st) : OutB A f (pathErr st pe) := by
  cases pe <;> simp [Tenon.pathErr, OutB, Tenon.stuckT, h]

theorem discard_out {v : Val} {st st' : St} (h : discard v st = some st') : st'.out = st.out := by
  unfold discard at h; split at h <;> simp_all; subst h; rfl

theorem discardSlot_out {s : Option Val} {st st' : St} (h : discardSlot s st = some st') : st'.out = st.out := by
  cases s with
  | none => simp [discardSlot] at h; subst h; rfl
  | some v => exact discard_out h

theorem discardAll_out : ∀ {vs : List Val} {st st' : St}, discardAll vs st = some st' → st'.out = st.out
  | [], st, st', h => by simp [discardAll] at h; subst h; rfl
  | v :: vs, st, st', h => by
    simp only [discardAll] at h
    split at h
    · rename_i st1 h1; rw [discardAll_out h, discard_out h1]
    · cases h

theorem StB.of_out {st st' : St} (h : st'.out = st.out) (hb : StB A st) : StB A st' := by
  unfold StB; rw [h]; exact hb

/-! ## The helpers of the evaluator -/

variable (P : Prog)

theorem peek_ok {ρ : Env} {st : St} {x : String} {ss : List Step}
    (hρ : Bnd A (envCaps ρ)) (hs : StB A st) : OutB A Val.caps (peek P ρ st x ss) := by
  unfold peek
  split
  · rename_i v0 hl
    split
    · rename_i w hw
      exact ⟨Bnd.mono (List.Subset.trans (getPath_caps P hw) (lookup_caps hl)) hρ, hρ, hs⟩
    · exact OutB.pathErr _ hs
  · exact trivial
  · exact trivial

theorem update_bnd {ρ : Env} {x : String} {s : Option Val} (hρ : Bnd A (envCaps ρ)) (hs : Bnd A (slotCaps s)) :
    Bnd A (envCaps (update ρ x s)) :=
  Bnd.mono (update_caps ρ x s) (Bnd.append.2 ⟨hρ, hs⟩)

theorem readPlace_ok {ρ : Env} {st : St} {x : String} {ss : List Step}
    (hρ : Bnd A (envCaps ρ)) (hs : StB A st) : OutB A Val.caps (readPlace P ρ st x ss) := by
  unfold readPlace
  have hp := peek_ok P (x := x) (ss := ss) hρ hs
  split
  · rename_i v ρ1 st1 heq
    rw [heq] at hp
    obtain ⟨hv, hρ1, hs1⟩ := hp
    split
    · exact ⟨hv, hρ1, hs1⟩
    · split
      · exact ⟨hv, update_bnd hρ1 (by simp [slotCaps, Bnd.nil]), hs1⟩
      · exact trivial
  · rename_i r hr; exact hp

def wbCaps : WB → List Cap
  | .place _ ss => stepsCaps ss
  | _ => []

/-- The authority an evaluated argument carries: its value and its write-back path. -/
def argCaps (a : ArgV) : List Cap := a.v.caps ++ wbCaps a.wb

def argsCaps : List ArgV → List Cap
  | [] => []
  | a :: as => argCaps a ++ argsCaps as

def placeCaps : Option (String × List Step) → List Cap
  | some (_, ss) => stepsCaps ss
  | none => []

def opCaps (o : Val × Option (String × List Step)) : List Cap := o.1.caps ++ placeCaps o.2

def opsCaps : List (Val × Option (String × List Step)) → List Cap
  | [] => []
  | o :: os => opCaps o ++ opsCaps os

theorem placeArg_ok {ρ : Env} {st : St} {m : Mode} {x : String} {ss : List Step}
    (hρ : Bnd A (envCaps ρ)) (hs : StB A st) (hss : Bnd A (stepsCaps ss)) :
    OutB A argCaps (placeArg P ρ st m x ss) := by
  unfold placeArg
  split
  · have := readPlace_ok P (x := x) (ss := ss) hρ hs
    split <;> rename_i heq <;> rw [heq] at this <;> first | exact OutB.err this | (simp only [OutB, argCaps, wbCaps, Bnd.append] at this ⊢; simp_all [Bnd.nil])
  · have hp := peek_ok P (x := x) (ss := ss) hρ hs
    split
    · rename_i v ρ1 st1 heq
      rw [heq] at hp
      obtain ⟨hv, hρ1, hs1⟩ := hp
      split
      · exact ⟨Bnd.append.2 ⟨hv, hss⟩, hρ1, hs1⟩
      · split
        · exact ⟨Bnd.append.2 ⟨hv, Bnd.nil⟩, update_bnd hρ1 (by simp [slotCaps, Bnd.nil]), hs1⟩
        · exact trivial
    · rename_i c ρ1 st1 heq; rw [heq] at hp; exact hp
    · rename_i e heq; rw [heq] at hp; exact OutB.err hp

theorem unwindArg_ok {a : ArgV} {ρ ρ' : Env} {st st' : St} (h : unwindArg a ρ st = some (ρ', st'))
    (ha : Bnd A (argCaps a)) (hρ : Bnd A (envCaps ρ)) (hs : StB A st) : Bnd A (envCaps ρ') ∧ StB A st' := by
  have ha1 := (Bnd.append.1 ha).1
  unfold unwindArg at h
  split at h
  · split at h
    · simp only [Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
      exact ⟨update_bnd hρ (by simpa [slotCaps] using ha1), hs⟩
    · cases h
  · cases hd : discard a.v st with
    | none => simp [hd] at h
    | some st1 => simp [hd] at h; obtain ⟨rfl, rfl⟩ := h; exact ⟨hρ, StB.of_out (discard_out hd) hs⟩

theorem unwindArgs_ok : ∀ {as : List ArgV} {ρ ρ' : Env} {st st' : St}, unwindArgs as ρ st = some (ρ', st') →
    Bnd A (argsCaps as) → Bnd A (envCaps ρ) → StB A st → Bnd A (envCaps ρ') ∧ StB A st'
  | [], ρ, ρ', st, st', h, _, hρ, hs => by simp [unwindArgs] at h; obtain ⟨rfl, rfl⟩ := h; exact ⟨hρ, hs⟩
  | a :: as, ρ, ρ', st, st', h, ha, hρ, hs => by
    simp only [unwindArgs] at h
    simp only [argsCaps] at ha
    obtain ⟨ha1, ha2⟩ := Bnd.append.1 ha
    split at h
    · rename_i ρ1 st1 h1
      obtain ⟨hρ1, hs1⟩ := unwindArg_ok h1 ha1 hρ hs
      exact unwindArgs_ok h ha2 hρ1 hs1
    · cases h

theorem writeBack_ok {ρ : Env} {st : St} {wb : WB} {v : Val} (hv : Bnd A v.caps) (hw : Bnd A (wbCaps wb))
    (hρ : Bnd A (envCaps ρ)) (hs : StB A st) : OutB A (fun _ => []) (writeBack P ρ st wb v) := by
  unfold writeBack
  split
  · split
    · rename_i st' h; exact ⟨Bnd.nil, hρ, StB.of_out (discard_out h) hs⟩
    · exact trivial
  · split
    · exact ⟨Bnd.nil, update_bnd hρ (by simpa [slotCaps] using hv), hs⟩
    · exact trivial
  · rename_i x ss
    split
    · rename_i v0 hl
      split
      · split
        · split
          · rename_i v1 hv1
            refine ⟨Bnd.nil, update_bnd hρ ?_, hs⟩
            simp only [slotCaps]
            exact Bnd.mono (setPath_caps P hv1)
              (Bnd.append.2 ⟨Bnd.append.2 ⟨Bnd.mono (lookup_caps hl) hρ, hv⟩, by simpa [wbCaps] using hw⟩)
          · exact OutB.pathErr _ hs
        · exact trivial
      · exact OutB.pathErr _ hs
    · exact trivial

theorem endParam_out {o : Option String} {b : Bool} {s : Option Val} {st st' : St}
    (h : endParam o b s st = some st') : st'.out = st.out := by
  unfold endParam at h
  split at h
  · split at h
    · exact (discardAll_out h).trans rfl
    · exact discardSlot_out h
  · exact discardSlot_out h

theorem endFrame_ok (owner : Option String) : ∀ (ps : List (String × Mode)) (as : List ArgV) (fr ρc : Env) (st : St),
    Bnd A (argsCaps as) → Bnd A (envCaps fr) → Bnd A (envCaps ρc) → StB A st →
    OutB A (fun _ => []) (endFrame P owner ps as fr ρc st)
  | [], [], rest, ρc, st, _, _, hρ, hs => by
    unfold endFrame
    split
    · rename_i st' h; exact ⟨Bnd.nil, hρ, StB.of_out (discardAll_out h) hs⟩
    · exact trivial
  | (p, m) :: ps, a :: as, (y, slot) :: fr, ρc, st, ha, hf, hρ, hs => by
    simp only [argsCaps] at ha
    obtain ⟨ha1, ha2⟩ := Bnd.append.1 ha
    rw [envCaps_cons] at hf
    obtain ⟨hf1, hf2⟩ := Bnd.append.1 hf
    unfold endFrame
    split
    · split
      · rename_i st' h; exact endFrame_ok owner ps as fr ρc st' ha2 hf2 hρ (StB.of_out (endParam_out h) hs)
      · exact trivial
    · split
      · rename_i v
        have hw := writeBack_ok P (wb := a.wb) (st := st) (ρ := ρc) (by simpa [slotCaps] using hf1)
          (Bnd.append.1 ha1).2 hρ hs
        split
        · rename_i ρc' st' heq
          rw [heq] at hw
          exact endFrame_ok owner ps as fr ρc' st' ha2 hf2 hw.2.1 hw.2.2
        · rename_i c ρ' st' heq; rw [heq] at hw; exact hw
        · rename_i e heq; rw [heq] at hw; exact OutB.err hw
      · exact trivial
  | [], _ :: _, _, _, _, _, _, _, _ | _ :: _, [], _, _, _, _, _, _, _
  | _ :: _, _ :: _, [], _, _, _, _, _, _ => by unfold endFrame; exact trivial

theorem afterCall_ok {owner : Option String} {ps : List (String × Mode)} {as : List ArgV} {ρc : Env}
    {r : Out Val} (hr : OutB A Val.caps r) (ha : Bnd A (argsCaps as)) (hρ : Bnd A (envCaps ρc)) :
    OutB A Val.caps (afterCall P owner ps as ρc r) := by
  unfold afterCall
  split
  · rename_i v fr st
    obtain ⟨hv, hf, hs⟩ := hr
    have := endFrame_ok P owner ps as fr ρc st ha hf hρ hs
    split
    · rename_i heq; rw [heq] at this; exact ⟨hv, this.2.1, this.2.2⟩
    · rename_i heq; rw [heq] at this; exact this
    · rename_i heq; rw [heq] at this; exact OutB.err this
  · rename_i v fr st
    obtain ⟨hv, hf, hs⟩ := hr
    have := endFrame_ok P owner ps as fr ρc st ha hf hρ hs
    split
    · rename_i heq; rw [heq] at this; exact ⟨hv, this.2.1, this.2.2⟩
    · rename_i heq; rw [heq] at this; exact this
    · rename_i heq; rw [heq] at this; exact OutB.err this
  · exact trivial
  · exact OutB.err hr

theorem popEnv_ok {k : Nat} {ρ : Env} {st : St} (hρ : Bnd A (envCaps ρ)) (hs : StB A st) :
    OutB A (fun _ => []) (popEnv k ρ st) := by
  unfold popEnv
  split
  · split
    · rename_i st' h; exact ⟨Bnd.nil, Bnd.mono (drop_caps _ _) hρ, StB.of_out (discardAll_out h) hs⟩
    · exact trivial
  · exact trivial

theorem popScope_ok {k : Nat} {r : Out Val} (hr : OutB A Val.caps r) : OutB A Val.caps (popScope k r) := by
  unfold popScope
  split
  · obtain ⟨hv, hρ, hs⟩ := hr
    exact OutB.bind (popEnv_ok hρ hs) fun _ ρ' st' _ hρ' hs' => ⟨hv, hρ', hs'⟩
  · obtain ⟨hv, hρ, hs⟩ := hr
    exact OutB.bind (popEnv_ok hρ hs) fun _ ρ' st' _ hρ' hs' => ⟨hv, hρ', hs'⟩
  · exact hr

theorem StB.events {st : St} {evs : List Event} (hs : StB A st) (he : Bnd A (evs.map (·.cap))) :
    StB A { st with out := evs.reverse ++ st.out, world := w } := by
  unfold StB at *
  simp only [List.map_append, List.map_reverse]
  exact Bnd.append.2 ⟨Bnd.mono (fun c hc => List.mem_reverse.1 hc) he, hs⟩

theorem primApply_ok {ρ : Env} {st : St} {pf : List Val → Nat → PrimRes} {vs : List Val}
    {sp : Option (String × List Step)} (hv : Bnd A (capsL vs)) (hsp : Bnd A (placeCaps sp))
    (hρ : Bnd A (envCaps ρ)) (hs : StB A st) : OutB A Val.caps (primApply P ρ st pf vs sp) := by
  unfold primApply
  split
  · rename_i v self evs w heq
    split
    · exact trivial
    · rename_i hg
      simp only [Bool.not_eq_true', Bool.not_eq_false] at hg
      have hall := Bnd.of_granted hg hv
      obtain ⟨hab, he⟩ := Bnd.append.1 hall
      obtain ⟨hvb, hself⟩ := Bnd.append.1 hab
      have hs' := StB.events (w := w) hs he
      split
      · split
        · exact ⟨hvb, hρ, hs'⟩
        · rename_i w' x ss
          split
          · rename_i v0 hl
            split
            · split
              · split
                · rename_i v1 hv1
                  refine ⟨hvb, update_bnd hρ ?_, hs'⟩
                  simp only [slotCaps]
                  exact Bnd.mono (setPath_caps P hv1)
                    (Bnd.append.2 ⟨Bnd.append.2 ⟨Bnd.mono (lookup_caps hl) hρ, by simpa using hself⟩,
                      by simpa [placeCaps] using hsp⟩)
                · exact OutB.pathErr _ hs'
              · exact trivial
            · exact OutB.pathErr _ hs'
          · exact trivial
        · split
          · exact ⟨hvb, hρ, hs'⟩
          · exact trivial
      · exact trivial
  · exact hs
  · exact trivial
  · exact trivial

theorem assignAt_ok {ρ : Env} {st : St} {x : String} {ss : List Step} {v : Val}
    (hv : Bnd A v.caps) (hss : Bnd A (stepsCaps ss)) (hρ : Bnd A (envCaps ρ)) (hs : StB A st) :
    OutB A Val.caps (assignAt P ρ st x ss v) := by
  have hslot : Bnd A (slotCaps (some v)) := by simpa [slotCaps] using hv
  unfold assignAt
  split
  · exact ⟨by simp [Val.caps, Bnd.nil], update_bnd hρ hslot, hs⟩
  · split
    · rename_i st1 h; exact ⟨by simp [Val.caps, Bnd.nil], update_bnd hρ hslot, StB.of_out (discard_out h) hs⟩
    · exact trivial
  · rename_i v0 _ hl _
    split
    · split
      · rename_i st1 h
        split
        · rename_i v1 hv1
          refine ⟨by simp [Val.caps, Bnd.nil], update_bnd hρ ?_, StB.of_out (discardSlot_out h) hs⟩
          simp only [slotCaps]
          exact Bnd.mono (setPath_caps P hv1) (Bnd.append.2 ⟨Bnd.append.2 ⟨Bnd.mono (lookup_caps hl) hρ, hv⟩, hss⟩)
        · exact OutB.pathErr _ (StB.of_out (discardSlot_out h) hs)
      · exact trivial
    · exact OutB.pathErr _ hs
  · exact trivial
  · exact trivial

theorem captured_caps : ∀ (names : List String) (cvs : List Val),
    envCaps ((names.zip cvs).map (fun (x, v) => (x, some v))) ⊆ capsL cvs
  | [], _ => by simp [envCaps]
  | _ :: _, [] => by simp [envCaps]
  | x :: names, v :: cvs => by
    have ih := captured_caps names cvs
    simp only [List.zip_cons_cons, List.map_cons]
    rw [envCaps_cons]
    simp only [slotCaps, capsL]
    exact sub_app (fun _ h => h) ih

theorem frameOf_caps : ∀ (ps : List (String × Mode)) (as : List ArgV) (names : List String) (cvs : List Val),
    envCaps (frameOf ps as names cvs) ⊆ argsCaps as ++ capsL cvs
  | [], as, names, cvs => by
    simp only [frameOf, List.zip_nil_left, List.map_nil, List.nil_append]
    exact List.Subset.trans (captured_caps names cvs) (List.subset_append_right _ _)
  | p :: ps, [], names, cvs => by
    simp only [frameOf, List.zip_nil_right, List.map_nil, List.nil_append, argsCaps]
    exact captured_caps names cvs
  | p :: ps, a :: as, names, cvs => by
    have ih := frameOf_caps ps as names cvs
    simp only [frameOf] at ih ⊢
    simp only [List.zip_cons_cons, List.map_cons, List.cons_append]
    rw [envCaps_cons]
    simp only [slotCaps, argsCaps, argCaps]
    intro c hc
    simp only [List.mem_append] at hc ⊢
    rcases hc with h | h
    · exact Or.inl (Or.inl (Or.inl h))
    · have := ih h; simp only [List.mem_append] at this
      rcases this with h' | h'
      · exact Or.inl (Or.inr h')
      · exact Or.inr h'

theorem tryVal_caps {v : Val} : ∀ {r : Sum Val Val}, tryVal v = some r →
    (match r with | .inl x => x.caps | .inr x => x.caps) ⊆ v.caps := by
  intro r h
  unfold tryVal at h
  split at h <;> simp only [Option.some.injEq, reduceCtorEq] at h <;> subst h <;>
    simp [Val.caps, capsL]

theorem argsCaps_append (a b : List ArgV) : argsCaps (a ++ b) = argsCaps a ++ argsCaps b := by
  induction a with
  | nil => rfl
  | cons x a ih => simp [argsCaps, ih]

theorem capsL_ops (os : List (Val × Option (String × List Step))) : capsL (os.map (·.1)) ⊆ opsCaps os := by
  induction os with
  | nil => simp [capsL, opsCaps]
  | cons o os ih =>
    simp only [List.map_cons, capsL, opsCaps, opCaps]
    intro c hc; simp only [List.mem_append] at hc ⊢
    rcases hc with h | h
    · exact Or.inl (Or.inl h)
    · exact Or.inr (ih h)

theorem headPlace_ops (os : List (Val × Option (String × List Step))) :
    placeCaps (os.head?.bind (·.2)) ⊆ opsCaps os := by
  cases os with
  | nil => simp [placeCaps]
  | cons o os =>
    simp only [List.head?, Option.bind_some, opsCaps, opCaps]
    intro c hc; simp only [List.mem_append]; exact Or.inl (Or.inr hc)

/-! ## The theorem -/

variable (A) in
def RecvB : Option (Sum (String × List Step) Val) → Prop
  | none => True
  | some (.inl (_, ss)) => Bnd A (stepsCaps ss)
  | some (.inr v) => Bnd A v.caps

variable (A)

/-- The statement for every function of the evaluator at fuel `n`. -/
def CapSafe (n : Nat) : Prop :=
  (∀ ρ st e, Bnd A (envCaps ρ) → StB A st → OutB A Val.caps (eval P n ρ st e)) ∧
  (∀ ρ st es, Bnd A (envCaps ρ) → StB A st → OutB A capsL (evalList P n ρ st es)) ∧
  (∀ ρ st ps, Bnd A (envCaps ρ) → StB A st → OutB A stepsCaps (evalSteps P n ρ st ps)) ∧
  (∀ ρ st m e, Bnd A (envCaps ρ) → StB A st → OutB A argCaps (evalArg P n ρ st m e)) ∧
  (∀ ρ st ms es, Bnd A (envCaps ρ) → StB A st → OutB A argsCaps (evalArgs P n ρ st ms es)) ∧
  (∀ ρ st e, Bnd A (envCaps ρ) → StB A st → OutB A opCaps (evalOpnd P n ρ st e)) ∧
  (∀ ρ st es, Bnd A (envCaps ρ) → StB A st → OutB A opsCaps (evalOpnds P n ρ st es)) ∧
  (∀ ρ st v arms, Bnd A (envCaps ρ) → StB A st → Bnd A v.caps → OutB A Val.caps (evalArms P n ρ st v arms)) ∧
  (∀ ρ st owner ps names cvs body pre args, Bnd A (envCaps ρ) → StB A st → Bnd A (capsL cvs) →
    Bnd A (argsCaps pre) → OutB A Val.caps (callWith P n ρ st owner ps names cvs body pre args)) ∧
  (∀ ρ st pf recv args, Bnd A (envCaps ρ) → StB A st → RecvB A recv →
    OutB A Val.caps (primCall P n ρ st pf recv args))

variable {A}

theorem capSafe_zero : CapSafe A P 0 := by
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩ <;> intros <;>
    simp [eval, evalList, evalSteps, evalArg, evalArgs, evalOpnd, evalOpnds, evalArms, callWith, primCall, OutB]

theorem mint_out (st : St) (k : Kind) : (mint st k).2.out = st.out := by
  cases k <;> rfl

theorem lit_caps (l : Lit) : l.val.caps = [] := by cases l <;> rfl

theorem capSafe_succ {n : Nat} (ih : CapSafe A P n) : CapSafe A P (n + 1) := by
  obtain ⟨hE, hL, hS, hA, hAs, hO, hOs, hM, hC, hPc⟩ := ih
  refine ⟨?eval, ?list, ?steps, ?arg, ?args, ?opnd, ?opnds, ?arms, ?call, ?prim⟩
  case eval =>
    intro ρ st e hρ hs
    cases e with
    | lit l => simp only [eval]; exact ⟨by rw [lit_caps]; exact Bnd.nil, hρ, hs⟩
    | place x ps =>
      simp only [eval]
      exact OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 _ hρ1 hs1 => readPlace_ok P hρ1 hs1
    | proj e ps =>
      simp only [eval]
      refine OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      split
      · refine OutB.bind (hS ρ1 st1 ps hρ1 hs1) fun ss ρ2 st2 _ hρ2 hs2 => ?_
        split
        · rename_i w hw; exact ⟨Bnd.mono (getPath_caps P hw) hv, hρ2, hs2⟩
        · exact OutB.pathErr _ hs2
      · exact trivial
    | seq k es =>
      simp only [eval]
      exact OutB.bind (hL ρ st es hρ hs) fun vs ρ1 st1 hv hρ1 hs1 => ⟨by simpa [Val.caps] using hv, hρ1, hs1⟩
    | con s tag es =>
      simp only [eval]
      refine OutB.bind (hL ρ st es hρ hs) fun vs ρ1 st1 hv hρ1 hs1 => ?_
      split
      · exact ⟨by simpa [Val.caps] using hv, hρ1, StB.of_out (mint_out _ _) hs1⟩
      · exact trivial
    | lam ps body =>
      simp only [eval]
      exact ⟨by simp only [Val.caps]; exact Bnd.mono (capture_caps ρ) hρ, hρ, hs⟩
    | fnref f => simp only [eval]; exact ⟨by simp [Val.caps, Bnd.nil], hρ, hs⟩
    | call f args =>
      simp only [eval]
      refine OutB.bind (hE ρ st f hρ hs) fun fv ρ1 st1 hv hρ1 hs1 => ?_
      split
      · split
        · exact hC _ _ _ _ _ _ _ _ _ hρ1 hs1 (by simp [capsL, Bnd.nil]) (by simp [argsCaps, Bnd.nil])
        · split
          · exact hPc _ _ _ _ _ hρ1 hs1 trivial
          · exact trivial
      · exact hC _ _ _ _ _ _ _ _ _ hρ1 hs1 (by simpa [Val.caps] using hv) (by simp [argsCaps, Bnd.nil])
      · exact trivial
    | mcall m recv args =>
      simp only [eval]
      split
      · rename_i x ps
        refine OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 hss hρ1 hs1 => ?_
        refine OutB.bind (peek_ok P hρ1 hs1) fun v0 _ _ _ _ _ => ?_
        split
        · split
          · refine OutB.bind (placeArg_ok P hρ1 hs1 hss) fun a0 ρ2 st2 ha0 hρ2 hs2 => ?_
            exact hC _ _ _ _ _ _ _ _ _ hρ2 hs2 (by simp [capsL, Bnd.nil])
              (by simp only [argsCaps]; exact Bnd.append.2 ⟨ha0, Bnd.nil⟩)
          · exact trivial
        · exact hPc _ _ _ _ _ hρ1 hs1 hss
        · exact trivial
      · refine OutB.bind (hE ρ st _ hρ hs) fun v0 ρ1 st1 hv hρ1 hs1 => ?_
        split
        · split
          · exact hC _ _ _ _ _ _ _ _ _ hρ1 hs1 (by simp [capsL, Bnd.nil])
              (by simp only [argsCaps, argCaps, wbCaps]; simpa [Bnd.append, Bnd.nil] using hv)
          · exact trivial
        · split
          · exact hPc _ _ _ _ _ hρ1 hs1 hv
          · exact trivial
        · exact trivial
    | prim p args =>
      simp only [eval]
      split
      · exact hPc _ _ _ _ _ hρ hs trivial
      · exact trivial
    | letE x mu e body =>
      simp only [eval]
      refine OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      apply popScope_ok
      apply hE
      · rw [envCaps_cons]; exact Bnd.append.2 ⟨by simpa [slotCaps] using hv, hρ1⟩
      · exact hs1
    | assign x ps e =>
      simp only [eval]
      refine OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 hss hρ1 hs1 => ?_
      refine OutB.bind (hE ρ1 st1 e hρ1 hs1) fun v ρ2 st2 hv hρ2 hs2 => ?_
      exact assignAt_ok P hv hss hρ2 hs2
    | seqE e1 e2 =>
      simp only [eval]
      refine OutB.bind (hE ρ st e1 hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      split
      · rename_i st2 h; exact hE _ _ _ hρ1 (StB.of_out (discard_out h) hs1)
      · exact trivial
    | ite c t f =>
      simp only [eval]
      refine OutB.bind (hE ρ st c hρ hs) fun cv ρ1 st1 _ hρ1 hs1 => ?_
      split
      · exact hE _ _ _ hρ1 hs1
      · exact trivial
    | mtch e arms =>
      simp only [eval]
      exact OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => hM _ _ _ _ hρ1 hs1 hv
    | «while» c body =>
      simp only [eval]
      refine OutB.bind (hE ρ st c hρ hs) fun cv ρ1 st1 _ hρ1 hs1 => ?_
      split
      · exact ⟨by simp [Val.caps, Bnd.nil], hρ1, hs1⟩
      · have hb := hE ρ1 st1 body hρ1 hs1
        split
        · rename_i v ρ2 st2 heq
          rw [heq] at hb
          split
          · rename_i st3 h; exact hE _ _ _ hb.2.1 (StB.of_out (discard_out h) hb.2.2)
          · exact trivial
        · rename_i ρ2 st2 heq; rw [heq] at hb; exact hE _ _ _ hb.2.1 hb.2.2
        · rename_i ρ2 st2 heq; rw [heq] at hb; exact ⟨by simp [Val.caps, Bnd.nil], hb.2.1, hb.2.2⟩
        · rename_i v ρ2 st2 heq; rw [heq] at hb; exact hb
        · rename_i e heq; rw [heq] at hb; exact OutB.err hb
      · exact trivial
    | ret e =>
      simp only [eval]
      exact OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ⟨hv, hρ1, hs1⟩
    | brk => simp only [eval]; exact ⟨trivial, hρ, hs⟩
    | cont => simp only [eval]; exact ⟨trivial, hρ, hs⟩
    | «try» e =>
      simp only [eval]
      refine OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      split
      · rename_i x hx; exact ⟨Bnd.mono (tryVal_caps hx) hv, hρ1, hs1⟩
      · rename_i r hr; exact ⟨Bnd.mono (tryVal_caps hr) hv, hρ1, hs1⟩
      · exact trivial
    | unsup w => simp only [eval]; exact trivial
  case list =>
    intro ρ st es hρ hs
    cases es with
    | nil => simp only [evalList]; exact ⟨by simp [capsL, Bnd.nil], hρ, hs⟩
    | cons e es =>
      simp only [evalList]
      refine OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      have hl := hL ρ1 st1 es hρ1 hs1
      split
      · rename_i vs ρ2 st2 heq; rw [heq] at hl
        exact ⟨by simp only [capsL]; exact Bnd.append.2 ⟨hv, hl.1⟩, hl.2⟩
      · rename_i c ρ2 st2 heq; rw [heq] at hl
        split
        · rename_i st3 h; exact ⟨hl.1, hl.2.1, StB.of_out (discard_out h) hl.2.2⟩
        · exact trivial
      · rename_i e heq; rw [heq] at hl; exact OutB.err hl
  case steps =>
    intro ρ st ps hρ hs
    cases ps with
    | nil => simp only [evalSteps]; exact ⟨by simp [stepsCaps, Bnd.nil], hρ, hs⟩
    | cons s ss =>
      cases s with
      | fld f =>
        simp only [evalSteps]
        exact OutB.bind (hS ρ st ss hρ hs) fun ss' ρ1 st1 h hρ1 hs1 =>
          ⟨by simpa [stepsCaps, stepCaps] using h, hρ1, hs1⟩
      | tfld i =>
        simp only [evalSteps]
        exact OutB.bind (hS ρ st ss hρ hs) fun ss' ρ1 st1 h hρ1 hs1 =>
          ⟨by simpa [stepsCaps, stepCaps] using h, hρ1, hs1⟩
      | idx e =>
        simp only [evalSteps]
        refine OutB.bind (hE ρ st e hρ hs) fun k ρ1 st1 hk hρ1 hs1 => ?_
        split
        · exact OutB.bind (hS ρ1 st1 ss hρ1 hs1) fun ss' ρ2 st2 h hρ2 hs2 =>
            ⟨by simp only [stepsCaps, stepCaps]; exact Bnd.append.2 ⟨hk, h⟩, hρ2, hs2⟩
        · exact trivial
  case arg =>
    intro ρ st m e hρ hs
    cases m with
    | val =>
      simp only [evalArg]
      exact OutB.bind (hE ρ st e hρ hs) fun v ρ1 st1 hv hρ1 hs1 =>
        ⟨by simp only [argCaps, wbCaps]; simpa using hv, hρ1, hs1⟩
    | ref =>
      cases e with
      | place x ps =>
        simp only [evalArg]
        exact OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 hss hρ1 hs1 => placeArg_ok P hρ1 hs1 hss
      | _ => simp [evalArg, OutB, stuckT]
    | «mut» =>
      cases e with
      | place x ps =>
        simp only [evalArg]
        exact OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 hss hρ1 hs1 => placeArg_ok P hρ1 hs1 hss
      | _ => simp [evalArg, OutB, stuckT]
  case args =>
    intro ρ st ms es hρ hs
    cases ms with
    | nil =>
      cases es with
      | nil => simp only [evalArgs]; exact ⟨by simp [argsCaps, Bnd.nil], hρ, hs⟩
      | cons e es => simp [evalArgs, OutB, stuckT]
    | cons m ms =>
      cases es with
      | nil => simp [evalArgs, OutB, stuckT]
      | cons e es =>
        simp only [evalArgs]
        refine OutB.bind (hA ρ st m e hρ hs) fun a ρ1 st1 ha hρ1 hs1 => ?_
        have hl := hAs ρ1 st1 ms es hρ1 hs1
        split
        · rename_i as ρ2 st2 heq; rw [heq] at hl
          exact ⟨by simp only [argsCaps]; exact Bnd.append.2 ⟨ha, hl.1⟩, hl.2⟩
        · rename_i c ρ2 st2 heq; rw [heq] at hl
          split
          · rename_i ρ3 st3 h
            obtain ⟨hρ3, hs3⟩ := unwindArg_ok h ha hl.2.1 hl.2.2
            exact ⟨hl.1, hρ3, hs3⟩
          · exact trivial
        · rename_i e heq; rw [heq] at hl; exact OutB.err hl
  case opnd =>
    intro ρ st e hρ hs
    cases e with
    | place x ps =>
      simp only [evalOpnd]
      refine OutB.bind (hS ρ st ps hρ hs) fun ss ρ1 st1 hss hρ1 hs1 => ?_
      exact OutB.bind (peek_ok P hρ1 hs1) fun v ρ2 st2 hv hρ2 hs2 =>
        ⟨by simp only [opCaps, placeCaps]; exact Bnd.append.2 ⟨hv, hss⟩, hρ2, hs2⟩
    | _ =>
      simp only [evalOpnd]
      refine OutB.bind (hE ρ st _ hρ hs) fun v ρ1 st1 hv hρ1 hs1 => ?_
      split
      · exact ⟨by simp only [opCaps, placeCaps]; simpa using hv, hρ1, hs1⟩
      · exact trivial
  case opnds =>
    intro ρ st es hρ hs
    cases es with
    | nil => simp only [evalOpnds]; exact ⟨by simp [opsCaps, Bnd.nil], hρ, hs⟩
    | cons e es =>
      simp only [evalOpnds]
      refine OutB.bind (hO ρ st e hρ hs) fun o ρ1 st1 ho hρ1 hs1 => ?_
      exact OutB.bind (hOs ρ1 st1 es hρ1 hs1) fun os ρ2 st2 hos hρ2 hs2 =>
        ⟨by simp only [opsCaps]; exact Bnd.append.2 ⟨ho, hos⟩, hρ2, hs2⟩
  case arms =>
    intro ρ st v arms hρ hs hv
    cases arms with
    | nil => simp only [evalArms]; exact hs
    | cons arm arms =>
      obtain ⟨p, g, body⟩ := arm
      simp only [evalArms]
      split
      · exact hM _ _ _ _ hρ hs hv
      · exact trivial
      · rename_i bs burn drop hm
        have hbs : Bnd A (envCaps (pushBinds bs ρ)) := by
          rw [pushBinds_caps]; exact Bnd.append.2 ⟨Bnd.mono (matchPat_caps P p v hm) hv, hρ⟩
        cases g with
        | none =>
          simp only
          split
          · rename_i st1 h
            exact popScope_ok (hE _ _ _ hbs (StB.of_out ((discardAll_out h).trans rfl) hs))
          · exact trivial
        | some ge =>
          simp only
          split
          · have hg := hE (pushBinds bs ρ) st ge hbs hs
            split
            · rename_i ρ1 st1 heq; rw [heq] at hg; exact popScope_ok (hE _ _ _ hg.2.1 hg.2.2)
            · rename_i ρ1 st1 heq; rw [heq] at hg
              exact OutB.bind (popEnv_ok hg.2.1 hg.2.2) fun _ ρ2 st2 _ hρ2 hs2 => hM _ _ _ _ hρ2 hs2 hv
            · exact trivial
            · rename_i c ρ1 st1 heq; rw [heq] at hg; exact popScope_ok hg
            · rename_i e heq; rw [heq] at hg; exact OutB.err hg
          · exact trivial
  case call =>
    intro ρ st owner ps names cvs body pre args hρ hs hcv hpre
    simp only [callWith]
    split
    case isFalse => exact trivial
    have ha := hAs ρ st ((ps.drop pre.length).map (·.2)) args hρ hs
    split
    · rename_i as ρ1 st1 heq; rw [heq] at ha
      have hall : Bnd A (argsCaps (pre ++ as)) := by rw [argsCaps_append]; exact Bnd.append.2 ⟨hpre, ha.1⟩
      split
      · exact afterCall_ok P (hE _ _ _ (Bnd.mono (frameOf_caps _ _ _ _) (Bnd.append.2 ⟨hall, hcv⟩)) ha.2.2)
          hall ha.2.1
      · exact trivial
    · rename_i c ρ1 st1 heq; rw [heq] at ha
      split
      · rename_i ρ2 st2 h
        obtain ⟨hρ2, hs2⟩ := unwindArgs_ok h hpre ha.2.1 ha.2.2
        exact ⟨ha.1, hρ2, hs2⟩
      · exact trivial
    · rename_i e heq; rw [heq] at ha; exact OutB.err ha
  case prim =>
    intro ρ st pf recv args hρ hs hr
    simp only [primCall]
    refine OutB.bind (hOs ρ st args hρ hs) fun os ρ1 st1 hos hρ1 hs1 => ?_
    split
    · exact primApply_ok P (Bnd.mono (capsL_ops os) hos) (Bnd.mono (headPlace_ops os) hos) hρ1 hs1
    · rename_i x ss
      refine OutB.bind (peek_ok P hρ1 hs1) fun v1 ρ2 st2 hv1 hρ2 hs2 => ?_
      exact primApply_ok P (by simp only [capsL]; exact Bnd.append.2 ⟨hv1, Bnd.mono (capsL_ops os) hos⟩)
        (by simpa [placeCaps, RecvB] using hr) hρ2 hs2
    · rename_i v0
      exact primApply_ok P (by simp only [capsL]; exact Bnd.append.2 ⟨hr, Bnd.mono (capsL_ops os) hos⟩)
        (by simp [placeCaps, Bnd.nil]) hρ1 hs1

theorem capSafe (n : Nat) : CapSafe A P n := by
  induction n with
  | zero => exact capSafe_zero P
  | succ n ih => exact capSafe_succ P ih

/-- **Capability safety.** Run any expression of any program, with any fuel,
in an environment whose capabilities are attenuations of `A`, after effects
that used only such capabilities: the result, the final environment and every
effect performed use only attenuations of `A`. Nothing forges authority. -/
theorem capability_safety (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (st : St) (e : Expr)
    (hρ : ∀ c ∈ envCaps ρ, ∃ a ∈ A, c ≤ a) (hst : ∀ ev ∈ st.out, ∃ a ∈ A, ev.cap ≤ a) :
    match eval P n ρ st e with
    | .ok v ρ' st' =>
      (∀ c ∈ v.caps, ∃ a ∈ A, c ≤ a) ∧ (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧
      (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .ctl _ ρ' st' => (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧ (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True := by
  have hs : StB A st := by
    intro c hc
    obtain ⟨ev, hev, rfl⟩ := List.mem_map.1 hc
    exact hst ev hev
  have h := (capSafe P (A := A) n).1 ρ st e hρ hs
  have toEv : ∀ st' : St, StB A st' → ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a :=
    fun st' h ev hev => h ev.cap (List.mem_map.2 ⟨ev, hev, rfl⟩)
  revert h
  cases eval P n ρ st e with
  | ok v ρ' st' => intro h; exact ⟨h.1, h.2.1, toEv _ h.2.2⟩
  | ctl c ρ' st' => intro h; exact ⟨h.2.1, toEv _ h.2.2⟩
  | err e => cases e <;> intro h <;> first | exact toEv _ h | trivial

/-- A program started with `Sys` (whose capabilities are `A`) never uses
authority beyond `A`, and an effect on a read-only `Fs` is done through a
read-only `Fs`. -/
theorem no_authority_escalation (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (e : Expr)
    (hρ : envCaps ρ ⊆ A) :
    match eval P n ρ {} e with
    | .ok _ _ st' | .ctl _ _ st' | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True := by
  have h := capability_safety P A n ρ {} e (fun c hc => ⟨c, hρ hc, Cap.le_refl c⟩) (by simp)
  revert h
  cases eval P n ρ {} e with
  | ok v ρ' st' => intro h; exact h.2.2
  | ctl c ρ' st' => intro h; exact h.2
  | err e => cases e <;> intro h <;> first | exact h | trivial

end

end Tenon

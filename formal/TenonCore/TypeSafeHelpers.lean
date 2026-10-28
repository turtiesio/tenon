/-
The invariant of the type-soundness proof (TypeSafe.lean) and the evaluator's
non-recursive helpers under it: reading, moving and writing places, builtins,
scopes, and the end of a call frame.
-/
import TenonCore.TypingPaths

namespace Tenon

section
variable (P : Prog) (prim : PrimSig)

/-- The context is deep enough for the enclosing frame and loop. -/
def SigOk (Δ : Sig) (Γ : Ctx) : Prop := Δ.fr ≤ Γ.length ∧ ∀ Γl, Δ.loop = some Γl → Γl.length ≤ Γ.length

/-- An early exit from an expression typed in `Γ`: a `return` carries a value
of the function's type and leaves the locals droppable and the frame finished;
a `break`/`continue` happens in a loop and leaves the loop's context. -/
def CtlOk (Δ : Sig) (Γ : Ctx) (ρ : Env) : Ctl → Prop
  | .ret v => Δ.exitOk = true ∧ ValTy P prim v Δ.ret ∧ ∃ Γx, Shape Γx Γ ∧ EnvOk P prim ρ Γx ∧ RetOk P Δ Γx
  | _ => ∃ Γl, Δ.loop = some Γl ∧ ∃ Γx, Shape Γx Γ ∧ EnvOk P prim ρ Γx ∧ LoopOk P Γl Γx

/-- **What a well-typed evaluation may end with**: a value (`Q`) and an
environment matching the context the judgement leaves; an early exit as
`CtlOk` says; a trap or running out of fuel. Never stuck, never unsupported. -/
def OutTy {α : Type} (Δ : Sig) (Γ Γ' : Ctx) (Q : α → Prop) : Out α → Prop
  | .ok a ρ _ => Q a ∧ EnvOk P prim ρ Γ' ∧ Shape Γ' Γ
  | .ctl c ρ _ => CtlOk P prim Δ Γ ρ c
  | .err (.stuck _ _) => False
  | .err (.unsup _) => False
  | .err _ => True

/-- A step that cannot exit early: done (in context `Γ`), trap or timeout. -/
def UnitOk (Γ : Ctx) : Out Unit → Prop
  | .ok _ ρ _ => EnvOk P prim ρ Γ
  | .ctl _ _ _ => False
  | .err (.stuck _ _) => False
  | .err (.unsup _) => False
  | .err _ => True

end

section
variable {P : Prog} {prim : PrimSig}

/-! ## The invariant's algebra -/

theorem CtlOk.rebase {Δ : Sig} {Γ1 Γ : Ctx} {ρ : Env} {c : Ctl} (h : CtlOk P prim Δ Γ1 ρ c) (hs : Shape Γ1 Γ) :
    CtlOk P prim Δ Γ ρ c := by
  cases c with
  | ret v => obtain ⟨h1, h2, Γx, h3, h4, h5⟩ := h; exact ⟨h1, h2, Γx, h3.trans hs, h4, h5⟩
  | brk => obtain ⟨Γl, h1, Γx, h3, h4, h5⟩ := h; exact ⟨Γl, h1, Γx, h3.trans hs, h4, h5⟩
  | cont => obtain ⟨Γl, h1, Γx, h3, h4, h5⟩ := h; exact ⟨Γl, h1, Γx, h3.trans hs, h4, h5⟩

theorem CtlOk.noExit {Δ : Sig} {Γ : Ctx} {ρ : Env} {c : Ctl} (h : CtlOk P prim Δ.noExit Γ ρ c) : False := by
  cases c with
  | ret v => exact absurd h.1 (by simp [Sig.noExit])
  | brk => obtain ⟨Γl, h1, -⟩ := h; simp [Sig.noExit] at h1
  | cont => obtain ⟨Γl, h1, -⟩ := h; simp [Sig.noExit] at h1

theorem OutTy.rebase {α} {Δ : Sig} {Γ1 Γ Γ2 : Ctx} {Q : α → Prop} {r : Out α} (h : OutTy P prim Δ Γ1 Γ2 Q r)
    (hs : Shape Γ1 Γ) : OutTy P prim Δ Γ Γ2 Q r := by
  cases r with
  | ok a ρ st => exact ⟨h.1, h.2.1, h.2.2.trans hs⟩
  | ctl c ρ st => exact CtlOk.rebase h hs
  | err e => cases e <;> exact h

theorem OutTy.mono {α} {Δ : Sig} {Γ Γ' : Ctx} {Q R : α → Prop} {r : Out α} (h : OutTy P prim Δ Γ Γ' Q r)
    (hq : ∀ a, Q a → R a) : OutTy P prim Δ Γ Γ' R r := by
  cases r with
  | ok a ρ st => exact ⟨hq a h.1, h.2⟩
  | ctl c ρ st => exact h
  | err e => cases e <;> exact h

theorem OutTy.bind {α β} {Δ : Sig} {Γ Γ1 Γ2 : Ctx} {Q : α → Prop} {R : β → Prop} {r : Out α}
    {k : α → Env → St → Out β} (h : OutTy P prim Δ Γ Γ1 Q r)
    (hk : ∀ a ρ st, Q a → EnvOk P prim ρ Γ1 → Shape Γ1 Γ → OutTy P prim Δ Γ1 Γ2 R (k a ρ st)) :
    OutTy P prim Δ Γ Γ2 R (r.bind k) := by
  cases r with
  | ok a ρ st => exact (hk a ρ st h.1 h.2.1 h.2.2).rebase h.2.2
  | ctl c ρ st => exact h
  | err e => cases e <;> exact h

/-- A tail typed under `TailSig` (no exits while a linear temporary is held). -/
theorem OutTy.tail {α} {Δ Δ' : Sig} {t : Ty} {Γ Γ' : Ctx} {Q : α → Prop} {r : Out α} (hΔ : TailSig P Δ Δ' t)
    (h : OutTy P prim Δ' Γ Γ' Q r) : OutTy P prim Δ Γ Γ' Q r := by
  rcases hΔ with ⟨rfl, -⟩ | rfl
  · exact h
  · cases r with
    | ok a ρ st => exact h
    | ctl c ρ st => exact (CtlOk.noExit h).elim
    | err e => cases e <;> exact h

theorem OutTy.noExit_ctl {α} {Δ : Sig} {Γ Γ' : Ctx} {Q : α → Prop} {c : Ctl} {ρ : Env} {st : St}
    (h : OutTy P prim Δ.noExit Γ Γ' Q (.ctl c ρ st)) : False := CtlOk.noExit h

theorem OutTy.stuck {α} {Δ : Sig} {Γ Γ' : Ctx} {Q : α → Prop} {k : Stuck} {w : String}
    (h : OutTy P prim Δ Γ Γ' Q (.err (.stuck k w))) : False := h

theorem OutTy.err_of {α β} {Δ : Sig} {Γ Γ' Γ2 Γ3 : Ctx} {Q : α → Prop} {R : β → Prop} {e : Err}
    (h : OutTy P prim Δ Γ Γ' Q (.err e)) : OutTy P prim Δ Γ2 Γ3 R (.err e) := by
  cases e <;> exact h

theorem OutTy.trap {α} {Δ : Sig} {Γ Γ' : Ctx} {Q : α → Prop} {m : String} {st : St} :
    OutTy P prim Δ Γ Γ' Q (.err (.trap m st)) := trivial

theorem OutTy.ok {α} {Δ : Sig} {Γ Γ' : Ctx} {Q : α → Prop} {a : α} {ρ : Env} {st : St} (hq : Q a)
    (hρ : EnvOk P prim ρ Γ') (hs : Shape Γ' Γ) : OutTy P prim Δ Γ Γ' Q (.ok a ρ st) := ⟨hq, hρ, hs⟩

theorem OutTy.pathErr {α} {Δ : Sig} {Γ Γ' : Ctx} {Q : α → Prop} {st : St} {pe : PErr} (h : PathOk (fun _ : Unit => True) (.error pe)) :
    OutTy P prim Δ Γ Γ' Q (pathErr st pe) := by
  cases pe with
  | trap m => trivial
  | stuck w => exact h.elim

/-! ## Splitting contexts at the frame and the loop -/

theorem RetOk.split {Δ : Sig} {Γ : Ctx} (h : RetOk P Δ Γ) (hl : Δ.fr ≤ Γ.length) :
    ∃ Γa Γb, Γ = Γa ++ Γb ∧ Γb.length = Δ.fr ∧ Ctx.noLinear P Γa ∧ Δ.fin Γb :=
  ⟨_, _, (List.take_append_drop _ _).symm, by simp; omega, h.1, h.2⟩

theorem RetOk.of_split {Δ : Sig} {Γa Γb : Ctx} (hl : Γb.length = Δ.fr) (h1 : Ctx.noLinear P Γa) (h2 : Δ.fin Γb) :
    RetOk P Δ (Γa ++ Γb) := by
  have : (Γa ++ Γb).length - Δ.fr = Γa.length := by simp; omega
  unfold RetOk; rw [this, List.take_left', List.drop_left'] <;> first | rfl | exact ⟨h1, h2⟩

theorem LoopOk.split {Γl Γ : Ctx} (h : LoopOk P Γl Γ) (hl : Γl.length ≤ Γ.length) :
    ∃ Γa, Γ = Γa ++ Γl ∧ Ctx.noLinear P Γa := by
  refine ⟨Γ.take (Γ.length - Γl.length), ?_, h.1⟩
  conv => lhs; rw [← List.take_append_drop (Γ.length - Γl.length) Γ]
  rw [h.2]

theorem LoopOk.of_split {Γa Γl : Ctx} (h1 : Ctx.noLinear P Γa) : LoopOk P Γl (Γa ++ Γl) := by
  have : (Γa ++ Γl).length - Γl.length = Γa.length := by simp
  unfold LoopOk; rw [this, List.take_left', List.drop_left'] <;> first | rfl | exact ⟨h1, rfl⟩

theorem noLinear_take_drop {Γ : Ctx} {k : Nat} (h : Ctx.noLinear P Γ) :
    Ctx.noLinear P (Γ.take k) ∧ Ctx.noLinear P (Γ.drop k) := by
  rw [← List.take_append_drop k Γ] at h
  exact noLinear_append.1 h

/-- Popping `Γb.length` locals that are part of a droppable prefix `Γa`. -/
theorem pop_prefix (hA : AdtsOk P) {Γa Γr Γb Γ : Ctx} {ρ : Env} (hρ : EnvOk P prim ρ (Γa ++ Γr))
    (hs : Shape (Γa ++ Γr) (Γb ++ Γ)) (hn : Ctx.noLinear P Γa) (hl : Γb.length ≤ Γa.length) (st : St) :
    ∃ st', popEnv Γb.length ρ st = .ok () (ρ.drop Γb.length) st' ∧
      EnvOk P prim (ρ.drop Γb.length) (Γa.drop Γb.length ++ Γr) ∧ Shape (Γa.drop Γb.length ++ Γr) Γ ∧
      Ctx.noLinear P (Γa.drop Γb.length) := by
  have hsplit : Γa ++ Γr = Γa.take Γb.length ++ (Γa.drop Γb.length ++ Γr) := by
    rw [← List.append_assoc, List.take_append_drop]
  have hlt : (Γa.take Γb.length).length = Γb.length := by simp; omega
  rw [hsplit] at hρ hs
  obtain ⟨st', hp, hρ'⟩ := popEnv_typed hA hρ (noLinear_take_drop hn).1 st
  rw [hlt] at hp hρ'
  exact ⟨st', hp, hρ', (Shape.unappend hlt hs).2, (noLinear_take_drop hn).2⟩

/-- Ending `k` scopes on an early exit keeps `CtlOk` (the popped variables are locals). -/
theorem CtlOk.pop (hA : AdtsOk P) {Δ : Sig} {Γb Γ : Ctx} {ρ : Env} {c : Ctl} (h : CtlOk P prim Δ (Γb ++ Γ) ρ c)
    (hsig : SigOk Δ Γ) (st : St) :
    ∃ st', popEnv Γb.length ρ st = .ok () (ρ.drop Γb.length) st' ∧ CtlOk P prim Δ Γ (ρ.drop Γb.length) c := by
  cases c with
  | ret v =>
    obtain ⟨h1, h2, Γx, hs, hρ, hr⟩ := h
    have hlx := hs.length; simp at hlx
    obtain ⟨Γa, Γf, rfl, hfl, hn, hfin⟩ := hr.split (by have := hsig.1; omega)
    simp at hlx
    obtain ⟨st', hp, hρ', hs', hn'⟩ := pop_prefix hA hρ hs hn (by have := hsig.1; omega) st
    exact ⟨st', hp, h1, h2, _, hs', hρ', RetOk.of_split hfl hn' hfin⟩
  | brk =>
    obtain ⟨Γl, h1, Γx, hs, hρ, hr⟩ := h
    have hlx := hs.length; simp at hlx
    have hll := hsig.2 Γl h1
    obtain ⟨Γa, rfl, hn⟩ := hr.split (by omega)
    simp at hlx
    obtain ⟨st', hp, hρ', hs', hn'⟩ := pop_prefix hA hρ hs hn (by omega) st
    exact ⟨st', hp, Γl, h1, _, hs', hρ', LoopOk.of_split hn'⟩
  | cont =>
    obtain ⟨Γl, h1, Γx, hs, hρ, hr⟩ := h
    have hlx := hs.length; simp at hlx
    have hll := hsig.2 Γl h1
    obtain ⟨Γa, rfl, hn⟩ := hr.split (by omega)
    simp at hlx
    obtain ⟨st', hp, hρ', hs', hn'⟩ := pop_prefix hA hρ hs hn (by omega) st
    exact ⟨st', hp, Γl, h1, _, hs', hρ', LoopOk.of_split hn'⟩

/-- Ending a scope of `k` variables (a `let`, a pattern's names). -/
theorem popScope_ty (hA : AdtsOk P) {Δ : Sig} {Γb Γbo Γ Γ' : Ctx} {Q : Val → Prop} {r : Out Val}
    (h : OutTy P prim Δ (Γb ++ Γ) (Γbo ++ Γ') Q r) (hl : Γbo.length = Γb.length) (hn : Ctx.noLinear P Γbo)
    (hsig : SigOk Δ Γ) : OutTy P prim Δ Γ Γ' Q (popScope Γb.length r) := by
  cases r with
  | ok v ρ st =>
    obtain ⟨hq, hρ, hs⟩ := h
    rw [← hl]
    obtain ⟨st', hp, hρ'⟩ := popEnv_typed hA hρ hn st
    simp only [popScope, hp, Out.bind]
    exact ⟨hq, hρ', (Shape.unappend hl hs).2⟩
  | ctl c ρ st =>
    obtain ⟨st', hp, hc⟩ := CtlOk.pop hA h hsig st
    simp only [popScope, hp, Out.bind]
    exact hc
  | err e => exact OutTy.err_of h

/-! ## Reading places -/

theorem update_lookup_self : ∀ {ρ : Env} {x : String} {s : Option Val}, lookup ρ x = some s → Tenon.update ρ x s = ρ
  | [], _, _, h => by simp [lookup] at h
  | (y, s0) :: ρ, x, s, h => by
    simp only [lookup] at h
    simp only [Tenon.update]
    split
    · rename_i hy; rw [if_pos hy] at h; simp at h; rw [h]
    · rename_i hy; rw [if_neg hy] at h; rw [update_lookup_self h]


theorem peek_ty (hA : AdtsOk P) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) (ha : en.avail = true) {ss : List Step} {t : Ty} (hss : StepsTy P prim en.ty ss t)
    (st : St) : (∃ v, peek P ρ st x ss = .ok v ρ st ∧ ValTy P prim v t) ∨ ∃ m, peek P ρ st x ss = .err (.trap m st) := by
  obtain ⟨v0, hl, hv0⟩ := hρ.lookup_avail hf ha
  have hg := getPath_ty hA hss hv0
  unfold peek; rw [hl]; simp only
  revert hg
  cases getPath P v0 ss with
  | ok w => intro hw; exact Or.inl ⟨w, rfl, hw⟩
  | error e => cases e with
    | trap m => intro _; exact Or.inr ⟨m, rfl⟩
    | stuck w => intro h; exact h.elim

theorem readPlace_copy (hA : AdtsOk P) {Δ : Sig} {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) (ha : en.avail = true) {ss : List Step} {t : Ty} (hss : StepsTy P prim en.ty ss t)
    (hc : t.copyable P) (st : St) : OutTy P prim Δ Γ Γ (ValTy P prim · t) (readPlace P ρ st x ss) := by
  unfold readPlace
  rcases peek_ty hA hρ hf ha hss st with ⟨v, hp, hv⟩ | ⟨m, hp⟩
  · rw [hp]; simp only [hv.toks_copy hA hc, ite_true]; exact ⟨hv, hρ, rfl⟩
  · rw [hp]; trivial

theorem readPlace_move (hA : AdtsOk P) {Δ : Sig} {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) (ha : en.avail = true) (st : St) :
    OutTy P prim Δ Γ (Γ.setAvail x false) (ValTy P prim · en.ty) (readPlace P ρ st x []) := by
  obtain ⟨v0, hl, hv0⟩ := hρ.lookup_avail hf ha
  unfold readPlace peek; rw [hl]; simp only [getPath]
  split
  · rename_i ht
    refine ⟨hv0, ?_, Shape.setAvail _ _ _⟩
    have := hρ.update false (some v0) hf ⟨fun h => by simp at h, fun _ w hw => by simp at hw; rw [← hw]; exact ht⟩
    rwa [show Tenon.update ρ x (some v0) = ρ from ?_] at this
    exact update_lookup_self hl
  · simp only [ite_true]
    exact ⟨hv0, hρ.update false none hf ⟨fun h => by simp at h, fun _ w hw => by simp at hw⟩, Shape.setAvail _ _ _⟩

/-! ## Arguments -/

/-- An evaluated argument, against its mode and parameter type, the caller's
context after all arguments: by value it is the value; by `ref`/`mut` a copy of
a place of a copyable type that is still in scope (it is written back). -/
inductive ArgOk (P : Prog) (prim : PrimSig) (Γ : Ctx) : Mode → ArgV → Ty → Prop
  | val {v t} : ValTy P prim v t → ArgOk P prim Γ .val ⟨v, .none⟩ t
  | place {m v t x ss en} : m ≠ .val → ValTy P prim v t → t.copyable P → Γ.find x = some en → en.avail = true →
      StepsTy P prim en.ty ss t → ArgOk P prim Γ m ⟨v, .place x ss⟩ t

inductive ArgsOk (P : Prog) (prim : PrimSig) (Γ : Ctx) : List Mode → List ArgV → List Ty → Prop
  | nil : ArgsOk P prim Γ [] [] []
  | cons {m ms a as t ts} : ArgOk P prim Γ m a t → ArgsOk P prim Γ ms as ts → ArgsOk P prim Γ (m :: ms) (a :: as) (t :: ts)

theorem ArgOk.valTy {Γ : Ctx} {m : Mode} {a : ArgV} {t : Ty} (h : ArgOk P prim Γ m a t) : ValTy P prim a.v t := by
  cases h <;> assumption

theorem ArgOk.noLin (hA : AdtsOk P) {Γ : Ctx} {m : Mode} {a : ArgV} {t : Ty} (h : ArgOk P prim Γ m a t)
    (hl : m = .val → ¬ t.linear P) : a.v.hasLin = false := by
  cases h with
  | val hv => exact hv.noLin hA (hl rfl)
  | place _ hv hc => exact hasLin_of_toks (hv.toks_copy hA hc)

theorem ArgsOk.append {Γ : Ctx} {ms1 ms2 : List Mode} {as1 as2 : List ArgV} {ts1 ts2 : List Ty}
    (h1 : ArgsOk P prim Γ ms1 as1 ts1) (h2 : ArgsOk P prim Γ ms2 as2 ts2) :
    ArgsOk P prim Γ (ms1 ++ ms2) (as1 ++ as2) (ts1 ++ ts2) := by
  induction h1 with
  | nil => exact h2
  | cons ha _ ih => exact .cons ha ih

theorem ArgsOk.length {Γ : Ctx} {ms : List Mode} {as : List ArgV} {ts : List Ty} (h : ArgsOk P prim Γ ms as ts) :
    as.length = ms.length ∧ ts.length = ms.length := by
  induction h with
  | nil => exact ⟨rfl, rfl⟩
  | cons _ _ ih => simp [ih.1, ih.2]

theorem unwindArg_typed {a : ArgV} (hw : ∀ x, a.wb ≠ .moved x) (hl : a.v.hasLin = false) (ρ : Env) (st : St) :
    ∃ st', unwindArg a ρ st = some (ρ, st') := by
  obtain ⟨st', h⟩ := discard_ok hl st
  unfold unwindArg
  split
  · rename_i x hx; exact absurd hx (hw x)
  · rw [h]; exact ⟨st', rfl⟩

theorem ArgOk.not_moved {Γ : Ctx} {m : Mode} {a : ArgV} {t : Ty} (h : ArgOk P prim Γ m a t) : ∀ x, a.wb ≠ .moved x := by
  cases h <;> simp

theorem unwindArgs_typed : ∀ {as : List ArgV}, (∀ a ∈ as, (∀ x, a.wb ≠ .moved x) ∧ a.v.hasLin = false) →
    ∀ (ρ : Env) (st : St), ∃ st', unwindArgs as ρ st = some (ρ, st')
  | [], _, ρ, st => ⟨st, rfl⟩
  | a :: as, h, ρ, st => by
    obtain ⟨st1, h1⟩ := unwindArg_typed (h a (by simp)).1 (h a (by simp)).2 ρ st
    obtain ⟨st2, h2⟩ := unwindArgs_typed (as := as) (fun b hb => h b (by simp [hb])) ρ st1
    exact ⟨st2, by simp [unwindArgs, h1, h2]⟩

theorem placeArg_val {Δ : Sig} {Γ Γ' : Ctx} {Q : Val → Prop} {ρ : Env} {st : St} {x : String} {ss : List Step}
    (h : OutTy P prim Δ Γ Γ' Q (readPlace P ρ st x ss)) :
    OutTy P prim Δ Γ Γ' (fun a : ArgV => Q a.v ∧ a.wb = .none) (placeArg P ρ st .val x ss) := by
  unfold placeArg
  revert h
  cases readPlace P ρ st x ss with
  | ok v ρ1 st1 => intro h; exact ⟨⟨h.1, rfl⟩, h.2⟩
  | ctl c ρ1 st1 => intro h; exact h
  | err e => intro h; cases e <;> exact h

theorem placeArg_ref (hA : AdtsOk P) {Δ : Sig} {m : Mode} (hm : m ≠ .val) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ)
    {x : String} {en : Entry} (hf : Γ.find x = some en) (ha : en.avail = true) {ss : List Step} {t : Ty}
    (hss : StepsTy P prim en.ty ss t) (hc : t.copyable P) (st : St) :
    OutTy P prim Δ Γ Γ (fun a : ArgV => ValTy P prim a.v t ∧ a.wb = .place x ss) (placeArg P ρ st m x ss) := by
  have key : placeArg P ρ st m x ss = match peek P ρ st x ss with
      | .ok v ρ1 st1 =>
        if v.toks = [] then .ok ⟨v, .place x ss⟩ ρ1 st1
        else if ss = [] then .ok ⟨v, .moved x⟩ (update ρ1 x none) st1
        else stuckL s!"an obligation in a part of '{x}' cannot be passed by ref or mut"
      | .ctl c ρ1 st1 => .ctl c ρ1 st1
      | .err e => .err e := by
    cases m with
    | val => exact absurd rfl hm
    | ref => rfl
    | «mut» => rfl
  rw [key]
  rcases peek_ty hA hρ hf ha hss st with ⟨v, hp, hv⟩ | ⟨mm, hp⟩
  · rw [hp]; simp only [hv.toks_copy hA hc, ite_true]; exact ⟨⟨hv, rfl⟩, hρ, rfl⟩
  · rw [hp]; trivial

/-! ## Assignment -/

theorem assignAt_whole (hA : AdtsOk P) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) {v : Val} (hv : ValTy P prim v en.ty) (hl : en.avail = true → ¬ en.ty.linear P)
    (st : St) : ∃ st', assignAt P ρ st x [] v = .ok .unit (Tenon.update ρ x (some v)) st' ∧
      EnvOk P prim (Tenon.update ρ x (some v)) (Γ.setAvail x true) := by
  obtain ⟨s, hlk, hs⟩ := hρ.lookup hf
  have hρ' := hρ.update true (some v) hf ⟨fun _ => ⟨v, rfl, hv⟩, fun h => by simp at h⟩
  unfold assignAt
  rw [hlk]
  cases s with
  | none => exact ⟨st, rfl, hρ'⟩
  | some old =>
    obtain ⟨st1, h1⟩ := discard_ok (hs.noLin hA hl old rfl) st
    simp only [h1]
    exact ⟨st1, rfl, hρ'⟩

theorem assignAt_part (hA : AdtsOk P) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) (ha : en.avail = true) {ss : List Step} {t : Ty} (hss : StepsTy P prim en.ty ss t)
    (hc : t.copyable P) {v : Val} (hv : ValTy P prim v t) (st : St) :
    (∃ ρ' st', assignAt P ρ st x ss v = .ok .unit ρ' st' ∧ EnvOk P prim ρ' Γ) ∨
    ∃ m st', assignAt P ρ st x ss v = .err (.trap m st') := by
  obtain ⟨v0, hlk, hv0⟩ := hρ.lookup_avail hf ha
  cases ss with
  | nil =>
    cases hss
    left
    obtain ⟨st1, h1⟩ := discard_ok_of_toks (hv0.toks_copy hA hc) st
    unfold assignAt; rw [hlk]; simp only [h1]
    exact ⟨_, st1, rfl, hρ.update_val hf ha hv⟩
  | cons s ss =>
    have ho := oldAt_ty hA hss hv0
    have hsp := setPath_ty hA hss hv0 hv
    unfold assignAt; rw [hlk]; simp only
    revert ho
    cases oldAt P v0 (s :: ss) with
    | ok o =>
      intro ho
      have hd : ∀ w, o = some w → w.hasLin = false := fun w hw => hasLin_of_toks ((ho w hw).toks_copy hA hc)
      obtain ⟨st1, h1⟩ := discardSlot_ok hd st
      simp only [h1]
      revert hsp
      cases setPath P v0 (s :: ss) v with
      | ok v1 => intro hv1; exact Or.inl ⟨_, st1, rfl, hρ.update_val hf ha hv1⟩
      | error e => cases e with
        | trap m => intro _; exact Or.inr ⟨m, st1, rfl⟩
        | stuck w => intro h; exact h.elim
    | error e => cases e with
      | trap m => intro _; exact Or.inr ⟨m, st, rfl⟩
      | stuck w => intro h; exact h.elim

/-! ## Builtins -/

theorem primApply_ty (hA : AdtsOk P) {Δ : Sig} {pf : List Val → Nat → PrimRes} {ts : List Ty} {t : Ty}
    (hpf : PfOk P prim pf ts t) (hc : t.copyable P) {vs : List Val} (hl : vs.length = ts.length)
    (hvs : ∀ q ∈ vs.zip ts, ValTy P prim q.1 q.2) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ)
    {sp : Option (String × List Step)}
    (hsp : ∀ x ss, sp = some (x, ss) → ∃ en t0, Γ.find x = some en ∧ en.avail = true ∧ ts.head? = some t0 ∧
      StepsTy P prim en.ty ss t0) (st : St) :
    OutTy P prim Δ Γ Γ (ValTy P prim · t) (primApply P ρ st pf vs sp) := by
  have h := hpf vs st.world hl hvs
  unfold primApply
  revert h
  cases pf vs st.world with
  | ok v self evs w =>
    intro h
    obtain ⟨hv, hg, hself⟩ := h
    simp only [hg, Bool.not_true, Bool.false_eq_true, ite_false, hv.toks_copy hA hc, ite_true]
    cases self with
    | none => exact ⟨hv, hρ, rfl⟩
    | some s =>
      obtain ⟨t0, ht0, hs, hc0⟩ := hself s rfl
      cases sp with
      | none => simp only [hs.toks_copy hA hc0, ite_true]; exact ⟨hv, hρ, rfl⟩
      | some xs =>
        obtain ⟨x, ss⟩ := xs
        obtain ⟨en, t0', hf, ha, ht0', hss⟩ := hsp x ss rfl
        rw [ht0] at ht0'; simp only [Option.some.injEq] at ht0'; subst ht0'
        obtain ⟨v0, hlk, hv0⟩ := hρ.lookup_avail hf ha
        simp only [hlk]
        have hg := getPath_ty hA hss hv0
        revert hg
        cases getPath P v0 ss with
        | ok old =>
          intro hold
          simp only [hold.toks_copy hA hc0, hs.toks_copy hA hc0, ite_true]
          have hsp' := setPath_ty hA hss hv0 hs
          revert hsp'
          cases setPath P v0 ss s with
          | ok v1 => intro hv1; exact ⟨hv, hρ.update_val hf ha hv1, rfl⟩
          | error e => cases e with
            | trap m => intro _; trivial
            | stuck w => intro h; exact h.elim
        | error e => cases e with
          | trap m => intro _; trivial
          | stuck w => intro h; exact h.elim
  | trap m => intro _; trivial
  | stuck w => intro h; exact h.elim
  | unsup w => intro h; exact h.elim

/-! ## The end of a call -/

theorem hasLin_adt_payload {s : String} {tag : Nat} {tok : Option Tok} {vs : List Val}
    (h : (Val.adt s tag tok vs).hasLin = false) : ∀ w ∈ vs, w.hasLin = false := by
  intro w hw
  simp only [Val.hasLin, List.any_eq_false, Val.toks, List.mem_append] at h ⊢
  intro τ hτ
  exact h τ (Or.inr (mem_toksL.2 ⟨w, hw, hτ⟩))

theorem endParam_ok (hA : AdtsOk P) {owner : Option String} {p : String} {e : Entry} {slot : Option Val}
    (hs : SlotOk P prim e slot) (hfin : FinEntry P owner (p, .val) e) (st : St) :
    ∃ st', endParam owner (decide (p = "self")) slot st = some st' := by
  cases ha : e.avail
  · -- moved: nothing, or a value without obligations
    have h0 := hs.2 ha
    have hnl : ∀ v, slot = some v → v.hasLin = false := fun v hv => hasLin_of_toks (h0 v hv)
    unfold endParam
    split
    · rename_i o s' tag τ vs
      have := h0 _ rfl; simp [Val.toks] at this
    · exact discardSlot_ok hnl st
  · obtain ⟨v, rfl, hv⟩ := hs.1 ha
    by_cases hl : e.ty.linear P
    · obtain ⟨hp, o, d, args, rfl, hty, hd, hk, hfl⟩ := ((hfin ha).resolve_left (by simpa using hl))
      rw [hty] at hv
      cases hv with
      | @adt _ tag tok vs d' name ts _ hd' hvar ha' hlen hvs htok =>
        rw [hd] at hd'; cases hd'
        cases tok with
        | none => revert htok hk; cases d.kind <;> simp [TokOk]
        | some τ =>
          subst hp
          simp only [endParam, decide_true, ite_true]
          apply discardAll_ok
          intro w hw
          obtain ⟨u, hu⟩ := mem_zip_left (bs := substL args ts) (by rw [substL_length]; exact hlen) hw
          obtain ⟨ft, hft, rfl⟩ := mem_substL (List.of_mem_zip hu).2
          exact (hvs _ hu).noLin hA (hfl _ (List.mem_of_getElem? hvar) ft hft)
    · have hnl := hv.noLin hA hl
      unfold endParam
      split
      · rename_i o s' tag τ vs heq
        simp only [Option.some.injEq] at heq; subst heq
        split
        · exact discardAll_ok (hasLin_adt_payload hnl) _
        · exact discard_ok hnl st
      · exact discardSlot_ok (fun w hw => by simp at hw; subst hw; exact hnl) st

theorem writeBack_place (hA : AdtsOk P) {ρ : Env} {Γ : Ctx} (hρ : EnvOk P prim ρ Γ) {x : String} {en : Entry}
    (hf : Γ.find x = some en) (ha : en.avail = true) {ss : List Step} {t : Ty} (hss : StepsTy P prim en.ty ss t)
    (hc : t.copyable P) {v : Val} (hv : ValTy P prim v t) (st : St) :
    UnitOk P prim Γ (writeBack P ρ st (.place x ss) v) := by
  obtain ⟨v0, hlk, hv0⟩ := hρ.lookup_avail hf ha
  unfold writeBack; simp only; rw [hlk]; simp only
  have hg := getPath_ty hA hss hv0
  revert hg
  cases getPath P v0 ss with
  | ok old =>
    intro hold
    simp only [hold.toks_copy hA hc, ite_true]
    have hsp := setPath_ty hA hss hv0 hv
    revert hsp
    cases setPath P v0 ss v with
    | ok v1 => intro hv1; exact hρ.update_val hf ha hv1
    | error e => cases e with
      | trap m => intro _; trivial
      | stuck w => intro h; exact h.elim
  | error e => cases e with
    | trap m => intro _; trivial
    | stuck w => intro h; exact h.elim

theorem paramsCtx_length : ∀ (ps : List (String × Mode)) (tys : List Ty), tys.length = ps.length →
    (paramsCtx ps tys).length = ps.length
  | [], [], _ => rfl
  | p :: ps, t :: tys, h => by simp [paramsCtx, paramsCtx_length ps tys (by simpa using h)]
  | [], _ :: _, h | _ :: _, [], h => by simp at h

theorem endFrame_ty (hA : AdtsOk P) (owner : Option String) {Γc : Ctx} :
    ∀ (ps : List (String × Mode)) (as : List ArgV) (fr ρc : Env) (Γx : Ctx) (tys : List Ty) (st : St),
    EnvOk P prim fr Γx → Shape Γx (paramsCtx ps tys) → tys.length = ps.length → FinFn P owner ps Γx →
    ArgsOk P prim Γc (ps.map (·.2)) as tys → EnvOk P prim ρc Γc →
    UnitOk P prim Γc (endFrame P owner ps as fr ρc st)
  | [], [], fr, ρc, Γx, [], st, hfr, hs, _, _, _, hρc => by
    have : Γx = [] := by have := hs.length; simp [paramsCtx] at this; exact this
    subst this
    have hfr0 : ∀ p ∈ fr, ∀ v, p.2 = some v → v.toks = [] := by cases fr <;> simpa [EnvOk] using hfr
    have hall : ∀ v ∈ fr.filterMap (·.2), v.hasLin = false := by
      intro v hv
      obtain ⟨p, hp, hpv⟩ := List.mem_filterMap.1 hv
      exact hasLin_of_toks (hfr0 p hp v hpv)
    obtain ⟨st', h⟩ := discardAll_ok hall st
    simp only [endFrame, h]; exact hρc
  | (p, m) :: ps, a :: as, (y, slot) :: fr, ρc, e :: Γx, ty :: tys, st, hfr, hs, hl, hfin, hargs, hρc => by
    obtain ⟨-, hslot, hfr'⟩ := hfr
    simp only [paramsCtx] at hs
    obtain ⟨hk, hs'⟩ := Shape.uncons hs
    have hty : e.ty = ty := Entry.key_ty hk
    obtain ⟨hfe, hfin'⟩ := hfin
    cases hargs with
    | cons ha hargs' =>
      have ih := fun st' ρc' (h : EnvOk P prim ρc' Γc) =>
        endFrame_ty hA owner ps as fr ρc' Γx tys st' hfr' hs' (by simpa using hl) hfin' hargs' h
      cases m with
      | val =>
        obtain ⟨st', h⟩ := endParam_ok hA hslot hfe st
        simp only [endFrame, h]
        exact ih st' ρc hρc
      | ref =>
        have hav : e.avail = true := hfe
        obtain ⟨v, rfl, hv⟩ := hslot.1 hav
        cases ha with
        | place _ _ hc hf hea hss =>
          simp only [endFrame]
          have hw := writeBack_place hA hρc hf hea hss hc (hty ▸ hv) st
          revert hw
          cases writeBack P ρc st _ v with
          | ok u ρ' st' => intro hw; exact ih st' ρ' hw
          | ctl c ρ' st' => intro hw; exact hw.elim
          | err e => intro hw; cases e <;> exact hw
      | «mut» =>
        have hav : e.avail = true := hfe
        obtain ⟨v, rfl, hv⟩ := hslot.1 hav
        cases ha with
        | place _ _ hc hf hea hss =>
          simp only [endFrame]
          have hw := writeBack_place hA hρc hf hea hss hc (hty ▸ hv) st
          revert hw
          cases writeBack P ρc st _ v with
          | ok u ρ' st' => intro hw; exact ih st' ρ' hw
          | ctl c ρ' st' => intro hw; exact hw.elim
          | err e => intro hw; cases e <;> exact hw
  | [], _ :: _, _, _, _, _, _, _, _, _, _, hargs, _ => by cases hargs
  | _ :: _, [], _, _, _, _, _, _, _, _, _, hargs, _ => by cases hargs
  | _ :: _, _ :: _, [], _, Γx, tys, _, hfr, hs, hl, _, _, _ => by
    cases Γx with
    | nil => have := hs.length; cases tys <;> simp_all [paramsCtx]
    | cons => simp [EnvOk] at hfr
  | _ :: _, _ :: _, _ :: _, _, [], tys, _, _, hs, hl, _, _, _ => by
    have := hs.length; cases tys <;> simp_all [paramsCtx]
  | [], [], _, _, _, _ :: _, _, _, _, hl, _, _, _ => by simp at hl
  | _ :: _, _ :: _, _ :: _, _, _ :: _, [], _, _, _, hl, _, _, _ => by simp at hl

theorem afterCall_ty (hA : AdtsOk P) {Δ : Sig} {owner : Option String} {ps : List (String × Mode)} {tys : List Ty}
    {r : Ty} {Γb Γ Γc : Ctx} {as : List ArgV} {ρc : Env} {res : Out Val}
    (hres : OutTy P prim (fnSig P owner ps r) (paramsCtx ps tys) Γb (ValTy P prim · r) res)
    (hfin : FinFn P owner ps Γb) (hl : tys.length = ps.length)
    (hargs : ArgsOk P prim Γc (ps.map (·.2)) as tys) (hρc : EnvOk P prim ρc Γc) (hsc : Shape Γc Γ) :
    OutTy P prim Δ Γ Γc (ValTy P prim · r) (afterCall P owner ps as ρc res) := by
  cases res with
  | ok v fr st =>
    obtain ⟨hv, hfr, hs⟩ := hres
    have he := endFrame_ty hA owner ps as fr ρc Γb tys st hfr hs hl hfin hargs hρc
    simp only [afterCall]
    revert he
    cases endFrame P owner ps as fr ρc st with
    | ok u ρ' st' => intro he; exact ⟨hv, he, hsc⟩
    | ctl c ρ' st' => intro he; exact he.elim
    | err e => intro he; cases e <;> exact he
  | ctl c fr st =>
    cases c with
    | ret v =>
      obtain ⟨-, hv, Γx, hs, hfr, hr⟩ := hres
      have hlx : Γx.length = ps.length := by rw [hs.length, paramsCtx_length ps tys hl]
      have hfx : FinFn P owner ps Γx := by
        have := hr.2; simp only [fnSig, hlx, Nat.sub_self, List.drop_zero] at this; exact this
      have he := endFrame_ty hA owner ps as fr ρc Γx tys st hfr hs hl hfx hargs hρc
      simp only [afterCall]
      revert he
      cases endFrame P owner ps as fr ρc st with
      | ok u ρ' st' => intro he; exact ⟨hv, he, hsc⟩
      | ctl c ρ' st' => intro he; exact he.elim
      | err e => intro he; cases e <;> exact he
    | brk => obtain ⟨Γl, h, -⟩ := hres; simp [fnSig] at h
    | cont => obtain ⟨Γl, h, -⟩ := hres; simp [fnSig] at h
  | err e => cases e <;> exact hres

/-- A call frame matches the parameters' context (the captured values below hold no obligation). -/
theorem frameOf_ty {Γc : Ctx} {names : List String} {cvs : List Val} (hcv : toksL cvs = []) :
    ∀ (ps : List (String × Mode)) (as : List ArgV) (tys : List Ty), ArgsOk P prim Γc (ps.map (·.2)) as tys →
    EnvOk P prim (frameOf ps as names cvs) (paramsCtx ps tys)
  | [], [], [], _ => by
    simp only [frameOf, List.zip_nil_left, List.map_nil, List.nil_append, paramsCtx, EnvOk]
    intro p hp v hv
    obtain ⟨⟨x, w⟩, hxw, rfl⟩ := List.mem_map.1 hp
    simp at hv; subst hv
    exact toksL_nil_iff.1 hcv _ (List.of_mem_zip hxw).2
  | (p, m) :: ps, a :: as, t :: tys, h => by
    cases h with
    | cons ha h' =>
      simp only [frameOf, List.zip_cons_cons, List.map_cons, List.cons_append, paramsCtx]
      exact ⟨rfl, ⟨fun _ => ⟨a.v, rfl, ha.valTy⟩, fun h => by simp at h⟩, frameOf_ty hcv ps as tys h'⟩
  | [], _ :: _, _, h | [], _, _ :: _, h | _ :: _, [], _, h | _ :: _, _, [], h => by cases h

end

end Tenon


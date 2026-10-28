/-
Facts about the static semantics (Typing.lean) used by the soundness proof
(TypeSafe.lean): kinds bound the obligations a value holds, contexts and
environments stay in step, typed paths and patterns never get stuck.
-/
import TenonCore.Typing
import TenonCore.LinearLemmas

namespace Tenon

/-! ## Kinds bound obligations -/

/-- The tokens a value of a type of kind `k` may hold. -/
def Kind.allows : Kind → Tok → Prop
  | .copy, _ => False
  | .unique, t => t.lin = false
  | .linear, _ => True

theorem Kind.le_refl (k : Kind) : Kind.le k k := Nat.le_refl _

theorem Kind.le_trans {a b c : Kind} (h1 : Kind.le a b) (h2 : Kind.le b c) : Kind.le a c := Nat.le_trans h1 h2

theorem Kind.rank_join (a b : Kind) : (Kind.join a b).rank = max a.rank b.rank := by
  cases a <;> cases b <;> rfl

theorem Kind.le_join_left (a b : Kind) : Kind.le a (Kind.join a b) := by
  unfold Kind.le; rw [Kind.rank_join]; omega

theorem Kind.le_join_right (a b : Kind) : Kind.le b (Kind.join a b) := by
  unfold Kind.le; rw [Kind.rank_join]; omega

theorem Kind.join_le {a b c : Kind} (h1 : Kind.le a c) (h2 : Kind.le b c) : Kind.le (Kind.join a b) c := by
  unfold Kind.le at *; rw [Kind.rank_join]; omega

theorem Kind.allows_mono {a b : Kind} {t : Tok} (h : Kind.le a b) (ha : a.allows t) : b.allows t := by
  cases a <;> cases b <;> simp_all [Kind.le, Kind.rank, Kind.allows]

theorem Kind.le_copy {a : Kind} (h : Kind.le a .copy) : a = .copy := by
  cases a <;> simp_all [Kind.le, Kind.rank]

theorem Kind.eq_linear {a : Kind} (h : Kind.le .linear a) : a = .linear := by
  cases a <;> simp_all [Kind.le, Kind.rank]

theorem kindL_le (P : Prog) : ∀ {t : Ty} {ts : List Ty}, t ∈ ts → Kind.le (t.kind P) (kindL P ts)
  | _, [], h => by cases h
  | t, u :: ts, h => by
    simp only [kindL]
    rcases List.mem_cons.1 h with rfl | h
    · exact Kind.le_join_left _ _
    · exact Kind.le_trans (kindL_le P h) (Kind.le_join_right _ _)

theorem mem_toksL {τ : Tok} : ∀ {vs : List Val}, τ ∈ toksL vs ↔ ∃ v ∈ vs, τ ∈ v.toks
  | [] => by simp [toksL]
  | v :: vs => by simp [toksL, mem_toksL]

theorem toksL_nil_iff : ∀ {vs : List Val}, toksL vs = [] ↔ ∀ v ∈ vs, v.toks = []
  | [] => by simp [toksL]
  | v :: vs => by simp [toksL, toksL_nil_iff]

theorem mem_zip_left {α β} : ∀ {as : List α} {bs : List β} {a : α}, as.length = bs.length → a ∈ as →
    ∃ b, (a, b) ∈ as.zip bs
  | [], _, _, _, h => by cases h
  | _ :: _, [], _, hl, _ => by simp at hl
  | x :: as, y :: bs, a, hl, h => by
    rcases List.mem_cons.1 h with rfl | h
    · exact ⟨y, by simp⟩
    · obtain ⟨b, hb⟩ := mem_zip_left (by simpa using hl) h
      exact ⟨b, by simp [hb]⟩

theorem substL_length (σ : List Ty) : ∀ ts : List Ty, (substL σ ts).length = ts.length
  | [] => rfl
  | _ :: ts => by simp [substL, substL_length σ ts]

theorem mem_substL {σ : List Ty} : ∀ {ts : List Ty} {u : Ty}, u ∈ substL σ ts → ∃ t ∈ ts, u = t.subst σ
  | [], _, h => by cases h
  | t :: ts, u, h => by
    simp only [substL, List.mem_cons] at h
    rcases h with rfl | h
    · exact ⟨t, by simp, rfl⟩
    · obtain ⟨t', ht', rfl⟩ := mem_substL h
      exact ⟨t', by simp [ht'], rfl⟩

section
variable {P : Prog} {prim : PrimSig}

/-- **Kinds bound obligations**: every token a value holds is allowed by the
kind of its type (none for a copyable type, only unique ones for a unique type). -/
theorem ValTy.toks_allowed (hA : AdtsOk P) {v : Val} {t : Ty} (h : ValTy P prim v t) :
    ∀ τ ∈ v.toks, (t.kind P).allows τ := by
  induction h with
  | int | bool | str | unit | fn | cap => intro τ hτ; simp [Val.toks] at hτ
  | clo _ hc => intro τ hτ; simp only [Val.toks] at hτ; rw [hc] at hτ; cases hτ
  | @tup vs ts hl _ ih =>
    intro τ hτ
    simp only [Val.toks] at hτ
    obtain ⟨w, hw, hτw⟩ := mem_toksL.1 hτ
    obtain ⟨u, hu⟩ := mem_zip_left hl hw
    have := ih _ hu τ hτw
    exact Kind.allows_mono (kindL_le P (List.of_mem_zip hu).2) this
  | @list vs t _ ih =>
    intro τ hτ
    simp only [Val.toks] at hτ
    obtain ⟨w, hw, hτw⟩ := mem_toksL.1 hτ
    exact ih w hw τ hτw
  | @map kvs k v hs _ _ ihk ihv =>
    intro τ hτ
    simp only [Val.toks] at hτ
    obtain ⟨e, he, hτe⟩ := mem_toksL.1 hτ
    have hsome := hs e he
    obtain ⟨⟨a, b⟩, hab⟩ := Option.isSome_iff_exists.1 hsome
    rw [entryKV_toks hab] at hτe
    simp only [Ty.kind]
    rcases List.mem_append.1 hτe with h | h
    · exact Kind.allows_mono (Kind.le_join_left _ _) (ihk e he a b hab τ h)
    · exact Kind.allows_mono (Kind.le_join_right _ _) (ihv e he a b hab τ h)
  | @adt s tag tok vs d name ts args hd hv ha hl _ htok ih =>
    intro τ hτ
    simp only [Val.toks] at hτ
    simp only [Ty.kind, hd, Option.elim]
    rcases List.mem_append.1 hτ with h | h
    · cases tok with
      | none => cases h
      | some t0 =>
        simp only [Option.toList, List.mem_singleton] at h; subst h
        apply Kind.allows_mono (Kind.le_join_left _ _)
        revert htok; cases d.kind <;> simp [TokOk, Kind.allows]
    · obtain ⟨w, hw, hτw⟩ := mem_toksL.1 h
      obtain ⟨u, hu⟩ := mem_zip_left (bs := substL args ts) (by rw [substL_length]; exact hl) hw
      have h1 := ih (w, u) hu τ hτw
      obtain ⟨ft, hft, hu'⟩ := mem_substL (List.of_mem_zip hu).2
      have hv' : (name, ts) ∈ d.variants := List.mem_of_getElem? hv
      have hb := (hA s d hd).2.2 args ha (name, ts) hv' ft hft
      simp only at h1
      rw [hu'] at h1
      exact Kind.allows_mono hb h1

theorem ValTy.toks_copy (hA : AdtsOk P) {v : Val} {t : Ty} (h : ValTy P prim v t) (hc : t.copyable P) :
    v.toks = [] := by
  have := h.toks_allowed hA
  rw [Ty.copyable] at hc; rw [hc] at this
  cases hv : v.toks with
  | nil => rfl
  | cons τ _ => exact absurd (this τ (by simp [hv])) (by simp [Kind.allows])

theorem ValTy.noLin (hA : AdtsOk P) {v : Val} {t : Ty} (h : ValTy P prim v t) (hl : ¬ t.linear P) :
    v.hasLin = false := by
  have := h.toks_allowed hA
  simp only [Val.hasLin, List.any_eq_false]
  intro τ hτ
  have h1 := this τ hτ
  unfold Ty.linear at hl
  revert h1 hl; cases t.kind P <;> simp [Kind.allows]

end

/-! ## Dropping values without linear obligations -/

theorem discard_ok {v : Val} (h : v.hasLin = false) (st : St) : ∃ st', discard v st = some st' := by
  unfold discard; simp [h]

theorem discard_ok_of_toks {v : Val} (h : v.toks = []) (st : St) : ∃ st', discard v st = some st' :=
  discard_ok (by simp [Val.hasLin, h]) st

theorem discardAll_ok : ∀ {vs : List Val}, (∀ v ∈ vs, v.hasLin = false) → ∀ st, ∃ st', discardAll vs st = some st'
  | [], _, st => ⟨st, rfl⟩
  | v :: vs, h, st => by
    obtain ⟨st1, h1⟩ := discard_ok (h v (by simp)) st
    obtain ⟨st2, h2⟩ := discardAll_ok (vs := vs) (fun w hw => h w (by simp [hw])) st1
    exact ⟨st2, by simp [discardAll, h1, h2]⟩

theorem discardSlot_ok {s : Option Val} (h : ∀ v, s = some v → v.hasLin = false) (st : St) :
    ∃ st', discardSlot s st = some st' := by
  cases s with
  | none => exact ⟨st, rfl⟩
  | some v => exact discard_ok (h v rfl) st

theorem hasLin_of_toks {v : Val} (h : v.toks = []) : v.hasLin = false := by simp [Val.hasLin, h]

/-! ## Contexts -/

theorem Shape.refl (Γ : Ctx) : Shape Γ Γ := rfl
theorem Shape.trans {a b c : Ctx} (h1 : Shape a b) (h2 : Shape b c) : Shape a c := Eq.trans h1 h2
theorem Shape.symm {a b : Ctx} (h : Shape a b) : Shape b a := Eq.symm h

theorem Shape.length {a b : Ctx} (h : Shape a b) : a.length = b.length := by
  have := congrArg List.length h; simpa using this

theorem Shape.cons {e e' : Entry} {a b : Ctx} (he : e.key = e'.key) (h : Shape a b) : Shape (e :: a) (e' :: b) := by
  simp only [Shape, List.map_cons] at *; rw [he, h]

theorem Shape.uncons {e e' : Entry} {a b : Ctx} (h : Shape (e :: a) (e' :: b)) : e.key = e'.key ∧ Shape a b := by
  simp only [Shape, List.map_cons, List.cons.injEq] at h; exact h

theorem Shape.append {a b c d : Ctx} (h1 : Shape a c) (h2 : Shape b d) : Shape (a ++ b) (c ++ d) := by
  simp only [Shape, List.map_append] at *; rw [h1, h2]

theorem Shape.unappend : ∀ {a b c d : Ctx}, a.length = c.length → Shape (a ++ b) (c ++ d) → Shape a c ∧ Shape b d
  | [], b, [], d, _, h => ⟨rfl, h⟩
  | _ :: _, _, [], _, hl, _ => by simp at hl
  | [], _, _ :: _, _, hl, _ => by simp at hl
  | e :: a, b, e' :: c, d, hl, h => by
    obtain ⟨he, h'⟩ := Shape.uncons h
    obtain ⟨h1, h2⟩ := Shape.unappend (by simpa using hl) h'
    exact ⟨Shape.cons he h1, h2⟩

theorem Shape.setAvail : ∀ (Γ : Ctx) (x : String) (a : Bool), Shape (Γ.setAvail x a) Γ
  | [], _, _ => rfl
  | e :: Γ, x, a => by
    simp only [Ctx.setAvail]
    split
    · exact Shape.cons rfl rfl
    · exact Shape.cons rfl (Shape.setAvail Γ x a)

theorem Ctx.find_name : ∀ {Γ : Ctx} {x : String} {e : Entry}, Γ.find x = some e → e.name = x
  | [], _, _, h => by simp [Ctx.find] at h
  | e' :: Γ, x, e, h => by
    simp only [Ctx.find] at h
    split at h
    · simp only [Option.some.injEq] at h; subst h; assumption
    · exact Ctx.find_name h

theorem Ctx.find_mem : ∀ {Γ : Ctx} {x : String} {e : Entry}, Γ.find x = some e → e ∈ Γ
  | [], _, _, h => by simp [Ctx.find] at h
  | e' :: Γ, x, e, h => by
    simp only [Ctx.find] at h
    split at h
    · simp only [Option.some.injEq] at h; subst h; simp
    · exact List.mem_cons_of_mem _ (Ctx.find_mem h)

theorem Shape.find : ∀ {Γ' Γ : Ctx}, Shape Γ' Γ → ∀ {x : String} {e : Entry}, Γ.find x = some e →
    ∃ e', Γ'.find x = some e' ∧ e'.key = e.key
  | [], [], _, _, _, h => by simp [Ctx.find] at h
  | [], _ :: _, hs, _, _, _ => by simp [Shape] at hs
  | _ :: _, [], hs, _, _, _ => by simp [Shape] at hs
  | e1 :: Γ', e2 :: Γ, hs, x, e, h => by
    obtain ⟨hk, hs'⟩ := Shape.uncons hs
    have hn : e1.name = e2.name := congrArg Prod.fst hk
    simp only [Ctx.find] at h ⊢
    rw [hn]
    split
    · rename_i hx; rw [if_pos hx] at h; simp only [Option.some.injEq] at h; subst h; exact ⟨e1, rfl, hk⟩
    · rename_i hx; rw [if_neg hx] at h; exact Shape.find hs' h

theorem Entry.key_ty {e e' : Entry} (h : e.key = e'.key) : e.ty = e'.ty := congrArg (·.2.1) h
theorem Entry.key_mut {e e' : Entry} (h : e.key = e'.key) : e.mutable = e'.mutable := congrArg (·.2.2) h

theorem Ctx.find_setAvail_same : ∀ {Γ : Ctx} {x : String} {e : Entry} (a : Bool), Γ.find x = some e →
    (Γ.setAvail x a).find x = some { e with avail := a }
  | [], _, _, _, h => by simp [Ctx.find] at h
  | e' :: Γ, x, e, a, h => by
    simp only [Ctx.find] at h
    simp only [Ctx.setAvail]
    split at h
    · rename_i hx; simp only [Option.some.injEq] at h; subst h; simp [Ctx.find, hx]
    · rename_i hx; simp only [hx, ite_false, Ctx.find]; exact Ctx.find_setAvail_same a h

theorem Ctx.find_setAvail_other : ∀ {Γ : Ctx} {x y : String} (a : Bool), y ≠ x →
    (Γ.setAvail x a).find y = Γ.find y
  | [], _, _, _, _ => rfl
  | e' :: Γ, x, y, a, hne => by
    simp only [Ctx.setAvail]
    split
    · rename_i hx; simp only [Ctx.find]; rw [hx]; simp [Ne.symm hne]
    · simp only [Ctx.find]; split
      · rfl
      · exact Ctx.find_setAvail_other a hne

theorem Ctx.setAvail_self : ∀ {Γ : Ctx} {x : String} {e : Entry}, Γ.find x = some e → Γ.setAvail x e.avail = Γ
  | [], _, _, h => by simp [Ctx.find] at h
  | e' :: Γ, x, e, h => by
    simp only [Ctx.find] at h
    simp only [Ctx.setAvail]
    split at h
    · rename_i hx; simp only [Option.some.injEq] at h; subst h; rw [if_pos hx]
    · rename_i hx; simp only [hx, ite_false]; rw [Ctx.setAvail_self h]

theorem noLinear_append {P : Prog} {a b : Ctx} : Ctx.noLinear P (a ++ b) ↔ Ctx.noLinear P a ∧ Ctx.noLinear P b := by
  unfold Ctx.noLinear; simp only [List.mem_append]
  exact ⟨fun h => ⟨fun e he => h e (Or.inl he), fun e he => h e (Or.inr he)⟩,
    fun h e he => he.elim (h.1 e) (h.2 e)⟩

theorem noLinear_cons {P : Prog} {e : Entry} {a : Ctx} :
    Ctx.noLinear P (e :: a) ↔ (e.avail = true → ¬ e.ty.linear P) ∧ Ctx.noLinear P a := by
  unfold Ctx.noLinear; simp

theorem noLinear_nil {P : Prog} : Ctx.noLinear P [] := by simp [Ctx.noLinear]

/-! ## Environments -/

section
variable {P : Prog} {prim : PrimSig}

theorem EnvOk.lookup : ∀ {ρ : Env} {Γ : Ctx}, EnvOk P prim ρ Γ → ∀ {x : String} {e : Entry}, Γ.find x = some e →
    ∃ s, Tenon.lookup ρ x = some s ∧ SlotOk P prim e s
  | _, [], _, _, _, h => by simp [Ctx.find] at h
  | [], _ :: _, h, _, _, _ => by simp [EnvOk] at h
  | (y, s) :: ρ, e' :: Γ, h, x, e, hf => by
    obtain ⟨hy, hs, hρ⟩ := h
    simp only [Ctx.find] at hf
    simp only [Tenon.lookup]
    split at hf
    · rename_i hx; simp only [Option.some.injEq] at hf; subst hf
      rw [hy, if_pos hx]; exact ⟨s, rfl, hs⟩
    · rename_i hx; rw [hy, if_neg hx]; exact EnvOk.lookup hρ hf

theorem EnvOk.lookup_avail {ρ : Env} {Γ : Ctx} (h : EnvOk P prim ρ Γ) {x : String} {e : Entry}
    (hf : Γ.find x = some e) (ha : e.avail = true) : ∃ v, Tenon.lookup ρ x = some (some v) ∧ ValTy P prim v e.ty := by
  obtain ⟨s, hl, hs⟩ := h.lookup hf
  obtain ⟨v, rfl, hv⟩ := hs.1 ha
  exact ⟨v, hl, hv⟩

theorem EnvOk.update : ∀ {ρ : Env} {Γ : Ctx}, EnvOk P prim ρ Γ → ∀ {x : String} {e : Entry} (a : Bool) (s : Option Val),
    Γ.find x = some e → SlotOk P prim { e with avail := a } s → EnvOk P prim (Tenon.update ρ x s) (Γ.setAvail x a)
  | _, [], _, _, _, _, _, h, _ => by simp [Ctx.find] at h
  | [], _ :: _, h, _, _, _, _, _, _ => by simp [EnvOk] at h
  | (y, s0) :: ρ, e' :: Γ, h, x, e, a, s, hf, hs => by
    obtain ⟨hy, hs0, hρ⟩ := h
    simp only [Ctx.find] at hf
    simp only [Tenon.update, Ctx.setAvail]
    split at hf
    · rename_i hx; simp only [Option.some.injEq] at hf; subst hf
      rw [hy, if_pos hx, if_pos hx]; exact ⟨rfl, hs, hρ⟩
    · rename_i hx; rw [hy, if_neg hx, if_neg hx]
      exact ⟨rfl, hs0, EnvOk.update hρ a s hf hs⟩

/-- Writing a new value of its type to an available variable. -/
theorem EnvOk.update_val {ρ : Env} {Γ : Ctx} (h : EnvOk P prim ρ Γ) {x : String} {e : Entry} (hf : Γ.find x = some e)
    (ha : e.avail = true) {v : Val} (hv : ValTy P prim v e.ty) : EnvOk P prim (Tenon.update ρ x (some v)) Γ := by
  have := h.update e.avail (some v) hf ⟨fun _ => ⟨v, rfl, hv⟩, fun h' => by simp [ha] at h'⟩
  rwa [Ctx.setAvail_self hf] at this

theorem EnvOk.length : ∀ {ρ : Env} {Γ : Ctx}, EnvOk P prim ρ Γ → Γ.length ≤ ρ.length
  | _, [], _ => Nat.zero_le _
  | [], _ :: _, h => by simp [EnvOk] at h
  | _ :: ρ, _ :: Γ, h => by simpa using EnvOk.length h.2.2

/-- The innermost `Γb.length` slots match `Γb`; below them the environment matches `Γ`. -/
theorem EnvOk.split : ∀ {Γb Γ : Ctx} {ρ : Env}, EnvOk P prim ρ (Γb ++ Γ) →
    EnvOk P prim (ρ.drop Γb.length) Γ ∧ Γb.length ≤ ρ.length ∧
    ∀ (i : Nat) e, Γb[i]? = some e → ∃ (y : String) (s : Option Val), ρ[i]? = some (y, s) ∧ SlotOk P prim e s
  | [], Γ, ρ, h => ⟨h, Nat.zero_le _, fun i e he => by simp at he⟩
  | _ :: _, _, [], h => by simp [EnvOk] at h
  | e :: Γb, Γ, (y, s) :: ρ, h => by
    obtain ⟨hy, hs, hρ⟩ := h
    obtain ⟨h1, h2, h3⟩ := EnvOk.split hρ
    refine ⟨by simpa using h1, by simpa using h2, ?_⟩
    intro i e' he'
    cases i with
    | zero => simp only [List.getElem?_cons_zero, Option.some.injEq] at he'; subst he'; exact ⟨y, s, rfl, hs⟩
    | succ i => simpa using h3 i e' (by simpa using he')

theorem EnvOk.join : ∀ {Γb Γ : Ctx} {ρb ρ : Env}, ρb.length = Γb.length →
    (∀ (i : Nat) e (p : String × Option Val), Γb[i]? = some e → ρb[i]? = some p → p.1 = e.name ∧ SlotOk P prim e p.2) →
    EnvOk P prim ρ Γ → EnvOk P prim (ρb ++ ρ) (Γb ++ Γ)
  | [], Γ, [], ρ, _, _, h => h
  | _ :: _, _, [], _, hl, _, _ => by simp at hl
  | [], _, _ :: _, _, hl, _, _ => by simp at hl
  | e :: Γb, Γ, (y, s) :: ρb, ρ, hl, hs, h => by
    obtain ⟨h1, h2⟩ := hs 0 e (y, s) rfl rfl
    exact ⟨h1, h2, EnvOk.join (by simpa using hl) (fun i e' p he hp => hs (i + 1) e' p (by simpa using he)
      (by simpa using hp)) h⟩

theorem SlotOk.noLin (hA : AdtsOk P) {e : Entry} {s : Option Val} (h : SlotOk P prim e s)
    (hl : e.avail = true → ¬ e.ty.linear P) : ∀ v, s = some v → v.hasLin = false := by
  intro v hv
  cases ha : e.avail
  · exact hasLin_of_toks (h.2 ha v hv)
  · obtain ⟨w, hw, hwt⟩ := h.1 ha
    rw [hv] at hw; cases hw
    exact hwt.noLin hA (hl ha)

/-- Ending a scope whose variables hold no linear value. -/
theorem popEnv_typed (hA : AdtsOk P) {Γb Γ : Ctx} {ρ : Env} (h : EnvOk P prim ρ (Γb ++ Γ)) (hn : Ctx.noLinear P Γb)
    (st : St) : ∃ st', popEnv Γb.length ρ st = .ok () (ρ.drop Γb.length) st' ∧ EnvOk P prim (ρ.drop Γb.length) Γ := by
  obtain ⟨h1, h2, h3⟩ := h.split
  have hall : ∀ v ∈ (ρ.take Γb.length).filterMap (·.2), v.hasLin = false := by
    intro v hv
    obtain ⟨p, hp, hpv⟩ := List.mem_filterMap.1 hv
    obtain ⟨i, hi, rfl⟩ := List.getElem_of_mem hp
    have hi' : i < Γb.length := by simp at hi; omega
    have hρi : ρ[i]? = some (ρ.take Γb.length)[i] := by
      rw [List.getElem_take]; exact List.getElem?_eq_getElem _
    obtain ⟨y, s, hys, hs⟩ := h3 i Γb[i] (List.getElem?_eq_getElem hi')
    rw [hρi] at hys; simp only [Option.some.injEq] at hys
    rw [hys] at hpv
    exact hs.noLin hA (fun ha => hn _ (List.getElem_mem hi') ha) v hpv
  obtain ⟨st', hst⟩ := discardAll_ok hall st
  exact ⟨st', by simp [popEnv, h2, hst], h1⟩

end

end Tenon

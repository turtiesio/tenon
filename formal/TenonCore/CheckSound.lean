/-
**The checker is sound** (formal/README.md, "The checker"): whatever the
checker of Check.lean accepts is well typed in the stage-3 judgement
(`HasTyX (Ext.stage3 I)`, Typing.lean) at the instances it was given, and a
program it accepts satisfies `ProgOkX` (`check_sound`), so
`type_soundness_full` applies: its run is never stuck.

The proof is an induction on the checker's fuel over its mutually recursive
functions (`Sound`), following the code: every success of the checker
yields the rule of the judgement whose side conditions it checked.
-/
import TenonCore.Check

namespace Tenon.Check
open Tenon

/-! ## The monad -/

theorem bind_ok {α β} {x : CM α} {f : α → CM β} {b : β} (h : (x >>= f) = .ok b) : ∃ a, x = .ok a ∧ f a = .ok b := by
  cases x with
  | error e => cases h
  | ok a => exact ⟨a, rfl, h⟩

theorem req_ok {c : Bool} {s : String} {u : Unit} (h : req c s = .ok u) : c = true := by
  unfold req at h; split at h
  · assumption
  · cases h

theorem getO_ok {α} {o : Option α} {s : String} {a : α} (h : getO o s = .ok a) : o = some a := by
  unfold getO at h; split at h
  · cases h; rfl
  · cases h

theorem pure_ok {α} {a b : α} (h : (pure a : CM α) = .ok b) : a = b := by cases h; rfl

theorem fail_ok {α} {s : String} {b : α} (h : (fail s : CM α) = .ok b) : False := by cases h

theorem reqInst_ok {E : CEnv} {f : String} {σ : List Ty} {u : Unit} (h : reqInst E f σ = .ok u) : E.inst f σ = true := by
  unfold reqInst at h; split at h
  · assumption
  · cases h

theorem beq_eq {α} [BEq α] [LawfulBEq α] {a b : α} (h : (a == b) = true) : a = b := eq_of_beq h

/-! ## Side conditions -/

theorem availB_ok {Γ : Ctx} {x : String} (h : availB Γ x = true) : Γ.Avail x := by
  unfold availB at h; split at h
  · rename_i e he; exact ⟨e, he, h⟩
  · cases h

theorem availAtB_ok {Γ : Ctx} {x : String} {T : Ty} (h : availAtB Γ x T = true) : Γ.AvailAt x T := by
  unfold availAtB at h; split at h
  · rename_i e he; simp only [Bool.and_eq_true] at h; exact ⟨e, he, h.1, beq_eq h.2⟩
  · cases h

theorem tailSig_ok (P : Prog) (Δ : Sig) (t : Ty) : TailSig P Δ (tailSig P Δ t) t := by
  unfold tailSig TailSig; split
  · exact Or.inr rfl
  · rename_i h; exact Or.inl ⟨rfl, h⟩

theorem tailSig_fin (P : Prog) (Δ : Sig) (t : Ty) : (tailSig P Δ t).fin = Δ.fin := by
  unfold tailSig; split <;> rfl

theorem capTys_ok (P : Prog) (Γ : Ctx) : ∀ {caps : List String} {cts : List Ty}, capTys P Γ caps = some cts →
    CapsTy Γ caps cts ∧ ∀ t ∈ cts, t.copyable P
  | [], cts, h => by simp [capTys] at h; subst h; exact ⟨.nil, by simp⟩
  | x :: xs, cts, h => by
    simp only [capTys] at h
    split at h
    · rename_i e ts he hts
      split at h
      · rename_i hc
        simp only [Option.some.injEq] at h; subst h
        simp only [Bool.and_eq_true, decide_eq_true_eq] at hc
        obtain ⟨h1, h2⟩ := capTys_ok P Γ hts
        exact ⟨.cons ⟨e, he, hc.1, rfl⟩ h1, fun t ht => by
          simp only [List.mem_cons] at ht; rcases ht with rfl | ht
          · exact hc.2
          · exact h2 t ht⟩
      · cases h
    · cases h

theorem expFn_ok {exp : Option Ty} {k : Nat} {ts : List Ty} {r? : Option Ty} (h : expFn exp k = .ok (ts, r?)) :
    ts.length = k := by
  unfold expFn at h
  split at h
  · split at h
    · rename_i ts' r hc; cases h; exact hc.1
    · cases h
  · cases h

/-! ## The statement -/

variable (E : CEnv)

/-- The judgement the checker decides: stage 3, at the checker's instances and builtins. -/
abbrev XE : Ext := Ext.stage3 (fun f σ => E.inst f σ = true)
abbrev PrE : PrimSig := fun p ts t => E.prim p ts t = true

abbrev Ty3 := HasTyX (XE E) E.P (PrE E)

def RSound (Δ : Sig) (Γ : Ctx) (e : Expr) : R → Prop
  | .ty t Γ' => Ty3 E Δ Γ e t Γ'
  | .div => ∀ t Γ', Ty3 E Δ Γ e t Γ'

/-- One arm, typed at the arms' type `t` and the context `Γ'` they leave. -/
def ArmOk (Δ : Sig) (Γ : Ctx) (t0 : Ty) (arm : Pat × Option Expr × Expr) (t : Ty) (Γ' : Ctx) : Prop :=
  ∃ bs Γb, PatTy E.P arm.1 t0 bs ∧ (arm.2.1.isSome → t0.copyable E.P) ∧
    (∀ ge, arm.2.1 = some ge → Ty3 E Δ (bindCtx bs ++ Γ) ge .bool (bindCtx bs ++ Γ)) ∧
    Ty3 E Δ (bindCtx bs ++ Γ) arm.2.2 t (Γb ++ Γ') ∧ Γb.length = bs.length ∧ Ctx.noLinear E.P Γb

def ArmsRes (Δ : Sig) (Γ : Ctx) (t0 : Ty) : List (Pat × Option Expr × Expr) → List (Option (Ty × Ctx)) → Prop
  | [], [] => True
  | a :: as, r :: rs => (match r with
      | some (t, Γ') => ArmOk E Δ Γ t0 a t Γ'
      | none => ∀ t Γ', ArmOk E Δ Γ t0 a t Γ') ∧ ArmsRes Δ Γ t0 as rs
  | _, _ => False

theorem ArmsRes.armsTy {Δ : Sig} {Γ : Ctx} {t0 t : Ty} {Γ' : Ctx} :
    ∀ {arms : List (Pat × Option Expr × Expr)} {rs : List (Option (Ty × Ctx))}, ArmsRes E Δ Γ t0 arms rs →
    (∀ r ∈ rs, ∀ tc, r = some tc → tc = (t, Γ')) → ArmsTyX (XE E) E.P (PrE E) Δ Γ t0 arms t Γ'
  | [], [], _, _ => .nil
  | (p, g, body) :: arms, r :: rs, ⟨h1, h2⟩, hall => by
    have hrest := ArmsRes.armsTy h2 (fun r' hr' tc htc => hall r' (by simp [hr']) tc htc)
    have ha : ArmOk E Δ Γ t0 (p, g, body) t Γ' := by
      cases r with
      | some tc =>
        obtain ⟨t1, Γ1⟩ := tc
        have := hall (some (t1, Γ1)) (by simp) _ rfl
        simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this
        exact h1
      | none => exact h1 t Γ'
    obtain ⟨bs, Γb, hp, hg, hgt, hb, hl, hn⟩ := ha
    exact .cons hp hg hgt hb hl hn hrest
  | [], _ :: _, h, _ | _ :: _, [], h, _ => h.elim

/-- A body with no value result fits every arm's type (its names marked consumed). -/
theorem armOk_div {Δ : Sig} {Γ : Ctx} {t0 : Ty} {p : Pat} {g : Option Expr} {body : Expr} {bs : List (String × Ty)}
    (hp : PatTy E.P p t0 bs) (hg : g.isSome → t0.copyable E.P)
    (hgt : ∀ ge, g = some ge → Ty3 E Δ (bindCtx bs ++ Γ) ge .bool (bindCtx bs ++ Γ))
    (hb : ∀ t Γ', Ty3 E Δ (bindCtx bs ++ Γ) body t Γ') : ∀ t Γ', ArmOk E Δ Γ t0 (p, g, body) t Γ' := by
  intro t Γ'
  refine ⟨bs, (bindCtx bs).map fun e => { e with avail := false }, hp, hg, hgt, hb _ _, by simp [bindCtx], ?_⟩
  intro e he ha
  simp only [List.mem_map] at he
  obtain ⟨e', -, rfl⟩ := he
  cases ha

structure Sound (n : Nat) : Prop where
  chk : ∀ Δ fb Γ e exp r, (∀ Γ, fb Γ = true → Δ.fin Γ) → chk E n Δ fb Γ e exp = .ok r → RSound E Δ Γ e r
  chkV : ∀ Δ fb Γ e exp t Γ', (∀ Γ, fb Γ = true → Δ.fin Γ) → chkV E n Δ fb Γ e exp = .ok (t, Γ') →
    Ty3 E Δ Γ e t Γ'
  list : ∀ Δ fb Γ es hints same ts Γ', (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chkList E n Δ fb Γ es hints same = .ok (ts, Γ') → ListTyX (XE E) E.P (PrE E) Δ Γ es ts Γ'
  args : ∀ Δ fb Γ ms es pats σp ts Γ' σp', (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chkArgs E n Δ fb Γ ms es pats σp = .ok (ts, Γ', σp') → ArgsTyX (XE E) E.P (PrE E) Δ Γ ms es ts Γ'
  opnds : ∀ Δ fb Γ es p pre ts Γ', (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chkOpnds E n Δ fb Γ es p pre = .ok (ts, Γ') → OpndsTyX (XE E) E.P (PrE E) Δ Γ es ts Γ'
  path : ∀ Δ fb Γ T ps t Γ', (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chkPath E n Δ fb Γ T ps = .ok (t, Γ') → PathTyX (XE E) E.P (PrE E) Δ Γ T ps t Γ'
  arms : ∀ Δ fb Γ t0 arms exp rs, (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chkArms E n Δ fb Γ t0 arms exp = .ok rs → ArmsRes E Δ Γ t0 arms rs

theorem sound_zero : Sound E 0 := by
  constructor <;> intros <;> rename_i h <;> simp [chk, chkV, chkList, chkArgs, chkOpnds, chkPath, chkArms, fail] at h

/-! ## The induction step -/

section
variable {E : CEnv}

theorem RSound.tyOr {Δ : Sig} {Γ : Ctx} {e : Expr} {r : R} (h : RSound E Δ Γ e r) :
    Ty3 E Δ Γ e (r.tyOr Γ).1 (r.tyOr Γ).2 := by
  cases r with
  | ty t Γ' => exact h
  | div => exact h _ _

theorem unit_nonlinear (P : Prog) : ¬ Ty.unit.linear P := by simp [Ty.linear, Ty.kind]

theorem firstTy_none : ∀ {rs : List (Option (Ty × Ctx))}, firstTy rs = none → ∀ r ∈ rs, r = none
  | [], _, _, h => by cases h
  | some _ :: _, h, _, _ => by simp [firstTy] at h
  | none :: rs, h, r, hr => by
    simp only [List.mem_cons] at hr
    rcases hr with rfl | hr
    · rfl
    · exact firstTy_none (by simpa [firstTy] using h) r hr

theorem fnSig_fb (P : Prog) (owner : Option String) (ps : List (String × Mode)) (r : Ty) :
    ∀ Γ, finFnB P owner ps Γ = true → (fnSig P owner ps r).fin Γ := fun _ h => finFnB_sound P owner h

theorem closSig_fb (P : Prog) (ps : List String) (nc : Nat) (r : Ty) :
    ∀ Γ, closFin P ps Γ = true → (closSig P ps nc r).fin Γ := fun _ h => finFnB_sound P none h

theorem primAt_of {E : CEnv} {h m : String} {ts : List Ty} {t : Ty}
    (hpr : E.prim (if (E.P.prim (h ++ "." ++ m)).isSome then h ++ "." ++ m else "*." ++ m) ts t = true) :
    PrimAt (XE E) E.P (PrE E) h m ts t := by
  split at hpr
  · exact Or.inl hpr
  · rename_i hn
    exact Or.inr ⟨rfl, by simpa using hn, hpr⟩

theorem tryTy_ok {t0 r t : Ty} (h : tryTy t0 r = some t) :
    (t0 = .adt "Option" [t] ∧ ∃ t', r = .adt "Option" [t']) ∨
    (∃ er t', t0 = .adt "Result" [t, er] ∧ r = .adt "Result" [t', er]) := by
  unfold tryTy at h
  split at h
  · rename_i s a s' b
    split at h
    · rename_i hs; obtain ⟨rfl, rfl⟩ := hs; cases h; exact Or.inl ⟨rfl, b, rfl⟩
    · cases h
  · rename_i s a er s' b er'
    split at h
    · rename_i hs; obtain ⟨rfl, rfl, rfl⟩ := hs; cases h; exact Or.inr ⟨er, b, rfl, rfl⟩
    · cases h
  · cases h

theorem chk_succ {n : Nat} (ih : Sound E n) : ∀ Δ fb Γ e exp r, (∀ Γ, fb Γ = true → Δ.fin Γ) →
    chk E (n + 1) Δ fb Γ e exp = .ok r → RSound E Δ Γ e r := by
  intro Δ fb Γ e exp r hfb h
  unfold chk at h
  split at h
  next l => have := pure_ok h; subst this; exact .lit
  next x =>
    obtain ⟨en, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    have hf := getO_ok h1
    have ha := req_ok h2
    have := pure_ok h; subst this
    split
    · rename_i hc; exact .copy hf ha .nil ⟨en, hf, ha⟩ (of_decide_eq_true hc)
    · exact .move hf ha
  next x ps _ =>
    obtain ⟨en, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨⟨t, Γ'⟩, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    obtain ⟨_, h5, h⟩ := bind_ok h
    have := pure_ok h; subst this
    exact .copy (getO_ok h1) (req_ok h2) (ih.path _ _ _ _ _ _ _ hfb h3) (availB_ok (req_ok h4))
      (of_decide_eq_true (req_ok h5))
  next e ps =>
    obtain ⟨⟨t0, Γ1⟩, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨⟨t, Γ2⟩, h3, h⟩ := bind_ok h
    have := pure_ok h; subst this
    exact .proj (ih.chkV _ _ _ _ _ _ _ hfb h1) (of_decide_eq_true (req_ok h2)) (ih.path _ _ _ _ _ _ _ hfb h3)
  next es =>
    obtain ⟨⟨ts, Γ'⟩, h1, h⟩ := bind_ok h
    have := pure_ok h; subst this
    exact .tup (ih.list _ _ _ _ _ _ _ _ hfb h1)
  next es =>
    obtain ⟨⟨ts, Γ'⟩, h1, h⟩ := bind_ok h
    obtain ⟨t, h2, h⟩ := bind_ok h
    obtain ⟨_, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have hl := ih.list _ _ _ _ _ _ _ _ hfb h1
    rw [beq_eq (req_ok h3)] at hl
    exact .list hl (of_decide_eq_true (req_ok h4))
  next => exact (fail_ok h).elim
  next s tag es =>
    obtain ⟨d, h1, h⟩ := bind_ok h
    obtain ⟨v, h2, h⟩ := bind_ok h
    obtain ⟨⟨pts, Γ'⟩, h3, h⟩ := bind_ok h
    obtain ⟨args, h4, h⟩ := bind_ok h
    obtain ⟨_, h5, h⟩ := bind_ok h
    obtain ⟨_, h6, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have hl := ih.list _ _ _ _ _ _ _ _ hfb h3
    rw [beq_eq (req_ok h6)] at hl
    exact .con (getO_ok h1) (getO_ok h2) (beq_eq (req_ok h5)) hl
  next ps body =>
    obtain ⟨⟨ts, r?⟩, h1, h⟩ := bind_ok h
    obtain ⟨rr, -, h⟩ := bind_ok h
    obtain ⟨⟨r', Γb⟩, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have h4' := req_ok h4
    simp only [Bool.and_eq_true] at h4'
    obtain ⟨⟨hr, hfin⟩, hlen⟩ := h4'
    have hb := ih.chkV _ _ _ _ _ _ _ (fnSig_fb E.P none _ rr) h3
    rw [beq_eq hr] at hb
    exact .lam (beq_eq hlen) hb (finFnB_sound E.P none hfin)
  next caps ps body =>
    obtain ⟨⟨ts, r?⟩, h1, h⟩ := bind_ok h
    obtain ⟨cts, h2, h⟩ := bind_ok h
    obtain ⟨rr, -, h⟩ := bind_ok h
    obtain ⟨⟨r', Γb⟩, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have h4' := req_ok h4
    simp only [Bool.and_eq_true] at h4'
    obtain ⟨⟨hr, hfin⟩, hlen⟩ := h4'
    obtain ⟨hcaps, hcop⟩ := capTys_ok E.P Γ (getO_ok h2)
    have hb := ih.chkV _ _ _ _ _ _ _ (closSig_fb E.P ps cts.length rr) h3
    rw [beq_eq hr] at hb
    exact .clos rfl (beq_eq hlen) hcaps hcop hb (finFnB_sound E.P none hfin)
  next f =>
    obtain ⟨d, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨σ, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    obtain ⟨_, h5, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have hall : ∀ p ∈ d.params, p.2 = .val := fun p hp => beq_eq (List.all_eq_true.1 (req_ok h2) p hp)
    exact .fnref (getO_ok h1) hall (beq_eq (req_ok h4)) (reqInst_ok h5)
  next f args =>
    split at h
    · rename_i d hd
      obtain ⟨⟨ts, Γ', σp⟩, h1, h⟩ := bind_ok h
      obtain ⟨σ, h2, h⟩ := bind_ok h
      obtain ⟨_, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      obtain ⟨_, h5, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have ha := ih.args _ _ _ _ _ _ _ _ _ _ hfb h1
      rw [beq_eq (req_ok h5)] at ha
      exact .call hd (beq_eq (req_ok h3)) (reqInst_ok h4) ha
    · rename_i hd
      obtain ⟨⟨ts, Γ'⟩, h1, h⟩ := bind_ok h
      obtain ⟨t, h2, h⟩ := bind_ok h
      obtain ⟨_, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      have := pure_ok h; subst this
      exact .callPrim rfl hd (req_ok h3) (ih.opnds _ _ _ _ _ _ _ _ hfb h1) (of_decide_eq_true (req_ok h4))
  next fe args _ =>
    obtain ⟨⟨ft, Γ1⟩, h1, h⟩ := bind_ok h
    dsimp only at h
    split at h
    · rename_i ts rr
      obtain ⟨⟨ts', Γ2, σp⟩, h2, h⟩ := bind_ok h
      obtain ⟨_, h3, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have ha := ih.args _ _ _ _ _ _ _ _ _ _ hfb h2
      have e3 : ts' = ts := by have := beq_eq (req_ok h3); simpa using this
      rw [e3] at ha
      exact .callv (ih.chkV _ _ _ _ _ _ _ hfb h1) ha
    · exact (fail_ok h).elim
  next m x ps args =>
    obtain ⟨en, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨⟨t0, Γ1⟩, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    have hf := getO_ok h1
    have ha := req_ok h2
    have hp := ih.path _ _ _ _ _ _ _ hfb h3
    have h4' := req_ok h4
    simp only [Bool.and_eq_true, Bool.not_eq_true'] at h4'
    obtain ⟨hav1, hvar⟩ := h4'
    split at h
    · rename_i d hd
      split at h
      · rename_i p0 m0 prest pt0 ptrest hpar hpty
        obtain ⟨Γr, hΓr, h⟩ := bind_ok h
        obtain ⟨⟨ts, Γ2, σp⟩, h5, h⟩ := bind_ok h
        obtain ⟨σ, h6, h⟩ := bind_ok h
        obtain ⟨_, h7, h⟩ := bind_ok h
        obtain ⟨_, h8, h⟩ := bind_ok h
        obtain ⟨_, h9, h⟩ := bind_ok h
        obtain ⟨_, h10, h⟩ := bind_ok h
        have := pure_ok h; subst this
        have h9' := req_ok h9
        simp only [Bool.and_eq_true] at h9'
        obtain ⟨hsub, hts⟩ := h9'
        have hargs := ih.args _ _ _ _ _ _ _ _ _ _ (by rw [tailSig_fin]; exact hfb) h5
        rw [beq_eq hts] at hargs
        have h10' := req_ok h10
        refine .mcallP hf ha hp (availB_ok hav1) hvar hd (beq_eq (req_ok h7)) (reqInst_ok h8) hpar hpty
          (beq_eq hsub) ?_ ?_ (tailSig_ok E.P Δ t0) hargs
        · intro hm0
          subst hm0
          simp only [beq_self_eq_true, ite_true] at hΓr
          split at hΓr
          · rename_i hc
            have := pure_ok hΓr; subst this
            simp only [Bool.and_eq_true, List.isEmpty_iff, Bool.not_eq_true', decide_eq_false_iff_not] at hc
            exact Or.inl ⟨hc.1, rfl⟩
          · obtain ⟨_, hc, hΓr⟩ := bind_ok hΓr
            have := pure_ok hΓr; subst this
            exact Or.inr ⟨rfl, of_decide_eq_true (req_ok hc)⟩
        · intro hm0
          have hne : (m0 == Mode.val) = false := by cases m0 <;> simp_all
          simp only [hne] at hΓr
          obtain ⟨_, hc, hΓr⟩ := bind_ok hΓr
          have := pure_ok hΓr; subst this
          simp only [hne, Bool.false_or] at h10'
          exact ⟨rfl, of_decide_eq_true (req_ok hc), availAtB_ok h10'⟩
      · exact (fail_ok h).elim
    · rename_i hd
      obtain ⟨⟨ts, Γ2⟩, h5, h⟩ := bind_ok h
      obtain ⟨t, h6, h⟩ := bind_ok h
      obtain ⟨_, h7, h⟩ := bind_ok h
      obtain ⟨_, h8, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have h8' := req_ok h8
      simp only [Bool.and_eq_true] at h8'
      obtain ⟨hav2, hc⟩ := h8'
      exact .mprimP hf ha hp (availB_ok hav1) hvar hd (primAt_of (req_ok h7)) (ih.opnds _ _ _ _ _ _ _ _ hfb h5)
        (availAtB_ok hav2) (of_decide_eq_true hc)
  next m recv args hnp =>
    obtain ⟨⟨t0, Γ1⟩, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    have hr := ih.chkV _ _ _ _ _ _ _ hfb h1
    have hvar : t0.isVar = false := by simpa using req_ok h2
    have hnp' : ∀ x ps, recv ≠ .place x ps := fun x ps he => hnp x ps he
    split at h
    · rename_i d hd
      split at h
      · rename_i p0 prest pt0 ptrest hpar hpty
        obtain ⟨⟨ts, Γ2, σp⟩, h5, h⟩ := bind_ok h
        obtain ⟨σ, h6, h⟩ := bind_ok h
        obtain ⟨_, h7, h⟩ := bind_ok h
        obtain ⟨_, h8, h⟩ := bind_ok h
        obtain ⟨_, h9, h⟩ := bind_ok h
        have := pure_ok h; subst this
        have h9' := req_ok h9
        simp only [Bool.and_eq_true] at h9'
        obtain ⟨hsub, hts⟩ := h9'
        have hargs := ih.args _ _ _ _ _ _ _ _ _ _ (by rw [tailSig_fin]; exact hfb) h5
        rw [beq_eq hts] at hargs
        exact .mcallV hnp' hr hvar hd (beq_eq (req_ok h7)) (reqInst_ok h8) hpar hpty (beq_eq hsub)
          (tailSig_ok E.P Δ t0) hargs
      · exact (fail_ok h).elim
    · rename_i hd
      obtain ⟨_, h4, h⟩ := bind_ok h
      obtain ⟨⟨ts, Γ2⟩, h5, h⟩ := bind_ok h
      obtain ⟨t, h6, h⟩ := bind_ok h
      obtain ⟨_, h7, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have h7' := req_ok h7
      simp only [Bool.and_eq_true] at h7'
      obtain ⟨hpr, hc⟩ := h7'
      exact .mprimV hnp' hr (of_decide_eq_true (req_ok h4)) hvar hd (primAt_of hpr)
        (ih.opnds _ _ _ _ _ _ _ _ hfb h5) (of_decide_eq_true hc)
  next p args =>
    obtain ⟨⟨ts, Γ'⟩, h1, h⟩ := bind_ok h
    obtain ⟨t, h2, h⟩ := bind_ok h
    obtain ⟨_, h3, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have h3' := req_ok h3
    simp only [Bool.and_eq_true] at h3'
    obtain ⟨hpr, hc⟩ := h3'
    exact .prim hpr (ih.opnds _ _ _ _ _ _ _ _ hfb h1) (of_decide_eq_true hc)
  next x mu e body =>
    obtain ⟨r1, h1, h⟩ := bind_ok h
    have he := (ih.chk _ _ _ _ _ _ hfb h1).tyOr
    obtain ⟨r2, h2, h⟩ := bind_ok h
    have hr2 := ih.chk _ _ _ _ _ _ hfb h2
    split at h
    · have := pure_ok h; subst this
      intro t' Γ2
      exact .letE (a := false) he (hr2 t' _) (by simp)
    · rename_i t' e0 Γ2
      obtain ⟨_, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have h3' := req_ok h3
      simp only [Bool.and_eq_true] at h3'
      obtain ⟨⟨hn, hty⟩, hmu⟩ := h3'
      have h4' := req_ok h4
      obtain ⟨n0, ty0, mu0, a0⟩ := e0
      simp only at hn hty hmu h4'
      rw [beq_eq hn, beq_eq hty, beq_eq hmu] at hr2
      refine .letE he hr2 ?_
      intro ha0; subst ha0
      simpa using h4'
    · exact (fail_ok h).elim
  next x e =>
    obtain ⟨en, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨⟨t, Γ1⟩, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    obtain ⟨_, h5, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have he := ih.chkV _ _ _ _ _ _ _ hfb h3
    rw [beq_eq (req_ok h4)] at he
    have h5' := req_ok h5
    refine .assign (getO_ok h1) (req_ok h2) he ?_
    intro en1 hf1 ha1 hl
    rw [hf1] at h5'
    simp [ha1, hl] at h5'
  next x ps e _ =>
    obtain ⟨en, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨⟨t, Γ1⟩, h3, h⟩ := bind_ok h
    obtain ⟨⟨t', Γ2⟩, h4, h⟩ := bind_ok h
    obtain ⟨_, h5, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have h2' := req_ok h2
    have h5' := req_ok h5
    simp only [Bool.and_eq_true] at h2' h5'
    obtain ⟨⟨ht, hav⟩, hc⟩ := h5'
    have he := ih.chkV _ _ _ _ _ _ _ hfb h4
    rw [beq_eq ht] at he
    exact .assignPart (getO_ok h1) h2'.1 h2'.2 (ih.path _ _ _ _ _ _ _ hfb h3) he (availB_ok hav)
      (of_decide_eq_true hc)
  next e1 e2 =>
    obtain ⟨r1, h1, h⟩ := bind_ok h
    have hr1 := ih.chk _ _ _ _ _ _ hfb h1
    split at h
    · rename_i t1 Γ1
      obtain ⟨_, h2, h⟩ := bind_ok h
      have hnl : ¬ t1.linear E.P := by simpa using req_ok h2
      have hr2 := ih.chk _ _ _ _ _ _ hfb h
      cases r with
      | ty t Γ2 => exact .seqE hr1 hnl hr2
      | div => intro t Γ2; exact .seqE hr1 hnl (hr2 t Γ2)
    · have hr2 := ih.chk _ _ _ _ _ _ hfb h
      cases r with
      | ty t Γ2 => exact .seqE (hr1 .unit Γ) (unit_nonlinear _) hr2
      | div => intro t Γ2; exact .seqE (hr1 .unit Γ) (unit_nonlinear _) (hr2 t Γ2)
  next c a b =>
    obtain ⟨⟨tc, Γ1⟩, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨ra, h3, h⟩ := bind_ok h
    obtain ⟨rb, h4, h⟩ := bind_ok h
    have hc := ih.chkV _ _ _ _ _ _ _ hfb h1
    rw [beq_eq (req_ok h2)] at hc
    have hra := ih.chk _ _ _ _ _ _ hfb h3
    have hrb := ih.chk _ _ _ _ _ _ hfb h4
    cases ra with
    | ty t Γ2 =>
      cases rb with
      | ty t' Γ2' =>
        simp only [joinR] at h
        obtain ⟨_, h5, h⟩ := bind_ok h
        have := pure_ok h; subst this
        have h5' := req_ok h5
        simp only [Bool.and_eq_true] at h5'
        obtain ⟨e1, e2⟩ := h5'
        have hrb' : Ty3 E Δ Γ1 b t Γ2 := by rw [beq_eq e1, beq_eq e2]; exact hrb
        exact .ite hc hra hrb'
      | div => simp only [joinR] at h; have := pure_ok h; subst this; exact .ite hc hra (hrb _ _)
    | div =>
      cases rb with
      | ty t' Γ2' => simp only [joinR] at h; have := pure_ok h; subst this; exact .ite hc (hra _ _) hrb
      | div =>
        simp only [joinR] at h; have := pure_ok h; subst this
        intro t Γ2; exact .ite hc (hra _ _) (hrb _ _)
  next e arms =>
    obtain ⟨⟨t0, Γ1⟩, h1, h⟩ := bind_ok h
    obtain ⟨rs, h2, h⟩ := bind_ok h
    have he := ih.chkV _ _ _ _ _ _ _ hfb h1
    have hrs := ih.arms _ _ _ _ _ _ _ hfb h2
    split at h
    · rename_i t Γ2 hft
      obtain ⟨_, h3, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have hall := List.all_eq_true.1 (req_ok h3)
      refine .mtch he (hrs.armsTy E fun r hr tc htc => ?_)
      have := hall r hr
      rw [htc] at this
      exact beq_eq this
    · rename_i hft
      have := pure_ok h; subst this
      intro t Γ2
      exact .mtch he (hrs.armsTy E fun r hr tc htc => by rw [firstTy_none hft r hr] at htc; cases htc)
  next c body =>
    obtain ⟨⟨tc, Γ1⟩, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    obtain ⟨rb, h3, h⟩ := bind_ok h
    have h2' := req_ok h2
    simp only [Bool.and_eq_true] at h2'
    obtain ⟨htc, hΓ⟩ := h2'
    have hc := ih.chkV _ _ _ _ _ _ _ hfb h1
    rw [beq_eq htc, beq_eq hΓ] at hc
    have hb := ih.chk (Δ.withLoop Γ) fb Γ body _ _ hfb h3
    split at h
    · rename_i t Γb
      obtain ⟨_, h4, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have h4' := req_ok h4
      simp only [Bool.and_eq_true] at h4'
      obtain ⟨hΓb, hnl⟩ := h4'
      rw [beq_eq hΓb] at hb
      have hb' : Ty3 E (Δ.withLoop Γ) Γ body t Γ := hb
      exact .while hc hb' (by simpa using hnl)
    · have := pure_ok h; subst this
      exact .while hc (hb .unit Γ) (unit_nonlinear _)
  next e =>
    obtain ⟨_, h1, h⟩ := bind_ok h
    obtain ⟨⟨t, Γ1⟩, h2, h⟩ := bind_ok h
    obtain ⟨_, h3, h⟩ := bind_ok h
    obtain ⟨_, h4, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have he := ih.chkV _ _ _ _ _ _ _ hfb h2
    rw [beq_eq (req_ok h3)] at he
    intro t' Γ'
    exact .ret (req_ok h1) he (retOkB_sound E.P hfb (req_ok h4))
  next =>
    split at h
    · rename_i Γl hl
      obtain ⟨_, h1, h⟩ := bind_ok h
      have := pure_ok h; subst this
      intro t Γ'
      exact .brk hl (loopOkB_sound E.P (req_ok h1))
    · exact (fail_ok h).elim
  next =>
    split at h
    · rename_i Γl hl
      obtain ⟨_, h1, h⟩ := bind_ok h
      have := pure_ok h; subst this
      intro t Γ'
      exact .cont hl (loopOkB_sound E.P (req_ok h1))
    · exact (fail_ok h).elim
  next e =>
    obtain ⟨_, h1, h⟩ := bind_ok h
    obtain ⟨⟨t0, Γ1⟩, h2, h⟩ := bind_ok h
    obtain ⟨_, h3, h⟩ := bind_ok h
    obtain ⟨t, h4, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have he := ih.chkV _ _ _ _ _ _ _ hfb h2
    have hr := retOkB_sound E.P hfb (req_ok h3)
    have hex := req_ok h1
    rcases tryTy_ok (getO_ok h4) with ⟨rfl, t', hret⟩ | ⟨er, t', rfl, hret⟩
    · exact .tryOpt hex he hret hr
    · exact .tryRes hex he hret hr
  next t0 e =>
    obtain ⟨r', h1, h⟩ := bind_ok h
    obtain ⟨_, -, h⟩ := bind_ok h
    have := pure_ok h; subst this
    have hr := ih.chk _ _ _ _ _ _ hfb h1
    cases r' with
    | ty t Γ' => exact .ann rfl hr
    | div => intro t Γ'; exact .ann rfl (hr t Γ')
  next => exact (fail_ok h).elim

end

section
variable {E : CEnv}

theorem armRes_ok {Δ : Sig} {Γ : Ctx} {body : Expr} {k : Nat} {rb : R} {bs : List (String × Ty)}
    (hk : k = bs.length) (hb : RSound E Δ (bindCtx bs ++ Γ) body rb) (hr : (armRes E.P k rb).isSome = true) :
    ∃ t Γ', armRes E.P k rb = some (t, Γ') ∧ ∃ Γb, Ty3 E Δ (bindCtx bs ++ Γ) body t (Γb ++ Γ') ∧
      Γb.length = bs.length ∧ Ctx.noLinear E.P Γb := by
  cases rb with
  | div => simp [armRes] at hr
  | ty t Γr =>
    simp only [armRes] at hr ⊢
    split
    · rename_i hc
      refine ⟨t, _, rfl, Γr.take k, ?_, by simp [← hk]; omega, noLinearB_sound E.P hc.2⟩
      rw [List.take_append_drop]; exact hb
    · rename_i hc; simp [hc] at hr

theorem sound_succ {n : Nat} (ih : Sound E n) : Sound E (n + 1) := by
  have hchk := chk_succ ih
  refine ⟨hchk, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · -- chkV
    intro Δ fb Γ e exp t Γ' hfb h
    simp only [chkV] at h
    obtain ⟨r, h1, h⟩ := bind_ok h
    have hr := hchk _ _ _ _ _ _ hfb h1
    split at h
    · have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this; exact hr
    · exact (fail_ok h).elim
  · -- chkList
    intro Δ fb Γ es hints same ts Γ' hfb h
    cases es with
    | nil => simp only [chkList] at h; have := pure_ok h; simp only [Prod.mk.injEq] at this
             obtain ⟨rfl, rfl⟩ := this; exact .nil
    | cons e es =>
      simp only [chkList] at h
      obtain ⟨⟨t, Γ1⟩, h1, h⟩ := bind_ok h
      obtain ⟨⟨ts', Γ2⟩, h2, h⟩ := bind_ok h
      have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this
      exact .cons (ih.chkV _ _ _ _ _ _ _ hfb h1) (tailSig_ok E.P Δ t)
        (ih.list _ _ _ _ _ _ _ _ (by rw [tailSig_fin]; exact hfb) h2)
  · -- chkArgs
    intro Δ fb Γ ms es pats σp ts Γ' σp' hfb h
    unfold chkArgs at h
    split at h
    · have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl, -⟩ := this; exact .nil
    · rename_i ms e es
      obtain ⟨⟨t, Γ1⟩, h1, h⟩ := bind_ok h
      obtain ⟨⟨ts', Γ2, σp2⟩, h2, h⟩ := bind_ok h
      have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl, -⟩ := this
      exact .val (ih.chkV _ _ _ _ _ _ _ hfb h1) (tailSig_ok E.P Δ t)
        (ih.args _ _ _ _ _ _ _ _ _ _ (by rw [tailSig_fin]; exact hfb) h2)
    · rename_i m ms x ps es hm
      obtain ⟨en, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      obtain ⟨⟨t, Γ1⟩, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      obtain ⟨⟨ts', Γ2, σp2⟩, h5, h⟩ := bind_ok h
      obtain ⟨_, h6, h⟩ := bind_ok h
      have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl, -⟩ := this
      have h2' := req_ok h2
      have h4' := req_ok h4
      simp only [Bool.and_eq_true, Bool.or_eq_true, bne_iff_ne, ne_eq] at h2' h4'
      have hmv : m ≠ .val := by
        rintro rfl
        first | exact hm rfl | exact hm rfl rfl | exact hm _ _ _ rfl rfl | exact hm ms _ es rfl rfl
      refine .byRef hmv (getO_ok h1) h2'.1 (fun hmu => h2'.2.resolve_left (by simp [hmu]))
        (ih.path _ _ _ _ _ _ _ hfb h3) (availB_ok h4'.1) (of_decide_eq_true h4'.2)
        (ih.args _ _ _ _ _ _ _ _ _ _ hfb h5) (availAtB_ok (req_ok h6))
    · exact (fail_ok h).elim
  · -- chkOpnds
    intro Δ fb Γ es p pre ts Γ' hfb h
    unfold chkOpnds at h
    split at h
    · have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this; exact .nil
    · rename_i x ps es
      obtain ⟨en, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      obtain ⟨⟨t, Γ1⟩, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      obtain ⟨⟨ts', Γ2⟩, h5, h⟩ := bind_ok h
      obtain ⟨_, h6, h⟩ := bind_ok h
      have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this
      exact .place (getO_ok h1) (req_ok h2) (ih.path _ _ _ _ _ _ _ hfb h3) (availB_ok (req_ok h4))
        (ih.opnds _ _ _ _ _ _ _ _ hfb h5) (availAtB_ok (req_ok h6))
    · rename_i e es hnp
      obtain ⟨⟨t, Γ1⟩, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      obtain ⟨⟨ts', Γ2⟩, h3, h⟩ := bind_ok h
      have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this
      exact .val (fun x ps he => by first | exact hnp x ps he | exact hnp x ps es he) (ih.chkV _ _ _ _ _ _ _ hfb h1)
        (of_decide_eq_true (req_ok h2)) (ih.opnds _ _ _ _ _ _ _ _ hfb h3)
  · -- chkPath
    intro Δ fb Γ T ps t Γ' hfb h
    unfold chkPath at h
    split at h
    · have := pure_ok h; simp only [Prod.mk.injEq] at this; obtain ⟨rfl, rfl⟩ := this; exact .nil
    · rename_i f ps s args
      obtain ⟨d, h1, h⟩ := bind_ok h
      obtain ⟨i, h2, h⟩ := bind_ok h
      obtain ⟨ft, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      have hi := getO_ok h2
      split at hi
      · rename_i hs
        exact .fld (getO_ok h1) hs hi (getO_ok h3) (beq_eq (req_ok h4)) (ih.path _ _ _ _ _ _ _ hfb h)
      · cases hi
    · rename_i i ps ts
      obtain ⟨ti, h1, h⟩ := bind_ok h
      exact .tfld (getO_ok h1) (ih.path _ _ _ _ _ _ _ hfb h)
    · rename_i e ps el
      obtain ⟨⟨ti, Γ1⟩, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      have he := ih.chkV _ _ _ _ _ _ _ hfb h1
      rw [beq_eq (req_ok h2)] at he
      exact .idxList he (ih.path _ _ _ _ _ _ _ hfb h)
    · rename_i e ps k v
      obtain ⟨⟨tk, Γ1⟩, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      have h2' := req_ok h2
      simp only [Bool.and_eq_true] at h2'
      have he := ih.chkV _ _ _ _ _ _ _ hfb h1
      rw [beq_eq h2'.1] at he
      exact .idxMap he (of_decide_eq_true h2'.2) (ih.path _ _ _ _ _ _ _ hfb h)
    · exact (fail_ok h).elim
  · -- chkArms
    intro Δ fb Γ t0 arms exp rs hfb h
    unfold chkArms at h
    split at h
    · have := pure_ok h; subst this; trivial
    · rename_i p g body arms
      obtain ⟨bs, h1, h⟩ := bind_ok h
      obtain ⟨_, h2, h⟩ := bind_ok h
      obtain ⟨tg, h3, h⟩ := bind_ok h
      obtain ⟨_, h4, h⟩ := bind_ok h
      obtain ⟨rb, h5, h⟩ := bind_ok h
      obtain ⟨_, h6, h⟩ := bind_ok h
      obtain ⟨rs', h7, h⟩ := bind_ok h
      have := pure_ok h; subst this
      have hp := (patTy_sound E.P 64).1 (getO_ok h1)
      have hgc : g.isSome → t0.copyable E.P := by
        intro hs
        have := req_ok h2
        simp only [Bool.or_eq_true, decide_eq_true_eq] at this
        rcases this with hn | hc
        · cases g with
          | none => cases hs
          | some _ => cases hn
        · exact hc
      have h4' := req_ok h4
      simp only [Bool.and_eq_true] at h4'
      have hgt : ∀ ge, g = some ge → Ty3 E Δ (bindCtx bs ++ Γ) ge .bool (bindCtx bs ++ Γ) := by
        intro ge hge
        subst hge
        have hg := ih.chkV _ _ _ _ _ _ _ hfb h3
        rw [beq_eq h4'.1, beq_eq h4'.2] at hg
        exact hg
      have hb := ih.chk _ _ _ _ _ _ hfb h5
      refine ⟨?_, ih.arms _ _ _ _ _ _ _ hfb h7⟩
      have h6' := req_ok h6
      simp only [Bool.or_eq_true] at h6'
      rcases h6' with hs | hd
      · obtain ⟨t, Γ', he, Γb, hbt, hl, hn⟩ := armRes_ok rfl hb hs
        simp only [he]
        exact ⟨bs, Γb, hp, hgc, hgt, hbt, hl, hn⟩
      · cases rb with
        | ty t Γr => simp at hd
        | div =>
          simp only [armRes]
          exact armOk_div E hp hgc hgt hb

theorem sound (n : Nat) : Sound E n := by
  induction n with
  | zero => exact sound_zero E
  | succ n ih => exact sound_succ ih

end

/-! ## Programs -/

section
variable {E : CEnv}

/-- The frame of a function whose body always exits early: by-value parameters consumed. -/
def doneCtx : List (String × Mode) → List Ty → Ctx
  | p :: ps, t :: ts => ⟨p.1, t, p.2 == .mut, p.2 != .val⟩ :: doneCtx ps ts
  | _, _ => []

theorem finFn_done (P : Prog) (owner : Option String) :
    ∀ (ps : List (String × Mode)) (tys : List Ty), tys.length = ps.length → FinFn P owner ps (doneCtx ps tys)
  | [], [], _ => trivial
  | (x, m) :: ps, t :: ts, h => by
    refine ⟨?_, finFn_done P owner ps ts (by simpa using h)⟩
    unfold FinEntry
    cases m <;> simp
  | [], _ :: _, h | _ :: _, [], h => by simp at h

theorem chkFn_sound {fuel : Nat} {d : FnDecl} {σ : List Ty} (h : chkFn E fuel d σ = .ok ()) :
    d.params.length = d.ptys.length ∧ σ.length = d.tparams ∧
    ∃ Γ', Ty3 E (fnSig E.P d.owner d.params (d.ret.subst σ)) (paramsCtx d.params (substL σ d.ptys)) d.body
      (d.ret.subst σ) Γ' ∧ FinFn E.P d.owner d.params Γ' := by
  unfold chkFn at h
  obtain ⟨_, h1, h⟩ := bind_ok h
  have h1' := req_ok h1
  simp only [Bool.and_eq_true] at h1'
  have hl := beq_eq h1'.1
  refine ⟨hl, beq_eq h1'.2, ?_⟩
  obtain ⟨r, h2, h⟩ := bind_ok h
  have hr := (sound (E := { E with σ := σ }) fuel).chk _ _ _ _ _ _ (fnSig_fb E.P d.owner d.params _) h2
  split at h
  · rename_i t Γ'
    have h' := req_ok h
    simp only [Bool.and_eq_true] at h'
    have hb : Ty3 E _ _ d.body t Γ' := hr
    rw [beq_eq h'.1] at hb
    exact ⟨Γ', hb, finFnB_sound E.P d.owner h'.2⟩
  · exact ⟨_, hr _ (doneCtx d.params (substL σ d.ptys)),
      finFn_done E.P d.owner d.params _ (by rw [substL_length]; exact hl.symm)⟩

theorem chkInsts_sound {fuel : Nat} : ∀ {L : List (String × List Ty)}, chkInsts E fuel L = .ok () →
    ∀ fσ ∈ L, ∃ d, E.P.fns fσ.1 = some d ∧ chkFn E fuel d fσ.2 = .ok ()
  | [], _, _, hm => by cases hm
  | (f, σ) :: L, h, fσ, hm => by
    simp only [chkInsts] at h
    obtain ⟨d, h1, h⟩ := bind_ok h
    obtain ⟨_, h2, h⟩ := bind_ok h
    simp only [List.mem_cons] at hm
    rcases hm with rfl | hm
    · exact ⟨d, getO_ok h1, h2⟩
    · exact chkInsts_sound h fσ hm

theorem sysOkB_envOk {X : Ext} {prim : PrimSig} {P : Prog} (h : sysOkB P = true) (args : List String) :
    EnvOkX X P prim [("%sys", some (sysVal args))] sysCtx := by
  unfold sysOkB at h
  split at h
  · rename_i d hd
    simp only [Bool.and_eq_true, beq_iff_eq] at h
    obtain ⟨⟨htp, hk⟩, hv⟩ := h
    split at hv
    · rename_i nm ts hvs
      have hts := beq_eq hv
      subst hts
      refine ⟨rfl, ⟨fun _ => ⟨_, rfl, ?_⟩, fun h => by simp [sysCtx] at h⟩, by simp [EnvOkX]⟩
      refine .adt (tag := 0) (name := nm) (ts := sysTys) hd (by rw [hvs]; rfl) (by simp [htp]) (by simp [sysTys])
        ?_ (by rw [hk]; trivial)
      intro q hq
      simp only [substL, sysTys, Ty.subst, List.zip_cons_cons, List.zip_nil_right, List.mem_cons,
        List.not_mem_nil, or_false] at hq
      rcases hq with rfl | rfl | rfl | rfl | rfl | rfl
      · exact .cap
      · exact .cap
      · exact .cap
      · exact .cap
      · exact .cap
      · exact .list fun v hv => by
          simp only [List.mem_map] at hv; obtain ⟨a, -, rfl⟩ := hv; exact .str
    · cases hv
  · cases h

/-- **The checker is sound** for programs: a program `checkAll` accepts (with
`keys` listing its declared types) is well typed (`ProgOkX`) at the instances
`L`, and so is the call of its `main`, in the context of the initial
environment it starts in. -/
theorem checkAll_sound {fuel : Nat} {keys : List (String × AdtDecl)} {L : List (String × List Ty)}
    {main : String} {arity : Nat} (h : checkAll E fuel keys L main arity = .ok ())
    (hk : ∀ s d, E.P.adts s = some d → (s, d) ∈ keys) :
    ProgOkX (XE (E.withInsts L)) E.P (PrE E) ∧ sysOkB E.P = true ∧
    ∃ t Γ', HasTyX (XE (E.withInsts L)) E.P (PrE E) topSig sysCtx (mainCall main arity) t Γ' := by
  unfold checkAll at h
  obtain ⟨_, h1, h⟩ := bind_ok h
  obtain ⟨_, h2, h⟩ := bind_ok h
  obtain ⟨_, h3, h⟩ := bind_ok h
  obtain ⟨_, h4, h⟩ := bind_ok h
  obtain ⟨r, h5, h⟩ := bind_ok h
  refine ⟨⟨adtsOk_of_list E.P keys hk (req_ok h1), stdOkB_sound E.P (req_ok h2), ?_⟩, req_ok h3, ?_⟩
  · intro f d hd σ hσ hi
    have hm : (f, σ) ∈ L := of_decide_eq_true hi
    obtain ⟨d', hd', hc⟩ := chkInsts_sound h4 (f, σ) hm
    have hd2 : E.P.fns f = some d' := hd'
    rw [hd] at hd2; cases hd2
    obtain ⟨hl, -, Γ', hb, hfin⟩ := chkFn_sound hc
    exact ⟨hl, Γ', hb, hfin⟩
  · have hr := (sound (E := E.withInsts L) fuel).chk _ _ _ _ _ _ (fun _ _ => trivial) h5
    cases r with
    | ty t Γ' => exact ⟨t, Γ', hr⟩
    | div => exact ⟨.unit, [], hr _ _⟩

end
end Tenon.Check

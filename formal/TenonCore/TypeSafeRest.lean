/-
The induction on fuel of the type-soundness proof: the evaluator's other
functions (lists, paths, arguments, operands, arms, calls, builtins), and
the theorem (formal/README.md, "Theorems").
-/
import TenonCore.TypeSafeEval

namespace Tenon

section
variable {P : Prog} {prim : PrimSig}

theorem mem_zip_cons {α β} {a : α} {b : β} {as : List α} {bs : List β} {q : α × β}
    (h : q ∈ (a :: as).zip (b :: bs)) : q = (a, b) ∨ q ∈ as.zip bs := by
  simpa using h

theorem ArgsOk.not_moved {Γ : Ctx} {ms : List Mode} {as : List ArgV} {ts : List Ty} (h : ArgsOk P prim Γ ms as ts) :
    ∀ a ∈ as, ∀ x, a.wb ≠ .moved x := by
  induction h with
  | nil => simp
  | cons ha _ ih =>
    intro a hmem x
    rcases List.mem_cons.1 hmem with rfl | hmem
    · exact ha.not_moved x
    · exact ih a hmem x

theorem OpndsOk.vals {Γ : Ctx} {os : List (Val × Option (String × List Step))} {ts : List Ty}
    (h : OpndsOk P prim Γ os ts) :
    (os.map (·.1)).length = ts.length ∧ ∀ q ∈ (os.map (·.1)).zip ts, ValTy P prim q.1 q.2 := by
  induction h with
  | nil => simp
  | cons hv _ _ ih =>
    refine ⟨by simp [ih.1], fun q hq => ?_⟩
    rcases mem_zip_cons hq with rfl | hq
    · exact hv
    · exact ih.2 q hq

theorem SigOk.tailOr {Δ Δ' : Sig} {Γ : Ctx} (h : SigOk Δ Γ) (hΔ : Δ' = Δ.noExit ∨ Δ' = Δ) : SigOk Δ' Γ := by
  rcases hΔ with rfl | rfl
  · exact h.noExit
  · exact h

theorem tySafe_succ (hP : ProgOk P prim) (hprim : PrimsOk P prim) {n : Nat} (ih : TySafe P prim n) :
    TySafe P prim (n + 1) where
  eval := tySafe_eval hP hprim ih
  list := by
    have hA := hP.1
    intro Δ Γ Γ' es ts ρ st h hρ hsig
    cases h with
    | nil => simp only [evalList]; exact ⟨⟨rfl, by simp⟩, hρ, rfl⟩
    | @cons _ Δ' _ e es t ts Γ1 _ he htail hl =>
      simp only [evalList]
      refine OutTy.bind (ih.eval _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
      have hr := ih.list _ _ _ _ _ ρ1 st1 hl hρ1 ((hsig.shape hs1).tail htail)
      revert hr
      cases evalList P n ρ1 st1 es with
      | ok vs ρ2 st2 =>
        intro hr
        obtain ⟨⟨hlen, hvs⟩, hρ2, hs2⟩ := hr
        refine ⟨⟨by simp [hlen], fun q hq => ?_⟩, hρ2, hs2⟩
        rcases mem_zip_cons hq with rfl | hq
        · exact hv
        · exact hvs q hq
      | ctl c ρ2 st2 =>
        intro hr
        rcases htail with ⟨rfl, hnl⟩ | rfl
        · obtain ⟨st3, hd⟩ := discard_ok (hv.noLin hA hnl) st2
          simp only [hd]; exact hr
        · exact (CtlOk.noExit hr).elim
      | err e => intro hr; cases e <;> exact hr
  steps := by
    intro Δ Γ Γ' T ps t ρ st h hρ hsig
    cases h with
    | nil => simp only [evalSteps]; exact ⟨⟨.nil, rfl⟩, hρ, rfl⟩
    | fld hd hs hi hft _ hp =>
      simp only [evalSteps]
      exact OutTy.bind (ih.steps _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 _ =>
        ⟨⟨.cons (.fld hd hs hi hft) hss.1, by simp [hss.2]⟩, hρ1, rfl⟩
    | tfld hti hp =>
      simp only [evalSteps]
      exact OutTy.bind (ih.steps _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 _ =>
        ⟨⟨.cons (.tfld hti) hss.1, by simp [hss.2]⟩, hρ1, rfl⟩
    | idxList he hp =>
      simp only [evalSteps]
      refine OutTy.bind (ih.eval _ _ _ _ _ ρ st he hρ hsig) fun k ρ1 st1 hk hρ1 hs1 => ?_
      cases hk with
      | @int i =>
        simp only [Val.toks, ite_true]
        exact OutTy.bind (ih.steps _ _ _ _ _ _ ρ1 st1 hp hρ1 (hsig.shape hs1)) fun ss ρ2 st2 hss hρ2 _ =>
          ⟨⟨.cons .idxList hss.1, by simp [hss.2]⟩, hρ2, rfl⟩
    | idxMap he hc hp =>
      simp only [evalSteps]
      refine OutTy.bind (ih.eval _ _ _ _ _ ρ st he hρ hsig) fun k ρ1 st1 hk hρ1 hs1 => ?_
      simp only [hk.toks_copy hP.1 hc, ite_true]
      exact OutTy.bind (ih.steps _ _ _ _ _ _ ρ1 st1 hp hρ1 (hsig.shape hs1)) fun ss ρ2 st2 hss hρ2 _ =>
        ⟨⟨.cons (.idxMap hk) hss.1, by simp [hss.2]⟩, hρ2, rfl⟩
  argv := by
    intro Δ Γ Γ' e t ρ st h hρ hsig
    simp only [evalArg]
    exact OutTy.bind (ih.eval _ _ _ _ _ ρ st h hρ hsig) fun v ρ1 st1 hv hρ1 _ => ⟨⟨hv, rfl⟩, hρ1, rfl⟩
  argr := by
    intro Δ Γ Γ' m x ps en t ρ st hm hf ha hp hav hc hρ hsig
    have key : evalArg P (n + 1) ρ st m (.place x ps) =
        (evalSteps P n ρ st ps).bind fun ss ρ1 st1 => placeArg P ρ1 st1 m x ss := by
      cases m with
      | val => exact absurd rfl hm
      | ref => rfl
      | «mut» => rfl
    rw [key]
    refine OutTy.bind (ih.steps _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    obtain ⟨en1, hf1, ha1, hty⟩ := hav.get hs1 hf
    exact (placeArg_ref hP.1 hm hρ1 hf1 ha1 (by rw [hty]; exact hss.1) hc st1).mono
      fun a ⟨hv, hwb⟩ => ⟨hv, ss, hwb, hss.1⟩
  args := by
    have hA := hP.1
    intro Δ Γ Γ' ms es ts ρ st h hρ hsig
    cases h with
    | nil => simp only [evalArgs]; exact ⟨.nil, hρ, rfl⟩
    | @val _ Δ' _ e es ms t ts Γ1 _ he htail hrest =>
      simp only [evalArgs]
      refine OutTy.bind (ih.argv _ _ _ _ _ ρ st he hρ hsig) fun a ρ1 st1 ha hρ1 hs1 => ?_
      obtain ⟨hv, hwb⟩ := ha
      obtain ⟨v, wb⟩ := a; simp only at hwb hv; subst hwb
      have hr := ih.args _ _ _ _ _ _ ρ1 st1 hrest hρ1 ((hsig.shape hs1).tail htail)
      revert hr
      cases evalArgs P n ρ1 st1 ms es with
      | ok as ρ2 st2 => intro hr; exact ⟨.cons (.val hv) hr.1, hr.2⟩
      | ctl c ρ2 st2 =>
        intro hr
        rcases htail with ⟨rfl, hnl⟩ | rfl
        · obtain ⟨st3, hu⟩ := unwindArg_typed (a := ⟨v, .none⟩) (by simp) (hv.noLin hA hnl) ρ2 st2
          simp only [hu]; exact hr
        · exact (CtlOk.noExit hr).elim
      | err e => intro hr; cases e <;> exact hr
    | @byRef _ _ m x ps en t es ms ts Γ1 _ hm hf ha hmut hp hav1 hc hrest hav2 =>
      simp only [evalArgs]
      refine OutTy.bind (ih.argr _ _ _ m x ps en t ρ st hm hf ha hp hav1 hc hρ hsig) fun a ρ1 st1 ha' hρ1 hs1 => ?_
      obtain ⟨hv, ss, hwb, hss⟩ := ha'
      obtain ⟨v, wb⟩ := a; simp only at hwb hv; subst hwb
      have hr := ih.args _ _ _ _ _ _ ρ1 st1 hrest hρ1 (hsig.shape hs1)
      revert hr
      cases evalArgs P n ρ1 st1 ms es with
      | ok as ρ2 st2 =>
        intro hr
        obtain ⟨en2, hf2, ha2, hty2⟩ := hav2
        exact ⟨.cons (.place hm hv hc hf2 ha2 (by rw [hty2]; exact hss)) hr.1, hr.2⟩
      | ctl c ρ2 st2 =>
        intro hr
        obtain ⟨st3, hu⟩ := unwindArg_typed (a := ⟨v, .place x ss⟩) (by simp)
          (hasLin_of_toks (hv.toks_copy hA hc)) ρ2 st2
        simp only [hu]; exact hr
      | err e => intro hr; cases e <;> exact hr
  opp := by
    intro Δ Γ Γ' x ps en t ρ st hf ha hp hav hρ hsig
    simp only [evalOpnd]
    refine OutTy.bind (ih.steps _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    obtain ⟨en1, hf1, ha1, hty⟩ := hav.get hs1 hf
    rcases peek_ty hP.1 hρ1 hf1 ha1 (by rw [hty]; exact hss.1) st1 with ⟨v, hpk, hv⟩ | ⟨mm, hpk⟩
    · rw [hpk]; exact ⟨⟨hv, ss, rfl, hss.1⟩, hρ1, rfl⟩
    · rw [hpk]; trivial
  opv := by
    intro Δ Γ Γ' e t ρ st hnp h hc hρ hsig
    rw [evalOpnd_val hnp]
    refine OutTy.bind (ih.eval _ _ _ _ _ ρ st h hρ hsig) fun v ρ1 st1 hv hρ1 _ => ?_
    simp only [hv.toks_copy hP.1 hc, ite_true]
    exact ⟨⟨hv, rfl⟩, hρ1, rfl⟩
  opnds := by
    intro Δ Γ Γ' es ts ρ st h hρ hsig
    cases h with
    | nil => simp only [evalOpnds]; exact ⟨.nil, hρ, rfl⟩
    | @place _ _ x ps en t es ts Γ1 _ hf ha hp hav1 hrest hav2 =>
      simp only [evalOpnds]
      refine OutTy.bind (ih.opp _ _ _ x ps en t ρ st hf ha hp hav1 hρ hsig) fun o ρ1 st1 ho hρ1 hs1 => ?_
      refine OutTy.bind (ih.opnds _ _ _ _ _ ρ1 st1 hrest hρ1 (hsig.shape hs1)) fun os ρ2 st2 hos hρ2 _ => ?_
      obtain ⟨hv, ss, ho2, hss⟩ := ho
      refine ⟨.cons hv (fun x' ss' h => ?_) hos, hρ2, rfl⟩
      rw [ho2] at h; simp only [Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
      obtain ⟨en2, hf2, ha2, hty2⟩ := hav2
      exact ⟨en2, hf2, ha2, by rw [hty2]; exact hss⟩
    | @val _ _ e t es ts Γ1 _ hnp he hc hrest =>
      simp only [evalOpnds]
      refine OutTy.bind (ih.opv _ _ _ _ _ ρ st hnp he hc hρ hsig) fun o ρ1 st1 ho hρ1 hs1 => ?_
      refine OutTy.bind (ih.opnds _ _ _ _ _ ρ1 st1 hrest hρ1 (hsig.shape hs1)) fun os ρ2 st2 hos hρ2 _ => ?_
      exact ⟨.cons ho.1 (fun x' ss' h => by rw [ho.2] at h; cases h) hos, hρ2, rfl⟩
  arms := by
    have hA := hP.1
    intro Δ Γ Γ' t0 arms t v ρ st h hv hρ hsig
    cases h with
    | nil => simp only [evalArms]; trivial
    | @cons _ _ _ p g body arms _ bs _ Γb hpat hg hgt hbody hlb hnb hrest =>
      simp only [evalArms]
      rcases matchPat_ty hA hpat hv with hm | ⟨b, u, dr, hm, hb, hdr⟩
      · rw [hm]; exact ih.arms _ _ _ _ _ _ v ρ st hrest hv hρ hsig
      · rw [hm]
        have blen : b.length = (bindCtx bs).length := by rw [bindCtx_length, hb.length]
        cases g with
        | none =>
          simp only
          obtain ⟨st1, hd⟩ := discardAll_ok hdr { st with burned := u ++ st.burned }
          simp only [hd]
          have hbe := ih.eval _ _ _ _ _ (pushBinds b ρ) st1 hbody (hb.envOk hρ) (hsig.append _)
          rw [blen]
          exact popScope_ty hA hbe (by rw [hlb, bindCtx_length]) hnb hsig
        | some ge =>
          simp only
          have hc0 := hg rfl
          simp only [hv.toks_copy hA hc0, ite_true]
          have hge := ih.eval _ _ _ _ _ (pushBinds b ρ) st (hgt ge rfl) (hb.envOk hρ) (hsig.append _)
          have hnbc : Ctx.noLinear P (bindCtx bs) :=
            noLinear_bindCtx_of_copyable (PatTy.copyable_binds hA hpat hc0)
          revert hge
          cases eval P n (pushBinds b ρ) st ge with
          | ok gv ρ1 st1 =>
            intro hge
            obtain ⟨hgv, hρ1, _⟩ := hge
            cases hgv with
            | @bool bb =>
              cases bb with
              | true =>
                simp only; rw [blen]
                exact popScope_ty hA (ih.eval _ _ _ _ _ ρ1 st1 hbody hρ1 (hsig.append _))
                  (by rw [hlb, bindCtx_length]) hnb hsig
              | false =>
                simp only
                obtain ⟨st2, hp, hρ2⟩ := popEnv_typed hA hρ1 hnbc st1
                rw [blen, hp]; simp only [Out.bind]
                exact ih.arms _ _ _ _ _ _ v _ st2 hrest hv hρ2 hsig
          | ctl c ρ1 st1 =>
            intro hge
            rw [blen]
            exact popScope_ty (Γbo := bindCtx bs) (Γ' := Γ') (Q := (ValTy P prim · t)) (r := .ctl c ρ1 st1)
              hA hge rfl hnbc hsig
          | err e => intro hge; cases e <;> exact hge
  call := by
    have hA := hP.1
    intro Δ Δ' Γ Γ' ρ st owner ps names cvs body pre args tys r Γb hn hcv htl hb hfin hpl hpre hargs hΔ hρ hsig
    simp only [callWith]
    rw [if_pos ⟨hn, hcv⟩]
    have ha := ih.args _ _ _ _ _ _ ρ st hargs hρ
      (hsig.tailOr (hΔ.imp id (fun h => h.1)))
    revert ha
    cases evalArgs P n ρ st _ args with
    | ok as ρ1 st1 =>
      intro ha
      obtain ⟨has, hρ1, hs1⟩ := ha
      have hall : ArgsOk P prim Γ' (ps.map (·.2)) (pre ++ as) tys := by
        have := hpre.append has
        rwa [← List.map_append, List.take_append_drop, List.take_append_drop] at this
      have hlen : (pre ++ as).length = ps.length := by have := hall.length; simpa using this.1
      simp only [hlen, ite_true]
      exact afterCall_ty hA (ih.eval _ _ _ _ _ _ st1 hb (frameOf_ty hcv ps (pre ++ as) tys hall)
        (SigOk.fn owner ps tys r htl)) hfin htl hall hρ1 hs1
    | ctl c ρ1 st1 =>
      intro ha
      rcases hΔ with rfl | ⟨rfl, hpl'⟩
      · exact (CtlOk.noExit ha).elim
      · obtain ⟨st2, hu⟩ := unwindArgs_typed (fun a ha' => ⟨hpre.not_moved a ha', hpl' a ha'⟩) ρ1 st1
        simp only [hu]; exact ha
    | err e => intro ha; cases e <;> exact ha
  prim := by
    have hA := hP.1
    intro Δ Γ Γ' pf recv args ts t tsA ρ st hpf hc hops hrecv hρ hsig
    simp only [primCall]
    refine OutTy.bind (ih.opnds _ _ _ _ _ ρ st hops hρ hsig) fun os ρ1 st1 hos hρ1 hs1 => ?_
    obtain ⟨hl, hz⟩ := hos.vals
    cases recv with
    | none =>
      simp only [RecvOk] at hrecv; subst hrecv
      refine primApply_ty hA hpf hc hl hz hρ1 ?_ st1
      intro x ss hsp
      cases hos with
      | nil => simp at hsp
      | @cons o os t0 ts ho hpl _ =>
        simp only [List.head?, Option.bind_some] at hsp
        obtain ⟨en, hf, ha, hss⟩ := hpl x ss hsp
        exact ⟨en, t0, hf, ha, rfl, hss⟩
    | some rv =>
      cases rv with
      | inl xs =>
        obtain ⟨x, ss⟩ := xs
        obtain ⟨en, t0, rfl, hf, ha, hss⟩ := hrecv
        simp only
        rcases peek_ty hA hρ1 hf ha hss st1 with ⟨v1, hpk, hv1⟩ | ⟨mm, hpk⟩
        · rw [hpk]; simp only [Out.bind]
          refine primApply_ty hA hpf hc (by simp [hl]) (fun q hq => ?_) hρ1 ?_ st1
          · rcases mem_zip_cons hq with rfl | hq
            · exact hv1
            · exact hz q hq
          · intro x' ss' h; simp only [Option.some.injEq, Prod.mk.injEq] at h; obtain ⟨rfl, rfl⟩ := h
            exact ⟨en, t0, hf, ha, rfl, hss⟩
        · rw [hpk]; trivial
      | inr v0 =>
        obtain ⟨t0, rfl, hv0, hc0⟩ := hrecv
        simp only
        refine primApply_ty hA hpf hc (by simp [hl]) (fun q hq => ?_) hρ1 (fun _ _ h => by cases h) st1
        rcases mem_zip_cons hq with rfl | hq
        · exact hv0
        · exact hz q hq

theorem tySafe (hP : ProgOk P prim) (hprim : PrimsOk P prim) (n : Nat) : TySafe P prim n := by
  induction n with
  | zero => exact tySafe_zero
  | succ n ih => exact tySafe_succ hP hprim ih

end

end Tenon

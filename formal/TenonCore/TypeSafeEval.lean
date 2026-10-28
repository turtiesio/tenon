/-
The induction on fuel of the type-soundness proof (TypeSafe.lean): the
expression cases. TypeSafeRest.lean has the other functions of the evaluator
and the theorem.
-/
import TenonCore.TypeSafe

namespace Tenon

section
variable {X : Ext} {P : Prog} {prim : PrimSig}

theorem tySafe_zero : TySafe X P prim 0 := by
  constructor <;> intros <;>
    simp [eval, evalList, evalSteps, evalArg, evalArgs, evalOpnd, evalOpnds, evalArms, callWith, primCall, OutTy]

theorem loop_exact {Γx Γ : Ctx} (hs : Shape Γx Γ) (h : LoopOk P Γ Γx) : Γx = Γ := by
  have := h.2; rw [hs.length, Nat.sub_self, List.drop_zero] at this; exact this

theorem mem_zip_const {vs : List Val} {es : List Expr} {t : Ty} (hl : vs.length = (es.map fun _ => t).length)
    (h : ∀ q ∈ vs.zip (es.map fun _ => t), ValTyX X P prim q.1 q.2) : ∀ v ∈ vs, ValTyX X P prim v t := by
  intro v hv
  obtain ⟨b, hb⟩ := mem_zip_left hl hv
  have := h _ hb
  obtain ⟨_, _, rfl⟩ := List.mem_map.1 (List.of_mem_zip hb).2
  exact this

/-- Finishing a method call once the receiver is evaluated (TypeSafe's `callWith` part). -/
theorem mcall_finish (hP : ProgOkX X P prim) {n : Nat} (ih : TySafe X P prim n)
    {Δ Δ' : Sig} {Γr Γ2 : Ctx} {d : FnDecl} {σ : List Ty} {p0 : String} {m0 : Mode}
    {prest : List (String × Mode)} {pt0 : Ty} {ptrest : List Ty} {t0 : Ty} {args : List Expr} {f : String}
    (hd : P.fns f = some d) (hσ : σ.length = d.tparams) (hi : X.inst f σ) (hpar : d.params = (p0, m0) :: prest)
    (hpty : d.ptys = pt0 :: ptrest) (hsub : pt0.subst σ = t0) (htail : TailSig P Δ Δ' t0)
    (hargs : ArgsTyX X P prim Δ' Γr (prest.map (·.2)) args (substL σ ptrest) Γ2)
    {a0 : ArgV} (ha0 : ArgOk X P prim Γ2 m0 a0 t0)
    {ρ2 : Env} {st2 : St} (hρ2 : EnvOkX X P prim ρ2 Γr) (hsig : SigOk Δ Γr) :
    OutTy X P prim Δ Γr Γ2 (ValTyX X P prim · (d.ret.subst σ))
      (callWith P n ρ2 st2 d.owner ((p0, m0) :: prest) [] [] d.body [a0] args) := by
  rw [← hpar]
  obtain ⟨hlenp, Γb, hb, hfin⟩ := hP.2.2 f d hd σ hσ hi
  have htys : substL σ d.ptys = t0 :: substL σ ptrest := by rw [hpty]; simp [substL, hsub]
  refine ih.call Δ Δ' Γr Γ2 ρ2 st2 d.owner d.params [] [] d.body [a0] args (substL σ d.ptys) (d.ret.subst σ)
    _ [] Γb rfl rfl (by rw [substL_length]; exact hlenp.symm) (FrameSig.fn _ _ _ _) (by simp) (capEnv_nil rfl)
    (by rw [List.append_nil]; exact hb) hfin.take (by simp [hpar]) ?_ ?_ ?_ hρ2 hsig
  · rw [htys, hpar]; exact .cons ha0 .nil
  · rw [htys, hpar]; exact hargs
  · rcases htail with ⟨rfl, hl⟩ | rfl
    · exact Or.inr ⟨rfl, fun a ha => by simp at ha; subst ha; exact ha0.noLin hP.1 (fun _ => hl)⟩
    · exact Or.inl rfl

/-- The builtin a typed method call selects is the one `resolve` finds. -/
theorem primAt_resolve (hprim : PrimsOkX X P prim) {h m : String} {ts : List Ty} {t : Ty}
    (hd : P.fns (h ++ "." ++ m) = none) (hpr : PrimAt X P prim h m ts t) :
    ∃ pf, resolve P h m = .prim pf ∧ PfOkX X P prim pf ts t := by
  rcases hpr with hpr | ⟨-, hn, hpr⟩
  · obtain ⟨pf, hpf, hok⟩ := hprim _ _ _ hpr
    exact ⟨pf, resolve_prim hd hpf, hok⟩
  · obtain ⟨pf, hpf, hok⟩ := hprim _ _ _ hpr
    exact ⟨pf, by simp [resolve, hd, hn, hpf], hok⟩

/-- The variables a closure captures hold typed values without obligations. -/
theorem captureNames_ty (hA : AdtsOk P) {ρ : Env} {Γ : Ctx} (hρ : EnvOkX X P prim ρ Γ) :
    ∀ {caps : List String} {cts : List Ty}, CapsTy Γ caps cts → (∀ t ∈ cts, t.copyable P) →
    ∃ vs, captureNames ρ caps = some vs ∧ vs.length = cts.length ∧ ∀ q ∈ vs.zip cts, ValTyX X P prim q.1 q.2
  | [], [], .nil, _ => ⟨[], rfl, rfl, by simp⟩
  | x :: caps, t :: cts, .cons hx hr, hc => by
    obtain ⟨en, hf, ha, hty⟩ := hx
    obtain ⟨v, hl, hv⟩ := hρ.lookup_avail hf ha
    rw [hty] at hv
    have hvt := hv.toks_copy hA (hc t (by simp))
    obtain ⟨vs, h1, h2, h3⟩ := captureNames_ty hA hρ hr (fun t' ht' => hc t' (by simp [ht']))
    refine ⟨v :: vs, ?_, by simp [h2], fun q hq => ?_⟩
    · simp [captureNames, hl, h1, hvt]
    · simp only [List.zip_cons_cons, List.mem_cons] at hq
      rcases hq with rfl | hq
      · exact hv
      · exact h3 q hq

theorem tySafe_eval (hP : ProgOkX X P prim) (hprim : PrimsOkX X P prim) {n : Nat} (ih : TySafe X P prim n) :
    ∀ Δ Γ Γ' e t ρ st, HasTyX X P prim Δ Γ e t Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (ValTyX X P prim · t) (eval P (n + 1) ρ st e) := by
  have hA := hP.1
  have hE := ih.eval; have hL := ih.list; have hS := ih.steps; have hM := ih.arms; have hC := ih.call
  have hPc := ih.prim
  intro Δ Γ Γ' e t ρ st h hρ hsig
  cases h with
  | lit => simp only [eval]; exact ⟨Lit.valTy _, hρ, rfl⟩
  | move hf ha =>
    simp only [eval]
    rcases evalSteps_nil (P := P) n ρ st with h0 | h0 <;> rw [h0]
    · trivial
    · exact readPlace_move hA hρ hf ha st
  | copy hf ha hp hav hc =>
    simp only [eval]
    refine OutTy.bind (hS _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    obtain ⟨en', hf', ha', hty⟩ := hav.get hs1 hf
    exact readPlace_copy hA hρ1 hf' ha' (by rw [hty]; exact hss.1) hc st1
  | proj he hc hp =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
    simp only [hv.toks_copy hA hc, ite_true]
    refine OutTy.bind (hS _ _ _ _ _ _ ρ1 st1 hp hρ1 (hsig.shape hs1)) fun ss ρ2 st2 hss hρ2 hs2 => ?_
    have hg := getPath_ty hA hss.1 hv
    revert hg
    cases getPath P v ss with
    | ok w => intro hw; exact ⟨hw, hρ2, rfl⟩
    | error pe => intro hpe; cases pe with
      | trap m => trivial
      | stuck w => exact hpe.elim
  | tup hl =>
    simp only [eval]
    exact OutTy.bind (hL _ _ _ _ _ ρ st hl hρ hsig) fun vs ρ1 st1 hvs hρ1 _ => ⟨.tup hvs.1 hvs.2, hρ1, rfl⟩
  | list hl hc =>
    simp only [eval]
    exact OutTy.bind (hL _ _ _ _ _ ρ st hl hρ hsig) fun vs ρ1 st1 hvs hρ1 _ =>
      ⟨.list (mem_zip_const hvs.1 hvs.2), hρ1, rfl⟩
  | con hd hvar ha hl =>
    simp only [eval]
    refine OutTy.bind (hL _ _ _ _ _ ρ st hl hρ hsig) fun vs ρ1 st1 hvs hρ1 _ => ?_
    simp only [hd]
    exact ⟨.adt hd hvar ha (by rw [hvs.1, substL_length]) hvs.2 (mint_tok _ _), hρ1, rfl⟩
  | lam hl hb hfin =>
    simp only [eval]
    exact ⟨.clo (by simp) (capture_toks ρ) hl hb hfin, hρ, rfl⟩
  | @clos _ _ caps ps body ts r cts Γb hfull hl hcaps hcop hb hfin =>
    simp only [eval]
    obtain ⟨vs, hcn, hlen, hvs⟩ := captureNames_ty hA hρ hcaps hcop
    rw [hcn]
    have ht := captureNames_toks ρ hcn
    exact ⟨.closC hfull ht.2.symm ht.1 hl hlen hvs hcop hb hfin, hρ, rfl⟩
  | ann _ he => simp only [eval]; exact hE _ _ _ _ _ ρ st he hρ hsig
  | @callPrim _ _ f args ts t _ _ hnf hp hops hc =>
    cases n with
    | zero => simp [eval, Out.bind, OutTy]
    | succ k =>
      simp only [eval, Out.bind, hnf]
      obtain ⟨pf, hpf, hok⟩ := hprim _ _ _ hp
      simp only [hpf]
      exact hPc _ _ _ pf none args ts t ts ρ st hok hc hops rfl hρ hsig
  | fnref hf hall hσ hi => simp only [eval]; exact ⟨.fn hf hall hσ hi, hρ, rfl⟩
  | @callv _ _ f args ts r Γ1 _ hf hargs =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st hf hρ hsig) fun fv ρ1 st1 hfv hρ1 hs1 => ?_
    have hal := ArgsTyX.length hargs
    cases hfv with
    | @fn g d σ hg hall hσ hi =>
      simp only [hg]
      obtain ⟨hlenp, Γb, hb, hfin⟩ := hP.2.2 g d hg σ hσ hi
      refine hC Δ Δ Γ1 Γ' ρ1 st1 d.owner d.params [] [] d.body [] args (substL σ d.ptys) _ _ [] Γb rfl rfl
        (by rw [substL_length]; exact hlenp.symm) (FrameSig.fn _ _ _ _) (by simp) (capEnv_nil rfl)
        (by rw [List.append_nil]; exact hb) hfin.take (by simp) (by simp; exact .nil) ?_
        (Or.inr ⟨rfl, by simp⟩) hρ1 (hsig.shape hs1)
      simp only [List.length_nil, List.drop_zero]
      rw [modes_all_val hall (by rw [hlenp, ← substL_length σ, hal.2])]
      exact hargs
    | @clo names cvs ps body ts' r' Γb hn hcv hl hb hfin =>
      simp only
      refine hC Δ Δ Γ1 Γ' ρ1 st1 none (ps.map (·, Mode.val)) names cvs body [] args ts _ _ [] Γb hn hcv
        (by simp [hl]) (FrameSig.fn _ _ _ _) (by simp) (capEnv_nil hcv) (by rw [List.append_nil]; exact hb) hfin.take
        (by simp) (by simp; exact .nil) ?_ (Or.inr ⟨rfl, by simp⟩) hρ1 (hsig.shape hs1)
      simp only [List.length_nil, List.drop_zero]
      rw [modes_all_val (ps := ps.map (·, Mode.val)) (by simp) (by simp only [List.length_map]; exact hl.trans hal.2)]
      exact hargs
    | @closC names cvs ps body ts' r' cts Γb _ hn hcv hl hlen hvs hcop hb hfin =>
      simp only
      have hcl : (capCtx names cts).length = cts.length := capCtx_length (hn.trans hlen)
      refine hC Δ Δ Γ1 Γ' ρ1 st1 none (ps.map (·, Mode.val)) names cvs body [] args _ _ _ (capCtx names cts) Γb hn hcv
        (by simp [hl]) (by rw [hcl]; exact FrameSig.clos P ps cts.length t) (capCtx_nonlinear hcop)
        (capEnv_ty hn hlen hvs) hb (by simpa using hfin)
        (by simp) (by simp; exact .nil) ?_ (Or.inr ⟨rfl, by simp⟩) hρ1 (hsig.shape hs1)
      simp only [List.length_nil, List.drop_zero]
      rw [modes_all_val (ps := ps.map (·, Mode.val)) (by simp) (by simp only [List.length_map]; exact hl.trans hal.2)]
      exact hargs
  | @call _ _ f d σ args _ hf hσ hi hargs =>
    cases n with
    | zero => simp [eval, Out.bind, OutTy]
    | succ k =>
      simp only [eval, Out.bind, hf]
      obtain ⟨hlenp, Γb, hb, hfin⟩ := hP.2.2 f d hf σ hσ hi
      exact hC Δ Δ Γ Γ' ρ st d.owner d.params [] [] d.body [] args (substL σ d.ptys) _ _ [] Γb rfl rfl
        (by rw [substL_length]; exact hlenp.symm) (FrameSig.fn _ _ _ _) (by simp) (capEnv_nil rfl)
        (by rw [List.append_nil]; exact hb) hfin.take (by simp) (by simp; exact .nil)
        (by simpa using hargs) (Or.inr ⟨rfl, by simp⟩) hρ hsig
  | @mcallP _ Δ' _ m x ps en t0 d σ p0 m0 prest pt0 ptrest args Γ1 Γr _ hf ha hp hav1 hvar hd hσ hi hpar hpty
      hsub hval hnval htail hargs =>
    simp only [eval]
    refine OutTy.bind (hS _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    obtain ⟨en1, hf1, ha1, hty1⟩ := hav1.get hs1 hf
    have hss1 : StepsTy X P prim en1.ty ss t0 := by rw [hty1]; exact hss.1
    rcases peek_ty hA hρ1 hf1 ha1 hss1 st1 with ⟨v0, hpk, hv0⟩ | ⟨mm, hpk⟩
    · rw [hpk]; simp only [Out.bind]
      rw [hv0.head, resolve_tenon hd]; simp only [hpar]
      cases m0 with
      | val =>
        rcases hval rfl with ⟨rfl, rfl⟩ | ⟨rfl, hc⟩
        · have hss0 : ss = [] := by have := hss.2; simp at this; exact this
          subst hss0
          have ht0 : en1.ty = t0 := by cases hss1; rfl
          have hpa := placeArg_val (readPlace_move hA (Δ := Δ) hρ1 hf1 ha1 st1)
          refine OutTy.bind hpa fun a0 ρ2 st2 ha0 hρ2 hs2 => ?_
          obtain ⟨hv, hwb⟩ := ha0
          obtain ⟨v, wb⟩ := a0; simp only at hwb; subst hwb
          exact mcall_finish hP ih hd hσ hi hpar hpty hsub htail hargs (.val (ht0 ▸ hv))
            hρ2 ((hsig.shape hs1).shape hs2)
        · have hpa := placeArg_val (readPlace_copy hA (Δ := Δ) hρ1 hf1 ha1 hss1 hc st1)
          refine OutTy.bind hpa fun a0 ρ2 st2 ha0 hρ2 hs2 => ?_
          obtain ⟨hv, hwb⟩ := ha0
          obtain ⟨v, wb⟩ := a0; simp only at hwb; subst hwb
          exact mcall_finish hP ih hd hσ hi hpar hpty hsub htail hargs (.val hv)
            hρ2 ((hsig.shape hs1).shape hs2)
      | ref | «mut» =>
        obtain ⟨rfl, hc, en2, hf2, ha2, hty2⟩ := hnval (by simp)
        refine OutTy.bind (placeArg_ref hA (by simp) hρ1 hf1 ha1 hss1 hc st1) fun a0 ρ2 st2 ha0 hρ2 hs2 => ?_
        obtain ⟨hv, hwb⟩ := ha0
        obtain ⟨v, wb⟩ := a0; simp only at hwb; subst hwb
        exact mcall_finish hP ih hd hσ hi hpar hpty hsub htail hargs
          (.place (by simp) hv hc hf2 ha2 (by rw [hty2]; exact hss.1)) hρ2 ((hsig.shape hs1).shape hs2)
    · rw [hpk]; trivial
  | @mcallV _ Δ' _ m recv t0 d σ p0 prest pt0 ptrest args Γ1 _ hnp hr hvar hd hσ hi hpar hpty hsub htail hargs =>
    rw [eval_mcall_val hnp]
    refine OutTy.bind (hE _ _ _ _ _ ρ st hr hρ hsig) fun v0 ρ1 st1 hv0 hρ1 hs1 => ?_
    rw [hv0.head, resolve_tenon hd]; simp only [hpar]
    exact mcall_finish hP ih hd hσ hi hpar hpty hsub htail hargs (.val hv0) hρ1 (hsig.shape hs1)
  | @mprimP _ _ m x ps en t0 ts t args Γ1 _ hf ha hp hav1 hvar hd hpr hops hav hc =>
    simp only [eval]
    refine OutTy.bind (hS _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    obtain ⟨en1, hf1, ha1, hty1⟩ := hav1.get hs1 hf
    have hss1 : StepsTy X P prim en1.ty ss t0 := by rw [hty1]; exact hss.1
    rcases peek_ty hA hρ1 hf1 ha1 hss1 st1 with ⟨v0, hpk, hv0⟩ | ⟨mm, hpk⟩
    · rw [hpk]; simp only [Out.bind]
      obtain ⟨pf, hpf, hok⟩ := primAt_resolve hprim hd hpr
      rw [hv0.head, hpf]; simp only
      obtain ⟨en2, hf2, ha2, hty2⟩ := hav
      exact (hPc _ _ _ pf _ args ts t _ ρ1 st1 hok hc hops ⟨en2, t0, rfl, hf2, ha2, by rw [hty2]; exact hss.1⟩ hρ1
        (hsig.shape hs1))
    · rw [hpk]; trivial
  | @mprimV _ _ m recv t0 ts t args Γ1 _ hnp hr hc0 hvar hd hpr hops hc =>
    rw [eval_mcall_val hnp]
    refine OutTy.bind (hE _ _ _ _ _ ρ st hr hρ hsig) fun v0 ρ1 st1 hv0 hρ1 hs1 => ?_
    obtain ⟨pf, hpf, hok⟩ := primAt_resolve hprim hd hpr
    rw [hv0.head, hpf]; simp only [hv0.toks_copy hA hc0, ite_true]
    exact hPc _ _ _ pf _ args ts t _ ρ1 st1 hok hc hops ⟨t0, rfl, hv0, hc0⟩ hρ1 (hsig.shape hs1)
  | @prim _ _ p args ts t _ hp hops hc =>
    simp only [eval]
    obtain ⟨pf, hpf, hok⟩ := hprim _ _ _ hp
    simp only [hpf]
    exact hPc _ _ _ pf none args ts t ts ρ st hok hc hops rfl hρ hsig
  | @letE _ _ x mu e1 body t1 _ Γ1 a Γ2 he hb ha =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
    have hb' := hE _ _ _ _ _ ((x, some v) :: ρ1) st1 hb ⟨rfl, ⟨fun _ => ⟨v, rfl, hv⟩, fun h => by simp at h⟩, hρ1⟩
      ((hsig.shape hs1).cons _)
    exact popScope_ty (Γb := [_]) (Γbo := [_]) hA hb' rfl (noLinear_cons.2 ⟨ha, noLinear_nil⟩) (hsig.shape hs1)
  | @assign _ _ x e1 en Γ1 hf hm he hl =>
    simp only [eval]
    rcases evalSteps_nil (P := P) n ρ st with h0 | h0 <;> rw [h0]
    · trivial
    · simp only [Out.bind]
      refine OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ2 st2 hv hρ2 hs2 => ?_
      obtain ⟨en1, hf1, hk⟩ := hs2.find hf
      have hty : en1.ty = en.ty := Entry.key_ty hk
      obtain ⟨st', has, hρ'⟩ := assignAt_whole hA hρ2 hf1 (hty ▸ hv) (fun hav => hty ▸ hl en1 hf1 hav) st2
      rw [has]; exact ⟨.unit, hρ', Shape.setAvail _ _ _⟩
  | @assignPart _ _ x ps e1 t1 en Γ1 Γ2 hf hm ha hp he hav hc =>
    simp only [eval]
    refine OutTy.bind (hS _ _ _ _ _ _ ρ st hp hρ hsig) fun ss ρ1 st1 hss hρ1 hs1 => ?_
    refine OutTy.bind (hE _ _ _ _ _ ρ1 st1 he hρ1 (hsig.shape hs1)) fun v ρ2 st2 hv hρ2 hs2 => ?_
    obtain ⟨en2, hf2, ha2, hty⟩ := hav.get (hs2.trans hs1) hf
    rcases assignAt_part hA hρ2 hf2 ha2 (by rw [hty]; exact hss.1) hc hv st2 with ⟨ρ', st', h1, h2⟩ | ⟨mm, st', h1⟩
    · rw [h1]; exact ⟨.unit, h2, rfl⟩
    · rw [h1]; trivial
  | seqE h1 hl h2 =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st h1 hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
    obtain ⟨st2, hd⟩ := discard_ok (hv.noLin hA hl) st1
    simp only [hd]
    exact hE _ _ _ _ _ ρ1 st2 h2 hρ1 (hsig.shape hs1)
  | ite hc ha hb =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st hc hρ hsig) fun cv ρ1 st1 hcv hρ1 hs1 => ?_
    cases hcv with
    | @bool b =>
      cases b
      · exact hE _ _ _ _ _ ρ1 st1 hb hρ1 (hsig.shape hs1)
      · exact hE _ _ _ _ _ ρ1 st1 ha hρ1 (hsig.shape hs1)
  | mtch he harms =>
    simp only [eval]
    exact OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 =>
      hM _ _ _ _ _ _ v ρ1 st1 harms hv hρ1 (hsig.shape hs1)
  | «while» hc hb hl =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st hc hρ hsig) fun cv ρ1 st1 hcv hρ1 hs1 => ?_
    cases hcv with
    | @bool b =>
      cases b with
      | false => exact ⟨.unit, hρ1, rfl⟩
      | true =>
        simp only
        have hbody := hE _ _ _ _ _ ρ1 st1 hb hρ1 hsig.withLoop
        revert hbody
        cases eval P n ρ1 st1 _ with
        | ok v ρ2 st2 =>
          intro hbody
          obtain ⟨hv, hρ2, _⟩ := hbody
          obtain ⟨st3, hd⟩ := discard_ok (hv.noLin hA hl) st2
          simp only [hd]
          exact hE _ _ _ _ _ ρ2 st3 (.while hc hb hl) hρ2 hsig
        | ctl c ρ2 st2 =>
          cases c with
          | ret v => intro hbody; exact hbody
          | brk =>
            intro hbody
            obtain ⟨Γl, hl', Γx, hsx, hρx, hlx⟩ := hbody
            simp [Sig.withLoop] at hl'; subst hl'
            have := loop_exact hsx hlx; subst this
            exact ⟨.unit, hρx, rfl⟩
          | cont =>
            intro hbody
            obtain ⟨Γl, hl', Γx, hsx, hρx, hlx⟩ := hbody
            simp [Sig.withLoop] at hl'; subst hl'
            have := loop_exact hsx hlx; subst this
            exact hE _ _ _ _ _ ρ2 st2 (.while hc hb hl) hρx hsig
        | err e => intro hbody; cases e <;> exact hbody
  | ret hex he hr =>
    simp only [eval]
    exact OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ⟨hex, hv, _, rfl, hρ1, hr⟩
  | brk hl hlo => simp only [eval]; exact ⟨_, hl, Γ, rfl, hρ, hlo⟩
  | cont hl hlo => simp only [eval]; exact ⟨_, hl, Γ, rfl, hρ, hlo⟩
  | tryOpt hex he hret hr =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
    rcases tryVal_opt hP.2.1 hv with ⟨x, hx, hxv⟩ | hx
    · rw [hx]; exact ⟨hxv, hρ1, rfl⟩
    · rw [hx]; exact ⟨hex, hret ▸ ValTyX.none_opt hP.2.1 _, _, rfl, hρ1, hr⟩
  | tryRes hex he hret hr =>
    simp only [eval]
    refine OutTy.bind (hE _ _ _ _ _ ρ st he hρ hsig) fun v ρ1 st1 hv hρ1 hs1 => ?_
    rcases tryVal_res hP.2.1 hv with ⟨x, hx, hxv⟩ | ⟨er, hx, hev⟩
    · rw [hx]; exact ⟨hxv, hρ1, rfl⟩
    · rw [hx]; exact ⟨hex, hret ▸ ValTyX.err_res hP.2.1 _ hev, _, rfl, hρ1, hr⟩

end

end Tenon

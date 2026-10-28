/-
Worker isolation (formal/README.md, "Theorems"; reference §18).

A machine of workers over one heap whose cells are tagged with the worker
that owns them. Worker-local steps (computing, writing a cell, allocating)
only use what the worker reaches. A message crosses to another worker only
through `send`/`recv` (and `spawn`'s argument), and only as a `Msg`: a
location-free tree made by `Marshal`, the deep copy that the `Send` rule
makes possible. `Marshal` has no case for a cell that is not sendable (a
socket: `Listener`, `Conn`, `Poller`), as `Send` excludes them; `recv`
rebuilds the message in fresh cells of the receiver. Linear values are not
`Send` at all (Linear.lean covers obligations); unique values are moved:
`send` with `move` removes the value from the sender.

Theorem `step_isolated`: every step keeps the invariant that every cell a
worker reaches exists and is owned by that worker. Corollary
`no_shared_cell`: no cell is reachable from two workers — no data race.
-/
namespace Tenon.Workers


/-- Values in a worker's heap: data, pointers to cells (buffers, strings, sockets), tuples. -/
inductive HV where
  | int (i : Int)
  | ptr (l : Nat)
  | tup (vs : List HV)

mutual
def HV.locs : HV → List Nat
  | .int _ => []
  | .ptr l => [l]
  | .tup vs => locsL vs
def locsL : List HV → List Nat
  | [] => []
  | v :: vs => v.locs ++ locsL vs
end

structure Cell where
  owner : Nat
  sendable : Bool      -- false: a socket, bound to the worker that opened it
  vs : List HV

/-- A message: what crosses between workers; it holds no location. -/
inductive Msg where
  | int (i : Int)
  | buf (ms : List Msg)
  | tup (ms : List Msg)

abbrev Heap := Nat → Option Cell

def upd {α : Type} (f : Nat → α) (k : Nat) (a : α) : Nat → α := fun j => if j = k then a else f j

/-- The cells reachable from some roots. -/
inductive Reach (h : Heap) (roots : List HV) : Nat → Prop
  | root {v : HV} {l : Nat} : v ∈ roots → l ∈ v.locs → Reach h roots l
  | step {l : Nat} {c : Cell} {v : HV} {l' : Nat} : Reach h roots l → h l = some c → v ∈ c.vs → l' ∈ v.locs →
      Reach h roots l'

/- The `Send` rule at run time: a deep copy, refused for sockets. -/
mutual
inductive Marshal (h : Heap) : HV → Msg → Prop
  | int {i : Int} : Marshal h (.int i) (.int i)
  | buf {l : Nat} {c : Cell} {ms : List Msg} : h l = some c → c.sendable = true → MarshalL h c.vs ms →
      Marshal h (.ptr l) (.buf ms)
  | tup {vs : List HV} {ms : List Msg} : MarshalL h vs ms → Marshal h (.tup vs) (.tup ms)
inductive MarshalL (h : Heap) : List HV → List Msg → Prop
  | nil : MarshalL h [] []
  | cons {v : HV} {m : Msg} {vs : List HV} {ms : List Msg} : Marshal h v m → MarshalL h vs ms →
      MarshalL h (v :: vs) (m :: ms)
end

/- Rebuild a message in fresh cells owned by worker `w`, from location `n` on. -/
mutual
inductive Unm (w : Nat) : Heap → Nat → Msg → Heap → Nat → HV → Prop
  | int {h : Heap} {n : Nat} {i : Int} : Unm w h n (.int i) h n (.int i)
  | buf {h h1 : Heap} {n n1 : Nat} {ms : List Msg} {vs : List HV} : UnmL w h n ms h1 n1 vs →
      Unm w h n (.buf ms) (upd h1 n1 (some ⟨w, true, vs⟩)) (n1 + 1) (.ptr n1)
  | tup {h h1 : Heap} {n n1 : Nat} {ms : List Msg} {vs : List HV} : UnmL w h n ms h1 n1 vs →
      Unm w h n (.tup ms) h1 n1 (.tup vs)
inductive UnmL (w : Nat) : Heap → Nat → List Msg → Heap → Nat → List HV → Prop
  | nil {h : Heap} {n : Nat} : UnmL w h n [] h n []
  | cons {h h1 h2 : Heap} {n n1 n2 : Nat} {m : Msg} {ms : List Msg} {v : HV} {vs : List HV} :
      Unm w h n m h1 n1 v → UnmL w h1 n1 ms h2 n2 vs → UnmL w h n (m :: ms) h2 n2 (v :: vs)
end

structure Cfg where
  heap : Heap
  next : Nat                         -- every location from here on is free
  workers : Nat → Option (List HV)   -- a worker's roots (its variables)
  chans : Nat → List Msg

def Cfg.setRoots (cfg : Cfg) (w : Nat) (rs : List HV) : Cfg := { cfg with workers := upd cfg.workers w (some rs) }

/-- Everything worker `w` may compute with: values whose cells it reaches. -/
def Within (h : Heap) (roots vs : List HV) : Prop := ∀ v ∈ vs, ∀ l ∈ v.locs, Reach h roots l

inductive Step : Cfg → Cfg → Prop
  /-- Compute: new roots built from what the worker reaches (copying, dropping, building tuples). -/
  | compute {cfg : Cfg} {w : Nat} {rs rs' : List HV} : cfg.workers w = some rs → Within cfg.heap rs rs' →
      Step cfg ⟨cfg.heap, cfg.next, upd cfg.workers w (some rs'), cfg.chans⟩
  /-- Write a cell the worker reaches. -/
  | write {cfg : Cfg} {w : Nat} {rs : List HV} {l : Nat} {c : Cell} {vs : List HV} :
      cfg.workers w = some rs → Reach cfg.heap rs l → cfg.heap l = some c → Within cfg.heap rs vs →
      Step cfg ⟨upd cfg.heap l (some { c with vs := vs }), cfg.next, cfg.workers, cfg.chans⟩
  /-- Allocate a cell (a buffer or a socket) owned by the worker. -/
  | alloc {cfg : Cfg} {w : Nat} {rs : List HV} {vs : List HV} {s : Bool} :
      cfg.workers w = some rs → Within cfg.heap rs vs →
      Step cfg ⟨upd cfg.heap cfg.next (some ⟨w, s, vs⟩), cfg.next + 1,
        upd cfg.workers w (some (.ptr cfg.next :: rs)), cfg.chans⟩
  /-- Send a copy of a value; `move` (a unique value) removes it from the sender. -/
  | send {cfg : Cfg} {w : Nat} {rs : List HV} {v : HV} {m : Msg} {ch : Nat} {i : Nat} (move : Bool) :
      cfg.workers w = some rs → rs[i]? = some v → Marshal cfg.heap v m →
      Step cfg ⟨cfg.heap, cfg.next, upd cfg.workers w (some (if move then rs.eraseIdx i else rs)),
        upd cfg.chans ch (cfg.chans ch ++ [m])⟩
  /-- Receive the next message into fresh cells of the receiver. -/
  | recv {cfg : Cfg} {w : Nat} {rs : List HV} {ch : Nat} {m : Msg} {rest : List Msg} {h' : Heap} {n' : Nat} {v : HV} :
      cfg.workers w = some rs → cfg.chans ch = m :: rest → Unm w cfg.heap cfg.next m h' n' v →
      Step cfg ⟨h', n', upd cfg.workers w (some (v :: rs)), upd cfg.chans ch rest⟩
  /-- Start a worker on a copy of a value. -/
  | spawn {cfg : Cfg} {w w' : Nat} {rs : List HV} {v : HV} {m : Msg} {h' : Heap} {n' : Nat} {v' : HV} :
      cfg.workers w = some rs → cfg.workers w' = none → v ∈ rs → Marshal cfg.heap v m →
      Unm w' cfg.heap cfg.next m h' n' v' →
      Step cfg ⟨h', n', upd cfg.workers w' (some [v']), cfg.chans⟩

/-- The invariant: locations from `next` on are free, and every cell a worker
reaches exists and is owned by that worker. -/
def Isolated (cfg : Cfg) : Prop :=
  (∀ l, cfg.next ≤ l → cfg.heap l = none) ∧
  (∀ w rs l, cfg.workers w = some rs → Reach cfg.heap rs l → ∃ c, cfg.heap l = some c ∧ c.owner = w)

/-! ## Reachability -/

theorem locsL_mem {l : Nat} : ∀ {vs : List HV}, l ∈ locsL vs ↔ ∃ v ∈ vs, l ∈ v.locs
  | [] => by simp [locsL]
  | v :: vs => by simp [locsL, locsL_mem]

theorem Reach.mono {h : Heap} {rs rs' : List HV} (hsub : ∀ v ∈ rs, v ∈ rs') {l : Nat} (hr : Reach h rs l) :
    Reach h rs' l := by
  induction hr with
  | root hv hl => exact .root (hsub _ hv) hl
  | step _ hc hv hl ih => exact .step ih hc hv hl

/-- Reaching from roots that are themselves within `rs` stays within `rs`. -/
theorem Reach.within {h : Heap} {rs rs' : List HV} (hw : Within h rs rs') {l : Nat} (hr : Reach h rs' l) :
    Reach h rs l := by
  induction hr with
  | root hv hl => exact hw _ hv _ hl
  | step _ hc hv hl ih => exact .step ih hc hv hl

/-- If the new heap agrees with the old one on every cell the roots reach in
the old heap, the roots reach the same cells. -/
theorem Reach.transfer {h h' : Heap} {rs : List HV}
    (hag : ∀ l, Reach h rs l → h' l = h l) {l : Nat} (hr : Reach h' rs l) : Reach h rs l := by
  induction hr with
  | root hv hl => exact .root hv hl
  | step hrl hc hv hl ih =>
    rename_i l0 c0 v0 l1
    have := hag l0 ih
    rw [this] at hc
    exact .step ih hc hv hl

/-! ## Unmarshalling allocates fresh cells of the receiver -/

/-- What `Unm` guarantees: it only grows `next`, keeps every old cell, fills
`[n, n')` with cells owned by `w` that point only into `[n, n')`, and the
value it builds points only into `[n, n')`. -/
def Fresh (w : Nat) (h : Heap) (n : Nat) (h' : Heap) (n' : Nat) : Prop :=
  n ≤ n' ∧ (∀ l, l < n → h' l = h l) ∧ (∀ l, n' ≤ l → h' l = h l) ∧
  (∀ l, n ≤ l → l < n' → ∃ c, h' l = some c ∧ c.owner = w ∧ ∀ v ∈ c.vs, ∀ l2 ∈ v.locs, n ≤ l2 ∧ l2 < n')

theorem Fresh.refl (w : Nat) (h : Heap) (n : Nat) : Fresh w h n h n :=
  ⟨Nat.le_refl _, fun _ _ => rfl, fun _ _ => rfl, fun l h1 h2 => absurd h2 (by omega)⟩

theorem Fresh.trans {w : Nat} {h h1 h2 : Heap} {n n1 n2 : Nat} (a : Fresh w h n h1 n1) (b : Fresh w h1 n1 h2 n2) :
    Fresh w h n h2 n2 := by
  obtain ⟨a1, a2, a3, a4⟩ := a
  obtain ⟨b1, b2, b3, b4⟩ := b
  refine ⟨Nat.le_trans a1 b1, fun l hl => ?_, fun l hl => ?_, fun l hl1 hl2 => ?_⟩
  · rw [b2 l (by omega), a2 l hl]
  · rw [b3 l hl, a3 l (by omega)]
  · by_cases hl : l < n1
    · obtain ⟨c, hc, ho, hp⟩ := a4 l hl1 hl
      refine ⟨c, by rw [b2 l hl, hc], ho, fun v hv l2 h2 => ?_⟩
      have := hp v hv l2 h2; omega
    · obtain ⟨c, hc, ho, hp⟩ := b4 l (by omega) hl2
      refine ⟨c, hc, ho, fun v hv l2 h2 => ?_⟩
      have := hp v hv l2 h2; omega

mutual
theorem unm_fresh {w : Nat} : ∀ {h : Heap} {n : Nat} {m : Msg} {h' : Heap} {n' : Nat} {v : HV},
    Unm w h n m h' n' v → Fresh w h n h' n' ∧ ∀ l ∈ v.locs, n ≤ l ∧ l < n'
  | _, _, _, _, _, _, .int => ⟨Fresh.refl _ _ _, by simp [HV.locs]⟩
  | h, n, _, _, _, _, .buf (h1 := h1) (n1 := n1) (vs := vs) hl => by
    obtain ⟨f1, hv1⟩ := unmL_fresh hl
    obtain ⟨a1, a2, a3, a4⟩ := f1
    refine ⟨⟨by omega, fun l hl' => ?_, fun l hl' => ?_, fun l hl1 hl2 => ?_⟩, ?_⟩
    · simp only [upd]; rw [if_neg (by omega)]; exact a2 l hl'
    · simp only [upd]; rw [if_neg (by omega)]; exact a3 l (by omega)
    · simp only [upd]
      by_cases he : l = n1
      · rw [if_pos he]
        refine ⟨_, rfl, rfl, fun v hv l2 h2 => ?_⟩
        have := hv1 l2 (locsL_mem.2 ⟨v, hv, h2⟩); omega
      · rw [if_neg he]
        obtain ⟨c, hc, ho, hp⟩ := a4 l hl1 (by omega)
        exact ⟨c, hc, ho, fun v hv l2 h2 => by have := hp v hv l2 h2; omega⟩
    · intro l hl'; simp [HV.locs] at hl'; omega
  | _, _, _, _, _, _, .tup hl => by
    obtain ⟨f1, hv1⟩ := unmL_fresh hl
    exact ⟨f1, fun l hl' => hv1 l (by simpa [HV.locs] using hl')⟩
theorem unmL_fresh {w : Nat} : ∀ {h : Heap} {n : Nat} {ms : List Msg} {h' : Heap} {n' : Nat} {vs : List HV},
    UnmL w h n ms h' n' vs → Fresh w h n h' n' ∧ ∀ l ∈ locsL vs, n ≤ l ∧ l < n'
  | _, _, _, _, _, _, .nil => ⟨Fresh.refl _ _ _, by simp [locsL]⟩
  | _, _, _, _, _, _, .cons hu hl => by
    obtain ⟨f1, hv1⟩ := unm_fresh hu
    obtain ⟨f2, hv2⟩ := unmL_fresh hl
    refine ⟨f1.trans f2, fun l hl' => ?_⟩
    simp only [locsL, List.mem_append] at hl'
    have e1 := f1.1; have e2 := f2.1
    rcases hl' with h | h
    · have := hv1 l h; omega
    · have := hv2 l h; omega
end

/-- What the fresh value reaches: only the fresh cells. -/
theorem reach_fresh {w : Nat} {h h' : Heap} {n n' : Nat} {v : HV} (f : Fresh w h n h' n')
    (hv : ∀ l ∈ v.locs, n ≤ l ∧ l < n') {l : Nat} (hr : Reach h' [v] l) : n ≤ l ∧ l < n' := by
  induction hr with
  | root hm hl => simp at hm; subst hm; exact hv _ hl
  | @step l0 c0 v0 l1 _ hc hm hl ih =>
    obtain ⟨c, hc', -, hp⟩ := f.2.2.2 l0 ih.1 ih.2
    rw [hc] at hc'; cases hc'
    exact hp v0 hm l1 hl

/-! ## Facts about the invariant -/

theorem reach_alloc {cfg : Cfg} (hi : Isolated cfg) {w : Nat} {rs : List HV} (hw : cfg.workers w = some rs)
    {l : Nat} (hr : Reach cfg.heap rs l) : l < cfg.next := by
  obtain ⟨c, hc, -⟩ := hi.2 w rs l hw hr
  exact Nat.lt_of_not_le fun hn => by rw [hi.1 l hn] at hc; cases hc

/-- Roots that reach only old cells reach the same cells after cells at or above `next` change. -/
theorem reach_old {cfg : Cfg} (hi : Isolated cfg) {w : Nat} {rs : List HV} (hw : cfg.workers w = some rs)
    {h' : Heap} (hag : ∀ l, l < cfg.next → h' l = cfg.heap l) {l : Nat} (hr : Reach h' rs l) : Reach cfg.heap rs l :=
  Reach.transfer (fun l' hr' => hag l' (reach_alloc hi hw hr')) hr

theorem upd_same {α : Type} (f : Nat → α) (k : Nat) (a : α) : upd f k a k = a := by simp [upd]
theorem upd_other {α : Type} (f : Nat → α) {k j : Nat} (a : α) (h : j ≠ k) : upd f k a j = f j := by simp [upd, h]

/-- Other workers keep what they own when cells below `next` do not change. -/
theorem other_owned {cfg : Cfg} (hi : Isolated cfg) {h' : Heap} (hag : ∀ l, l < cfg.next → h' l = cfg.heap l)
    {w2 : Nat} {rs2 : List HV} (hw2 : cfg.workers w2 = some rs2) {l : Nat} (hr : Reach h' rs2 l) :
    ∃ c, h' l = some c ∧ c.owner = w2 := by
  have hold := reach_old hi hw2 hag hr
  obtain ⟨c, hc, ho⟩ := hi.2 _ _ _ hw2 hold
  exact ⟨c, by rw [hag _ (reach_alloc hi hw2 hold)]; exact hc, ho⟩

/-! ## The theorem -/

theorem step_isolated {cfg cfg' : Cfg} (hi : Isolated cfg) (hs : Step cfg cfg') : Isolated cfg' := by
  have hi0 := hi
  obtain ⟨hfree, hown⟩ := hi
  cases hs with
  | @compute w rs rs' hw hwin =>
    refine ⟨hfree, fun w2 rs2 l hw2 hr => ?_⟩
    dsimp only at hw2 hr ⊢
    by_cases he : w2 = w
    · subst he; rw [upd_same] at hw2; cases hw2
      exact hown _ _ _ hw (Reach.within hwin hr)
    · rw [upd_other _ _ he] at hw2; exact hown _ _ _ hw2 hr
  | @write w rs l c vs hw hrl hc hwin =>
    obtain ⟨cw, hcw, hcwo⟩ := hown _ _ _ hw hrl
    rw [hc] at hcw; cases hcw
    refine ⟨fun l' hl' => ?_, fun w2 rs2 l' hw2 hr => ?_⟩
    · dsimp only at hl' ⊢
      by_cases he : l' = l
      · subst he; rw [hfree _ hl'] at hc; cases hc
      · rw [upd_other _ _ he]; exact hfree _ hl'
    · dsimp only at hw2 hr ⊢
      -- what w2 reaches in the new heap it reached in the old one
      have back : ∀ x, Reach (upd cfg.heap l (some { c with vs := vs })) rs2 x → Reach cfg.heap rs2 x := by
        intro x hx
        induction hx with
        | root hv hl => exact .root hv hl
        | @step l0 c0 v0 l1 _ hc2 hv hl ih =>
          by_cases he : l0 = l
          · subst he
            rw [upd_same] at hc2; cases hc2
            obtain ⟨c1, hc1, ho1⟩ := hown _ _ _ hw2 ih
            rw [hc] at hc1; cases hc1
            have hww : w2 = w := ho1.symm.trans hcwo
            subst hww
            rw [hw] at hw2; cases hw2
            exact hwin _ hv _ hl
          · rw [upd_other _ _ he] at hc2; exact .step ih hc2 hv hl
      obtain ⟨c2, hc2, ho2⟩ := hown _ _ _ hw2 (back _ hr)
      by_cases he : l' = l
      · subst he; rw [hc] at hc2; cases hc2; exact ⟨_, upd_same _ _ _, ho2⟩
      · exact ⟨c2, by rw [upd_other _ _ he]; exact hc2, ho2⟩
  | @alloc w rs vs s hw hwin =>
    have hag : ∀ l, l < cfg.next → upd cfg.heap cfg.next (some ⟨w, s, vs⟩) l = cfg.heap l :=
      fun l hl => upd_other _ _ (by omega)
    refine ⟨fun l hl => ?_, fun w2 rs2 l hw2 hr => ?_⟩
    · dsimp only at hl ⊢; rw [upd_other _ _ (by omega)]; exact hfree _ (by omega)
    · dsimp only at hw2 hr ⊢
      by_cases he : w2 = w
      · subst he; rw [upd_same] at hw2; cases hw2
        -- reached: the new cell, or something w reached before
        have key : ∀ l, Reach (upd cfg.heap cfg.next (some ⟨w2, s, vs⟩)) (.ptr cfg.next :: rs) l →
            l = cfg.next ∨ Reach cfg.heap rs l := by
          intro l hr
          induction hr with
          | @root v0 l0 hv hl =>
            simp only [List.mem_cons] at hv
            rcases hv with rfl | hv
            · simp [HV.locs] at hl; exact Or.inl hl
            · exact Or.inr (.root hv hl)
          | @step l0 c0 v0 l1 _ hc hv hl ih =>
            rcases ih with rfl | ih
            · rw [upd_same] at hc; cases hc; exact Or.inr (hwin _ hv _ hl)
            · rw [hag _ (reach_alloc hi0 hw ih)] at hc; exact Or.inr (.step ih hc hv hl)
        rcases key l hr with rfl | hold
        · exact ⟨_, upd_same _ _ _, rfl⟩
        · obtain ⟨c, hc, ho⟩ := hown _ _ _ hw hold
          exact ⟨c, by rw [hag _ (reach_alloc hi0 hw hold)]; exact hc, ho⟩
      · rw [upd_other _ _ he] at hw2
        exact other_owned hi0 hag hw2 hr
  | @send w rs v m ch i move hw hv hm =>
    refine ⟨hfree, fun w2 rs2 l hw2 hr => ?_⟩
    dsimp only at hw2 hr ⊢
    by_cases he : w2 = w
    · subst he; rw [upd_same] at hw2; cases hw2
      refine hown _ _ _ hw (Reach.mono (fun x hx => ?_) hr)
      split at hx
      · exact List.mem_of_mem_eraseIdx hx
      · exact hx
    · rw [upd_other _ _ he] at hw2; exact hown _ _ _ hw2 hr
  | @recv w rs ch m rest h' n' v hw hch hu =>
    obtain ⟨f, hvl⟩ := unm_fresh hu
    obtain ⟨f1, f2, f3, f4⟩ := f
    refine ⟨fun l hl => ?_, fun w2 rs2 l hw2 hr => ?_⟩
    · dsimp only at hl ⊢; rw [f3 l hl]; exact hfree _ (by omega)
    · dsimp only at hw2 hr ⊢
      by_cases he : w2 = w
      · subst he; rw [upd_same] at hw2; cases hw2
        -- reached from the new value: fresh cells of w2; from the old roots: old cells
        have key : ∀ l, Reach h' (v :: rs) l → (cfg.next ≤ l ∧ l < n') ∨ Reach cfg.heap rs l := by
          intro l hr
          induction hr with
          | @root v0 l0 hv hl =>
            simp only [List.mem_cons] at hv
            rcases hv with rfl | hv
            · exact Or.inl (hvl _ hl)
            · exact Or.inr (.root hv hl)
          | @step l0 c0 v0 l1 _ hc hv hl ih =>
            rcases ih with ⟨i1, i2⟩ | ih
            · obtain ⟨c, hc', -, hp⟩ := f4 l0 i1 i2
              rw [hc] at hc'; cases hc'
              exact Or.inl (hp v0 hv l1 hl)
            · rw [f2 _ (reach_alloc hi0 hw ih)] at hc; exact Or.inr (.step ih hc hv hl)
        rcases key l hr with ⟨i1, i2⟩ | hold
        · obtain ⟨c, hc, ho, -⟩ := f4 l i1 i2; exact ⟨c, hc, ho⟩
        · obtain ⟨c, hc, ho⟩ := hown _ _ _ hw hold
          exact ⟨c, by rw [f2 _ (reach_alloc hi0 hw hold)]; exact hc, ho⟩
      · rw [upd_other _ _ he] at hw2
        exact other_owned hi0 f2 hw2 hr
  | @spawn w w' rs v m h' n' v' hw hw' hv hm hu =>
    obtain ⟨f, hvl⟩ := unm_fresh hu
    refine ⟨fun l hl => ?_, fun w2 rs2 l hw2 hr => ?_⟩
    · dsimp only at hl ⊢; rw [f.2.2.1 l hl]; exact hfree _ (by have := f.1; omega)
    · dsimp only at hw2 hr ⊢
      by_cases he : w2 = w'
      · subst he; rw [upd_same] at hw2; cases hw2
        obtain ⟨i1, i2⟩ := reach_fresh f hvl hr
        obtain ⟨c, hc, ho, -⟩ := f.2.2.2 l i1 i2
        exact ⟨c, hc, ho⟩
      · rw [upd_other _ _ he] at hw2
        exact other_owned hi0 f.2.1 hw2 hr

/-- Runs: any number of steps. -/
inductive Steps : Cfg → Cfg → Prop
  | refl (cfg : Cfg) : Steps cfg cfg
  | tail {cfg cfg' cfg'' : Cfg} : Steps cfg cfg' → Step cfg' cfg'' → Steps cfg cfg''

/-- Isolation holds along any run. -/
theorem steps_isolated {cfg cfg' : Cfg} (hi : Isolated cfg) (hs : Steps cfg cfg') : Isolated cfg' := by
  induction hs with
  | refl => exact hi
  | tail _ hs ih => exact step_isolated ih hs

/-- **No shared mutable state.** In an isolated configuration (every reachable
one, from a start where it holds), no cell is reachable from two different
workers: two workers never touch the same buffer, string or socket. -/
theorem no_shared_cell {cfg : Cfg} (hi : Isolated cfg) {w1 w2 : Nat} {rs1 rs2 : List HV} {l : Nat}
    (h1 : cfg.workers w1 = some rs1) (h2 : cfg.workers w2 = some rs2)
    (r1 : Reach cfg.heap rs1 l) (r2 : Reach cfg.heap rs2 l) : w1 = w2 := by
  obtain ⟨c1, hc1, ho1⟩ := hi.2 _ _ _ h1 r1
  obtain ⟨c2, hc2, ho2⟩ := hi.2 _ _ _ h2 r2
  rw [hc1] at hc2; cases hc2
  exact ho1.symm.trans ho2

/-- In a heap of empty cells, roots reach exactly the cells they point to. -/
theorem reach_flat {h : Heap} (hf : ∀ l c, h l = some c → c.vs = []) {rs : List HV} {l : Nat}
    (hr : Reach h rs l) : ∃ v ∈ rs, l ∈ v.locs := by
  induction hr with
  | root hv hl => exact ⟨_, hv, hl⟩
  | @step l0 c0 v0 l1 _ hc hv _ _ => rw [hf _ _ hc] at hv; cases hv

/-- A program starts with one worker (`main`) that reaches nothing yet. -/
theorem start_isolated (rs : List HV) (hrs : ∀ v ∈ rs, v.locs = []) :
    Isolated ⟨fun _ => none, 0, fun w => if w = 0 then some rs else none, fun _ => []⟩ := by
  refine ⟨fun _ _ => rfl, fun w rs2 l hw hr => ?_⟩
  dsimp only at hw hr
  obtain ⟨v, hv, hl⟩ := reach_flat (fun _ _ h => by cases h) hr
  split at hw
  · cases hw; rw [hrs _ hv] at hl; cases hl
  · cases hw

/-- Every configuration a program reaches is isolated. -/
theorem run_isolated (rs : List HV) (hrs : ∀ v ∈ rs, v.locs = []) {cfg' : Cfg}
    (hs : Steps ⟨fun _ => none, 0, fun w => if w = 0 then some rs else none, fun _ => []⟩ cfg') :
    Isolated cfg' :=
  steps_isolated (start_isolated rs hrs) hs

/-- Without the `Send` rule (giving another worker a pointer instead of a copy) isolation breaks. -/
theorem unchecked_sharing_breaks_isolation :
    ∃ cfg : Cfg, Isolated cfg ∧
      ¬ Isolated ⟨cfg.heap, cfg.next, upd cfg.workers 1 (some [.ptr 0]), cfg.chans⟩ := by
  let h : Heap := fun l => if l = 0 then some ⟨0, true, []⟩ else none
  have hf : ∀ l c, h l = some c → c.vs = [] := by
    intro l c hc; simp only [h] at hc; split at hc <;> cases hc; rfl
  refine ⟨⟨h, 1, fun w => if w = 0 then some [.ptr 0] else if w = 1 then some [] else none, fun _ => []⟩,
          ⟨fun l hl => ?_, fun w rs l hw hr => ?_⟩, fun hi => ?_⟩
  · dsimp only at hl ⊢; simp only [h]; rw [if_neg (by omega)]
  · dsimp only at hw hr ⊢
    obtain ⟨v, hv, hl⟩ := reach_flat hf hr
    split at hw
    · rename_i hw0
      cases hw; simp at hv; subst hv; simp [HV.locs] at hl; subst hl
      exact ⟨_, rfl, hw0.symm⟩
    · split at hw
      · cases hw; simp at hv
      · cases hw
  · obtain ⟨_, h2⟩ := hi
    dsimp only at h2
    obtain ⟨c, hc, ho⟩ := h2 1 [.ptr 0] 0 (upd_same _ _ _) (.root (List.mem_singleton_self _) (by simp [HV.locs]))
    simp only [h] at hc
    simp at hc; subst hc; simp at ho

end Tenon.Workers

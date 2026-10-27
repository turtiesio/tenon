// C backend, part 4: matches and patterns, `?`, closures and function values.

use crate::ast::*;
use crate::check::Res;
use crate::emit_body::*;
use crate::emit_c::*;
use crate::types::Ty;
use std::fmt::Write;

impl<'a> Emitter<'a> {
    pub(crate) fn pat_test(&mut self, p: &Pattern, v: &str, t: &Ty) -> String {
        match &p.kind {
            PatKind::Wild | PatKind::Bind(_) => "1".into(),
            PatKind::Int(i) => format!("({} == {})", v, int_lit(*i)),
            PatKind::Bool(b) => if *b { format!("({})", v) } else { format!("(!{})", v) },
            PatKind::Str(s) => format!("tn_Str_eq({}, tn_str_lit({}, {}))", v, c_string(s), s.len()),
            PatKind::Tuple(ps) => {
                let Ty::Tuple(ts) = t else { unreachable!() };
                let parts: Vec<String> =
                    ps.iter().zip(ts.clone()).enumerate().map(|(i, (p, t))| self.pat_test(p, &format!("({}).f{}", v, i), &t)).collect();
                parts.join(" && ")
            }
            PatKind::Variant(_, _, ps) => {
                let Some(Res::Variant(_, vi, _)) = self.c.res.get(&p.id) else { unreachable!() };
                let vi = *vi;
                let fts = self.c.enum_variants(t).unwrap()[vi].1.clone();
                let mut parts = vec![format!("{} == {}", self.tag(t, v), vi)];
                for (j, (sp, ft)) in ps.iter().zip(fts).enumerate() {
                    let pv = self.payload(t, v, vi, j);
                    let s = self.pat_test(sp, &pv, &ft);
                    if s != "1" {
                        parts.push(s);
                    }
                }
                format!("({})", parts.join(" && "))
            }
            PatKind::Or(_) => unreachable!("or-patterns are expanded"),
        }
    }
    // Bind pattern variables (retained) from value `v`, which is known to match.
    // `borrow`: the matched value outlives these bindings and cannot change
    // meanwhile, so they need no reference of their own.
    pub(crate) fn bind(&mut self, p: &Pattern, v: &str, t: &Ty, borrow: bool) {
        match &p.kind {
            PatKind::Bind(n) => {
                let tn = self.cty(t);
                if borrow || self.trivial(t) {
                    self.line(&format!("{} v_{} = {};", tn, n, v));
                    return;
                }
                self.line(&format!("{} v_{} = {}_retain({});", tn, n, tn, v));
                self.reg_local(&format!("v_{}", n), t);
            }
            PatKind::Tuple(ps) => {
                let Ty::Tuple(ts) = t else { unreachable!() };
                for (i, (p, t)) in ps.iter().zip(ts.clone()).enumerate() {
                    self.bind(p, &format!("({}).f{}", v, i), &t, borrow);
                }
            }
            PatKind::Variant(_, _, ps) => {
                let Some(Res::Variant(_, vi, _)) = self.c.res.get(&p.id) else { unreachable!() };
                let vi = *vi;
                let fts = self.c.enum_variants(t).unwrap()[vi].1.clone();
                for (j, (sp, ft)) in ps.iter().zip(fts).enumerate() {
                    let pv = self.payload(t, v, vi, j);
                    self.bind(sp, &pv, &ft, borrow);
                }
            }
            _ => {}
        }
    }
    pub(crate) fn match_expr(&mut self, e: &Expr, s: &Expr, arms: &[Arm], t: &Ty) -> CV {
        let st = self.ety(s);
        let res = self.result_var(t);
        let cv = self.expr(s);
        let stable = cv.owned || (is_ident(&cv.code) && cv.code.starts_with("v_") && !self.st.muts.contains(&cv.code));
        let sv = if cv.owned || is_ident(&cv.code) { cv.code } else { self.tmp_val(&st, &cv.code).code };
        let done = self.fresh("done");
        for a in arms {
            for alt in expand_or(&a.pat) {
                let test = self.pat_test(&alt, &sv, &st);
                self.line(&format!("if ({}) {{", test));
                self.st.indent += 1;
                self.push(ScopeKind::Block);
                self.bind(&alt, &sv, &st, stable);
                if let Some(g) = &a.guard {
                    let gv = self.expr(g);
                    self.line(&format!("if ({}) {{", gv.code));
                    self.st.indent += 1;
                }
                self.push(ScopeKind::Stmt);
                let v = self.expr(&a.body);
                if let Some(r) = &res {
                    let code = self.own(v, t);
                    self.line(&format!("{} = {};", r, code));
                }
                self.pop();
                self.release_to(ScopeKind::Block);
                self.line(&format!("goto {};", done));
                if a.guard.is_some() {
                    self.st.indent -= 1;
                    self.line("}");
                }
                self.pop();
                self.st.indent -= 1;
                self.line("}");
            }
        }
        let loc = self.loc(e.span);
        self.line(&format!("tn_trap(\"no match arm (internal error)\", {});", loc));
        self.line(&format!("{}:;", done));
        self.finish_result(res, t)
    }
    pub(crate) fn try_expr(&mut self, e: &Expr, x: &Expr, t: &Ty) -> CV {
        let xt = self.ety(x);
        let cv = self.expr(x);
        let v = if cv.owned || cv.code.starts_with("v_") { cv.code } else { self.tmp_val(&xt, &cv.code).code };
        let rt = self.st.ret.clone().unwrap();
        let tag = self.tag(&xt, &v);
        self.line(&format!("if ({} != 0) {{", tag));
        self.st.indent += 1;
        let ret = if xt.is("Option") {
            self.ctor_named(&rt, "None", &[])
        } else {
            let et = xt.args()[1].clone();
            let p = self.payload(&xt, &v, 1, 0);
            let code = self.own(bor(p), &et);
            self.ctor_named(&rt, "Err", &[code])
        };
        let rn = self.cty(&rt);
        let r = self.fresh("r");
        self.line(&format!("{} {} = {};", rn, r, ret));
        self.release_to(ScopeKind::Fn);
        self.line(&format!("return {};", r));
        self.st.indent -= 1;
        self.line("}");
        let _ = e;
        let p = self.payload(&xt, &v, 0, 0);
        let _ = t;
        bor(p)
    }
    pub(crate) fn lambda(&mut self, e: &Expr, params: &[(String, Option<TypeExpr>)], body: &Expr, t: &Ty) -> CV {
        let Ty::Fn(pts, rt) = t else { unreachable!() };
        let caps: Vec<(String, Ty)> = self.c.captures[&e.id].iter().map(|(n, ct)| (n.clone(), self.sub(ct))).collect();
        let name = self.fresh("lam");
        let rn = self.cty(rt);
        // environment
        let mut env = format!("struct {}_env {{ tn_env h;", name);
        let mut drop = format!("static void {}_drop(tn_env *e) {{ struct {}_env *E = (void *)e; ", name, name);
        for (n, ct) in &caps {
            let tn = self.cty(ct);
            let _ = write!(env, " {} c_{};", tn, n);
            let _ = write!(drop, "{}_release(E->c_{}); ", tn, n);
        }
        env.push_str(" };\n");
        drop.push_str("tn_free(E); }\n");
        self.helpers.push_str(&env);
        self.helpers.push_str(&drop);
        let mut ps = vec!["tn_env *env_".to_string()];
        for ((pn, _), pt) in params.iter().zip(pts) {
            let tn = self.cty(pt);
            ps.push(format!("{} v_{}", tn, pn));
        }
        let sig = format!("static {} {}({})", rn, name, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        // body, in a fresh function context
        let tsub = self.st.tsub.clone();
        let saved = std::mem::replace(
            &mut self.st,
            FnState { tsub, ret: Some((**rt).clone()), self_ptr: false, indent: 1, ..Default::default() },
        );
        self.push(ScopeKind::Fn);
        self.line(&format!("struct {}_env *E = (void *)env_; (void)E;", name));
        for (n, ct) in &caps {
            let tn = self.cty(ct);
            self.line(&format!("{} v_{} = E->c_{};", tn, n, n));
        }
        let r = self.fresh("ret");
        self.line(&format!("{} {};", rn, r));
        self.push(ScopeKind::Stmt);
        let v = self.expr(body);
        let code = self.own(v, rt);
        self.line(&format!("{} = {};", r, code));
        self.pop();
        self.release_to(ScopeKind::Fn);
        self.line(&format!("return {};", r));
        let out = std::mem::replace(&mut self.st, saved).out;
        let _ = write!(self.bodies, "{} {{\n{}}}\n", sig, out);
        // creation
        if caps.is_empty() {
            return bor(format!("((tn_fn){{ (void *){}, NULL }})", name));
        }
        let env_v = self.fresh("env");
        self.line(&format!("struct {n}_env *{env_v} = tn_alloc(sizeof *{env_v}); {env_v}->h.rc = 1; {env_v}->h.drop = {n}_drop;", n = name));
        for (n, ct) in &caps {
            let code = self.own(bor(self.local_code(n)), ct);
            self.line(&format!("{}->c_{} = {};", env_v, n, code));
        }
        self.tmp_owned(t, &format!("((tn_fn){{ (void *){}, &{}->h }})", name, env_v))
    }
    pub(crate) fn fn_wrapper(&mut self, fi: usize, targs: Vec<Ty>) -> String {
        let key = format!("fn{}:{:?}", fi, targs);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let (ptys, rt) = self.sig(fi, &targs);
        let w = self.fresh("fnv");
        self.wrappers.insert(key, w.clone());
        let rn = self.cty(&rt);
        let mut ps = vec!["tn_env *e".to_string()];
        for (i, p) in ptys.iter().enumerate() {
            let tn = self.cty(p);
            ps.push(format!("{} a{}", tn, i));
        }
        let sig = format!("static {} {}({})", rn, w, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        let args: Vec<CV> = (0..ptys.len()).map(|i| bor(format!("a{}", i))).collect();
        if self.c.fns[fi].is_extern {
            let saved = std::mem::replace(&mut self.st, FnState { ret: Some(rt.clone()), indent: 1, ..Default::default() });
            self.push(ScopeKind::Fn);
            let name = self.c.fns[fi].name.clone();
            let v = self.extern_call(&name, args, &ptys, &rt, crate::diag::Span::default());
            let code = self.own(v, &rt);
            let r = self.fresh("r");
            self.line(&format!("{} {} = {};", rn, r, code));
            self.release_to(ScopeKind::Fn);
            self.line(&format!("return {};", r));
            let out = std::mem::replace(&mut self.st, saved).out;
            let _ = write!(self.bodies, "{} {{ (void)e;\n{}}}\n", sig, out);
        } else {
            let f = self.fn_inst(fi, targs);
            let a: Vec<String> = (0..ptys.len()).map(|i| format!("a{}", i)).collect();
            let _ = writeln!(self.bodies, "{} {{ (void)e; return {}({}); }}", sig, f, a.join(", "));
        }
        w
    }
    pub(crate) fn ctor_wrapper(&mut self, et: &Ty, vi: usize, ptys: &[Ty]) -> String {
        let key = format!("ctor{:?}:{}", et, vi);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let w = self.fresh("fnv");
        self.wrappers.insert(key, w.clone());
        let en = self.cty(et);
        let mut ps = vec!["tn_env *e".to_string()];
        let mut args = Vec::new();
        for (i, p) in ptys.iter().enumerate() {
            let tn = self.cty(p);
            ps.push(format!("{} a{}", tn, i));
            args.push(format!("{}_retain(a{})", tn, i));
        }
        let sig = format!("static {} {}({})", en, w, ps.join(", "));
        let _ = writeln!(self.protos, "{};", sig);
        let code = self.ctor(et, vi, &args);
        let _ = writeln!(self.bodies, "{} {{ (void)e; return {}; }}", sig, code);
        w
    }
}

// Expand or-patterns (also nested ones) into separate alternatives.
fn expand_or(p: &Pattern) -> Vec<Pattern> {
    let mk = |kind: PatKind| Pattern { id: p.id, span: p.span, kind };
    match &p.kind {
        PatKind::Or(alts) => alts.iter().flat_map(expand_or).collect(),
        PatKind::Tuple(ps) => product(ps).into_iter().map(|v| mk(PatKind::Tuple(v))).collect(),
        PatKind::Variant(q, n, ps) => product(ps).into_iter().map(|v| mk(PatKind::Variant(q.clone(), n.clone(), v))).collect(),
        _ => vec![p.clone()],
    }
}

fn product(ps: &[Pattern]) -> Vec<Vec<Pattern>> {
    let mut acc: Vec<Vec<Pattern>> = vec![vec![]];
    for p in ps {
        let alts = expand_or(p);
        let mut next = Vec::new();
        for a in &acc {
            for alt in &alts {
                let mut v = a.clone();
                v.push(alt.clone());
                next.push(v);
            }
        }
        acc = next;
    }
    acc
}

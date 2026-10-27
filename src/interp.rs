// Reference interpreter: the executable specification that the C backend is
// differentially tested against. Clarity over speed.

use crate::ast::*;
use crate::check::{Checked, Res};
use crate::diag::{SourceMap, Span};
use crate::value::*;
use std::collections::HashMap;
use std::io::{BufRead, Read, Write};
use std::rc::Rc;

pub const EXIT_ERR: i32 = 1;
pub const EXIT_TRAP: i32 = 70;
pub const EXIT_STACK: i32 = 72;
pub const EXIT_OUTPUT: i32 = 74;
const MAX_DEPTH: usize = 20_000;

pub enum Ctrl {
    Ret(V),
    Break,
    Continue,
    Trap(String, Span),
    Exit(i32),
}

type R = Result<V, Ctrl>;

fn trap<T>(msg: impl Into<String>, sp: Span) -> Result<T, Ctrl> {
    Err(Ctrl::Trap(msg.into(), sp))
}

enum Step {
    Field(usize),
    Index(V),
}

pub struct Interp<'a> {
    c: &'a Checked,
    lambdas: HashMap<Id, &'a Expr>,
    env: Vec<(String, V)>,
    depth: usize,
    out: std::io::BufWriter<std::io::Stdout>,
    snames: Vec<(String, Vec<Option<String>>)>,
    enames: Vec<(String, Vec<String>)>,
    mono_origin: std::time::Instant,
    args: Vec<String>,
}

fn collect_lambdas<'a>(e: &'a Expr, m: &mut HashMap<Id, &'a Expr>) {
    if let ExprKind::Lambda(..) = e.kind {
        m.insert(e.id, e);
    }
    visit_children(e, &mut |x| collect_lambdas(x, m));
}

pub fn visit_children<'a>(e: &'a Expr, f: &mut dyn FnMut(&'a Expr)) {
    let blk = |b: &'a Block, f: &mut dyn FnMut(&'a Expr)| {
        for s in &b.stmts {
            visit_stmt(s, f);
        }
    };
    match &e.kind {
        ExprKind::Str(segs) => {
            for s in segs {
                if let StrSeg::Expr(x) = s {
                    f(x)
                }
            }
        }
        ExprKind::Field(b, _) | ExprKind::TupleField(b, _) | ExprKind::Unary(_, b) | ExprKind::Try(b) => f(b),
        ExprKind::Index(a, b) | ExprKind::Binary(_, a, b) => {
            f(a);
            f(b)
        }
        ExprKind::Call(c, args) | ExprKind::Method(c, _, args) => {
            f(c);
            args.iter().for_each(|a| f(a))
        }
        ExprKind::If(c, t, e2) => {
            f(c);
            blk(t, f);
            if let Some(x) = e2 {
                f(x)
            }
        }
        ExprKind::Match(s, arms) => {
            f(s);
            for a in arms {
                if let Some(g) = &a.guard {
                    f(g)
                }
                f(&a.body)
            }
        }
        ExprKind::Block(b) => blk(b, f),
        ExprKind::List(xs) | ExprKind::Tuple(xs) => xs.iter().for_each(|a| f(a)),
        ExprKind::MapLit(ps) => ps.iter().for_each(|(k, v)| {
            f(k);
            f(v)
        }),
        ExprKind::StructLit(_, fs, b) => {
            fs.iter().for_each(|(_, v)| f(v));
            if let Some(b) = b {
                f(b)
            }
        }
        ExprKind::Lambda(_, _, b) => f(b),
        _ => {}
    }
}

pub fn visit_children_mut(e: &mut Expr, f: &mut dyn FnMut(&mut Expr)) {
    let blk = |b: &mut Block, f: &mut dyn FnMut(&mut Expr)| {
        for s in &mut b.stmts {
            visit_stmt_mut(s, f);
        }
    };
    match &mut e.kind {
        ExprKind::Str(segs) => {
            for s in segs {
                if let StrSeg::Expr(x) = s {
                    f(x)
                }
            }
        }
        ExprKind::Field(b, _) | ExprKind::TupleField(b, _) | ExprKind::Unary(_, b) | ExprKind::Try(b) => f(b),
        ExprKind::Index(a, b) | ExprKind::Binary(_, a, b) => {
            f(a);
            f(b)
        }
        ExprKind::Call(c, args) | ExprKind::Method(c, _, args) => {
            f(c);
            args.iter_mut().for_each(|a| f(a))
        }
        ExprKind::If(c, t, e2) => {
            f(c);
            blk(t, f);
            if let Some(x) = e2 {
                f(x)
            }
        }
        ExprKind::Match(s, arms) => {
            f(s);
            for a in arms {
                if let Some(g) = &mut a.guard {
                    f(g)
                }
                f(&mut a.body)
            }
        }
        ExprKind::Block(b) => blk(b, f),
        ExprKind::List(xs) | ExprKind::Tuple(xs) => xs.iter_mut().for_each(|a| f(a)),
        ExprKind::MapLit(ps) => ps.iter_mut().for_each(|(k, v)| {
            f(k);
            f(v)
        }),
        ExprKind::StructLit(_, fs, b) => {
            fs.iter_mut().for_each(|(_, v)| f(v));
            if let Some(b) = b {
                f(b)
            }
        }
        ExprKind::Lambda(_, _, b) => f(b),
        _ => {}
    }
}

pub fn visit_stmt_mut(s: &mut Stmt, f: &mut dyn FnMut(&mut Expr)) {
    let blk = |b: &mut Block, f: &mut dyn FnMut(&mut Expr)| {
        for s in &mut b.stmts {
            visit_stmt_mut(s, f);
        }
    };
    match &mut s.kind {
        StmtKind::Let { value, .. } => f(value),
        StmtKind::Expr(e) => f(e),
        StmtKind::Assign { target, value, .. } => {
            f(target);
            f(value)
        }
        StmtKind::While { cond, body } => {
            f(cond);
            blk(body, f)
        }
        StmtKind::For { iter, body, .. } => {
            match iter {
                ForIter::Range(a, b) => {
                    f(a);
                    f(b)
                }
                ForIter::Each(e) => f(e),
            }
            blk(body, f)
        }
        StmtKind::Return(Some(e)) => f(e),
        _ => {}
    }
}

pub fn visit_stmt<'a>(s: &'a Stmt, f: &mut dyn FnMut(&'a Expr)) {
    let blk = |b: &'a Block, f: &mut dyn FnMut(&'a Expr)| {
        for s in &b.stmts {
            visit_stmt(s, f);
        }
    };
    match &s.kind {
        StmtKind::Let { value, .. } => f(value),
        StmtKind::Expr(e) => f(e),
        StmtKind::Assign { target, value, .. } => {
            f(target);
            f(value)
        }
        StmtKind::While { cond, body } => {
            f(cond);
            blk(body, f)
        }
        StmtKind::For { iter, body, .. } => {
            match iter {
                ForIter::Range(a, b) => {
                    f(a);
                    f(b)
                }
                ForIter::Each(e) => f(e),
            }
            blk(body, f)
        }
        StmtKind::Return(Some(e)) => f(e),
        _ => {}
    }
}

// Fields shown by derived formatting: a module's private fields are hidden
// (shown as `..`) so formatting cannot leak them.
pub fn shown_fields(s: &crate::check::StructInfo) -> Vec<Option<String>> {
    let mut v: Vec<Option<String>> = Vec::new();
    for (i, (f, _)) in s.fields.iter().enumerate() {
        if s.file > 1 && !s.pub_fields[i] {
            v.push(None);
            break;
        }
        v.push(Some(f.clone()));
    }
    v
}

// Type names as users write them (without the module prefix).
pub fn display(n: &str) -> &str {
    n.rsplit('.').next().unwrap()
}

pub fn run(c: &Checked, sm: &SourceMap, args: Vec<String>) -> i32 {
    let mut lambdas = HashMap::new();
    for f in &c.prog.fns {
        if let Some(b) = &f.body {
            for s in &b.stmts {
                visit_stmt(s, &mut |e| collect_lambdas(e, &mut lambdas));
            }
        }
    }
    let mut it = Interp {
        c,
        lambdas,
        env: vec![],
        depth: 0,
        out: std::io::BufWriter::with_capacity(1 << 16, std::io::stdout()),
        snames: c.structs.iter().map(|s| (display(&s.name).to_string(), shown_fields(s))).collect(),
        enames: c.enums.iter().map(|e| (display(&e.name).to_string(), e.variants.iter().map(|v| v.0.clone()).collect())).collect(),
        mono_origin: std::time::Instant::now(),
        args,
    };
    let main = &c.fns[c.main];
    let margs = if main.params.is_empty() { vec![] } else { vec![it.sys()] };
    let r = it.call_fn(c.main, margs, Span::default());
    let code = match r {
        Ok(v) => match v {
            V::Enum(_, 1, payload) => {
                let msg = it.show_top(&payload[0]);
                let _ = it.out.flush();
                eprintln!("error: {}", msg);
                EXIT_ERR
            }
            _ => 0,
        },
        Err(Ctrl::Trap(msg, sp)) => {
            let _ = it.out.flush();
            eprintln!("trap: {}\n  at {}", msg, sm.loc(sp));
            EXIT_TRAP
        }
        Err(Ctrl::Exit(code)) => code,
        Err(_) => 0,
    };
    if it.out.flush().is_err() && code == 0 {
        return EXIT_OUTPUT;
    }
    code
}

impl<'a> Interp<'a> {
    fn names(&self) -> Names<'_> {
        Names { structs: &self.snames, enums: &self.enames }
    }
    fn show_top(&self, v: &V) -> String {
        let mut s = String::new();
        show(v, true, &self.names(), &mut s);
        s
    }
    fn show_nested(&self, v: &V) -> String {
        let mut s = String::new();
        show(v, false, &self.names(), &mut s);
        s
    }

    fn sys(&self) -> V {
        let si = self.c.struct_idx("Sys").unwrap() as u32;
        let args = V::List(Rc::new(self.args.iter().map(|a| V::Str(a.as_str().into())).collect()));
        V::Struct(si, Rc::new(vec![
            V::Cap(Rc::new(Cap::Console)),
            V::Cap(Rc::new(Cap::Fs { root: String::new(), attenuated: false, writable: true })),
            V::Cap(Rc::new(Cap::Clock)),
            args,
        ]))
    }

    fn variant(&self, en: &str, vn: &str, payload: Vec<V>) -> V {
        let ei = self.c.enum_idx(en).unwrap();
        let vi = self.c.enums[ei].variants.iter().position(|v| v.0 == vn).unwrap();
        V::Enum(ei as u32, vi as u32, Rc::new(payload))
    }
    fn some(&self, v: V) -> V {
        self.variant("Option", "Some", vec![v])
    }
    fn none(&self) -> V {
        self.variant("Option", "None", vec![])
    }
    fn opt(&self, v: Option<V>) -> V {
        match v {
            Some(v) => self.some(v),
            None => self.none(),
        }
    }

    fn lookup(&self, n: &str) -> V {
        for (m, v) in self.env.iter().rev() {
            if m == n {
                return v.clone();
            }
        }
        panic!("interp: unbound local {}", n)
    }

    fn local_mut(&mut self, n: &str) -> &mut V {
        for (m, v) in self.env.iter_mut().rev() {
            if m == n {
                return v;
            }
        }
        panic!("interp: unbound local {}", n)
    }

    // ---- calls ----

    pub fn call_fn(&mut self, fi: usize, args: Vec<V>, sp: Span) -> R {
        let info = &self.c.fns[fi];
        if info.is_extern {
            return self.call_extern(&info.name, args, sp);
        }
        if self.depth >= MAX_DEPTH {
            let _ = self.out.flush();
            eprintln!("trap: stack overflow");
            return Err(Ctrl::Exit(EXIT_STACK));
        }
        let decl = &self.c.prog.fns[fi];
        let mut env: Vec<(String, V)> = info.params.iter().map(|(n, _)| n.clone()).zip(args).collect();
        std::mem::swap(&mut self.env, &mut env);
        self.depth += 1;
        let r = self.block(decl.body.as_ref().unwrap());
        self.depth -= 1;
        std::mem::swap(&mut self.env, &mut env);
        match r {
            Ok(v) | Err(Ctrl::Ret(v)) => Ok(v),
            Err(e) => Err(e),
        }
    }

    // A user method with `mut self`: run it on the value and hand back the new self.
    fn call_fn_mut(&mut self, fi: usize, recv: V, args: Vec<V>, sp: Span) -> Result<(V, V), Ctrl> {
        if self.depth >= MAX_DEPTH {
            let _ = self.out.flush();
            eprintln!("trap: stack overflow");
            return Err(Ctrl::Exit(EXIT_STACK));
        }
        let _ = sp;
        let info = &self.c.fns[fi];
        let decl = &self.c.prog.fns[fi];
        let mut env: Vec<(String, V)> = vec![("self".to_string(), recv)];
        env.extend(info.params[1..].iter().map(|(n, _)| n.clone()).zip(args));
        std::mem::swap(&mut self.env, &mut env);
        self.depth += 1;
        let r = self.block(decl.body.as_ref().unwrap());
        self.depth -= 1;
        let new_self = self.env[0].1.clone();
        std::mem::swap(&mut self.env, &mut env);
        match r {
            Ok(v) | Err(Ctrl::Ret(v)) => Ok((new_self, v)),
            Err(e) => Err(e),
        }
    }

    fn apply(&mut self, f: &V, args: Vec<V>, sp: Span) -> R {
        let V::Fn(cl) = f else { panic!("interp: calling a non-function") };
        match &**cl {
            Closure::Named(fi) => self.call_fn(*fi, args, sp),
            Closure::Variant(ei, vi) => Ok(V::Enum(*ei, *vi, Rc::new(args))),
            Closure::Lambda(id, caps) => {
                let lam = self.lambdas[id];
                let ExprKind::Lambda(params, _, body) = &lam.kind else { unreachable!() };
                if self.depth >= MAX_DEPTH {
                    let _ = self.out.flush();
                    eprintln!("trap: stack overflow");
                    return Err(Ctrl::Exit(EXIT_STACK));
                }
                let mut env = caps.clone();
                env.extend(params.iter().map(|(n, _)| n.clone()).zip(args));
                std::mem::swap(&mut self.env, &mut env);
                self.depth += 1;
                let r = self.eval(body);
                self.depth -= 1;
                std::mem::swap(&mut self.env, &mut env);
                match r {
                    Ok(v) | Err(Ctrl::Ret(v)) => Ok(v),
                    Err(e) => Err(e),
                }
            }
        }
    }

    // ---- statements ----

    fn block(&mut self, b: &Block) -> R {
        let mark = self.env.len();
        let mut last = V::Unit;
        let mut r = Ok(());
        for s in &b.stmts {
            match self.stmt(s) {
                Ok(v) => last = v,
                Err(e) => {
                    r = Err(e);
                    break;
                }
            }
        }
        self.env.truncate(mark);
        r.map(|_| last)
    }

    fn stmt(&mut self, s: &Stmt) -> R {
        match &s.kind {
            StmtKind::Expr(e) => self.eval(e),
            StmtKind::Let { pat, value, .. } => {
                let v = self.eval(value)?;
                self.bind_irrefutable(pat, v);
                Ok(V::Unit)
            }
            StmtKind::Assign { target, op, value } => {
                let (root, steps) = self.place_path(target)?;
                let v = self.eval(value)?;
                let nv = match op {
                    None => v,
                    Some(op) => {
                        let cur = navigate(self.local_mut(&root), &steps, false, target.span)?.clone();
                        self.binop(*op, cur, v, s.span)?
                    }
                };
                let slot = navigate(self.local_mut(&root), &steps, op.is_none(), target.span)?;
                *slot = nv;
                Ok(V::Unit)
            }
            StmtKind::While { cond, body } => {
                loop {
                    match self.eval(cond)? {
                        V::Bool(true) => {}
                        _ => break,
                    }
                    match self.block(body) {
                        Ok(_) | Err(Ctrl::Continue) => {}
                        Err(Ctrl::Break) => break,
                        Err(e) => return Err(e),
                    }
                }
                Ok(V::Unit)
            }
            StmtKind::For { pat, iter, body } => {
                let items: Box<dyn Iterator<Item = V>> = match iter {
                    ForIter::Range(a, b) => {
                        let (V::Int(a), V::Int(b)) = (self.eval(a)?, self.eval(b)?) else { unreachable!() };
                        Box::new((a..b).map(V::Int))
                    }
                    ForIter::Each(e) => match self.eval(e)? {
                        V::List(xs) => Box::new((0..xs.len()).map(move |i| xs[i].clone())),
                        V::Map(m) => {
                            let items: Vec<V> =
                                m.iter().map(|(k, v)| V::Tuple(Rc::new(vec![k.clone(), v.clone()]))).collect();
                            Box::new(items.into_iter())
                        }
                        _ => unreachable!(),
                    },
                };
                for v in items {
                    let mark = self.env.len();
                    self.bind_irrefutable(pat, v);
                    let r = self.block(body);
                    self.env.truncate(mark);
                    match r {
                        Ok(_) | Err(Ctrl::Continue) => {}
                        Err(Ctrl::Break) => break,
                        Err(e) => return Err(e),
                    }
                }
                Ok(V::Unit)
            }
            StmtKind::Return(v) => {
                let v = match v {
                    Some(e) => self.eval(e)?,
                    None => V::Unit,
                };
                Err(Ctrl::Ret(v))
            }
            StmtKind::Break => Err(Ctrl::Break),
            StmtKind::Continue => Err(Ctrl::Continue),
        }
    }

    fn bind_irrefutable(&mut self, p: &Pattern, v: V) {
        let mut binds = Vec::new();
        let ok = self.matches(p, &v, &mut binds);
        debug_assert!(ok);
        self.env.extend(binds);
    }

    fn matches(&self, p: &Pattern, v: &V, binds: &mut Vec<(String, V)>) -> bool {
        match (&p.kind, v) {
            (PatKind::Wild, _) => true,
            (PatKind::Bind(n), _) => {
                binds.push((n.clone(), v.clone()));
                true
            }
            (PatKind::Int(i), V::Int(j)) => i == j,
            (PatKind::Str(s), V::Str(t)) => **s == **t,
            (PatKind::Bool(b), V::Bool(c)) => b == c,
            (PatKind::Tuple(ps), V::Tuple(vs)) => ps.iter().zip(vs.iter()).all(|(p, v)| self.matches(p, v, binds)),
            (PatKind::Variant(_, _, ps), V::Enum(_, vi, vs)) => {
                let Some(Res::Variant(_, want, _)) = self.c.res.get(&p.id) else { unreachable!() };
                *want as u32 == *vi && ps.iter().zip(vs.iter()).all(|(p, v)| self.matches(p, v, binds))
            }
            (PatKind::Or(alts), _) => {
                for a in alts {
                    let mark = binds.len();
                    if self.matches(a, v, binds) {
                        return true;
                    }
                    binds.truncate(mark);
                }
                false
            }
            _ => false,
        }
    }

    // ---- places ----

    fn place_path(&mut self, e: &Expr) -> Result<(String, Vec<Step>), Ctrl> {
        match &e.kind {
            ExprKind::Name(n) => Ok((n.clone(), vec![])),
            ExprKind::Field(b, _) => {
                let (r, mut s) = self.place_path(b)?;
                let Some(Res::Field(i)) = self.c.res.get(&e.id) else { unreachable!() };
                s.push(Step::Field(*i));
                Ok((r, s))
            }
            ExprKind::TupleField(b, i) => {
                let (r, mut s) = self.place_path(b)?;
                s.push(Step::Field(*i));
                Ok((r, s))
            }
            ExprKind::Index(b, i) => {
                let (r, mut s) = self.place_path(b)?;
                let iv = self.eval(i)?;
                s.push(Step::Index(iv));
                Ok((r, s))
            }
            _ => unreachable!("checker guarantees places"),
        }
    }

    // ---- expressions ----

    fn eval(&mut self, e: &Expr) -> R {
        match &e.kind {
            ExprKind::Int(i) => Ok(V::Int(*i)),
            ExprKind::Float(f) => Ok(V::Float(*f)),
            ExprKind::Bool(b) => Ok(V::Bool(*b)),
            ExprKind::Unit => Ok(V::Unit),
            ExprKind::Str(segs) => {
                let mut s = String::new();
                for seg in segs {
                    match seg {
                        StrSeg::Lit(l) => s.push_str(l),
                        StrSeg::Expr(x) => {
                            let v = self.eval(x)?;
                            show(&v, true, &self.names(), &mut s);
                        }
                    }
                }
                Ok(V::Str(s.into()))
            }
            ExprKind::Name(_) | ExprKind::Path(..) => match &self.c.res[&e.id] {
                Res::Local(n) => Ok(self.lookup(n)),
                Res::Fn(fi, _) => Ok(V::Fn(Rc::new(Closure::Named(*fi)))),
                Res::Variant(ei, vi, _) => {
                    let n = self.c.enums[*ei].variants[*vi].1.len();
                    if n == 0 {
                        Ok(V::Enum(*ei as u32, *vi as u32, Rc::new(vec![])))
                    } else {
                        Ok(V::Fn(Rc::new(Closure::Variant(*ei as u32, *vi as u32))))
                    }
                }
                _ => unreachable!(),
            },
            ExprKind::Call(callee, args) => {
                if let Some(Res::CallValue) = self.c.res.get(&e.id) {
                    let f = self.eval(callee)?;
                    let av = self.eval_args(args)?;
                    return self.apply(&f, av, e.span);
                }
                match self.c.res.get(&callee.id).cloned() {
                    Some(Res::Fn(fi, _)) => {
                        let av = self.eval_args(args)?;
                        self.call_fn(fi, av, e.span)
                    }
                    Some(Res::Variant(ei, vi, _)) => {
                        let av = self.eval_args(args)?;
                        Ok(V::Enum(ei as u32, vi as u32, Rc::new(av)))
                    }
                    _ => {
                        let f = self.eval(callee)?;
                        let av = self.eval_args(args)?;
                        self.apply(&f, av, e.span)
                    }
                }
            }
            ExprKind::Method(recv, _, args) => match self.c.res[&e.id].clone() {
                Res::ToStr => {
                    let v = self.eval(recv)?;
                    Ok(V::Str(self.show_top(&v).into()))
                }
                Res::Method(fi, _) => {
                    let info = &self.c.fns[fi];
                    if info.self_kind == Some(SelfKind::Mut) {
                        let (root, steps) = self.place_path(recv)?;
                        let av = self.eval_args(args)?;
                        let name = info.name.clone();
                        let is_extern = info.is_extern;
                        let slot = navigate(self.local_mut(&root), &steps, false, recv.span)?;
                        if is_extern {
                            return self.extern_mut(&name, &root, &steps, av, e.span);
                        }
                        let recv_v = std::mem::replace(slot, V::Unit);
                        let (new_self, r) = self.call_fn_mut(fi, recv_v, av, e.span)?;
                        *navigate(self.local_mut(&root), &steps, false, recv.span)? = new_self;
                        Ok(r)
                    } else {
                        let rv = self.eval(recv)?;
                        let mut av = vec![rv];
                        av.extend(self.eval_args(args)?);
                        self.call_fn(fi, av, e.span)
                    }
                }
                _ => unreachable!(),
            },
            ExprKind::Field(b, _) => {
                let v = self.eval(b)?;
                let Some(Res::Field(i)) = self.c.res.get(&e.id) else { unreachable!() };
                match v {
                    V::Struct(_, fs) => Ok(fs[*i].clone()),
                    _ => unreachable!(),
                }
            }
            ExprKind::TupleField(b, i) => match self.eval(b)? {
                V::Tuple(fs) => Ok(fs[*i].clone()),
                _ => unreachable!(),
            },
            ExprKind::Index(b, i) => {
                let bv = self.eval(b)?;
                let iv = self.eval(i)?;
                index(&bv, &iv, e.span, &self.names()).cloned()
            }
            ExprKind::Unary(op, x) => {
                let v = self.eval(x)?;
                match (op, v) {
                    (UnOp::Not, V::Bool(b)) => Ok(V::Bool(!b)),
                    (UnOp::Neg, V::Int(i)) => match i.checked_neg() {
                        Some(n) => Ok(V::Int(n)),
                        None => trap("integer overflow", e.span),
                    },
                    (UnOp::Neg, V::Float(f)) => Ok(V::Float(-f)),
                    _ => unreachable!(),
                }
            }
            ExprKind::Binary(op, l, r) => {
                if *op == BinOp::And || *op == BinOp::Or {
                    let V::Bool(a) = self.eval(l)? else { unreachable!() };
                    if (*op == BinOp::And) != a {
                        return Ok(V::Bool(a));
                    }
                    return self.eval(r);
                }
                let a = self.eval(l)?;
                let b = self.eval(r)?;
                self.binop(*op, a, b, e.span)
            }
            ExprKind::If(c, t, els) => {
                let V::Bool(b) = self.eval(c)? else { unreachable!() };
                if b {
                    self.block(t)
                } else if let Some(x) = els {
                    self.eval(x)
                } else {
                    Ok(V::Unit)
                }
            }
            ExprKind::Block(b) => self.block(b),
            ExprKind::Match(s, arms) => {
                let v = self.eval(s)?;
                for a in arms {
                    let mut binds = Vec::new();
                    if !self.matches(&a.pat, &v, &mut binds) {
                        continue;
                    }
                    let mark = self.env.len();
                    self.env.extend(binds);
                    if let Some(g) = &a.guard {
                        match self.eval(g) {
                            Ok(V::Bool(true)) => {}
                            Ok(_) => {
                                self.env.truncate(mark);
                                continue;
                            }
                            Err(x) => {
                                self.env.truncate(mark);
                                return Err(x);
                            }
                        }
                    }
                    let r = self.eval(&a.body);
                    self.env.truncate(mark);
                    return r;
                }
                unreachable!("checker guarantees exhaustive matches")
            }
            ExprKind::List(xs) => Ok(V::List(Rc::new(self.eval_args(xs)?))),
            ExprKind::Tuple(xs) => Ok(V::Tuple(Rc::new(self.eval_args(xs)?))),
            ExprKind::MapLit(ps) => {
                let mut m = MapV::default();
                for (k, v) in ps {
                    let k = self.eval(k)?;
                    let v = self.eval(v)?;
                    m.insert(k, v);
                }
                Ok(V::Map(Rc::new(m)))
            }
            ExprKind::StructLit(_, fields, base) => {
                let Some(Res::Struct(si)) = self.c.res.get(&e.id).cloned() else { unreachable!() };
                let decl = &self.c.structs[si];
                let mut given: Vec<(usize, V)> = Vec::new();
                for (f, x) in fields {
                    let i = decl.fields.iter().position(|(n, _)| n == f).unwrap();
                    given.push((i, self.eval(x)?));
                }
                let mut vals: Vec<V> = match base {
                    Some(b) => match self.eval(b)? {
                        V::Struct(_, fs) => (*fs).clone(),
                        _ => unreachable!(),
                    },
                    None => vec![V::Unit; decl.fields.len()],
                };
                for (i, v) in given {
                    vals[i] = v;
                }
                Ok(V::Struct(si as u32, Rc::new(vals)))
            }
            ExprKind::Try(x) => match self.eval(x)? {
                V::Enum(ei, vi, p) => {
                    let en = &self.c.enums[ei as usize].name;
                    let is_ok = vi == 0;
                    if is_ok {
                        Ok(p[0].clone())
                    } else if en == "Option" {
                        Err(Ctrl::Ret(V::Enum(ei, vi, p)))
                    } else {
                        Err(Ctrl::Ret(V::Enum(ei, vi, p)))
                    }
                }
                _ => unreachable!(),
            },
            ExprKind::Lambda(..) => {
                let caps = &self.c.captures[&e.id];
                let vals = caps.iter().map(|(n, _)| (n.clone(), self.lookup(n))).collect();
                Ok(V::Fn(Rc::new(Closure::Lambda(e.id, vals))))
            }
        }
    }

    fn eval_args(&mut self, args: &[Expr]) -> Result<Vec<V>, Ctrl> {
        let mut v = Vec::with_capacity(args.len());
        for a in args {
            v.push(self.eval(a)?);
        }
        Ok(v)
    }

    fn binop(&mut self, op: BinOp, a: V, b: V, sp: Span) -> R {
        use BinOp::*;
        let ovf = || Ctrl::Trap("integer overflow".into(), sp);
        Ok(match (op, &a, &b) {
            (Eq, _, _) => V::Bool(a == b),
            (Ne, _, _) => V::Bool(a != b),
            (Lt | Le | Gt | Ge, _, _) => {
                let c = match cmp(&a, &b) {
                    Ok(c) => c,
                    Err(m) => return trap(m, sp),
                };
                // IEEE: comparisons involving NaN are false.
                if let (V::Float(x), V::Float(y)) = (&a, &b) {
                    return Ok(V::Bool(match op {
                        Lt => x < y,
                        Le => x <= y,
                        Gt => x > y,
                        _ => x >= y,
                    }));
                }
                V::Bool(match op {
                    Lt => c < 0,
                    Le => c <= 0,
                    Gt => c > 0,
                    _ => c >= 0,
                })
            }
            (Add, V::Int(x), V::Int(y)) => V::Int(x.checked_add(*y).ok_or_else(ovf)?),
            (Sub, V::Int(x), V::Int(y)) => V::Int(x.checked_sub(*y).ok_or_else(ovf)?),
            (Mul, V::Int(x), V::Int(y)) => V::Int(x.checked_mul(*y).ok_or_else(ovf)?),
            (Div | Rem, V::Int(_), V::Int(0)) => return trap("division by zero", sp),
            (Div, V::Int(x), V::Int(y)) => V::Int(x.checked_div(*y).ok_or_else(ovf)?),
            (Rem, V::Int(x), V::Int(y)) => V::Int(x.checked_rem(*y).ok_or_else(ovf)?),
            (Add, V::Float(x), V::Float(y)) => V::Float(x + y),
            (Sub, V::Float(x), V::Float(y)) => V::Float(x - y),
            (Mul, V::Float(x), V::Float(y)) => V::Float(x * y),
            (Div, V::Float(x), V::Float(y)) => V::Float(x / y),
            (Rem, V::Float(x), V::Float(y)) => V::Float(x % y),
            (Add, V::Str(x), V::Str(y)) => {
                let mut s = String::with_capacity(x.len() + y.len());
                s.push_str(x);
                s.push_str(y);
                V::Str(s.into())
            }
            (Add, V::List(x), V::List(y)) => {
                let mut v = (**x).clone();
                v.extend(y.iter().cloned());
                V::List(Rc::new(v))
            }
            _ => unreachable!("binop {:?}", op),
        })
    }

    // ---- builtins (signatures live in prelude.tn) ----

    fn extern_mut(&mut self, name: &str, root: &str, steps: &[Step], args: Vec<V>, sp: Span) -> R {
        // Evaluate anything that needs &self before borrowing the slot.
        let keys: Option<Vec<V>> = if name == "List.sort_by" {
            let xs = match navigate(self.local_mut(root), steps, false, sp)? {
                V::List(xs) => xs.clone(),
                _ => unreachable!(),
            };
            let mut ks = Vec::with_capacity(xs.len());
            for x in xs.iter() {
                ks.push(self.apply(&args[0], vec![x.clone()], sp)?);
            }
            Some(ks)
        } else {
            None
        };
        let none = self.none();
        let some_ctor = |v: V, s: &Self| s.some(v);
        let slot = navigate(self.local_mut(root), steps, false, sp)?;
        let mut args = args.into_iter();
        match (name, slot) {
            ("List.push", V::List(xs)) => {
                Rc::make_mut(xs).push(args.next().unwrap());
                Ok(V::Unit)
            }
            ("List.pop", V::List(xs)) => {
                let v = Rc::make_mut(xs).pop();
                Ok(match v {
                    Some(v) => some_ctor(v, self),
                    None => none,
                })
            }
            ("List.insert", V::List(xs)) => {
                let V::Int(i) = args.next().unwrap() else { unreachable!() };
                if i < 0 || i as usize > xs.len() {
                    return trap(format!("index {} out of bounds for length {}", i, xs.len()), sp);
                }
                Rc::make_mut(xs).insert(i as usize, args.next().unwrap());
                Ok(V::Unit)
            }
            ("List.remove", V::List(xs)) => {
                let V::Int(i) = args.next().unwrap() else { unreachable!() };
                if i < 0 || i as usize >= xs.len() {
                    return trap(format!("index {} out of bounds for length {}", i, xs.len()), sp);
                }
                Ok(Rc::make_mut(xs).remove(i as usize))
            }
            ("List.clear", V::List(xs)) => {
                Rc::make_mut(xs).clear();
                Ok(V::Unit)
            }
            ("List.reverse", V::List(xs)) => {
                Rc::make_mut(xs).reverse();
                Ok(V::Unit)
            }
            ("List.sort", V::List(xs)) => {
                let mut bad = None;
                Rc::make_mut(xs).sort_by(|a, b| match cmp(a, b) {
                    Ok(c) => c.cmp(&0),
                    Err(m) => {
                        bad = Some(m);
                        std::cmp::Ordering::Equal
                    }
                });
                match bad {
                    Some(m) => trap(m, sp),
                    None => Ok(V::Unit),
                }
            }
            ("List.sort_by", V::List(xs)) => {
                let keys = keys.unwrap();
                let mut idx: Vec<usize> = (0..xs.len()).collect();
                let mut bad = None;
                idx.sort_by(|a, b| match cmp(&keys[*a], &keys[*b]) {
                    Ok(c) => c.cmp(&0),
                    Err(m) => {
                        bad = Some(m);
                        std::cmp::Ordering::Equal
                    }
                });
                if let Some(m) = bad {
                    return trap(m, sp);
                }
                let sorted: Vec<V> = idx.iter().map(|i| xs[*i].clone()).collect();
                *xs = Rc::new(sorted);
                Ok(V::Unit)
            }
            ("Map.insert", V::Map(m)) => {
                let k = args.next().unwrap();
                let v = args.next().unwrap();
                Rc::make_mut(m).insert(k, v);
                Ok(V::Unit)
            }
            ("Map.remove", V::Map(m)) => {
                let k = args.next().unwrap();
                let r = Rc::make_mut(m).remove(&k);
                Ok(match r {
                    Some(v) => some_ctor(v, self),
                    None => none,
                })
            }
            (n, _) => panic!("interp: missing mutating builtin {}", n),
        }
    }

    fn io_err(&self, kind: &str, msg: String) -> V {
        let e = self.variant("IoError", kind, vec![V::Str(msg.into())]);
        self.variant("Result", "Err", vec![e])
    }
    fn ok(&self, v: V) -> V {
        self.variant("Result", "Ok", vec![v])
    }
    fn io_result<T>(&self, path: &str, r: std::io::Result<T>, f: impl FnOnce(T) -> V) -> V {
        match r {
            Ok(x) => self.ok(f(x)),
            Err(e) => match e.kind() {
                std::io::ErrorKind::NotFound => self.io_err("NotFound", path.to_string()),
                std::io::ErrorKind::PermissionDenied => self.io_err("Denied", path.to_string()),
                _ => self.io_err("Failed", format!("{}: {}", path, os_msg(&e))),
            },
        }
    }

    fn write_out(&mut self, s: &str) -> Result<(), Ctrl> {
        if self.out.write_all(s.as_bytes()).is_err() {
            return Err(Ctrl::Exit(EXIT_OUTPUT));
        }
        Ok(())
    }

    fn call_extern(&mut self, name: &str, args: Vec<V>, sp: Span) -> R {
        use V::*;
        let a = &args;
        let s = |i: usize| -> &str {
            match &a[i] {
                Str(s) => s,
                _ => unreachable!(),
            }
        };
        let int = |i: usize| -> i64 {
            match &a[i] {
                Int(x) => *x,
                _ => unreachable!(),
            }
        };
        let flt = |i: usize| -> f64 {
            match &a[i] {
                Float(x) => *x,
                _ => unreachable!(),
            }
        };
        let strv = |x: &str| V::Str(x.into());
        let list = |v: Vec<V>| V::List(Rc::new(v));
        Ok(match name {
            "panic" => return trap(s(0), sp),
            "assert" => {
                if let Bool(false) = a[0] {
                    return trap("assertion failed", sp);
                }
                Unit
            }
            "Int.to_float" => Float(int(0) as f64),
            "Int.char" => match u32::try_from(int(0)).ok().and_then(char::from_u32) {
                Some(c) => strv(&c.to_string()),
                None => return trap(format!("invalid character code {}", int(0)), sp),
            },
            "Float.to_int" => {
                let x = flt(0);
                if !(x >= -9223372036854775808.0 && x < 9223372036854775808.0) {
                    return trap("float to int conversion out of range", sp);
                }
                Int(x as i64)
            }
            "Float.sqrt" => Float(flt(0).sqrt()),
            "Float.floor" => Float(flt(0).floor()),
            "Float.ceil" => Float(flt(0).ceil()),
            "Float.round" => Float(flt(0).round()),
            "Str.len" => Int(s(0).len() as i64),
            "Str.byte" => {
                let (st, i) = (s(0), int(1));
                if i < 0 || i as usize >= st.len() {
                    return trap(format!("index {} out of bounds for length {}", i, st.len()), sp);
                }
                Int(st.as_bytes()[i as usize] as i64)
            }
            "Str.slice" => {
                let (st, x, y) = (s(0), int(1), int(2));
                if x < 0 || y < x || y as usize > st.len() {
                    return trap(format!("slice [{}, {}) out of bounds for length {}", x, y, st.len()), sp);
                }
                if !st.is_char_boundary(x as usize) || !st.is_char_boundary(y as usize) {
                    return trap(format!("slice [{}, {}) is not on a character boundary", x, y), sp);
                }
                strv(&st[x as usize..y as usize])
            }
            "Str.find" => self.opt(s(0).find(s(1)).map(|i| Int(i as i64))),
            "Str.split" => {
                if s(1).is_empty() {
                    return trap("split with an empty separator", sp);
                }
                list(s(0).split(s(1)).map(strv).collect())
            }
            "Str.words" => list(s(0).split([' ', '\t', '\n', '\r']).filter(|w| !w.is_empty()).map(strv).collect()),
            "Str.lines" => {
                let mut parts: Vec<V> = s(0).split('\n').map(strv).collect();
                if let Some(V::Str(l)) = parts.last() {
                    if l.is_empty() {
                        parts.pop();
                    }
                }
                list(parts)
            }
            "Str.trim" => strv(s(0).trim_matches(|c: char| c.is_ascii_whitespace())),
            "Str.trim_start" => strv(s(0).trim_start_matches(|c: char| c.is_ascii_whitespace())),
            "Str.trim_end" => strv(s(0).trim_end_matches(|c: char| c.is_ascii_whitespace())),
            "Str.starts_with" => Bool(s(0).starts_with(s(1))),
            "Str.ends_with" => Bool(s(0).ends_with(s(1))),
            "Str.to_int" => self.opt(parse_int(s(0)).map(Int)),
            "Str.to_float" => self.opt(parse_float(s(0)).map(Float)),
            "Str.upper" => strv(&s(0).to_ascii_uppercase()),
            "Str.lower" => strv(&s(0).to_ascii_lowercase()),
            "Str.replace" => {
                if s(1).is_empty() {
                    return trap("replace with an empty pattern", sp);
                }
                strv(&s(0).replace(s(1), s(2)))
            }
            "Str.chars" => list(s(0).chars().map(|c| strv(&c.to_string())).collect()),
            "List.len" => match &a[0] {
                List(xs) => Int(xs.len() as i64),
                _ => unreachable!(),
            },
            "List.slice" => match &a[0] {
                List(xs) => {
                    let (x, y) = (int(1), int(2));
                    if x < 0 || y < x || y as usize > xs.len() {
                        return trap(format!("slice [{}, {}) out of bounds for length {}", x, y, xs.len()), sp);
                    }
                    list(xs[x as usize..y as usize].to_vec())
                }
                _ => unreachable!(),
            },
            "List.join" => match &a[0] {
                List(xs) => {
                    let parts: Vec<&str> = xs.iter().map(|x| if let Str(s) = x { &**s } else { "" }).collect();
                    strv(&parts.join(s(1)))
                }
                _ => unreachable!(),
            },
            "Map.len" => match &a[0] {
                Map(m) => Int(m.len() as i64),
                _ => unreachable!(),
            },
            "Map.get" => match &a[0] {
                Map(m) => self.opt(m.get(&a[1]).cloned()),
                _ => unreachable!(),
            },
            "Map.keys" => match &a[0] {
                Map(m) => list(m.iter().map(|(k, _)| k.clone()).collect()),
                _ => unreachable!(),
            },
            "Map.values" => match &a[0] {
                Map(m) => list(m.iter().map(|(_, v)| v.clone()).collect()),
                _ => unreachable!(),
            },
            "Option.unwrap" | "Option.expect" => match &a[0] {
                Enum(_, 0, p) => p[0].clone(),
                _ if name == "Option.expect" => return trap(s(1), sp),
                _ => return trap("unwrap on None", sp),
            },
            "Result.unwrap" | "Result.expect" => match &a[0] {
                Enum(_, 0, p) => p[0].clone(),
                Enum(_, _, p) if name == "Result.expect" => {
                    return trap(format!("{}: {}", s(1), self.show_nested(&p[0])), sp);
                }
                v => return trap(format!("unwrap on {}", self.show_nested(v)), sp),
            },
            "Console.print" | "Console.println" => {
                self.write_out(s(1))?;
                if name == "Console.println" {
                    self.write_out("\n")?;
                }
                Unit
            }
            "Console.eprintln" => {
                let _ = self.out.flush();
                eprintln!("{}", s(1));
                Unit
            }
            "Console.read_line" => {
                let _ = self.out.flush();
                let mut line = Vec::new();
                match std::io::stdin().lock().read_until(b'\n', &mut line) {
                    Ok(0) | Err(_) => self.none(),
                    Ok(_) => {
                        if line.ends_with(b"\n") {
                            line.pop();
                            if line.ends_with(b"\r") {
                                line.pop();
                            }
                        }
                        self.some(strv(&String::from_utf8_lossy(&line)))
                    }
                }
            }
            "Console.read_all" => {
                let mut buf = Vec::new();
                let _ = std::io::stdin().lock().read_to_end(&mut buf);
                strv(&String::from_utf8_lossy(&buf))
            }
            n if n.starts_with("Fs.") => return self.fs_op(n, &args, sp),
            "Clock.now_ms" => Int(std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis() as i64)
                .unwrap_or(0)),
            "Clock.mono_ns" => Int(self.mono_origin.elapsed().as_nanos() as i64),
            "Clock.sleep_ms" => {
                if int(1) > 0 {
                    std::thread::sleep(std::time::Duration::from_millis(int(1) as u64));
                }
                Unit
            }
            _ => panic!("interp: missing builtin {}", name),
        })
    }

    fn fs_op(&mut self, name: &str, a: &[V], _sp: Span) -> R {
        let V::Cap(cap) = &a[0] else { unreachable!() };
        let Cap::Fs { root, attenuated, writable } = &**cap else { unreachable!() };
        let arg = |i: usize| -> String {
            match &a[i] {
                V::Str(s) => s.to_string(),
                _ => unreachable!(),
            }
        };
        if name == "Fs.read_only" {
            return Ok(V::Cap(Rc::new(Cap::Fs { root: root.clone(), attenuated: *attenuated, writable: false })));
        }
        let p = arg(1);
        let full = match fs_path(root, *attenuated, &p) {
            Some(f) => f,
            None => {
                return Ok(match name {
                    "Fs.exists" => V::Bool(false),
                    "Fs.within" => V::Cap(Rc::new(Cap::Fs { root: "/nonexistent-denied".into(), attenuated: true, writable: false })),
                    _ => self.io_err("Denied", format!("path escapes the Fs root: {}", p)),
                });
            }
        };
        let writes = matches!(name, "Fs.write" | "Fs.append" | "Fs.remove" | "Fs.mkdir");
        if writes && !writable {
            return Ok(self.io_err("Denied", format!("read-only Fs: {}", p)));
        }
        Ok(match name {
            "Fs.read" => {
                let r = std::fs::read(&full).and_then(|b| {
                    String::from_utf8(b).map_err(|_| std::io::Error::other("invalid UTF-8"))
                });
                self.io_result(&p, r, |s| V::Str(s.into()))
            }
            "Fs.write" => {
                let data = arg(2);
                let tmp = format!("{}.tmp", full);
                let r = (|| {
                    let mut f = std::fs::File::create(&tmp)?;
                    f.write_all(data.as_bytes())?;
                    f.sync_all()?;
                    std::fs::rename(&tmp, &full)
                })();
                if r.is_err() {
                    let _ = std::fs::remove_file(&tmp);
                }
                self.io_result(&p, r, |_| V::Unit)
            }
            "Fs.append" => {
                let data = arg(2);
                let r = (|| {
                    let mut f = std::fs::OpenOptions::new().append(true).create(true).open(&full)?;
                    f.write_all(data.as_bytes())?;
                    f.sync_all()
                })();
                self.io_result(&p, r, |_| V::Unit)
            }
            "Fs.exists" => V::Bool(std::path::Path::new(&full).exists()),
            "Fs.remove" => {
                let r = if std::path::Path::new(&full).is_dir() { std::fs::remove_dir(&full) } else { std::fs::remove_file(&full) };
                self.io_result(&p, r, |_| V::Unit)
            }
            "Fs.mkdir" => self.io_result(&p, std::fs::create_dir_all(&full), |_| V::Unit),
            "Fs.list" => {
                let r = std::fs::read_dir(&full).and_then(|rd| {
                    let mut names = Vec::new();
                    for e in rd {
                        names.push(e?.file_name().to_string_lossy().to_string());
                    }
                    names.sort();
                    Ok(names)
                });
                self.io_result(&p, r, |ns| V::List(Rc::new(ns.into_iter().map(|n| V::Str(n.into())).collect())))
            }
            "Fs.within" => V::Cap(Rc::new(Cap::Fs { root: full, attenuated: true, writable: *writable })),
            _ => panic!("interp: missing builtin {}", name),
        })
    }
}

// Path resolution under an Fs capability; None = escapes the root.
pub fn fs_path(root: &str, attenuated: bool, p: &str) -> Option<String> {
    if attenuated && (p.is_empty() || p.starts_with('/') || p.split('/').any(|c| c == "..")) {
        return None;
    }
    if root.is_empty() {
        Some(if p.is_empty() { ".".to_string() } else { p.to_string() })
    } else if p.is_empty() || p == "." {
        Some(root.to_string())
    } else {
        Some(format!("{}/{}", root, p))
    }
}

fn os_msg(e: &std::io::Error) -> String {
    let s = e.to_string();
    match s.find(" (os error") {
        Some(i) => s[..i].to_string(),
        None => s,
    }
}

fn navigate<'v>(mut v: &'v mut V, steps: &[Step], create: bool, sp: Span) -> Result<&'v mut V, Ctrl> {
    for (i, st) in steps.iter().enumerate() {
        let last = i + 1 == steps.len();
        v = match (st, v) {
            (Step::Field(f), V::Struct(_, fs)) | (Step::Field(f), V::Tuple(fs)) => &mut Rc::make_mut(fs)[*f],
            (Step::Index(V::Int(i)), V::List(xs)) => {
                let n = xs.len();
                if *i < 0 || *i as usize >= n {
                    return trap(format!("index {} out of bounds for length {}", i, n), sp);
                }
                &mut Rc::make_mut(xs)[*i as usize]
            }
            (Step::Index(k), V::Map(m)) => {
                let m = Rc::make_mut(m);
                if create && last && m.get(k).is_none() {
                    m.insert(k.clone(), V::Unit);
                }
                match m.index.get(k) {
                    Some(&j) => &mut m.entries[j].as_mut().unwrap().1,
                    None => return trap(format!("key not found: {}", show_plain(k)), sp),
                }
            }
            _ => unreachable!(),
        };
    }
    Ok(v)
}

// Formatting without type names (keys in messages are scalars in practice).
fn show_plain(v: &V) -> String {
    let mut s = String::new();
    show(v, false, &Names { structs: &[], enums: &[] }, &mut s);
    s
}

fn index<'v>(b: &'v V, i: &V, sp: Span, n: &Names) -> Result<&'v V, Ctrl> {
    match (b, i) {
        (V::List(xs), V::Int(i)) => {
            if *i < 0 || *i as usize >= xs.len() {
                return trap(format!("index {} out of bounds for length {}", i, xs.len()), sp);
            }
            Ok(&xs[*i as usize])
        }
        (V::Map(m), k) => match m.get(k) {
            Some(v) => Ok(v),
            None => {
                let mut s = String::new();
                show(k, false, n, &mut s);
                trap(format!("key not found: {}", s), sp)
            }
        },
        _ => unreachable!(),
    }
}

// Strict number syntax shared with the C runtime: [+-]?digits
pub fn parse_int(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    let digits = if !b.is_empty() && (b[0] == b'+' || b[0] == b'-') { &b[1..] } else { b };
    if digits.is_empty() || !digits.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    s.parse().ok()
}

// [+-]? (digits [. digits*] | . digits) ([eE] [+-]? digits)?  |  [+-]? (inf|infinity|nan)
pub fn parse_float(s: &str) -> Option<f64> {
    let b = s.as_bytes();
    let mut i = 0;
    if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
        i += 1;
    }
    let rest = s[i..].to_ascii_lowercase();
    if rest == "inf" || rest == "infinity" || rest == "nan" {
        return s.parse().ok();
    }
    let int_start = i;
    while i < b.len() && b[i].is_ascii_digit() {
        i += 1;
    }
    let mut nd = i - int_start;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        let fs = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        nd += i - fs;
    }
    if nd == 0 {
        return None;
    }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        let es = i;
        while i < b.len() && b[i].is_ascii_digit() {
            i += 1;
        }
        if i == es {
            return None;
        }
    }
    if i != b.len() {
        return None;
    }
    s.parse().ok()
}

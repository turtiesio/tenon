// Reference interpreter: the executable specification that the C backend is
// differentially tested against. Clarity over speed.

use crate::ast::*;
use crate::check::{Checked, Res};
use crate::diag::{SourceMap, Span};
use crate::value::*;
use std::collections::HashMap;
use std::io::Write;
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

pub(crate) type R = Result<V, Ctrl>;

pub(crate) fn trap<T>(msg: impl Into<String>, sp: Span) -> Result<T, Ctrl> {
    Err(Ctrl::Trap(msg.into(), sp))
}

pub(crate) enum Step {
    Field(usize),
    Index(V),
}

pub struct Interp<'a> {
    pub(crate) c: &'a Checked,
    pub(crate) lambdas: HashMap<Id, &'a Expr>,
    pub(crate) env: Vec<(String, V)>,
    pub(crate) depth: usize,
    pub(crate) out: std::io::BufWriter<std::io::Stdout>,
    pub(crate) snames: Vec<(String, Vec<Option<String>>)>,
    pub(crate) snames_full: Vec<(String, Vec<Option<String>>)>, // for `encode`: every field
    pub(crate) enames: Vec<(String, Vec<String>)>,
    pub(crate) mono_origin: std::time::Instant,
    pub(crate) args: Vec<String>,
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

// `main` returning Int: 0-255, except the codes reserved for traps.
pub fn exit_status(code: i64) -> Result<i32, String> {
    if !(0..=255).contains(&code) || [EXIT_TRAP, 71, EXIT_STACK, EXIT_OUTPUT].contains(&(code as i32)) {
        return Err(format!("exit status {} is out of range or reserved", code));
    }
    Ok(code as i32)
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
        snames_full: c.structs.iter().map(|s| (display(&s.name).to_string(), s.fields.iter().map(|f| Some(f.0.clone())).collect())).collect(),
        enames: c.enums.iter().map(|e| (display(&e.name).to_string(), e.variants.iter().map(|v| v.0.clone()).collect())).collect(),
        mono_origin: std::time::Instant::now(),
        args,
    };
    let main = &c.fns[c.main];
    let margs = if main.params.is_empty() { vec![] } else { vec![it.sys()] };
    let r = it.call_fn(c.main, margs, Span::default());
    let code = match r {
        Ok(v) => match v {
            V::Int(code) => match exit_status(code) {
                Ok(c) => c,
                Err(m) => {
                    let _ = it.out.flush();
                    eprintln!("trap: {}\n  at {}", m, sm.loc(c.prog.fns[c.main].span));
                    EXIT_TRAP
                }
            },
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
    pub(crate) fn names_full(&self) -> Names<'_> {
        Names { structs: &self.snames_full, enums: &self.enames }
    }
    fn show_top(&self, v: &V) -> String {
        let mut s = String::new();
        show(v, true, &self.names(), &mut s);
        s
    }
    pub(crate) fn show_nested(&self, v: &V) -> String {
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
            V::Cap(Rc::new(Cap::Net)),
            args,
        ]))
    }

    pub(crate) fn variant(&self, en: &str, vn: &str, payload: Vec<V>) -> V {
        let ei = self.c.enum_idx(en).unwrap();
        let vi = self.c.enums[ei].variants.iter().position(|v| v.0 == vn).unwrap();
        V::Enum(ei as u32, vi as u32, Rc::new(payload))
    }
    pub(crate) fn some(&self, v: V) -> V {
        self.variant("Option", "Some", vec![v])
    }
    pub(crate) fn none(&self) -> V {
        self.variant("Option", "None", vec![])
    }
    pub(crate) fn opt(&self, v: Option<V>) -> V {
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

    pub(crate) fn local_mut(&mut self, n: &str) -> &mut V {
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

    pub(crate) fn apply(&mut self, f: &V, args: Vec<V>, sp: Span) -> R {
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
                    Some(Res::Fn(fi, targs)) if self.c.fns[fi].name == "decode" => {
                        let av = self.eval_args(args)?;
                        let V::Str(text) = &av[0] else { unreachable!() };
                        let r = crate::codec::decode(self.c, &self.names_full(), &targs[0], text);
                        Ok(match r {
                            Ok(v) => self.ok(v),
                            Err(m) => self.variant("Result", "Err", vec![V::Str(m.into())]),
                        })
                    }
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






}



pub(crate) fn navigate<'v>(mut v: &'v mut V, steps: &[Step], create: bool, sp: Span) -> Result<&'v mut V, Ctrl> {
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



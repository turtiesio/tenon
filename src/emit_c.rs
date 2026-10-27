// C backend, part 1: driver, type layout and per-type helpers.
// Function bodies are lowered in emit_body.rs.
//
// Ownership protocol: every expression yields a CV that is either *owned*
// (a temp registered in the innermost scope, released at statement or
// scope end unless moved) or *borrowed* (valid until the statement ends).
// Parameters are borrowed; results are owned; storing anything retains it.

use crate::check::Checked;
use crate::diag::{SourceMap, Span};
use crate::types::Ty;
use std::collections::{HashMap, HashSet};
use std::fmt::Write;

pub const RUNTIME: &str = include_str!("../runtime/tenon.h");

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ScopeKind {
    Fn,
    Block,
    Stmt,
    LoopBody,
}

pub struct Scope {
    pub kind: ScopeKind,
    pub owned: Vec<(String, Ty)>,
}

#[derive(Default)]
pub struct FnState {
    pub out: String,
    pub scopes: Vec<Scope>,
    pub tsub: HashMap<String, Ty>,
    pub ret: Option<Ty>,
    pub self_ptr: bool,
    pub indent: usize,
    pub muts: HashSet<String>, // `var` locals: values bound from them must be retained
}

pub struct Emitter<'a> {
    pub c: &'a Checked,
    pub sm: &'a SourceMap,
    pub tnames: HashMap<Ty, String>,
    pub tlist: Vec<Ty>,
    boxed: HashMap<Ty, bool>,
    pub fn_names: HashMap<(usize, Vec<Ty>), String>,
    pub fn_queue: Vec<(usize, Vec<Ty>, String)>,
    pub wrappers: HashMap<String, String>,
    pub protos: String,
    pub bodies: String,
    pub helpers: String,
    pub counter: usize,
    pub st: FnState,
}

pub fn build(c: &Checked, sm: &SourceMap, out: &str, opt: &str) -> Result<(), String> {
    let code = emit(c, sm);
    let cpath = format!("{}.c", out);
    std::fs::write(&cpath, code).map_err(|e| format!("cannot write {}: {}", cpath, e))?;
    let cc = std::env::var("CC").unwrap_or_else(|_| "cc".to_string());
    let st = std::process::Command::new(&cc)
        .args([opt, "-w", "-std=gnu11", "-o", out, &cpath, "-lm"])
        .status()
        .map_err(|e| format!("cannot run {}: {}", cc, e))?;
    if !st.success() {
        return Err(format!("C compiler failed on {}", cpath));
    }
    if std::env::var("TENON_KEEP_C").is_err() {
        let _ = std::fs::remove_file(&cpath);
    }
    Ok(())
}

pub fn emit(c: &Checked, sm: &SourceMap) -> String {
    let mut e = Emitter {
        c,
        sm,
        tnames: HashMap::new(),
        tlist: Vec::new(),
        boxed: HashMap::new(),
        fn_names: HashMap::new(),
        fn_queue: Vec::new(),
        wrappers: HashMap::new(),
        protos: String::new(),
        bodies: String::new(),
        helpers: String::new(),
        counter: 0,
        st: FnState::default(),
    };
    let main_name = e.fn_inst(c.main, vec![]);
    while let Some((fi, targs, name)) = e.fn_queue.pop() {
        e.emit_fn(fi, &targs, &name);
    }
    let main_c = e.main_wrapper(&main_name);
    e.assemble(&main_c)
}

pub fn sanitize(s: &str) -> String {
    s.chars().map(|c| if c.is_ascii_alphanumeric() { c } else { '_' }).collect()
}

pub fn c_string(s: &str) -> String {
    let mut out = String::from("\"");
    for b in s.bytes() {
        match b {
            b'"' => out.push_str("\\\""),
            b'\\' => out.push_str("\\\\"),
            b'?' => out.push_str("\\?"),
            0x20..=0x7e => out.push(b as char),
            _ => {
                let _ = write!(out, "\\{:03o}", b);
            }
        }
    }
    out.push('"');
    out
}

impl<'a> Emitter<'a> {
    pub fn fresh(&mut self, base: &str) -> String {
        self.counter += 1;
        format!("{}{}", base, self.counter)
    }

    pub fn loc(&self, sp: Span) -> String {
        c_string(&self.sm.loc(sp))
    }

    // ---- types ----

    pub fn is_ptr_kind(&mut self, t: &Ty) -> bool {
        match t {
            Ty::Con(n, _) if n == "List" || n == "Map" => true,
            Ty::Con(..) if self.c.enum_variants(t).is_some() => self.is_boxed(t),
            _ => false,
        }
    }

    // An enum is boxed when it can contain itself by value.
    pub fn is_boxed(&mut self, t: &Ty) -> bool {
        if let Some(b) = self.boxed.get(t) {
            return *b;
        }
        let mut seen = HashSet::new();
        let mut stack: Vec<Ty> = self.c.enum_variants(t).unwrap().into_iter().flat_map(|(_, f)| f).collect();
        let mut found = false;
        while let Some(x) = stack.pop() {
            if x == *t {
                found = true;
                break;
            }
            if !seen.insert(x.clone()) {
                continue;
            }
            match &x {
                Ty::Tuple(ts) => stack.extend(ts.iter().cloned()),
                Ty::Con(n, _) if n == "List" || n == "Map" => {}
                Ty::Con(..) => {
                    if let Some(fs) = self.c.struct_fields(&x) {
                        stack.extend(fs.into_iter().map(|(_, t)| t));
                    } else if let Some(vs) = self.c.enum_variants(&x) {
                        stack.extend(vs.into_iter().flat_map(|(_, f)| f));
                    }
                }
                _ => {}
            }
        }
        self.boxed.insert(t.clone(), found);
        found
    }

    pub fn cty(&mut self, t: &Ty) -> String {
        if let Some(n) = self.tnames.get(t) {
            return n.clone();
        }
        let name = match t {
            Ty::Con(n, a) if a.is_empty() && matches!(n.as_str(), "Int" | "Float" | "Bool" | "Unit" | "Str" | "Console" | "Clock" | "Fs" | "Net" | "Listener" | "Conn") => {
                format!("tn_{}", n)
            }
            Ty::Con(n, a) if n == "List" && a[0].is("Str") => "tn_List_Str".to_string(),
            Ty::Fn(..) => "tn_fn".to_string(),
            Ty::Con(n, _) => {
                self.counter += 1;
                format!("t{}_{}", self.counter, sanitize(n))
            }
            Ty::Tuple(_) => {
                self.counter += 1;
                format!("t{}_Tuple", self.counter)
            }
            Ty::Param(_) | Ty::Var(_) => panic!("emit: non-concrete type {}", t),
        };
        self.tnames.insert(t.clone(), name.clone());
        let user = !name.starts_with("tn_");
        if user {
            // components first, so that by-value definitions can be ordered
            match t {
                Ty::Con(n, a) if n == "List" || n == "Map" => {
                    for x in a {
                        self.cty(x);
                    }
                }
                Ty::Tuple(ts) => {
                    for x in ts {
                        self.cty(x);
                    }
                }
                Ty::Con(..) => {
                    if let Some(fs) = self.c.struct_fields(t) {
                        for (_, x) in fs {
                            self.cty(&x);
                        }
                    } else if let Some(vs) = self.c.enum_variants(t) {
                        for (_, fs) in vs {
                            for x in fs {
                                self.cty(&x);
                            }
                        }
                    }
                }
                _ => {}
            }
            self.tlist.push(t.clone());
        }
        name
    }

    // By-value dependencies (types that must be complete before t).
    fn value_deps(&mut self, t: &Ty) -> Vec<Ty> {
        let mut v = match t {
            Ty::Tuple(ts) => ts.clone(),
            Ty::Con(n, _) if n == "List" || n == "Map" => vec![],
            Ty::Con(..) => {
                if let Some(fs) = self.c.struct_fields(t) {
                    fs.into_iter().map(|(_, t)| t).collect()
                } else if let Some(vs) = self.c.enum_variants(t) {
                    vs.into_iter().flat_map(|(_, f)| f).collect()
                } else {
                    vec![]
                }
            }
            _ => vec![],
        };
        v.retain(|x| self.tnames.get(x).map(|n| !n.starts_with("tn_")).unwrap_or(false));
        v
    }

    fn fields_of(&mut self, t: &Ty) -> Vec<(String, Ty)> {
        match t {
            Ty::Tuple(ts) => ts.iter().enumerate().map(|(i, t)| (format!("f{}", i), t.clone())).collect(),
            _ => self.c.struct_fields(t).unwrap().into_iter().map(|(n, t)| (format!("f_{}", n), t)).collect(),
        }
    }

    // Accessors used by the body emitter.
    pub fn tag(&mut self, t: &Ty, v: &str) -> String {
        if self.is_boxed(t) { format!("({})->tag", v) } else { format!("({}).tag", v) }
    }
    pub fn payload(&mut self, t: &Ty, v: &str, vi: usize, fi: usize) -> String {
        if self.is_boxed(t) {
            format!("({})->u.v{}.f{}", v, vi, fi)
        } else {
            format!("({}).u.v{}.f{}", v, vi, fi)
        }
    }
    pub fn variant_index(&self, t: &Ty, name: &str) -> usize {
        self.c.enum_variants(t).unwrap().iter().position(|(n, _)| n == name).unwrap()
    }
    pub fn ctor(&mut self, t: &Ty, vi: usize, args: &[String]) -> String {
        let n = self.cty(t);
        format!("{}_mk{}({})", n, vi, args.join(", "))
    }
    pub fn ctor_named(&mut self, t: &Ty, vname: &str, args: &[String]) -> String {
        let vi = self.variant_index(t, vname);
        self.ctor(t, vi, args)
    }

    fn union_def(&mut self, vs: &[(String, Vec<Ty>)]) -> String {
        let mut s = String::new();
        if vs.iter().any(|(_, f)| !f.is_empty()) {
            s.push_str(" union {");
            for (i, (_, fs)) in vs.iter().enumerate() {
                if fs.is_empty() {
                    continue;
                }
                s.push_str(" struct {");
                for (j, f) in fs.iter().enumerate() {
                    let ct = self.cty(f);
                    let _ = write!(s, " {} f{};", ct, j);
                }
                let _ = write!(s, " }} v{};", i);
            }
            s.push_str(" } u;");
        }
        s
    }

    // ---- assembly ----

    fn assemble(&mut self, main_c: &str) -> String {
        let mut out = String::new();
        out.push_str("/* generated by tenon; do not edit */\n");
        out.push_str(RUNTIME);
        out.push('\n');
        let types = self.tlist.clone();
        // 1. forward declarations
        for t in &types {
            let n = self.tnames[t].clone();
            if self.is_ptr_kind(t) {
                let _ = writeln!(out, "typedef struct {}_s *{};", n, n);
            } else {
                let _ = writeln!(out, "typedef struct {} {};", n, n);
            }
        }
        // 2. by-value definitions in dependency order
        let mut done: HashSet<Ty> = HashSet::new();
        for t in &types {
            self.define_value(t, &mut done, &mut out);
        }
        // 3. heap layouts
        for t in &types {
            let n = self.tnames[t].clone();
            match t {
                Ty::Con(k, a) if k == "List" => {
                    let e = self.cty(&a[0]);
                    let _ = writeln!(out, "TN_LIST_TYPE({}, {})", n, e);
                }
                Ty::Con(k, a) if k == "Map" => {
                    let (kk, vv) = (self.cty(&a[0]), self.cty(&a[1]));
                    let _ = writeln!(out, "TN_MAP_TYPE({}, {}, {})", n, kk, vv);
                }
                _ if self.is_ptr_kind(t) => {
                    let vs = self.c.enum_variants(t).unwrap();
                    let u = self.union_def(&vs);
                    let _ = writeln!(out, "struct {}_s {{ int64_t rc; int32_t tag;{} }};", n, u);
                }
                _ => {}
            }
        }
        // 4. helper prototypes, 5. container functions, 6. helper bodies
        let mut protos = String::new();
        let mut bodies = String::new();
        for t in &types {
            if matches!(t, Ty::Con(k, _) if k == "List" || k == "Map") {
                continue;
            }
            self.helpers_for(t, &mut protos, &mut bodies);
        }
        out.push_str(&protos);
        for t in &types {
            let n = self.tnames[t].clone();
            match t {
                Ty::Con(k, a) if k == "List" => {
                    let e = self.cty(&a[0]);
                    let _ = writeln!(out, "TN_LIST_FUNCS({}, {})", n, e);
                }
                Ty::Con(k, a) if k == "Map" => {
                    let (kk, vv) = (self.cty(&a[0]), self.cty(&a[1]));
                    let _ = writeln!(out, "TN_MAP_FUNCS({}, {}, {})", n, kk, vv);
                }
                _ => {}
            }
        }
        out.push_str(&bodies);
        out.push_str(&self.protos);
        out.push_str(&self.helpers);
        out.push_str(&self.bodies);
        out.push_str(main_c);
        out
    }

    fn define_value(&mut self, t: &Ty, done: &mut HashSet<Ty>, out: &mut String) {
        if done.contains(t) || self.is_ptr_kind(t) {
            return;
        }
        done.insert(t.clone());
        for d in self.value_deps(t) {
            self.define_value(&d, done, out);
        }
        let n = self.tnames[t].clone();
        if let Some(vs) = self.c.enum_variants(t) {
            let u = self.union_def(&vs);
            let _ = writeln!(out, "struct {} {{ int32_t tag;{} }};", n, u);
            return;
        }
        let fs = self.fields_of(t);
        let mut s = format!("struct {} {{", n);
        for (f, ft) in &fs {
            let ct = self.cty(ft);
            let _ = write!(s, " {} {};", ct, f);
        }
        if fs.is_empty() {
            s.push_str(" char _empty;");
        }
        s.push_str(" };\n");
        out.push_str(&s);
    }

    fn helpers_for(&mut self, t: &Ty, protos: &mut String, b: &mut String) {
        let n = self.tnames[t].clone();
        let _ = writeln!(
            protos,
            "static TN_UNUSED {n} {n}_retain({n} x); static TN_UNUSED void {n}_release({n} x); \
             static TN_UNUSED bool {n}_eq({n} a, {n} b); static TN_UNUSED int {n}_cmp({n} a, {n} b); \
             static TN_UNUSED uint64_t {n}_hash({n} x); static TN_UNUSED void {n}_show(tn_buf *b, {n} x, int mode); \
             static inline TN_UNUSED bool {n}_same({n} a, {n} b) {{ (void)a; (void)b; return false; }} \
             static TN_UNUSED bool {n}_dec(tn_dec *d, {n} *out);"
        );
        self.decoder_for(t, &n, b);
        if let Some(vs) = self.c.enum_variants(t) {
            let boxed = self.is_boxed(t);
            let acc = if boxed { "->" } else { "." };
            // constructors
            for (i, (_, fs)) in vs.iter().enumerate() {
                let params: Vec<String> = fs.iter().enumerate().map(|(j, f)| format!("{} a{}", self.cty(f), j)).collect();
                let _ = writeln!(protos, "static TN_UNUSED {} {}_mk{}({});", n, n, i, params.join(", "));
                if boxed && fs.is_empty() {
                    // Nullary variants of boxed enums are shared immortal objects.
                    let _ = writeln!(b, "static struct {n}_s {n}_null{i} = {{ .rc = INT64_MAX / 2, .tag = {i} }};");
                    let _ = writeln!(b, "static TN_UNUSED {n} {n}_mk{i}(void) {{ return &{n}_null{i}; }}");
                    continue;
                }
                let _ = write!(b, "static TN_UNUSED {} {}_mk{}({}) {{ ", n, n, i, params.join(", "));
                if boxed {
                    let _ = write!(b, "{n} x = tn_alloc(sizeof(struct {n}_s)); x->rc = 1; ");
                } else {
                    let _ = write!(b, "{n} x; ");
                }
                let _ = write!(b, "x{acc}tag = {i}; ");
                for j in 0..fs.len() {
                    let _ = write!(b, "x{acc}u.v{i}.f{j} = a{j}; ");
                }
                b.push_str("return x; }\n");
            }
            let each = |me: &mut Self, f: &dyn Fn(usize, usize, &str) -> String| -> String {
                let mut s = String::new();
                for (i, (_, fs)) in vs.iter().enumerate() {
                    if fs.is_empty() {
                        continue;
                    }
                    let _ = write!(s, "case {}: ", i);
                    for (j, ft) in fs.iter().enumerate() {
                        let tn = me.cty(ft);
                        s.push_str(&f(i, j, &tn));
                    }
                    s.push_str("break; ");
                }
                s
            };
            let rc = each(self, &|i, j, tn| format!("{tn}_retain(x{acc}u.v{i}.f{j}); "));
            let rl = each(self, &|i, j, tn| format!("{tn}_release(x{acc}u.v{i}.f{j}); "));
            let eq = each(self, &|i, j, tn| format!("if (!{tn}_eq(a{acc}u.v{i}.f{j}, b{acc}u.v{i}.f{j})) return false; "));
            let cm = each(self, &|i, j, tn| format!("if ((c = {tn}_cmp(a{acc}u.v{i}.f{j}, b{acc}u.v{i}.f{j}))) return c; "));
            let hs = each(self, &|i, j, tn| format!("h = tn_mix(h * 31 + {tn}_hash(x{acc}u.v{i}.f{j})); "));
            if boxed {
                let _ = writeln!(b, "static TN_UNUSED {n} {n}_retain({n} x) {{ x->rc++; return x; }}");
                let _ = writeln!(b, "static TN_UNUSED void {n}_release({n} x) {{ if (!x || --x->rc) return; switch (x->tag) {{ {rl}}} free(x); }}");
            } else {
                let _ = writeln!(b, "static TN_UNUSED {n} {n}_retain({n} x) {{ switch (x.tag) {{ {rc}}} return x; }}");
                let _ = writeln!(b, "static TN_UNUSED void {n}_release({n} x) {{ switch (x.tag) {{ {rl}}} }}");
            }
            let _ = writeln!(b, "static TN_UNUSED bool {n}_eq({n} a, {n} b) {{ if (a{acc}tag != b{acc}tag) return false; switch (a{acc}tag) {{ {eq}}} return true; }}");
            let _ = writeln!(b, "static TN_UNUSED int {n}_cmp({n} a, {n} b) {{ int c = 0; if (a{acc}tag != b{acc}tag) return a{acc}tag < b{acc}tag ? -1 : 1; switch (a{acc}tag) {{ {cm}}} return c; }}");
            let _ = writeln!(b, "static TN_UNUSED uint64_t {n}_hash({n} x) {{ uint64_t h = (uint64_t)x{acc}tag + 1; switch (x{acc}tag) {{ {hs}}} return h; }}");
            let mut sh = String::new();
            for (i, (vn, fs)) in vs.iter().enumerate() {
                let _ = write!(sh, "case {}: tn_buf_cstr(b, {}); ", i, c_string(vn));
                if !fs.is_empty() {
                    sh.push_str("tn_buf_add(b, \"(\", 1); ");
                    for (j, ft) in fs.iter().enumerate() {
                        let tn = self.cty(ft);
                        if j > 0 {
                            sh.push_str("tn_buf_add(b, \", \", 2); ");
                        }
                        let _ = write!(sh, "{tn}_show(b, x{acc}u.v{i}.f{j}, mode & TN_FULL); ");
                    }
                    sh.push_str("tn_buf_add(b, \")\", 1); ");
                }
                sh.push_str("break; ");
            }
            let _ = writeln!(b, "static TN_UNUSED void {n}_show(tn_buf *b, {n} x, int mode) {{ (void)mode; switch (x{acc}tag) {{ {sh}}} }}");
            return;
        }
        // struct or tuple
        let fs = self.fields_of(t);
        let mut rc = String::new();
        let mut rl = String::new();
        let mut eq = String::from("true");
        let mut cm = String::new();
        let mut hs = String::new();
        let mut sh = String::new();
        let is_tuple = matches!(t, Ty::Tuple(_));
        let tname = match t {
            Ty::Con(n, _) => crate::interp::display(n).to_string(),
            _ => String::new(),
        };
        if is_tuple {
            sh.push_str("tn_buf_add(b, \"(\", 1); ");
        } else if fs.is_empty() {
            let _ = write!(sh, "tn_buf_cstr(b, {}); ", c_string(&format!("{} {{}}", tname)));
        } else {
            let _ = write!(sh, "tn_buf_cstr(b, {}); ", c_string(&format!("{} {{ ", tname)));
        }
        let shown: Vec<Option<String>> = match t {
            Ty::Con(n, _) => crate::interp::shown_fields(&self.c.structs[self.c.struct_idx(n).unwrap()]),
            _ => vec![],
        };
        let mut hidden = false;
        for (k, (f, ft)) in fs.iter().enumerate() {
            let tn = self.cty(ft);
            let _ = write!(rc, "{tn}_retain(x.{f}); ");
            let _ = write!(rl, "{tn}_release(x.{f}); ");
            let _ = write!(eq, " && {tn}_eq(a.{f}, b.{f})");
            let _ = write!(cm, "if ((c = {tn}_cmp(a.{f}, b.{f}))) return c; ");
            let _ = write!(hs, "h = tn_mix(h * 31 + {tn}_hash(x.{f})); ");
            if k > 0 {
                sh.push_str("tn_buf_add(b, \", \", 2); ");
            }
            if !is_tuple && matches!(shown.get(k), Some(None)) {
                // private to another module: hidden unless encoding
                sh.push_str("if (!(mode & TN_FULL)) { tn_buf_cstr(b, \"..\"); goto end; } ");
                hidden = true;
            }
            if !is_tuple {
                let _ = write!(sh, "tn_buf_cstr(b, {}); ", c_string(&format!("{}: ", &f[2..])));
            }
            let _ = write!(sh, "{tn}_show(b, x.{f}, mode & TN_FULL); ");
        }
        if hidden {
            sh.push_str("end: ");
        }
        if is_tuple {
            sh.push_str("tn_buf_add(b, \")\", 1); ");
        } else if !fs.is_empty() {
            sh.push_str("tn_buf_cstr(b, \" }\"); ");
        }
        let _ = writeln!(b, "static TN_UNUSED {n} {n}_retain({n} x) {{ {rc}return x; }}");
        let _ = writeln!(b, "static TN_UNUSED void {n}_release({n} x) {{ {rl}(void)x; }}");
        let _ = writeln!(b, "static TN_UNUSED bool {n}_eq({n} a, {n} b) {{ (void)a; (void)b; return {eq}; }}");
        let _ = writeln!(b, "static TN_UNUSED int {n}_cmp({n} a, {n} b) {{ int c; (void)a; (void)b; (void)c; {cm}return 0; }}");
        let _ = writeln!(b, "static TN_UNUSED uint64_t {n}_hash({n} x) {{ uint64_t h = 3; {hs}(void)x; return h; }}");
        let _ = writeln!(b, "static TN_UNUSED void {n}_show(tn_buf *b, {n} x, int mode) {{ (void)mode; (void)x; {sh}}}");
    }

    // Strict decoder, step for step the same as codec.rs (so failure offsets agree).
    fn decoder_for(&mut self, t: &Ty, n: &str, b: &mut String) {
        let ex = |l: &str| format!("if (!tn_dec_expect(d, {})) goto fail; ", c_string(l));
        let mut body = String::new();
        let mut fail = String::new(); // releases, guarded by how far decoding got
        if let Some(vs) = self.c.enum_variants(t) {
            body.push_str("int64_t st = d->pos; tn_Str nm = tn_dec_run(d, 2); ");
            for (i, (vn, fs)) in vs.iter().enumerate() {
                let _ = write!(body, "if (tn_str_eq_c(nm, {})) {{ ", c_string(vn));
                let mut args = Vec::new();
                if !fs.is_empty() {
                    body.push_str(&ex("("));
                    for (j, ft) in fs.iter().enumerate() {
                        let tn = self.cty(ft);
                        let _ = write!(body, "{tn} a{j}; ");
                        if j > 0 {
                            body.push_str(&format!("if (!tn_dec_expect(d, \", \")) {{ {}goto fail; }} ", self.rel_args(fs, j)));
                        }
                        let _ = write!(body, "if (!{tn}_dec(d, &a{j})) {{ {}goto fail; }} ", self.rel_args(fs, j));
                        args.push(format!("a{}", j));
                    }
                    let _ = write!(body, "if (!tn_dec_expect(d, \")\")) {{ {}goto fail; }} ", self.rel_args(fs, fs.len()));
                }
                let _ = write!(body, "*out = {}_mk{}({}); return true; }} ", n, i, args.join(", "));
            }
            body.push_str("tn_dec_fail(d, st); ");
        } else {
            let fs = self.fields_of(t);
            let is_tuple = matches!(t, Ty::Tuple(_));
            let _ = write!(body, "{n} x; ");
            if is_tuple {
                body.push_str(&ex("("));
            } else {
                let disp = match t {
                    Ty::Con(tn, _) => crate::interp::display(tn).to_string(),
                    _ => unreachable!(),
                };
                body.push_str(&ex(&disp));
                body.push_str(&ex(if fs.is_empty() { " {}" } else { " { " }));
            }
            for (k, (f, ft)) in fs.iter().enumerate() {
                let tn = self.cty(ft);
                let rel: String = fs[..k].iter().map(|(g, gt)| format!("{}_release(x.{}); ", self.cty(gt), g)).collect();
                if k > 0 {
                    let _ = write!(body, "if (!tn_dec_expect(d, \", \")) {{ {rel}goto fail; }} ");
                }
                if !is_tuple {
                    let _ = write!(body, "if (!tn_dec_expect(d, {})) {{ {rel}goto fail; }} ", c_string(&f[2..]));
                    let _ = write!(body, "if (!tn_dec_expect(d, \": \")) {{ {rel}goto fail; }} ");
                }
                let _ = write!(body, "if (!{tn}_dec(d, &x.{f})) {{ {rel}goto fail; }} ");
            }
            let rel: String = fs.iter().map(|(g, gt)| format!("{}_release(x.{}); ", self.cty(gt), g)).collect();
            let close = if is_tuple { ")" } else if fs.is_empty() { "" } else { " }" };
            if !close.is_empty() {
                let _ = write!(body, "if (!tn_dec_expect(d, {})) {{ {rel}goto fail; }} ", c_string(close));
            }
            body.push_str("*out = x; return true; ");
        }
        fail.push_str("fail: return false;");
        let _ = writeln!(b, "static TN_UNUSED bool {n}_dec(tn_dec *d, {n} *out) {{ {body}{fail} }}");
    }

    fn rel_args(&mut self, fs: &[Ty], upto: usize) -> String {
        fs[..upto].iter().enumerate().map(|(j, ft)| format!("{}_release(a{}); ", self.cty(ft), j)).collect()
    }

    fn main_wrapper(&mut self, main_name: &str) -> String {
        let f = &self.c.fns[self.c.main];
        let mut s = String::from("int main(int argc, char **argv) {\n    tn_init(argc, argv);\n");
        let args = if f.params.is_empty() {
            String::new()
        } else {
            let sys = Ty::con("Sys");
            let n = self.cty(&sys);
            let _ = writeln!(
                s,
                "    {n} sys = {{ .f_console = 0, .f_fs = tn_fs_make(tn_str_lit(\"\", 0), false, true), .f_clock = 0, .f_net = 0, .f_args = tn_args() }};"
            );
            "sys".to_string()
        };
        let ret = f.ret.clone();
        if ret.is("Int") {
            let loc = c_string(&self.sm.loc(f.span));
            let _ = writeln!(
                s,
                "    tn_Int code = {main_name}({args});\n    if (code < 0 || code > 255 || code == 70 || code == 71 || code == 72 || code == 74)\n        \
                 tn_trapf({loc}, \"exit status %lld is out of range or reserved\", (long long)code);\n    tn_exit((int)code);"
            );
            s.push_str("}\n");
            return s;
        }
        if ret.is("Result") {
            let rn = self.cty(&ret);
            let en = self.cty(&ret.args()[1]);
            let _ = writeln!(s, "    {rn} r = {main_name}({args});");
            let p = self.payload(&ret, "r", 1, 0);
            let _ = writeln!(
                s,
                "    if (r.tag == 1) {{ tn_buf b = tn_buf_new(); tn_buf_cstr(&b, \"error: \"); {en}_show(&b, {p}, true); \
                 tn_buf_add(&b, \"\\n\", 1); tn_flush(); tn_write_fd(2, b.p + sizeof(tn_rc), (size_t)b.len, false); tn_exit(TN_EXIT_ERR); }}"
            );
        } else {
            let _ = writeln!(s, "    {main_name}({args});");
        }
        s.push_str("    tn_exit(0);\n}\n");
        s
    }
}

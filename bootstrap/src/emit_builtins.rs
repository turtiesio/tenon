// C backend, part 3: the `extern fn`s of lib/prelude.tn, lowered to runtime
// calls (runtime/tenon.h).

use crate::emit_body::{bor, CV};
use crate::emit_c::*;
use crate::types::Ty;
use std::fmt::Write;

impl<'a> Emitter<'a> {
    fn some_none(&mut self, t: &Ty, cond: &str, val: &str) -> CV {
        let s = self.ctor_named(t, "Some", &[val.to_string()]);
        let n = self.ctor_named(t, "None", &[]);
        self.tmp_owned(t, &format!("{} ? {} : {}", cond, s, n))
    }
    fn io_result(&mut self, t: &Ty, k: &str, ok: &str, msg: &str) -> CV {
        let et = t.args()[1].clone();
        let errs: Vec<String> = (0..3).map(|i| self.ctor(&et, i, &[msg.to_string()])).collect();
        let err = format!("({k} == 1 ? {} : {k} == 2 ? {} : {})", errs[0], errs[1], errs[2]);
        let okv = self.ctor_named(t, "Ok", &[ok.to_string()]);
        let errv = self.ctor_named(t, "Err", &[err]);
        self.tmp_owned(t, &format!("{} == 0 ? {} : {}", k, okv, errv))
    }
    pub(crate) fn extern_call(&mut self, name: &str, args: Vec<CV>, ptys: &[Ty], t: &Ty, sp: crate::diag::Span) -> CV {
        let a: Vec<String> = args.iter().map(|v| v.code.clone()).collect();
        let loc = self.loc(sp);
        let tn = self.cty(t);
        match name {
            "panic" => {
                self.line(&format!("tn_trap_str({}, {});", a[0], loc));
                let r = self.fresh("t");
                self.line(&format!("{} {} = {{0}};", tn, r));
                bor(r)
            }
            "encode" => {
                let xn = self.cty(&ptys[0]);
                let b = self.fresh("b");
                self.line(&format!("tn_buf {} = tn_buf_new(); {}_show(&{}, {}, TN_FULL);", b, xn, b, a[0]));
                self.tmp_owned(t, &format!("tn_buf_finish(&{})", b))
            }
            "decode" => {
                let vt = t.args()[0].clone();
                let vn = self.cty(&vt);
                let (d, v, ok) = (self.fresh("d"), self.fresh("v"), self.fresh("ok"));
                self.line(&format!("tn_dec {d} = {{ ({0}).p, ({0}).len, 0, -1 }}; {vn} {v}; bool {ok} = {vn}_dec(&{d}, &{v});", a[0]));
                self.line(&format!("if ({ok} && {d}.pos != {d}.n) {{ {vn}_release({v}); {ok} = false; tn_dec_fail(&{d}, {d}.pos); }}"));
                let okv = self.ctor_named(t, "Ok", &[v.clone()]);
                let msg = format!("tn_dec_msg(&{}, {})", d, c_string(&vt.to_string()));
                let errv = self.ctor_named(t, "Err", &[msg]);
                self.tmp_owned(t, &format!("{} ? {} : {}", ok, okv, errv))
            }
            "assert" => {
                self.line(&format!("if (!({})) tn_trap(\"assertion failed\", {});", a[0], loc));
                bor("0")
            }
            "Int.to_float" => self.tmp_val(t, &format!("(double)({})", a[0])),
            "Int.checked_add" | "Int.checked_sub" | "Int.checked_mul" | "Int.checked_div" => {
                let r = self.fresh("r");
                self.line(&format!("tn_Int {} = 0;", r));
                let ok = match name {
                    "Int.checked_add" => format!("!__builtin_add_overflow({}, {}, &{})", a[0], a[1], r),
                    "Int.checked_sub" => format!("!__builtin_sub_overflow({}, {}, &{})", a[0], a[1], r),
                    "Int.checked_mul" => format!("!__builtin_mul_overflow({}, {}, &{})", a[0], a[1], r),
                    _ => format!("(({1}) != 0 && !(({0}) == INT64_MIN && ({1}) == -1) && (({r} = ({0}) / ({1})), 1))", a[0], a[1], r = r),
                };
                let okv = self.tmp_val(&Ty::bool(), &ok).code;
                self.some_none(t, &okv, &r)
            }
            "Int.char" => self.tmp_owned(t, &format!("tn_int_char({}, {})", a[0], loc)),
            "Float.to_int" => self.tmp_val(t, &format!("tn_float_to_int({}, {})", a[0], loc)),
            "Float.to_fixed" => self.tmp_owned(t, &format!("tn_float_fixed({}, {})", a[0], a[1])),
            "Float.sqrt" | "Float.floor" | "Float.ceil" | "Float.round" => {
                self.tmp_val(t, &format!("{}({})", &name[6..], a[0]))
            }
            "Str.len" => self.tmp_val(t, &format!("({}).len", a[0])),
            "Str.char_count" => self.tmp_val(t, &format!("tn_str_char_count({})", a[0])),
            "Str.byte" => self.tmp_val(t, &format!("tn_str_byte({}, {}, {})", a[0], a[1], loc)),
            "Str.slice" => self.tmp_owned(t, &format!("tn_str_slice({}, {}, {}, {})", a[0], a[1], a[2], loc)),
            "Str.find_from" => {
                let n = self.tmp_val(&Ty::int(), &format!("{}", a[2])).code;
                self.line(&format!("if ({n} < 0 || {n} > ({0}).len) tn_trapf({loc}, \"index %lld out of bounds for length %lld\", (long long){n}, (long long)({0}).len);", a[0]));
                let i = self.tmp_val(&Ty::int(), &format!("tn_str_find({}, {}, {})", a[0], a[1], n)).code;
                self.some_none(t, &format!("{} >= 0", i), &i)
            }
            "Str.find" => {
                let i = self.tmp_val(&Ty::int(), &format!("tn_str_find({}, {}, 0)", a[0], a[1])).code;
                self.some_none(t, &format!("{} >= 0", i), &i)
            }
            "Str.split" => self.tmp_owned(t, &format!("tn_str_split({}, {}, {})", a[0], a[1], loc)),
            "Str.words" => self.tmp_owned(t, &format!("tn_str_words({})", a[0])),
            "Str.lines" => self.tmp_owned(t, &format!("tn_str_lines({})", a[0])),
            "Str.trim" => self.tmp_owned(t, &format!("tn_str_trim({}, true, true)", a[0])),
            "Str.trim_start" => self.tmp_owned(t, &format!("tn_str_trim({}, true, false)", a[0])),
            "Str.trim_end" => self.tmp_owned(t, &format!("tn_str_trim({}, false, true)", a[0])),
            "Str.starts_with" => self.tmp_val(t, &format!("tn_str_starts({}, {})", a[0], a[1])),
            "Str.ends_with" => self.tmp_val(t, &format!("tn_str_ends({}, {})", a[0], a[1])),
            "Str.to_int" | "Str.to_float" => {
                let (ty, f) = if name == "Str.to_int" { ("tn_Int", "tn_str_to_int") } else { ("tn_Float", "tn_str_to_float") };
                let o = self.fresh("o");
                self.line(&format!("{} {} = 0;", ty, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}({}, &{})", f, a[0], o)).code;
                self.some_none(t, &ok, &o)
            }
            "Str.upper" | "Str.lower" if args[0].owned => {
                // The receiver is a temporary: hand it over so it can be reused in place.
                self.unreg(&a[0]);
                self.tmp_owned(t, &format!("tn_str_case_move({}, {})", a[0], name == "Str.upper"))
            }
            "Str.upper" | "Str.lower" => {
                self.tmp_owned(t, &format!("tn_str_case({}, {})", a[0], name == "Str.upper"))
            }
            "Str.replace" => self.tmp_owned(t, &format!("tn_str_replace({}, {}, {}, {})", a[0], a[1], a[2], loc)),
            "Str.chars" => self.tmp_owned(t, &format!("tn_str_chars({})", a[0])),
            "Str.bytes" => self.tmp_owned(t, &format!("tn_bytes_list(({0}).p, ({0}).len)", a[0])),
            "Str.from_utf8" => {
                let s = self.fresh("s");
                self.line(&format!("tn_Str {} = {{0}};", s));
                let ok = self.tmp_val(&Ty::bool(), &format!("tn_str_from_utf8({}, &{})", a[0], s)).code;
                self.some_none(t, &ok, &s)
            }
            "Str.from_utf8_lossy" => self.tmp_owned(t, &format!("tn_str_from_utf8_lossy({}, {})", a[0], loc)),
            "List.len" => {
                let ln = self.cty(&ptys[0]);
                self.tmp_val(t, &format!("{}_len({})", ln, a[0]))
            }
            "List.slice" => {
                let ln = self.cty(&ptys[0]);
                self.tmp_owned(t, &format!("{}_slice({}, {}, {}, {})", ln, a[0], a[1], a[2], loc))
            }
            "List.join" => self.tmp_owned(t, &format!("tn_str_join({}, {})", a[0], a[1])),
            "Map.len" => {
                let mn = self.cty(&ptys[0]);
                self.tmp_val(t, &format!("{}_len({})", mn, a[0]))
            }
            "Map.get" => {
                let mn = self.cty(&ptys[0]);
                let vt = ptys[0].args()[1].clone();
                let vn = self.cty(&vt);
                let p = self.fresh("p");
                self.line(&format!("{} *{} = {}_get({}, {});", vn, p, mn, a[0], a[1]));
                let val = if self.trivial(&vt) { format!("*{}", p) } else { format!("{}_retain(*{})", vn, p) };
                self.some_none(t, &p, &val)
            }
            "Map.keys" | "Map.values" => {
                let ln = tn.clone();
                let et = t.args()[0].clone();
                let en = self.cty(&et);
                let l = self.tmp_owned(t, "NULL");
                let f = if name == "Map.keys" { "k" } else { "v" };
                let i = self.fresh("i");
                self.line(&format!(
                    "for (int64_t {i} = 0; {m} && {i} < {m}->n; {i}++) if ({m}->e[{i}].live) {ln}_push(&{l}, {en}_retain({m}->e[{i}].{f}));",
                    m = a[0],
                    l = l.code
                ));
                l
            }
            "Option.unwrap" | "Option.expect" | "Result.unwrap" | "Result.expect" => {
                let xt = ptys[0].clone();
                let tag = self.tag(&xt, &a[0]);
                self.line(&format!("if ({} != 0) {{", tag));
                match name {
                    "Option.unwrap" => self.line(&format!("    tn_trap(\"unwrap on None\", {});", loc)),
                    "Option.expect" => self.line(&format!("    tn_trap_str({}, {});", a[1], loc)),
                    _ => {
                        let b = self.fresh("b");
                        self.line(&format!("    tn_buf {} = tn_buf_new();", b));
                        if name == "Result.unwrap" {
                            let xn = self.cty(&xt);
                            self.line(&format!("    tn_buf_cstr(&{}, \"unwrap on \"); {}_show(&{}, {}, 0);", b, xn, b, a[0]));
                        } else {
                            let et = xt.args()[1].clone();
                            let en = self.cty(&et);
                            let p = self.payload(&xt, &a[0], 1, 0);
                            self.line(&format!("    tn_buf_str(&{b}, {}); tn_buf_cstr(&{b}, \": \"); {en}_show(&{b}, {p}, 0);", a[1]));
                        }
                        self.line(&format!("    tn_trap_buf(&{}, {});", b, loc));
                    }
                }
                self.line("}");
                bor(self.payload(&xt, &a[0], 0, 0))
            }
            "Console.print" | "Console.println" => {
                self.line(&format!("tn_write(({}).p, (size_t)({}).len);", a[1], a[1]));
                if name == "Console.println" {
                    self.line("tn_write(\"\\n\", 1);");
                }
                bor("0")
            }
            "Console.flush" => {
                self.line("tn_flush();");
                bor("0")
            }
            "Console.eprintln" => {
                self.line(&format!("tn_eprintln({});", a[1]));
                bor("0")
            }
            "Console.read_line" => {
                let s = self.fresh("s");
                self.line(&format!("tn_Str {} = {{0}};", s));
                let ok = self.tmp_val(&Ty::bool(), &format!("tn_read_line(&{})", s)).code;
                self.some_none(t, &ok, &s)
            }
            "Console.read_all" => self.tmp_owned(t, "tn_read_all()"),
            "Console.read_all_bytes" => self.tmp_owned(t, "tn_read_all_bytes()"),
            "Console.write_bytes" => {
                self.line(&format!("tn_write_bytes({}, {});", a[1], loc));
                bor("0")
            }
            "Fs.read" | "Fs.list" | "Fs.read_bytes" => {
                let okt = t.args()[0].clone();
                let on = self.cty(&okt);
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("{} {} = {{0}}; tn_Str {} = {{0}};", on, r, m));
                let f = format!("tn_fs_{}", &name[3..]);
                let k = self.tmp_val(&Ty::int(), &format!("{}({}, {}, &{}, &{})", f, a[0], a[1], r, m)).code;
                self.io_result(t, &k, &r, &m)
            }
            "Fs.write" | "Fs.append" | "Fs.write_bytes" | "Fs.append_bytes" | "Fs.remove" | "Fs.mkdir" | "Fs.mkdir_one" => {
                // the byte variants convert first (an out-of-range byte traps before any check)
                let data = match name {
                    "Fs.write" | "Fs.append" => a[2].clone(),
                    "Fs.write_bytes" | "Fs.append_bytes" => self.tmp_owned(&Ty::str(), &format!("tn_bytes_of({}, {})", a[2], loc)).code,
                    _ => String::new(),
                };
                let m = self.fresh("m");
                self.line(&format!("tn_Str {} = {{0}};", m));
                let f = format!("tn_fs_{}", name[3..].trim_end_matches("_bytes"));
                let extra = if data.is_empty() { String::new() } else { format!("{}, ", data) };
                let k = self.tmp_val(&Ty::int(), &format!("{}({}, {}, {}&{})", f, a[0], a[1], extra, m)).code;
                self.io_result(t, &k, "0", &m)
            }
            "Fs.truncate" => {
                let m = self.fresh("m");
                self.line(&format!("tn_Str {} = {{0}};", m));
                let k = self.tmp_val(&Ty::int(), &format!("tn_fs_truncate({}, {}, {}, &{})", a[0], a[1], a[2], m)).code;
                self.io_result(t, &k, "0", &m)
            }
            "Fs.exists" => self.tmp_val(t, &format!("tn_fs_exists({}, {})", a[0], a[1])),
            "Fs.is_dir" => self.tmp_val(t, &format!("tn_fs_is_dir({}, {})", a[0], a[1])),
            "Fs.rename" => {
                let m = self.fresh("m");
                self.line(&format!("tn_Str {} = {{0}};", m));
                let k = self.tmp_val(&Ty::int(), &format!("tn_fs_rename({}, {}, {}, &{})", a[0], a[1], a[2], m)).code;
                self.io_result(t, &k, "0", &m)
            }
            "Fs.within" => self.tmp_owned(t, &format!("tn_fs_within({}, {})", a[0], a[1])),
            "Fs.read_only" => {
                self.tmp_owned(t, &format!("tn_fs_make(tn_Str_retain(({0})->root), ({0})->att, false)", a[0]))
            }
            "Net.listen" | "Net.connect" | "Listener.accept" | "Conn.read" | "Conn.write" => {
                let okt = t.args()[0].clone();
                let on = self.cty(&okt);
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("{} {} = {{0}}; tn_Str {} = {{0}};", on, r, m));
                let call = match name {
                    "Net.listen" => format!("tn_net_listen({}, &{}, &{})", a[1], r, m),
                    "Net.connect" => format!("tn_net_connect({}, {}, &{}, &{})", a[1], a[2], r, m),
                    "Listener.accept" => format!("tn_listener_accept({}, &{}, &{})", a[0], r, m),
                    "Conn.read" => format!("tn_conn_read({}, {}, &{}, &{})", a[0], a[1], r, m),
                    _ => format!("tn_conn_write({}, {}, &{})", a[0], a[1], m),
                };
                let k = self.tmp_val(&Ty::int(), &call).code;
                self.io_result(t, &k, &r, &m)
            }
            "Conn.read_line" => {
                let opt = t.args()[0].clone();
                let (some, l, m) = (self.fresh("some"), self.fresh("l"), self.fresh("m"));
                self.line(&format!("bool {} = false; tn_Str {} = {{0}}, {} = {{0}};", some, l, m));
                let k = self.tmp_val(&Ty::int(), &format!("tn_conn_read_line({}, &{}, &{}, &{})", a[0], some, l, m)).code;
                let sm = self.ctor_named(&opt, "Some", &[l.clone()]);
                let nn = self.ctor_named(&opt, "None", &[]);
                let o = self.tmp_val(&opt, &format!("{} ? {} : {}", some, sm, nn)).code;
                self.io_result(t, &k, &o, &m)
            }
            "Listener.port" => self.tmp_val(t, &format!("tn_listener_port({})", a[0])),
            "Net.poller" => self.tmp_owned(t, "tn_net_poller()"),
            "Poller.port" => self.tmp_val(t, &format!("tn_poller_port({}, {})", a[0], a[1])),
            "Poller.close" => {
                self.line(&format!("tn_poller_close({}, {});", a[0], a[1]));
                bor("0")
            }
            "Poller.listen" | "Poller.connect" | "Poller.send" => {
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("tn_Int {} = 0; tn_Str {} = {{0}};", r, m));
                let call = match name {
                    "Poller.listen" => format!("tn_poller_listen({}, {}, &{}, &{})", a[0], a[1], r, m),
                    "Poller.connect" => format!("tn_poller_connect({}, {}, {}, &{}, &{})", a[0], a[1], a[2], r, m),
                    _ => format!("tn_poller_send({}, {}, {}, &{})", a[0], a[1], a[2], m),
                };
                let k = self.tmp_val(&Ty::int(), &call).code;
                let okv = if name == "Poller.send" { "0".to_string() } else { r };
                self.io_result(t, &k, &okv, &m)
            }
            "Poller.wait" => {
                let et = t.args()[0].clone();
                let ln = self.cty(t);
                let (ev, n, i) = (self.fresh("ev"), self.fresh("n"), self.fresh("i"));
                self.line(&format!("tn_rawev *{ev}; int64_t {n} = tn_poller_wait({}, {}, &{ev});", a[0], a[1]));
                let l = self.tmp_owned(t, "NULL").code;
                let acc = self.ctor(&et, 0, &[format!("{ev}[{i}].a"), format!("{ev}[{i}].b")]);
                let dat = self.ctor(&et, 1, &[format!("{ev}[{i}].a"), format!("{ev}[{i}].data")]);
                let clo = self.ctor(&et, 2, &[format!("{ev}[{i}].a")]);
                let tmo = self.ctor(&et, 3, &[]);
                self.line(&format!(
                    "for (int64_t {i} = 0; {i} < {n}; {i}++) {ln}_push(&{l}, {ev}[{i}].kind == 0 ? {acc} : {ev}[{i}].kind == 1 ? {dat} : {ev}[{i}].kind == 2 ? {clo} : {tmo});"
                ));
                self.line(&format!("tn_free({ev});"));
                bor(l)
            }
            "Proc.run" => {
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("tn_Int {} = 0; tn_Str {} = {{0}};", r, m));
                let k = self.tmp_val(&Ty::int(), &format!("tn_proc_run({}, {}, &{}, &{})", a[1], a[2], r, m)).code;
                self.io_result(t, &k, &r, &m)
            }
            "Proc.env" => {
                let s = self.fresh("s");
                self.line(&format!("tn_Str {} = {{0}};", s));
                let ok = self.tmp_val(&Ty::bool(), &format!("tn_proc_env({}, &{})", a[1], s)).code;
                self.some_none(t, &ok, &s)
            }
            "Proc.run_capture" => {
                let input = self.tmp_owned(&Ty::str(), &format!("tn_bytes_of({}, {})", a[4], loc)).code;
                let on = self.cty(&t.args()[0]);
                let (r, m) = (self.fresh("r"), self.fresh("m"));
                self.line(&format!("{} {} = {{0}}; tn_Str {} = {{0}};", on, r, m));
                let call = format!("tn_proc_capture({}, {}, {}, {}, {}, &{}, &{})", a[1], a[2], a[3], input, a[5], r, m);
                let k = self.tmp_val(&Ty::int(), &call).code;
                self.io_result(t, &k, &r, &m)
            }
            "Proc.exit" => {
                self.line(&format!("tn_proc_exit({}, {});", a[1], loc));
                bor("0")
            }
            "Clock.now_ms" => self.tmp_val(t, "tn_now_ms()"),
            "Clock.mono_ns" => self.tmp_val(t, "tn_mono_ns()"),
            "Clock.sleep_ms" => {
                self.line(&format!("tn_sleep_ms({});", a[1]));
                bor("0")
            }
            _ => panic!("emit: missing builtin {}", name),
        }
    }
    // Mutating builtins: `p` points at the receiver place; args are owned temps.
    pub(crate) fn extern_mut(&mut self, name: &str, p: &str, ptys: &[Ty], args: Vec<CV>, t: &Ty, sp: crate::diag::Span) -> CV {
        let rt = &ptys[0];
        let loc = self.loc(sp);
        let ln = self.cty(rt);
        let mut a = Vec::new();
        let tys: Vec<Ty> = match name {
            "List.push" => vec![rt.args()[0].clone()],
            "List.insert" => vec![Ty::int(), rt.args()[0].clone()],
            "List.sort_by" | "List.sort_by_desc" => vec![Ty::unit()],
            "Map.insert" => vec![rt.args()[0].clone(), rt.args()[1].clone()],
            _ => args.iter().map(|_| Ty::unit()).collect(),
        };
        for (v, ty) in args.into_iter().zip(tys) {
            if name == "List.sort_by" || name == "List.sort_by_desc" || name == "Map.remove" || name == "List.remove" {
                a.push(v.code);
            } else {
                a.push(self.own(v, &ty));
            }
        }
        match name {
            "List.push" => {
                self.line(&format!("{}_push({}, {});", ln, p, a[0]));
                bor("0")
            }
            "List.pop" => {
                let et = rt.args()[0].clone();
                let en = self.cty(&et);
                let o = self.fresh("o");
                self.line(&format!("{} {} = {{0}};", en, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}_pop({}, &{})", ln, p, o)).code;
                self.some_none(t, &ok, &o)
            }
            "List.insert" => {
                self.line(&format!("{}_insert({}, {}, {}, {});", ln, p, a[0], a[1], loc));
                bor("0")
            }
            "List.remove" => self.tmp_owned(t, &format!("{}_remove({}, {}, {})", ln, p, a[0], loc)),
            "List.clear" | "List.reverse" | "List.sort" => {
                if name == "List.sort" && rt.any(&|x| x.is("Map")) {
                    self.line(&format!("tn_cur_loc = {};", loc));
                }
                self.line(&format!("{}_{}({});", ln, &name[5..], p));
                bor("0")
            }
            "List.sort_by" | "List.sort_by_desc" => {
                let Ty::Fn(_, kt) = ptys[1].clone() else { unreachable!() };
                let h = self.sort_by_helper(rt, &kt, name == "List.sort_by_desc");
                if kt.any(&|x| x.is("Map")) {
                    self.line(&format!("tn_cur_loc = {};", loc));
                }
                self.line(&format!("{}({}, {});", h, p, a[0]));
                bor("0")
            }
            "Map.insert" => {
                self.line(&format!("{}_insert({}, {}, {});", ln, p, a[0], a[1]));
                bor("0")
            }
            "Map.remove" => {
                let vt = rt.args()[1].clone();
                let vn = self.cty(&vt);
                let o = self.fresh("o");
                self.line(&format!("{} {} = {{0}};", vn, o));
                let ok = self.tmp_val(&Ty::bool(), &format!("{}_remove({}, {}, &{})", ln, p, a[0], o)).code;
                self.some_none(t, &ok, &o)
            }
            _ => panic!("emit: missing mutating builtin {}", name),
        }
    }
    fn sort_by_helper(&mut self, lt: &Ty, kt: &Ty, desc: bool) -> String {
        let key = format!("sortby{:?}{:?}{}", lt, kt, desc);
        if let Some(w) = self.wrappers.get(&key) {
            return w.clone();
        }
        let h = self.fresh("sortby");
        self.wrappers.insert(key, h.clone());
        let ln = self.cty(lt);
        let et = self.cty(&lt.args()[0]);
        let kn = self.cty(kt);
        let _ = writeln!(self.protos, "static void {}({} *p, tn_fn f);", h, ln);
        let _ = writeln!(
            self.helpers,
            "static int {h}_cmp(void *ctx, int64_t a, int64_t b) {{ {kn} *k = ctx; return {}{kn}_cmp(k[a], k[b]); }}",
            if desc { "-" } else { "" }
        );
        let _ = writeln!(
            self.bodies,
            "static void {h}({ln} *p, tn_fn f) {{\n    int64_t n = {ln}_len(*p);\n    if (n < 2) return;\n    \
             {kn} *keys = tn_alloc(sizeof({kn}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) keys[i] = (({kn} (*)(tn_env *, {et})) f.f)(f.env, (*p)->data[i]);\n    \
             int64_t *idx = tn_alloc(sizeof(int64_t) * (size_t)n), *tmp = tn_alloc(sizeof(int64_t) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) idx[i] = i;\n    tn_msort_idx(idx, tmp, n, {h}_cmp, keys);\n    \
             {ln}_unique(p);\n    {et} *out = tn_alloc(sizeof({et}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) out[i] = (*p)->data[idx[i]];\n    \
             memcpy((*p)->data, out, sizeof({et}) * (size_t)n);\n    \
             for (int64_t i = 0; i < n; i++) {kn}_release(keys[i]);\n    tn_free(keys); tn_free(idx); tn_free(tmp); tn_free(out);\n}}"
        );
        h
    }
}

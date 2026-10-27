// Reference-interpreter builtins: the `extern fn`s of src/prelude.tn
// (strings, lists, maps, console, file system, network, clock).

use crate::diag::Span;
use crate::interp::*;
use crate::value::*;
use std::io::{BufRead, Read, Write};
use std::rc::Rc;

impl<'a> Interp<'a> {
    pub(crate) fn extern_mut(&mut self, name: &str, root: &str, steps: &[Step], args: Vec<V>, sp: Span) -> R {
        // Evaluate anything that needs &self before borrowing the slot.
        let keys: Option<Vec<V>> = if name == "List.sort_by" || name == "List.sort_by_desc" {
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
            ("List.sort_by" | "List.sort_by_desc", V::List(xs)) => {
                let keys = keys.unwrap();
                let desc = name == "List.sort_by_desc";
                let mut idx: Vec<usize> = (0..xs.len()).collect();
                let mut bad = None;
                idx.sort_by(|a, b| match cmp(&keys[*a], &keys[*b]) {
                    Ok(c) => if desc { 0.cmp(&c) } else { c.cmp(&0) },
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
    pub(crate) fn ok(&self, v: V) -> V {
        self.variant("Result", "Ok", vec![v])
    }
    pub(crate) fn io_result<T>(&self, path: &str, r: std::io::Result<T>, f: impl FnOnce(T) -> V) -> V {
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
    pub(crate) fn call_extern(&mut self, name: &str, args: Vec<V>, sp: Span) -> R {
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
            "encode" => {
                let mut out = String::new();
                show(&a[0], false, &self.names_full(), &mut out);
                strv(&out)
            }
            "assert" => {
                if let Bool(false) = a[0] {
                    return trap("assertion failed", sp);
                }
                Unit
            }
            "Int.to_float" => Float(int(0) as f64),
            "Int.checked_add" => self.opt(int(0).checked_add(int(1)).map(Int)),
            "Int.checked_sub" => self.opt(int(0).checked_sub(int(1)).map(Int)),
            "Int.checked_mul" => self.opt(int(0).checked_mul(int(1)).map(Int)),
            "Int.checked_div" => self.opt(int(0).checked_div(int(1)).map(Int)),
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
            "Str.find_from" => {
                let (st, sub, from) = (s(0).as_bytes(), s(1).as_bytes(), int(2));
                if from < 0 || from as usize > st.len() {
                    return trap(format!("index {} out of bounds for length {}", from, st.len()), sp);
                }
                let from = from as usize;
                let hit = if sub.is_empty() { Some(from) } else { (from..st.len()).find(|&i| st[i..].starts_with(sub)) };
                self.opt(hit.map(|i| Int(i as i64)))
            }
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
            "Console.flush" => {
                if self.out.flush().is_err() {
                    return Err(Ctrl::Exit(crate::interp::EXIT_OUTPUT));
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
            n if n.starts_with("Net.") || n.starts_with("Listener.") || n.starts_with("Conn.") => return Ok(self.net_op(n, &args)),
            "Clock.now_ms" => Int(std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis() as i64)
                .unwrap_or(0)),
            "Clock.mono_ns" => Int(self.mono_origin.elapsed().as_nanos() as i64),
            "Clock.sleep_ms" => {
                let _ = self.out.flush();
                if int(1) > 0 {
                    std::thread::sleep(std::time::Duration::from_millis(int(1) as u64));
                }
                Unit
            }
            _ => panic!("interp: missing builtin {}", name),
        })
    }
    fn net_op(&mut self, name: &str, a: &[V]) -> V {
        use std::io::BufRead;
        // A program about to block has shown all of its output.
        let _ = self.out.flush();
        let V::Cap(cap) = &a[0] else { unreachable!() };
        let arg_s = |i: usize| match &a[i] {
            V::Str(s) => s.to_string(),
            _ => unreachable!(),
        };
        let arg_i = |i: usize| match &a[i] {
            V::Int(x) => *x,
            _ => unreachable!(),
        };
        let conn = |s: std::net::TcpStream| V::Cap(Rc::new(Cap::Conn(std::cell::RefCell::new(std::io::BufReader::new(s)))));
        match (name, &**cap) {
            ("Net.listen", _) => {
                let port = arg_i(1);
                let what = format!("127.0.0.1:{}", port);
                if !(0..=65535).contains(&port) {
                    return self.io_err("Failed", format!("{}: port must be 0-65535", what));
                }
                let r = std::net::TcpListener::bind(("127.0.0.1", port as u16));
                self.io_result(&what, r, |l| V::Cap(Rc::new(Cap::Listener(l))))
            }
            ("Net.connect", _) => {
                let (h, port) = (arg_s(1), arg_i(2));
                let what = format!("{}:{}", h, port);
                if !(0..=65535).contains(&port) {
                    return self.io_err("Failed", format!("{}: port must be 0-65535", what));
                }
                if h.contains('\0') || h.is_empty() {
                    return self.io_err("Failed", format!("{}: invalid host name", what));
                }
                // Name lookup failures are worded differently by every resolver: normalize.
                let addrs: Vec<std::net::SocketAddr> = match std::net::ToSocketAddrs::to_socket_addrs(&(h.as_str(), port as u16)) {
                    Ok(a) => a.collect(),
                    Err(_) => return self.io_err("Failed", format!("{}: host not found", what)),
                };
                let r = std::net::TcpStream::connect(&addrs[..]);
                self.io_result(&what, r, conn)
            }
            ("Listener.port", Cap::Listener(l)) => V::Int(l.local_addr().map(|a| a.port() as i64).unwrap_or(0)),
            ("Listener.accept", Cap::Listener(l)) => {
                let r = l.accept().map(|(s, _)| s);
                self.io_result("accept", r, conn)
            }
            ("Conn.read_line", Cap::Conn(c)) => {
                let mut buf = Vec::new();
                let r = c.borrow_mut().read_until(b'\n', &mut buf);
                let r = r.map(|n| {
                    if n == 0 {
                        return None;
                    }
                    if buf.ends_with(b"\n") {
                        buf.pop();
                        if buf.ends_with(b"\r") {
                            buf.pop();
                        }
                    }
                    Some(String::from_utf8_lossy(&buf).into_owned())
                });
                self.io_result("read", r, |o| self.opt(o.map(|s| V::Str(s.into()))))
            }
            ("Conn.read", Cap::Conn(c)) => {
                let n = arg_i(1).max(0) as usize;
                let mut buf = vec![0u8; n];
                let mut got = 0;
                let mut res = Ok(());
                while got < n {
                    match std::io::Read::read(&mut *c.borrow_mut(), &mut buf[got..]) {
                        Ok(0) => break,
                        Ok(k) => got += k,
                        Err(e) if e.kind() == std::io::ErrorKind::Interrupted => {}
                        Err(e) => {
                            res = Err(e);
                            break;
                        }
                    }
                }
                buf.truncate(got);
                self.io_result("read", res, |_| V::Str(String::from_utf8_lossy(&buf).into_owned().into()))
            }
            ("Conn.write", Cap::Conn(c)) => {
                let s = arg_s(1);
                let r = std::io::Write::write_all(c.borrow_mut().get_mut(), s.as_bytes());
                self.io_result("write", r, |_| V::Unit)
            }
            _ => unreachable!("net op {}", name),
        }
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
                    "Fs.exists" | "Fs.is_dir" => V::Bool(false),
                    "Fs.within" => V::Cap(Rc::new(Cap::Fs { root: "/nonexistent-denied".into(), attenuated: true, writable: false })),
                    _ => self.io_err("Denied", format!("path escapes the Fs root: {}", p)),
                });
            }
        };
        let writes = matches!(name, "Fs.write" | "Fs.append" | "Fs.remove" | "Fs.mkdir" | "Fs.rename");
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
                    // never write through a pre-existing temp file (it may be a planted symlink)
                    let _ = std::fs::remove_file(&tmp);
                    let mut f = std::fs::OpenOptions::new().write(true).create_new(true).open(&tmp)?;
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
            "Fs.is_dir" => V::Bool(std::path::Path::new(&full).is_dir()),
            "Fs.rename" => {
                let to = arg(2);
                match fs_path(root, *attenuated, &to) {
                    None => self.io_err("Denied", format!("path escapes the Fs root: {}", to)),
                    Some(full_to) => self.io_result(&p, std::fs::rename(&full, &full_to), |_| V::Unit),
                }
            }
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
// None if the path escapes the capability: a NUL byte (C would truncate), or,
// for an attenuated Fs, an absolute path, a `..` component, or an existing
// symlink on the way (checked component by component; a concurrent change
// between this check and the use is not prevented).
pub fn fs_path(root: &str, attenuated: bool, p: &str) -> Option<String> {
    if p.contains('\0') {
        return None;
    }
    if attenuated && (p.is_empty() || p.starts_with('/') || p.split('/').any(|c| c == "..")) {
        return None;
    }
    if attenuated {
        let mut cur = root.to_string();
        for comp in p.split('/').filter(|c| !c.is_empty() && *c != ".") {
            cur = format!("{}/{}", cur, comp);
            match std::fs::symlink_metadata(&cur) {
                Ok(m) if m.file_type().is_symlink() => return None,
                Ok(_) => {}
                Err(_) => break,
            }
        }
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

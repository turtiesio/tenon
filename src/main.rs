// tenon: bootstrap compiler and reference interpreter for the Tenon language.

mod ast;
mod check;
mod diag;
mod emit_body;
mod emit_c;
mod exhaust;
mod interp;
mod lexer;
mod linear;
mod parser;
mod testrun;
mod types;
mod value;

use diag::SourceMap;
use std::process::exit;

const PRELUDE: &str = include_str!("prelude.tn");

fn usage() -> ! {
    eprintln!(
        "usage:\n  tenon run FILE.tn [ARGS...]     interpret (reference semantics)\n  \
         tenon build FILE.tn [-o OUT]    compile to a native executable via C\n  \
         tenon emit FILE.tn              print the generated C\n  \
         tenon check FILE.tn             type-check only\n  \
         tenon test DIR... [--bless]     run the differential test corpus"
    );
    exit(2)
}

// Standard library modules, embedded so the compiler is a single file.
const STD: &[(&str, &str)] = &[("journal", include_str!("../std/journal.tn"))];

// Load the program: prelude, the main file, then every imported module
// (from the importing file's directory, else the standard library).
pub fn front(path: &str) -> (check::Checked, SourceMap) {
    let src = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("tenon: cannot read {}: {}", path, e);
            exit(2)
        }
    };
    let mut sm = SourceMap { files: vec![("<prelude>".into(), PRELUDE.into()), (path.into(), src)] };
    let mut prog = ast::Program { structs: vec![], enums: vec![], fns: vec![], imports: vec![], modules: vec![String::new(), String::new()] };
    let mut next_id = 0;
    let mut i = 0;
    while i < sm.files.len() {
        let text = sm.files[i].1.clone();
        let r = lexer::lex(&text, i as u16).and_then(|t| parser::parse_program(&t, &mut next_id, &mut prog));
        if let Err(d) = r {
            eprintln!("{}", sm.render(&d));
            exit(1)
        }
        let imports: Vec<ast::Import> = prog.imports.iter().filter(|im| im.file == i as u16).cloned().collect();
        for im in imports {
            if prog.modules.contains(&im.name) {
                continue;
            }
            let dir = std::path::Path::new(&sm.files[i].0).parent().map(|p| p.to_path_buf()).unwrap_or_default();
            let local = dir.join(format!("{}.tn", im.name));
            let found = match std::fs::read_to_string(&local) {
                Ok(t) => Some((local.to_string_lossy().into_owned(), t)),
                Err(_) => STD.iter().find(|(n, _)| *n == im.name).map(|(n, t)| (format!("<std>/{}.tn", n), t.to_string())),
            };
            let Some(f) = found else {
                let d = diag::Diag::new(im.span, &format!("cannot find module '{}' ({} or the standard library)", im.name, local.display()));
                eprintln!("{}", sm.render(&d));
                exit(1)
            };
            sm.files.push(f);
            prog.modules.push(im.name.clone());
        }
        i += 1;
    }
    match check::check(prog) {
        Ok(c) => (c, sm),
        Err(d) => {
            eprintln!("{}", sm.render(&d));
            exit(1)
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        usage()
    }
    let (cmd, file) = (args[1].as_str(), args[2].as_str());
    match cmd {
        "test" => exit(testrun::main(&args[2..])),
        "check" => {
            front(file);
        }
        "run" => {
            let (c, sm) = front(file);
            let rest = args[3..].to_vec();
            // Deep recursion needs a big stack; the depth limit stops it first.
            let code = std::thread::Builder::new()
                .stack_size(1 << 30)
                .spawn(move || interp::run(&c, &sm, rest))
                .unwrap()
                .join()
                .unwrap_or(101);
            exit(code)
        }
        "emit" => {
            let (c, sm) = front(file);
            print!("{}", emit_c::emit(&c, &sm));
        }
        "build" => {
            let (c, sm) = front(file);
            let out = match args.iter().position(|a| a == "-o") {
                Some(i) if i + 1 < args.len() => args[i + 1].clone(),
                _ => file.trim_end_matches(".tn").to_string(),
            };
            let opt = if args.iter().any(|a| a == "-O0") { "-O0" } else { "-O2" };
            if let Err(e) = emit_c::build(&c, &sm, &out, opt) {
                eprintln!("tenon: {}", e);
                exit(1)
            }
        }
        _ => usage(),
    }
}

// Test runner (`tenon test DIR...`): the contract a landing must pass.
//
//   DIR/run/NAME.tn      run with the interpreter AND the C backend; both must
//                        match NAME.out (stdout + "exit: N" + stderr lines)
//   DIR/reject/NAME.tn   must fail to compile; first line `// error: TEXT`
//                        names a substring of the expected diagnostic
//
// Optional first-line directives in run tests: `// stdin: TEXT` (\n escapes,
// and \xHH for any byte, so stdin can be invalid UTF-8) and `// args: A B C`.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::time::Instant;

struct Outcome {
    stdout: String,
    stderr: String,
    code: i32,
}

const TIMEOUT_SECS: u64 = 20;

// Run with stdin, capturing output; the whole process is killed on timeout.
fn run_cmd(cmd: &mut Command, stdin: &[u8]) -> Outcome {
    let mut child = cmd
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn");
    let mut si = child.stdin.take().unwrap();
    let input = stdin.to_vec();
    let w = std::thread::spawn(move || {
        use std::io::Write;
        let _ = si.write_all(&input);
    });
    let mut so = child.stdout.take().unwrap();
    let mut se = child.stderr.take().unwrap();
    let ro = std::thread::spawn(move || {
        let mut v = Vec::new();
        let _ = std::io::Read::read_to_end(&mut so, &mut v);
        v
    });
    let re = std::thread::spawn(move || {
        let mut v = Vec::new();
        let _ = std::io::Read::read_to_end(&mut se, &mut v);
        v
    });
    let deadline = Instant::now() + std::time::Duration::from_secs(TIMEOUT_SECS);
    let mut timed_out = false;
    let status = loop {
        if let Some(st) = child.try_wait().expect("wait") {
            break st;
        }
        if Instant::now() > deadline {
            let _ = child.kill();
            timed_out = true;
            break child.wait().expect("wait");
        }
        std::thread::sleep(std::time::Duration::from_millis(2));
    };
    let _ = w.join();
    let stdout = ro.join().unwrap_or_default();
    let mut stderr = String::from_utf8_lossy(&re.join().unwrap_or_default()).into_owned();
    if timed_out {
        stderr.push_str(&format!("<killed after {}s>\n", TIMEOUT_SECS));
    }
    Outcome {
        stdout: String::from_utf8_lossy(&stdout).into_owned(),
        stderr,
        code: status.code().unwrap_or(-1),
    }
}

fn render(o: &Outcome) -> String {
    let mut s = o.stdout.clone();
    if !s.is_empty() && !s.ends_with('\n') {
        s.push_str("\n<no newline>\n");
    }
    s.push_str(&format!("exit: {}\n", o.code));
    for l in o.stderr.lines() {
        s.push_str(&format!("stderr: {}\n", l));
    }
    s
}

fn directive(src: &str, key: &str) -> Option<String> {
    for l in src.lines().take(3) {
        if let Some(rest) = l.strip_prefix(&format!("// {}:", key)) {
            return Some(rest.trim().replace("\\n", "\n"));
        }
    }
    None
}

// "\xHH" (two hex digits) is that byte; everything else is kept as is.
fn hex_escapes(s: &str) -> Vec<u8> {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'\\' && i + 4 <= b.len() && b[i + 1] == b'x' {
            if let Some(v) = std::str::from_utf8(&b[i + 2..i + 4]).ok().and_then(|h| u8::from_str_radix(h, 16).ok()) {
                out.push(v);
                i += 4;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    out
}

// Test programs; files whose first line is `// module` are imported by tests, not run.
fn files(dir: &Path) -> Vec<PathBuf> {
    let is_module = |p: &Path| std::fs::read_to_string(p).map(|s| s.starts_with("// module")).unwrap_or(false);
    let mut v: Vec<PathBuf> = std::fs::read_dir(dir)
        .map(|rd| {
            rd.flatten().map(|e| e.path()).filter(|p| p.extension().map(|x| x == "tn").unwrap_or(false) && !is_module(p)).collect()
        })
        .unwrap_or_default();
    v.sort();
    v
}

fn check_run(exe: &Path, tn: &Path, tmp: &Path, bless: bool) -> Result<(), String> {
    let src = std::fs::read_to_string(tn).map_err(|e| e.to_string())?;
    let stdin = hex_escapes(&directive(&src, "stdin").unwrap_or_default());
    let args: Vec<String> = directive(&src, "args").map(|a| a.split_whitespace().map(String::from).collect()).unwrap_or_default();
    // Run from the test's directory with a bare file name, so that trap
    // locations in golden files do not depend on where the suite runs.
    let dir = tn.parent().unwrap();
    let name = tn.file_name().unwrap();
    let interp = run_cmd(Command::new(exe).arg("run").arg(name).args(&args).current_dir(dir), &stdin);
    let bin = tmp.join(tn.file_stem().unwrap());
    let build = run_cmd(Command::new(exe).arg("build").arg(name).arg("-o").arg(&bin).arg("-O0").current_dir(dir), b"");
    if build.code != 0 {
        return Err(format!("C build failed:\n{}{}", build.stdout, build.stderr));
    }
    let native = run_cmd(Command::new(&bin).args(&args).current_dir(dir), &stdin);
    let _ = std::fs::remove_file(&bin);
    let (ri, rn) = (render(&interp), render(&native));
    if ri != rn {
        return Err(format!("backends disagree\n--- interpreter\n{}--- C\n{}", ri, rn));
    }
    let golden = tn.with_extension("out");
    match std::fs::read_to_string(&golden) {
        Ok(g) if g == ri => Ok(()),
        _ if bless => std::fs::write(&golden, &ri).map_err(|e| e.to_string()),
        Ok(g) => Err(format!("output differs from {}\n--- expected\n{}--- got\n{}", golden.display(), g, ri)),
        Err(_) => Err(format!("missing {} (run `tenon test --bless`)\n--- got\n{}", golden.display(), ri)),
    }
}

fn check_reject(exe: &Path, tn: &Path) -> Result<(), String> {
    let src = std::fs::read_to_string(tn).map_err(|e| e.to_string())?;
    let want = directive(&src, "error").ok_or("reject test needs a first line `// error: TEXT`")?;
    let o = run_cmd(Command::new(exe).arg("check").arg(tn.file_name().unwrap()).current_dir(tn.parent().unwrap()), b"");
    if o.code == 0 {
        return Err("compiled, but must be rejected".into());
    }
    if !o.stderr.contains(&want) {
        return Err(format!("expected an error containing {:?}, got:\n{}", want, o.stderr));
    }
    Ok(())
}

pub fn main(args: &[String]) -> i32 {
    let start = Instant::now();
    let bless = args.iter().any(|a| a == "--bless");
    let dirs: Vec<&String> = args.iter().filter(|a| !a.starts_with("--")).collect();
    let exe = std::env::current_exe().unwrap();
    let tmp = std::env::temp_dir().join(format!("tenon-test-{}", std::process::id()));
    let tmp = std::fs::canonicalize(std::env::temp_dir()).unwrap_or(tmp.clone()).join(tmp.file_name().unwrap());
    std::fs::create_dir_all(&tmp).unwrap();
    let mut jobs: Vec<(bool, PathBuf)> = Vec::new();
    for d in &dirs {
        let d = Path::new(d);
        jobs.extend(files(&d.join("run")).into_iter().map(|p| (true, p)));
        jobs.extend(files(&d.join("reject")).into_iter().map(|p| (false, p)));
    }
    let next = AtomicUsize::new(0);
    let failures: Mutex<Vec<(PathBuf, String)>> = Mutex::new(Vec::new());
    let workers = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4).min(8);
    std::thread::scope(|s| {
        for _ in 0..workers {
            s.spawn(|| loop {
                let i = next.fetch_add(1, Ordering::SeqCst);
                let Some((is_run, p)) = jobs.get(i) else { break };
                let r = if *is_run { check_run(&exe, p, &tmp, bless) } else { check_reject(&exe, p) };
                if let Err(e) = r {
                    failures.lock().unwrap().push((p.clone(), e));
                }
            });
        }
    });
    let _ = std::fs::remove_dir_all(&tmp);
    let failures = failures.into_inner().unwrap();
    for (p, e) in &failures {
        println!("FAIL {}\n{}\n", p.display(), e);
    }
    let runs = jobs.iter().filter(|j| j.0).count();
    println!(
        "tests: {} run (x2 backends), {} reject, {} failed, {:.1}s",
        runs,
        jobs.len() - runs,
        failures.len(),
        start.elapsed().as_secs_f64()
    );
    if failures.is_empty() { 0 } else { 1 }
}

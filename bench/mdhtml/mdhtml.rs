// mdhtml: Markdown subset to HTML, stdin to stdout (std only).
use std::io::{Read, Write};

fn is_space(b: u8) -> bool { b == b' ' || b == b'\t' || b == b'\n' || b == b'\r' }

fn trim(s: &str) -> &str { s.trim_matches(|c: char| c.is_ascii_whitespace()) }

fn esc(out: &mut String, s: &str) {
    let mut run = 0;
    for (i, b) in s.bytes().enumerate() {
        let rep = match b {
            b'&' => "&amp;",
            b'<' => "&lt;",
            b'>' => "&gt;",
            b'"' => "&quot;",
            _ => continue,
        };
        out.push_str(&s[run..i]);
        out.push_str(rep);
        run = i + 1;
    }
    out.push_str(&s[run..]);
}

// ---- inline ----

// Each matcher returns the construct's inner end and where scanning resumes.
fn code_span(s: &[u8], i: usize) -> Option<usize> {
    let n = s.len();
    let mut j = i + 1;
    while j < n && s[j] != b'`' { j += 1; }
    if j >= n || j == i + 1 { return None; }
    Some(j)
}

fn bold(s: &[u8], i: usize) -> Option<usize> {
    let n = s.len();
    let start = i + 2;
    if start >= n || is_space(s[start]) { return None; }
    let mut j = start + 1;
    while j + 1 < n {
        if s[j] == b'*' && s[j + 1] == b'*' && !is_space(s[j - 1]) {
            while j + 2 < n && s[j + 2] == b'*' { j += 1; }
            return Some(j);
        }
        j += 1;
    }
    None
}

fn em(s: &[u8], i: usize) -> Option<usize> {
    let n = s.len();
    let start = i + 1;
    if start >= n || is_space(s[start]) { return None; }
    let mut j = start + 1;
    while j < n {
        if s[j] == b'*' {
            if j + 1 < n && s[j + 1] == b'*' {
                j += 2;
                continue;
            }
            if !is_space(s[j - 1]) { return Some(j); }
        }
        j += 1;
    }
    None
}

// Returns (index of "]", index of the closing ")").
fn link(s: &[u8], i: usize) -> Option<(usize, usize)> {
    let n = s.len();
    let mut j = i + 1;
    while j < n && s[j] != b']' { j += 1; }
    if j == i + 1 || j + 1 >= n || s[j + 1] != b'(' { return None; }
    let mut k = j + 2;
    while k < n && s[k] != b')' && !is_space(s[k]) { k += 1; }
    if k >= n || k == j + 2 || s[k] != b')' { return None; }
    Some((j, k))
}

fn try_inline(s: &[u8], i: usize) -> Option<(u8, usize, usize)> {
    match s[i] {
        b'`' => code_span(s, i).map(|j| (b'`', j, j + 1)),
        b'[' => link(s, i).map(|(j, k)| (b'[', j, k + 1)),
        b'*' if i + 1 < s.len() && s[i + 1] == b'*' => bold(s, i).map(|j| (b'B', j, j + 2)),
        b'*' => em(s, i).map(|j| (b'*', j, j + 1)),
        _ => None,
    }
}

fn inline(out: &mut String, text: &str) {
    let s = text.as_bytes();
    let n = s.len();
    let mut run = 0;
    let mut i = 0;
    while i < n {
        let Some((kind, j, stop)) = try_inline(s, i) else {
            // an unclosed "**" is literal as a pair
            i += if s[i] == b'*' && i + 1 < n && s[i + 1] == b'*' { 2 } else { 1 };
            continue;
        };
        esc(out, &text[run..i]);
        match kind {
            b'`' => {
                out.push_str("<code>");
                esc(out, &text[i + 1..j]);
                out.push_str("</code>");
            }
            b'[' => {
                out.push_str("<a href=\"");
                esc(out, &text[j + 2..stop - 1]);
                out.push_str("\">");
                inline(out, &text[i + 1..j]);
                out.push_str("</a>");
            }
            b'B' => {
                out.push_str("<strong>");
                inline(out, &text[i + 2..j]);
                out.push_str("</strong>");
            }
            _ => {
                out.push_str("<em>");
                inline(out, &text[i + 1..j]);
                out.push_str("</em>");
            }
        }
        i = stop;
        run = stop;
    }
    esc(out, &text[run..]);
}

// ---- blocks ----

fn heading_level(line: &str) -> usize {
    let b = line.as_bytes();
    let mut k = 0;
    while k < b.len() && b[k] == b'#' { k += 1; }
    if (1..=6).contains(&k) && (k == b.len() || b[k] == b' ') { k } else { 0 }
}

// (kind, marker length); kind 0 = not an item, 1 = bullet, 2 = ordered
fn item_marker(line: &str) -> (u8, usize) {
    if line.starts_with("- ") || line.starts_with("* ") { return (1, 2); }
    let b = line.as_bytes();
    let mut k = 0;
    while k < b.len() && b[k].is_ascii_digit() { k += 1; }
    if k >= 1 && k + 1 < b.len() && b[k] == b'.' && b[k + 1] == b' ' { return (2, k + 2); }
    (0, 0)
}

fn is_fence(line: &str) -> bool {
    line.starts_with("```") && !line[3..].contains('`')
}

fn starts_block(line: &str) -> bool {
    is_fence(line) || heading_level(line) > 0 || line == "---" || line.starts_with('>') || item_marker(line).0 > 0
}

fn render(out: &mut String, lines: &[&str]) {
    let n = lines.len();
    let mut i = 0;
    while i < n {
        let line = trim(lines[i]);
        if line.is_empty() {
            i += 1;
        } else if is_fence(line) {
            let lang = trim(&line[3..]).split(' ').next().unwrap();
            i += 1;
            out.push_str("<pre><code");
            if !lang.is_empty() {
                out.push_str(" class=\"language-");
                esc(out, lang);
                out.push('"');
            }
            out.push('>');
            while i < n && trim(lines[i]) != "```" {
                esc(out, lines[i]);
                out.push('\n');
                i += 1;
            }
            if i < n { i += 1; }
            out.push_str("</code></pre>\n");
        } else if heading_level(line) > 0 {
            let lvl = heading_level(line);
            out.push_str(&format!("<h{}>", lvl));
            inline(out, trim(&line[lvl..]));
            out.push_str(&format!("</h{}>\n", lvl));
            i += 1;
        } else if line == "---" {
            out.push_str("<hr>\n");
            i += 1;
        } else if line.starts_with('>') {
            let mut inner: Vec<&str> = Vec::new();
            while i < n && trim(lines[i]).starts_with('>') {
                let rest = &trim(lines[i])[1..];
                inner.push(rest.strip_prefix(' ').unwrap_or(rest));
                i += 1;
            }
            out.push_str("<blockquote>\n");
            render(out, &inner);
            out.push_str("</blockquote>\n");
        } else if item_marker(line).0 > 0 {
            let kind = item_marker(line).0;
            let tag = if kind == 1 { "ul" } else { "ol" };
            out.push_str(&format!("<{}>\n", tag));
            while i < n {
                let t = trim(lines[i]);
                let (k, m) = item_marker(t);
                if k != kind { break; }
                out.push_str("<li>");
                inline(out, trim(&t[m..]));
                out.push_str("</li>\n");
                i += 1;
            }
            out.push_str(&format!("</{}>\n", tag));
        } else {
            let mut parts: Vec<&str> = vec![line];
            i += 1;
            while i < n {
                let t = trim(lines[i]);
                if t.is_empty() || starts_block(t) { break; }
                parts.push(t);
                i += 1;
            }
            out.push_str("<p>");
            inline(out, &parts.join("\n"));
            out.push_str("</p>\n");
        }
    }
}

fn main() {
    let mut text = String::new();
    std::io::stdin().read_to_string(&mut text).unwrap();
    let mut lines: Vec<&str> = text.split('\n').collect();
    if lines.last() == Some(&"") { lines.pop(); }
    let lines: Vec<&str> = lines.into_iter().map(|l| l.strip_suffix('\r').unwrap_or(l)).collect();
    let mut out = String::new();
    render(&mut out, &lines);
    std::io::stdout().write_all(out.as_bytes()).unwrap();
}

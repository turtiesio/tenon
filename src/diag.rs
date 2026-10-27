// Diagnostics and source locations shared by every stage.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Default)]
pub struct Span {
    pub file: u16,
    pub line: u32,
    pub col: u32,
}

#[derive(Debug, Clone)]
pub struct Diag {
    pub span: Span,
    pub msg: String,
}

impl Diag {
    pub fn new(span: Span, msg: &str) -> Diag {
        Diag { span, msg: msg.to_string() }
    }
}

pub struct SourceMap {
    pub files: Vec<(String, String)>, // (name, text)
}

impl SourceMap {
    pub fn name(&self, sp: Span) -> &str {
        &self.files[sp.file as usize].0
    }
    pub fn loc(&self, sp: Span) -> String {
        format!("{}:{}:{}", self.name(sp), sp.line, sp.col)
    }
    pub fn render(&self, d: &Diag) -> String {
        let (name, text) = &self.files[d.span.file as usize];
        let line = text.lines().nth(d.span.line.saturating_sub(1) as usize).unwrap_or("");
        let caret = " ".repeat(d.span.col.saturating_sub(1) as usize);
        format!(
            "{}:{}:{}: error: {}\n  {}\n  {}^",
            name, d.span.line, d.span.col, d.msg, line, caret
        )
    }
}

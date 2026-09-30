import { Component, computed, input } from "@angular/core";

interface HighlightedLine {
  number: number;
  html: string;
}

const KEYWORDS: Record<string, string[]> = {
  python: [
    "def", "class", "return", "if", "elif", "else", "for", "while", "in",
    "import", "from", "as", "try", "except", "finally", "raise", "with",
    "lambda", "pass", "yield", "async", "await", "not", "and", "or", "is",
    "None", "True", "False", "self", "global", "nonlocal", "assert", "del",
  ],
  java: [
    "public", "private", "protected", "class", "interface", "extends",
    "implements", "return", "if", "else", "for", "while", "new", "static",
    "final", "void", "int", "long", "double", "float", "boolean", "String",
    "try", "catch", "finally", "throw", "throws", "import", "package",
    "this", "super", "null", "true", "false", "abstract", "enum", "record",
  ],
  javascript: [
    "function", "return", "if", "else", "for", "while", "const", "let",
    "var", "new", "class", "extends", "import", "export", "from", "default",
    "try", "catch", "finally", "throw", "async", "await", "yield", "typeof",
    "instanceof", "this", "null", "undefined", "true", "false", "of", "in",
  ],
  typescript: [
    "function", "return", "if", "else", "for", "while", "const", "let",
    "var", "new", "class", "extends", "implements", "import", "export",
    "from", "default", "try", "catch", "finally", "throw", "async", "await",
    "yield", "typeof", "instanceof", "this", "null", "undefined", "true",
    "false", "of", "in", "interface", "type", "enum", "readonly", "private",
    "public", "protected", "abstract", "as", "string", "number", "boolean",
  ],
  sql: [
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON", "AND", "OR",
    "NOT", "NULL", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET",
    "CREATE", "TABLE", "ALTER", "DROP", "INDEX", "AS", "DISTINCT", "UNION",
  ],
};

const COMMENT_PATTERNS: Record<string, RegExp> = {
  python: /(#.*)$/,
  java: /(\/\/.*)$/,
  javascript: /(\/\/.*)$/,
  typescript: /(\/\/.*)$/,
  sql: /(--.*)$/,
};

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Podświetla pojedynczą (już HTML-escapowaną) linię kodu. Kolejność:
 * komentarz → string → liczba → keyword. Prosty tokenizer bez zewnętrznych
 * bibliotek (brak PrismJS/Monaco w zależnościach projektu).
 */
export function highlightLine(rawLine: string, language: string): string {
  const escaped = escapeHtml(rawLine);
  const lang = KEYWORDS[language] ? language : "python";

  // Split off trailing comment (naive, ignores strings containing markers).
  let codePart = escaped;
  let commentPart = "";
  const commentMatch = COMMENT_PATTERNS[lang].exec(escaped);
  if (commentMatch && commentMatch.index >= 0) {
    codePart = escaped.slice(0, commentMatch.index);
    commentPart = `<span class="tok-comment">${commentMatch[1]}</span>`;
  }

  // Strings (single/double quoted).
  codePart = codePart.replace(
    /(&quot;.*?&quot;|'[^']*')/g,
    '<span class="tok-string">$1</span>',
  );
  // Numbers — avoid replacing inside already-inserted span tags.
  codePart = codePart.replace(
    /\b(\d+(?:\.\d+)?)\b(?![^<]*<\/span>)/g,
    '<span class="tok-number">$1</span>',
  );
  // Keywords.
  const kwPattern = new RegExp(
    `\\b(${KEYWORDS[lang].join("|")})\\b(?![^<]*</span>)`,
    lang === "sql" ? "gi" : "g",
  );
  codePart = codePart.replace(
    kwPattern,
    '<span class="tok-keyword">$1</span>',
  );

  return codePart + commentPart;
}

/**
 * AC5 — podświetlanie składni fragmentów kodu (Python, Java, JS, TS, SQL)
 * z numeracją linii. Wejście jest HTML-escapowane przed tokenizacją, więc
 * [innerHTML] otrzymuje wyłącznie nasze własne znaczniki <span>.
 */
@Component({
  selector: "app-code-highlighter",
  standalone: true,
  imports: [],
  templateUrl: "./code-highlighter.component.html",
  styleUrls: ["./code-highlighter.component.scss"],
})
export class CodeHighlighterComponent {
  readonly code = input<string>("");
  readonly language = input<string>("python");
  readonly startLine = input<number>(1);

  readonly lines = computed<HighlightedLine[]>(() => {
    const lang = (this.language() || "python").toLowerCase();
    const start = this.startLine();
    return (this.code() ?? "")
      .replace(/\r\n/g, "\n")
      .split("\n")
      .map((line, i) => ({
        number: start + i,
        html: highlightLine(line, lang),
      }));
  });
}

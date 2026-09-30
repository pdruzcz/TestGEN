# Katalog reguł — definicje taint (sources / sinks / sanitizers)

Pliki: `app/services/security_scan/taint_definitions/`

## Struktury bazowe (`base.py`)

- **TaintSource** — `name`, `patterns`, `language`, `taint_type` ∈
  {user_input, file_input, env_input}.
- **TaintSink** — `name`, `patterns`, `language`, `sink_type` ∈
  {sql, html, exec, file, log}, `vulnerability_type`, `cwe_id`, `severity`.
- **TaintSanitizer** — `name`, `patterns`, `language`, `protects_against`
  (frozenset typów sinków), metoda `protects(sink_type)`.

Domyślna severity sinka (`SINK_SEVERITY`): exec→critical, sql→high,
html→medium, file→medium, log→low.

## Python

| Kategoria | Pozycje |
|---|---|
| Sources | `request.(GET\|POST\|args\|form\|...)`, `input()`, `sys.argv`, `os.environ`/`os.getenv`, `.read()`/`.readline()` |
| Sinks | `.execute()`/`.executemany()` (sql), `os.system`/`subprocess.*` (exec), `eval`/`exec` (exec), `render_template_string`/`Markup` (html), `open()` (file) |
| Sanitizers | `html.escape`/`escape`→{html}, `bleach.clean`→{html}, `int`/`float`→{sql,exec,file}, `shlex.quote`→{exec} |

## JavaScript / TypeScript

| Kategoria | Pozycje |
|---|---|
| Sources | `req.(body\|params\|query\|...)`, `location.(hash\|search\|href)`/`document.cookie`/`window.name`, `process.env.` |
| Sinks | `.query`/`.execute` (sql), `.innerHTML=`/`.outerHTML=`/`document.write` (html), `eval`/`new Function` (exec), `child_process.exec`/`exec` (exec) |
| Sanitizers | `DOMPurify.sanitize`→{html}, `escapeHtml`/`escape`→{html}, `parseInt`/`Number`→{sql,exec,html} |

## Java

| Kategoria | Pozycje |
|---|---|
| Sources | `request.getParameter`/`getHeader`/`getQueryString`, `@RequestParam`/`@PathVariable`, `System.getenv` |
| Sinks | `.execute(Query\|Update)?`/`createStatement` (sql), `Runtime.getRuntime().exec`/`new ProcessBuilder` (exec), `.getWriter().(print\|write)`/`.println` (html) |
| Sanitizers | `prepareStatement`/`setString`→{sql}, `ESAPI.encoder()`/`Encode.forHtml`→{html}, `Integer.parseInt`/`Long.parseLong`→{sql,exec,html} |

## C#

| Kategoria | Pozycje |
|---|---|
| Sources | `Request.(Form\|QueryString\|...)`/`Request["..."]`, `ModelState`, `Environment.GetEnvironmentVariable` |
| Sinks | `new SqlCommand`/`.ExecuteReader`/`.ExecuteNonQuery` (sql), `Process.Start` (exec), `Response.Write` (html) |
| Sanitizers | `new SqlParameter`/`.Parameters.Add`→{sql}, `HtmlEncode`/`HttpUtility.HtmlEncode`→{html}, `int.Parse`/`Convert.ToInt32`→{sql,exec,html} |

## C / C++

| Kategoria | Pozycje |
|---|---|
| Sources | `argv[`/`argc`, `fgets`/`scanf`/`gets`, `getenv` |
| Sinks | `system`/`popen`/`execvp?` (exec), `sprintf`/`strcpy`/`strcat` (buffer_overflow, CWE-120), `fopen`/`open` (file) |
| Sanitizers | `snprintf`/`strncpy`/`strncat`→{exec}, `atoi`/`strtol`→{exec,file} |

## Adekwatność sanitizera

Sanitizer chroni wyłącznie przed sinkami z `protects_against`. Np.
`html.escape` NIE chroni przed sinkiem `sql` — taka ścieżka jest flagowana z
`sanitizer_adequate = False` (patrz [taint analyzer](../01-architektura/03-taint-analyzer.md)).

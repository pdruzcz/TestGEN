"""Anonymization of client code before cloud (LLM) analysis — Story 1.54, FR72.

Masks sensitive fragments (secrets, URLs, e-mails, IPs/IBANs, string literals
and domain-revealing identifier names) before the payload is sent to the LLM
provider, and detokenizes the LLM output afterwards.  Only token *values* are
replaced — placeholders are valid identifiers, so the syntactic structure
(AST, dependencies, control flow) is preserved and analysis quality does not
degrade.

Detection is dual-path (Story 1.11):
- native  — deterministic regexes; secret patterns are REUSED from
  ``security_scan/rules/secrets_rules.py`` (Story 4.2) without modification;
- llm     — contextual recognition of domain-revealing names (e.g.
  ``CustomerSSNValidator``) with a per-token confidence; below the threshold
  the name is left in place to avoid over-anonymization.

The mapping (placeholder → original) is per-analysis, must never be sent to
the LLM and is persisted encrypted (AES-256-GCM, per-tenant key) by the
pipeline integration — see ``AnonymizationMap``.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.core.config import get_settings
from app.services.security_scan.rules.secrets_rules import SECRETS_RULES

logger = logging.getLogger(__name__)

# --- native detection patterns ------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IP_RE = re.compile(rf"\b{_OCTET}(?:\.{_OCTET}){{3}}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
# Bare high-entropy literal inside quotes (no spaces, >=16 chars, letters+digits).
_STR_LIKE_RE = re.compile(r"([\"'])([A-Za-z0-9+/_=-]{16,})\1")
_QUOTED_IN_MATCH_RE = re.compile(r"[\"']([^\"'\s]{6,})[\"']")
# Domain-revealing identifier segments (high precision — keep tight).
# Segment = słowo po rozbiciu snake_case/camelCase, więc keywordy muszą być
# pojedynczymi słowami ("accountnumber" nigdy nie powstanie jako segment).
_DOMAIN_KEYWORDS = frozenset(
    {
        "ssn",
        "pesel",
        "nip",
        "regon",
        "kyc",
        "cvv",
        "cvc",
        "iban",
        "pan",
        "account",
        "card",
        "tax",
    }
)
# Split identifiers into word segments: snake_case + camelCase/PascalCase.
_CAMEL_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")
_ACRONYM_BOUNDARY_RE = re.compile(r"([A-Z])([A-Z][a-z])")


def _identifier_segments(name: str) -> set[str]:
    spaced = _CAMEL_BOUNDARY_RE.sub(r"\1 \2", name.replace("_", " "))
    spaced = _ACRONYM_BOUNDARY_RE.sub(r"\1 \2", spaced)
    return {seg.lower() for seg in spaced.split() if seg}


# Generic identifier fallback when no AST tree is available (LLM detection input).
_WORD_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")

_LLM_DETECTION_PROMPT = (
    "Poniżej lista identyfikatorów z kodu klienta. Wskaż wyłącznie te nazwy, "
    "które zdradzają wrażliwą domenę biznesową klienta lub dane osobowe "
    "(np. dane finansowe, identyfikatory podatkowe, sekrety płatności). "
    'Zwróć WYŁĄCZNIE czysty JSON: [{"name": "...", "confidence": 0.0-1.0}]. '
    "Nie dodawaj żadnego tekstu poza JSON.\n\nIdentyfikatory:\n{names}"
)


class TokenKind(StrEnum):
    """Kinds of sensitive tokens subject to anonymization."""

    IDENT = "ident"  # nazwy klas/metod/zmiennych → IDENT_n (parseable)
    STR = "str"  # literały stringowe → <STR_n>
    URL = "url"  # URL-e → <URL_n>
    EMAIL = "email"  # adresy email → <EMAIL_n>
    IP_ACCOUNT = "ip_acc"  # IP / numery kont → <ACC_n>
    SECRET = "secret"  # klucze API, tokeny, hasła → <SECRET_n>


@dataclass(frozen=True)
class SensitiveToken:
    """One detected sensitive fragment of the source."""

    kind: TokenKind
    value: str
    confidence: float = 1.0
    source: str = "native"  # native | llm


@dataclass
class AnonymizationResult:
    """Outcome of one ``anonymize`` run (single source text)."""

    source: str
    mapping: dict[str, str] = field(default_factory=dict)
    token_count: int = 0
    secret_count: int = 0


def _placeholder(kind: TokenKind, number: int) -> str:
    """IDENT placeholders stay valid identifiers so the payload still parses."""
    if kind is TokenKind.IDENT:
        return f"IDENT_{number:03d}"
    tag = {"str": "STR", "url": "URL", "email": "EMAIL", "ip_acc": "ACC", "secret": "SECRET"}[kind.value]
    return f"<{tag}_{number:03d}>"


def _secret_value(match: re.Match) -> str:
    """Extract the sensitive VALUE from a secrets-rule match.

    The hardcoded-assignment rule matches ``api_key = "sk-..."`` — the value
    is the quoted literal (quotes stay in place so the code keeps parsing).
    Key/JWT/PEM rules match the bare secret itself.
    """
    quoted = _QUOTED_IN_MATCH_RE.search(match.group(0))
    return quoted.group(1) if quoted else match.group(0)


class AnonymizationService:
    """Tokenizuje wrażliwe identyfikatory przed LLM, detokenizuje wynik (FR72)."""

    def __init__(self, llm_gateway=None, confidence_threshold: float | None = None):
        self._llm_gateway = llm_gateway
        settings = get_settings()
        self._threshold = (
            confidence_threshold if confidence_threshold is not None else settings.anonymization_confidence_threshold
        )
        # Per-instance counters/mapping: one service per analysis run keeps
        # placeholders unique across all files of that run.
        self._counters: dict[TokenKind, int] = {}
        self.mapping: dict[str, str] = {}

    # ── public API ────────────────────────────────────────────────────────────

    async def anonymize(
        self,
        source: str,
        ast_tree=None,
        use_llm_detection: bool = False,
    ) -> tuple[str, dict[str, str]]:
        """Zwraca (zanonimizowany payload, mapping). Struktura AST zachowana."""
        tokens = await self.detect(source, ast_tree=ast_tree, use_llm_detection=use_llm_detection)
        return self._apply(source, tokens)

    async def anonymize_with_stats(
        self,
        source: str,
        ast_tree=None,
        use_llm_detection: bool = False,
    ) -> AnonymizationResult:
        """Anonymize + counts for the audit log (liczby, bez wartości)."""
        tokens = await self.detect(source, ast_tree=ast_tree, use_llm_detection=use_llm_detection)
        anonymized, mapping = self._apply(source, tokens)
        return AnonymizationResult(
            source=anonymized,
            mapping=mapping,
            token_count=len(mapping),
            secret_count=sum(1 for k in mapping if k.startswith("<SECRET_")),
        )

    async def deanonymize(self, llm_output: str, mapping: dict[str, str]) -> str:
        """Detokenizacja — placeholder → oryginał (spójna mapa per analiza)."""
        # Longest placeholder first: IDENT_010 must not clobber IDENT_001.
        for placeholder, original in sorted(mapping.items(), key=lambda x: -len(x[0])):
            llm_output = llm_output.replace(placeholder, original)
        return llm_output

    async def detect(
        self,
        source: str,
        ast_tree=None,
        use_llm_detection: bool = False,
    ) -> list[SensitiveToken]:
        """Detect sensitive fragments (dual-path: native + optional LLM)."""
        tokens: list[SensitiveToken] = []
        tokens.extend(self._detect_secrets(source))
        tokens.extend(self._detect_patterns(source))
        tokens.extend(self._detect_string_literals(source, tokens))
        native_identifiers = self._domain_identifiers(source, ast_tree)
        tokens.extend(SensitiveToken(TokenKind.IDENT, name) for name in native_identifiers)
        if use_llm_detection and self._llm_gateway is not None:
            tokens.extend(await self._detect_via_llm(source, native_identifiers))
        return self._dedupe(tokens)

    # ── native detection ──────────────────────────────────────────────────────

    def _detect_secrets(self, source: str) -> list[SensitiveToken]:
        """REUSE wzorców z secrets_rules (Story 4.2) — bez modyfikacji pliku."""
        tokens = []
        for rule in SECRETS_RULES:
            for pattern in rule.patterns:
                for match in pattern.regex.finditer(source):
                    tokens.append(SensitiveToken(TokenKind.SECRET, _secret_value(match)))
        return tokens

    def _detect_patterns(self, source: str) -> list[SensitiveToken]:
        tokens = []
        tokens += [SensitiveToken(TokenKind.URL, m.group(0)) for m in _URL_RE.finditer(source)]
        tokens += [SensitiveToken(TokenKind.EMAIL, m.group(0)) for m in _EMAIL_RE.finditer(source)]
        tokens += [SensitiveToken(TokenKind.IP_ACCOUNT, m.group(0)) for m in _IP_RE.finditer(source)]
        tokens += [SensitiveToken(TokenKind.IP_ACCOUNT, m.group(0)) for m in _IBAN_RE.finditer(source)]
        return tokens

    def _detect_string_literals(self, source: str, existing: list[SensitiveToken]) -> list[SensitiveToken]:
        """High-entropy string literals not already covered by other tokens."""
        covered = {t.value for t in existing}
        tokens = []
        for match in _STR_LIKE_RE.finditer(source):
            literal = match.group(2)
            if literal in covered or not (any(c.isalpha() for c in literal) and any(c.isdigit() for c in literal)):
                continue
            tokens.append(SensitiveToken(TokenKind.STR, literal))
        return tokens

    def _domain_identifiers(self, source: str, ast_tree) -> list[str]:
        """Domain-revealing identifier names (native heuristic over AST)."""
        names: list[str] = []
        if ast_tree is not None:
            for cls in getattr(ast_tree, "classes", []):
                names.append(cls.name)
                for method in getattr(cls, "methods", []):
                    names.append(method.name)
                    names.extend(p.name for p in getattr(method, "parameters", []))
            for func in getattr(ast_tree, "functions", []):
                names.append(func.name)
                names.extend(p.name for p in getattr(func, "parameters", []))
            names.extend(v.name for v in getattr(ast_tree, "variables", []))
        else:
            names = list(dict.fromkeys(_WORD_RE.findall(source)))
        return [n for n in dict.fromkeys(names) if _identifier_segments(n) & _DOMAIN_KEYWORDS]

    # ── LLM contextual detection (Story 1.26) ─────────────────────────────────

    async def _detect_via_llm(self, source: str, native_hits: list[str]) -> list[SensitiveToken]:
        """Kontekstowe rozpoznanie nazw domenowych — tylko lista NAZW do LLM."""
        from app.services.analysis.llm_gateway import LLMMessage, LLMProvider

        names = list(
            dict.fromkeys(
                _WORD_RE.findall(source)[:300]  # cap the payload
            )
        )
        if not names:
            return []
        prompt = _LLM_DETECTION_PROMPT.replace("{names}", "\n".join(names))
        try:
            response = await self._llm_gateway.complete(
                provider=LLMProvider.ANTHROPIC,
                messages=[LLMMessage(role="user", content=prompt)],
                max_tokens=2048,
                temperature=0.0,
                module="anonymization",
                task_type="domain_identifier_detection",
            )
            payload = json.loads(response.content)
        except Exception as exc:  # fail-open — brak detekcji, bez crasha
            logger.warning("LLM identifier detection failed (leaving names): %s", exc)
            return []

        tokens = []
        for item in payload if isinstance(payload, list) else []:
            name = str(item.get("name", ""))
            confidence = float(item.get("confidence", 0.0))
            if not name or name in native_hits:
                continue
            if confidence < self._threshold:
                # Poniżej progu → pozostawione (log), by nie psuć analizy.
                logger.info(
                    "Anonymization: identifier %r below confidence %.2f — left in place",
                    name,
                    confidence,
                )
                continue
            tokens.append(SensitiveToken(TokenKind.IDENT, name, confidence=confidence, source="llm"))
        return tokens

    # ── token application ─────────────────────────────────────────────────────

    @staticmethod
    def _dedupe(tokens: list[SensitiveToken]) -> list[SensitiveToken]:
        seen: set[tuple[TokenKind, str]] = set()
        unique = []
        for token in tokens:
            key = (token.kind, token.value)
            if key not in seen:
                seen.add(key)
                unique.append(token)
        return unique

    def _apply(self, source: str, tokens: list[SensitiveToken]) -> tuple[str, dict[str, str]]:
        """Assign placeholders and replace (longest originals first)."""
        assignments: list[tuple[SensitiveToken, str]] = []
        for token in tokens:
            self._counters[token.kind] = self._counters.get(token.kind, 0) + 1
            placeholder = _placeholder(token.kind, self._counters[token.kind])
            self.mapping[placeholder] = token.value
            assignments.append((token, placeholder))

        result = source
        for token, placeholder in sorted(assignments, key=lambda a: -len(a[0].value)):
            if token.kind is TokenKind.IDENT:
                # Word-boundary replace: never clobber a longer identifier.
                result = re.sub(rf"\b{re.escape(token.value)}\b", placeholder, result)
            else:
                result = result.replace(token.value, placeholder)

        # Drop placeholders that ended up unused (their span was consumed by a
        # longer token, e.g. an IP inside an already-masked URL).
        call_placeholders = {p for _, p in assignments}
        call_mapping = {p: self.mapping[p] for p in call_placeholders if p in result}
        for p in call_placeholders:
            if p not in result:
                del self.mapping[p]
        return result, call_mapping

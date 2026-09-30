"""Terraform (HCL) configuration scanner — Epic 4, Story 4.5.

Regex/line-based pass over ``*.tf`` files (no full HCL parser dependency).
Detects: public S3 buckets, fully-open security-group CIDRs, unencrypted
resources, missing logging and plaintext sensitive variables.
"""

import re

from app.services.security_scan.config_scanners.base import ConfigFinding

_RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
_VARIABLE_RE = re.compile(r'^\s*variable\s+"([^"]+)"\s*\{')


class TerraformScanner:
    config_type = "terraform"

    def scan(self, content: str, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        lines = content.splitlines()

        for idx, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            if re.search(r'acl\s*=\s*"public-(read|read-write)"', line):
                findings.append(
                    self._f(
                        "PUBLIC_S3_BUCKET", "high", idx, filename,
                        "Bucket S3 z publicznym ACL.",
                        "Ustaw ACL na 'private' i użyj polityk dostępu.",
                        'acl = "private"',
                        "public_resource", "CWE-732",
                    )
                )

            if re.search(r'cidr_blocks\s*=\s*\[\s*"0\.0\.0\.0/0"', line) or re.search(
                r'"0\.0\.0\.0/0"', line
            ):
                findings.append(
                    self._f(
                        "OPEN_SECURITY_GROUP", "critical", idx, filename,
                        "Reguła sieciowa otwarta na cały świat (0.0.0.0/0).",
                        "Ogranicz cidr_blocks do zaufanych zakresów IP.",
                        'cidr_blocks = ["10.0.0.0/16"]',
                        "open_security_group", "CWE-284",
                    )
                )

            if re.search(r'sensitive\s*=\s*false', line):
                findings.append(
                    self._f(
                        "PLAINTEXT_SECRET", "medium", idx, filename,
                        "Zmienna oznaczona jako sensitive = false.",
                        "Ustaw sensitive = true dla danych wrażliwych.",
                        "sensitive = true",
                        "plaintext_secret", "CWE-312",
                    )
                )

        # Resource-block level checks (encryption / logging absence).
        findings.extend(self._scan_blocks(content, filename))
        return findings

    def _scan_blocks(self, content: str, filename: str) -> list[ConfigFinding]:
        findings: list[ConfigFinding] = []
        lines = content.splitlines()
        i = 0
        n = len(lines)
        while i < n:
            m = _RESOURCE_RE.match(lines[i])
            if not m:
                i += 1
                continue
            res_type = m.group(1)
            start = i
            depth = lines[i].count("{") - lines[i].count("}")
            j = i + 1
            while j < n and depth > 0:
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            block = "\n".join(lines[start:j])

            encryptable = ("aws_s3_bucket", "aws_db_instance", "aws_ebs_volume")
            if res_type in encryptable and not re.search(
                r"(encrypt|server_side_encryption|kms_key)", block, re.IGNORECASE
            ):
                findings.append(
                    self._f(
                        "NO_ENCRYPTION", "high", start + 1, filename,
                        f"Zasób '{res_type}' bez konfiguracji szyfrowania.",
                        "Włącz szyfrowanie at-rest (np. server_side_encryption / storage_encrypted).",
                        "server_side_encryption_configuration { rule { apply_server_side_encryption_by_default { sse_algorithm = \"aws:kms\" } } }",
                        "no_encryption", "CWE-311",
                    )
                )

            loggable = ("aws_s3_bucket", "aws_cloudfront_distribution", "aws_lb")
            if res_type in loggable and not re.search(r"logging", block, re.IGNORECASE):
                findings.append(
                    self._f(
                        "NO_LOGGING", "medium", start + 1, filename,
                        f"Zasób '{res_type}' bez konfiguracji logowania.",
                        "Skonfiguruj logowanie dostępu dla audytu.",
                        "logging { target_bucket = aws_s3_bucket.logs.id }",
                        "no_logging", "CWE-778",
                    )
                )
            i = j
        return findings

    def _f(
        self, rule_id, severity, line, filename, description, recommendation,
        fix_example, vuln_type, cwe,
    ) -> ConfigFinding:
        return ConfigFinding(
            rule_id=rule_id,
            config_type=self.config_type,
            severity=severity,
            description=description,
            recommendation=recommendation,
            fix_example=fix_example,
            file_path=filename,
            line=line,
            vulnerability_type=vuln_type,
            cwe_id=cwe,
        )

"""Terraform scanner tests (Story 4.5)."""

from app.services.security_scan.config_scanners.terraform_scanner import (
    TerraformScanner,
)

scanner = TerraformScanner()


def _rules(content, filename="main.tf"):
    return {f.rule_id for f in scanner.scan(content, filename)}


def test_public_s3_bucket():
    tf = 'resource "aws_s3_bucket" "b" {\n  acl = "public-read"\n  server_side_encryption_configuration {}\n  logging {}\n}\n'
    assert "PUBLIC_S3_BUCKET" in _rules(tf)


def test_open_security_group():
    tf = 'resource "aws_security_group" "sg" {\n  cidr_blocks = ["0.0.0.0/0"]\n}\n'
    assert "OPEN_SECURITY_GROUP" in _rules(tf)


def test_no_encryption_on_bucket():
    tf = 'resource "aws_s3_bucket" "b" {\n  acl = "private"\n  logging {}\n}\n'
    assert "NO_ENCRYPTION" in _rules(tf)


def test_encryption_present_clears():
    tf = (
        'resource "aws_s3_bucket" "b" {\n'
        '  acl = "private"\n'
        "  server_side_encryption_configuration {}\n"
        "  logging {}\n"
        "}\n"
    )
    assert "NO_ENCRYPTION" not in _rules(tf)


def test_no_logging_on_bucket():
    tf = (
        'resource "aws_s3_bucket" "b" {\n'
        '  acl = "private"\n'
        "  server_side_encryption_configuration {}\n"
        "}\n"
    )
    assert "NO_LOGGING" in _rules(tf)


def test_plaintext_secret_variable():
    tf = 'variable "db_password" {\n  sensitive = false\n}\n'
    assert "PLAINTEXT_SECRET" in _rules(tf)


def test_findings_carry_config_type_and_line():
    findings = scanner.scan('resource "aws_security_group" "sg" {\n  cidr_blocks = ["0.0.0.0/0"]\n}\n', "main.tf")
    assert findings
    for f in findings:
        assert f.config_type == "terraform"
        assert f.line is not None

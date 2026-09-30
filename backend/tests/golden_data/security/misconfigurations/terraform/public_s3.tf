// Golden misconfig fixture (Story 4.14) — public S3 bucket (CWE-732).
resource "aws_s3_bucket" "public" {
  bucket = "company-public-assets"
  acl    = "public-read"
}

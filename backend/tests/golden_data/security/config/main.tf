resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
  acl    = "public-read"
}

resource "aws_security_group" "web" {
  name = "web-sg"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

variable "db_password" {
  description = "Database password"
  sensitive   = false
}

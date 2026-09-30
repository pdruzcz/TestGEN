// Golden misconfig fixture (Story 4.14) — security group open to the world (CWE-284).
resource "aws_security_group" "open" {
  name = "allow-all"

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

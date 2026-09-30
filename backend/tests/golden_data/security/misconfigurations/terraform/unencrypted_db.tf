// Golden misconfig fixture (Story 4.14) — RDS instance without encryption (CWE-311).
resource "aws_db_instance" "main" {
  identifier        = "app-db"
  engine            = "postgres"
  instance_class    = "db.t3.medium"
  allocated_storage = 20
  username          = "app"
}

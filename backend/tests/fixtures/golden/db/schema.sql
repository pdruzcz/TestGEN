-- Golden schema — Story 1.53 (FR70) database-layer generator validation.
-- Pełny zestaw ograniczeń: PK, NOT NULL, UNIQUE, CHECK, FK (z ON DELETE CASCADE/RESTRICT),
-- composite UNIQUE. Używany przez tests/golden/test_db_golden.py (§Test 13: pokrycie ≥90%).

CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(32) NOT NULL UNIQUE
);

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INT NOT NULL,
    role VARCHAR(32) NOT NULL,
    org_id INT NOT NULL,
    CONSTRAINT chk_age CHECK (age >= 18),
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_total CHECK (total >= 0),
    CONSTRAINT uq_user_status UNIQUE (user_id, status)
);

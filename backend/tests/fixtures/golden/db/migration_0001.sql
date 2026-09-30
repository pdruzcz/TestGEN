-- Golden migration — Story 1.53 (FR70). Up/down idempotentność (§Test 8/13).

-- up
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity VARCHAR(64) NOT NULL,
    entity_id INT NOT NULL,
    action VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- down
DROP TABLE audit_log;

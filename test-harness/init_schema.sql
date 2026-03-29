-- Business tables watched by the CDC agent

-- Trigger function: auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS accounts (
    account_id   SERIAL PRIMARY KEY,
    account_code VARCHAR(20)    NOT NULL UNIQUE,
    account_name VARCHAR(100)   NOT NULL,
    status       VARCHAR(20)    NOT NULL DEFAULT 'ACTIVE',
    credit_limit NUMERIC(12, 2) NOT NULL DEFAULT 0,
    account_type VARCHAR(20)    NOT NULL DEFAULT 'STANDARD',
    updated_at   TIMESTAMP      NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE TRIGGER accounts_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    account_id  INTEGER        NOT NULL REFERENCES accounts(account_id),
    first_name  VARCHAR(50)    NOT NULL,
    last_name   VARCHAR(50)    NOT NULL,
    email       VARCHAR(100)   NOT NULL UNIQUE,
    tier        VARCHAR(20)    NOT NULL DEFAULT 'BRONZE',
    active      BOOLEAN        NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rules (
    rule_id     INTEGER PRIMARY KEY,
    rule_code   VARCHAR(30)    NOT NULL UNIQUE,
    description VARCHAR(200)   NOT NULL,
    rate        NUMERIC(6, 4)  NOT NULL DEFAULT 0,
    applies_to  VARCHAR(20)    NOT NULL,
    enabled     BOOLEAN        NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS memberships (
    membership_id  INTEGER PRIMARY KEY,
    customer_id    INTEGER      NOT NULL REFERENCES customers(customer_id),
    program_code   VARCHAR(30)  NOT NULL,
    points         INTEGER      NOT NULL DEFAULT 0,
    enrolled_date  DATE         NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
);

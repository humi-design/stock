-- Humisense Expo schema for MySQL.
-- SQLite databases create these tables automatically.

CREATE TABLE IF NOT EXISTS cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_ref VARCHAR(32) UNIQUE,
    case_type VARCHAR(64),
    reference VARCHAR(64),
    amount DECIMAL(18,2),
    currency VARCHAR(8),
    severity VARCHAR(16),
    status VARCHAR(32),
    root_cause TEXT,
    recommendation TEXT,
    confidence DECIMAL(5,2),
    evidence TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS case_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT,
    event_type VARCHAR(64),
    detail TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS leads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128),
    company VARCHAR(128),
    email VARCHAR(128),
    phone VARCHAR(64),
    role VARCHAR(128),
    company_type VARCHAR(64),
    process VARCHAR(64),
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(128) PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS ai_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider VARCHAR(64),
    model VARCHAR(64),
    case_id VARCHAR(64),
    prompt_type VARCHAR(64),
    success TINYINT,
    latency_ms INT,
    created_at DATETIME
);
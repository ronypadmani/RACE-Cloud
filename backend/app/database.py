"""
Database initialization and access layer for RACE-Cloud.
Uses SQLite with a clean schema for users, AWS accounts, and recommendations.
"""
import sqlite3
import os
from flask import g, current_app


# ── Schema Definition ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS aws_accounts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,
    account_alias           TEXT    DEFAULT '',
    encrypted_access_key    TEXT    NOT NULL,
    encrypted_secret_key    TEXT    NOT NULL,
    region                  TEXT    NOT NULL DEFAULT 'us-east-1',
    is_validated            INTEGER DEFAULT 0,
    last_synced             TIMESTAMP,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    aws_account_id      INTEGER NOT NULL,
    rule_id             TEXT    NOT NULL,
    resource_id         TEXT    DEFAULT '',
    resource_type       TEXT    DEFAULT '',
    recommendation_text TEXT    NOT NULL,
    severity            TEXT    NOT NULL CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH')),
    estimated_savings   REAL   DEFAULT 0.0,
    status              TEXT   DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DISMISSED', 'RESOLVED')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (aws_account_id) REFERENCES aws_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    aws_account_id      INTEGER NOT NULL,
    report_data_json    TEXT    NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (aws_account_id) REFERENCES aws_accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS budgets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE,
    monthly_limit   REAL    NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_behavior (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    rule_id         TEXT    NOT NULL,
    recommendation_id INTEGER,
    action_type     TEXT    NOT NULL CHECK(action_type IN ('applied', 'dismissed', 'ignored')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    input           TEXT    NOT NULL,
    input_hash      TEXT    NOT NULL,
    ai_response     TEXT    NOT NULL,
    cost_analysis   TEXT    NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aws_accounts_user ON aws_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_user ON recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_behavior_user ON user_behavior(user_id);
CREATE INDEX IF NOT EXISTS idx_user_behavior_rule ON user_behavior(user_id, rule_id);
CREATE INDEX IF NOT EXISTS idx_ai_requests_hash ON ai_requests(input_hash);
CREATE INDEX IF NOT EXISTS idx_ai_requests_user ON ai_requests(user_id);
"""


# ── Database Helpers ───────────────────────────────────────────────────────────

def get_db():
    """Get a database connection for the current request context."""
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize the database with schema."""
    with app.app_context():
        db_path = app.config['DATABASE_PATH']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_SQL)
        conn.close()

    app.teardown_appcontext(close_db)


def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute an INSERT/UPDATE/DELETE and commit."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

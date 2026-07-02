"""
SQLite schema + connection management.
Zero-DevOps choice for MVP. Migrate to Postgres only when scaling past
~1000 campaigns or needing concurrent writers (see CLAUDE.md).
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    industry TEXT,
    geo TEXT,
    status TEXT NOT NULL DEFAULT 'analyzing',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    entity TEXT,
    location TEXT,
    catalyst TEXT,
    pain_points TEXT,     -- JSON array, exactly 3 items
    product_id TEXT,
    urgency_score INTEGER
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    apollo_id TEXT,
    first_name TEXT,
    last_name TEXT,
    title TEXT,
    seniority TEXT,       -- director | vp | c_suite
    email TEXT,
    phone TEXT,
    linkedin TEXT,
    UNIQUE(campaign_id, apollo_id)
);

CREATE TABLE IF NOT EXISTS creatives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    channel TEXT NOT NULL,   -- email | whatsapp | google_ads
    subject_line TEXT,
    body_text TEXT NOT NULL,
    tracking_url TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    apollo_id TEXT,
    channel TEXT,
    clicked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    service TEXT,         -- openai | apollo
    model TEXT,
    operation TEXT,        -- context_extraction | copy_generation | lead_search | enrichment | icp_theme_extraction | icp_scoring
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    credits_used INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS theme_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    theme_summary TEXT,
    affected_problem_space TEXT,          -- JSON array, stored as text
    vendor_categories_who_benefit TEXT,   -- JSON array, stored as text
    apollo_keyword_candidates TEXT,       -- JSON array, stored as text
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS icp_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    company_name TEXT,
    domain TEXT,
    apollo_industry TEXT,
    apollo_employee_count INTEGER,
    apollo_description TEXT,
    prefilter_result TEXT,      -- kept | dropped_at_prefilter
    prefilter_reason TEXT,
    score INTEGER,              -- nullable, null if dropped at prefilter
    score_reason TEXT,
    exclude_flag BOOLEAN,
    bucket TEXT,                -- approved | needs_review | rejected | dropped_at_prefilter
    human_override TEXT,        -- nullable: approved | rejected, set only if a human changed the bucket
    status TEXT DEFAULT 'pending_review',  -- pending_review | reviewed | leads_fetched
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, domain)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DATABASE_PATH}")

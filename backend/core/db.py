import sqlite3
from pathlib import Path

from core.config import BASE_DIR

DB_PATH = BASE_DIR / "autopilot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS creds (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            claude_api_key_encrypted TEXT,
            upwork_api_key_encrypted TEXT,
            composio_api_key_encrypted TEXT,
            playwright_cookies_encrypted TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY,
            job_id TEXT,
            job_title TEXT,
            job_description TEXT,
            client_history TEXT,
            budget TEXT,
            skills TEXT,
            screening_questions TEXT,
            cover_letter TEXT,
            generated_answers TEXT,
            status TEXT DEFAULT 'pending',  -- pending, approved, improved, submitted, discarded
            feedback TEXT,
            improved_cover_letter TEXT,
            submitted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS job_analyzes (
            id INTEGER PRIMARY KEY,
            job_id TEXT,
            job_url TEXT,
            job_title TEXT,
            job_description TEXT,
            score INTEGER,
            grade TEXT,
            match_breakdown TEXT,
            red_flags TEXT,
            tips TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id)
        );

        CREATE TABLE IF NOT EXISTS autobid_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            min_score INTEGER DEFAULT 70,
            max_budget_usd INTEGER DEFAULT 5000,
            skills_filter TEXT DEFAULT '[]',
            exclude_skills TEXT DEFAULT '[]',
            job_types TEXT DEFAULT '["FIXED"]',
            locations TEXT DEFAULT '[]',
            hourly_rate_min REAL DEFAULT 0,
            hourly_rate_max REAL DEFAULT 200,
            max_proposals_per_day INTEGER DEFAULT 10,
            new_jobs_only BOOLEAN DEFAULT 1,
            proposal_style TEXT DEFAULT '',
            custom_instructions TEXT DEFAULT '',
            running BOOLEAN DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY,
            event_type TEXT,
            job_id TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
        CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at);
        CREATE INDEX IF NOT EXISTS idx_analyzes_job ON job_analyzes(job_id);
        CREATE INDEX IF NOT EXISTS idx_log_created ON activity_log(created_at);
    """)
    conn.close()

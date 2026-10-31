import sqlite3
from typing import Optional, Dict, Any, List
from pathlib import Path
from .config import DB_PATH

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[Path] = None):
    """Initialize the SQLite database schema if not present."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                source_name TEXT NOT NULL,
                original_title TEXT NOT NULL,
                original_summary TEXT,
                original_published TEXT,
                translated_title TEXT,
                description TEXT,
                translated_content TEXT,
                slug TEXT,
                tags TEXT,
                categories TEXT,
                status TEXT NOT NULL DEFAULT 'FETCHED', -- FETCHED, TRANSLATED, APPROVED, FLAGGED, PUBLISHED, FAILED
                audit_score INTEGER DEFAULT 0,
                audit_notes TEXT,
                output_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)")
        conn.commit()

def is_url_processed(url: str, db_path: Optional[Path] = None) -> bool:
    """Check if the given article URL was already fetched/processed."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url.strip(),))
        return cursor.fetchone() is not None

def record_fetched_article(
    url: str,
    source_name: str,
    original_title: str,
    original_summary: str = "",
    original_published: str = "",
    db_path: Optional[Path] = None
) -> int:
    """Insert a new article record."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO articles (url, source_name, original_title, original_summary, original_published, status)
            VALUES (?, ?, ?, ?, ?, 'FETCHED')
        """, (url.strip(), source_name, original_title.strip(), original_summary, original_published))
        conn.commit()
        return cursor.lastrowid

def record_translation(
    article_id: int,
    translated_title: str,
    description: str,
    translated_content: str,
    slug: str,
    tags: str,
    categories: str,
    db_path: Optional[Path] = None
):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE articles
            SET translated_title = ?,
                description = ?,
                translated_content = ?,
                slug = ?,
                tags = ?,
                categories = ?,
                status = 'TRANSLATED'
            WHERE id = ?
        """, (translated_title, description, translated_content, slug, tags, categories, article_id))
        conn.commit()

def record_audit_result(
    article_id: int,
    audit_score: int,
    audit_notes: str,
    is_approved: bool,
    output_file: Optional[str] = None,
    db_path: Optional[Path] = None
):
    status = "PUBLISHED" if is_approved else "FLAGGED"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE articles
            SET audit_score = ?,
                audit_notes = ?,
                status = ?,
                output_file = ?,
                published_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE id = ?
        """, (audit_score, audit_notes, status, output_file, is_approved, article_id))
        conn.commit()

def get_stats(db_path: Optional[Path] = None) -> Dict[str, int]:
    """Retrieve counts by status."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, count(*) as cnt FROM articles GROUP BY status")
        counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
        return counts

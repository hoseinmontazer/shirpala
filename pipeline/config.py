import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = BASE_DIR / "pipeline"

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Pipeline Configuration
SOURCES_FILE = Path(os.getenv("SOURCES_FILE", str(PIPELINE_DIR / "sources.yaml")))
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "pipeline.db")))
POSTS_OUTPUT_DIR = Path(os.getenv("POSTS_OUTPUT_DIR", str(BASE_DIR / "blog" / "content" / "fa" / "posts")))
DAILY_MAX_POSTS = int(os.getenv("DAILY_MAX_POSTS", "3"))
AUDIT_MIN_SCORE = int(os.getenv("AUDIT_MIN_SCORE", "75"))
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")  # HH:MM UTC

# Hugo Configuration
HUGO_SITE_DIR = BASE_DIR / "blog"
HUGO_REBUILD_ON_PUBLISH = os.getenv("HUGO_REBUILD_ON_PUBLISH", "true").lower() in ("true", "1", "yes")

# Quality & Audit Rules
MIN_BODY_WORD_COUNT = int(os.getenv("MIN_BODY_WORD_COUNT", "150"))
AUTO_PUBLISH_APPROVED = os.getenv("AUTO_PUBLISH_APPROVED", "true").lower() in ("true", "1", "yes")

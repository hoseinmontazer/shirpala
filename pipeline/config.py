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

# LLM Provider Configuration
# Supported: "nexusllm", "gemini", "mock"
DEFAULT_NEXUS_KEY = "nxs_24d0db882c2ae12c0cecb761f9f2c91e71816c12db887a1e816d2b131c9c7077"
NEXUSLLM_API_KEY = os.getenv("NEXUSLLM_API_KEY", DEFAULT_NEXUS_KEY).strip()
NEXUSLLM_BASE_URL = os.getenv("NEXUSLLM_BASE_URL", "https://api-nexusllm.dariasystem.com/v1").rstrip("/")
NEXUSLLM_MODEL = os.getenv("NEXUSLLM_MODEL", "qwen")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Determine active provider
if os.getenv("LLM_PROVIDER"):
    LLM_PROVIDER = os.getenv("LLM_PROVIDER").lower()
elif NEXUSLLM_API_KEY:
    LLM_PROVIDER = "nexusllm"
elif GEMINI_API_KEY:
    LLM_PROVIDER = "gemini"
else:
    LLM_PROVIDER = "mock"

# Audio & TTS Configuration (Piper TTS on NexusLLM)
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() in ("true", "1", "yes")
TTS_MODEL = os.getenv("TTS_MODEL", "piper")
TTS_VOICE = os.getenv("TTS_VOICE", "fa_IR-amir-medium")
AUDIO_OUTPUT_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", str(BASE_DIR / "blog" / "static" / "audio" / "posts")))

# Whisper STT Configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")

# Pipeline Configuration
SOURCES_FILE = Path(os.getenv("SOURCES_FILE", str(PIPELINE_DIR / "sources.yaml")))
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "pipeline.db")))
POSTS_FA_DIR = Path(os.getenv("POSTS_FA_DIR", str(BASE_DIR / "blog" / "content" / "fa" / "posts")))
POSTS_EN_DIR = Path(os.getenv("POSTS_EN_DIR", str(BASE_DIR / "blog" / "content" / "en" / "posts")))
POSTS_OUTPUT_DIR = POSTS_FA_DIR
DAILY_MAX_POSTS = int(os.getenv("DAILY_MAX_POSTS", "3"))
AUDIT_MIN_SCORE = int(os.getenv("AUDIT_MIN_SCORE", "75"))
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")  # HH:MM UTC

# Hugo Configuration
HUGO_SITE_DIR = BASE_DIR / "blog"
HUGO_REBUILD_ON_PUBLISH = os.getenv("HUGO_REBUILD_ON_PUBLISH", "true").lower() in ("true", "1", "yes")

# Quality & Audit Rules
MIN_BODY_WORD_COUNT = int(os.getenv("MIN_BODY_WORD_COUNT", "250"))
AUTO_PUBLISH_APPROVED = os.getenv("AUTO_PUBLISH_APPROVED", "true").lower() in ("true", "1", "yes")

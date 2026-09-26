import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "8192"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))

# Upwork GraphQL API (reads: search jobs, profiles, proposals, messages)
UPWORK_GRAPHQL_URL = "https://api.upwork.com/graphql"
UPWORK_API_KEY = os.getenv("UPWORK_API_KEY", "")  # OAuth access token

# Composio (optional write provider — set COMPOSIO_API_KEY + UPWORK connected account)
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_BASE_URL = os.getenv("COMPOSIO_BASE_URL", "https://backend.composio.dev/api/v3.1")

# Playwright fallback for submissions (always available)
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

# Encryption
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

# Auto-bidder
AUTO_BID_SCAN_INTERVAL_SECONDS = int(os.getenv("AUTO_BID_SCAN_INTERVAL", "120"))
AUTO_BID_MAX_CONCURRENT = int(os.getenv("AUTO_BID_MAX_CONCURRENT", "1"))

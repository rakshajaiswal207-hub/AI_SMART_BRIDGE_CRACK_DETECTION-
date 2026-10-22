"""Runtime settings for the bridge crack inspection prototype.

Environment variables override these defaults. Leave DB_ENGINE as "auto"
to use MySQL when it is reachable and SQLite otherwise, so the dashboard
still runs in a classroom without a database server.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

# auto | mysql | sqlite
DB_ENGINE = os.getenv("DB_ENGINE", "auto").lower()
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "bridge_crack")

SQLITE_PATH = ROOT / "data" / "inspections.db"
UPLOAD_DIR = ROOT / "data" / "uploads"
RESULT_DIR = ROOT / "data" / "results"
PROCESSED_DIR = ROOT / "data" / "processed"
SAMPLE_DIR = ROOT / "static" / "samples"

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_SIDE = 1280
import aiosqlite
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_DIR = Path("/app/data")
# DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_FILE = DB_DIR / "channels.db"

async def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"[DB] Database directory: {DB_FILE}")

    db = await aiosqlite.connect(str(DB_FILE))

    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'proxy',
            "group" TEXT NOT NULL DEFAULT 'Default',
            logo TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)

    await db.commit()
    logger.info(f"[DB] Table 'channels' ready.")

    return db

async def close_db(db: Optional[aiosqlite.Connection]):
    if db:
        try:
            await db.close()
            logger.info("[DB] Connection closed.")
        except Exception as e:
            logger.warning(f"[DB] Error closing connection: {e}")
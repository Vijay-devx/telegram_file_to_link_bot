import aiosqlite
import json
from config import settings

async def init_db():
    async with aiosqlite.connect(settings.db_path) as db:
        # Enable WAL mode for concurrent access between web and bot processes
        await db.execute("PRAGMA journal_mode=WAL;")
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS files (
                token TEXT PRIMARY KEY,
                document_id INTEGER,
                access_hash INTEGER,
                file_reference BLOB,
                file_name TEXT,
                file_size INTEGER,
                mime_type TEXT,
                expires_at INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Handle migration if table already exists
        try:
            await db.execute("ALTER TABLE files ADD COLUMN expires_at INTEGER;")
        except Exception:
            pass
        await db.commit()

async def save_file_metadata(token: str, document_id: int, access_hash: int, file_reference: bytes, file_name: str, file_size: int, mime_type: str, expires_at: int):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute('''
            INSERT INTO files (token, document_id, access_hash, file_reference, file_name, file_size, mime_type, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (token, document_id, access_hash, file_reference, file_name, file_size, mime_type, expires_at))
        await db.commit()

async def get_file_metadata(token: str):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        async with db.execute('''
            SELECT document_id, access_hash, file_reference, file_name, file_size, mime_type, expires_at
            FROM files
            WHERE token = ?
        ''', (token,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "document_id": row[0],
                    "access_hash": row[1],
                    "file_reference": row[2],
                    "file_name": row[3],
                    "file_size": row[4],
                    "mime_type": row[5],
                    "expires_at": row[6]
                }
            return None

async def delete_expired_links(db_path: str):
    import time
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute('DELETE FROM files WHERE expires_at < ?', (int(time.time()),))
        await db.commit()

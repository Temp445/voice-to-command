"""
ACE Voice Controller — Background File Indexer
Indexes user directories and drives into a local SQLite database for instant searching.
Uses watchfiles to keep the index updated in real-time.
"""

import asyncio
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from watchfiles import watch, Change
    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    logger.warning("watchfiles not installed. FileIndexer will not update in real-time.")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "file_cache.db"

# Exclude heavy, system, or hidden directories to speed up scanning
EXCLUDED_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    "appdata", "program files", "program files (x86)", "windows",
    "programdata", "$recycle.bin", "system volume information",
    ".idea", ".vscode"
}

def clean_name(name: str) -> str:
    """Normalize file/folder name for searching."""
    return name.lower().strip()


class FileIndexer:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._watch_thread = None

    def _get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    name TEXT,
                    is_folder INTEGER,
                    drive TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_name ON files(name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_is_folder ON files(is_folder)')

    def _insert_or_update(self, path: str, name: str, is_folder: int, drive: str):
        with self._lock:
            with self._get_conn() as conn:
                conn.execute('''
                    INSERT INTO files (path, name, is_folder, drive) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET 
                        name=excluded.name, 
                        is_folder=excluded.is_folder,
                        drive=excluded.drive
                ''', (path, name, is_folder, drive))

    def _delete(self, path: str):
        with self._lock:
            with self._get_conn() as conn:
                conn.execute('DELETE FROM files WHERE path = ?', (path,))

    def _bulk_insert(self, records: list):
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany('''
                    INSERT OR IGNORE INTO files (path, name, is_folder, drive) 
                    VALUES (?, ?, ?, ?)
                ''', records)

    def start_background_indexing(self):
        """Start the background scanner and watchfiles observer."""
        threading.Thread(target=self._scan_and_watch, daemon=True).start()

    def _scan_and_watch(self):
        logger.info("📁 Starting background file indexing...")
        
        roots_to_scan = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path.home() / "Pictures",
            Path.home() / "Music",
            Path.home() / "Videos",
        ]
        
        # Add common drives if they exist
        for letter in ['C', 'D', 'E', 'F']:
            drive = Path(f"{letter}:/")
            if drive.exists() and letter != 'C': # Skip scanning whole C drive to save time, C is huge
                roots_to_scan.append(drive)

        valid_roots = [str(r) for r in set(roots_to_scan) if r.exists()]
        total_scanned = 0

        for root in valid_roots:
            logger.debug(f"Indexing root: {root}")
            batch = []
            
            for dirpath, dirnames, filenames in os.walk(root):
                # Filter out excluded directories in-place
                dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIRS]
                
                path_obj = Path(dirpath)
                drive = path_obj.drive.replace(":", "") if path_obj.drive else ""
                
                # Add folders
                for d in dirnames:
                    full_path = os.path.join(dirpath, d)
                    batch.append((full_path, clean_name(d), 1, drive))
                    
                # Add files
                for f in filenames:
                    full_path = os.path.join(dirpath, f)
                    batch.append((full_path, clean_name(f), 0, drive))
                    
                if len(batch) >= 1000:
                    self._bulk_insert(batch)
                    total_scanned += len(batch)
                    batch = []
                    
            if batch:
                self._bulk_insert(batch)
                total_scanned += len(batch)

        logger.info(f"✅ Indexing complete. Total files/folders indexed: {total_scanned}")
        
        # Disabled: Windows Search API (ADODB) is now used instead.
        # if WATCHFILES_AVAILABLE and valid_roots:
        #     self._watch_thread = threading.Thread(
        #         target=self._watch_changes, 
        #         args=(valid_roots,), 
        #         daemon=True
        #     )
        #     self._watch_thread.start()
        #     logger.info("👀 watchfiles observer started for real-time updates.")

    def _watch_changes(self, roots: list[str]):
        try:
            for changes in watch(*roots, stop_event=self._stop_event):
                for change, path_str in changes:
                    path = Path(path_str)
                    
                    if any(exc in [p.lower() for p in path.parts] for exc in EXCLUDED_DIRS):
                        continue
                        
                    if change == Change.deleted:
                        self._delete(path_str)
                    else: # added or modified
                        is_folder = 1 if path.is_dir() else 0
                        name = clean_name(path.name)
                        drive = path.drive.replace(":", "") if path.drive else ""
                        self._insert_or_update(path_str, name, is_folder, drive)
        except Exception as e:
            logger.warning(f"watchfiles error: {e}")

    def stop(self):
        self._stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)

    def search(self, query: str, drive: str | None = None, is_folder: bool = True, limit: int = 10) -> list[dict]:
        """Search for a file or folder by name substring using Windows Search API or SQLite."""
        clean_q = clean_name(query)
        
        # 1. Try Windows Search API (Extremely Fast, Drive-Wide)
        try:
            import win32com.client
            conn = win32com.client.Dispatch("ADODB.Connection")
            conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            
            kind_condition = "System.Kind = 'folder'" if is_folder else "System.Kind <> 'folder'"
            query_escaped = clean_q.replace("'", "''")
            
            sql = f"SELECT System.ItemPathDisplay, System.ItemNameDisplay FROM SystemIndex WHERE {kind_condition} AND System.FileName LIKE '%{query_escaped}%'"
            
            if drive:
                sql += f" AND System.ItemPathDisplay LIKE '{drive.upper()}:\\%'"
                
            rs, status = conn.Execute(sql)
            
            results = []
            while not rs.EOF and len(results) < limit:
                path = rs.Fields.Item("System.ItemPathDisplay").Value
                name = rs.Fields.Item("System.ItemNameDisplay").Value
                if path and name:
                    results.append({
                        "id": path,
                        "path": path,
                        "name": name,
                        "is_folder": is_folder,
                        "drive": path[0] if len(path) > 1 and path[1] == ':' else None
                    })
                rs.MoveNext()
                
            if results:
                logger.info(f"Windows Search API returned {len(results)} results for '{clean_q}'")
                return results
        except Exception as e:
            logger.warning(f"Windows Search API failed (fallback to local cache): {e}")

        # 2. Fallback to Local SQLite Cache
        sql = "SELECT id, path, name, is_folder, drive FROM files WHERE is_folder = ?"
        params = [1 if is_folder else 0]
        
        if drive:
            sql += " AND LOWER(drive) = ?"
            params.append(drive.lower())
            
        sql += " AND name LIKE ? LIMIT ?"
        params.extend([f"%{clean_q}%", limit])
        
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

# Singleton instance
_indexer: Optional[FileIndexer] = None

def get_indexer() -> FileIndexer:
    global _indexer
    if _indexer is None:
        _indexer = FileIndexer()
    return _indexer

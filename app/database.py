"""
SQLite database management for track and stem metadata persistence.
"""
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Database file location
DB_PATH = Path(__file__).parent / "spleeter.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                bpm REAL,
                duration REAL,
                stem_count INTEGER,
                original_filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                filename TEXT NOT NULL,
                duration REAL,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_stems_track_id ON stems(track_id);

            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_name TEXT NOT NULL,
                stem_name TEXT NOT NULL,
                filename TEXT UNIQUE NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_samples_track ON samples(track_name);

            CREATE TABLE IF NOT EXISTS loops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                track_name TEXT NOT NULL,
                stem_name TEXT NOT NULL,
                filename TEXT UNIQUE NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                loop_count INTEGER NOT NULL,
                duration REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_loops_track ON loops(track_name);
        """)

        # Migration: Add original_filename column if it doesn't exist
        cursor = conn.execute("PRAGMA table_info(tracks)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'original_filename' not in columns:
            conn.execute("ALTER TABLE tracks ADD COLUMN original_filename TEXT")


def create_track(name: str, bpm: Optional[float], duration: Optional[float], stem_count: int, original_filename: Optional[str] = None) -> int:
    """
    Create a new track record.

    Returns the track ID.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (name, bpm, duration, stem_count, original_filename) VALUES (?, ?, ?, ?, ?)",
            (name, bpm, duration, stem_count, original_filename)
        )
        return cursor.lastrowid


def create_stem(track_id: int, name: str, filename: str, duration: Optional[float]) -> int:
    """
    Create a new stem record.

    Returns the stem ID.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO stems (track_id, name, filename, duration) VALUES (?, ?, ?, ?)",
            (track_id, name, filename, duration)
        )
        return cursor.lastrowid


def get_all_tracks() -> list[dict]:
    """Get all tracks with their metadata."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, bpm, duration, stem_count, original_filename, created_at
            FROM tracks
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_track_with_stems(track_id: int) -> Optional[dict]:
    """Get a track with all its stems."""
    with get_db() as conn:
        # Get track
        cursor = conn.execute(
            "SELECT id, name, bpm, duration, stem_count, original_filename, created_at FROM tracks WHERE id = ?",
            (track_id,)
        )
        track_row = cursor.fetchone()

        if not track_row:
            return None

        track = dict(track_row)

        # Get stems
        cursor = conn.execute(
            "SELECT id, name, filename, duration FROM stems WHERE track_id = ? ORDER BY name",
            (track_id,)
        )
        track["stems"] = [dict(row) for row in cursor.fetchall()]

        return track


def track_exists(name: str) -> bool:
    """Check if a track with the given name exists."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM tracks WHERE name = ?",
            (name,)
        )
        return cursor.fetchone() is not None


def delete_track(track_id: int) -> bool:
    """
    Delete a track and its stems.

    Returns True if a track was deleted, False otherwise.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM tracks WHERE id = ?",
            (track_id,)
        )
        return cursor.rowcount > 0


def get_track_by_name(name: str) -> Optional[dict]:
    """Get a track by its name."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, bpm, duration, stem_count, original_filename, created_at FROM tracks WHERE name = ?",
            (name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_track_original(track_id: int, original_filename: str) -> bool:
    """Update a track's original filename."""
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE tracks SET original_filename = ? WHERE id = ?",
            (original_filename, track_id)
        )
        return cursor.rowcount > 0


# Sample CRUD operations

def create_sample(
    track_name: str,
    stem_name: str,
    filename: str,
    start_time: float,
    end_time: float,
    duration: float
) -> int:
    """
    Create a new sample record.

    Returns the sample ID.
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO samples
               (track_name, stem_name, filename, start_time, end_time, duration)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (track_name, stem_name, filename, start_time, end_time, duration)
        )
        return cursor.lastrowid


def get_all_samples() -> list[dict]:
    """Get all samples with their metadata."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, track_name, stem_name, filename, start_time, end_time, duration, created_at
            FROM samples
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_sample_by_id(sample_id: int) -> Optional[dict]:
    """Get a sample by its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT id, track_name, stem_name, filename, start_time, end_time, duration, created_at
               FROM samples WHERE id = ?""",
            (sample_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_sample(sample_id: int) -> bool:
    """
    Delete a sample.

    Returns True if a sample was deleted, False otherwise.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM samples WHERE id = ?",
            (sample_id,)
        )
        return cursor.rowcount > 0


def sample_exists(filename: str) -> bool:
    """Check if a sample with the given filename exists."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM samples WHERE filename = ?",
            (filename,)
        )
        return cursor.fetchone() is not None


# Loop CRUD operations

def create_loop(
    source_type: str,
    track_name: str,
    stem_name: str,
    filename: str,
    start_time: float,
    end_time: float,
    loop_count: int,
    duration: float
) -> int:
    """
    Create a new loop record.

    Returns the loop ID.
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO loops
               (source_type, track_name, stem_name, filename, start_time, end_time, loop_count, duration)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_type, track_name, stem_name, filename, start_time, end_time, loop_count, duration)
        )
        return cursor.lastrowid


def get_all_loops() -> list[dict]:
    """Get all loops with their metadata."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, source_type, track_name, stem_name, filename, start_time, end_time, loop_count, duration, created_at
            FROM loops
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_loop_by_id(loop_id: int) -> Optional[dict]:
    """Get a loop by its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT id, source_type, track_name, stem_name, filename, start_time, end_time, loop_count, duration, created_at
               FROM loops WHERE id = ?""",
            (loop_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_loop(loop_id: int) -> bool:
    """
    Delete a loop.

    Returns True if a loop was deleted, False otherwise.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM loops WHERE id = ?",
            (loop_id,)
        )
        return cursor.rowcount > 0


def loop_exists(filename: str) -> bool:
    """Check if a loop with the given filename exists."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM loops WHERE filename = ?",
            (filename,)
        )
        return cursor.fetchone() is not None

#!/usr/bin/env python3
"""
Add video_path column to summaries table for existing databases.
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: str = "focuslog.db"):
    """Add video_path column to summaries table if it doesn't exist."""
    
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if video_path column already exists
    cursor.execute("PRAGMA table_info(summaries)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'video_path' in columns:
        print("✓ video_path column already exists in summaries table")
        conn.close()
        return
    
    print("Adding video_path column to summaries table...")
    
    try:
        cursor.execute("""
            ALTER TABLE summaries
            ADD COLUMN video_path TEXT
        """)
        conn.commit()
        print("✓ Successfully added video_path column")
    except Exception as e:
        print(f"✗ Error adding column: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "focuslog.db"
    migrate_database(db_path)

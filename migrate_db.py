#!/usr/bin/env python3
"""
Migrate old FocusLog database schema to new schema with labels.
This will preserve your existing captures.
"""

import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: str = "focuslog.db"):
    """Migrate database from old schema to new schema."""
    
    if not Path(db_path).exists():
        print(f"Database '{db_path}' not found. No migration needed.")
        return
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if we need to migrate
    cursor.execute("PRAGMA table_info(captures)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'description' in columns:
        print("✓ Database already migrated!")
        conn.close()
        return
    
    print("Starting migration...")
    
    try:
        # Create new tables
        print("  Creating labels table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("  Creating captures_labels junction table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captures_labels (
                capture_id INTEGER NOT NULL,
                label_id INTEGER NOT NULL,
                PRIMARY KEY (capture_id, label_id),
                FOREIGN KEY (capture_id) REFERENCES captures(id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            )
        """)
        
        print("  Creating summaries table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_type TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Rename old captures table
        print("  Backing up old captures table...")
        cursor.execute("ALTER TABLE captures RENAME TO captures_old")
        
        # Create new captures table
        print("  Creating new captures table...")
        cursor.execute("""
            CREATE TABLE captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                screenshot BLOB NOT NULL,
                description TEXT,
                classification_raw TEXT,
                classification_error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migrate data
        print("  Migrating existing captures...")
        cursor.execute("""
            INSERT INTO captures (id, timestamp, screenshot, description, classification_raw, classification_error, created_at)
            SELECT id, timestamp, screenshot, classification, classification_raw, classification_error, created_at
            FROM captures_old
        """)
        
        # Create indexes
        print("  Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_captures_timestamp 
            ON captures(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summaries_time 
            ON summaries(start_time, end_time, summary_type)
        """)
        
        # Drop old table
        print("  Cleaning up...")
        cursor.execute("DROP TABLE captures_old")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        
        # Show stats
        cursor.execute("SELECT COUNT(*) FROM captures")
        count = cursor.fetchone()[0]
        print(f"  Migrated {count} captures")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate FocusLog database to new schema")
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to database file (default: focuslog.db)"
    )
    
    args = parser.parse_args()
    migrate_database(args.database)

#!/usr/bin/env python3
"""
Migration script to add video_path column to summaries table.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = "focuslog.db"

def main():
    """Add video_path column to summaries table."""
    
    # Check if database exists
    if not Path(DB_PATH).exists():
        print(f"Error: Database {DB_PATH} not found")
        return 1
    
    # Backup database first
    backup_path = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    print("✓ Backup created")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if video_path column already exists
    cursor.execute("PRAGMA table_info(summaries)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'video_path' in columns:
        print("✓ video_path column already exists")
        conn.close()
        return 0
    
    # Add video_path column
    print("Adding video_path column to summaries table...")
    try:
        cursor.execute("""
            ALTER TABLE summaries
            ADD COLUMN video_path TEXT
        """)
        conn.commit()
        print("✓ video_path column added successfully")
        
        # Verify
        cursor.execute("PRAGMA table_info(summaries)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"\nSummaries table columns: {', '.join(columns)}")
        
    except Exception as e:
        print(f"✗ Error adding column: {e}")
        conn.rollback()
        conn.close()
        return 1
    
    conn.close()
    print("\n✓ Migration completed successfully")
    return 0

if __name__ == "__main__":
    exit(main())

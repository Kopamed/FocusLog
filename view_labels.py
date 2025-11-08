#!/usr/bin/env python3
"""
View all labels and their usage statistics.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from focuslogd.database import FocusLogDB


def main():
    parser = argparse.ArgumentParser(description="View FocusLog labels")
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to SQLite database file (default: focuslog.db)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.database).exists():
        print(f"Error: Database file '{args.database}' not found")
        sys.exit(1)
    
    with FocusLogDB(db_path=args.database) as db:
        labels = db.get_all_labels()
        
        print("="*60)
        print("FocusLog Labels")
        print("="*60)
        
        if not labels:
            print("No labels found yet.")
        else:
            print(f"Total labels: {len(labels)}\n")
            
            # Get usage count for each label
            cursor = db.conn.cursor()
            for label in labels:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM captures_labels cl
                    JOIN labels l ON cl.label_id = l.id
                    WHERE l.name = ?
                """, (label,))
                count = cursor.fetchone()['count']
                print(f"  • {label} ({count} uses)")


if __name__ == "__main__":
    main()

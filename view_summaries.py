#!/usr/bin/env python3
"""
View summaries from the FocusLog database.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent / "src"))

from focuslogd.database import FocusLogDB


def main():
    parser = argparse.ArgumentParser(description="View FocusLog summaries")
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to SQLite database file (default: focuslog.db)"
    )
    parser.add_argument(
        "-t", "--type",
        type=str,
        choices=['5min', 'hourly', 'all'],
        default='all',
        help="Type of summaries to show (default: all)"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Number of summaries to show (default: 10)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.database).exists():
        print(f"Error: Database file '{args.database}' not found")
        sys.exit(1)
    
    with FocusLogDB(db_path=args.database) as db:
        cursor = db.conn.cursor()
        
        print("="*80)
        print("FocusLog Summaries")
        print("="*80)
        
        # Get summaries
        if args.type == 'all':
            cursor.execute("""
                SELECT summary_type, start_time, end_time, content, created_at
                FROM summaries
                ORDER BY end_time DESC
                LIMIT ?
            """, (args.limit,))
        else:
            cursor.execute("""
                SELECT summary_type, start_time, end_time, content, created_at
                FROM summaries
                WHERE summary_type = ?
                ORDER BY end_time DESC
                LIMIT ?
            """, (args.type, args.limit))
        
        summaries = cursor.fetchall()
        
        if not summaries:
            print("No summaries found yet.")
        else:
            for summary in summaries:
                summary_type = summary['summary_type']
                start = summary['start_time']
                end = summary['end_time']
                content = summary['content']
                
                print(f"\n[{summary_type.upper()}] {start} → {end}")
                print("-"*80)
                print(content)
                print()


if __name__ == "__main__":
    main()

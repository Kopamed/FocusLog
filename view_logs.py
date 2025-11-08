#!/usr/bin/env python3
"""
Simple utility to view FocusLog database statistics and recent captures.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from focuslogd.database import FocusLogDB
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="View FocusLog database contents")
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to SQLite database file (default: focuslog.db)"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Number of recent captures to show (default: 10)"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only show statistics, not individual captures"
    )
    
    args = parser.parse_args()
    
    if not Path(args.database).exists():
        print(f"Error: Database file '{args.database}' not found")
        sys.exit(1)
    
    with FocusLogDB(db_path=args.database) as db:
        # Show statistics
        stats = db.get_statistics()
        print("="*60)
        print("FocusLog Database Statistics")
        print("="*60)
        print(f"Total captures: {stats['total_captures']}")
        print(f"Database size: {stats['total_size_mb']} MB")
        if stats['first_capture']:
            print(f"First capture: {stats['first_capture']}")
            print(f"Last capture: {stats['last_capture']}")
        print()
        
        if not args.stats_only and stats['total_captures'] > 0:
            # Show recent captures
            print(f"Recent {args.limit} captures:")
            print("-"*60)
            
            captures = db.get_recent_captures(limit=args.limit, include_screenshots=False)
            for cap in captures:
                print(f"\nID: {cap['id']}")
                print(f"Time: {cap['timestamp']}")
                if cap.get('labels'):
                    print(f"Labels: {', '.join(cap['labels'])}")
                if cap.get('description'):
                    print(f"Description: {cap['description']}")
                if cap.get('classification_error'):
                    print(f"Error: {cap['classification_error']}")


if __name__ == "__main__":
    main()

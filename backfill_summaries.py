#!/usr/bin/env python3
"""
Backfill summaries for existing captures in the FocusLog database.
Generates 5-minute and hourly summaries for all past captures.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from focuslogd.database import FocusLogDB
from focuslogd.summarizer import SummaryGenerator


def backfill_summaries(db_path: str = "focuslog.db", api_key: str = None):
    """Generate summaries for all existing captures."""
    
    if not Path(db_path).exists():
        print(f"Error: Database '{db_path}' not found")
        sys.exit(1)
    
    print("="*80)
    print("FocusLog Summary Backfill")
    print("="*80)
    
    db = FocusLogDB(db_path=db_path)
    summarizer = SummaryGenerator(api_key=api_key)
    
    # Get all captures
    cursor = db.conn.cursor()
    cursor.execute("SELECT MIN(timestamp) as first, MAX(timestamp) as last FROM captures")
    result = cursor.fetchone()
    
    if not result['first']:
        print("No captures found in database.")
        db.close()
        return
    
    first_capture = datetime.fromisoformat(result['first'])
    last_capture = datetime.fromisoformat(result['last'])
    
    print(f"\nCapture range: {first_capture} to {last_capture}")
    print(f"Duration: {last_capture - first_capture}")
    
    # Check for existing summaries
    cursor.execute("SELECT COUNT(*) as count FROM summaries WHERE summary_type = '5min'")
    existing_5min = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM summaries WHERE summary_type = 'hourly'")
    existing_hourly = cursor.fetchone()['count']
    
    print(f"\nExisting summaries:")
    print(f"  5-minute: {existing_5min}")
    print(f"  Hourly: {existing_hourly}")
    
    response = input("\nGenerate summaries for all captures? [y/N]: ")
    if response.lower() != 'y':
        print("Cancelled.")
        db.close()
        return
    
    print("\nGenerating 5-minute summaries...")
    print("-"*80)
    
    # Generate 5-minute summaries
    current_time = first_capture
    five_min_count = 0
    
    while current_time < last_capture:
        end_time = current_time + timedelta(minutes=5)
        
        # Get captures in this 5-minute window
        captures = []
        cursor.execute("""
            SELECT id, timestamp, description, classification_error
            FROM captures
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (current_time.isoformat(), end_time.isoformat()))
        
        for row in cursor.fetchall():
            capture = dict(row)
            # Get labels
            cursor.execute("""
                SELECT l.name
                FROM labels l
                JOIN captures_labels cl ON l.id = cl.label_id
                WHERE cl.capture_id = ?
            """, (capture['id'],))
            capture['labels'] = [r['name'] for r in cursor.fetchall()]
            captures.append(capture)
        
        if captures:
            print(f"  {current_time.strftime('%H:%M:%S')} → {end_time.strftime('%H:%M:%S')}: {len(captures)} captures", end=" ")
            
            # Generate summary
            summary = summarizer.generate_5min_summary(captures)
            
            # Save to database
            db.save_summary(
                summary_type='5min',
                start_time=current_time,
                end_time=end_time,
                content=summary
            )
            
            print("✓")
            five_min_count += 1
        
        current_time = end_time
    
    print(f"\n✓ Generated {five_min_count} 5-minute summaries")
    
    # Generate hourly summaries
    print("\nGenerating hourly summaries...")
    print("-"*80)
    
    current_time = first_capture
    hourly_count = 0
    
    while current_time < last_capture:
        end_time = current_time + timedelta(hours=1)
        
        # Get 5-min summaries in this hour
        five_min_summaries = db.get_summaries_in_range(
            summary_type='5min',
            start_time=current_time,
            end_time=end_time
        )
        
        if five_min_summaries:
            print(f"  {current_time.strftime('%H:%M:%S')} → {end_time.strftime('%H:%M:%S')}: {len(five_min_summaries)} 5-min summaries", end=" ")
            
            # Generate summary
            summary = summarizer.generate_hourly_summary(five_min_summaries)
            
            # Save to database
            db.save_summary(
                summary_type='hourly',
                start_time=current_time,
                end_time=end_time,
                content=summary
            )
            
            print("✓")
            hourly_count += 1
        
        current_time = end_time
    
    print(f"\n✓ Generated {hourly_count} hourly summaries")
    
    print("\n" + "="*80)
    print("Backfill complete!")
    print("="*80)
    
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill FocusLog summaries")
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to database file (default: focuslog.db)"
    )
    parser.add_argument(
        "-k", "--api-key",
        type=str,
        help="OpenAI API key (or use OPENAI_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    backfill_summaries(db_path=args.database, api_key=args.api_key)

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json


class FocusLogDB:
    """SQLite database for storing screenshots and classifications."""
    
    def __init__(self, db_path: str = "focuslog.db"):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_tables()
    
    def _connect(self) -> None:
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def _create_tables(self) -> None:
        """Create necessary database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Labels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Main table for screenshot captures
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                screenshot BLOB NOT NULL,
                description TEXT,
                classification_raw TEXT,
                classification_error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Junction table for captures to labels (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captures_labels (
                capture_id INTEGER NOT NULL,
                label_id INTEGER NOT NULL,
                PRIMARY KEY (capture_id, label_id),
                FOREIGN KEY (capture_id) REFERENCES captures(id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            )
        """)
        
        # Summaries table for 5-min, hourly summaries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_type TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                content TEXT NOT NULL,
                video_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index on timestamp for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_captures_timestamp 
            ON captures(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_summaries_time 
            ON summaries(start_time, end_time, summary_type)
        """)
        
        self.conn.commit()
    
    def get_or_create_label(self, label_name: str) -> int:
        """
        Get label ID by name, or create it if it doesn't exist.
        
        Args:
            label_name: Name of the label
        
        Returns:
            int: Label ID
        """
        cursor = self.conn.cursor()
        
        # Try to get existing label
        cursor.execute("SELECT id FROM labels WHERE name = ?", (label_name,))
        row = cursor.fetchone()
        
        if row:
            # Update last_used timestamp
            cursor.execute(
                "UPDATE labels SET last_used = ? WHERE id = ?",
                (datetime.now().isoformat(), row['id'])
            )
            self.conn.commit()
            return row['id']
        
        # Create new label
        cursor.execute(
            "INSERT INTO labels (name) VALUES (?)",
            (label_name,)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_labels(self) -> List[str]:
        """
        Get all label names from the database.
        
        Returns:
            List of label names, ordered by most recently used
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM labels 
            ORDER BY last_used DESC
        """)
        return [row['name'] for row in cursor.fetchall()]
    
    def save_capture(
        self,
        screenshot: bytes,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
        classification_raw: Optional[str] = None,
        classification_error: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Save a screenshot capture with labels and description to the database.
        
        Args:
            screenshot: PNG image data as bytes
            description: Detailed description of what user is doing
            labels: List of label names to attach to this capture
            classification_raw: Raw JSON response from classifier
            classification_error: Error message if classification failed
            timestamp: Capture timestamp (defaults to now)
        
        Returns:
            int: ID of the inserted record
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO captures 
            (timestamp, screenshot, description, classification_raw, classification_error)
            VALUES (?, ?, ?, ?, ?)
        """, (
            timestamp.isoformat(),
            screenshot,
            description,
            classification_raw,
            classification_error
        ))
        
        capture_id = cursor.lastrowid
        
        # Add labels if provided
        if labels:
            for label_name in labels:
                label_id = self.get_or_create_label(label_name)
                cursor.execute("""
                    INSERT OR IGNORE INTO captures_labels (capture_id, label_id)
                    VALUES (?, ?)
                """, (capture_id, label_id))
        
        self.conn.commit()
        return capture_id
    
    def save_summary(
        self,
        summary_type: str,
        start_time: datetime,
        end_time: datetime,
        content: str,
        video_path: Optional[str] = None
    ) -> int:
        """
        Save a time-based summary (5-minute, hourly, etc).
        
        Args:
            summary_type: Type of summary ('5min', 'hourly', 'daily')
            start_time: Start of summary period
            end_time: End of summary period
            content: Summary text content
            video_path: Optional path to time-lapse video for this period
        
        Returns:
            int: ID of the inserted summary
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO summaries (summary_type, start_time, end_time, content, video_path)
            VALUES (?, ?, ?, ?, ?)
        """, (summary_type, start_time.isoformat(), end_time.isoformat(), content, video_path))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_summary_video_path(self, summary_id: int, video_path: str) -> None:
        """
        Update the video path for an existing summary.
        
        Args:
            summary_id: ID of the summary to update
            video_path: Path to the video file
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE summaries
            SET video_path = ?
            WHERE id = ?
        """, (video_path, summary_id))
        self.conn.commit()
    
    def cleanup_screenshots_except_thumbnails(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Keep only the first screenshot per 5-minute window and delete the rest from disk.
        Returns information about what was kept and deleted.
        
        Args:
            start_time: Start of time range to clean
            end_time: End of time range to clean
        
        Returns:
            Dict with 'kept' and 'deleted' counts and thumbnail capture IDs
        """
        cursor = self.conn.cursor()
        
        # Get all captures in the time range, ordered by timestamp
        cursor.execute("""
            SELECT id, timestamp, screenshot
            FROM captures
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (start_time.isoformat(), end_time.isoformat()))
        
        captures = cursor.fetchall()
        
        if not captures:
            return {'kept': 0, 'deleted': 0, 'thumbnails': []}
        
        # Group captures into 5-minute windows and keep first of each
        thumbnails = []
        to_delete = []
        current_window_start = None
        
        for capture in captures:
            capture_time = datetime.fromisoformat(capture['timestamp'])
            
            # Calculate which 5-minute window this capture belongs to
            minutes = capture_time.minute
            window_minute = (minutes // 5) * 5
            window_start = capture_time.replace(minute=window_minute, second=0, microsecond=0)
            
            if current_window_start != window_start:
                # New window - keep this capture as thumbnail
                thumbnails.append(capture['id'])
                current_window_start = window_start
            else:
                # Same window - mark for deletion
                to_delete.append(capture['id'])
        
        # Delete screenshot blobs for non-thumbnail captures
        # We keep the capture records for data integrity, just NULL out the screenshot
        if to_delete:
            placeholders = ','.join('?' * len(to_delete))
            cursor.execute(f"""
                UPDATE captures
                SET screenshot = NULL
                WHERE id IN ({placeholders})
            """, to_delete)
            self.conn.commit()
        
        return {
            'kept': len(thumbnails),
            'deleted': len(to_delete),
            'thumbnails': thumbnails
        }
    
    def get_latest_summary(self, summary_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent summary of a given type.
        
        Args:
            summary_type: Type of summary to retrieve
        
        Returns:
            Dict with summary data, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, summary_type, start_time, end_time, content, created_at
            FROM summaries
            WHERE summary_type = ?
            ORDER BY end_time DESC
            LIMIT 1
        """, (summary_type,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_captures_since(
        self,
        since_time: datetime,
        include_screenshots: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all captures since a given time.
        
        Args:
            since_time: Get captures after this time
            include_screenshots: Whether to include screenshot blobs
        
        Returns:
            List of capture dictionaries with labels
        """
        cursor = self.conn.cursor()
        
        if include_screenshots:
            fields = "id, timestamp, screenshot, description, classification_raw, classification_error, created_at"
        else:
            fields = "id, timestamp, description, classification_raw, classification_error, created_at"
        
        cursor.execute(f"""
            SELECT {fields}
            FROM captures
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        """, (since_time.isoformat(),))
        
        captures = [dict(row) for row in cursor.fetchall()]
        
        # Get labels for each capture
        for capture in captures:
            cursor.execute("""
                SELECT l.name
                FROM labels l
                JOIN captures_labels cl ON l.id = cl.label_id
                WHERE cl.capture_id = ?
            """, (capture['id'],))
            capture['labels'] = [r['name'] for r in cursor.fetchall()]
        
        return captures
    
    def get_summaries_in_range(
        self,
        summary_type: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get summaries of a given type within a time range.
        
        Args:
            summary_type: Type of summaries to retrieve
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            List of summary dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, summary_type, start_time, end_time, content, created_at
            FROM summaries
            WHERE summary_type = ?
                AND start_time >= ?
                AND end_time <= ?
            ORDER BY start_time ASC
        """, (summary_type, start_time.isoformat(), end_time.isoformat()))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_capture(self, capture_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific capture by ID with its labels.
        
        Args:
            capture_id: ID of the capture to retrieve
        
        Returns:
            Dict with capture data including labels, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, screenshot, description, 
                   classification_raw, classification_error, created_at
            FROM captures
            WHERE id = ?
        """, (capture_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        capture = dict(row)
        
        # Get labels for this capture
        cursor.execute("""
            SELECT l.name
            FROM labels l
            JOIN captures_labels cl ON l.id = cl.label_id
            WHERE cl.capture_id = ?
        """, (capture_id,))
        
        capture['labels'] = [r['name'] for r in cursor.fetchall()]
        return capture
    
    def get_recent_captures(
        self,
        limit: int = 100,
        include_screenshots: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent captures with their labels.
        
        Args:
            limit: Maximum number of captures to return
            include_screenshots: Whether to include screenshot blobs (can be large)
        
        Returns:
            List of capture dictionaries with labels
        """
        cursor = self.conn.cursor()
        
        if include_screenshots:
            fields = "id, timestamp, screenshot, description, classification_raw, classification_error, created_at"
        else:
            fields = "id, timestamp, description, classification_raw, classification_error, created_at"
        
        cursor.execute(f"""
            SELECT {fields}
            FROM captures
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        captures = [dict(row) for row in cursor.fetchall()]
        
        # Get labels for each capture
        for capture in captures:
            cursor.execute("""
                SELECT l.name
                FROM labels l
                JOIN captures_labels cl ON l.id = cl.label_id
                WHERE cl.capture_id = ?
            """, (capture['id'],))
            capture['labels'] = [r['name'] for r in cursor.fetchall()]
        
        return captures
    
    def get_captures_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        include_screenshots: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve captures within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            include_screenshots: Whether to include screenshot blobs
        
        Returns:
            List of capture dictionaries
        """
        cursor = self.conn.cursor()
        
        if include_screenshots:
            fields = "id, timestamp, screenshot, classification, classification_raw, classification_error, created_at"
        else:
            fields = "id, timestamp, classification, classification_raw, classification_error, created_at"
        
        cursor.execute(f"""
            SELECT {fields}
            FROM captures
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        """, (start_date.isoformat(), end_date.isoformat()))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with statistics like total captures, date range, etc.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM captures")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT MIN(timestamp) as first, MAX(timestamp) as last FROM captures")
        dates = cursor.fetchone()
        
        cursor.execute("""
            SELECT SUM(LENGTH(screenshot)) as total_size 
            FROM captures
        """)
        total_size = cursor.fetchone()['total_size'] or 0
        
        return {
            "total_captures": total,
            "first_capture": dates['first'],
            "last_capture": dates['last'],
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

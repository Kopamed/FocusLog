"""
Web dashboard for FocusLog analytics and visualization.
"""

from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime, timedelta
from pathlib import Path
import sys
from collections import Counter, defaultdict
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from focuslogd.database import FocusLogDB

app = Flask(__name__)
DB_PATH = "focuslog.db"


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    """Get overall statistics."""
    with FocusLogDB(db_path=DB_PATH) as db:
        stats = db.get_statistics()
        
        # Get label counts
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT l.name, COUNT(*) as count
            FROM labels l
            JOIN captures_labels cl ON l.id = cl.label_id
            GROUP BY l.name
            ORDER BY count DESC
        """)
        label_counts = {row['name']: row['count'] for row in cursor.fetchall()}
        
        # Get total summaries
        cursor.execute("SELECT COUNT(*) as count FROM summaries WHERE summary_type = '5min'")
        five_min_summaries = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM summaries WHERE summary_type = 'hourly'")
        hourly_summaries = cursor.fetchone()['count']
        
        return jsonify({
            'total_captures': stats['total_captures'],
            'first_capture': stats['first_capture'],
            'last_capture': stats['last_capture'],
            'total_size_mb': stats['total_size_mb'],
            'total_labels': len(label_counts),
            'label_counts': label_counts,
            'five_min_summaries': five_min_summaries,
            'hourly_summaries': hourly_summaries
        })


@app.route('/api/timeline')
def get_timeline():
    """Get timeline data for visualization."""
    # Get date range from query params
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        
        if start_date and end_date:
            cursor.execute("""
                SELECT c.id, c.timestamp, l.name as label
                FROM captures c
                JOIN captures_labels cl ON c.id = cl.capture_id
                JOIN labels l ON cl.label_id = l.id
                WHERE c.timestamp BETWEEN ? AND ?
                ORDER BY c.timestamp ASC
            """, (start_date, end_date))
        else:
            # Last 24 hours by default
            cursor.execute("""
                SELECT c.id, c.timestamp, l.name as label
                FROM captures c
                JOIN captures_labels cl ON c.id = cl.capture_id
                JOIN labels l ON cl.label_id = l.id
                WHERE c.timestamp >= datetime('now', '-1 day')
                ORDER BY c.timestamp ASC
            """)
        
        timeline_data = []
        for row in cursor.fetchall():
            timeline_data.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'label': row['label']
            })
        
        return jsonify(timeline_data)


@app.route('/api/label_time')
def get_label_time():
    """Calculate time spent per label (15 seconds per capture)."""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        
        if start_date and end_date:
            cursor.execute("""
                SELECT l.name, COUNT(*) as count
                FROM captures c
                JOIN captures_labels cl ON c.id = cl.capture_id
                JOIN labels l ON cl.label_id = l.id
                WHERE c.timestamp BETWEEN ? AND ?
                GROUP BY l.name
                ORDER BY count DESC
            """, (start_date, end_date))
        else:
            cursor.execute("""
                SELECT l.name, COUNT(*) as count
                FROM captures c
                JOIN captures_labels cl ON c.id = cl.capture_id
                JOIN labels l ON cl.label_id = l.id
                WHERE c.timestamp >= datetime('now', '-1 day')
                GROUP BY l.name
                ORDER BY count DESC
            """)
        
        label_times = []
        for row in cursor.fetchall():
            # Each capture = 15 seconds
            seconds = row['count'] * 15
            minutes = seconds / 60
            hours = minutes / 60
            
            label_times.append({
                'label': row['name'],
                'count': row['count'],
                'seconds': seconds,
                'minutes': round(minutes, 1),
                'hours': round(hours, 2)
            })
        
        return jsonify(label_times)


@app.route('/api/heatmap')
def get_heatmap():
    """Get hourly activity heatmap data."""
    days = int(request.args.get('days', 7))
    
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                strftime('%H', timestamp) as hour,
                COUNT(*) as count
            FROM captures
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY date, hour
            ORDER BY date, hour
        """, (f'-{days}',))
        
        heatmap_data = []
        for row in cursor.fetchall():
            heatmap_data.append({
                'date': row['date'],
                'hour': int(row['hour']),
                'count': row['count']
            })
        
        return jsonify(heatmap_data)


@app.route('/api/recent_captures')
def get_recent_captures():
    """Get recent captures with labels and descriptions."""
    limit = int(request.args.get('limit', 20))
    
    with FocusLogDB(db_path=DB_PATH) as db:
        captures = db.get_recent_captures(limit=limit, include_screenshots=False)
        return jsonify(captures)


@app.route('/api/recent_summaries')
def get_recent_summaries():
    """Get recent summaries with video paths."""
    summary_type = request.args.get('type', 'all')
    limit = int(request.args.get('limit', 10))
    
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        
        if summary_type == 'all':
            cursor.execute("""
                SELECT id, summary_type, start_time, end_time, content, video_path
                FROM summaries
                ORDER BY end_time DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT id, summary_type, start_time, end_time, content, video_path
                FROM summaries
                WHERE summary_type = ?
                ORDER BY end_time DESC
                LIMIT ?
            """, (summary_type, limit))
        
        summaries = []
        for row in cursor.fetchall():
            summaries.append({
                'id': row['id'],
                'type': row['summary_type'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'content': row['content'],
                'video_path': row['video_path']
            })
        
        return jsonify(summaries)


@app.route('/api/video/<int:summary_id>')
def get_video(summary_id):
    """Serve video file for a specific summary."""
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT video_path
            FROM summaries
            WHERE id = ?
        """, (summary_id,))
        
        row = cursor.fetchone()
        if not row or not row['video_path']:
            return jsonify({'error': 'Video not found'}), 404
        
        video_path = Path(row['video_path'])
        
        # Make path absolute if it's relative
        if not video_path.is_absolute():
            video_path = Path(__file__).parent.parent.parent / video_path
        
        if not video_path.exists():
            return jsonify({'error': f'Video file not found on disk: {video_path}'}), 404
        
        return send_file(
            str(video_path),
            mimetype='video/mp4',
            as_attachment=False,
            download_name=video_path.name
        )


@app.route('/api/daily_summary')
def get_daily_summary():
    """Get summary for a specific day."""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    with FocusLogDB(db_path=DB_PATH) as db:
        cursor = db.conn.cursor()
        
        # Get all captures for the day
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM captures
            WHERE date(timestamp) = ?
        """, (date,))
        total_captures = cursor.fetchone()['count']
        
        # Get label distribution for the day
        cursor.execute("""
            SELECT l.name, COUNT(*) as count
            FROM captures c
            JOIN captures_labels cl ON c.id = cl.capture_id
            JOIN labels l ON cl.label_id = l.id
            WHERE date(c.timestamp) = ?
            GROUP BY l.name
            ORDER BY count DESC
        """, (date,))
        
        labels = []
        for row in cursor.fetchall():
            labels.append({
                'name': row['name'],
                'count': row['count'],
                'minutes': round((row['count'] * 15) / 60, 1)
            })
        
        # Get hourly summaries for the day
        cursor.execute("""
            SELECT start_time, end_time, content
            FROM summaries
            WHERE summary_type = 'hourly'
                AND date(start_time) = ?
            ORDER BY start_time ASC
        """, (date,))
        
        hourly_summaries = []
        for row in cursor.fetchall():
            hourly_summaries.append({
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'content': row['content']
            })
        
        return jsonify({
            'date': date,
            'total_captures': total_captures,
            'total_minutes': round((total_captures * 15) / 60, 1),
            'labels': labels,
            'hourly_summaries': hourly_summaries
        })


if __name__ == '__main__':
    app.run(debug=True, port=5000)

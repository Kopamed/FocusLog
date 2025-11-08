#!/usr/bin/env python3
"""
FocusLog Daemon - Automated screenshot capture and classification service.

This daemon captures screenshots every 15 seconds, classifies them using OpenAI,
and stores both the screenshot and classification in a SQLite database.
"""

import sys
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import argparse
import os
import threading

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from focuslogd.capture import GrimCapture
from focuslogd.classifier import ScreenshotClassifier
from focuslogd.database import FocusLogDB
from focuslogd.summarizer import SummaryGenerator
from focuslogd.video_generator import VideoGenerator


class FocusLogDaemon:
    """Main daemon service for automated screenshot capture and classification."""
    
    def __init__(
        self,
        interval: int = 15,
        db_path: str = "focuslog.db",
        api_key: Optional[str] = None,
        classification_prompt: Optional[str] = None,
        model: str = "gpt-5-mini"
    ):
        """
        Initialize the FocusLog daemon.
        
        Args:
            interval: Screenshot capture interval in seconds (default: 15)
            db_path: Path to SQLite database file
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            classification_prompt: Custom classification prompt
            model: OpenAI model to use
        """
        self.interval = interval
        self.running = False
        self.classification_prompt = classification_prompt
        
        # Initialize components
        print("Initializing FocusLog daemon...")
        
        try:
            self.capture = GrimCapture()
            print("✓ Screenshot capture initialized (grim)")
        except RuntimeError as e:
            print(f"✗ Screenshot capture failed: {e}")
            sys.exit(1)
        
        try:
            self.classifier = ScreenshotClassifier(api_key=api_key, model=model)
            print(f"✓ OpenAI classifier initialized (model: {model})")
        except ValueError as e:
            print(f"✗ Classifier initialization failed: {e}")
            sys.exit(1)
        
        try:
            self.summarizer = SummaryGenerator(api_key=api_key, model=model)
            print(f"✓ Summary generator initialized")
        except ValueError as e:
            print(f"✗ Summarizer initialization failed: {e}")
            sys.exit(1)
        
        try:
            self.video_generator = VideoGenerator(fps=30)
            print(f"✓ Video generator initialized (30 fps)")
        except RuntimeError as e:
            print(f"✗ Video generator failed: {e}")
            sys.exit(1)
        
        self.db = FocusLogDB(db_path=db_path)
        print(f"✓ Database initialized ({db_path})")
        
        # Create videos directory
        self.videos_dir = Path("videos")
        self.videos_dir.mkdir(exist_ok=True)
        print(f"✓ Videos directory: {self.videos_dir.absolute()}")
        
        # Initialize summary tracking based on last summary in DB
        last_5min = self.db.get_latest_summary('5min')
        last_hourly = self.db.get_latest_summary('hourly')
        
        self.last_5min_summary = (
            datetime.fromisoformat(last_5min['end_time']) if last_5min 
            else datetime.now() - timedelta(minutes=5)  # Start fresh if no summaries
        )
        self.last_hourly_summary = (
            datetime.fromisoformat(last_hourly['end_time']) if last_hourly
            else datetime.now() - timedelta(hours=1)  # Start fresh if no summaries
        )
        
        print(f"  Last 5-min summary: {self.last_5min_summary.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Last hourly summary: {self.last_hourly_summary.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n\nReceived signal {signum}. Shutting down gracefully...")
        self.stop()
    
    def _classify_and_save(
        self, 
        screenshot_data: bytes, 
        timestamp: datetime,
        capture_num: int
    ) -> None:
        """Classify screenshot and save to database (runs in background thread)."""
        try:
            # Get existing labels and last summary for context
            existing_labels = self.db.get_all_labels()
            last_summary_data = self.db.get_latest_summary('5min')
            last_summary = last_summary_data['content'] if last_summary_data else None
            
            # Classify screenshot
            print(f"[{timestamp.strftime('%H:%M:%S')}] #{capture_num} Classifying...", end=" ", flush=True)
            result = self.classifier.classify(
                screenshot_data,
                existing_labels=existing_labels,
                last_summary=last_summary
            )
            
            if result["success"]:
                labels = result["labels"]
                description = result["description"]
                
                # Display labels
                labels_str = ", ".join(labels)
                print(f"✓ [{labels_str}]")
                print(f"  Description: {description[:80]}..." if len(description) > 80 else f"  Description: {description}")
                
                # Save to database (labels will be auto-created if new)
                capture_id = self.db.save_capture(
                    screenshot=screenshot_data,
                    description=description,
                    labels=labels,
                    classification_raw=result["raw_response"],
                    timestamp=timestamp
                )
                print(f"  → Saved to database (ID: {capture_id})")
            else:
                error = result["error"]
                print(f"✗ Error: {error}")
                
                # Save to database with error
                self.db.save_capture(
                    screenshot=screenshot_data,
                    classification_error=error,
                    timestamp=timestamp
                )
        except Exception as e:
            print(f"✗ Classification thread error: {e}")
            import traceback
            traceback.print_exc()
    
    def _capture_and_classify(self, capture_num: int) -> None:
        """Capture a screenshot and fire off classification in background."""
        timestamp = datetime.now()
        
        # Capture screenshot
        print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Capturing screenshot...", end=" ", flush=True)
        screenshot_data = self.capture.capture()
        
        if screenshot_data is None:
            print("✗ Failed")
            # Still save to DB with error
            self.db.save_capture(
                screenshot=b"",
                classification_error="Screenshot capture failed",
                timestamp=timestamp
            )
            return
        
        screenshot_size_kb = len(screenshot_data) / 1024
        print(f"✓ ({screenshot_size_kb:.1f} KB)")
        
        # Fire off classification in background thread (non-blocking)
        thread = threading.Thread(
            target=self._classify_and_save,
            args=(screenshot_data, timestamp, capture_num),
            daemon=True
        )
        thread.start()
    
    def _generate_5min_summary(self) -> None:
        """Generate a 5-minute summary in background thread."""
        try:
            now = datetime.now()
            start_time = self.last_5min_summary
            
            print(f"\n5min {start_time.isoformat()} → {now.isoformat()}")
            
            # Get captures from last 5 minutes
            captures = self.db.get_captures_since(start_time, include_screenshots=False)
            
            if not captures:
                print("  No captures to summarize")
                self.last_5min_summary = now
                return
            
            # Generate summary
            summary = self.summarizer.generate_5min_summary(captures)
            
            # Check if summary generation failed
            if summary.startswith("Error generating summary:"):
                print(f"  ✗ {summary}")
                # Don't update last_5min_summary on failure - will retry next time
                return
            
            # Save to database
            summary_id = self.db.save_summary(
                summary_type='5min',
                start_time=start_time,
                end_time=now,
                content=summary
            )
            
            print(f"  ✓ 5-min summary saved (ID: {summary_id})")
            print(f"  Summary: {summary[:100]}..." if len(summary) > 100 else f"  Summary: {summary}")
            
            self.last_5min_summary = now
            
        except Exception as e:
            print(f"  ✗ Error generating 5-min summary: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_hourly_summary(self) -> None:
        """Generate an hourly summary and video in background thread."""
        try:
            now = datetime.now()
            start_time = self.last_hourly_summary
            
            print(f"\n[{now.strftime('%H:%M:%S')}] Generating hourly summary and video...")
            
            # Get 5-min summaries from last hour
            five_min_summaries = self.db.get_summaries_in_range(
                summary_type='5min',
                start_time=start_time,
                end_time=now
            )
            
            if not five_min_summaries:
                print("  No 5-min summaries to aggregate")
                self.last_hourly_summary = now
                return
            
            # Generate text summary
            summary = self.summarizer.generate_hourly_summary(five_min_summaries)
            
            # Check if summary generation failed
            if summary.startswith("Error generating summary:"):
                print(f"  ✗ {summary}")
                # Don't update last_hourly_summary on failure - will retry next time
                return
            
            # Generate video from captures
            captures = self.db.get_captures_since(start_time, include_screenshots=True)
            video_path = None
            
            if captures:
                print(f"  Creating video from {len(captures)} captures...")
                
                # Save screenshots to temp files for ffmpeg
                import tempfile
                temp_dir = Path(tempfile.mkdtemp(prefix="focuslog_"))
                screenshot_paths = []
                
                try:
                    for i, capture in enumerate(captures):
                        if capture.get('screenshot'):
                            temp_path = temp_dir / f"capture_{i:05d}.png"
                            temp_path.write_bytes(capture['screenshot'])
                            screenshot_paths.append(str(temp_path))
                    
                    if screenshot_paths:
                        # Generate video filename
                        video_filename = f"focuslog_{start_time.strftime('%Y%m%d_%H%M%S')}.mp4"
                        video_path_full = self.videos_dir / video_filename
                        
                        # Create video
                        success = self.video_generator.generate_video(
                            screenshot_paths,
                            str(video_path_full)
                        )
                        
                        if success:
                            video_path = str(video_path_full)
                            print(f"  ✓ Video saved: {video_path}")
                        else:
                            print(f"  ✗ Video generation failed")
                    
                finally:
                    # Cleanup temp files
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Save summary to database
            summary_id = self.db.save_summary(
                summary_type='hourly',
                start_time=start_time,
                end_time=now,
                content=summary,
                video_path=video_path
            )
            
            print(f"  ✓ Hourly summary saved (ID: {summary_id})")
            print(f"  Summary: {summary[:100]}..." if len(summary) > 100 else f"  Summary: {summary}")
            
            # Cleanup screenshots - keep only 1 per 5 minutes
            print(f"  Cleaning up screenshots (keeping 1 per 5 minutes)...")
            cleanup_result = self.db.cleanup_screenshots_except_thumbnails(start_time, now)
            print(f"  ✓ Kept {cleanup_result['kept']} thumbnails, removed {cleanup_result['deleted']} screenshots")
            
            self.last_hourly_summary = now
            
        except Exception as e:
            print(f"  ✗ Error generating hourly summary: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_and_generate_summaries(self) -> None:
        """Check if it's time to generate summaries and fire them off."""
        now = datetime.now()
        
        # Check for 5-minute summary (every 5 minutes)
        time_since_5min = (now - self.last_5min_summary).total_seconds()
        if time_since_5min >= 300:  # 5 minutes = 300 seconds
            thread = threading.Thread(
                target=self._generate_5min_summary,
                daemon=True
            )
            thread.start()
        
        # Check for hourly summary (every 60 minutes)
        time_since_hourly = (now - self.last_hourly_summary).total_seconds()
        if time_since_hourly >= 3600:  # 60 minutes = 3600 seconds
            thread = threading.Thread(
                target=self._generate_hourly_summary,
                daemon=True
            )
            thread.start()
    
    def run(self) -> None:
        """Start the daemon main loop."""
        self.running = True
        
        print(f"\n{'='*60}")
        print(f"FocusLog daemon started")
        print(f"Capture interval: {self.interval} seconds")
        print(f"Press Ctrl+C to stop")
        print(f"{'='*60}\n")
        
        # Show database stats
        stats = self.db.get_statistics()
        if stats['total_captures'] > 0:
            print(f"Existing captures: {stats['total_captures']} "
                  f"({stats['total_size_mb']} MB)")
            print(f"Date range: {stats['first_capture']} to {stats['last_capture']}\n")
        
        iteration = 0
        next_capture_time = time.time()
        
        while self.running:
            try:
                iteration += 1
                
                # Wait until it's time for the next capture
                now = time.time()
                if now < next_capture_time:
                    sleep_time = next_capture_time - now
                    print(f"Waiting {sleep_time:.1f} seconds until next capture...")
                    time.sleep(sleep_time)
                
                print(f"\n--- Capture #{iteration} ---")
                
                # Schedule next capture BEFORE processing (ensures exact intervals)
                next_capture_time = time.time() + self.interval
                
                # Capture and classify (classification happens in background thread)
                self._capture_and_classify(iteration)
                
                # Check if we need to generate summaries
                self._check_and_generate_summaries()
                    
            except Exception as e:
                print(f"Unexpected error in main loop: {e}")
                import traceback
                traceback.print_exc()
                # Still maintain the schedule even on error
                next_capture_time = time.time() + self.interval
    
    def stop(self) -> None:
        """Stop the daemon."""
        self.running = False
        print("\nStopping daemon...")
        
        # Show final stats
        stats = self.db.get_statistics()
        print(f"\nFinal statistics:")
        print(f"  Total captures: {stats['total_captures']}")
        print(f"  Database size: {stats['total_size_mb']} MB")
        
        self.db.close()
        print("Database closed. Goodbye!")


def main():
    """Main entry point for the daemon."""
    parser = argparse.ArgumentParser(
        description="FocusLog - Automated screenshot capture and classification daemon"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=15,
        help="Screenshot capture interval in seconds (default: 15)"
    )
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="focuslog.db",
        help="Path to SQLite database file (default: focuslog.db)"
    )
    parser.add_argument(
        "-k", "--api-key",
        type=str,
        help="OpenAI API key (or set OPENAI_API_KEY environment variable)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="gpt-5-mini",
        help="OpenAI model to use (default: gpt-5-mini)"
    )
    parser.add_argument(
        "-p", "--prompt-file",
        type=str,
        help="Path to file containing custom classification prompt"
    )
    
    args = parser.parse_args()
    
    # Load custom prompt if provided
    classification_prompt = None
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if prompt_path.exists():
            classification_prompt = prompt_path.read_text()
            print(f"Loaded custom classification prompt from {args.prompt_file}")
        else:
            print(f"Warning: Prompt file {args.prompt_file} not found, using default")
    
    # Create and run daemon
    daemon = FocusLogDaemon(
        interval=args.interval,
        db_path=args.database,
        api_key=args.api_key,
        classification_prompt=classification_prompt,
        model=args.model
    )
    
    daemon.run()


if __name__ == "__main__":
    main()

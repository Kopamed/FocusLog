"""
Video generation for FocusLog captures.
Creates time-lapse videos from hourly screenshot captures.
"""

import subprocess
import os
import tempfile
from pathlib import Path
from typing import List
import shutil


class VideoGenerator:
    """Generates time-lapse videos from screenshot sequences."""
    
    def __init__(self, fps: int = 30):
        """
        Initialize the video generator.
        
        Args:
            fps: Frames per second for output video (default: 30)
        """
        self.fps = fps
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check if ffmpeg is installed."""
        if not shutil.which('ffmpeg'):
            raise RuntimeError(
                "ffmpeg not found. Please install it:\n"
                "  Ubuntu/Debian: sudo apt install ffmpeg\n"
                "  Fedora: sudo dnf install ffmpeg\n"
                "  Arch: sudo pacman -S ffmpeg"
            )
    
    def generate_video(self, screenshot_paths: List[str], output_path: str) -> bool:
        """
        Generate a time-lapse video from screenshots.
        
        Args:
            screenshot_paths: List of absolute paths to screenshot files (in chronological order)
            output_path: Absolute path for output video file (should end in .mp4)
        
        Returns:
            True if successful, False otherwise
        """
        if not screenshot_paths:
            print("No screenshots provided for video generation")
            return False
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Create temporary directory for symlinked files
        with tempfile.TemporaryDirectory() as temp_dir:
            # ffmpeg requires sequential numbered files (frame001.png, frame002.png, etc.)
            # Create symlinks with proper naming
            for i, src_path in enumerate(screenshot_paths, 1):
                if not os.path.exists(src_path):
                    print(f"Warning: Screenshot not found: {src_path}")
                    continue
                
                # Use zero-padded numbers for proper sorting
                link_name = f"frame{i:05d}.png"
                link_path = os.path.join(temp_dir, link_name)
                os.symlink(src_path, link_path)
            
            # Count actual frames
            frame_count = len(os.listdir(temp_dir))
            if frame_count == 0:
                print("No valid screenshots found for video generation")
                return False
            
            print(f"Generating video from {frame_count} frames at {self.fps} fps...")
            
            # Build ffmpeg command
            # -framerate: input framerate
            # -i: input pattern
            # -c:v libx264: use H.264 codec
            # -pix_fmt yuv420p: pixel format for compatibility
            # -crf 23: quality (lower = better, 23 is default)
            # -y: overwrite output file
            cmd = [
                'ffmpeg',
                '-framerate', str(self.fps),
                '-i', os.path.join(temp_dir, 'frame%05d.png'),
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-crf', '23',
                '-y',  # Overwrite output file
                output_path
            ]
            
            try:
                # Run ffmpeg with suppressed output
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                
                # Verify output file was created
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"Video generated successfully: {output_path} ({file_size / 1024 / 1024:.2f} MB)")
                    return True
                else:
                    print("Video generation failed: output file not created")
                    return False
                
            except subprocess.CalledProcessError as e:
                print(f"ffmpeg error: {e.stderr}")
                return False
            except Exception as e:
                print(f"Video generation error: {e}")
                return False
    
    def get_video_duration(self, frame_count: int) -> float:
        """
        Calculate video duration in seconds.
        
        Args:
            frame_count: Number of frames in video
        
        Returns:
            Duration in seconds
        """
        return frame_count / self.fps

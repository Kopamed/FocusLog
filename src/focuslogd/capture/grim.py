import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .base import CaptureStrategy


class GrimCapture(CaptureStrategy):
    """Screenshot capture using grim (Wayland screenshot utility)."""
    
    def __init__(self):
        """Initialize the Grim capture strategy."""
        self._check_grim_available()
    
    def _check_grim_available(self) -> None:
        """Check if grim is installed and available."""
        try:
            subprocess.run(
                ["which", "grim"],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError:
            raise RuntimeError(
                "grim is not installed. Please install it: "
                "sudo apt install grim (Debian/Ubuntu) or sudo pacman -S grim (Arch)"
            )
    
    def capture(self) -> Optional[bytes]:
        """
        Capture a screenshot using grim.
        
        Returns:
            bytes: PNG image data, or None if capture failed
        """
        try:
            # Create a temporary file for the screenshot
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            # Capture screenshot with grim
            result = subprocess.run(
                ["grim", tmp_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Read the image data
            with open(tmp_path, 'rb') as f:
                image_data = f.read()
            
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
            return image_data
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to capture screenshot: {e.stderr}")
            return None
        except subprocess.TimeoutExpired:
            print("Screenshot capture timed out")
            return None
        except Exception as e:
            print(f"Unexpected error during screenshot capture: {e}")
            return None

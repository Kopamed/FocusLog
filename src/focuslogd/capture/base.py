from abc import ABC, abstractmethod
from typing import Optional


class CaptureStrategy(ABC):
    """Abstract base class for screenshot capture strategies."""
    
    @abstractmethod
    def capture(self) -> Optional[bytes]:
        """
        Capture a screenshot and return the image data as bytes.
        
        Returns:
            bytes: PNG image data, or None if capture failed
        """
        pass
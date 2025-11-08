import base64
from typing import Optional, Dict, Any, List
import os

from openai import OpenAI
from pydantic import BaseModel, Field


class ActivityClassification(BaseModel):
    """Structured response for screenshot classification."""
    labels: List[str] = Field(
        description="List of activity labels. Can use existing labels or create new ones. Multiple labels can be assigned."
    )
    description: str = Field(
        description="Detailed description of what the user is doing in this screenshot (2-3 sentences)."
    )


class ScreenshotClassifier:
    """Classifies screenshots using OpenAI's vision API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-5-mini"):
        """
        Initialize the classifier.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env variable
            model: OpenAI model to use (default: gpt-5-mini for cost efficiency)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def classify(
        self,
        image_data: bytes,
        existing_labels: List[str],
        last_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a screenshot using OpenAI's vision API with structured output.
        
        Args:
            image_data: PNG image data as bytes
            existing_labels: List of existing label names from database
            last_summary: Last 5-minute summary for context (optional)
        
        Returns:
            Dict containing:
                - success: bool indicating if classification succeeded
                - labels: List[str] with activity labels
                - description: str with detailed description
                - raw_response: str with full API response
                - error: str with error message (if success is False)
        """
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Build prompt with existing labels and context
            prompt = f"""Analyze this screenshot and classify the user's activity.

EXISTING LABELS: {', '.join(existing_labels) if existing_labels else 'None yet - create new ones'}

You can:
- Use existing labels if they fit
- Create new labels if needed
- Assign MULTIPLE labels (activities can overlap, e.g., "meeting" + "reading_documentation")

Provide:
1. Labels for this activity (multiple allowed)
2. Detailed description of what the user is doing (2-3 sentences)"""

            if last_summary:
                prompt += f"\n\nLAST 5-MIN SUMMARY (for context):\n{last_summary}"
            
            # Use structured outputs with Pydantic via responses.parse
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                response_format=ActivityClassification,
            )
            
            result = completion.choices[0].message.parsed
            
            return {
                "success": True,
                "labels": result.labels,
                "description": result.description,
                "raw_response": completion.model_dump_json(),
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "labels": [],
                "description": None,
                "raw_response": None,
                "error": str(e)
            }

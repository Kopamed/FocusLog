"""
Summary generation for FocusLog captures.
Creates hierarchical summaries: 5-minute → hourly summaries.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os


class SummaryGenerator:
    """Generates summaries of activity captures."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize the summary generator.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env variable
            model: OpenAI model to use (default: gpt-4o-mini)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        print(f"[SummaryGenerator] Using model: {model}")
    
    def generate_5min_summary(self, captures: List[Dict[str, Any]]) -> str:
        """
        Generate a 5-minute summary from recent captures.
        
        Args:
            captures: List of capture dicts with 'labels', 'description', 'timestamp'
        
        Returns:
            Summary text
        """
        if not captures:
            return "No activity captured in this period."
        
        # Build context from captures
        context_parts = []
        for i, cap in enumerate(captures, 1):
            labels_str = ", ".join(cap.get('labels', []))
            desc = cap.get('description', 'No description')
            timestamp = cap.get('timestamp', '')
            context_parts.append(f"{i}. [{timestamp}] Labels: {labels_str}\n   {desc}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Summarize the user's activity over the last 5 minutes based on these {len(captures)} screenshots.

CAPTURES:
{context}

Create a concise 2-3 sentence summary that:
1. Identifies the main activities
2. Notes any transitions or context switches
3. Mentions productivity level if clear

Be specific and actionable."""
        
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are an activity summarization assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            if not hasattr(response, 'status'):
                return f"Error generating summary: Invalid response object"
            
            if response.status != "completed":
                return f"Error generating summary: Response status {response.status}"
            
            # Safely check for refusal
            if hasattr(response, 'output') and response.output:
                if len(response.output) > 0:
                    first_msg = response.output[0]
                    if hasattr(first_msg, 'content') and first_msg.content and len(first_msg.content) > 0:
                        first_content = first_msg.content[0]
                        if hasattr(first_content, 'type') and first_content.type == "refusal":
                            return f"Error generating summary: {first_content.refusal}"
            
            if not hasattr(response, 'output_text'):
                return "Error generating summary: No output_text in response"
            
            content = response.output_text
            if content is None or content == "":
                return "Error generating summary: API returned empty content"
            return content.strip()
        
        except Exception as e:
            import traceback
            return f"Error generating summary: {e}\n{traceback.format_exc()}"
    
    def generate_hourly_summary(self, five_min_summaries: List[Dict[str, Any]]) -> str:
        """
        Generate an hourly summary from 5-minute summaries.
        
        Args:
            five_min_summaries: List of summary dicts with 'content', 'start_time', 'end_time'
        
        Returns:
            Summary text
        """
        if not five_min_summaries:
            return "No activity captured in this hour."
        
        # Build context from 5-min summaries
        context_parts = []
        for i, summary in enumerate(five_min_summaries, 1):
            start = summary.get('start_time', '')
            end = summary.get('end_time', '')
            content = summary.get('content', '')
            context_parts.append(f"{i}. [{start} to {end}]\n   {content}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Summarize the user's activity over the last hour based on these {len(five_min_summaries)} 5-minute summaries.

5-MINUTE SUMMARIES:
{context}

Create a comprehensive 3-5 sentence hourly summary that:
1. Identifies main work/activity themes
2. Notes productivity patterns and focus areas
3. Highlights any significant transitions or breaks
4. Provides actionable insights

Be specific about what was accomplished or focused on."""
        
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are an activity summarization assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            if not hasattr(response, 'status'):
                return f"Error generating summary: Invalid response object"
            
            if response.status != "completed":
                return f"Error generating summary: Response status {response.status}"
            
            # Safely check for refusal
            if hasattr(response, 'output') and response.output:
                if len(response.output) > 0:
                    first_msg = response.output[0]
                    if hasattr(first_msg, 'content') and first_msg.content and len(first_msg.content) > 0:
                        first_content = first_msg.content[0]
                        if hasattr(first_content, 'type') and first_content.type == "refusal":
                            return f"Error generating summary: {first_content.refusal}"
            
            if not hasattr(response, 'output_text'):
                return "Error generating summary: No output_text in response"
            
            content = response.output_text
            if content is None or content == "":
                return "Error generating summary: API returned empty content"
            return content.strip()
        
        except Exception as e:
            import traceback
            return f"Error generating summary: {e}\n{traceback.format_exc()}"

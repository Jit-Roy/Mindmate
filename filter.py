import random
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from models import MentalHealthTopicFilter, ChatResponse
from config import config


class MentalHealthFilter:
    """Filter to ensure conversations stay focused on mental health topics."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.3  # Lower temperature for more consistent filtering
        )
    
    def filter(self, message: str) -> MentalHealthTopicFilter:
        """Analyze message for mental health relevance with confidence and reason."""
        
        system_prompt = """You are a mental health topic classifier for a therapeutic chatbot named MyBro. 

        Determine if the message is mental health related:
        MENTAL HEALTH RELATED includes:
        - Emotions and feelings (sad, happy, anxious, stressed, angry, excited, etc.)
        - Mental health conditions and symptoms
        - Life challenges, struggles, and personal issues
        - Relationships, family, and social problems  
        - Work stress, school pressure, life changes
        - Sleep, self-care, and wellness topics
        - Personal growth, therapy, and healing
        - Greetings and check-ins ("Hi", "Hello", "How are you?")
        - Conversation continuity ("Do you remember me?", "We talked before")
        - Any personal questions that could lead to emotional support
        - Casual conversation that builds therapeutic rapport

        Respond EXACTLY in this format:
        MENTAL_HEALTH: YES/NO
        CONFIDENCE: 0.1-1.0
        REASON: [brief explanation]"""
                
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this message: '{message}'")
        ]
        
        response = self.llm.invoke(messages)
        response_text = response.content.strip()
        
        # Parse the response
        lines = response_text.split('\n')
        is_mental_health = None
        confidence = None
        reason = None
        
        for line in lines:
            if line.startswith("MENTAL_HEALTH:"):
                is_mental_health = "YES" in line.upper()
            elif line.startswith("CONFIDENCE:"):
                confidence = float(line.split(":", 1)[1].strip())
                confidence = max(0.1, min(1.0, confidence))
            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
        
        # Raise error if any required field is missing
        if is_mental_health is None:
            raise ValueError("MENTAL_HEALTH field not found in LLM response")
        if confidence is None:
            raise ValueError("CONFIDENCE field not found in LLM response")
        if reason is None:
            raise ValueError("REASON field not found in LLM response")
        
        return MentalHealthTopicFilter(
            is_mental_health_related=is_mental_health,
            confidence_score=confidence,
            reason=reason
        )
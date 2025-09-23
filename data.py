from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Tracks important upcoming events mentioned in conversation."""
    eventType: str  # 'exam', 'interview', 'appointment'
    description: str  
    eventDate: Optional[str] = None 
    mentionedAt: str = Field(default_factory=lambda: datetime.now().isoformat())  
    followUpNeeded: bool = True
    followUpDone: bool = False


class UserProfile(BaseModel):
    """User profile information for personalization."""
    name: Optional[str] = None
    username: Optional[str] = None
    age: Optional[int] = None  
    gender: Optional[str] = None
    avatar: Optional[int] = None


class UserMessage(BaseModel):
    """User message in a conversation."""
    content: str
    emotion_detected: Optional[str] = None
    urgency_level: Optional[int] = Field(default=1, ge=1, le=5)


class LLMMessage(BaseModel):
    """LLM response message in a conversation."""
    content: str
    suggestions: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)


class MessagePair(BaseModel):
    """One message pair containing both user message and LLM response."""
    user_message: UserMessage
    llm_message: LLMMessage
    timestamp: datetime = Field(default_factory=datetime.now) 
    conversation_id: Optional[str] = None


class ConversationMemory(BaseModel):
    """Memory structure for conversation history."""
    conversation_id: str
    chat: List[MessagePair] = Field(default_factory=list)
    summary: str = ""
    key_topics: List[str] = Field(default_factory=list)


class MentalHealthTopicFilter(BaseModel):
    """Filter for mental health related topics."""
    is_mental_health_related: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    reason: str = ""
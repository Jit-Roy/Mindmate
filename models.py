from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile information for personalization."""
    user_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    preferred_name: Optional[str] = None
    mental_health_concerns: List[str] = Field(default_factory=list)
    support_preferences: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_interaction: datetime = Field(default_factory=datetime.now)


class ConversationMessage(BaseModel):
    """Individual message in a conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    emotion_detected: Optional[str] = None
    urgency_level: Optional[int] = Field(default=1, ge=1, le=5)


class ConversationMemory(BaseModel):
    """Memory structure for conversation history."""
    conversation_id: str
    user_id: str
    messages: List[ConversationMessage] = Field(default_factory=list)
    summary: str = ""
    key_topics: List[str] = Field(default_factory=list)
    user_mood_trend: List[Dict[str, Any]] = Field(default_factory=list)
    important_details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ChatResponse(BaseModel):
    """Response from the chatbot."""
    message: str
    emotion_tone: str
    suggestions: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    urgency_detected: bool = False
    professional_help_suggested: bool = False


class MentalHealthTopicFilter(BaseModel):
    """Filter for mental health related topics."""
    is_mental_health_related: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    detected_topics: List[str] = Field(default_factory=list)
    reason: str = ""

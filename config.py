import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Config(BaseModel):
    """Configuration settings for the mental health chatbot."""
    
    # Gemini API Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    model_name: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1000"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    
    # Memory Configuration
    max_conversation_history: int = 50
    summary_trigger_length: int = 20
    
    # Mental Health Configuration
    mental_health_keywords: list = [
        "depression", "anxiety", "stress", "mental health", "mood", "emotional",
        "therapy", "counseling", "suicide", "self-harm", "panic", "trauma",
        "bipolar", "ptsd", "ocd", "adhd", "eating disorder", "addiction",
        "grief", "loss", "loneliness", "anger", "fear", "worry", "sad",
        "happy", "frustrated", "overwhelmed", "exhausted", "hopeless",
        "support", "coping", "meditation", "mindfulness", "self-care",
        "relationship", "family", "work stress", "burnout", "sleep",
        "insomnia", "confidence", "self-esteem", "motivation", "purpose"
    ]
    
    non_mental_health_responses: list = [
        "I'm here to support you with mental health and emotional well-being. Let's talk about how you're feeling today instead.",
        "I focus on mental health support. Is there something on your mind that's bothering you?",
        "As your mental health companion, I'd rather chat about your emotional well-being. What's going on in your life?",
        "I'm designed to help with mental health concerns. How are you doing emotionally today?",
        "Let's keep our conversation focused on your mental well-being. What's on your mind, bro?"
    ]
    
    class Config:
        env_file = ".env"


# Global config instance
config = Config()

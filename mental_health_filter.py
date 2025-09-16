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
        
        self.emotion_keywords = {
            "anxious": ["anxious", "worried", "nervous", "panic", "fear"],
            "depressed": ["sad", "depressed", "hopeless", "empty", "worthless"],
            "angry": ["angry", "frustrated", "mad", "furious", "irritated"],
            "happy": ["happy", "joy", "excited", "cheerful", "positive"],
            "stressed": ["stressed", "overwhelmed", "pressure", "tense"],
            "lonely": ["lonely", "alone", "isolated", "disconnected"],
            "confused": ["confused", "lost", "uncertain", "unclear"],
            "grateful": ["grateful", "thankful", "appreciate", "blessed"]
        }
    
    def is_mental_health_related(self, message: str) -> MentalHealthTopicFilter:
        """Determine if a message is related to mental health using Gemini API."""
        
        # Use Gemini API for comprehensive mental health topic detection
        system_prompt = """You are a mental health topic classifier for a therapeutic chatbot named MyBro. Your job is to determine if ANY message could be part of a valid mental health conversation or therapeutic relationship.

MENTAL HEALTH RELATED includes:
- Emotions and feelings (sad, happy, anxious, stressed, angry, excited, etc.)
- Mental health conditions and symptoms
- Life challenges, struggles, and personal issues
- Relationships, family, and social problems  
- Work stress, school pressure, life changes
- Sleep, self-care, and wellness topics
- Personal growth, therapy, and healing
- Greetings and check-ins ("Hi", "Hello", "How are you?") - these are valid starts to mental health conversations
- Conversation continuity ("Do you remember me?", "We talked before", "Last time...")
- Any personal questions that could lead to emotional support
- Casual conversation that builds therapeutic rapport
- Questions about the AI's memory or previous interactions

BE VERY INCLUSIVE - Mental health support often starts with simple interactions like:
- "Hi" - someone reaching out for connection
- "How's it going?" - checking in on well-being  
- "Remember me?" - maintaining therapeutic relationship
- "What's up?" - casual opening to deeper conversation

ONLY classify as NON-mental health if it's clearly:
- Pure academic/factual questions with no personal element ("What's the capital of France?")
- Technical instructions unrelated to well-being ("How do I code in Python?")
- Commercial/business inquiries
- Spam or completely unrelated content

IMPORTANT: When in doubt, classify as MENTAL HEALTH RELATED. It's better to be inclusive than to block someone seeking support.

Respond with only 'YES' or 'NO' and a brief reason (max 20 words)."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Is this mental health related: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip().upper()
            
            is_related = response_text.startswith('YES')
            confidence = 0.7 if is_related else 0.3
            
            return MentalHealthTopicFilter(
                is_mental_health_related=is_related,
                confidence_score=confidence,
                detected_topics=[],
                reason=response.content
            )
            
        except Exception as e:
            print(f"Error in LLM filtering: {e}")
            # Fallback to conservative approach
            return MentalHealthTopicFilter(
                is_mental_health_related=False,
                confidence_score=0.1,
                detected_topics=[],
                reason="Error in classification, defaulting to non-mental health"
            )
    
    def get_redirect_response(self) -> str:
        """Get a friendly response to redirect non-mental health conversations."""
        return random.choice(config.non_mental_health_responses)
    
    def detect_emotion(self, message: str) -> tuple[str, int]:
        """Detect primary emotion and urgency level (1-5)."""
        
        message_lower = message.lower()
        
        # Quick keyword-based detection
        detected_emotions = []
        for emotion, keywords in self.emotion_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_emotions.append(emotion)
        
        # Check for EXTREME urgency indicators only (immediate danger/specific plans)
        extreme_urgency_indicators = [
            "going to kill myself", "planning to kill myself", "plan to kill myself",
            "planning to die", "ending my life tonight", "ending my life today",
            "have a plan to", "taking pills to die", "going to jump",
            "going to hurt myself", "going to end it", "tonight i will",
            "today i will die", "going to commit suicide", "suicide tonight",
            "emergency", "can't hold on", "minutes away from"
        ]
        
        urgency_level = 1
        
        # Only trigger high urgency for very specific immediate danger phrases
        for indicator in extreme_urgency_indicators:
            if indicator in message_lower:
                urgency_level = 5
                break
        
        # Moderate urgency for concerning but not immediate phrases
        moderate_indicators = [
            "want to die", "wish i was dead", "wish i were dead", "can't take it anymore",
            "no point in living", "better off dead", "no reason to live"
        ]
        
        if urgency_level < 5:  # Only if not already extreme
            for indicator in moderate_indicators:
                if indicator in message_lower:
                    urgency_level = 3  # Changed from 5 to 3
                    break
        
        # Slight increase for intensity words, but cap at 3 unless extreme
        if any(word in message_lower for word in ["really", "very", "extremely", "so"]):
            urgency_level = min(urgency_level + 1, 3 if urgency_level < 5 else 5)
        
        primary_emotion = detected_emotions[0] if detected_emotions else "neutral"
        
        return primary_emotion, urgency_level

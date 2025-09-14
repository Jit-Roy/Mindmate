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
    
    def is_mental_health_related(self, message: str) -> MentalHealthTopicFilter:
        """Determine if a message is related to mental health."""
        
        # Quick keyword check first
        message_lower = message.lower()
        keyword_matches = [
            keyword for keyword in config.mental_health_keywords 
            if keyword in message_lower
        ]
        
        if keyword_matches:
            return MentalHealthTopicFilter(
                is_mental_health_related=True,
                confidence_score=0.9,
                detected_topics=keyword_matches,
                reason="Contains mental health keywords"
            )
        
        # Use LLM for more nuanced detection
        system_prompt = """You are a mental health topic classifier. Determine if the user's message is related to mental health, emotional well-being, relationships, stress, mood, or personal struggles.

Mental health related topics include:
- Emotions (sad, happy, angry, anxious, etc.)
- Mental health conditions
- Stress and coping
- Relationships and social issues
- Life challenges and struggles
- Sleep and self-care
- Personal growth and therapy
- Work-life balance
- Family issues

Respond with only 'YES' or 'NO' and a brief reason."""
        
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


class EmotionDetector:
    """Detect emotions and urgency in user messages."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.3
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

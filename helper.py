"""
Helper Functions Module
Contains utility functions for generating follow-up questions and suggestions
"""

from typing import List, Dict, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage



class HelperManager:
    """Manages helper functions for generating follow-up questions and suggestions."""
    
    def __init__(self,config):
        """Initialize the HelperManager with LLM for response generation."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )

    def detect_emotion(self, message: str) -> Tuple[str, int]:
        """
        Detect emotion and urgency level from user message.
        
        Args:
            message: User's message to analyze
            
        Returns:
            Tuple of (emotion, urgency_level) where urgency_level is 1-5
        """
        system_prompt = """You are an expert emotion detection system for a mental health chatbot. Analyze the user's message and determine:

        1. PRIMARY EMOTION: The main emotion expressed (happy, sad, anxious, angry, excited, frustrated, depressed, hopeful, etc.)
        2. URGENCY LEVEL: Rate from 1-5 based on how urgent the situation seems:

        URGENCY LEVELS:
        1 = Casual/Positive: Good news, casual chat, mild stress, normal life updates
        2 = Mild Concern: Minor worries, everyday stress, slight sadness, general life issues
        3 = Moderate Distress: Significant stress, relationship problems, work/school issues, moderate anxiety/depression
        4 = High Distress: Severe anxiety, major life crisis, intense emotional pain, thoughts of self-harm (non-suicidal)
        5 = CRISIS: Suicidal thoughts, immediate danger, severe depression with self-harm ideation, emergency situation

        IMPORTANT GUIDELINES:
        - Most messages should be level 1-3. Only use 4-5 for genuinely serious situations
        - Don't over-dramatize normal stress or sadness
        - Look for keywords like "kill myself", "end it all", "can't go on" for level 5
        - Consider context: "I'm so tired" could be level 1 (normal) or level 3 (depression symptom)

        Respond EXACTLY in this format:
        EMOTION: [single word emotion]
        URGENCY: [number 1-5]
        REASONING: [brief explanation of why you chose this urgency level]"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analyze this message for emotion and urgency: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse the response
            emotion = "neutral"
            urgency_level = 1
            
            lines = response_text.split('\n')
            for line in lines:
                if line.startswith("EMOTION:"):
                    emotion = line.split(":", 1)[1].strip().lower()
                elif line.startswith("URGENCY:"):
                    try:
                        urgency_level = int(line.split(":", 1)[1].strip())
                        urgency_level = max(1, min(5, urgency_level))  
                    except (ValueError, IndexError):
                        urgency_level = 1
            
            return emotion, urgency_level
            
        except Exception as e:
            return "neutral", 1

    def generate_suggestions(self, emotion: str, urgency_level: int, email: str, firebase_manager, message_manager, user_message: str = "") -> List[str]:
        """
        Generate practical suggestions based on user's emotional state and conversation context.
        
        Args:
            emotion: The detected emotion
            urgency_level: Urgency level from 1-5
            user_name: User's preferred name
            email: User's email for conversation context
            user_message: Current user message
            
        Returns:
            List of practical suggestions
        """
        user_profile = firebase_manager.get_user_profile(email)
        name = user_profile.name
        
        # Get conversation context
        recent_messages = message_manager.get_conversation(email, firebase_manager,limit=10)
        
        # Build conversation history for context
        conversation_context = ""
        if recent_messages:
            for msg_pair in recent_messages[-5:]:  # Last 5 messages for context
                conversation_context += f"User: {msg_pair.user_message.content}\n"
                conversation_context += f"Assistant: {msg_pair.llm_message.content}\n"

        system_prompt = f"""You are a caring mental health companion. Generate practical suggestions for someone based on their emotional state and conversation context.

        CONTEXT:
        - User's name: {name}
        - Current emotion: {emotion}
        - Urgency level: {urgency_level}/5 (1=casual, 2=mild concern, 3=moderate distress, 4=high distress, 5=crisis)

        GUIDELINES BY URGENCY LEVEL:
        - Level 1-2: Gentle self-care suggestions and positive activities
        - Level 3: Focused coping strategies and stress management techniques
        - Level 4-5: Immediate help suggestions and safety-focused recommendations

        CONVERSATION DEPTH GUIDELINES:
        - Early conversation (1-3 messages): General wellness suggestions
        - Developing relationship (4-10 messages): More personalized recommendations
        - Deeper relationship (10+ messages): Can suggest specific lifestyle changes or reaching out to support systems

        Recent conversation context:
        {conversation_context}

        RESPONSE FORMAT:
        Generate 3-4 practical suggestions, one per line, without any headers or formatting.

        REQUIREMENTS:
        - Suggestions should be immediately helpful and actionable
        - Suggestions should be specific (not generic advice)
        - Use {name} naturally when appropriate
        - Match urgency level appropriately
        - Each suggestion should be 1-2 sentences max
        - Focus on practical steps they can take right now"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Current user message: '{user_message}' | Generate practical suggestions for someone feeling {emotion} at urgency level {urgency_level}/5.")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            suggestions = self._parse_suggestions(response_text)
            
            return suggestions
            
        except Exception as e:
            return []

    def _parse_suggestions(self, response_text: str) -> List[str]:
        """
        Parse the LLM response to extract suggestions.
        
        Args:
            response_text: The raw response from the LLM
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        try:
            # Split response into lines and extract meaningful suggestions
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()
                # Skip empty lines and headers
                if line and not line.upper().startswith(('SUGGESTIONS:', 'QUESTIONS:')):
                    # Remove bullet points or numbering if present
                    cleaned_line = line.lstrip('- •*123456789. ')
                    if cleaned_line and len(suggestions) < 4:  # Max 4 suggestions
                        suggestions.append(cleaned_line)
            
        except Exception:
            pass
        
        return suggestions

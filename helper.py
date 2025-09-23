"""
Helper Functions Module
Contains utility functions for generating follow-up questions and suggestions
"""

from typing import List, Dict, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import config
from message import message_manager


class HelperManager:
    """Manages helper functions for generating follow-up questions and suggestions."""
    
    def __init__(self):
        """Initialize the HelperManager with LLM for response generation."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )

    def generate_questions_and_suggestions(self, emotion: str, urgency_level: int, user_name: str, email: str, user_message: str = "") -> Tuple[List[str], List[str]]:
        """
        Generate both follow-up questions and suggestions in a single API call.
        
        Args:
            emotion: The detected emotion
            urgency_level: Urgency level from 1-5
            user_name: User's preferred name
            email: User's email for conversation context
            user_message: Current user message
            
        Returns:
            Tuple of (follow_up_questions, suggestions)
        """
        name = user_name or "friend"
        
        # Get conversation context
        recent_messages = message_manager.get_recent_messages(email, 10)
        conversation_depth = len(recent_messages)
        
        # Build conversation history for context
        conversation_context = ""
        if recent_messages:
            for msg_pair in recent_messages[-5:]:  # Last 5 messages for context
                conversation_context += f"User: {msg_pair.user_message.content}\n"
                conversation_context += f"Assistant: {msg_pair.llm_message.content}\n"

        system_prompt = f"""You are a caring mental health companion. Generate BOTH follow-up questions AND suggestions for someone based on their emotional state and conversation context.

        CONTEXT:
        - User's name: {name}
        - Current emotion: {emotion}
        - Urgency level: {urgency_level}/5 (1=casual, 2=mild concern, 3=moderate distress, 4=high distress, 5=crisis)
        - Conversation depth: {conversation_depth} messages exchanged

        GUIDELINES BY URGENCY LEVEL:
        - Level 1-2: Casual, supportive questions and gentle self-care suggestions
        - Level 3: More caring questions about well-being and focused coping strategies
        - Level 4-5: Questions about safety/support systems and immediate help suggestions

        CONVERSATION DEPTH GUIDELINES:
        - Early conversation (1-3 messages): General, rapport-building questions
        - Developing relationship (4-10 messages): More personal but gentle questions  
        - Deeper relationship (10+ messages): Can ask about family, relationships, self-care naturally

        Recent conversation context:
        {conversation_context}

        RESPONSE FORMAT:
        Generate your response in this EXACT format:

        QUESTIONS:
        [2-3 thoughtful follow-up questions, one per line]

        SUGGESTIONS:
        [3 practical suggestions, one per line]

        REQUIREMENTS:
        - Questions should show genuine care and help explore feelings deeper
        - Questions should be conversational, not clinical
        - Use {name} naturally when appropriate
        - Suggestions should be immediately helpful and actionable
        - Suggestions should be specific (not generic advice)
        - Match urgency level appropriately
        - Each suggestion should be 1-2 sentences max"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Current user message: '{user_message}' | Generate empathetic follow-up questions and practical suggestions for someone feeling {emotion} at urgency level {urgency_level}/5.")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse the response to extract questions and suggestions
            questions, suggestions = self._parse_response(response_text)
            
            return questions, suggestions
            
        except Exception as e:
            # Return empty lists if there's an error
            return [], []

    def _parse_response(self, response_text: str) -> Tuple[List[str], List[str]]:
        """
        Parse the LLM response to extract questions and suggestions.
        
        Args:
            response_text: The raw response from the LLM
            
        Returns:
            Tuple of (questions, suggestions)
        """
        questions = []
        suggestions = []
        
        try:
            # Split response into sections
            sections = response_text.split("SUGGESTIONS:")
            
            if len(sections) >= 2:
                # Extract questions section
                questions_section = sections[0].replace("QUESTIONS:", "").strip()
                questions = [
                    q.strip() 
                    for q in questions_section.split('\n') 
                    if q.strip() and '?' in q
                ][:3]  # Max 3 questions
                
                # Extract suggestions section
                suggestions_section = sections[1].strip()
                suggestions = [
                    s.strip() 
                    for s in suggestions_section.split('\n') 
                    if s.strip()
                ][:3]  # Max 3 suggestions
            
            # Fallback: try to extract any questions and suggestions from the text
            if not questions or not suggestions:
                lines = response_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and '?' in line and len(questions) < 3:
                        questions.append(line)
                    elif line and '?' not in line and line and len(suggestions) < 3:
                        suggestions.append(line)
            
        except Exception:
            pass
        
        return questions, suggestions


# Create a global instance
helper_manager = HelperManager()
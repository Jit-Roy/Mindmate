"""
Crisis Management Module
Handles crisis intervention and error handling for the mental health chatbot
"""

from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from data import LLMMessage
from config import config


class CrisisManager:
    """Manages crisis intervention and error handling responses."""
    
    def __init__(self):
        """Initialize the CrisisManager with LLM for response generation."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.7  # Balanced temperature for empathetic but consistent responses
        )
    
    def handle_crisis_situation(self, message: str, user_name: str) -> LLMMessage:
        """Handle crisis situations with immediate support and resources using LLM."""
        name = user_name or "friend"
        
        # Generate crisis response using LLM
        crisis_message = self._generate_crisis_response_with_llm(message, name)
        
        # Generate crisis-specific suggestions and follow-up questions
        suggestions = self._generate_crisis_suggestions_with_llm(message, name)
        follow_up_questions = self._generate_crisis_follow_up_questions_with_llm(message, name)
        
        return LLMMessage(
            content=crisis_message,
            suggestions=suggestions,
            follow_up_questions=follow_up_questions
        )

    def _generate_crisis_response_with_llm(self, message: str, name: str) -> str:
        """Generate personalized crisis intervention response using LLM."""
        system_prompt = f"""You are MyBro, a caring friend responding to someone in severe emotional crisis. Generate a compassionate, urgent, but caring crisis intervention response that:

        1. IMMEDIATELY shows deep concern and love for them
        2. Acknowledges their pain without minimizing it
        3. Fights against harmful thoughts with protective, loving energy
        4. Includes essential crisis resources (MUST include these exactly):
           - Call 988 (Suicide & Crisis Lifeline) - Available 24/7
           - Text HOME to 741741 (Crisis Text Line)
           - Call 911 if in immediate danger
           - Go to nearest emergency room
        5. Emphasizes their value and that people care about them
        6. Shows urgency about getting help TODAY
        7. Uses their name naturally and personally

        TONE GUIDELINES:
        - Be passionately protective, like fighting for a family member
        - Show genuine fear for their safety while remaining strong
        - Be direct and urgent but not clinical
        - Challenge negative thoughts with love and reality
        - Make it personal - this is about THEM specifically

        STRUCTURE:
        - Start with immediate, caring concern that uses their name
        - Acknowledge their crisis and pain
        - List the crisis resources clearly (use the exact format above)
        - End with personal, urgent plea for them to reach out TODAY

        USER CONTEXT:
        - Name: {name}
        - Crisis message: "{message}"
        
        Generate a powerful, loving crisis intervention response that could save their life."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate a crisis intervention response for {name} who said: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            # Critical fallback for crisis situations
            return f"""{name}, I'm genuinely scared for you right now, but I also know you're stronger than this moment. You reached out to me, which means part of you is still fighting.

Listen to me: You're in crisis right now, and that's okay - it happens to the strongest people. But you don't have to face this alone.

**Please reach out to someone who can help immediately:**
• **Call 988** (Suicide & Crisis Lifeline) - Available 24/7
• **Text HOME to 741741** (Crisis Text Line)
• **Call 911** if you're in immediate danger
• **Go to your nearest emergency room**

{name}, I need you to promise me you'll reach out to one of these resources today. Your life has value, and people care about you more than you know right now."""

    def _generate_crisis_suggestions_with_llm(self, message: str, name: str) -> List[str]:
        """Generate crisis-specific suggestions using LLM."""
        system_prompt = f"""Generate 4 immediate, actionable crisis intervention suggestions for someone in severe emotional distress. These should be:

        1. IMMEDIATE safety-focused actions they can take right now
        2. Specific and actionable (not vague)
        3. Appropriate for crisis level urgency
        4. Mix of professional help and personal support
        5. Focus on TODAY - immediate actions

        USER CONTEXT:
        - Name: {name}
        - Crisis situation: "{message}"

        Return exactly 4 suggestions, one per line, without numbering."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate crisis suggestions for {name}: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            suggestions_text = response.content.strip()
            
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            return suggestions[:4] if len(suggestions) >= 4 else [
                "Call 988 Suicide & Crisis Lifeline",
                "Text HOME to 741741",
                "Call a trusted friend or family member",
                "Go to the nearest emergency room"
            ]
            
        except Exception as e:
            return [
                "Call 988 Suicide & Crisis Lifeline",
                "Text HOME to 741741", 
                "Call a trusted friend or family member",
                "Go to the nearest emergency room"
            ]

    def _generate_crisis_follow_up_questions_with_llm(self, message: str, name: str) -> List[str]:
        """Generate crisis-specific follow-up questions using LLM."""
        system_prompt = f"""Generate 2 caring but urgent follow-up questions for someone in crisis. These should:

        1. Check their immediate safety and support systems
        2. Encourage immediate action for getting help
        3. Be personal and caring, using their name
        4. Focus on RIGHT NOW - immediate needs
        5. Help assess their current safety situation

        USER CONTEXT:
        - Name: {name}
        - Crisis message: "{message}"

        Return exactly 2 questions, one per line."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate crisis follow-up questions for {name}: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            questions_text = response.content.strip()
            
            questions = [q.strip() for q in questions_text.split('\n') if q.strip() and '?' in q]
            return questions[:2] if len(questions) >= 2 else [
                "Can you call someone to be with you right now?",
                "Do you have the 988 number saved in your phone?"
            ]
            
        except Exception as e:
            return [
                "Can you call someone to be with you right now?",
                "Do you have the 988 number saved in your phone?"
            ]

    def generate_error_response(self, message: str, emotion: str, urgency_level: int, user_name: str) -> str:
        """Generate contextual error message using LLM."""
        system_prompt = f"""You are MyBro, a caring mental health companion. Your AI systems just encountered an error while processing a user's message, but you need to respond in a way that:

        1. Maintains the caring, supportive relationship
        2. Acknowledges their message without revealing the technical error
        3. Provides meaningful emotional support anyway
        4. Encourages them to try again or continue the conversation
        5. Matches their emotional state appropriately

        USER CONTEXT:
        - Name: {user_name or 'friend'}
        - Their message: "{message}"
        - Detected emotion: {emotion}
        - Urgency level: {urgency_level}/5

        Generate a natural, caring response that provides support even though you couldn't process their message fully. Don't mention technical errors - just be present for them."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate an error response for {user_name}: '{message}' (emotion: {emotion}, urgency: {urgency_level})")
            ]
            
            response = self.llm.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            name = user_name or "friend"
            return f"Hey {name}, I'm having trouble processing that right now, but I'm still here for you. Can you tell me a bit more about how you're feeling? I want to make sure I understand and can support you properly."

    def generate_error_suggestions(self, message: str, emotion: str) -> List[str]:
        """Generate error-specific suggestions using LLM."""
        system_prompt = f"""Generate 3 helpful suggestions for when there's been a processing error but you still want to support someone. Focus on:

        1. Ways to continue the conversation
        2. Alternative ways to express their feelings
        3. General supportive actions they can take

        USER CONTEXT:
        - Their original message: "{message}"
        - Detected emotion: {emotion}

        Return exactly 3 suggestions, one per line, without numbering."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate error recovery suggestions for: '{message}' (emotion: {emotion})")
            ]
            
            response = self.llm.invoke(messages)
            suggestions_text = response.content.strip()
            
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            return suggestions[:3] if len(suggestions) >= 3 else [
                "Try telling me how you're feeling in different words",
                "Share what's been on your mind today",
                "Let me know if you need someone to listen"
            ]
            
        except Exception as e:
            return [
                "Try telling me how you're feeling in different words",
                "Share what's been on your mind today", 
                "Let me know if you need someone to listen"
            ]

    def generate_error_follow_up_questions(self, user_name: str) -> List[str]:
        """Generate error-specific follow-up questions using LLM."""
        system_prompt = f"""Generate 2 caring follow-up questions to help continue a conversation after a processing error. These should:

        1. Be open and inviting
        2. Help the person feel heard and supported
        3. Encourage them to share more about their feelings
        4. Be personal using their name

        USER CONTEXT:
        - Name: {user_name or 'friend'}

        Return exactly 2 questions, one per line."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate error recovery questions for {user_name}")
            ]
            
            response = self.llm.invoke(messages)
            questions_text = response.content.strip()
            
            questions = [q.strip() for q in questions_text.split('\n') if q.strip() and '?' in q]
            return questions[:2] if len(questions) >= 2 else [
                "What's really on your heart right now?",
                "How can I best support you today?"
            ]
            
        except Exception as e:
            name = user_name or "friend"
            return [
                f"What's really on your heart right now, {name}?",
                "How can I best support you today?"
            ]


# Global crisis manager instance
crisis_manager = CrisisManager()
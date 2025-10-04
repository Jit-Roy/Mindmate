"""
Crisis Management Module
Handles crisis intervention and error handling for the mental health chatbot
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from data import LLMMessage



class CrisisManager:
    """Manages crisis intervention and error handling responses."""
    
    def __init__(self,config):
        """Initialize the CrisisManager with LLM for response generation."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.7 
        )
    
    def handle_crisis_situation(self, user_email: str, message: str,firebase_manager) -> LLMMessage:
        """Handle crisis situations with immediate support and resources using LLM."""
        user_profile = firebase_manager.get_user_profile(user_email)
        name = user_profile.name 
        
        # Generate complete crisis response using single LLM call
        system_prompt = f"""You are MyBro, a caring friend responding to someone in severe emotional crisis. Generate a complete crisis intervention response with all components.

        CRISIS RESPONSE REQUIREMENTS:
        1. IMMEDIATELY show deep concern and love for them
        2. Acknowledge their pain without minimizing it  
        3. Fight against harmful thoughts with protective, loving energy
        4. Include essential crisis resources (MUST include these exactly):
           - Call 988 (Suicide & Crisis Lifeline) - Available 24/7
           - Text HOME to 741741 (Crisis Text Line)
           - Call 911 if in immediate danger
           - Go to nearest emergency room
        5. Emphasize their value and that people care about them
        6. Show urgency about getting help TODAY
        7. Use their name naturally and personally

        TONE GUIDELINES:
        - Be passionately protective, like fighting for a family member
        - Show genuine fear for their safety while remaining strong
        - Be direct and urgent but not clinical
        - Challenge negative thoughts with love and reality
        - Make it personal - this is about THEM specifically

        USER CONTEXT:
        - Name: {name}
        - Crisis message: "{message}"

        RESPONSE FORMAT:
        Return your response as a JSON object with this EXACT structure:
        {{
            "crisis_response": "The main crisis intervention message (include all crisis resources)",
            "suggestions": [
                "Immediate actionable suggestion 1",
                "Immediate actionable suggestion 2"
            ],
            "follow_up_questions": [
                "Caring urgent question about safety?",
                "Personal question encouraging immediate action?"
            ]
        }}

        SUGGESTIONS should be:
        - IMMEDIATE safety-focused actions they can take right now
        - Specific and actionable (not vague)
        - Appropriate for crisis level urgency
        - Mix of professional help and personal support
        - Focus on TODAY - immediate actions

        FOLLOW-UP QUESTIONS should:
        - Check their immediate safety and support systems
        - Encourage immediate action for getting help
        - Be personal and caring, using their name
        - Focus on RIGHT NOW - immediate needs
        - Help assess their current safety situation

        Generate a powerful, loving response that could save their life."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate a complete crisis intervention response for {name} who said: '{message}'. Return as JSON.")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
        
            try:
                # Extract JSON from response if wrapped in markdown
                if '```json' in response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                elif '{' in response_text and '}' in response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                else:
                    raise ValueError("No JSON found in response")
                
                crisis_data = json.loads(json_str)
                
                return LLMMessage(
                    content=crisis_data.get('crisis_response', ''),
                    suggestions=crisis_data.get('suggestions', []),
                    follow_up_questions=crisis_data.get('follow_up_questions', [])
                )
                
            except (json.JSONDecodeError, ValueError, KeyError) as json_error:
                raise Exception(f"JSON parsing failed: {json_error}")
            
        except Exception as e:
            fallback_name = name if 'name' in locals() else "friend"
            fallback_message = (
                f"What's really on your heart right now, {fallback_name}? "
                "How can I best support you today?"
            )
            return LLMMessage(content=fallback_message)

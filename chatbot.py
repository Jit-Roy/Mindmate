import random
import asyncio
from datetime import datetime, date
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from data import MessagePair, UserMessage, LLMMessage
from message import MessageManager
from filter import MentalHealthFilter
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager
from events import event_manager
from crisis import crisis_manager
from helper import helper_manager



class MentalHealthChatbot:
    """Main chatbot class that orchestrates the mental health conversation."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        
        self.message_manager = MessageManager()
        self.health_filter = MentalHealthFilter()
        
        self.system_prompt = """You are MyBro - a caring, supportive friend who adapts your response style based on what the person needs. Your personality adjusts to match the situation:

        ⏰ TIME AWARENESS - VERY IMPORTANT:
        - ALWAYS acknowledge when time has passed since your last conversation
        - If they haven't talked in 1+ days, mention it: "Haven't heard from you since yesterday, how are you holding up?"
        - If it's been several days: "Man, it's been 3 days! I was worried about you. How have you been?"
        - Reference time naturally: "Last time we talked..." "Since yesterday..." "A few days ago you mentioned..."
        - If it's the same day: "Earlier today you said..." "A few hours ago..."
        - Use the time context provided to show you care and remember their timeline

        🎭 ADAPTIVE RESPONSE LEVELS:

        🟢 CASUAL/POSITIVE CONVERSATIONS (when they're sharing good news, casual chat, mild stress):
        - Be a supportive, chill friend 
        - Use encouraging language but don't overreact
        - Ask follow-up questions naturally
        - Match their energy level - if they're casual, be casual
        - Example: "That's awesome, man! How did that make you feel?" "Sounds like you're handling things well"

        🟡 MILD CONCERN (everyday stress, minor worries, feeling down but not severe):
        - Be more attentive and caring
        - Offer gentle support and encouragement  
        - Ask deeper questions but don't assume crisis
        - Provide perspective and coping suggestions
        - Example: "That sounds tough, bro. Want to talk about what's making you feel this way?"

        🟠 MODERATE DISTRESS (significant anxiety, depression symptoms, relationship issues):
        - Show more emotional investment
        - Be more direct about caring and support
        - Challenge negative thoughts gently but firmly
        - Remind them of their strengths and support system
        - Example: "Hey, I can tell this is really affecting you. You don't have to go through this alone"

        � CRISIS MODE (suicidal thoughts, severe depression, immediate danger):
        - NOW you become passionate and protective
        - Fight back against harmful thoughts aggressively but lovingly
        - Remind them of people who love them (family, friends, partners)
        - Challenge their negative thoughts directly: "That's not true, bro, and you know it"
        - Be their protector: "I'm not letting you think like that, man"
        - Show urgency about their wellbeing

        🛡️ CRISIS INTERVENTION EXAMPLES:
        "Bro, STOP. Your mom said that because she's scared and stressed, not because she doesn't love you!"
        "Listen to me - you are NOT going anywhere! Your family needs you, even if they're bad at showing it right now."
        "No way, man! You think your dad sacrificed everything just to lose his son? Hell no!"

        💡 KEY PRINCIPLE: MATCH THE ENERGY AND NEED
        - Don't treat someone sharing good news like they're in crisis
        - Don't treat casual frustration like severe depression  
        - Escalate your intensity only when the situation truly calls for it
        - Be supportive without being overwhelming

        🤗 CARING CONTEXTUAL QUESTIONS (Ask these AFTER building rapport, not immediately):
        When someone seems stressed/sad/troubled, gradually ask about:
        - Basic care: "Have you been eating okay?" "How's your sleep been lately?"
        - Relationships: "Everything okay with family?" "How are things with your girlfriend/boyfriend?"
        - Life context: "What's been going on at school/work?" "Did something happen with your parents?"
        - Support system: "Do you have friends you can talk to about this?"

        ⏰ TIMING FOR DEEPER QUESTIONS:
        - NEVER ask personal questions in the first 1-2 exchanges
        - Wait until they've shared something emotional or concerning
        - Build on what they tell you naturally
        - If they mention being sad, THEN ask what happened
        - If they seem stressed, THEN explore the source

        EXAMPLE PROGRESSION:
        User: "I'm feeling really down"
        You: "I'm sorry to hear that, bro. What's been going on?"
        User: [shares more]
        You: "That sounds tough. How have you been sleeping through all this?" OR "Have you talked to anyone close to you about this?"

        Remember: You can be caring and supportive without being aggressive. Save the intense, protective energy for when someone actually needs saving."""

    def process_conversation(self, email: str, message: str) -> str:
        """Unified conversation processing method for both sync and async usage."""
        try:
            # Get user profile and generate conversation summary
            user_profile = firebase_manager.get_user_profile(email)
            user_name = user_profile.name
            summary_manager.generate_conversation_summary(email)
            
            # Check for pending events and generate proactive greeting
            pending_events = event_manager.get_events(email)
            greeting = None
            if pending_events:
                greeting = event_manager._generate_event_greeting(pending_events, email)
            
            # Check if message is mental health related
            topic_filter = self.health_filter.filter(message)
            emotion, urgency_level = helper_manager.detect_emotion(message)
            
            if not topic_filter.is_mental_health_related:
                redirect_response = "Sorry but i can not answer to that question!!!."
                
                MessageManager.add_chat_pair(
                    email=email,
                    user_message=message,
                    model_response=redirect_response,
                    emotion_detected=emotion,
                    urgency_level=urgency_level
                )
                
                return redirect_response
            
            # Detect and store important events
            event = event_manager._extract_events_with_llm(message, email)
            if event:
                event_manager.add_event(email, event)
            
            # Get conversation context
            context = self.message_manager.get_conversation_context(email)
            recent_messages = self.message_manager.get_conversation(email, limit=20)
            conversation_depth = len(recent_messages) if recent_messages else 0
            
            # Handle crisis situations
            if urgency_level >= 5:
                crisis_response = crisis_manager.handle_crisis_situation(message, user_name)

                MessageManager.add_chat_pair(
                    email=email,
                    user_message=message,
                    model_response=crisis_response.content,
                    emotion_detected=emotion,
                    urgency_level=urgency_level
                )
                
                return crisis_response.content
            
            # Build enhanced prompt
            conversation_history = self.message_manager.build_conversation_history(email)
            enhanced_prompt = f"""{self.system_prompt}

            CONVERSATION CONTEXT:
            {context}

            {f"PROACTIVE GREETING: You should start your response with this caring follow-up: '{greeting}'" if greeting else ""}

            CURRENT USER STATE:
            - Detected emotion: {emotion}
            - Urgency level: {urgency_level}/5
            - User prefers to be called: {user_name}
            - Conversation depth: {conversation_depth} messages

            🎯 RESPONSE GUIDANCE BASED ON URGENCY LEVEL:
            Level 1-2 (Casual/Mild): Be supportive but relaxed. Don't overreact. Match their energy level.
            Level 3 (Moderate): Show more concern and support. Ask deeper questions but stay calm.
            Level 4-5 (Crisis): NOW use your passionate, protective mode. Fight for them!

            🤗 CONVERSATION DEPTH GUIDANCE:
            - First 1-2 exchanges: Keep it general, build rapport
            - 3-5 exchanges: Start exploring their situation more
            - 6+ exchanges with emotional content: NOW you can ask about sleep, food, family, relationships naturally

            Remember to:
            1. Address them by their preferred name: {user_name}
            2. Reference relevant past conversations
            3. Match your tone to their ACTUAL emotional state
            4. Only escalate intensity if urgency level is high
            5. If there's a proactive greeting above, start with that
            """
            
            # Build messages for LLM
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [SystemMessage(content=enhanced_prompt)]
            for msg in conversation_history[-10:]:
                messages.append(msg)
            
            messages.append(HumanMessage(content=message))
            response = self.llm.invoke(messages)
            bot_message = response.content
            
            # Generate follow-up questions and suggestions
            try:
                follow_up_questions, suggestions = helper_manager.generate_questions_and_suggestions(
                    emotion, urgency_level, user_name, email, message
                )
            except:
                follow_up_questions = []
                suggestions = []
            
            # Mark events as followed up if proactive greeting was used
            if greeting and pending_events:
                event_manager.mark_event_followed_up(pending_events, email)
            
            # Save interaction
            firebase_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=bot_message,
                emotion_detected=emotion,
                urgency_level=urgency_level
            )
            
            return bot_message
            
        except Exception as e:
            try:
                # Use crisis manager for error handling
                user_profile = firebase_manager.get_user_profile(email)
                user_name = user_profile.name
                emotion, urgency_level = helper_manager.detect_emotion(message)
                return crisis_manager.handle_error_response(message, emotion, urgency_level, user_name).content
            except:
                return f"Sorry, I'm having technical difficulties. Please try again later. Error: {e}"

    async def chat(self, email: str, message: str) -> LLMMessage:
        """Async chat method that wraps the unified conversation processor."""
        # Get user data for LLMMessage format
        emotion, urgency_level = helper_manager.detect_emotion(message)
        user_profile = firebase_manager.get_user_profile(email)
        
        try:
            # Use the unified processor for core logic
            bot_message = self.process_conversation(email, message)
            
            # Generate follow-up questions and suggestions
            try:
                follow_up_questions, suggestions = helper_manager.generate_questions_and_suggestions(
                    emotion, urgency_level, user_profile.name, email, message
                )
            except:
                follow_up_questions = []
                suggestions = []
            
            return LLMMessage(
                content=bot_message,
                suggestions=suggestions,
                follow_up_questions=follow_up_questions
            )
            
        except Exception as e:
            # Generate contextual error message using LLM
            try:
                error_message = crisis_manager.generate_error_response(message, emotion, urgency_level, user_profile.name)
                error_suggestions = crisis_manager.generate_error_suggestions(message, emotion)
                error_questions = crisis_manager.generate_error_follow_up_questions(user_profile.name)
                
                return LLMMessage(
                    content=error_message,
                    suggestions=error_suggestions,
                    follow_up_questions=error_questions
                )
            except:
                return LLMMessage(
                    content=f"Sorry, I'm having technical difficulties. Please try again later.",
                    suggestions=[],
                    follow_up_questions=[]
                )
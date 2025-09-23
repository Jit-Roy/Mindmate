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
        
        self.system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt that defines the chatbot's personality."""
        return """You are MyBro - a caring, supportive friend who adapts your response style based on what the person needs. Your personality adjusts to match the situation:

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

    async def chat(self, email: str, message: str) -> LLMMessage:
        """Main chat method that processes user input and generates response."""
        
        # Check if we should generate a proactive greeting first
        proactive_greeting = event_manager.generate_proactive_greeting(email)
        
        # Check if message is mental health related
        topic_filter = self.health_filter.filter(message)
        
        if not topic_filter.is_mental_health_related:
            redirect_response = "Sorry but i can not answer to that question!!!."
            
            # Detect emotion and urgency for the redirect response
            emotion, urgency_level = self.health_filter.detect_emotion(message)
            
            # Define redirect suggestions and questions
            redirect_suggestions = ["Tell me how you're feeling today", "Share what's on your mind"]
            redirect_questions = ["How are you doing emotionally?", "What's been on your mind lately?"]
            
            # Save the interaction with redirect using add_chat_pair
            firebase_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=redirect_response,
                emotion_detected=emotion,
                urgency_level=urgency_level,
                suggestions=redirect_suggestions,
                follow_up_questions=redirect_questions
            )
            
            return LLMMessage(
                content=redirect_response,
                suggestions=redirect_suggestions,
                follow_up_questions=redirect_questions
            )
        
        # Detect emotion and urgency for mental health messages
        emotion, urgency_level = self.health_filter.detect_emotion(message)
        
        # Detect and store important events
        event_manager.detect_important_events(message, email)
        
        # Get conversation context BEFORE adding the current message
        context = self.message_manager.get_conversation_context(email)
        user_profile = firebase_manager.get_user_profile(email)
        
        # Check if this is a crisis situation - only trigger for urgency level 5 (extreme)
        if urgency_level >= 5:
            crisis_response = crisis_manager.handle_crisis_situation(message, user_profile.name)
            
            # Save crisis interaction using add_chat_pair
            firebase_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=crisis_response.content,
                emotion_detected=emotion,
                urgency_level=urgency_level,
                suggestions=crisis_response.suggestions,
                follow_up_questions=crisis_response.follow_up_questions
            )
            return crisis_response
        
        # Build conversation for LLM
        conversation_history = self._build_conversation_history(email)
        recent_messages = self.message_manager.get_recent_messages(email, 20)
        conversation_depth = len(recent_messages)
        
        # Create the prompt with context
        enhanced_prompt = f"""{self.system_prompt}

        CONVERSATION CONTEXT:
        {context}

        {f"PROACTIVE GREETING: You should start your response with this caring follow-up: '{proactive_greeting}'" if proactive_greeting else ""}

        CURRENT USER STATE:
        - Detected emotion: {emotion}
        - Urgency level: {urgency_level}/5
        - User prefers to be called: {user_profile.name}
        - Conversation depth: {conversation_depth} messages (deeper conversations allow more personal questions)

        🎯 RESPONSE GUIDANCE BASED ON URGENCY LEVEL:

        Level 1-2 (Casual/Mild): Be supportive but relaxed. Don't overreact. Match their energy level.
        Level 3 (Moderate): Show more concern and support. Ask deeper questions but stay calm.
        Level 4-5 (Crisis): NOW use your passionate, protective mode. Fight for them!

        🤗 CONVERSATION DEPTH GUIDANCE:
        - First 1-2 exchanges: Keep it general, build rapport
        - 3-5 exchanges: Start exploring their situation more
        - 6+ exchanges with emotional content: NOW you can ask about sleep, food, family, relationships naturally

        IMPORTANT: Do not assume crisis or depression unless urgency level is 3+. For levels 1-2, be a normal supportive friend.

        Remember to:
        1. Address them by their preferred name
        2. Reference relevant past conversations
        3. Match your tone to their ACTUAL emotional state (don't assume worst case)
        4. Only escalate intensity if urgency level is high
        5. Acknowledge time passed since last conversation if applicable
        6. If there's a proactive greeting above, start with that and then naturally flow into responding to their current message"""
        
        # Build message list for the LLM
        messages = [
            SystemMessage(content=enhanced_prompt),
            *conversation_history,
            HumanMessage(content=message)
        ]
        
        try:
            # Get response from LLM
            response = await self.llm.ainvoke(messages)
            bot_message = response.content
            
            # Generate follow-up questions and suggestions
            follow_up_questions = self._generate_follow_up_questions(emotion, urgency_level, user_profile.name, email, message)
            suggestions = self._generate_suggestions(emotion, urgency_level, message, user_profile.name)
            
            # If we used a proactive greeting, mark relevant events as followed up
            if proactive_greeting:
                # Extract event type from greeting to mark as followed up
                for event_type in ['exam', 'interview', 'appointment']:
                    if event_type in proactive_greeting.lower():
                        event_manager.mark_event_followed_up(email, event_type)
                        break
            
            # Save successful interaction using add_chat_pair
            firebase_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=bot_message,
                emotion_detected=emotion,
                urgency_level=urgency_level,
                suggestions=suggestions,
                follow_up_questions=follow_up_questions
            )
            
            return LLMMessage(
                content=bot_message,
                suggestions=suggestions,
                follow_up_questions=follow_up_questions
            )
            
        except Exception as e:
            # Generate contextual error message using LLM
            error_message = crisis_manager.generate_error_response(message, emotion, urgency_level, user_profile.name)
            error_suggestions = crisis_manager.generate_error_suggestions(message, emotion)
            error_questions = crisis_manager.generate_error_follow_up_questions(user_profile.name)
            
            # Save error interaction using add_chat_pair
            firebase_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=error_message,
                emotion_detected=emotion,
                urgency_level=urgency_level,
                suggestions=error_suggestions,
                follow_up_questions=error_questions
            )
            
            return LLMMessage(
                content=error_message,
                suggestions=error_suggestions,
                follow_up_questions=error_questions
            )

    def _build_conversation_history(self, email: str) -> List:
        """Build conversation history for the LLM."""
        recent_messages = self.message_manager.get_recent_messages(email, 10)
        
        langchain_messages = []
        for msg_pair in recent_messages:
            # Add user message
            langchain_messages.append(HumanMessage(content=msg_pair.user_message.content))
            # Add LLM message
            langchain_messages.append(AIMessage(content=msg_pair.llm_message.content))
        
        return langchain_messages

    def _generate_follow_up_questions(self, emotion: str, urgency_level: int, user_name: str, email: str, user_message: str = "") -> List[str]:
        """Generate personalized follow-up questions using LLM based on emotion, urgency, and conversation context."""
        name = user_name or "friend"
        
        # Get conversation context
        recent_messages = self.message_manager.get_recent_messages(email, 10)
        conversation_depth = len(recent_messages)
        
        # Build conversation history for context
        conversation_context = ""
        if recent_messages:
            for msg_pair in recent_messages[-5:]:  # Last 5 messages for context
                conversation_context += f"User: {msg_pair.user_message.content}\n"
                conversation_context += f"Assistant: {msg_pair.llm_message.content}\n"
        
        system_prompt = f"""You are a caring mental health companion generating thoughtful follow-up questions. Based on the user's current emotional state, conversation history, and relationship depth, create 2-3 empathetic follow-up questions that:

        1. Show genuine care and interest in their situation
        2. Are appropriate for their emotional state and urgency level
        3. Consider the conversation depth and intimacy level
        4. Help them explore their feelings or situation deeper
        5. Feel natural and conversational, not clinical

        CONTEXT:
        - User's name: {name}
        - Current emotion: {emotion}
        - Urgency level: {urgency_level}/5 (1=casual, 2=mild concern, 3=moderate distress, 4=high distress, 5=crisis)
        - Conversation depth: {conversation_depth} messages exchanged

        CONVERSATION GUIDELINES BY URGENCY:
        - Level 1-2: Casual, supportive questions that show interest
        - Level 3: More caring questions about their well-being and situation
        - Level 4-5: Questions focused on safety, support systems, and immediate needs

        CONVERSATION DEPTH GUIDELINES:
        - Early conversation (1-3 messages): General, rapport-building questions
        - Developing relationship (4-10 messages): More personal but still gentle questions  
        - Deeper relationship (10+ messages): Can ask about family, relationships, self-care naturally

        QUESTION STYLE:
        - Use {name} naturally in questions when appropriate
        - Be conversational, not interrogating
        - Mix emotional support with practical exploration
        - Show you remember and care about their situation

        Recent conversation context:
        {conversation_context}

        Return 1/2/3 thoughtful follow-up questions in a paragraph without numbering or bullet points."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Current user message: '{user_message}' | Generate empathetic follow-up questions for someone feeling {emotion} at urgency level {urgency_level}/5.")
            ]
            
            response = self.llm.invoke(messages)
            questions_text = response.content.strip()
            
            # Split into individual questions and clean them
            questions = [
                question.strip() 
                for question in questions_text.split('\n') 
                if question.strip() and '?' in question
            ]
            
            # Ensure we have 2-3 questions
            if len(questions) >= 2:
                return questions[:3]  # Return max 3 questions
            else:
                # Return empty list if LLM response is inadequate
                return []
                
        except Exception as e:
            pass

    def _generate_suggestions(self, emotion: str, urgency_level: int, user_message: str = "", user_name: str = "friend") -> List[str]:
        """Generate helpful suggestions using LLM based on detected emotion, urgency, and context."""
        
        system_prompt = f"""You are a mental health support assistant generating personalized coping suggestions. Based on the user's emotional state and situation, provide 3 practical, actionable suggestions that are:

        1. Immediately helpful for their current emotional state
        2. Appropriate for their urgency level (1-5 scale)
        3. Realistic and achievable in the next few hours
        4. Supportive without being overwhelming

        CONTEXT:
        - User's emotion: {emotion}
        - Urgency level: {urgency_level}/5 (1=casual, 2=mild concern, 3=moderate distress, 4=high distress, 5=crisis)
        - User's name: {user_name}

        URGENCY GUIDELINES:
        - Level 1-2: Gentle self-care and wellness suggestions
        - Level 3: More focused coping strategies and support-seeking
        - Level 4-5: Immediate safety measures and professional help

        SUGGESTION RULES:
        - Each suggestion should be 1-2 sentences max
        - Be specific and actionable ("Call your best friend" not "reach out to someone")
        - Match the urgency level appropriately
        - Consider their emotional state (anxious needs different help than depressed)
        - Avoid generic advice - make it feel personal

        Return EXACTLY 3 suggestions, one per line, without numbering or bullet points."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"User's emotional state: {emotion} (urgency {urgency_level}/5). Generate 3 personalized suggestions for immediate support. User message context: '{user_message}'")
            ]
            
            response = self.llm.invoke(messages)
            suggestions_text = response.content.strip()
            
            # Split into individual suggestions and clean them
            suggestions = [
                suggestion.strip() 
                for suggestion in suggestions_text.split('\n') 
                if suggestion.strip()
            ]
            
            # Ensure we have exactly 3 suggestions
            if len(suggestions) >= 3:
                return suggestions[:3]
            else:
                # Return empty list if LLM response is inadequate
                return []
                
        except Exception as e:
            return []


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from message import MessageManager
from filter import MentalHealthFilter
from config import Config
from firebase_manager import FirebaseManager
from summary import SummaryManager
from events import EventManager
from crisis import CrisisManager
from helper import HelperManager
from daily import DailyTaskManager
import asyncio
import concurrent.futures
import logging


class MentalHealthChatbot:
    """Main chatbot class that orchestrates the mental health conversation."""
    
    def __init__(self):
        self.firebase_manager = FirebaseManager()
        self.config = Config()
        self.llm = ChatGoogleGenerativeAI(
            model=self.config.model_name,
            google_api_key=self.config.gemini_api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )

        self.message_manager = MessageManager(self.firebase_manager)
        self.health_filter = MentalHealthFilter(self.config)
        self.event_manager = EventManager(self.config,self.firebase_manager)
        self.crisis_manager = CrisisManager(self.config)
        self.helper_manager = HelperManager(self.config)
        self.summary_manager = SummaryManager(self.config)
        self.daily_task_manager = DailyTaskManager(self.config)
        
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

        🛑 CRISIS MODE (suicidal thoughts, severe depression, immediate danger):
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

    async def process_conversation_async(self, email: str, message: str) -> str:
        """Async conversation processing with parallel blocking calls using asyncio.to_thread.

        Notes:
        - Uses asyncio.to_thread to offload blocking CPU/IO work (Firestore + LLM helpers)
        - Avoids passing a ThreadPoolExecutor around after shutdown
        - Background tasks (event storage & chat persistence) run fire-and-forget
        - Falls back to sync method on unexpected errors
        """
        try:
            # Run initial independent blocking operations concurrently
            (user_profile, topic_filter, emotion_urgency, recent_messages) = await asyncio.gather(
                asyncio.to_thread(self.firebase_manager.get_user_profile, email),
                asyncio.to_thread(self.health_filter.filter, message),
                asyncio.to_thread(self.helper_manager.detect_emotion, message),
                asyncio.to_thread(self.message_manager.get_conversation, email, None, 20)  # (email, date=None, limit=20)
            )

            emotion, urgency_level = emotion_urgency
            user_name = user_profile.name

            # Early exit if not mental-health related
            if not topic_filter.is_mental_health_related:
                redirect_response = "Sorry but i can not answer to that question!!!."
                asyncio.create_task(asyncio.to_thread(
                    self.message_manager.add_chat_pair,
                    email, message, redirect_response, emotion, urgency_level
                ))
                return redirect_response

            # Start event extraction (don't await yet unless non-crisis)
            event_future = asyncio.create_task(asyncio.to_thread(
                self.event_manager._extract_events_with_llm, message, email
            ))

            # Crisis handling short-circuits normal flow
            if urgency_level >= 5:
                crisis_response = self.crisis_manager.handle_crisis_situation(message, user_name)
                # Persist conversation asynchronously
                asyncio.create_task(asyncio.to_thread(
                    self.message_manager.add_chat_pair,
                    email, message, crisis_response.content, emotion, urgency_level
                ))
                # Continue event extraction/storage in background (ignore result if fails)
                async def _background_event_store():
                    try:
                        evt = await event_future
                        if evt:
                            await asyncio.to_thread(self.event_manager.add_event, email, evt)
                    except Exception as bg_err:
                        logging.warning(f"Background event storage failed (crisis path): {bg_err}")
                asyncio.create_task(_background_event_store())
                return crisis_response.content

            # Non-crisis: wait for event extraction
            event = await event_future
            if event:
                asyncio.create_task(asyncio.to_thread(self.event_manager.add_event, email, event))

            # Generate LLM response (blocking -> offloaded)
            bot_message = await self._generate_response_async(
                email=email,
                message=message,
                user_name=user_name,
                emotion=emotion,
                urgency_level=urgency_level,
                recent_messages=recent_messages
            )
            return bot_message

        except Exception as e:
            logging.error(f"Error in async conversation processing: {e}")
            return self.process_conversation_sync(email, message)
    
    async def _generate_response_async(self, email: str, message: str, user_name: str, emotion: str, urgency_level: int, recent_messages) -> str:
        """Generate the LLM response asynchronously (offloading blocking invoke)."""
        try:
            enhanced_prompt = f"""
            {self.system_prompt}
            CONVERSATION CONTEXT:
            {recent_messages}

            CURRENT USER STATE:
            - Detected emotion: {emotion}
            - Urgency level: {urgency_level}/5
            - User prefers to be called: {user_name}

            🎯 RESPONSE GUIDANCE BASED ON URGENCY LEVEL:
            Level 1-2 (Casual/Mild): Be supportive but relaxed. Don't overreact. Match their energy level.
            Level 3 (Moderate): Show more concern and support. Ask deeper questions but stay calm.
            Level 4-5 (Crisis): NOW use your passionate, protective mode. Fight for them!

            🤗 CONVERSATION DEPTH GUIDANCE:
            - First 1-2 exchanges: Keep it general, build rapport
            - 3-5 exchanges: Start exploring their situation more
            - 6+ exchanges with emotional content: NOW you can ask about sleep, food, family, relationships naturally

            💡 FOLLOW-UP QUESTIONS GUIDANCE:
            Based on the user's emotional state and urgency level, naturally include 1-2 thoughtful follow-up questions in your response that:
            - Are appropriate for their current emotional state and urgency level
            - Help them explore their feelings or situation deeper
            - Show genuine care and interest in their wellbeing
            - Match the conversation depth (don't ask personal questions too early)
            - Are contextually relevant to what they've shared

            Remember to:
            1. Address them by their preferred name: {user_name}
            2. Reference relevant past conversations
            3. Match your tone to their ACTUAL emotional state
            4. Only escalate intensity if urgency level is high
            5. If there's a proactive greeting above, start with that
            6. Include natural, caring follow-up questions within your response
            """
            
            # Build messages for LLM
            messages = [SystemMessage(content=enhanced_prompt)]
            if recent_messages:
                for msg_pair in recent_messages:
                    messages.append(HumanMessage(content=msg_pair.user_message.content))
                    messages.append(AIMessage(content=msg_pair.llm_message.content))
            messages.append(HumanMessage(content=message))

            response = await asyncio.to_thread(self.llm.invoke, messages)
            bot_message = response.content

            # Persist interaction (non-blocking for caller)
            asyncio.create_task(asyncio.to_thread(
                self.message_manager.add_chat_pair,
                email, message, bot_message, emotion, urgency_level
            ))
            return bot_message
        
        except Exception as e:
            logging.error(f"Error generating async response: {e}")
            raise
    
    def process_conversation(self, email: str, message: str) -> str:
        """Synchronous wrapper for backward compatibility."""
        return asyncio.run(self.process_conversation_async(email, message))
    
    def process_conversation_sync(self, email: str, message: str) -> str:
        """Fallback synchronous conversation processing method."""
        try:
            # Get user profile and generate conversation summary
            user_profile = self.firebase_manager.get_user_profile(email)
            user_name = user_profile.name
            
            # Check if message is mental health related
            topic_filter = self.health_filter.filter(message)
            emotion, urgency_level = self.helper_manager.detect_emotion(message)
            
            if not topic_filter.is_mental_health_related:
                redirect_response = "Sorry but i can not answer to that question!!!."
                
                self.message_manager.add_chat_pair(
                    email=email,
                    user_message=message,
                    model_response=redirect_response,
                    emotion_detected=emotion,
                    urgency_level=urgency_level
                )
                
                return redirect_response
            
            # Detect and store important events
            event = self.event_manager._extract_events_with_llm(message, email)
            if event:
                self.event_manager.add_event(email, event)
            
            # Get conversation context
            recent_messages = self.message_manager.get_conversation(email, self.firebase_manager,limit=20)
            
            # Handle crisis situations
            if urgency_level >= 5:
                crisis_response = self.crisis_manager.handle_crisis_situation(message, user_name)

                self.message_manager.add_chat_pair(
                    email=email,
                    user_message=message,
                    model_response=crisis_response.content,
                    emotion_detected=emotion,
                    urgency_level=urgency_level
                )
                
                return crisis_response.content
            
            # Build enhanced prompt
            enhanced_prompt = f"""
            {self.system_prompt}
            CONVERSATION CONTEXT:
            {recent_messages}

            CURRENT USER STATE:
            - Detected emotion: {emotion}
            - Urgency level: {urgency_level}/5
            - User prefers to be called: {user_name}

            🎯 RESPONSE GUIDANCE BASED ON URGENCY LEVEL:
            Level 1-2 (Casual/Mild): Be supportive but relaxed. Don't overreact. Match their energy level.
            Level 3 (Moderate): Show more concern and support. Ask deeper questions but stay calm.
            Level 4-5 (Crisis): NOW use your passionate, protective mode. Fight for them!

            🤗 CONVERSATION DEPTH GUIDANCE:
            - First 1-2 exchanges: Keep it general, build rapport
            - 3-5 exchanges: Start exploring their situation more
            - 6+ exchanges with emotional content: NOW you can ask about sleep, food, family, relationships naturally

            💡 FOLLOW-UP QUESTIONS GUIDANCE:
            Based on the user's emotional state and urgency level, naturally include 1-2 thoughtful follow-up questions in your response that:
            - Are appropriate for their current emotional state and urgency level
            - Help them explore their feelings or situation deeper
            - Show genuine care and interest in their wellbeing
            - Match the conversation depth (don't ask personal questions too early)
            - Are contextually relevant to what they've shared

            Remember to:
            1. Address them by their preferred name: {user_name}
            2. Reference relevant past conversations
            3. Match your tone to their ACTUAL emotional state
            4. Only escalate intensity if urgency level is high
            5. If there's a proactive greeting above, start with that
            6. Include natural, caring follow-up questions within your response
            """
            
            # Build messages for LLM
            messages = [SystemMessage(content=enhanced_prompt)]
            
            # Convert MessagePair objects to proper message format
            if recent_messages:
                for msg_pair in recent_messages:  
                    messages.append(HumanMessage(content=msg_pair.user_message.content))
                    messages.append(AIMessage(content=msg_pair.llm_message.content))
            
            messages.append(HumanMessage(content=message))
            response = self.llm.invoke(messages)
            bot_message = response.content
            
            # Save interaction
            self.message_manager.add_chat_pair(
                email=email,
                user_message=message,
                model_response=bot_message,
                emotion_detected=emotion,
                urgency_level=urgency_level
            )
            
            return bot_message
            
        except Exception as e:
            logging.error(f"Error in sync conversation processing: {e}")
            raise
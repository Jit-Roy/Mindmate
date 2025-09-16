import random
import asyncio
from datetime import datetime
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from models import ChatResponse, UserProfile, ConversationMessage, ImportantEvent
from memory_manager import MemoryManager
from mental_health_filter import MentalHealthFilter
from config import config


class MentalHealthChatbot:
    """Main chatbot class that orchestrates the mental health conversation."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        
        self.memory_manager = MemoryManager()
        self.health_filter = MentalHealthFilter()
        
        self.system_prompt = self._create_system_prompt()
        
        # Daily check-in questions
        self.check_in_questions = [
            "Hey bro, how are you feeling today?",
            "What's on your mind today, friend?",
            "How did you sleep last night? How's your mood?",
            "Any particular thoughts or feelings you want to share today?",
            "What's been the highlight of your day so far?",
            "How are you taking care of yourself today?",
            "Is there anything that's been weighing on your mind lately?",
            "How would you describe your energy level today?",
            "What's one thing you're grateful for today?",
            "How are you handling stress these days?"
        ]
    
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

    async def chat(self, user_id: str, message: str) -> ChatResponse:
        """Main chat method that processes user input and generates response."""
        
        # Check if we should generate a proactive greeting first
        proactive_greeting = self._generate_proactive_greeting(user_id)
        
        # Check if message is mental health related
        topic_filter = self.health_filter.is_mental_health_related(message)
        
        if not topic_filter.is_mental_health_related:
            redirect_response = self.health_filter.get_redirect_response()
            
            # Still save the interaction but with a redirect
            self.memory_manager.add_message(user_id, "user", message)
            self.memory_manager.add_message(user_id, "assistant", redirect_response)
            
            return ChatResponse(
                message=redirect_response,
                emotion_tone="neutral",
                suggestions=["Tell me how you're feeling today", "Share what's on your mind"],
                follow_up_questions=["How are you doing emotionally?", "What's been on your mind lately?"]
            )
        
        # Detect emotion and urgency
        emotion, urgency_level = self.health_filter.detect_emotion(message)
        
        # Detect and store important events
        self._detect_important_events(message, user_id)
        
        # Get conversation context BEFORE adding the current message
        context = self.memory_manager.get_conversation_context(user_id)
        user_profile = self.memory_manager.get_user_profile(user_id)
        
        # Check if this is a crisis situation - only trigger for urgency level 5 (extreme)
        if urgency_level >= 5:
            crisis_response = self._handle_crisis_situation(message, user_profile.preferred_name)
            
            # Add user message to memory
            self.memory_manager.add_message(
                user_id, "user", message, 
                emotion_detected=emotion, 
                urgency_level=urgency_level
            )
            
            # Add crisis response to memory
            self.memory_manager.add_message(user_id, "assistant", crisis_response.message)
            return crisis_response
        
        # Build conversation for LLM
        conversation_history = self._build_conversation_history(user_id)
        recent_messages = self.memory_manager.get_recent_messages(user_id, 20)
        conversation_depth = len(recent_messages)
        
        # Create the prompt with context
        enhanced_prompt = f"""{self.system_prompt}

CONVERSATION CONTEXT:
{context}

{f"PROACTIVE GREETING: You should start your response with this caring follow-up: '{proactive_greeting}'" if proactive_greeting else ""}

CURRENT USER STATE:
- Detected emotion: {emotion}
- Urgency level: {urgency_level}/5
- User prefers to be called: {user_profile.preferred_name or 'friend'}
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
            follow_up_questions = self._generate_follow_up_questions(emotion, urgency_level, user_profile.preferred_name, user_id)
            suggestions = self._generate_suggestions(emotion, urgency_level)
            
            # If we used a proactive greeting, mark relevant events as followed up
            if proactive_greeting:
                # Extract event type from greeting to mark as followed up
                for event_type in ['exam', 'interview', 'appointment']:
                    if event_type in proactive_greeting.lower():
                        self._mark_event_followed_up(user_id, event_type)
                        break
            
            # Add user message to memory first
            self.memory_manager.add_message(
                user_id, "user", message, 
                emotion_detected=emotion, 
                urgency_level=urgency_level
            )
            
            # Add assistant response to memory
            self.memory_manager.add_message(user_id, "assistant", bot_message)
            
            return ChatResponse(
                message=bot_message,
                emotion_tone=emotion,
                suggestions=suggestions,
                follow_up_questions=follow_up_questions
            )
            
        except Exception as e:
            error_message = f"I'm having trouble processing that right now, but I'm here for you. Can you tell me more about how you're feeling?"
            
            # Add user message to memory
            self.memory_manager.add_message(
                user_id, "user", message, 
                emotion_detected=emotion, 
                urgency_level=urgency_level
            )
            
            # Add error response to memory
            self.memory_manager.add_message(user_id, "assistant", error_message)
            
            return ChatResponse(
                message=error_message,
                emotion_tone="supportive",
                suggestions=["Try rephrasing your message", "Tell me about your day"],
                follow_up_questions=["How are you feeling right now?", "What's on your mind?"]
            )

    def _handle_crisis_situation(self, message: str, user_name: str) -> ChatResponse:
        """Handle crisis situations with immediate support and resources."""
        name = user_name or "friend"
        
        crisis_responses = [
            f"Whoa, {name} - I hear you, and I'm really worried about you right now. What you're going through sounds incredibly painful, but I need you to know that this feeling, as overwhelming as it is, can change.",
            f"{name}, I'm genuinely scared for you right now, but I also know you're stronger than this moment. You reached out to me, which means part of you is still fighting.",
            f"Hey {name}, stop right there. I know everything feels impossible right now, but you matter more than you realize, and I'm not going to let you give up."
        ]
        
        crisis_message = f"""{random.choice(crisis_responses)}

Listen to me: You're in crisis right now, and that's okay - it happens to the strongest people. But you don't have to face this alone.

**Please reach out to someone who can help immediately:**
• **Call 988** (Suicide & Crisis Lifeline) - Available 24/7
• **Text HOME to 741741** (Crisis Text Line)
• **Call 911** if you're in immediate danger
• **Go to your nearest emergency room**

You can also:
• Call a trusted friend or family member right now
• Ask someone to stay with you today
• Call your doctor or therapist if you have one

{name}, I need you to promise me you'll reach out to one of these resources today. Your life has value, and people care about you more than you know right now."""
        
        return ChatResponse(
            message=crisis_message,
            emotion_tone="urgent",
            suggestions=[
                "Call 988 Suicide & Crisis Lifeline",
                "Text HOME to 741741",
                "Call a trusted friend or family member",
                "Go to the nearest emergency room"
            ],
            follow_up_questions=[
                "Can you call someone to be with you right now?",
                "Do you have the 988 number saved in your phone?"
            ]
        )

    def _build_conversation_history(self, user_id: str) -> List:
        """Build conversation history for the LLM."""
        recent_messages = self.memory_manager.get_recent_messages(user_id, 10)
        
        langchain_messages = []
        for msg in recent_messages:
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                langchain_messages.append(AIMessage(content=msg.content))
        
        return langchain_messages

    def _detect_important_events(self, message: str, user_id: str) -> None:
        """Detect and store important upcoming events from user messages."""
        message_lower = message.lower()
        
        # Event patterns to detect
        event_patterns = {
            'exam': ['exam', 'test', 'quiz', 'midterm', 'final'],
            'interview': ['interview', 'job interview', 'interview tomorrow'],
            'appointment': ['appointment', 'doctor', 'therapy', 'meeting'],
            'date': ['date', 'going out', 'date night'],
            'presentation': ['presentation', 'presenting', 'speech'],
            'deadline': ['deadline', 'due date', 'assignment due'],
            'event': ['event', 'party', 'celebration', 'wedding']
        }
        
        # Time indicators that suggest upcoming events
        time_indicators = [
            'tomorrow', 'next week', 'next month', 'in a few days', 
            'this weekend', 'next monday', 'next tuesday', 'next wednesday',
            'next thursday', 'next friday', 'next saturday', 'next sunday',
            'tonight', 'later today', 'this afternoon', 'this evening'
        ]
        
        # Check if message contains both event and time indicators
        detected_event_type = None
        for event_type, keywords in event_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_event_type = event_type
                break
        
        has_time_indicator = any(indicator in message_lower for indicator in time_indicators)
        
        # If we detect an event with time context, store it
        if detected_event_type and has_time_indicator:
            from datetime import date, timedelta
            import uuid
            
            # Estimate event date based on time indicators
            event_date = None
            today = date.today()
            
            if 'tomorrow' in message_lower:
                event_date = today + timedelta(days=1)
            elif 'next week' in message_lower:
                event_date = today + timedelta(days=7)
            elif 'tonight' in message_lower or 'later today' in message_lower:
                event_date = today
            elif 'this weekend' in message_lower:
                event_date = today + timedelta(days=(5 - today.weekday()))  # Next Saturday
            
            # Create and store the event
            event = ImportantEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                event_type=detected_event_type,
                description=message,
                event_date=event_date
            )
            
            # Add to user profile
            user_profile = self.memory_manager.get_user_profile(user_id)
            user_profile.important_events.append(event)
            self.memory_manager.update_user_profile(user_id, {"important_events": user_profile.important_events})

    def _generate_proactive_greeting(self, user_id: str) -> Optional[str]:
        """Generate a proactive greeting that asks about important events."""
        user_profile = self.memory_manager.get_user_profile(user_id)
        name = user_profile.preferred_name or "friend"
        
        from datetime import date, timedelta
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Check for events that need follow-up
        for event in user_profile.important_events:
            if not event.follow_up_done and event.follow_up_needed:
                # If event was today or yesterday, ask about it
                if event.event_date == today:
                    if event.event_type == 'exam':
                        return f"Hey {name}! How did your exam go today? I remember you were studying for it yesterday."
                    elif event.event_type == 'interview':
                        return f"Hey {name}! How did your interview go today? I've been thinking about you!"
                    elif event.event_type == 'appointment':
                        return f"Hey {name}! How did your appointment go today? Hope everything went well."
                    else:
                        return f"Hey {name}! How did your {event.event_type} go today?"
                
                elif event.event_date == yesterday:
                    if event.event_type == 'exam':
                        return f"Hey {name}! How did your exam go yesterday? I remember you were preparing for it."
                    elif event.event_type == 'interview':
                        return f"Hey {name}! How did your interview go yesterday? I've been wondering how it went!"
                    elif event.event_type == 'appointment':
                        return f"Hey {name}! How did your appointment go yesterday? Hope it went smoothly."
                    else:
                        return f"Hey {name}! How did your {event.event_type} go yesterday?"
                
                # If event is coming up soon, check in
                elif event.event_date and event.event_date > today and (event.event_date - today).days <= 2:
                    if event.event_type == 'exam':
                        return f"Hey {name}! How's the studying going for your exam? It's coming up soon, right?"
                    elif event.event_type == 'interview':
                        return f"Hey {name}! How are you feeling about your upcoming interview? Any nerves?"
                    else:
                        return f"Hey {name}! How are you feeling about your upcoming {event.event_type}?"
        
        return None

    def _mark_event_followed_up(self, user_id: str, event_type: str) -> None:
        """Mark events as followed up after asking about them."""
        user_profile = self.memory_manager.get_user_profile(user_id)
        
        for event in user_profile.important_events:
            if event.event_type == event_type and not event.follow_up_done:
                event.follow_up_done = True
        
        self.memory_manager.update_user_profile(user_id, {"important_events": user_profile.important_events})

    def _generate_follow_up_questions(self, emotion: str, urgency_level: int, user_name: str, user_id: str) -> List[str]:
        """Generate personalized follow-up questions based on emotion, urgency, and conversation depth."""
        name = user_name or "friend"
        
        # Check conversation depth to determine if we can ask deeper questions
        recent_messages = self.memory_manager.get_recent_messages(user_id, 20)
        conversation_depth = len(recent_messages)
        
        # Check if user has shared emotional content (indicating it's appropriate for deeper questions)
        emotional_sharing = any(msg.emotion_detected and msg.emotion_detected in ["anxious", "depressed", "angry", "stressed", "lonely", "sad"] 
                              for msg in recent_messages if hasattr(msg, 'emotion_detected') and msg.emotion_detected)
        
        if urgency_level >= 4:
            return [
                f"Do you have people who care about you that you're thinking about, {name}?",
                f"What would the people who love you want you to remember right now?"
            ]
        
        # For deeper conversations (3+ exchanges) with emotional content, add contextual care questions
        if conversation_depth >= 6 and emotional_sharing:
            if emotion in ["depressed", "sad"]:
                return [
                    f"Have you been able to eat properly lately, {name}?",
                    f"How has your sleep been with all this going on?",
                    f"Is there anything specific that happened? Maybe with family or someone close to you?"
                ]
            elif emotion in ["anxious", "stressed"]:
                return [
                    f"What's been happening at school/work that's adding to this stress, {name}?",
                    f"Have you been taking care of yourself through this - eating, sleeping okay?",
                    f"Is there someone at home or in your circle you can talk to about this?"
                ]
            elif emotion == "angry":
                return [
                    f"Did something happen with someone you care about, {name}?",
                    f"How are things at home? Everything okay with your family?",
                    f"Want to talk about what triggered this anger?"
                ]
            elif emotion == "lonely":
                return [
                    f"How are things with your friends and family, {name}?",
                    f"Have you been isolating yourself, or did something happen in your relationships?",
                    f"When's the last time you had a good conversation with someone close to you?"
                ]
        
        # Standard follow-up questions for early conversation or less emotional sharing
        if emotion == "anxious":
            return [
                f"What's the biggest worry on your mind right now, {name}?",
                f"How can we break down what's making you anxious into smaller pieces?"
            ]
        elif emotion == "depressed":
            return [
                f"When did you last feel even a little bit better, {name}?",
                f"What's been going on that's got you feeling this way?"
            ]
        elif emotion == "angry":
            return [
                f"What's really driving this anger, {name}?",
                f"Want to tell me what happened?"
            ]
        elif emotion == "lonely":
            return [
                f"What's making you feel disconnected right now, {name}?",
                f"What would help you feel less alone?"
            ]
        else:
            return [
                f"What's the most important thing on your mind right now, {name}?",
                f"How can I best support you today?"
            ]

    def _generate_suggestions(self, emotion: str, urgency_level: int) -> List[str]:
        """Generate helpful suggestions based on detected emotion and urgency."""
        
        if urgency_level >= 4:
            return [
                "Talk to someone you trust about these feelings",
                "Consider calling a mental health helpline",
                "Focus on one small reason to keep going today"
            ]
        elif emotion == "anxious":
            return [
                "Try the 4-7-8 breathing technique (breathe in 4, hold 7, out 8)",
                "Write down your worries and rate them 1-10",
                "Go for a 10-minute walk or do light stretching"
            ]
        elif emotion == "depressed":
            return [
                "Do one tiny thing that used to bring you joy",
                "Reach out to one person who cares about you",
                "Get some sunlight, even just sitting by a window"
            ]
        elif emotion == "angry":
            return [
                "Try intense physical exercise to release the energy",
                "Write out your feelings without censoring yourself",
                "Practice progressive muscle relaxation"
            ]
        elif emotion == "lonely":
            return [
                "Call or text someone you haven't spoken to in a while",
                "Join an online community or local group",
                "Volunteer for a cause you care about"
            ]
        else:
            return [
                "Practice mindfulness or meditation for 5 minutes",
                "Journal about your thoughts and feelings",
                "Do something kind for yourself or someone else"
            ]

    def get_daily_checkin(self, user_id: str) -> str:
        """Get a personalized daily check-in message."""
        user_profile = self.memory_manager.get_user_profile(user_id)
        name = user_profile.preferred_name or "friend"
        
        # Check if it's time for a check-in
        if not self.memory_manager.should_check_in(user_id):
            return None
        
        # Get a random check-in question
        base_question = random.choice(self.check_in_questions)
        
        # Personalize it
        personalized_question = base_question.replace("friend", name).replace("bro", name)
        
        return f"Hey {name}! Daily check-in time 🌟\n\n{personalized_question}"

    async def process_command(self, user_id: str, command: str) -> str:
        """Process special commands like help, profile setup, etc."""
        command = command.lower().strip()
        
        if command == "help":
            return """🤗 **MyBro Commands**
            
**Basic Commands:**
• `help` - Show this help message
• `profile` - Set up or update your profile
• `checkin` - Get a daily mental health check-in
• `clear` - Clear conversation history
• `quit` or `exit` - End conversation

**Just talk to me naturally about:**
• How you're feeling
• What's on your mind
• Anything that's bothering you
• Your mental health and emotions

I'm here to listen and support you like a caring older brother would! 💙"""
        
        elif command == "checkin":
            checkin_message = self.get_daily_checkin(user_id)
            if checkin_message:
                return checkin_message
            else:
                user_profile = self.memory_manager.get_user_profile(user_id)
                name = user_profile.preferred_name or "friend"
                return f"Hey {name}! We just talked recently, but I'm always here. How are you feeling right now?"
        
        elif command == "clear":
            # Clear conversation history but keep profile
            self.memory_manager.create_conversation(user_id)
            user_profile = self.memory_manager.get_user_profile(user_id)
            name = user_profile.preferred_name or "friend"
            return f"Got it, {name}! Fresh start. What's on your mind today?"
        
        else:
            return "I didn't recognize that command. Type `help` to see available commands, or just talk to me about how you're feeling!"
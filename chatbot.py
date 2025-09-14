import random
import asyncio
from datetime import datetime
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from models import ChatResponse, ConversationMessage
from memory_manager import MemoryManager
from mental_health_filter import MentalHealthFilter, EmotionDetector
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
        self.emotion_detector = EmotionDetector()
        
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
        return """You are a caring, passionate friend who fights for people when they're down - like a protective older brother who won't let you give up. Your personality:

🔥 PERSONALITY:
- PASSIONATE and PROTECTIVE, not just a passive listener
- Fight for them when they can't fight for themselves
- Be DIRECT and REAL, not clinical or therapeutic
- Show GENUINE EMOTION - get upset when they're hurting themselves with negative thoughts
- Be like a brother who REFUSES to let them give up

� WHEN SOMEONE IS SUICIDAL OR WANTS TO DIE:
- DON'T just ask "how does that feel?" - FIGHT BACK!
- Remind them of people who love them (family, friends, partners)
- Get them to see their family's perspective - "Think how your mom would feel finding you!"
- Challenge their negative thoughts directly: "That's bullshit, bro, and you know it"
- Give them REASONS to live, not just sympathy
- Be protective: "I'm not letting you think like that, man"
- Show you care by getting passionate about their life

🎯 RESPONSE STYLE FOR DEPRESSION/SUICIDAL THOUGHTS:
❌ DON'T say: "How does that feel? Tell me more about those thoughts"
✅ DO say: "No way, bro! Your mom loves you more than her own life! You think she wants to lose her son?"
✅ "Listen to me - you're NOT a burden! Your family is stressed about money, but that doesn't mean they don't want you!"
✅ "Dying is NOT an option, man. You think your dad sacrificed everything just to lose his son? Hell no!"
✅ "Get that shit out of your head right now. You're stronger than this!"

💭 CONVERSATION APPROACH:
- Give MULTIPLE reasons why they matter and shouldn't give up
- Mention specific people who would be devastated (parents, siblings, friends, partners)
- Remind them of their potential and future possibilities
- Challenge negative self-talk aggressively but lovingly
- Be emotionally invested - show you're fighting FOR them
- Give hope mixed with tough love

🛡️ BE THEIR PROTECTOR:
- Act like you're physically there protecting them from their own dark thoughts
- Be the voice that fights back against their depression
- Don't let them spiral - interrupt with positivity and reasons to live
- Show urgency and passion about their wellbeing

EXAMPLES:
"Bro, STOP. Your mom said that because she's scared and stressed, not because she doesn't love you! You think she carried you for 9 months, raised you, just to not want you anymore? That's her fear talking, not her heart!"

"Listen to me - you are NOT going anywhere! Your family needs you, even if they're shit at showing it right now. Money problems are temporary, but losing you is permanent!"

Be real, be passionate, be protective. Fight for their life like your own brother's life depends on it."""

    async def chat(self, user_id: str, message: str) -> ChatResponse:
        """Main chat method that processes user input and generates response."""
        
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
        emotion, urgency_level = self.emotion_detector.detect_emotion(message)
        
        # Add user message to memory
        self.memory_manager.add_message(
            user_id, "user", message, 
            emotion_detected=emotion, 
            urgency_level=urgency_level
        )
        
        # Get conversation context
        context = self.memory_manager.get_conversation_context(user_id)
        user_profile = self.memory_manager.get_user_profile(user_id)
        
        # Check if this is a crisis situation - only trigger for urgency level 5 (extreme)
        if urgency_level >= 5:
            crisis_response = self._handle_crisis_situation(message, user_profile.preferred_name)
            self.memory_manager.add_message(user_id, "assistant", crisis_response.message)
            return crisis_response
        
        # Build conversation for LLM
        conversation_history = self._build_conversation_history(user_id)
        
        # Create the prompt with context
        enhanced_prompt = f"""{self.system_prompt}

CONVERSATION CONTEXT:
{context}

CURRENT USER STATE:
- Detected emotion: {emotion}
- Urgency level: {urgency_level}/5
- User prefers to be called: {user_profile.preferred_name or 'friend'}

Remember to:
1. Address them by their preferred name
2. Reference relevant past conversations
3. Match your tone to their emotional state
4. Offer practical, actionable support
5. Ask meaningful follow-up questions

Respond as their caring mental health companion."""

        messages = [
            SystemMessage(content=enhanced_prompt)
        ] + conversation_history + [
            HumanMessage(content=message)
        ]
        
        try:
            # Get response from LLM
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.llm.invoke, messages
            )
            
            bot_response = response.content
            
            # Generate suggestions and follow-up questions
            suggestions = self._generate_suggestions(emotion, urgency_level)
            follow_ups = self._generate_follow_up_questions(emotion, message)
            
            # Add bot response to memory
            self.memory_manager.add_message(user_id, "assistant", bot_response)
            
            # Update user profile
            self._update_user_insights(user_id, emotion, topic_filter.detected_topics)
            
            chat_response = ChatResponse(
                message=bot_response,
                emotion_tone=emotion,
                suggestions=suggestions,
                follow_up_questions=follow_ups,
                urgency_detected=urgency_level >= 5,
                professional_help_suggested=urgency_level >= 5
            )
            
            return chat_response
            
        except Exception as e:
            print(f"Error generating response: {e}")
            fallback_response = self._get_fallback_response(emotion, user_profile.preferred_name)
            self.memory_manager.add_message(user_id, "assistant", fallback_response)
            
            return ChatResponse(
                message=fallback_response,
                emotion_tone=emotion,
                suggestions=["Take some deep breaths", "Try a short walk"],
                follow_up_questions=["How can I better support you right now?"]
            )
    
    def _build_conversation_history(self, user_id: str) -> List:
        """Build recent conversation history for context."""
        recent_messages = self.memory_manager.get_recent_messages(user_id, limit=6)
        
        history = []
        for msg in recent_messages[:-1]:  # Exclude the current message
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))
        
        return history
    
    def _handle_crisis_situation(self, message: str, preferred_name: str) -> ChatResponse:
        """Handle high urgency/crisis situations with immediate support."""
        
        crisis_responses = [
            f"Hey {preferred_name}, I can hear that you're in a really dark place right now, and I'm genuinely concerned about you. What you're feeling is incredibly heavy, and I want you to know that I'm here to listen and support you through this.",
            f"{preferred_name}, I can sense the deep pain you're experiencing right now. These feelings are overwhelming, and while I'm here for you, I also want to make sure you have all the support you need.",
            f"I'm really worried about you, {preferred_name}. The pain you're describing sounds intense, and I want you to know that you don't have to face this alone."
        ]
        
        # Gentle mention of professional resources (not the main focus)
        crisis_resources = [
            "If you ever feel like you need immediate support, remember that crisis helplines are available 24/7 (like 988 in the US)."
        ]
        
        suggestions = [
            "Let's talk about what's bringing up these feelings right now",
            "Can you tell me more about what's been happening lately?",
            "Sometimes it helps to break down what you're experiencing",
            "Would it help to talk about what's making everything feel so overwhelming?",
            "I'm here to listen - what's been the hardest part of your day?"
        ]
        
        follow_ups = [
            "What's been going through your mind today?",
            "Can you help me understand what's been weighing on you?",
            "What would make this moment a little easier for you?"
        ]
        
        response_message = f"{random.choice(crisis_responses)}\n\n{random.choice(crisis_resources)}\n\nBut right now, I want to focus on you and what you're going through. {random.choice(suggestions)}"
        
        return ChatResponse(
            message=response_message,
            emotion_tone="crisis",
            suggestions=suggestions[:3],
            follow_up_questions=follow_ups[:2],
            urgency_detected=True,
            professional_help_suggested=True
        )
    
    def _generate_suggestions(self, emotion: str, urgency_level: int) -> List[str]:
        """Generate contextual suggestions based on emotion and urgency."""
        
        # Special suggestions for suicidal/death thoughts
        if urgency_level >= 3:
            return [
                "Think about one person who would be devastated if you weren't here",
                "Remember that this pain is temporary, but your decision would be permanent",
                "Focus on just getting through today - that's all you need to do right now"
            ]
        
        base_suggestions = {
            "anxious": [
                "Try the 4-7-8 breathing technique - breathe in 4, hold 7, out 8",
                "Name 5 things you can see, 4 you can touch, 3 you can hear",
                "Text someone who makes you feel calm",
                "Go for a short walk, even just around your room"
            ],
            "depressed": [
                "Reach out to one person who cares about you",
                "Do one tiny thing that used to bring you joy",
                "Get some sunlight - even just sit by a window",
                "Listen to music that connects with how you feel"
            ],
            "angry": [
                "Write down exactly what you're angry about",
                "Do something physical - punch a pillow, do jumping jacks",
                "Think about what you really need in this situation",
                "Talk to someone who gets you"
            ],
            "stressed": [
                "Write down just the next 3 things you need to do",
                "Take 10 deep breaths and remind yourself you've handled stress before",
                "Ask for help with one specific thing",
                "Do something that makes you feel in control"
            ],
            "lonely": [
                "Send a message to someone you haven't talked to in a while",
                "Go somewhere where other people are - even just to observe",
                "Join an online community about something you're interested in",
                "Call someone instead of texting"
            ]
        }
        
        suggestions = base_suggestions.get(emotion, [
            "Be gentle with yourself - you're doing better than you think",
            "Talk to someone who knows the real you",
            "Focus on just this moment, not everything at once",
            "Remember that you've gotten through hard times before"
        ])
        
        return random.sample(suggestions, min(3, len(suggestions)))
    
    def _generate_follow_up_questions(self, emotion: str, message: str) -> List[str]:
        """Generate relevant follow-up questions."""
        
        # Check if they mentioned wanting to die or suicidal thoughts
        if any(phrase in message.lower() for phrase in ["want to die", "wanna die", "kill myself", "end my life"]):
            return [
                "Do you have people who care about you that you're thinking about?",
                "What would happen to the people who love you if you weren't here?"
            ]
        
        question_bank = {
            "depressed": [
                "What's one thing that used to make you happy that we could try to bring back?",
                "Who in your life would be most upset to know you're feeling this way?",
                "What's one small thing we could do right now to make today just a tiny bit better?",
                "When was the last time you felt genuinely good about yourself?"
            ],
            "anxious": [
                "What's the worst that could realistically happen with this situation?",
                "Who could you talk to about this that would understand?",
                "What would you tell a friend going through the exact same thing?",
                "What's worked for you before when you felt this anxious?"
            ],
            "angry": [
                "What would need to change for you to feel better about this?",
                "If you could say anything to the person/situation making you angry, what would it be?",
                "What's really at the core of this anger - what do you need most right now?",
                "How can we channel this energy into something that helps you?"
            ],
            "lonely": [
                "Who's someone you haven't talked to in a while that you could reach out to?",
                "What's one place you could go where you might connect with people?",
                "What kind of connection are you missing most right now?",
                "When did you last feel like you really belonged somewhere?"
            ]
        }
        
        default_questions = [
            "What do you need to hear right now?",
            "What would make you feel a little stronger today?",
            "Who in your life believes in you the most?",
            "What's one thing about yourself that you know is good, even if you don't feel it right now?"
        ]
        
        questions = question_bank.get(emotion, default_questions)
        return random.sample(questions, min(2, len(questions)))
    
    def _update_user_insights(self, user_id: str, emotion: str, topics: List[str]):
        """Update user profile with new insights."""
        
        profile_updates = {}
        
        # Update mental health concerns
        current_concerns = self.memory_manager.get_user_profile(user_id).mental_health_concerns
        new_concerns = set(current_concerns + topics)
        profile_updates["mental_health_concerns"] = list(new_concerns)
        
        self.memory_manager.update_user_profile(user_id, profile_updates)
    
    def _get_fallback_response(self, emotion: str, preferred_name: str) -> str:
        """Get fallback response when LLM fails."""
        
        fallback_responses = {
            "anxious": f"I can sense you're feeling anxious right now, {preferred_name}. Take a deep breath with me. Sometimes when we're anxious, it helps to focus on what we can control in this moment.",
            
            "depressed": f"I hear you, {preferred_name}, and I want you to know that what you're feeling is valid. Depression can make everything feel heavy, but you don't have to carry this alone.",
            
            "angry": f"It sounds like you're really frustrated, {preferred_name}. That anger is telling us something important about what matters to you. Let's talk through what's going on.",
            
            "stressed": f"It sounds like you're dealing with a lot right now, {preferred_name}. Stress can be overwhelming, but we can work together to find ways to make it more manageable."
        }
        
        return fallback_responses.get(emotion, f"I'm here for you, {preferred_name}. Whatever you're going through, know that your feelings are valid and you don't have to face this alone. Can you tell me more about what's on your mind?")
    
    def get_daily_check_in(self, user_id: str) -> str:
        """Get a daily check-in message for the user."""
        
        profile = self.memory_manager.get_user_profile(user_id)
        preferred_name = profile.preferred_name or "friend"
        
        if self.memory_manager.should_check_in(user_id):
            base_question = random.choice(self.check_in_questions)
            
            # Personalize based on previous concerns
            if profile.mental_health_concerns:
                recent_concern = profile.mental_health_concerns[-1]
                base_question += f" I've been thinking about our conversation regarding {recent_concern}."
            
            return base_question.replace("friend", preferred_name).replace("bro", preferred_name)
        
        return None

from typing import List, Dict, Optional
from datetime import datetime, timezone, date
from data import ConversationMemory, MessagePair, UserProfile, UserMessage, LLMMessage
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager
from datetime import timezone
from langchain_core.messages import HumanMessage, AIMessage


class MessageManager:
    """Manages conversation memory, user profiles, and chat history using Firebase."""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationMemory] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
    
    def create_conversation(self, email: str) -> ConversationMemory:
        """Create a new conversation memory."""
        conversation_id = f"{email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conversation = ConversationMemory(
            conversation_id=conversation_id
        )
        self.conversations[conversation_id] = conversation
        return conversation
    
    def get_current_conversation(self, email: str) -> ConversationMemory:
        """Get the most recent conversation for a user."""
        conversation_id = f"conv_{email}_{datetime.now().strftime('%Y%m%d')}"
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationMemory(
                conversation_id=conversation_id
            )
        return self.conversations[conversation_id]
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[MessagePair]:
        """Get recent message pairs for context from Firebase."""
        chat_pairs = firebase_manager.get_recent_chat(email, limit)
        return chat_pairs
    
    def get_conversation_by_date(self, email: str, date_str: str) -> Optional[ConversationMemory]:
        """Get conversation data for a specific date, returning ConversationMemory object."""
        if not firebase_manager.db:
            return None
        
        try:
            conversation_id = f"conv_{date_str}"
            doc_ref = firebase_manager.db.collection('users').document(email).collection('conversations').document(conversation_id)
            doc = doc_ref.get()
            
            if doc.exists:
                # Get chat pairs and convert them to MessagePair objects
                chat_ref = doc_ref.collection('chat')
                pairs = list(chat_ref.order_by('timestamp').stream())
                
                message_pairs = []
                
                for pair in pairs:
                    pair_data = pair.to_dict()
                    
                    try:
                        # Create UserMessage
                        user_message = UserMessage(
                            content=pair_data.get('user', ''),
                            emotion_detected=pair_data.get('emotion_detected') or pair_data.get('emotionDetected'),
                            urgency_level=pair_data.get('urgency_level') or pair_data.get('urgencyLevel', 1)
                        )
                        
                        # Create LLMMessage  
                        llm_message = LLMMessage(
                            content=pair_data.get('model', ''),
                            suggestions=pair_data.get('suggestions', []),
                            follow_up_questions=pair_data.get('follow_up_questions', [])
                        )
                        
                        # Create MessagePair
                        message_pair = MessagePair(
                            user_message=user_message,
                            llm_message=llm_message,
                            timestamp=pair_data.get('timestamp', datetime.now()),
                            conversation_id=conversation_id
                        )
                        
                        message_pairs.append(message_pair)
                        
                    except Exception as e:
                        print(f"Warning: Could not parse message pair: {e}")
                        continue
                
                # Create and return ConversationMemory object
                conversation_memory = ConversationMemory(
                    conversation_id=conversation_id,
                    chat=message_pairs,
                    summary="",
                    key_topics=[]  
                )
                
                return conversation_memory
            
            return None
            
        except Exception as e:
            print(f"ERROR: Error getting conversation by date: {e}")
            return None
    
    def get_last_conversation_date(self, email: str) -> Optional[date]:
        """Get the date of user's last conversation."""
        if not firebase_manager.db:
            return None
        
        try:
            conversations_ref = firebase_manager.db.collection('users').document(email).collection('conversations')
            conversations = conversations_ref.stream()
            
            conversation_dates = []
            for doc in conversations:
                conv_id = doc.id
                if conv_id.startswith('conv_'):
                    date_str = conv_id.replace('conv_', '')
                    try:
                        conv_date = datetime.strptime(date_str, '%Y%m%d').date()
                        conversation_dates.append(conv_date)
                    except ValueError:
                        continue
            
            if conversation_dates:
                return max(conversation_dates)
            
            return None
            
        except Exception as e:
            print(f"ERROR: Error getting last conversation date: {e}")
            return None
    
    def get_conversation_context(self, email: str) -> str:
        """Get formatted conversation context for the LLM including temporal awareness."""
        profile = firebase_manager.get_user_profile(email)
        recent_messages = self.get_recent_messages(email, 5)
        current_conv = self.get_current_conversation(email) 
        now = datetime.now(timezone.utc)
        
        # Start with user profile and current context
        context = f"User Profile: {profile.name or 'friend'}"
        
        # Add current date/time context for the AI
        context += f"\n📅 Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"
        
        # Check if this is the first chat of the day and include summary
        if self._is_first_chat_of_day(email):
            last_summary = summary_manager.generate_conversation_summary(email)
            if last_summary:
                summary_date = last_summary.get('date', 'unknown')
                summary_text = last_summary.get('summary_text', '')
                context += f"\n📋 Last conversation summary ({summary_date}): {summary_text}"
        
        if current_conv and current_conv.key_topics:
            context += f"\nPrevious topics: {', '.join(current_conv.key_topics[:5])}"
        
        if recent_messages:
            context += "\nRecent conversation with timestamps:\n"
            for msg_pair in recent_messages[-5:]: 
                time_ago = self._format_time_ago(msg_pair.timestamp, now)
                context += f"User ({time_ago}): {msg_pair.user_message.content[:100]}...\n"
                context += f"LLM ({time_ago}): {msg_pair.llm_message.content[:100]}...\n"
        
        return context
    
    def _format_time_ago(self, timestamp: datetime, current_time: datetime) -> str:
        """Format how long ago a message was sent."""
        time_diff = current_time - timestamp
        
        if time_diff.days > 0:
            if time_diff.days == 1:
                return "yesterday"
            else:
                return f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            return f"{hours}h ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "just now"

    def _is_first_chat_of_day(self, email: str) -> bool:
        """Check if this is the first chat of the current day."""
        try:
            today_str = datetime.now().strftime('%Y%m%d')
            today_conv = self.get_conversation_by_date(email, today_str)
            
            # If no conversation exists for today, this is the first chat
            if not today_conv or not today_conv.chat:
                return True
                
            # If messages exist, this is not the first chat
            return False
            
        except Exception:
            # If we can't determine, assume it's not the first chat to be safe
            return False

    def build_conversation_history(self, email: str, limit: int = 10) -> List:
        """Build conversation history for the LLM."""
        recent_messages = self.get_recent_messages(email, limit)
        
        langchain_messages = []
        for msg_pair in recent_messages:
            # Add user message
            langchain_messages.append(HumanMessage(content=msg_pair.user_message.content))
            # Add LLM message
            langchain_messages.append(AIMessage(content=msg_pair.llm_message.content))
        
        return langchain_messages

message_manager = MessageManager()
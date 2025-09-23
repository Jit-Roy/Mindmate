from typing import List, Dict
from datetime import datetime, timezone
from data import ConversationMemory, MessagePair, UserProfile
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager
from datetime import timezone


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
            last_summary = summary_manager.get_last_conversation_summary(email)
            if last_summary:
                summary_date = last_summary.get('date', 'unknown')
                summary_text = last_summary.get('summary_text', '')
                context += f"\n📋 Last conversation summary ({summary_date}): {summary_text}"
        
        if current_conv and current_conv.summary:
            context += f"\nConversation Summary: {current_conv.summary}"
        
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
            today_conv = summary_manager.get_conversation_by_date(email, today_str)
            
            # If no messages exist for today, this is the first chat
            if not today_conv or not today_conv.get('messages'):
                return True
                
            # If messages exist, this is not the first chat
            return False
            
        except Exception:
            # If we can't determine, assume it's not the first chat to be safe
            return False

message_manager = MessageManager()
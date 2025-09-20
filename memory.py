import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from models import ConversationMemory, ConversationMessage, UserProfile
from config import config
from firebase_manager import firebase_manager


class MemoryManager:
    """Manages conversation memory, user profiles, and chat history using Firebase."""
    
    def __init__(self):
        # Firebase-first approach - no local storage
        self.conversations: Dict[str, ConversationMemory] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
    
    def create_user_profile(self, email: str, name: str = None) -> UserProfile:
        """Create a new user profile."""
        # Create in Firebase only
        profile = firebase_manager.create_user_profile(email, name, name)
        
        # Cache locally for performance
        self.user_profiles[email] = profile
        return profile
    
    def get_user_profile(self, email: str) -> UserProfile:
        """Get user profile from Firebase with correct lastInteraction."""
        # Get from the standard location first
        profile = firebase_manager.get_user_profile(email)
        
        # Try to get lastInteraction from profiles table
        try:
            user_key = email.replace('.', '_').replace('@', '_at_')
            profiles_data = firebase_manager.db_ref.child("profiles").child(user_key).get()
            
            if profiles_data and 'lastInteraction' in profiles_data:
                from datetime import datetime
                last_interaction_str = profiles_data['lastInteraction']
                profile.last_interaction = datetime.fromisoformat(last_interaction_str)
            
        except Exception as e:
            # Silently handle lastInteraction read errors - not critical for functionality
            pass
        
        # Cache locally for performance
        self.user_profiles[email] = profile
        return profile
    
    def get_all_user_profiles(self) -> Dict[str, UserProfile]:
        """Get all user profiles from Firebase."""
        return firebase_manager.get_all_user_profiles()
    
    def find_user_by_name(self, name: str) -> UserProfile:
        """Find user profile by name (case insensitive)."""
        return firebase_manager.find_user_by_name(name)
    
    def update_user_profile(self, email: str, updates: Dict[str, Any]):
        """Update user profile information."""
        # Update in Firebase only
        firebase_manager.update_user_profile(email, updates)
        
        # Update local cache if exists
        if email in self.user_profiles:
            profile = self.user_profiles[email]
            for key, value in updates.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.last_interaction = datetime.now()
    
    def create_conversation(self, email: str) -> ConversationMemory:
        """Create a new conversation memory."""
        conversation_id = f"{email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conversation = ConversationMemory(
            conversation_id=conversation_id,
            user_id=email
        )
        self.conversations[conversation_id] = conversation
        return conversation
    
    def add_message(self, email: str, role: str, content: str, 
                   emotion_detected: str = None, urgency_level: int = 1) -> ConversationMemory:
        """Add a message to the conversation."""
        # Add to Firebase only
        firebase_manager.add_message(email, role, content, emotion_detected, urgency_level)
        
        # For local cache, create a simple conversation object
        # This is just for immediate access, real data comes from Firebase
        current_conv = self.get_current_conversation(email)
        if not current_conv:
            conversation_id = f"conv_{email}_{datetime.now().strftime('%Y%m%d')}"
            current_conv = ConversationMemory(
                conversation_id=conversation_id,
                user_id=email
            )
            self.conversations[conversation_id] = current_conv
        
        message = ConversationMessage(
            role=role,
            content=content,
            emotion_detected=emotion_detected,
            urgency_level=urgency_level
        )
        
        current_conv.messages.append(message)
        current_conv.updated_at = datetime.now()
        
        return current_conv
    
    def get_current_conversation(self, email: str) -> ConversationMemory:
        """Get the most recent conversation for a user."""
        user_conversations = [
            conv for conv in self.conversations.values() 
            if conv.user_id == email
        ]
        if user_conversations:
            return max(user_conversations, key=lambda x: x.updated_at)
        return None
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[ConversationMessage]:
        """Get recent messages for context from Firebase."""
        # Get recent messages directly from Firebase
        messages_data = firebase_manager.get_recent_messages(email, limit)
        
        # Convert dictionaries to ConversationMessage objects
        messages = []
        for msg_data in messages_data:
            try:
                message = ConversationMessage(
                    role=msg_data.get('role', 'user'),
                    content=msg_data.get('content', ''),
                    timestamp=datetime.fromisoformat(msg_data['timestamp']) if msg_data.get('timestamp') else datetime.now(),
                    emotion_detected=msg_data.get('emotion_detected'),
                    urgency_level=msg_data.get('urgency_level', 1)
                )
                messages.append(message)
            except Exception as e:
                # Skip invalid messages silently
                continue
        
        return messages
    
    def summarize_conversation(self, conversation_id: str):
        """Create a summary of the conversation to manage memory."""
        if conversation_id not in self.conversations:
            return
        
        conv = self.conversations[conversation_id]
        
        # Simple summarization logic (can be enhanced with LLM)
        moods = []
        key_points = []
        
        for message in conv.messages:
            if message.role == "user":
                # Extract key information
                if message.emotion_detected:
                    moods.append(message.emotion_detected)
        
        # Create summary based on emotions and basic message count
        conv.key_topics = []  # Remove keyword-based topic extraction
        conv.summary = f"Conversation with {len(conv.messages)} messages. User moods: {', '.join(set(moods[-5:]))}"
        
        # Keep only recent messages and summary
        if len(conv.messages) > config.max_conversation_history:
            conv.messages = conv.messages[-config.max_conversation_history//2:]
        
        self.save_memory()
    
    def get_conversation_context(self, email: str) -> str:
        """Get formatted conversation context for the LLM including temporal awareness."""
        profile = self.get_user_profile(email)
        recent_messages = self.get_recent_messages(email, 5)
        current_conv = self.get_current_conversation(email)
        
        now = datetime.now()
        
        # Start with user profile and temporal context
        context = f"User Profile: {profile.display_name or 'friend'}"
        
        # Add temporal awareness about user's interaction patterns
        if profile.last_interaction:
            time_since_last = now - profile.last_interaction
            if time_since_last.days > 0:
                context += f"\n⏰ IMPORTANT TIME CONTEXT: Last conversation was {time_since_last.days} day(s) ago"
                if time_since_last.days == 1:
                    context += " (yesterday)"
                elif time_since_last.days >= 3:
                    context += f" - user has been away for {time_since_last.days} days"
                
                # Only include summary on first chat of the day
                if self._is_first_chat_of_day(email):
                    last_summary = self._get_last_conversation_summary(email)
                    if last_summary:
                        summary_date = last_summary.get('date', 'unknown')
                        summary_text = last_summary.get('summary_text', '')
                        context += f"\n📋 Last conversation summary ({summary_date}): {summary_text}"
                    
            elif time_since_last.seconds > 3600:
                hours_ago = time_since_last.seconds // 3600
                context += f"\n⏰ TIME CONTEXT: Last conversation was {hours_ago} hour(s) ago"
        
        # Add current date/time context for the AI
        context += f"\n📅 Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"
        
        if profile.mental_health_concerns:
            context += f"\nPrevious concerns: {', '.join(profile.mental_health_concerns[:3])}"
        
        if current_conv and current_conv.summary:
            context += f"\nConversation Summary: {current_conv.summary}"
        
        if current_conv and current_conv.key_topics:
            context += f"\nPrevious topics: {', '.join(current_conv.key_topics[:5])}"
        
        if recent_messages:
            context += "\nRecent conversation with timestamps:\n"
            for msg in recent_messages[-5:]:  # Show more recent messages with time
                time_ago = self._format_time_ago(msg.timestamp, now)
                context += f"{msg.role} ({time_ago}): {msg.content[:100]}...\n"
        
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
            # Get today's conversation data
            today_str = datetime.now().strftime('%Y%m%d')
            today_conv = firebase_manager.get_conversation_by_date(email, today_str)
            
            # If no messages exist for today, this is the first chat
            if not today_conv or not today_conv.get('messages'):
                return True
                
            # If messages exist, this is not the first chat
            return False
            
        except Exception:
            # If we can't determine, assume it's not the first chat to be safe
            return False

    def _get_last_conversation_summary(self, email: str) -> Optional[dict]:
        """Get the summary of user's last conversation day if it exists."""
        # Find the last day user actually had conversations (not just when they were online)
        last_conversation_date = firebase_manager.get_last_conversation_date(email)
        
        if last_conversation_date:
            today_date = datetime.now().date()
            
            # Only get summary if it's not today (today's conversation is ongoing)
            if last_conversation_date != today_date:
                date_str = last_conversation_date.strftime('%Y%m%d')
                return firebase_manager.get_daily_summary(email, date_str)
        
        return None

# Global memory manager instance
memory_manager = MemoryManager()

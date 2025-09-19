import json
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
from models import ConversationMemory, ConversationMessage, UserProfile
from config import config


class MemoryManager:
    """Manages conversation memory, user profiles, and chat history."""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationMemory] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        self.memory_file = "conversation_memory.json"
        self.profiles_file = "user_profiles.json"
        self.load_memory()
        self.load_profiles()
    
    def create_user_profile(self, user_id: str, name: str = None) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(
            user_id=user_id,
            name=name,
            preferred_name=name or "friend"
        )
        self.user_profiles[user_id] = profile
        self.save_profiles()
        return profile
    
    def get_user_profile(self, user_id: str) -> UserProfile:
        """Get user profile or create if doesn't exist."""
        if user_id not in self.user_profiles:
            return self.create_user_profile(user_id)
        return self.user_profiles[user_id]
    
    def get_all_user_profiles(self) -> Dict[str, UserProfile]:
        """Get all user profiles."""
        return self.user_profiles.copy()
    
    def find_user_by_name(self, name: str) -> UserProfile:
        """Find user profile by name (case insensitive)."""
        name_lower = name.lower()
        for profile in self.user_profiles.values():
            if (profile.name and profile.name.lower() == name_lower) or \
               (profile.preferred_name and profile.preferred_name.lower() == name_lower):
                return profile
        return None
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """Update user profile information."""
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            for key, value in updates.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.last_interaction = datetime.now()
            self.save_profiles()
    
    def create_conversation(self, user_id: str) -> ConversationMemory:
        """Create a new conversation memory."""
        conversation_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conversation = ConversationMemory(
            conversation_id=conversation_id,
            user_id=user_id
        )
        self.conversations[conversation_id] = conversation
        return conversation
    
    def add_message(self, user_id: str, role: str, content: str, 
                   emotion_detected: str = None, urgency_level: int = 1) -> ConversationMemory:
        """Add a message to the conversation."""
        # Get or create current conversation
        current_conv = self.get_current_conversation(user_id)
        if not current_conv:
            current_conv = self.create_conversation(user_id)
        
        message = ConversationMessage(
            role=role,
            content=content,
            emotion_detected=emotion_detected,
            urgency_level=urgency_level
        )
        
        current_conv.messages.append(message)
        current_conv.updated_at = datetime.now()
        
        # Trigger summarization if conversation is getting long
        if len(current_conv.messages) >= config.summary_trigger_length:
            self.summarize_conversation(current_conv.conversation_id)
        
        self.save_memory()
        return current_conv
    
    def get_current_conversation(self, user_id: str) -> ConversationMemory:
        """Get the most recent conversation for a user."""
        user_conversations = [
            conv for conv in self.conversations.values() 
            if conv.user_id == user_id
        ]
        if user_conversations:
            return max(user_conversations, key=lambda x: x.updated_at)
        return None
    
    def get_recent_messages(self, user_id: str, limit: int = 10) -> List[ConversationMessage]:
        """Get recent messages for context."""
        current_conv = self.get_current_conversation(user_id)
        if current_conv:
            return current_conv.messages[-limit:]
        return []
    
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
    
    def get_conversation_context(self, user_id: str) -> str:
        """Get formatted conversation context for the LLM including temporal awareness."""
        profile = self.get_user_profile(user_id)
        recent_messages = self.get_recent_messages(user_id, 5)
        current_conv = self.get_current_conversation(user_id)
        
        now = datetime.now()
        
        # Start with user profile and temporal context
        context = f"User Profile: {profile.preferred_name or 'friend'}"
        
        # Add temporal awareness about user's interaction patterns
        if profile.last_interaction:
            time_since_last = now - profile.last_interaction
            if time_since_last.days > 0:
                context += f"\n⏰ IMPORTANT TIME CONTEXT: Last conversation was {time_since_last.days} day(s) ago"
                if time_since_last.days == 1:
                    context += " (yesterday)"
                elif time_since_last.days >= 3:
                    context += f" - user has been away for {time_since_last.days} days"
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
    
    def should_check_in(self, user_id: str) -> bool:
        """Determine if it's time for a daily check-in."""
        profile = self.get_user_profile(user_id)
        time_since_last = datetime.now() - profile.last_interaction
        return time_since_last.days >= 1
    
    def save_memory(self):
        """Save conversation memory to file."""
        try:
            memory_data = {
                conv_id: {
                    "conversation_id": conv.conversation_id,
                    "user_id": conv.user_id,
                    "messages": [
                        {
                            "role": msg.role,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                            "emotion_detected": msg.emotion_detected,
                            "urgency_level": msg.urgency_level
                        } for msg in conv.messages
                    ],
                    "summary": conv.summary,
                    "key_topics": conv.key_topics,
                    "important_details": conv.important_details,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat()
                } for conv_id, conv in self.conversations.items()
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(memory_data, f, indent=2)
        except Exception as e:
            pass
    
    def load_memory(self):
        """Load conversation memory from file."""
        try:
            with open(self.memory_file, 'r') as f:
                memory_data = json.load(f)
            
            for conv_id, data in memory_data.items():
                messages = []
                for msg_data in data.get("messages", []):
                    message = ConversationMessage(
                        role=msg_data["role"],
                        content=msg_data["content"],
                        timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                        emotion_detected=msg_data.get("emotion_detected"),
                        urgency_level=msg_data.get("urgency_level", 1)
                    )
                    messages.append(message)
                
                conv = ConversationMemory(
                    conversation_id=data["conversation_id"],
                    user_id=data["user_id"],
                    messages=messages,
                    summary=data.get("summary", ""),
                    key_topics=data.get("key_topics", []),
                    important_details=data.get("important_details", {}),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"])
                )
                self.conversations[conv_id] = conv
                
        except FileNotFoundError:
            self.conversations = {}
        except Exception as e:
            pass
            self.conversations = {}
    
    def save_profiles(self):
        """Save user profiles to file."""
        try:
            profiles_data = {
                user_id: {
                    "user_id": profile.user_id,
                    "name": profile.name,
                    "age": profile.age,
                    "preferred_name": profile.preferred_name,
                    "mental_health_concerns": profile.mental_health_concerns,
                    "support_preferences": profile.support_preferences,
                    "created_at": profile.created_at.isoformat(),
                    "last_interaction": profile.last_interaction.isoformat()
                } for user_id, profile in self.user_profiles.items()
            }
            
            with open(self.profiles_file, 'w') as f:
                json.dump(profiles_data, f, indent=2)
        except Exception as e:
            pass
    
    def load_profiles(self):
        """Load user profiles from file."""
        try:
            with open(self.profiles_file, 'r') as f:
                profiles_data = json.load(f)
            
            for user_id, data in profiles_data.items():
                profile = UserProfile(
                    user_id=data["user_id"],
                    name=data.get("name"),
                    age=data.get("age"),
                    preferred_name=data.get("preferred_name"),
                    mental_health_concerns=data.get("mental_health_concerns", []),
                    support_preferences=data.get("support_preferences", []),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    last_interaction=datetime.fromisoformat(data["last_interaction"])
                )
                self.user_profiles[user_id] = profile
                
        except FileNotFoundError:
            self.user_profiles = {}
        except Exception as e:
            pass
            self.user_profiles = {}

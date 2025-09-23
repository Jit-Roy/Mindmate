"""
Summary Manager for Daily Conversation Summaries
Handles generation, storage, and retrieval of conversation summaries
"""

import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import firestore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import config
from data import MessagePair, UserMessage, LLMMessage, ConversationMemory


class SummaryManager:
    """Manages conversation summaries and daily summary generation."""
    
    def __init__(self, db=None):
        """Initialize with optional database connection."""
        self.db = db
        if not self.db:
            # Initialize Firebase if not provided
            try:
                if firebase_admin._apps:
                    self.db = firestore.client()
                else:
                    print("WARNING: Firebase not initialized for SummaryManager")
            except Exception as e:
                print(f"ERROR: Could not initialize Firebase in SummaryManager: {e}")
                self.db = None
        
        # Initialize LLM for summary generation
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.5  # Slightly lower temperature for more consistent summaries
        )
    
    # ==================== DAILY SUMMARY OPERATIONS ====================
    
    def daily_summary_exists(self, email: str, date_str: str) -> bool:
        """Check if a daily summary already exists for the given date."""
        if not self.db:
            return False
        
        try:
            doc_ref = self.db.collection('users').document(email).collection('summaries').document(f'daily_{date_str}')
            doc = doc_ref.get()
            return doc.exists
            
        except Exception as e:
            print(f"ERROR: Error checking daily summary existence: {e}")
            return False
    
    def get_conversation_by_date(self, email: str, date_str: str) -> Optional[dict]:
        """Get conversation data for a specific date, returning MessagePair objects."""
        if not self.db:
            return None
        
        try:
            conversation_id = f"conv_{date_str}"
            doc_ref = self.db.collection('users').document(email).collection('conversations').document(conversation_id)
            doc = doc_ref.get()
            
            if doc.exists:
                conversation = doc.to_dict()
                conversation['date'] = date_str
                
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
                
                conversation['message_pairs'] = message_pairs
                return conversation
            
            return None
            
        except Exception as e:
            print(f"ERROR: Error getting conversation by date: {e}")
            return None
    
    def store_daily_summary(self, email: str, date_str: str, summary: dict):
        """Store a daily conversation summary."""
        if not self.db:
            return
        
        try:
            self.db.collection('users').document(email).collection('summaries').document(f'daily_{date_str}').set(summary)
            print(f"SUCCESS: Stored daily summary for {email} on {date_str}")
            
        except Exception as e:
            print(f"ERROR: Error storing daily summary: {e}")
    
    def get_daily_summary(self, email: str, date_str: str) -> Optional[dict]:
        """Get daily summary for a specific date."""
        if not self.db:
            return None
        
        try:
            doc_ref = self.db.collection('users').document(email).collection('summaries').document(f'daily_{date_str}')
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
            
        except Exception as e:
            print(f"ERROR: Error getting daily summary: {e}")
            return None
    
    def get_all_summaries(self, email: str) -> List[Dict]:
        """Get all conversation summaries for a user, ordered by date."""
        if not self.db:
            return []
        
        try:
            summaries_ref = self.db.collection('users').document(email).collection('summaries')
            summaries = summaries_ref.order_by('date', direction=firestore.Query.DESCENDING).stream()
            
            summary_list = []
            for doc in summaries:
                summary_data = doc.to_dict()
                summary_data['document_id'] = doc.id
                summary_list.append(summary_data)
            
            return summary_list
            
        except Exception as e:
            print(f"ERROR: Error getting all summaries: {e}")
            return []
    
    def get_last_conversation_date(self, email: str) -> Optional[date]:
        """Get the date of user's last conversation."""
        if not self.db:
            return None
        
        try:
            conversations_ref = self.db.collection('users').document(email).collection('conversations')
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
    
    # ==================== SUMMARY GENERATION ====================
    
    def generate_daily_summary_if_needed(self, email: str) -> Optional[dict]:
        """Generate summary for the user's last conversation day if needed."""
        # Find the last day user had a conversation
        last_conversation_date = self.get_last_conversation_date(email)
        
        if last_conversation_date:
            date_str = last_conversation_date.strftime('%Y%m%d')
            today_str = date.today().strftime('%Y%m%d')
            
            # Only generate if it's not today and summary doesn't exist
            if date_str != today_str and not self.daily_summary_exists(email, date_str):
                conversation_data = self.get_conversation_by_date(email, date_str)
                
                if conversation_data and len(conversation_data.get('message_pairs', [])) > 0:
                    # Generate summary for the last conversation day
                    summary = self.generate_conversation_summary(email, conversation_data, last_conversation_date)
                    if summary:
                        self.store_daily_summary(email, date_str, summary)
                        return summary
        
        return None

    def generate_conversation_summary(self, email: str, conversation_data: dict, conversation_date) -> Optional[dict]:
        """Generate AI summary of a day's conversation using LLM."""
        
        # Build conversation text from MessagePair objects
        message_pairs = conversation_data.get('message_pairs', [])
        conversation_text = ""
        emotions = []
        urgency_levels = []
        
        for message_pair in message_pairs:
            if isinstance(message_pair, MessagePair):
                # Extract user message info
                user_content = message_pair.user_message.content
                llm_content = message_pair.llm_message.content
                
                conversation_text += f"User: {user_content}\n"
                conversation_text += f"Assistant: {llm_content}\n"
                
                # Collect emotional data
                if message_pair.user_message.emotion_detected:
                    emotions.append(message_pair.user_message.emotion_detected)
                if message_pair.user_message.urgency_level:
                    urgency_levels.append(message_pair.user_message.urgency_level)
        
        if not conversation_text.strip():
            return None
        
        # Generate summary using LLM
        summary_prompt = f"""Summarize this conversation between a user and their mental health support friend:

CONVERSATION:
{conversation_text}

Create a friendly summary that covers:
1. What the user talked about and how they were feeling
2. Main topics or concerns they shared
3. Any positive moments or progress they mentioned
4. Important things to remember for next time you chat
5. How they seemed to be feeling by the end

Keep it:
- Simple and conversational (like notes a friend would take)
- Under 120 words
- Focused on what matters for continuing the friendship
- Written like "User talked about..." or "They seemed..."
- Remember this is for helping continue supportive conversations

Write a natural summary that helps remember what happened in this chat."""

        try:
            messages = [
                SystemMessage(content="You are a caring friend creating simple conversation summaries to help remember what you talked about with someone. Write in a natural, friendly tone like you're taking notes to remember for next time."),
                HumanMessage(content=summary_prompt)
            ]
            
            response = self.llm.invoke(messages)
            summary_text = response.content.strip()
            
            return {
                "date": conversation_date.strftime('%Y-%m-%d'),
                "summary_text": summary_text,
                "emotion_trend": list(set(emotions)) if emotions else [],
                "avg_urgency": sum(urgency_levels) / len(urgency_levels) if urgency_levels else 1,
                "message_count": len(message_pairs)
            }
            
        except Exception as e:
            # Silently handle summary generation errors - not critical for chat functionality
            print(f"Warning: Could not generate summary: {e}")
            return None
    
    def get_last_conversation_summary(self, email: str) -> Optional[dict]:
        """Get the summary of user's last conversation day if it exists."""
        # Find the last day user actually had conversations (not just when they were online)
        last_conversation_date = self.get_last_conversation_date(email)
        
        if last_conversation_date:
            today_date = date.today()
            
            # Only get summary if it's not today (today's conversation is ongoing)
            if last_conversation_date != today_date:
                date_str = last_conversation_date.strftime('%Y%m%d')
                return self.get_daily_summary(email, date_str)
        
        return None

    def summarize_conversation(self, conversation_id: str, messages: List[MessagePair]) -> str:
        """Create a simple summary of a conversation for memory management."""
        if not messages:
            return "No conversation to summarize."
        
        # Extract mood information from MessagePair objects
        moods = []
        urgency_levels = []
        
        for message_pair in messages:
            if isinstance(message_pair, MessagePair):
                # Extract emotion from user message
                if message_pair.user_message.emotion_detected:
                    moods.append(message_pair.user_message.emotion_detected)
                # Extract urgency level
                if message_pair.user_message.urgency_level:
                    urgency_levels.append(message_pair.user_message.urgency_level)
        
        # Create summary with meaningful information
        mood_summary = f"User moods: {', '.join(set(moods[-5:]))}" if moods else "No mood data"
        avg_urgency = sum(urgency_levels) / len(urgency_levels) if urgency_levels else 1
        urgency_note = f"Average urgency: {avg_urgency:.1f}/5" if urgency_levels else ""
        
        summary_parts = [
            f"Conversation with {len(messages)} message pairs",
            mood_summary
        ]
        
        if urgency_note:
            summary_parts.append(urgency_note)
        
        return ". ".join(summary_parts) + "."

    def create_conversation_memory(self, conversation_id: str, message_pairs: List[MessagePair]) -> ConversationMemory:
        """Create a ConversationMemory object from MessagePair objects."""
        return ConversationMemory(
            conversation_id=conversation_id,
            chat=message_pairs,
            summary=self.summarize_conversation(conversation_id, message_pairs),
            key_topics=[]  # Could be enhanced to extract topics from conversation
        )


# Global summary manager instance
summary_manager = SummaryManager()
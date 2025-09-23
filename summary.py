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
            try:
                if firebase_admin._apps:
                    self.db = firestore.client()
                else:
                    print("WARNING: Firebase not initialized for SummaryManager")
            except Exception as e:
                print(f"ERROR: Could not initialize Firebase in SummaryManager: {e}")
                self.db = None
        
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.5  
        )

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
    
    def generate_conversation_summary(self, email: str, conversation_date: Optional[date] = None) -> Optional[dict]:
        """Generate or retrieve AI summary of a day's conversation using LLM."""
        # Import here to avoid circular import
        from message import message_manager
        
        # If no date provided, get the last conversation date
        if conversation_date is None:
            conversation_date = message_manager.get_last_conversation_date(email)
            if not conversation_date:
                return None
        
        date_str = conversation_date.strftime('%Y%m%d')
        today_str = date.today().strftime('%Y%m%d')
        
        # Only generate if it's not today (today's conversation is ongoing)
        if date_str == today_str:
            return None
            
        # Check if summary already exists
        if self.daily_summary_exists(email, date_str):
            return self.get_daily_summary(email, date_str)
        
        # Get conversation data for the specified date
        conversation_data = message_manager.get_conversation_by_date(email, date_str)
        
        if not conversation_data or len(conversation_data.chat) == 0:
            return None
        
        # Build conversation text from MessagePair objects
        message_pairs = conversation_data.chat
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
            
            summary = {
                "date": conversation_date.strftime('%Y-%m-%d'),
                "summary_text": summary_text,
                "emotion_trend": list(set(emotions)) if emotions else [],
                "avg_urgency": sum(urgency_levels) / len(urgency_levels) if urgency_levels else 1,
                "message_count": len(message_pairs)
            }
            
            # Store the generated summary
            self.store_daily_summary(email, date_str, summary)
            return summary
            
        except Exception as e:
            # Silently handle summary generation errors - not critical for chat functionality
            print(f"Warning: Could not generate summary: {e}")
            return None

summary_manager = SummaryManager()
"""
Daily Task Manager
Handles all daily operations including summary creation, notifications, greetings, and message updates
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from firebase_manager import firebase_manager
from message import message_manager
from summary import summary_manager
from events import event_manager
from config import config
from data import Event


class DailyTaskManager:
    """Manages all daily tasks and operations for the mental health chatbot."""
    
    def __init__(self):
        """Initialize the daily task manager with necessary components."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.7
        )
        
    def daily_task(self, email: str) -> None:
        """Generate a personalized daily greeting based on user's recent activity."""
        events = event_manager.get_events(email)
        greeting = event_manager._generate_event_greeting(events, email)
        event_manager.delete_events(events, email)
        notification = message_manager.generate_notification_text(email)

        today = date.today().isoformat()

        last_message_date = message_manager.get_last_conversation_time(email)
        last_day_conversation = message_manager.get_conversation(email, last_message_date)
        conversation_summary = summary_manager.generate_conversation_summary(last_day_conversation)
        summary_manager.store_daily_summary(email, today, {"summary_text": conversation_summary})
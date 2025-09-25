"""
Daily Task Manager
Handles all daily operations including summary creation, notifications, greetings, and message updates
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from data import Event


class DailyTaskManager:
    """Manages all daily tasks and operations for the mental health chatbot."""

    def __init__(self, config):
        """Initialize the daily task manager with necessary components."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.7
        )
        
    def daily_task(self, email: str,event_manager, message_manager,config,firebase_manager,summary_manager) -> (str, str):
        """Generate a personalized daily greeting based on user's recent activity."""
        # Generate Greeting
        events = event_manager.get_events(email)
        greeting = event_manager._generate_event_greeting(events, email,firebase_manager)
        event_manager.delete_events(events, email) 

        # Send Notification
        notification = message_manager.generate_notification_text(email,config,firebase_manager)

        # Store Daily Summary
        today = date.today().isoformat()
        last_message_date = message_manager.get_last_conversation_time(email,firebase_manager)
        last_day_conversation = message_manager.get_conversation(email, firebase_manager,last_message_date)
        conversation_summary = summary_manager.generate_conversation_summary(last_day_conversation)
        summary_manager.store_daily_summary(email, today, {"summary_text": conversation_summary})
        return greeting, notification
    
# """
# Daily Task Manager
# Handles all daily operations including summary creation, notifications, greetings, and message updates
# """

# from datetime import datetime, date, timedelta
# from typing import List, Optional, Dict, Any
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.messages import SystemMessage, HumanMessage
# from data import Event
# from events import EventManager
# from message import MessageManager
# from summary import SummaryManager
# from firebase_manager import FirebaseManager
# from config import Config


# class DailyTaskManager:
#     """Manages all daily tasks and operations for the mental health chatbot."""

#     def __init__(self, config: Config):
#         self.config = config
#         """Initialize the daily task manager with necessary components."""
#         self.llm = ChatGoogleGenerativeAI(
#             model=config.model_name,
#             google_api_key=config.gemini_api_key,
#             temperature=0.7
#         )
        
        
#         #self.config = Config
#         self.firebase_manager = FirebaseManager()
#         self.event_manager = EventManager(self.config, self.firebase_manager)
#         self.message_manager = MessageManager(self.config, self.firebase_manager)
#         self.summary_manager = SummaryManager(self.config, self.firebase_manager.db)

#     def daily_task(self, email: str) -> tuple[str, str]:
#         """Generate a personalized daily greeting based on user's recent activity."""
        
            
#         events = self.event_manager.get_events(email)
#         greeting = self.event_manager._generate_event_greeting(events, email, self.firebase_manager)
#         self.event_manager.delete_events(events, email) 

#         # Send Notification
#         notification = self.message_manager.generate_notification_text(email, self.config, self.firebase_manager)

#         # Store Daily Summary
#         today = date.today().isoformat()
#         last_message_date = message_manager.get_last_conversation_time(email,firebase_manager)
#         last_day_conversation = message_manager.get_conversation(email, firebase_manager, last_message_date)
#         conversation_summary = summary_manager.generate_conversation_summary(last_day_conversation)
#         summary_manager.store_daily_summary(email, today, {"summary_text": conversation_summary})
#         return greeting, notification
    
    
    

from datetime import date
from config import Config
from firebase_manager import FirebaseManager
from events import EventManager
from message import MessageManager
from summary import SummaryManager
import logging

def run_daily_task_for_user(email: str) -> tuple[str, str]:
    
    
    try:
        config = Config()
        firebase_manager = FirebaseManager()
        event_manager = EventManager(config, firebase_manager)
        message_manager = MessageManager(firebase_manager)
        summary_manager = SummaryManager(config, firebase_manager.db)
    except Exception as e:
        logging.error(f"Error initializing components for {email}: {e}", exc_info=True)
        return "Error: Could not initialize components.", "Error: Initialization failed."

    try:
        
        events = event_manager.get_events(email)
        greeting = event_manager._generate_event_greeting(events, email, firebase_manager)
        event_manager.delete_events(events, email)

        
        notification = message_manager.generate_notification_text(email, config, firebase_manager)

        
        today_iso = date.today().isoformat()
        
        
        last_message_time = message_manager.get_last_conversation_time(firebase_manager,email)
        
        
        if last_message_time:
            
            last_message_date_str = last_message_time.strftime('%Y%m%d')
            
            
            last_day_conversation = message_manager.get_conversation(
                email, firebase_manager, date=last_message_date_str
            )
            
            
            if last_day_conversation:
                conversation_summary = summary_manager.generate_conversation_summary(last_day_conversation)
                
                
                if conversation_summary:
                    summary_manager.store_daily_summary(
                        email, today_iso, {"summary_text": conversation_summary}
                    )

        return greeting, notification

    except Exception as e:
        logging.error(f"Error executing daily task for {email}: {e}", exc_info=True)
        return "Error during task execution.", "Could not generate notification."
    
    

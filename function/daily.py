from datetime import date
from config import Config
from managers.firebase_manager import FirebaseManager
from managers.message import MessageManager
from managers.summary import SummaryManager
import logging
from typing import Union, Tuple


def run_daily_task_for_user(email: str) -> None:
    
    try:
        config = Config()
        firebase_manager = FirebaseManager()
        message_manager = MessageManager(firebase_manager)
        summary_manager = SummaryManager(config, firebase_manager.db)
    except Exception as e:
        logging.error(f"Error initializing components for {email}: {e}", exc_info=True)
        return 

    try:
        
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

        # no need return
        #return greeting, notification

    except Exception as e:
        logging.error(f"Error executing daily task for {email}: {e}", exc_info=True)
        #return "Error during task execution.", "Could not generate notification."
    
    

def send_notification(email: str) -> Union[str, Tuple[str, str]]:
    try:
        config = Config()
        firebase_manager = FirebaseManager()
        message_manager = MessageManager(firebase_manager)
    except Exception as e:
        logging.error(f"Error initializing components for {email}: {e}", exc_info=True)
        return "Error: Could not initialize components.", "Error: Initialization failed."

    try:
        notification = message_manager.generate_notification_text(email, config, firebase_manager)
        return notification

    except Exception as e:
        logging.error(f"Error executing daily task for {email}: {e}", exc_info=True)
        return "Error during task execution.", "Could not generate notification."
    
    
    

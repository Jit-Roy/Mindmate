import sys
import os
sys.path.append(os.getcwd())

from chatbot import MentalHealthChatbot

chatbot = MentalHealthChatbot()

def android_chat(user_prompt, user_email):
    """Simplified Android chat function using unified chatbot processor."""
    try:
        return chatbot.process_conversation(user_email, user_prompt)
        
    except Exception as e:
        return f"Sorry, I'm having technical difficulties. Please try again later. Error: {e}"
from typing import List, Dict, Optional
from datetime import datetime, timezone, date, timedelta
from firebase_admin import firestore
from data import ConversationMemory, MessagePair, UserProfile, UserMessage, LLMMessage
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager
from datetime import timezone
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI


class MessageManager:
    """Manages conversation memory, user profiles, and chat history using Firebase."""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationMemory] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        self.db = firebase_manager.db
    
    def add_chat_pair(self, email: str, user_message: str, model_response: str, emotion_detected: str = None, urgency_level: int = 1, suggestions: List[str] = None, follow_up_questions: List[str] = None):
        """Add a chat pair (user + model response) to Firestore."""
        if not self.db:
            return
        
        try:
            now = datetime.now()
            conversation_id = f"conv_{now.strftime('%Y%m%d')}"
            
            chat_pair_data = {
                "user": user_message,
                "model": model_response,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "emotion_detected": emotion_detected,  
                "urgency_level": urgency_level,      
                "suggestions": suggestions or [],     
                "follow_up_questions": follow_up_questions or [] 
            }
            
            # Add chat pair to user's conversation subcollection
            self.db.collection('users').document(email).collection('conversations').document(conversation_id).collection('chat').add(chat_pair_data)
            
            # Update conversation metadata
            conv_doc_ref = self.db.collection('users').document(email).collection('conversations').document(conversation_id)
            conv_doc = conv_doc_ref.get()
            
            if conv_doc.exists:
                existing_metadata = conv_doc.to_dict()
                pair_count = existing_metadata.get('MessagePairCount', 0) + 1
                message_count = existing_metadata.get('messageCount', 0) + 2  
            else:
                pair_count = 1
                message_count = 2 
            
            metadata = {
                "startDate": now.strftime('%Y-%m-%d'),
                "MessagePairCount": pair_count,
                "messageCount": message_count,
                "lastChatAt": firestore.SERVER_TIMESTAMP,
                "lastMessageAt": firestore.SERVER_TIMESTAMP
            }
            
            conv_doc_ref.set(metadata, merge=True)
            
        except Exception as e:
            print(f"ERROR: Error adding chat pair: {e}")
    
    def get_conversation(self, email: str, date: Optional[str] = None, limit: Optional[int] = None) -> List[MessagePair]:
        """
        Get conversation messages for a specific date with optional limit.
        
        Args:
            email: User's email address
            date: Date string in YYYYMMDD format. If None, uses today's date.
            limit: Maximum number of messages to return. If None, returns all messages. When limit is specified, returns the most recent messages first.
        
        Returns:
            List[MessagePair]: List of message pairs ordered chronologically (oldest first) unless limited, then most recent messages are returned.
        """
        if not firebase_manager.db:
            return []
        
        # Use today's date if no date provided
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        try:
            conversation_id = f"conv_{date}"
            doc_ref = firebase_manager.db.collection('users').document(email).collection('conversations').document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return []
            
            chat_ref = doc_ref.collection('chat')
            
            # Apply limit if specified (get most recent messages)
            if limit is not None:
                query = chat_ref.order_by('timestamp', direction='DESCENDING').limit(limit)
                pairs = list(query.stream())
                # Reverse to get chronological order (oldest first)
                pairs.reverse()
            else:
                # Get all messages in chronological order
                query = chat_ref.order_by('timestamp')
                pairs = list(query.stream())
            
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
            
            return message_pairs
            
        except Exception as e:
            print(f"ERROR: Error getting conversation: {e}")
            return []

    def get_last_conversation_time(self, email: str) -> Optional[datetime]:
        """Get the timestamp of the user's last message from any conversation date."""
        if not firebase_manager.db:
            return None
        
        try:
            conversations_ref = firebase_manager.db.collection('users').document(email).collection('conversations')
            conversations = conversations_ref.stream()
            latest_timestamp = None
            
            for doc in conversations:
                conv_id = doc.id
                if conv_id.startswith('conv_'):
                    try:
                        chat_ref = conversations_ref.document(conv_id).collection('chat')
                        last_message_query = chat_ref.order_by('timestamp', direction='DESCENDING').limit(1)
                        last_messages = last_message_query.stream()
                        
                        for message_doc in last_messages:
                            message_data = message_doc.to_dict()
                            timestamp = message_data.get('timestamp')
                            if timestamp:
                                if latest_timestamp is None or timestamp > latest_timestamp:
                                    latest_timestamp = timestamp
                                    
                    except Exception as conv_error:
                        print(f"Warning: Error processing conversation {conv_id}: {conv_error}")
                        continue
            return latest_timestamp
            
        except Exception as e:
            print(f"ERROR: Error getting last conversation time: {e}")
            return None
    
    def _is_first_chat_of_day(self, email: str) -> bool:
        """
        Returns True if this is the user's first chat of the day, False otherwise.
        """
        try:
            today_str = datetime.now().strftime('Y%m%d')
            conversation_id = f"conv_{today_str}"
            doc_ref = self.db.collection('users').document(email).collection('conversations').document(conversation_id)
            doc = doc_ref.get()
            # If the conversation document does not exist, it's the first chat of the day
            return not doc.exists
        except Exception as e:
            print(f"ERROR: Error checking first chat of day: {e}")
            return False

    def generate_notification_text(self, email: str) -> str:
        """Generate a short, comforting notification text based on recent activity and context."""
        try:
            now = datetime.now(timezone.utc)
            today = now.strftime('%Y%m%d')
            yesterday = (now - timedelta(days=1)).strftime('%Y%m%d')
            
            user_profile = firebase_manager.get_user_profile(email)
            user_name = user_profile.name
            last_message_time = self.get_last_conversation_time(email)
            
            if last_message_time:
                try:
                    if last_message_time.tzinfo is None:
                        last_message_time = last_message_time.replace(tzinfo=timezone.utc)
                    
                    hours_since_last = (now - last_message_time).total_seconds() / 3600
                    days_since_last = hours_since_last / 24
                    
                    # Don't send notification if too recent
                    if hours_since_last < 6:  
                        return ""
                    
                    # Determine which conversation to use based on when the last message was
                    last_message_date = last_message_time.date()
                    last_message_date_str = last_message_date.strftime('%Y%m%d')
                    
                    # Get conversation from the actual date of last message
                    recent_messages = self.get_conversation(email, last_message_date_str)
                    
                    if recent_messages and len(recent_messages) > 0:
                        if hours_since_last < 24:
                            conversation_context = f"User has been away for {int(hours_since_last)} hours after chatting earlier today"
                        elif days_since_last < 2:
                            conversation_context = "User has been away since yesterday"
                        else:
                            conversation_context = f"User hasn't been active since {last_message_date.strftime('%B %d')}"
                    else:
                        conversation_context = f"Hey {user_name}, Missing you. Are you feeling okay??"
                        
                except Exception as tz_error:
                    print(f"Timezone handling error: {tz_error}")
                    conversation_context = f"Hey {user_name}, Missing you. Are you feeling okay??"
            else:
                # No messages found at all
                return f"Hey {user_name}, Missing you. Are you feeling okay??"
            
            # Build context from recent messages
            context_text = ""
            if 'recent_messages' in locals():
                for pair in recent_messages:
                    context_text += f"User: {pair.user_message.content}\n"
                    context_text += f"Assistant: {pair.llm_message.content}\n"
            
            llm = ChatGoogleGenerativeAI(
                model=config.model_name,
                google_api_key=config.gemini_api_key,
                temperature=0.8
            )
            
            system_prompt = """You are a formal but caring big brother. Generate a SHORT notification (maximum 15 words) in the FORMAL BIG BROTHER + 2 QUESTIONS + CONCERN style.

            REQUIRED STYLE FORMAT:
            "[Name], [first concern question]? [second supportive question]??"

            GUIDELINES:
            - Always ask 2 short questions, both ending with "?" (second one with "??").
            - Keep total length under 15 words.
            - Maintain a formal yet caring big brother tone.
            - Show genuine concern based on their situation.

            QUESTION STARTERS: "How was", "Feeling", "Still", "Is", "Did", "Was", "Are you"
            TONE: Warm, supportive, checking in with care.

            EXAMPLES:
            - "Alex, how was class today? Feeling better now??"
            - "Sarah, was chemistry easier? Less stress this time??"
            - "Emma, was your day kind? Heart calmer this evening??"
            """
            
            human_prompt = f"""Analyze this conversation with {user_name} and create a FORMAL BIG BROTHER notification:

            USER SITUATION: {conversation_context if 'conversation_context' in locals() else "User has been away for several hours"}

            RECENT CONVERSATION:
            {context_text if context_text else "No recent conversation available"}

            TASK: Create a notification using this EXACT FORMAT:
            "[Name], [first concern question]? [second supportive question]??"

            The notification must be under 15 words, show concern, and match their current situation.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = llm.invoke(messages)
            notification_text = response.content.strip()
            
            # Remove quotes if LLM wrapped the response
            if notification_text.startswith('"') and notification_text.endswith('"'):
                notification_text = notification_text[1:-1]
            
            return notification_text
            
        except Exception as e:
            print(f"ERROR: Error generating notification text: {e}")
            user_profile = firebase_manager.get_user_profile(email)
            user_name = user_profile.name 
            return f"Hey {user_name}, Missing you. Are you feeling okay??"

message_manager = MessageManager()
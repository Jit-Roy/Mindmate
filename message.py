from typing import List, Dict, Optional
from datetime import datetime, timezone, date
from firebase_admin import firestore
from data import ConversationMemory, MessagePair, UserProfile, UserMessage, LLMMessage
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager
from datetime import timezone
from langchain_core.messages import HumanMessage, AIMessage


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
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[MessagePair]:
        """Get recent chat pairs from Firestore as List[MessagePair]."""
        today = datetime.now().strftime('%Y%m%d')
        conversation_id = f"conv_{today}"
        
        if not firebase_manager.db:
            return []
        
        try:
            chat_ref = firebase_manager.db.collection('users').document(email).collection('conversations').document(conversation_id).collection('chat')
            chat = chat_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
            
            chat_pair_list = []
            for doc in chat:
                pair_data = doc.to_dict()
                user_message = UserMessage(
                    content=pair_data.get('user', ''),
                    emotion_detected=pair_data.get('emotion_detected') or pair_data.get('emotionDetected'),
                    urgency_level=pair_data.get('urgency_level') or pair_data.get('urgencyLevel', 1)
                )
                
                llm_message = LLMMessage(
                    content=pair_data.get('model', ''),
                    suggestions=pair_data.get('suggestions', []),
                    follow_up_questions=pair_data.get('follow_up_questions', [])
                )
                
                chat_pair = MessagePair(
                    user_message=user_message,
                    llm_message=llm_message,
                    timestamp=pair_data.get('timestamp', datetime.now())
                )
                chat_pair_list.append(chat_pair)
            
            chat_pair_list.reverse()
            
            return chat_pair_list
            
        except Exception as e:
            print(f"ERROR: Error getting recent chat pairs: {e}")
        
        return []
    
    def get_conversation_by_date(self, email: str, date_str: str) -> List[MessagePair]:
        """Get conversation data for a specific date, returning list of MessagePair objects."""
        if not firebase_manager.db:
            return []
        
        try:
            conversation_id = f"conv_{date_str}"
            doc_ref = firebase_manager.db.collection('users').document(email).collection('conversations').document(conversation_id)
            doc = doc_ref.get()
            
            if doc.exists:
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
                
                return message_pairs
            
            return []
            
        except Exception as e:
            print(f"ERROR: Error getting conversation by date: {e}")
            return []
    
    def get_last_conversation_date(self, email: str) -> Optional[date]:
        """Get the date of user's last conversation."""
        if not firebase_manager.db:
            return None
        
        try:
            conversations_ref = firebase_manager.db.collection('users').document(email).collection('conversations')
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

message_manager = MessageManager()

"""
Firebase Manager for Email-Based User Schema
No sessions, no analytics, no separate tables - just users organized by email
"""

import os
import secrets
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter
from data import UserProfile, MessagePair, Event, UserMessage, LLMMessage

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class FirebaseManager:
    """Firebase manager with email-based user organization using Firestore."""
    
    def __init__(self):
        self.db = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase using environment variables or service account file."""
        try:
            if not firebase_admin._apps:
                # Try environment variables first
                if self._use_env_credentials():
                    print("SUCCESS: Firebase initialized with environment variables!")
                # Fallback to service account file
                elif self._use_service_account_file():
                    print("SUCCESS: Firebase initialized with service account file!")
                else:
                    raise Exception("No valid Firebase credentials found")
            
            self.db = firestore.client()
            
        except Exception as e:
            print(f"ERROR: Firebase initialization failed: {e}")
            self.db = None
    
    def _use_env_credentials(self):
        """Try to initialize Firebase using environment variables."""
        try:
            # Check if required environment variables exist
            project_id = os.getenv('FIREBASE_PROJECT_ID') or 'mybro-a1ea5'
            private_key = os.getenv('FIREBASE_PRIVATE_KEY')
            client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
            
            if not all([private_key, client_email]):
                return False
            
            # Create credentials from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key.replace('\\n', '\n'),
                "client_email": client_email,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            return True
            
        except Exception as e:
            print(f"Environment credentials failed: {e}")
            return False
    
    def _use_service_account_file(self):
        """Try to initialize Firebase using service account file."""
        try:
            cred = credentials.Certificate("mybro-a1ea5-firebase-adminsdk-5a3xf-6089092d21.json")
            firebase_admin.initialize_app(cred)
            return True
        except Exception as e:
            print(f"Service account file failed: {e}")
            return False
    
    # ==================== USER PROFILE OPERATIONS ====================
    
    def get_user_profile(self, email: str) -> UserProfile:
        """Get user profile from Firestore using email as document ID."""
        if self.db:
            try:
                # Get profile data from users collection
                doc_ref = self.db.collection('users').document(email)
                doc = doc_ref.get()
                
                if doc.exists:
                    user_data = doc.to_dict()
                    return UserProfile(
                        name=user_data.get('name')
                    )
            except Exception as e:
                print(f"ERROR: Error getting user profile: {e}")
        
        return UserProfile(
            name="Unknown"
        )
    
    # ==================== CONVERSATION OPERATIONS ====================
    
    def add_chat_pair(self, email: str, user_message: str, model_response: str, 
                      emotion_detected: str = None, urgency_level: int = 1,
                      suggestions: List[str] = None, follow_up_questions: List[str] = None):
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
                "emotion_detected": emotion_detected,  # Use snake_case consistently
                "urgency_level": urgency_level,        # Use snake_case consistently
                "suggestions": suggestions or [],      # Store suggestions from LLM
                "follow_up_questions": follow_up_questions or []  # Store follow-up questions
            }
            
            # Add chat pair to user's conversation subcollection
            self.db.collection('users').document(email).collection('conversations').document(conversation_id).collection('chat').add(chat_pair_data)
            
            # Update conversation metadata
            conv_doc_ref = self.db.collection('users').document(email).collection('conversations').document(conversation_id)
            conv_doc = conv_doc_ref.get()
            
            if conv_doc.exists:
                existing_metadata = conv_doc.to_dict()
                pair_count = existing_metadata.get('MessagePairCount', 0) + 1
                message_count = existing_metadata.get('messageCount', 0) + 2  # Each pair adds 2 messages
            else:
                pair_count = 1
                message_count = 2  # First pair = 2 messages
            
            metadata = {
                "startDate": now.strftime('%Y-%m-%d'),
                "MessagePairCount": pair_count,
                "messageCount": message_count,
                "lastChatAt": firestore.SERVER_TIMESTAMP,
                "lastMessageAt": firestore.SERVER_TIMESTAMP
            }
            
            conv_doc_ref.set(metadata, merge=True)
            print(f"SUCCESS: Added chat pair to {email}'s conversation")
            
        except Exception as e:
            print(f"ERROR: Error adding chat pair: {e}")
    

    
    def get_recent_chat(self, email: str, limit: int = 10) -> List[MessagePair]:
        """Get recent chat pairs from Firestore."""
        if not self.db:
            return []
        
        try:
            today = datetime.now().strftime('%Y%m%d')
            conversation_id = f"conv_{today}"
            
            chat_ref = self.db.collection('users').document(email).collection('conversations').document(conversation_id).collection('chat')
            chat = chat_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
            
            chat_pair_list = []
            for doc in chat:
                pair_data = doc.to_dict()
                # Create MessagePair object from the data (handle both formats for compatibility)
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
            
            # Reverse to get chronological order (oldest first)
            chat_pair_list.reverse()
            return chat_pair_list
            
        except Exception as e:
            print(f"ERROR: Error getting recent chat pairs: {e}")
        
        return []
    
    # ==================== EVENT OPERATIONS ====================
    
    def add_important_event(self, email: str, event: Event):
        """Add an important event to Firestore using subcollection."""
        if not self.db:
            return
        
        try:
            event_data = {
                "eventType": event.eventType,
                "description": event.description,
                "eventDate": event.eventDate,
                "mentionedAt": event.mentionedAt,
                "followUpNeeded": event.followUpNeeded,
                "followUpDone": event.followUpDone
            }
            
            # Generate a unique document ID since we no longer have event_id in the model
            doc_ref = self.db.collection('users').document(email).collection('events').document()
            doc_ref.set(event_data)
            print(f"SUCCESS: Added event for {email}: {event.eventType}")
            
        except Exception as e:
            print(f"ERROR: Error adding event: {e}")
    
    def get_pending_events(self, email: str) -> List[Dict]:
        """Get events that need follow-up for user."""
        if not self.db:
            return []
        
        try:
            events_ref = self.db.collection('users').document(email).collection('events')
            events = events_ref.where(filter=FieldFilter('followUpNeeded', '==', True)).where(filter=FieldFilter('followUpDone', '==', False)).stream()
            
            pending_events = []
            for doc in events:
                event_data = doc.to_dict()
                event_data['event_id'] = doc.id
                pending_events.append(event_data)
            
            return pending_events
            
        except Exception as e:
            print(f"ERROR: Error getting pending events: {e}")
        
        return []
    
    def mark_event_followed_up(self, email: str, event_type: str) -> None:
        """Mark events as followed up after asking about them."""
        if not self.db:
            return
        
        try:
            events_ref = self.db.collection('users').document(email).collection('events')
            events = events_ref.where(filter=FieldFilter('eventType', '==', event_type)).where(filter=FieldFilter('followUpDone', '==', False)).stream()
            
            for doc in events:
                # Mark this event as followed up
                doc.reference.update({'followUpDone': True})
                print(f"SUCCESS: Marked event as followed up: {event_type}")
                break
            
        except Exception as e:
            print(f"ERROR: Error marking event as followed up: {e}")

# Global Firebase manager instance
firebase_manager = FirebaseManager()
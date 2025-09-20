#!/usr/bin/env python3
"""
Firebase Manager for Email-Based User Schema
No sessions, no analytics, no separate tables - just users organized by email
"""

import os
import secrets
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, db
from models import UserProfile, ConversationMessage, ImportantEvent

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class FirebaseManager:
    """Firebase manager with email-based user organization."""
    
    def __init__(self):
        self.db_ref = None
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
            
            self.db_ref = db.reference()
            
        except Exception as e:
            print(f"ERROR: Firebase initialization failed: {e}")
            self.db_ref = None
    
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
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://mybro-a1ea5-default-rtdb.firebaseio.com/'
            })
            return True
            
        except Exception as e:
            print(f"Environment credentials failed: {e}")
            return False
    
    def _use_service_account_file(self):
        """Try to initialize Firebase using service account file."""
        try:
            cred = credentials.Certificate("mybro-a1ea5-firebase-adminsdk-5a3xf-6089092d21.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://mybro-a1ea5-default-rtdb.firebaseio.com/'
            })
            return True
        except Exception as e:
            print(f"Service account file failed: {e}")
            return False
    
    def _email_to_key(self, email: str) -> str:
        """Convert email to Firebase-safe key."""
        return email.replace('.', '_').replace('@', '_at_')
    
    # ==================== USER PROFILE OPERATIONS ====================
    
    def create_user_profile(self, email: str, display_name: str = None) -> UserProfile:
        """Create a new user profile using email as key in profile subfolder."""
        email_key = self._email_to_key(email)
        
        profile_data = {
            "displayName": display_name,
            "createdAt": datetime.now().isoformat(),
            "lastActive": datetime.now().isoformat()
        }
        
        if self.db_ref:
            try:
                self.db_ref.child('users').child(email_key).child('profile').update(profile_data)
                print(f"SUCCESS: Created user profile for {email}")
            except Exception as e:
                print(f"ERROR: Error creating user profile: {e}")
        
        return UserProfile(
            user_id=email,
            name=display_name,
            display_name=display_name or "friend"
        )
    
    def get_user_profile(self, email: str) -> UserProfile:
        """Get user profile from Firebase using email from profile subfolder."""
        email_key = self._email_to_key(email)
        
        if self.db_ref:
            try:
                # Get profile data from subfolder
                user_data = self.db_ref.child('users').child(email_key).child('profile').get()
                if user_data:
                    # Return profile without loading events - events are accessed separately
                    # Only use authorized fields from Firebase profile
                    return UserProfile(
                        user_id=email,
                        name=user_data.get('displayName'),
                        display_name=user_data.get('displayName', 'friend'),
                        age=None,  # Age not stored in profile table
                        mental_health_concerns=[],  # No mental health data in profile
                        support_preferences=[],     # No support preferences in profile
                        important_events=[]         # Events stored separately in events table
                    )
            except Exception as e:
                print(f"ERROR: Error getting user profile: {e}")
        
        return UserProfile(
            user_id=email,
            name="Unknown",
            display_name="friend",
            important_events=[]  # Events stored separately
        )
    
    def update_user_profile(self, email: str, updates: Dict[str, Any]):
        """Update user profile in Firebase using email in profile subfolder."""
        email_key = self._email_to_key(email)
        
        # Define allowed profile fields only
        allowed_fields = {
            'createdAt', 'displayName', 'isActive', 'isVerified', 
            'lastActive', 'lastLoginAt', 'passwordHash'
        }
        
        if self.db_ref:
            try:
                # Only allow authorized fields, reject everything else
                profile_updates = {
                    k: v for k, v in updates.items() 
                    if k in allowed_fields
                }
                
                # Always update lastActive when profile is updated
                profile_updates['lastActive'] = datetime.now().isoformat()
                
                if profile_updates:
                    self.db_ref.child('users').child(email_key).child('profile').update(profile_updates)
                    print(f"SUCCESS: Updated user profile for {email} with fields: {list(profile_updates.keys())}")
                else:
                    print(f"INFO: No authorized fields to update for {email}")
                    
            except Exception as e:
                print(f"ERROR: Error updating user profile: {e}")
    
    # ==================== CONVERSATION OPERATIONS ====================
    
    def add_message(self, email: str, role: str, content: str, 
                   emotion_detected: str = None, urgency_level: int = 1):
        """Add a message to Firebase with simplified email-based schema."""
        if not self.db_ref:
            return
        
        try:
            email_key = self._email_to_key(email)
            now = datetime.now()
            conversation_id = f"conv_{now.strftime('%Y%m%d')}"
            message_id = f"msg_{now.strftime('%H%M%S')}_{secrets.token_hex(4)}"
            
            message_data = {
                "role": role,
                "content": content,
                "timestamp": now.isoformat(),
                "emotionDetected": emotion_detected,
                "urgencyLevel": urgency_level
            }
            
            # Add message to user's conversation
            self.db_ref.child('users').child(email_key).child('conversations').child(conversation_id).child('messages').child(message_id).set(message_data)
            
            # Update conversation metadata
            conv_metadata_ref = self.db_ref.child('users').child(email_key).child('conversations').child(conversation_id).child('metadata')
            existing_metadata = conv_metadata_ref.get() or {}
            
            message_count = existing_metadata.get('messageCount', 0) + 1
            metadata = {
                "startDate": now.strftime('%Y-%m-%d'),
                "messageCount": message_count,
                "lastMessageAt": now.isoformat()
            }
            
            conv_metadata_ref.update(metadata)
            print(f"SUCCESS: Added message to {email}'s conversation")
            
        except Exception as e:
            print(f"ERROR: Error adding message: {e}")
    
    def get_recent_messages(self, email: str, limit: int = 10) -> List[Dict]:
        """Get recent messages from Firebase with simplified schema."""
        if not self.db_ref:
            return []
        
        try:
            email_key = self._email_to_key(email)
            today = datetime.now().strftime('%Y%m%d')
            conversation_id = f"conv_{today}"
            
            messages = self.db_ref.child('users').child(email_key).child('conversations').child(conversation_id).child('messages').order_by_key().limit_to_last(limit).get()
            
            if messages:
                message_list = []
                for msg in messages.values():
                    message_list.append({
                        'role': msg.get('role'),
                        'content': msg.get('content'),
                        'timestamp': msg.get('timestamp'),
                        'emotion_detected': msg.get('emotionDetected'),
                        'urgency_level': msg.get('urgencyLevel', 1)
                    })
                return message_list
            
        except Exception as e:
            print(f"ERROR: Error getting recent messages: {e}")
        
        return []
    
    # ==================== EVENT OPERATIONS ====================
    
    def add_important_event(self, email: str, event: ImportantEvent):
        """Add an important event to Firebase under user's email."""
        if not self.db_ref:
            return
        
        try:
            email_key = self._email_to_key(email)
            event_data = {
                "eventType": event.event_type,
                "description": event.description,
                "eventDate": event.event_date.isoformat() if event.event_date else None,
                "mentionedAt": event.mentioned_date.isoformat(),
                "followUpNeeded": event.follow_up_needed,
                "followUpDone": event.follow_up_done
            }
            
            self.db_ref.child('users').child(email_key).child('events').child(event.event_id).set(event_data)
            print(f"SUCCESS: Added event for {email}: {event.event_type}")
            
        except Exception as e:
            print(f"ERROR: Error adding event: {e}")
    
    def get_pending_events(self, email: str) -> List[Dict]:
        """Get events that need follow-up for user."""
        if not self.db_ref:
            return []
        
        try:
            email_key = self._email_to_key(email)
            events_data = self.db_ref.child('users').child(email_key).child('events').get() or {}
            
            pending_events = []
            for event_id, event_data in events_data.items():
                if event_data.get('followUpNeeded', True) and not event_data.get('followUpDone', False):
                    pending_events.append({
                        'event_id': event_id,
                        **event_data
                    })
            
            return pending_events
            
        except Exception as e:
            print(f"ERROR: Error getting pending events: {e}")
        
        return []
    
    def mark_event_followed_up(self, email: str, event_type: str) -> None:
        """Mark events as followed up after asking about them."""
        if not self.db_ref:
            return
        
        try:
            email_key = self._email_to_key(email)
            events_data = self.db_ref.child('users').child(email_key).child('events').get() or {}
            
            for event_id, event_data in events_data.items():
                if event_data.get('eventType') == event_type and not event_data.get('followUpDone', False):
                    # Mark this event as followed up
                    self.db_ref.child('users').child(email_key).child('events').child(event_id).update({
                        'followUpDone': True
                    })
                    print(f"SUCCESS: Marked event as followed up: {event_type}")
                    break
            
        except Exception as e:
            print(f"ERROR: Error marking event as followed up: {e}")
        
        return []
    
    # ==================== USER DISCOVERY OPERATIONS ====================
    
    def get_all_user_profiles(self) -> Dict[str, UserProfile]:
        """Get all user profiles from Firebase."""
        try:
            users_data = self.db_ref.child('users').get()
            profiles = {}
            
            if users_data:
                for email_key, user_data in users_data.items():
                    if 'profile' in user_data:
                        email = user_data['profile'].get('email')
                        if email:
                            profile = self._dict_to_user_profile(user_data['profile'])
                            profiles[email] = profile
            
            return profiles
            
        except Exception as e:
            print(f"ERROR: Error getting all user profiles: {e}")
            return {}

    # ==================== DAILY SUMMARY OPERATIONS ====================
    
    def get_last_conversation_date(self, email: str) -> Optional[date]:
        """Get the date of user's last conversation."""
        if not self.db_ref:
            return None
        
        try:
            email_key = self._email_to_key(email)
            conversations = self.db_ref.child('users').child(email_key).child('conversations').get()
            
            if conversations:
                # Get the latest conversation date
                conversation_dates = []
                for conv_id in conversations.keys():
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
    
    def daily_summary_exists(self, email: str, date_str: str) -> bool:
        """Check if a daily summary already exists for the given date."""
        if not self.db_ref:
            return False
        
        try:
            email_key = self._email_to_key(email)
            summary = self.db_ref.child('users').child(email_key).child('summaries').child('daily').child(date_str).get()
            return summary is not None
            
        except Exception as e:
            print(f"ERROR: Error checking daily summary existence: {e}")
            return False
    
    def get_conversation_by_date(self, email: str, date_str: str) -> Optional[dict]:
        """Get conversation data for a specific date."""
        if not self.db_ref:
            return None
        
        try:
            email_key = self._email_to_key(email)
            conversation_id = f"conv_{date_str}"
            conversation = self.db_ref.child('users').child(email_key).child('conversations').child(conversation_id).get()
            
            if conversation:
                conversation['date'] = date_str
                return conversation
            
            return None
            
        except Exception as e:
            print(f"ERROR: Error getting conversation by date: {e}")
            return None
    
    def store_daily_summary(self, email: str, date_str: str, summary: dict):
        """Store a daily conversation summary."""
        if not self.db_ref:
            return
        
        try:
            email_key = self._email_to_key(email)
            self.db_ref.child('users').child(email_key).child('summaries').child('daily').child(date_str).set(summary)
            print(f"SUCCESS: Stored daily summary for {email} on {date_str}")
            
        except Exception as e:
            print(f"ERROR: Error storing daily summary: {e}")
    
    def get_daily_summary(self, email: str, date_str: str) -> Optional[dict]:
        """Get daily summary for a specific date."""
        if not self.db_ref:
            return None
        
        try:
            email_key = self._email_to_key(email)
            summary = self.db_ref.child('users').child(email_key).child('summaries').child('daily').child(date_str).get()
            return summary
            
        except Exception as e:
            print(f"ERROR: Error getting daily summary: {e}")
            return None
    
    def find_user_by_name(self, name: str) -> Optional[UserProfile]:
        """Find user profile by name (case insensitive)."""
        try:
            all_profiles = self.get_all_user_profiles()
            name_lower = name.lower()
            
            for profile in all_profiles.values():
                if (profile.name and profile.name.lower() == name_lower) or \
                   (profile.display_name and profile.display_name.lower() == name_lower):
                    return profile
            
            return None
            
        except Exception as e:
            print(f"ERROR: Error finding user by name: {e}")
            return None

# Global Firebase manager instance
firebase_manager = FirebaseManager()
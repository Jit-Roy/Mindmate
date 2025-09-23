
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
from data import UserProfile, MessagePair, Event, UserMessage, LLMMessage, ConversationMemory

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

# Global Firebase manager instance
firebase_manager = FirebaseManager()
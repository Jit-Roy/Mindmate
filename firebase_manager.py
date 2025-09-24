
"""
Firebase Manager for Email-Based User Schema
No sessions, no analytics, no separate tables - just users organized by email
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter
from data import UserProfile

class FirebaseManager:
    """Firebase manager with email-based user organization using Firestore."""
    
    def __init__(self):
        self.db = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase using service account file."""
        try:
            if not firebase_admin._apps:
                if self._use_service_account_file():
                    print("SUCCESS: Firebase initialized with service account file!")
                else:
                    raise Exception("No valid Firebase credentials found")
            
            self.db = firestore.client()
            
        except Exception as e:
            print(f"ERROR: Firebase initialization failed: {e}")
            self.db = None
    
    def _use_service_account_file(self):
        """Try to initialize Firebase using service account file."""
        try:
            cred = credentials.Certificate("skatit-ec470-firebase-adminsdk-fbsvc-2d39f99bb7.json")
            firebase_admin.initialize_app(cred)
            return True
        except Exception as e:
            print(f"Service account file failed: {e}")
            return False
    
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
                        name=user_data.get('name'),
                        username=user_data.get('username'),
                        age=user_data.get('age'),
                        gender=user_data.get('gender'),
                        avatar=user_data.get('avatar')
                    )
            except Exception as e:
                print(f"ERROR: Error getting user profile: {e}")
        
        return UserProfile(
            name="Unknown"
        )

firebase_manager = FirebaseManager()
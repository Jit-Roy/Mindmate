"""
Firebase Manager for Email-Based User Schema
No sessions, no analytics, no separate tables - just users organized by email
"""

import os
import json
import base64
import firebase_admin
import logging
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter
from data import UserProfile

class FirebaseManager:
    """Firebase manager with email-based user organization using Firestore."""
    
    def __init__(self):
        self.db = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase using multiple credential strategies suitable for Azure Functions."""
        try:
            if not firebase_admin._apps:
                if self._use_credentials_from_base64_env():
                    logging.info("Firebase initialized!")
                elif self._use_service_account_file():
                    logging.info("Firebase initialized!")
                else:
                    raise Exception("No valid Firebase credentials found (env/ADC/file)")
            
            self.db = firestore.client()
        except Exception as e:
            logging.error(f"Firebase initialization failed: {e}")
            self.db = None
    
    def _use_credentials_from_json_env(self) -> bool:
        """Initialize using raw JSON from FIREBASE_CREDENTIALS_JSON App Setting."""
        try:
            json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
            if not json_str:
                return False
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, self._optional_project_settings())
            logging.info("Firebase initialized from FIREBASE_CREDENTIALS_JSON")
            return True
        except Exception as e:
            logging.debug(f"JSON env credentials not used: {e}")
            return False

    def _use_credentials_from_base64_env(self) -> bool:
        """Initialize using base64-encoded JSON from FIREBASE_CREDENTIALS_BASE64 App Setting."""
        try:
            b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64")
            if not b64:
                return False
            json_str = base64.b64decode(b64).decode("utf-8")
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, self._optional_project_settings())
            logging.info("Firebase initialized from FIREBASE_CREDENTIALS_BASE64")
            return True
        except Exception as e:
            logging.debug(f"Base64 env credentials not used: {e}")
            return False

    def _use_application_default(self) -> bool:
        """Initialize using Application Default Credentials (e.g., GOOGLE_APPLICATION_CREDENTIALS)."""
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, self._optional_project_settings())
            logging.info("Firebase initialized using Application Default Credentials")
            return True
        except Exception as e:
            logging.debug(f"Application Default Credentials not used: {e}")
            return False

    def _use_service_account_file(self) -> bool:
        """Initialize using a local service account file, resolved relative to this module."""
        try:
            filename = os.environ.get(
                "FIREBASE_CREDENTIALS_FILE",
                "skatit-ec470-firebase-adminsdk-fbsvc-1b6d547ba7.json"
            )
            module_dir = os.path.dirname(os.path.abspath(__file__))
            cred_path = os.path.join(module_dir, filename)
            if not os.path.exists(cred_path):
                logging.warning(f"Service account file not found at {cred_path}")
                return False
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, self._optional_project_settings())
            logging.info(f"Firebase initialized from file: {cred_path}")
            return True
        except Exception as e:
            logging.error(f"Service account file failed: {e}")
            return False

    def _optional_project_settings(self) -> dict:
        """Optionally include project settings to avoid project detection issues."""
        # These are optional, but can stabilize initialization in hosted environments.
        settings = {}
        project_id = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            settings["projectId"] = project_id
        return settings
    
    def get_user_profile(self, email: str) -> UserProfile:
        """Get user profile from Firestore using email as document ID."""
        if not self.db:
            raise RuntimeError("Firebase DB not initialized")
        doc_ref = self.db.collection('users').document(email)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return UserProfile(
                email=email,
                name=data.get('name', 'Friend'),
                timezone=data.get('timezone', 'UTC')
            )
        else:
            # Create a default profile if none exists
            default_profile = UserProfile(email=email, name='Friend', timezone='UTC')
            doc_ref.set({
                'name': default_profile.name,
                'timezone': default_profile.timezone
            })
            return default_profile
    
    def get_all_user_emails(self) -> list:
        """Retrieve all user emails from Firestore."""
        if not self.db:
            raise RuntimeError("Firebase DB not initialized")
        users_ref = self.db.collection('users')
        docs = users_ref.stream()
        return [doc.id for doc in docs]
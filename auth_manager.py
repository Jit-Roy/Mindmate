"""
User Authentication Manager for MyBro AI
Handles email-based authentication and user management
No sessions - simple email/password authentication only
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
from dataclasses import dataclass
from firebase_manager import firebase_manager

@dataclass
class AuthUser:
    """Authenticated user data"""
    user_id: str
    email: str
    display_name: str
    is_verified: bool
    created_at: datetime
    last_login_at: datetime

@dataclass 
class LoginResult:
    """Result of login attempt"""
    success: bool
    user: Optional[AuthUser] = None
    error_message: str = ""

class AuthManager:
    """Manages user authentication"""
    
    def __init__(self):
        self.password_salt = "mybro_ai_secure_salt_2025"
    
    def _email_to_key(self, email: str) -> str:
        """Convert email to Firebase-safe key."""
        return email.replace('.', '_').replace('@', '_at_')
        
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        combined = password + self.password_salt
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_password(self, password: str) -> tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        return True, "Password is valid"
    
    async def register_user(self, email: str, password: str, display_name: str) -> LoginResult:
        """Register a new user"""
        try:
            # Normalize email to lowercase
            email = email.lower().strip()
            
            # Validate input
            if not self._validate_email(email):
                return LoginResult(False, error_message="Invalid email format")
            
            password_valid, password_error = self._validate_password(password)
            if not password_valid:
                return LoginResult(False, error_message=password_error)
            
            if not display_name or len(display_name.strip()) < 2:
                return LoginResult(False, error_message="Display name must be at least 2 characters")
            
            # Check if user already exists using email-based lookup
            email_key = self._email_to_key(email)
            if firebase_manager.db_ref:
                existing_user = firebase_manager.db_ref.child('users').child(email_key).child('profile').get()
                if existing_user:
                    return LoginResult(False, error_message="Email already registered")
            
            # Create new user with email as key
            password_hash = self._hash_password(password)
            now = datetime.now()
            
            # Profile data in subfolder (only essential fields)
            profile_data = {
                "displayName": display_name.strip(),
                "passwordHash": password_hash,
                "isActive": True,
                "isVerified": True,
                "createdAt": now.isoformat(),
                "lastActive": now.isoformat(),
                "lastLoginAt": now.isoformat()
            }
            
            # Store in Firebase using profile subfolder structure
            if firebase_manager.db_ref:
                firebase_manager.db_ref.child('users').child(email_key).child('profile').set(profile_data)
            
            # Create AuthUser object
            auth_user = AuthUser(
                user_id=email.lower(),  # Use email as user_id
                email=email.lower(),
                display_name=display_name.strip(),
                is_verified=True,
                created_at=now,
                last_login_at=now
            )
            
            print(f"✅ User registered successfully: {email}")
            return LoginResult(True, user=auth_user)
            
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return LoginResult(False, error_message="Registration failed. Please try again.")
    
    async def login_user(self, email: str, password: str) -> LoginResult:
        """Login existing user"""
        try:
            # Normalize email to lowercase
            email = email.lower().strip()
            
            if not self._validate_email(email):
                return LoginResult(False, error_message="Invalid email format")
            
            # Find user by email using email-based structure
            if not firebase_manager.db_ref:
                return LoginResult(False, error_message="Database connection failed")
            
            email_key = self._email_to_key(email)
            
            # Get profile data from subfolder
            profile_data = firebase_manager.db_ref.child('users').child(email_key).child('profile').get()
            
            if not profile_data:
                return LoginResult(False, error_message="Email not found")
            
            # Verify password
            password_hash = self._hash_password(password)
            if profile_data.get('passwordHash') != password_hash:
                return LoginResult(False, error_message="Invalid password")
            
            # Check if account is active
            if not profile_data.get('isActive', True):
                return LoginResult(False, error_message="Account is deactivated")
            
            # Update last login
            now = datetime.now()
            firebase_manager.db_ref.child('users').child(email_key).child('profile').child('lastLoginAt').set(now.isoformat())
            
            # Create AuthUser object
            auth_user = AuthUser(
                user_id=email.lower(),  # Use email as user_id
                email=email.lower(),  # Get email from the key, not profile data
                display_name=profile_data['displayName'],
                is_verified=profile_data.get('isVerified', False),
                created_at=datetime.fromisoformat(profile_data['createdAt']),
                last_login_at=now
            )
            
            print(f"✅ User logged in successfully: {email}")
            return LoginResult(True, user=auth_user)
            
        except Exception as e:
            print(f"❌ Login error: {e}")
            return LoginResult(False, error_message="Login failed. Please try again.")
    
    async def get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        """Get user by ID (which is now the email)"""
        try:
            # Normalize email to lowercase
            user_id = user_id.lower().strip()
            
            if not firebase_manager.db_ref:
                return None
            
            # user_id is now the email, so convert to Firebase key
            email_key = self._email_to_key(user_id)
            
            # Get profile data from subfolder
            profile_data = firebase_manager.db_ref.child('users').child(email_key).child('profile').get()
            
            if not profile_data:
                return None
            
            return AuthUser(
                user_id=user_id,  # This is the email
                email=user_id,  # Get email from the key (user_id), not profile data
                display_name=profile_data['displayName'],
                is_verified=profile_data.get('isVerified', False),
                created_at=datetime.fromisoformat(profile_data['createdAt']),
                last_login_at=datetime.fromisoformat(profile_data['lastLoginAt'])
            )
            
        except Exception as e:
            print(f"❌ Get user error: {e}")
            return None

# Global auth manager instance
auth_manager = AuthManager()

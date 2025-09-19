#!/usr/bin/env python3
"""
Notification System for MyBro
Handles proactive check-ins, reminders, and caring notifications
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import time
from dataclasses import dataclass

try:
    # For Windows notifications
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

from memory import MemoryManager
from models import ConversationMessage

@dataclass
class NotificationRule:
    """Defines when and what to notify about"""
    name: str
    trigger_condition: str  # 'time_based', 'mood_based', 'inactivity'
    message_template: str
    priority: int  # 1-5, higher = more urgent
    cooldown_hours: int  # Minimum hours between same type of notifications

class NotificationSystem:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.notification_file = "notifications.json"
        self.is_running = False
        self.notification_thread = None
        
        # Load notification history
        self.notification_history = self._load_notification_history()
        
        # Predefined notification rules
        self.rules = [
            NotificationRule(
                name="daily_checkin",
                trigger_condition="time_based",
                message_template="Hey {name}, how's your day going? I'm here if you need to talk 🤗",
                priority=2,
                cooldown_hours=20
            ),
            NotificationRule(
                name="evening_support",
                trigger_condition="time_based", 
                message_template="Evening thoughts can be tough, {name}. Remember I'm always here for you 🌙",
                priority=2,
                cooldown_hours=22
            ),
            NotificationRule(
                name="concern_followup",
                trigger_condition="mood_based",
                message_template="I've been thinking about our conversation, {name}. You're stronger than you know ❤️",
                priority=4,
                cooldown_hours=6
            ),
            NotificationRule(
                name="inactivity_checkin",
                trigger_condition="inactivity",
                message_template="Haven't heard from you in a while, {name}. Just checking you're okay? 💙",
                priority=3,
                cooldown_hours=48
            ),
            NotificationRule(
                name="encouragement",
                trigger_condition="mood_based",
                message_template="Remember {name}, tough times don't last but tough people do. You've got this! 💪",
                priority=1,
                cooldown_hours=12
            )
        ]

    def _load_notification_history(self) -> Dict:
        """Load notification history from file"""
        try:
            if os.path.exists(self.notification_file):
                with open(self.notification_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            pass
        return {}

    def _save_notification_history(self):
        """Save notification history to file"""
        try:
            with open(self.notification_file, 'w') as f:
                json.dump(self.notification_history, f, indent=2)
        except Exception as e:
            pass

    def _can_send_notification(self, rule_name: str, user_id: str) -> bool:
        """Check if enough time has passed since last notification of this type"""
        history_key = f"{user_id}_{rule_name}"
        if history_key not in self.notification_history:
            return True
        
        last_sent = datetime.fromisoformat(self.notification_history[history_key])
        rule = next((r for r in self.rules if r.name == rule_name), None)
        if not rule:
            return False
            
        cooldown_period = timedelta(hours=rule.cooldown_hours)
        return datetime.now() - last_sent > cooldown_period

    def _record_notification(self, rule_name: str, user_id: str):
        """Record that a notification was sent"""
        history_key = f"{user_id}_{rule_name}"
        self.notification_history[history_key] = datetime.now().isoformat()
        self._save_notification_history()

    def send_system_notification(self, title: str, message: str, icon_path: str = None):
        """Send system notification (Windows/Mac/Linux)"""
        if not NOTIFICATIONS_AVAILABLE:
            return

        try:
            notification.notify(
                title=title,
                message=message,
                app_name="MyBro",
                timeout=10,
                toast=True
            )
        except Exception as e:
            pass

    def _get_user_context(self, user_id: str) -> Dict:
        """Get user context for personalized notifications"""
        profile = self.memory.get_user_profile(user_id)
        recent_messages = self.memory.get_recent_messages(user_id, 5)
        
        context = {
            'name': profile.name if profile else 'friend',
            'last_emotion': None,
            'last_urgency': 1,
            'days_since_last_chat': 0,
            'concerning_topics': []
        }
        
        if recent_messages:
            # Get last user message emotion and urgency
            last_user_msg = next((msg for msg in reversed(recent_messages) if msg.role == 'user'), None)
            if last_user_msg:
                context['last_emotion'] = last_user_msg.emotion_detected
                context['last_urgency'] = last_user_msg.urgency_level or 1
                
                # Calculate days since last chat
                if isinstance(last_user_msg.timestamp, str):
                    last_time = datetime.fromisoformat(last_user_msg.timestamp)
                else:
                    last_time = last_user_msg.timestamp
                context['days_since_last_chat'] = (datetime.now() - last_time).days
                
                # Check for concerning topics
                concerning_keywords = ['suicide', 'kill myself', 'end my life', 'hopeless', 'worthless']
                if any(keyword in last_user_msg.content.lower() for keyword in concerning_keywords):
                    context['concerning_topics'].append('self_harm')
        
        return context

    def _should_trigger_notification(self, rule: NotificationRule, context: Dict) -> bool:
        """Determine if a notification should be triggered based on rule and context"""
        now = datetime.now()
        
        if rule.trigger_condition == "time_based":
            if rule.name == "daily_checkin":
                # Send between 10 AM and 2 PM
                return 10 <= now.hour <= 14
            elif rule.name == "evening_support":
                # Send between 7 PM and 10 PM
                return 19 <= now.hour <= 22
                
        elif rule.trigger_condition == "mood_based":
            if rule.name == "concern_followup":
                # Trigger if last conversation had high urgency or concerning topics
                return (context['last_urgency'] >= 4 or 
                        'self_harm' in context['concerning_topics'])
            elif rule.name == "encouragement":
                # Trigger for moderate emotional distress
                return (context['last_emotion'] in ['anxious', 'depressed', 'overwhelmed'] and
                        context['last_urgency'] >= 2)
                        
        elif rule.trigger_condition == "inactivity":
            # Trigger if user hasn't chatted in 2+ days
            return context['days_since_last_chat'] >= 2
            
        return False

    def check_and_send_notifications(self, user_id: str):
        """Check all rules and send appropriate notifications"""
        if not self.memory.get_user_profile(user_id):
            return  # No user profile exists
            
        context = self._get_user_context(user_id)
        
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if (self._can_send_notification(rule.name, user_id) and 
                self._should_trigger_notification(rule, context)):
                
                # Format message with user context
                message = rule.message_template.format(**context)
                
                # Send notification
                self.send_system_notification(
                    title="MyBro is thinking of you",
                    message=message
                )
                
                # Record notification
                self._record_notification(rule.name, user_id)
                
                # Only send one notification per check (highest priority)
                break

    def start_background_monitoring(self, user_id: str, check_interval_minutes: int = 30):
        """Start background thread for monitoring and notifications"""
        if self.is_running:
            return
            
        self.is_running = True
        
        def monitoring_loop():
            while self.is_running:
                try:
                    self.check_and_send_notifications(user_id)
                    time.sleep(check_interval_minutes * 60)  # Convert to seconds
                except Exception as e:
                    pass
                    time.sleep(60)  # Wait 1 minute before retrying
        
        self.notification_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.notification_thread.start()
        pass

    def stop_background_monitoring(self):
        """Stop background monitoring"""
        self.is_running = False
        if self.notification_thread:
            self.notification_thread.join(timeout=1)
        pass

    def send_immediate_notification(self, user_id: str, message: str, title: str = "MyBro"):
        """Send an immediate notification without rule checking"""
        context = self._get_user_context(user_id)
        formatted_message = message.format(**context)
        
        self.send_system_notification(title, formatted_message)
        pass

    def get_suggested_checkin_message(self, user_id: str) -> str:
        """Get a personalized check-in message based on user's recent state"""
        context = self._get_user_context(user_id)
        
        if context['days_since_last_chat'] >= 3:
            return f"Hey {context['name']}, haven't heard from you in a few days. Hope you're doing okay? 💙"
        elif context['last_urgency'] >= 4:
            return f"{context['name']}, I've been thinking about our last conversation. How are you feeling now? ❤️"
        elif context['last_emotion'] == 'anxious':
            return f"Hey {context['name']}, how's your anxiety today? Remember, you're stronger than your worries 💪"
        elif context['last_emotion'] == 'depressed':
            return f"{context['name']}, thinking of you today. Small steps are still progress 🌱"
        else:
            return f"Hey {context['name']}, how's your day treating you? I'm here if you need me 🤗"

# Utility functions for integration with main app

def setup_notifications(memory_manager: MemoryManager, user_id: str) -> NotificationSystem:
    """Set up notification system for a user"""
    notif_system = NotificationSystem(memory_manager)
    
    # Start background monitoring with 30-minute checks
    notif_system.start_background_monitoring(user_id, check_interval_minutes=30)
    
    return notif_system

def send_exit_notification(memory_manager: MemoryManager, user_id: str):
    """Send a caring notification when user exits the app"""
    notif_system = NotificationSystem(memory_manager)
    context = notif_system._get_user_context(user_id)
    
    exit_messages = [
        "Take care of yourself, {name}. I'm always here when you need me ❤️",
        "Remember {name}, you're not alone. I'll be here waiting for you 🤗",
        "Keep your head up, {name}. Tomorrow is a new day with new possibilities 🌅",
        "You're stronger than you think, {name}. Rest well and know I care about you 💙"
    ]
    
    # Choose message based on user's recent emotional state
    if context['last_urgency'] >= 3:
        message = "Take care of yourself, {name}. I'm always here when you need me ❤️"
    else:
        import random
        message = random.choice(exit_messages)
    
    notif_system.send_immediate_notification(
        user_id, 
        message, 
        "MyBro cares about you"
    )

"""
Event Management Module
Handles detection, storage, and follow-up of important events in conversations
"""

import json
from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from data import Event
from config import config
from firebase_manager import firebase_manager
from summary import summary_manager


class EventManager:
    """Manages event detection, storage, and proactive follow-ups."""
    
    def __init__(self):
        """Initialize the EventManager with LLM for event detection."""
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.gemini_api_key,
            temperature=0.3 
        )
    
    def detect_important_events(self, message: str, email: str) -> None:
        """Detect and store important upcoming events from user messages using LLM."""
        
        # Use LLM to detect events and timing
        event_detection = self._extract_events_with_llm(message)
        
        if event_detection and event_detection.get('has_event'):

            event_date = self._parse_event_timing(event_detection.get('timing', ''), message)
            
            # Create and store the event
            event = Event(
                eventType=event_detection.get('event_type', 'event'),
                description=message,
                eventDate=event_date.isoformat() if event_date else None,
                followUpNeeded=True,
                followUpDone=False
            )
            
            # Store event directly in Firebase events table
            firebase_manager.add_important_event(email, event)

    def _extract_events_with_llm(self, message: str) -> Optional[dict]:
        """Use LLM to extract important events and timing from user messages."""
        system_prompt = """You are an expert at detecting important upcoming events or recent events that someone might want follow-up on. Analyze the user's message and determine:

        1. If there's an important event mentioned (exam, interview, appointment, date, presentation, meeting, deadline, party, etc.)
        2. The type of event (be specific but use common categories)
        3. The timing context (when it's happening or happened)

        IMPORTANT: Only detect events that are:
        - Significant enough that a caring friend would follow up about
        - Have clear timing indicators (today, tomorrow, next week, yesterday, etc.)
        - Are specific events, not general activities

        Return your analysis in this EXACT JSON format:
        {
            "has_event": true/false,
            "event_type": "exam" or "interview" or "appointment" or "date" or "presentation" or "meeting" or "deadline" or "party" or "other",
            "timing": "today" or "tomorrow" or "yesterday" or "next week" or "this weekend" or "next month" or "specific timing phrase",
            "confidence": 0.0-1.0
        }

        Only return has_event: true if you're confident (>0.7) there's a real important event with timing."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analyze this message for important events: '{message}'")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON response
            try:
                # Extract JSON from response if it's wrapped in text
                if '{' in response_text and '}' in response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                    event_data = json.loads(json_str)
                    
                    # Validate the response structure
                    if isinstance(event_data, dict) and 'has_event' in event_data:
                        confidence = event_data.get('confidence', 0.0)
                        if event_data.get('has_event') and confidence >= 0.7:
                            return event_data
                        
            except json.JSONDecodeError:
                pass
                
            return None
            
        except Exception as e:
            return None

    def _parse_event_timing(self, timing: str, original_message: str) -> Optional[date]:
        """Parse timing information to determine event date."""
        today = date.today()
        timing_lower = timing.lower()
        message_lower = original_message.lower()
        
        # LLM-provided timing
        if 'tomorrow' in timing_lower:
            return today + timedelta(days=1)
        elif 'today' in timing_lower or 'tonight' in timing_lower:
            return today
        elif 'yesterday' in timing_lower:
            return today - timedelta(days=1)
        elif 'next week' in timing_lower:
            return today + timedelta(days=7)
        elif 'this weekend' in timing_lower:
            return today + timedelta(days=(5 - today.weekday()) if today.weekday() < 5 else 1)
        elif 'next month' in timing_lower:
            return today + timedelta(days=30)
        
        # Fallback to original message analysis for specific days
        days_of_week = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_num in days_of_week.items():
            if f'next {day_name}' in message_lower:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)
        
        return None

    def generate_proactive_greeting(self, email: str) -> Optional[str]:
        """Generate a personalized proactive greeting using LLM for important events."""
        user_profile = firebase_manager.get_user_profile(email)
        name = user_profile.name or "friend"
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # STEP 1: Check if we need to generate yesterday's summary (first chat of new day)
        summary_manager.generate_conversation_summary(email)
        
        # STEP 2: Get pending events from Firebase events table
        pending_events = firebase_manager.get_pending_events(email)
        
        for event_data in pending_events:
            # Convert event_data to proper format for checking
            event_date_str = event_data.get('eventDate')
            if isinstance(event_date_str, str) and event_date_str:
                event_date = datetime.fromisoformat(event_date_str).date()
            else:
                event_date = None
            
            # Determine the timing context
            timing_context = ""
            if event_date == today:
                timing_context = "today"
            elif event_date == yesterday:
                timing_context = "yesterday"
            elif event_date and event_date > today and (event_date - today).days <= 2:
                days_until = (event_date - today).days
                timing_context = f"in {days_until} day{'s' if days_until > 1 else ''}"
            else:
                continue  # Skip events outside our follow-up window
            
            # Create temporary event object for greeting generation
            event = Event(
                eventType=event_data['eventType'],
                description=event_data['description'],
                eventDate=event_date.isoformat() if event_date else None,
                mentionedAt=event_data.get('mentionedAt', ''),
                followUpNeeded=event_data.get('followUpNeeded', True),
                followUpDone=event_data.get('followUpDone', False)
            )
            
            # Generate personalized greeting using LLM
            return self._generate_event_greeting_with_llm(event, name, timing_context)
        
        return None

    def _generate_event_greeting_with_llm(self, event: Event, name: str, timing_context: str) -> str:
        """Generate a personalized event greeting using LLM."""
        system_prompt = f"""You are MyBro, a caring friend who remembers important events in people's lives. Generate a warm, personalized greeting that asks about an important event. 

        GUIDELINES:
        - Be genuinely caring and show you remember the event
        - Use natural, friendly language like you're texting a close friend
        - Show appropriate emotion (excitement, concern, encouragement) for the event type
        - Keep it conversational and warm, not formal
        - Reference the timing naturally
        - Make it feel personal and thoughtful

        EVENT CONTEXT:
        - Person's name: {name}
        - Event type: {event.eventType}
        - Timing: {timing_context}
        - Event description: {event.description if hasattr(event, 'description') else 'Not available'}

        TIMING MEANINGS:
        - "today": Event happened today, ask how it went
        - "yesterday": Event happened yesterday, follow up on how it went
        - "in X days": Event is upcoming, check how they're feeling about it

        Generate ONE natural, caring greeting message that shows you remember and care about their event."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate a caring greeting for {name} about their {event.eventType} that happened/happens {timing_context}")
            ]
            
            response = self.llm.invoke(messages)
            greeting = response.content.strip()
            
            # Remove any quotes that might wrap the response
            if greeting.startswith('"') and greeting.endswith('"'):
                greeting = greeting[1:-1]
            
            return greeting
            
        except Exception as e:
            # Simple fallback if LLM fails
            if timing_context in ["today", "yesterday"]:
                return f"Hey {name}! How did your {event.eventType} go {timing_context}?"
            else:
                return f"Hey {name}! How are you feeling about your upcoming {event.eventType}?"

    def mark_event_followed_up(self, email: str, event_type: str) -> None:
        """Mark events as followed up after asking about them."""
        firebase_manager.mark_event_followed_up(email, event_type)

event_manager = EventManager()
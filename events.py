"""
Event Management Module
Handles detection, storage, and follow-up of important events in conversations
"""

import json
from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from firebase_admin import firestore
from google.cloud.firestore import FieldFilter
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
        self.db = firebase_manager.db 
    
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
    
    def get_pending_events(self, email: str) -> List[Event]:
        """Get events that need follow-up for user."""
        if not self.db:
            return []
        
        try:
            events_ref = self.db.collection('users').document(email).collection('events')
            events = events_ref.where(filter=FieldFilter('followUpNeeded', '==', True)).where(filter=FieldFilter('followUpDone', '==', False)).stream()
            
            pending_events = []
            for doc in events:
                event_data = doc.to_dict()
                
                try:
                    event = Event(
                        eventid=doc.id, 
                        eventType=event_data.get('eventType', ''),
                        description=event_data.get('description', ''),
                        eventDate=event_data.get('eventDate'),
                        mentionedAt=event_data.get('mentionedAt', ''),
                        followUpNeeded=event_data.get('followUpNeeded', True),
                        followUpDone=event_data.get('followUpDone', False)
                    )
                    pending_events.append(event)
                except Exception as parse_error:
                    print(f"Warning: Could not parse event {doc.id}: {parse_error}")
                    continue
            
            return pending_events
            
        except Exception as e:
            print(f"ERROR: Error getting pending events: {e}")
        
        return []
    
    def detect_important_events(self, message: str, email: str) -> None:
        """Detect and store important upcoming events from user messages using LLM."""
        
        event = self._extract_events_with_llm(message)
        
        if event:
            self.add_important_event(email, event)

    def _extract_events_with_llm(self, message: str) -> Optional[Event]:
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
            
            try:
                if '{' in response_text and '}' in response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                    event_data = json.loads(json_str)
                    
                    if isinstance(event_data, dict) and 'has_event' in event_data:
                        confidence = event_data.get('confidence', 0.0)
                        if event_data.get('has_event') and confidence >= 0.7:
                            event_date = self._parse_event_timing(event_data.get('timing', ''), message)
                    
                            return Event(
                                eventid="",
                                eventType=event_data.get('event_type', 'event'),
                                description=message,
                                eventDate=event_date.isoformat() if event_date else None,
                                followUpNeeded=True,
                                followUpDone=False
                            )
                        
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
        name = user_profile.name 
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        pending_events = self.get_pending_events(email)
        
        for event in pending_events:
            event_date = None
            if event.eventDate and isinstance(event.eventDate, str):
                try:
                    event_date = datetime.fromisoformat(event.eventDate).date()
                except ValueError:
                    continue
            
            timing_context = ""
            if event_date == today:
                timing_context = "today"
            elif event_date == yesterday:
                timing_context = "yesterday"
            elif event_date and event_date > today and (event_date - today).days <= 2:
                days_until = (event_date - today).days
                timing_context = f"in {days_until} day{'s' if days_until > 1 else ''}"
            else:
                continue  
            
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

            if greeting.startswith('"') and greeting.endswith('"'):
                greeting = greeting[1:-1]
            
            return greeting
            
        except Exception as e:
            pass

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

event_manager = EventManager()
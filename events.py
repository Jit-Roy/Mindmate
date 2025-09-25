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
import hashlib
from datetime import datetime


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
    
    def add_event(self, email: str, event: Event):
        """Add an event to Firestore using subcollection."""
        if not self.db:
            return
        
        try:
            event_data = event.model_dump()
            doc_ref = self.db.collection('users').document(email).collection('events').document(event.eventid)
            doc_ref.set(event_data)
            
        except Exception as e:
            print(f"ERROR: Error adding event: {e}")
    
    def get_events(self, email: str) -> List[Event]:
        """Get all events for user."""
        if not self.db:
            return []
        
        try:
            events = self.db.collection('users').document(email).collection('events').stream()
            
            all_events = []
            for doc in events:
                event_data = doc.to_dict()
                
                try:
                    event = Event(
                        eventid=doc.id, 
                        eventType=event_data.get('eventType', ''),
                        description=event_data.get('description', ''),
                        eventDate=event_data.get('eventDate'),
                        mentionedAt=event_data.get('mentionedAt', ''),
                        isCompleted=event_data.get('isCompleted', False)
                    )
                    all_events.append(event)
                except Exception as parse_error:
                    print(f"Warning: Could not parse event {doc.id}: {parse_error}")
                    continue
            
            return all_events
            
        except Exception as e:
            print(f"ERROR: Error getting events: {e}")
        
        return []

    def _extract_events_with_llm(self, message: str, email: str) -> Optional[Event]:
        """Use LLM to extract events and timing from user messages."""
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        next_week = today + timedelta(days=7)
        
        system_prompt = f"""You are an expert at detecting important upcoming events or recent events that someone might want follow-up on. Analyze the user's message and determine:

        1. If there's an important event mentioned (exam, interview, appointment, date, presentation, meeting, deadline, party, etc.)
        2. The type of event (be specific but use common categories)
        3. The timing context (when it's happening or happened)

        IMPORTANT: Only detect events that are:
        - Significant enough that a caring friend would follow up about
        - Have clear timing indicators (today, tomorrow, next week, yesterday, etc.)
        - Are specific events, not general activities

        TODAY'S DATE: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})

        Return your analysis in this EXACT JSON format:
        {{
            "has_event": true/false,
            "event_type": "exam" or "interview" or "appointment" or "date" or "presentation" or "meeting" or "deadline" or "party" or "other",
            "event_date": "YYYY-MM-DD" (calculate the actual date based on timing context),
            "confidence": 0.0-1.0
        }}

        Only return has_event: true if you're confident (>0.7) there's a real important event with timing.
        
        For event_date calculation, use today's date as {today.strftime('%Y-%m-%d')} and calculate:
        - "today" → {today.strftime('%Y-%m-%d')}
        - "tomorrow" → {tomorrow.strftime('%Y-%m-%d')}
        - "yesterday" → {yesterday.strftime('%Y-%m-%d')}
        - "next week" → {next_week.strftime('%Y-%m-%d')} (7 days from today)
        - "this weekend" → calculate Saturday/Sunday of this week
        - "next Monday/Tuesday/etc" → calculate the next occurrence of that day
        - Specific dates mentioned in the message should be converted to YYYY-MM-DD format"""

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
                            event_date_str = event_data.get('event_date') 
                            event_type = event_data.get('event_type', 'event')
                            base_components = [
                                event_type.lower().replace(' ', '_'),
                                email.split('@')[0],  
                                event_date_str
                            ]
                            description_hash = hashlib.md5(message.encode()).hexdigest()[:6]
                            event_id = f"{base_components[0]}_{base_components[1]}_{base_components[2]}_{description_hash}"
                    
                            return Event(
                                eventid=event_id,
                                eventType=event_type,
                                description=message,
                                eventDate=event_date_str,
                                isCompleted=False
                            )
                        
            except json.JSONDecodeError:
                pass
                
            return None
            
        except Exception as e:
            return None

    def _generate_event_greeting(self, events: List[Event], email: str) -> str:
        """Generate a personalized event greeting using LLM for multiple events."""
        user_profile = firebase_manager.get_user_profile(email)
        name = user_profile.name
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        
        # Build event context for all events
        events_context = []
        event_details = []
        for event in events:
            events_context.append(f"- {event.eventType} on {event.eventDate}: {event.description}")
            event_details.append(f"{event.eventType} on {event.eventDate}")
        
        events_text = "\n".join(events_context)
        events_summary = ", ".join(event_details)
        
        system_prompt = f"""You are MyBro, a caring friend who remembers important events in people's lives. Generate a warm, personalized greeting that asks about multiple important events. 

        GUIDELINES:
        - Be genuinely caring and show you remember all the events
        - Use natural, friendly language like you're texting a close friend
        - Show appropriate emotion (excitement, concern, encouragement) for the event types
        - Keep it conversational and warm, not formal
        - Reference the timing naturally based on the date comparisons
        - Make it feel personal and thoughtful
        - If there are multiple events, weave them together naturally or focus on the most relevant one

        EVENT CONTEXT:
        - Person's name: {name}
        - Today's date: {today_str}
        - Events to follow up on: {events_text}

        Generate ONE natural, caring greeting message that shows you remember and care about their events."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Generate a caring greeting for {name} about their events: {events_summary}. Today is {today_str}. Compare the dates and generate appropriate timing language.")
            ]
            
            response = self.llm.invoke(messages)
            greeting = response.content.strip()

            if greeting.startswith('"') and greeting.endswith('"'):
                greeting = greeting[1:-1]
            
            return greeting
            
        except Exception as e:
            pass

    def delete_events(self, events: List[Event], email: str) -> None:
        """Delete events from the database."""
        if not self.db:
            return
        
        today = date.today()
        
        for event in events:
            try:
                event_date = datetime.strptime(event.eventDate, '%Y-%m-%d').date()
                
                if event_date < today:
                    event_ref = self.db.collection('users').document(email).collection('events').document(event.eventid)
                    event_ref.delete()  
                    
            except Exception as e:
                print(f"ERROR: Error processing event {event.eventid}: {e}")

event_manager = EventManager()
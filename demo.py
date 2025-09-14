#!/usr/bin/env python3
"""
Demo script for the Mental Health Chatbot
This script demonstrates the key features without requiring API keys.
"""

import asyncio
from datetime import datetime
from memory_manager import MemoryManager
from mental_health_filter import MentalHealthFilter
from models import ChatResponse

def demo_memory_system():
    """Demonstrate the memory management system."""
    print("🧠 MEMORY SYSTEM DEMO")
    print("=" * 50)
    print("⚠️  Note: This demo uses fake data, not real API responses")
    
    # Create temporary memory manager that doesn't save to files
    from memory_manager import MemoryManager
    memory = MemoryManager()
    
    # Override save methods to prevent file creation during demo
    memory.save_memory = lambda: None
    memory.save_profiles = lambda: None
    
    user_id = "demo_user"
    
    # Create user profile
    profile = memory.create_user_profile(user_id, "Alex")
    print(f"✅ Created user profile: {profile.name} (ID: {profile.user_id})")
    
    # Add some conversation messages
    memory.add_message(user_id, "user", "I've been feeling really anxious lately", "anxious", 3)
    memory.add_message(user_id, "assistant", "I understand you're feeling anxious. Let's talk about what's causing this.")
    memory.add_message(user_id, "user", "Work has been really stressful", "stressed", 2)
    memory.add_message(user_id, "assistant", "Work stress is very common. What specifically is bothering you about work?")
    
    print(f"✅ Added conversation messages")
    
    # Get conversation context
    context = memory.get_conversation_context(user_id)
    print(f"📝 Conversation context:\n{context}")
    
    # Get recent messages
    recent = memory.get_recent_messages(user_id, 3)
    print(f"\n📊 Recent messages: {len(recent)} messages")
    for msg in recent:
        print(f"   {msg.role}: {msg.content[:50]}...")

def demo_topic_filtering():
    """Demonstrate the mental health topic filtering."""
    print("\n🔍 TOPIC FILTERING DEMO")
    print("=" * 50)
    
    filter_obj = MentalHealthFilter()
    
    test_messages = [
        ("I'm feeling really depressed today", True),
        ("My anxiety is getting worse", True),
        ("Write me a Python function", False),
        ("I'm stressed about my relationship", True),
        ("What's the weather like?", False),
        ("I can't sleep and feel overwhelmed", True)
    ]
    
    print("Testing message classification:")
    for message, expected in test_messages:
        try:
            result = filter_obj.is_mental_health_related(message)
            status = "✅" if result.is_mental_health_related == expected else "❌"
            print(f"{status} '{message[:40]}...' -> {'Mental Health' if result.is_mental_health_related else 'Non-Mental Health'}")
        except Exception as e:
            print(f"⚠️  '{message[:40]}...' -> Error: {str(e)[:50]}")

def demo_emotion_detection():
    """Demonstrate emotion detection."""
    print("\n😊 EMOTION DETECTION DEMO")
    print("=" * 50)
    
    from mental_health_filter import EmotionDetector
    detector = EmotionDetector()
    
    test_messages = [
        "I'm feeling really anxious about my presentation tomorrow",
        "I'm so happy about my promotion!",
        "I feel completely hopeless and don't know what to do",
        "I'm angry that my boss doesn't appreciate my work",
        "I feel lonely since my friends moved away"
    ]
    
    print("Detecting emotions and urgency levels:")
    for message in test_messages:
        emotion, urgency = detector.detect_emotion(message)
        urgency_bar = "🔴" * urgency + "⚪" * (5 - urgency)
        print(f"😊 {emotion:<10} | {urgency_bar} | '{message[:40]}...'")

def demo_chat_response_format():
    """Demonstrate chat response format."""
    print("\n💬 CHAT RESPONSE FORMAT DEMO")
    print("=" * 50)
    
    # Create a sample response
    response = ChatResponse(
        message="I hear that you're feeling anxious, and that's completely understandable. Anxiety can be really overwhelming, but you're not alone in this. Can you tell me more about what's been triggering these feelings?",
        emotion_tone="anxious",
        suggestions=[
            "Try the 4-7-8 breathing technique",
            "Practice grounding with 5-4-3-2-1 technique",
            "Take a short walk outside"
        ],
        follow_up_questions=[
            "What specific situations make you feel most anxious?",
            "Have you noticed any physical symptoms with your anxiety?"
        ],
        urgency_detected=False,
        professional_help_suggested=False
    )
    
    print(f"🤖 Bot Response:")
    print(f"   Message: {response.message[:100]}...")
    print(f"   Emotion: {response.emotion_tone}")
    print(f"   Urgency: {'Yes' if response.urgency_detected else 'No'}")
    print(f"   Suggestions: {len(response.suggestions)} provided")
    print(f"   Follow-ups: {len(response.follow_up_questions)} questions")

def demo_configuration():
    """Demonstrate configuration system."""
    print("\n⚙️  CONFIGURATION DEMO")
    print("=" * 50)
    
    from config import config
    
    print(f"🔧 Model: {config.model_name}")
    print(f"🌡️  Temperature: {config.temperature}")
    print(f"📏 Max tokens: {config.max_tokens}")
    print(f"💾 Memory settings: {config.max_conversation_history} messages, summarize at {config.summary_trigger_length}")
    print(f"🔑 Mental health keywords: {len(config.mental_health_keywords)} keywords")
    print(f"   Sample keywords: {', '.join(config.mental_health_keywords[:10])}")

def main():
    """Run all demos."""
    print("🤗 MENTAL HEALTH CHATBOT DEMO")
    print("=" * 60)
    print("This demo shows the key features of the chatbot system")
    print("WITHOUT using real API calls or creating persistent data.")
    print("All responses shown are examples, not real AI responses.")
    print("=" * 60)
    
    try:
        demo_memory_system()
        demo_topic_filtering()
        demo_emotion_detection()
        demo_chat_response_format()
        demo_configuration()
        
        print("\n🎉 DEMO COMPLETE!")
        print("=" * 60)
        print("✅ All core systems are working correctly!")
        print("\n📋 To run the full chatbot:")
        print("1. Get a Gemini API key from: https://makersuite.google.com/app/apikey")
        print("2. Add it to your .env file")
        print("3. Run: python main.py")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        print("Please check your installation and try again.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Setup script for the Mental Health Chatbot
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """Set up the environment for the mental health chatbot."""
    
    print("🔧 Setting up Mental Health Chatbot environment...")
    
    # Check if .env file exists
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📝 Creating .env file from template...")
        with open(env_example, 'r') as f:
            content = f.read()
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("✅ .env file created!")
        print("⚠️  Please edit the .env file and add your Gemini API key")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        return False
    
    elif not env_file.exists():
        print("❌ No .env file found and no .env.example template!")
        return False
    
    # Check if API key is configured
    from config import config
    
    if not config.gemini_api_key or config.gemini_api_key == "your_gemini_api_key_here":
        print("❌ Gemini API key not configured!")
        print("   Please edit the .env file and add your Gemini API key")
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        return False
    
    print("✅ Environment setup complete!")
    return True

def test_installation():
    """Test if all required packages are installed."""
    
    print("🧪 Testing package installation...")
    
    try:
        import google.generativeai as genai
        import langchain
        import pydantic
        import rich
        from langchain_google_genai import ChatGoogleGenerativeAI
        print("✅ All packages installed correctly!")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("   Run: pip install -r requirements.txt")
        return False

def main():
    """Main setup function."""
    
    print("🤗 Mental Health Chatbot Setup")
    print("=" * 50)
    
    # Test installation
    if not test_installation():
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        print("\n📋 Next steps:")
        print("1. Edit the .env file and add your Gemini API key")
        print("2. Run: python setup.py")
        print("3. Run: python main.py")
        sys.exit(1)
    
    print("\n🎉 Setup complete!")
    print("\n🚀 Ready to run the chatbot!")
    print("   Run: python main.py")
    
    # Ask if user wants to run the chatbot now
    response = input("\nWould you like to start the chatbot now? (y/n): ").strip().lower()
    if response == 'y':
        print("\n🤗 Starting Mental Health Chatbot...")
        os.system("python main.py")

if __name__ == "__main__":
    main()

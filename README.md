# MyBro - An AI To Help You Get Rid Of Depression

A compassionate AI chatbot designed to provide mental health support with genuine human-like responses. Built with Python, LangChain, and Google's Gemini API.

## 🎯 **What Makes MyBro Different?**

Unlike clinical chatbots that just ask questions, MyBro responds like a **caring older brother** who:
- **Fights for you** when you're feeling down
- **Challenges negative thoughts** with passion and protection
- **Gives you reasons to live** instead of just listening passively
- **Shows real emotion** and urgency about your wellbeing
- **Protects you from your own dark thoughts**

## ✨ **Key Features**

- **Mental Health Focused**: Only responds to mental health and emotional well-being topics
- **Human-like Support**: Acts like a protective friend, not a clinical therapist
- **Smart Conversation Memory**: Remembers past conversations and personalizes responses
- **Advanced Emotion Detection**: Identifies emotions and urgency levels accurately
- **Proactive Daily Check-ins**: Reaches out to check on your mental health
- **Intelligent Crisis Detection**: Recognizes serious situations while avoiding over-medicalization
- **Personalized Coping Strategies**: Offers support based on detected emotions
- **Persistent Memory**: Maintains conversation history and user profiles across sessions

## 🚀 **Installation & Setup**

### **1. Clone the Repository**
```bash
git clone https://github.com/Jit-Roy/MyBro.git
cd MyBro
```

### **2. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **3. Configure Environment**
```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:
```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### **4. Get Gemini API Key**
- Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- Create a new API key
- Copy it to your `.env` file

### **5. Run MyBro**
```bash
python main.py
```

## 🧠 **How MyBro Works**

### **1. Human-like Conversation Engine**
- Uses advanced system prompts to respond like a caring friend
- Challenges negative thoughts with passion and protection
- Focuses on reasons to live rather than clinical questioning

### **2. Smart Crisis Detection**
```python
# Only triggers crisis response for immediate danger
Urgency Level 5: "I'm planning to kill myself tonight" 
Urgency Level 3: "I want to die" (gets supportive conversation)
Urgency Level 1: "I feel sad" (gets normal conversation)
```

### **3. Conversation Memory**
- Remembers your name, concerns, and conversation history
- Automatically summarizes long conversations
- Personalizes responses based on past interactions

### **4. Emotion Recognition**
- Detects emotions: anxious, depressed, angry, lonely, etc.
- Assigns urgency levels (1-5) based on content severity
- Provides emotion-specific coping strategies

## 📋 **Technical Features**

### **Built With**
- **LangChain**: Advanced LLM orchestration and conversation management
- **Google Gemini**: State-of-the-art language model for human-like responses
- **Pydantic**: Type-safe data validation and serialization
- **Rich**: Beautiful terminal interface with panels and colors
- **Python asyncio**: Asynchronous processing for smooth interactions

## 🤝 **Contributing**

We welcome contributions! Areas for improvement:

- **Enhanced Emotion Detection**: More nuanced emotional understanding
- **Additional Coping Strategies**: Expanded support techniques
- **Multi-language Support**: Conversations in multiple languages
- **Voice Interface**: Speech-to-text and text-to-speech capabilities
- **Mobile App**: React Native or Flutter implementation
- **Integration APIs**: Connect with calendars, mood trackers, etc.

## ⚠️ **Important Disclaimers**

- **Not a Replacement for Professional Care**: MyBro provides peer support, not medical treatment
- **Crisis Situations**: Always contact emergency services (911) or crisis helplines for immediate danger
- **Privacy**: Conversations are stored locally; review data handling before deployment
- **Limitations**: AI responses, while sophisticated, cannot replace human judgment

## 📞 **Crisis Resources**

- **US**: 988 Suicide & Crisis Lifeline
- **UK**: 116 123 (Samaritans)
- **International**: [IASP Crisis Centers](https://www.iasp.info/resources/Crisis_Centres/)

## 📜 **License**

This project is open source and available under the [MIT License](LICENSE).

## 🙋 **Support**

- **Issues**: [GitHub Issues](https://github.com/Jit-Roy/MyBro/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Jit-Roy/MyBro/discussions)
- **Email**: [Your contact email]

---

**Built with ❤️ for mental health support**

*"Sometimes you need someone who fights for you when you can't fight for yourself."*

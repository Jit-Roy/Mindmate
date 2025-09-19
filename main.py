import asyncio
import sys
import atexit
import uuid
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from chatbot import MentalHealthChatbot
from config import config
from notification import setup_notifications, send_exit_notification

console = Console()

class ChatInterface:
    """Interactive chat interface for the mental health chatbot."""
    
    def __init__(self):
        self.chatbot = MentalHealthChatbot()
        # Generate unique user ID for each session
        self.user_id = f"user_{uuid.uuid4().hex[:8]}"
        self.running = True
        self.notification_system = None
        
        # Setup exit handler for notifications
        atexit.register(self._on_exit)
    
    def display_welcome(self):
        """Display welcome message."""
        welcome_text = Text()
        welcome_text.append("🤗 Mental Health Companion", style="bold cyan")
        welcome_text.append("\n\nHey there! I'm your mental health companion - think of me as a caring older brother who's always here to listen and support you. ")
        welcome_text.append("I'm here to chat about whatever's on your mind, especially when it comes to your emotional well-being.\n\n", style="green")
        welcome_text.append("💙 I can help with:", style="bold blue")
        welcome_text.append("\n• Managing stress and anxiety")
        welcome_text.append("\n• Working through difficult emotions")
        welcome_text.append("\n• Daily emotional check-ins")
        welcome_text.append("\n• Coping strategies and suggestions")
        welcome_text.append("\n• Just being someone to talk to")
        welcome_text.append("\n\n⚠️  Important: If you're experiencing a mental health crisis, please reach out to emergency services or a crisis helpline immediately.", style="bold red")
        welcome_text.append("\n\nType 'quit' or 'exit' to end our conversation anytime.", style="dim")
        welcome_text.append("\nType 'help' for more commands.\n", style="dim")
        
        console.print(Panel(welcome_text, title="Welcome", border_style="cyan"))
    
    def display_help(self):
        """Display help information."""
        help_text = Text()
        help_text.append("Available Commands:", style="bold cyan")
        help_text.append("\n• quit/exit - End the conversation")
        help_text.append("\n• help - Show this help message")
        help_text.append("\n• profile - Set up your profile")
        help_text.append("\n• checkin - Get a daily check-in")
        help_text.append("\n• clear - Clear conversation history")
        help_text.append("\n\nJust type naturally to chat about your mental health and well-being!", style="green")
        
        console.print(Panel(help_text, title="Help", border_style="yellow"))
    
    def setup_profile(self):
        """Set up user profile."""
        console.print("\n[bold cyan]Let's set up your profile so I can support you better![/bold cyan]")
        
        name = Prompt.ask("What would you like me to call you?", default="friend")
        age = Prompt.ask("What's your age? (optional)", default="")
        
        # Update profile
        profile_updates = {
            "name": name,
            "preferred_name": name
        }
        
        if age and age.isdigit():
            profile_updates["age"] = int(age)
        
        self.chatbot.memory_manager.update_user_profile(self.user_id, profile_updates)
        
        console.print(f"\n[green]Great! I'll call you {name}. Feel free to share whatever's on your mind.[/green]")
    
    def display_response(self, response):
        """Display chatbot response with styling."""
        
        # Main response
        response_text = Text(response.message, style="white")
        console.print(Panel(response_text, title="💙 Your Mental Health Companion", border_style="blue"))
        
        # Show suggestions if any
        if response.suggestions:
            suggestions_text = Text()
            suggestions_text.append("💡 Suggestions:", style="bold yellow")
            for i, suggestion in enumerate(response.suggestions, 1):
                suggestions_text.append(f"\n  {i}. {suggestion}")
            
            console.print(Panel(suggestions_text, title="Helpful Suggestions", border_style="yellow"))
        
        # Show urgency indicator if needed
        if response.urgency_detected:
            urgency_text = Text("⚠️  I notice you might be going through a particularly difficult time. Please consider reaching out to a mental health professional or crisis helpline if you need immediate support.", style="bold red")
            console.print(Panel(urgency_text, title="Important Notice", border_style="red"))
    
    def display_daily_checkin(self):
        """Display daily check-in."""
        checkin = self.chatbot.get_daily_check_in(self.user_id)
        if checkin:
            checkin_text = Text(checkin, style="cyan")
            console.print(Panel(checkin_text, title="🌅 Daily Check-in", border_style="cyan"))
        else:
            console.print("[yellow]You've already checked in today! How are you feeling now?[/yellow]")
    
    def clear_history(self):
        """Clear conversation history."""
        # Create new conversation
        self.chatbot.memory_manager.create_conversation(self.user_id)
        console.print("[green]Conversation history cleared. Fresh start![/green]")
    
    def _on_exit(self):
        """Handle application exit - send caring notification."""
        try:
            if hasattr(self, 'chatbot') and hasattr(self, 'user_id'):
                send_exit_notification(self.chatbot.memory_manager, self.user_id)
            
            if self.notification_system:
                self.notification_system.stop_background_monitoring()
        except Exception as e:
            pass  # Don't show errors during exit
    
    async def run(self):
        """Main chat loop."""
        
        # Check if API key is configured
        if not config.gemini_api_key or config.gemini_api_key == "your_gemini_api_key_here":
            console.print("[bold red]⚠️  SETUP REQUIRED:[/bold red]")
            console.print("Please set up your Gemini API key:")
            console.print("1. Copy .env.example to .env")
            console.print("2. Add your Gemini API key to the .env file")
            console.print("3. Restart the application")
            return
        
        self.display_welcome()
        
        # Check if there are existing users and offer to continue
        existing_profiles = self.chatbot.memory_manager.get_all_user_profiles()
        if existing_profiles:
            # Show existing users (without IDs for privacy)
            user_names = [p.name or p.preferred_name for p in existing_profiles.values() if p.name or p.preferred_name]
            if user_names:
                console.print(f"\n[dim]I recognize some friends: {', '.join(user_names[:3])}{'...' if len(user_names) > 3 else ''}[/dim]")
                continue_choice = Prompt.ask("Are you continuing a previous conversation?", choices=["y", "n"], default="n")
                
                if continue_choice.lower() == "y":
                    name_to_find = Prompt.ask("What name did you use before?")
                    existing_user = self.chatbot.memory_manager.find_user_by_name(name_to_find)
                    if existing_user:
                        self.user_id = existing_user.user_id
                        console.print(f"[green]Welcome back, {existing_user.name or existing_user.preferred_name}! 😊[/green]")
                        # Update notification system for the existing user
                        try:
                            if self.notification_system:
                                self.notification_system.stop_background_monitoring()
                            self.notification_system = setup_notifications(self.chatbot.memory_manager, self.user_id)
                        except Exception:
                            pass
                    else:
                        console.print(f"[yellow]Hmm, I don't recognize that name. Let's start fresh! 🌟[/yellow]")
        
        # Setup notification system
        try:
            if not self.notification_system:
                self.notification_system = setup_notifications(self.chatbot.memory_manager, self.user_id)
            console.print("[dim]🔔 Caring notifications enabled - I'll check in on you periodically[/dim]")
        except Exception as e:
            console.print(f"[dim yellow]⚠️  Notifications unavailable: {e}[/dim yellow]")
        
        # Ask if they want to set up profile
        setup = Prompt.ask("\nWould you like to set up your profile first?", choices=["y", "n"], default="n")
        if setup.lower() == "y":
            self.setup_profile()
        
        console.print("\n[green]Great! What's on your mind today?[/green]")
        
        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]", default="")
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit']:
                    console.print("\n[cyan]Take care of yourself! I'll keep you in my thoughts. 💙[/cyan]")
                    self.running = False
                    break
                
                elif user_input.lower() == 'help':
                    self.display_help()
                    continue
                
                elif user_input.lower() == 'profile':
                    self.setup_profile()
                    continue
                
                elif user_input.lower() == 'checkin':
                    self.display_daily_checkin()
                    continue
                
                elif user_input.lower() == 'clear':
                    self.clear_history()
                    continue
                
                # Show typing indicator
                with console.status("[bold blue]Thinking...", spinner="dots"):
                    # Get chatbot response
                    response = await self.chatbot.chat(self.user_id, user_input)
                
                # Display response
                self.display_response(response)
                
            except KeyboardInterrupt:
                console.print("\n\n[cyan]Take care! I'll keep you in my thoughts. 💙[/cyan]")
                self.running = False
                break
            
            except Exception as e:
                console.print(f"\n[red]I'm having some technical difficulties: {str(e)}[/red]")
                console.print("[yellow]But I'm still here for you! Try asking me something else.[/yellow]")


def main():
    """Main entry point."""
    try:
        interface = ChatInterface()
        asyncio.run(interface.run())
    except Exception as e:
        console.print(f"[red]Error starting the application: {str(e)}[/red]")
        console.print("[yellow]Please check your configuration and try again.[/yellow]")


if __name__ == "__main__":
    main()

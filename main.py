import asyncio
import sys
import uuid
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from chatbot import MentalHealthChatbot
from config import config
from firebase_manager import firebase_manager
from models import UserProfile

console = Console()

class ChatInterface:
    """Simple email-based chat interface for the mental health chatbot."""
    
    def __init__(self):
        self.chatbot = MentalHealthChatbot()
        self.current_user: UserProfile = None
        self.current_email: str = None  # Track email separately
        self.running = True
    
    def display_welcome(self):
        """Display welcome message."""
        welcome_text = Text()
        welcome_text.append("� MyBro AI - Mental Health Companion", style="bold cyan")
        welcome_text.append("\n\nWelcome to MyBro AI! Your mental health companion that remembers your conversations and provides personalized support.\n\n", style="green")
        welcome_text.append("🔑 Features:", style="bold blue")
        welcome_text.append("\n• Simple email-based access")
        welcome_text.append("\n• Personalized conversation history")
        welcome_text.append("\n• Mental health tracking and insights")
        welcome_text.append("\n• Crisis intervention support")
        welcome_text.append("\n• Important event reminders")
        welcome_text.append("\n\n💙 I can help with:", style="bold blue")
        welcome_text.append("\n• Managing stress and anxiety")
        welcome_text.append("\n• Working through difficult emotions")
        welcome_text.append("\n• Daily emotional check-ins")
        welcome_text.append("\n• Coping strategies and suggestions")
        welcome_text.append("\n• Being someone you can trust")
        welcome_text.append("\n\n⚠️  Important: If you're experiencing a mental health crisis, please reach out to emergency services or a crisis helpline immediately.", style="bold red")
        welcome_text.append("\n\nType 'quit' or 'exit' to end our conversation anytime.", style="dim")
        welcome_text.append("\nType 'help' for more commands.\n", style="dim")
        
        console.print(Panel(welcome_text, title="Welcome to MyBro AI", border_style="cyan"))
    
    async def get_user_email(self) -> bool:
        """Get user email and create/retrieve their profile"""
        console.print("\n[bold cyan]� Access MyBro AI[/bold cyan]")
        
        while True:
            email = Prompt.ask("Enter your email address").strip().lower()
            
            if not self._validate_email(email):
                console.print("[red]❌ Please enter a valid email address[/red]")
                continue
                
            # Get or create user profile
            with console.status("[bold blue]Setting up your profile...", spinner="dots"):
                try:
                    # Try to get existing user
                    user_profile = firebase_manager.get_user_profile(email)
                    
                    if user_profile.name == "Unknown":  # New user
                        name = Prompt.ask(f"Hi! I'm MyBro AI 💙 What should I call you?", default="friend")
                        user_profile = firebase_manager.create_user_profile(email, name)
                        console.print(f"[green]✅ Welcome to MyBro AI, {user_profile.name or 'friend'}! Nice to meet you![/green]")
                    else:  # Existing user
                        console.print(f"[green]✅ Welcome back, {user_profile.name or 'friend'}! 💙[/green]")
                    
                    self.current_user = user_profile
                    self.current_email = email  # Store email separately
                    return True
                    
                except Exception as e:
                    console.print(f"[red]❌ Error setting up profile: {e}[/red]")
                    retry = Prompt.ask("Would you like to try again?", choices=["y", "n"], default="y")
                    if retry.lower() == "n":
                        return False
    
    def _validate_email(self, email: str) -> bool:
        """Simple email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def display_user_info(self):
        """Display current user information"""
        if not self.current_user:
            return
            
        user_text = Text()
        user_text.append(f"👤 User: {self.current_user.name or 'friend'}", style="bold green")
        user_text.append(f"\n📧 Email: {self.current_email}")
        user_text.append(f"\n🆔 User ID: {self.current_email}")
        
        console.print(Panel(user_text, title="Current User", border_style="green"))
    
    def display_response(self, response):
        """Display chatbot response with styling."""
        
        # Main response
        response_text = Text(response.message, style="white")
        console.print(Panel(response_text, title=f"💙 MyBro AI (for {self.current_user.name or 'friend'})", border_style="blue"))
        
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
    
    def display_help(self):
        """Display help information."""
        help_text = Text()
        help_text.append("Available Commands:", style="bold cyan")
        help_text.append("\n• ")
        help_text.append("help", style="bold")
        help_text.append(" - Show this help message")
        help_text.append("\n• ")
        help_text.append("profile", style="bold")
        help_text.append(" - View/edit your profile")
        help_text.append("\n• ")
        help_text.append("user", style="bold")
        help_text.append(" - Show current user information")
        help_text.append("\n• ")
        help_text.append("clear", style="bold")
        help_text.append(" - Clear conversation history")
        help_text.append("\n• ")
        help_text.append("logout", style="bold")
        help_text.append(" - Logout and switch user")
        help_text.append("\n• ")
        help_text.append("quit/exit", style="bold")
        help_text.append(" - End conversation")
        
        console.print(Panel(help_text, title="Help", border_style="yellow"))
    
    def setup_profile(self):
        """Set up user profile."""
        console.print("\n[bold cyan]Let's set up your profile so I can support you better![/bold cyan]")
        
        name = Prompt.ask("What would you like me to call you?", default="friend")
        age = Prompt.ask("What's your age? (optional)", default="")
        
        # Update profile - only use name (authorized field)
        profile_updates = {
            "name": name
        }
        
        # Note: age is not stored in profile table
        # Only name is used as the user's name
        
        self.chatbot.memory_manager.update_user_profile(self.current_email, profile_updates)
        
        console.print(f"\n[green]Great! I'll call you {name}. Feel free to share whatever's on your mind.[/green]")
    
    async def run(self):
        """Run the main chat interface."""
        try:
            self.display_welcome()
            
            # Get user email and set up profile
            if not await self.get_user_email():
                console.print("[red]Email required to continue. Goodbye![/red]")
                return
            
            # Display user info
            self.display_user_info()
            
            console.print(f"\n[bold green]Hello {self.current_user.name or 'friend'}! 💙 I'm here to listen and support you.[/bold green]")
            console.print("[dim]Type 'help' for commands or just start chatting![/dim]\n")
            
            while self.running:
                try:
                    # Get user input
                    user_message = console.input("\n[bold cyan]You:[/bold cyan] ")
                    
                    if not user_message.strip():
                        continue
                    
                    # Handle commands
                    if user_message.lower() in ['quit', 'exit', 'bye']:
                        console.print("\n[green]Take care! Remember, I'm always here when you need someone to talk to. 💙[/green]")
                        break
                    elif user_message.lower() == 'help':
                        self.display_help()
                        continue
                    elif user_message.lower() == 'profile':
                        self.setup_profile()
                        continue
                    elif user_message.lower() == 'user':
                        self.display_user_info()
                        continue
                    elif user_message.lower() == 'clear':
                        console.clear()
                        self.display_welcome()
                        continue
                    elif user_message.lower() == 'logout':
                        console.print("\n[yellow]Switching user...[/yellow]")
                        self.current_user = None
                        self.current_email = None
                        if await self.get_user_email():
                            self.display_user_info()
                            console.print(f"\n[bold green]Welcome {self.current_user.name or 'friend'}![/bold green]")
                        else:
                            console.print("[red]Email required to continue. Goodbye![/red]")
                            break
                        continue
                    
                    # Get chatbot response
                    with console.status("[dim]Thinking...", spinner="dots"):
                        response = await self.chatbot.chat(self.current_email, user_message)
                    
                    # Display response
                    self.display_response(response)
                    
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Chat interrupted. Type 'quit' to exit properly.[/yellow]")
                    continue
                except Exception as e:
                    console.print(f"\n[red]❌ An error occurred: {e}[/red]")
                    console.print("[yellow]Please try again or type 'quit' to exit.[/yellow]")
                    continue
                    
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Goodbye! Take care of yourself. 💙[/yellow]")
        except Exception as e:
            console.print(f"\n[red]❌ Fatal error: {e}[/red]")
            console.print("[yellow]Please restart the application.[/yellow]")
        finally:
            self.running = False

async def main():
    """Main entry point."""
    chat = ChatInterface()
    await chat.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting application: {e}[/red]")
    
    def clear_history(self):
        """Clear conversation history."""
        # Create new conversation
        self.chatbot.memory_manager.create_conversation(self.current_email)
        console.print("[green]Conversation history cleared. Fresh start![/green]")
    
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
            user_names = [p.name for p in existing_profiles.values() if p.name]
            if user_names:
                console.print(f"\n[dim]I recognize some friends: {', '.join(user_names[:3])}{'...' if len(user_names) > 3 else ''}[/dim]")
                continue_choice = Prompt.ask("Are you continuing a previous conversation?", choices=["y", "n"], default="n")
                
                if continue_choice.lower() == "y":
                    name_to_find = Prompt.ask("What name did you use before?")
                    existing_user = self.chatbot.memory_manager.find_user_by_name(name_to_find)
                    if existing_user:
                        # Note: In email-based schema, we should match by email not user_id
                        console.print(f"[green]Welcome back, {existing_user.name or 'friend'}! 😊[/green]")
                    else:
                        console.print(f"[yellow]Hmm, I don't recognize that name. Let's start fresh! 🌟[/yellow]")
        
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
                
                elif user_input.lower() == 'clear':
                    self.clear_history()
                    continue
                
                # Show typing indicator
                with console.status("[bold blue]Thinking...", spinner="dots"):
                    # Get chatbot response
                    response = await self.chatbot.chat(self.current_email, user_input)
                
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

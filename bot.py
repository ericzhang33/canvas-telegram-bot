#!/usr/bin/env python3
"""
Canvas to Telegram Bot
Fetches your UofT Quercus assignments and sends daily reminders via Telegram
"""

import os
import sys
from datetime import datetime, timedelta
from canvasapi import Canvas
import requests
from dotenv import load_dotenv
import schedule
import time

# Load environment variables
load_dotenv()

# Configuration
CANVAS_API_URL = "https://q.utoronto.ca"  # UofT Quercus
CANVAS_API_KEY = os.getenv("CANVAS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# How many days ahead to look for assignments
DAYS_AHEAD = 7


def send_telegram_message(message):
    """Send a message via Telegram Bot API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"✓ Message sent successfully at {datetime.now()}")
        return True
    except Exception as e:
        print(f"✗ Error sending message: {e}")
        return False


def get_upcoming_assignments():
    """Fetch upcoming assignments from Canvas"""
    try:
        # Initialize Canvas
        canvas = Canvas(CANVAS_API_URL, CANVAS_API_KEY)
        
        # Get current user
        user = canvas.get_current_user()
        print(f"Connected to Canvas as: {user.name}")
        
        # Get all courses
        courses = list(user.get_courses(enrollment_state='active'))
        
        # Collect all assignments
        all_assignments = []
        
        for course in courses:
            try:
                assignments = course.get_assignments()
                for assignment in assignments:
                    # Only include assignments with due dates
                    if hasattr(assignment, 'due_at') and assignment.due_at:
                        due_date = datetime.strptime(assignment.due_at, "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Only include upcoming assignments
                        days_until_due = (due_date - datetime.now()).days
                        
                        if 0 <= days_until_due <= DAYS_AHEAD:
                            all_assignments.append({
                                'course': course.name,
                                'name': assignment.name,
                                'due_date': due_date,
                                'days_until': days_until_due,
                                'url': assignment.html_url
                            })
            except Exception as e:
                print(f"Warning: Couldn't fetch assignments for {course.name}: {e}")
                continue
        
        # Sort by due date
        all_assignments.sort(key=lambda x: x['due_date'])
        
        return all_assignments
        
    except Exception as e:
        print(f"Error fetching assignments: {e}")
        return None


def format_agenda_message(assignments):
    """Format assignments into a nice Telegram message"""
    if not assignments:
        return "🎉 <b>No upcoming assignments!</b>\n\nYou're all caught up for the next week. Enjoy your free time!"
    
    # Header
    message = f"📚 <b>Your Canvas Agenda</b>\n"
    message += f"📅 {datetime.now().strftime('%A, %B %d, %Y')}\n"
    message += "─" * 30 + "\n\n"
    
    # Group by urgency
    urgent = [a for a in assignments if a['days_until'] <= 2]
    upcoming = [a for a in assignments if 2 < a['days_until'] <= 7]
    
    if urgent:
        message += "🔴 <b>URGENT (Due in 2 days or less)</b>\n\n"
        for assignment in urgent:
            emoji = "🔥" if assignment['days_until'] == 0 else "⚠️"
            due_text = "TODAY" if assignment['days_until'] == 0 else f"in {assignment['days_until']} day(s)"
            message += f"{emoji} <b>{assignment['name']}</b>\n"
            message += f"   📖 {assignment['course']}\n"
            message += f"   ⏰ Due {due_text} - {assignment['due_date'].strftime('%b %d, %I:%M %p')}\n\n"
    
    if upcoming:
        message += "📋 <b>UPCOMING (Next 3-7 days)</b>\n\n"
        for assignment in upcoming:
            message += f"📌 <b>{assignment['name']}</b>\n"
            message += f"   📖 {assignment['course']}\n"
            message += f"   ⏰ Due in {assignment['days_until']} days - {assignment['due_date'].strftime('%b %d, %I:%M %p')}\n\n"
    
    # Footer
    message += "─" * 30 + "\n"
    message += f"Total: {len(assignments)} assignment(s) due this week"
    
    return message


def send_daily_agenda():
    """Main function to fetch and send daily agenda"""
    print(f"\n{'='*50}")
    print(f"Running daily agenda at {datetime.now()}")
    print(f"{'='*50}\n")
    
    # Fetch assignments
    assignments = get_upcoming_assignments()
    
    if assignments is None:
        send_telegram_message("⚠️ <b>Error</b>\n\nCouldn't fetch assignments from Canvas. Check your API key.")
        return
    
    # Format and send message
    message = format_agenda_message(assignments)
    send_telegram_message(message)


def test_connection():
    """Test Canvas and Telegram connections"""
    print("Testing connections...\n")
    
    # Test Canvas
    try:
        canvas = Canvas(CANVAS_API_URL, CANVAS_API_KEY)
        user = canvas.get_current_user()
        print(f"✓ Canvas connected: {user.name}")
    except Exception as e:
        print(f"✗ Canvas connection failed: {e}")
        return False
    
    # Test Telegram
    try:
        test_msg = f"🤖 Bot connected successfully!\n\nTesting at {datetime.now().strftime('%I:%M %p on %B %d, %Y')}"
        if send_telegram_message(test_msg):
            print("✓ Telegram connected")
        else:
            print("✗ Telegram connection failed")
            return False
    except Exception as e:
        print(f"✗ Telegram connection failed: {e}")
        return False
    
    print("\n✓ All connections successful!\n")
    return True


def main():
    """Main entry point"""
    # Check environment variables
    if not all([CANVAS_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: Missing environment variables!")
        print("Make sure .env file contains:")
        print("  - CANVAS_API_KEY")
        print("  - TELEGRAM_BOT_TOKEN")
        print("  - TELEGRAM_CHAT_ID")
        sys.exit(1)
    
    # Test connections first
    if not test_connection():
        print("\nConnection test failed. Please check your credentials.")
        sys.exit(1)
    
    # Check if running in test mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("\n🧪 TEST MODE - Sending one agenda now...\n")
        send_daily_agenda()
        print("\n✓ Test complete!")
        return
    
    # Schedule daily messages
    # Default: 8:00 AM every day (change this time as needed)
    schedule.every().day.at("08:00").do(send_daily_agenda)
    
    print("\n🤖 Bot is running!")
    print("📅 Scheduled to send daily agenda at 8:00 AM")
    print("Press Ctrl+C to stop\n")
    
    # Run immediately on startup (optional - comment out if you don't want this)
    send_daily_agenda()
    
    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped")


if __name__ == "__main__":
    main()

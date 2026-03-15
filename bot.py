#!/usr/bin/env python3
"""
Enhanced Canvas + Outlook Calendar to Telegram Bot
Features:
- Canvas assignments
- Outlook Calendar integration
- Custom events (/add command)
- Custom reminders (/remind command)
- Automatic day-before reminders
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import pytz
from canvasapi import Canvas
import requests
from dotenv import load_dotenv
import schedule
import time
import re
from msal import ConfidentialClientApplication

# Load environment variables
load_dotenv()

# Configuration
CANVAS_API_URL = "https://q.utoronto.ca"
CANVAS_API_KEY = os.getenv("CANVAS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Microsoft Graph API (Outlook)
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
MS_TENANT_ID = os.getenv("MS_TENANT_ID")

DAYS_AHEAD = 14
DB_FILE = "bot_data.db"

# Set your timezone
LOCAL_TZ = pytz.timezone('America/Toronto')

# Initialize database
def init_db():
    """Initialize SQLite database for custom events and reminders"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Custom events table
    c.execute('''CREATE TABLE IF NOT EXISTS custom_events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  due_date TEXT NOT NULL,
                  recurring TEXT DEFAULT 'no',
                  frequency TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Custom reminders table
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  remind_at TEXT NOT NULL,
                  message TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Sent day-before reminders tracking
    c.execute('''CREATE TABLE IF NOT EXISTS sent_reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  assignment_id TEXT NOT NULL,
                  sent_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()


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


def get_outlook_events():
    """Fetch upcoming events from Outlook Calendar using Microsoft Graph API"""
    if not all([MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID]):
        print("⚠ Outlook credentials not configured, skipping calendar sync")
        return []
    
    try:
        # Create MSAL application
        app = ConfidentialClientApplication(
            MS_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{MS_TENANT_ID}",
            client_credential=MS_CLIENT_SECRET
        )
        
        # Get access token
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        
        if "access_token" not in result:
            print(f"✗ Failed to get Outlook token: {result.get('error_description')}")
            return []
        
        access_token = result["access_token"]
        
        # Get calendar events for next 7 days
        now = datetime.utcnow()
        end_date = now + timedelta(days=DAYS_AHEAD)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "$filter": f"start/dateTime ge '{now.isoformat()}' and start/dateTime le '{end_date.isoformat()}'",
            "$select": "subject,start,end,location",
            "$orderby": "start/dateTime"
        }
        
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me/events",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        
        events = response.json().get("value", [])
        
        # Parse events
        calendar_events = []
        for event in events:
            start_str = event["start"]["dateTime"]
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            
            calendar_events.append({
                'name': event['subject'],
                'start_time': start_time,
                'location': event.get('location', {}).get('displayName', 'No location'),
                'days_until': (start_time.date() - datetime.now().date()).days
            })
        
        print(f"✓ Fetched {len(calendar_events)} Outlook events")
        return calendar_events
        
    except Exception as e:
        print(f"✗ Error fetching Outlook events: {e}")
        return []


def get_upcoming_assignments():
    """Fetch upcoming assignments from Canvas"""
    try:
        canvas = Canvas(CANVAS_API_URL, CANVAS_API_KEY)
        user = canvas.get_current_user()
        print(f"Connected to Canvas as: {user.name}")
        
        courses = list(user.get_courses(enrollment_state='active'))
        all_assignments = []
        
        for course in courses:
            try:
                assignments = course.get_assignments()
                for assignment in assignments:
                    if hasattr(assignment, 'due_at') and assignment.due_at:
                        due_date_utc = datetime.strptime(assignment.due_at, "%Y-%m-%dT%H:%M:%SZ")
                        due_date_utc = due_date_utc.replace(tzinfo=timezone.utc)
                        due_date = due_date_utc.astimezone(LOCAL_TZ)
                        days_until_due = (due_date - datetime.now()).days
                        
                        if 0 <= days_until_due <= DAYS_AHEAD:
                            all_assignments.append({
                                'id': f"canvas_{assignment.id}",
                                'course': course.name,
                                'name': assignment.name,
                                'due_date': due_date,
                                'days_until': days_until_due,
                                'url': assignment.html_url
                            })
            except Exception as e:
                print(f"Warning: Couldn't fetch assignments for {course.name}: {e}")
                continue
        
        all_assignments.sort(key=lambda x: x['due_date'])
        return all_assignments
        
    except Exception as e:
        print(f"Error fetching assignments: {e}")
        return None


def get_custom_events():
    """Fetch custom events from database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    events = []
    now = datetime.now()
    end_date = now + timedelta(days=DAYS_AHEAD)
    
    c.execute("SELECT id, name, due_date, recurring, frequency FROM custom_events")
    rows = c.fetchall()
    
    for row in rows:
        event_id, name, due_date_str, recurring, frequency = row
        due_date = datetime.fromisoformat(due_date_str)
        
        # Check if event is within range
        if now <= due_date <= end_date:
            days_until = (due_date - now).days
            events.append({
                'id': f"custom_{event_id}",
                'name': name,
                'due_date': due_date,
                'days_until': days_until,
                'recurring': recurring,
                'frequency': frequency
            })
    
    conn.close()
    return events


def format_full_agenda(assignments, calendar_events, custom_events):
    """Format complete agenda with all sources"""
    message = f"📚 <b>Your Complete Agenda</b>\n"
    message += f"📅 {datetime.now().strftime('%A, %B %d, %Y')}\n"
    message += "─" * 30 + "\n\n"
    
    # Combine all items and sort by date
    all_items = []
    
    # Canvas assignments
    if assignments:
        for a in assignments:
            all_items.append({
                'type': '📝 Assignment',
                'name': a['name'],
                'course': a.get('course', ''),
                'date': a['due_date'],
                'days_until': a['days_until']
            })
    
    # Outlook calendar events
    for e in calendar_events:
        all_items.append({
            'type': '📅 Calendar',
            'name': e['name'],
            'location': e.get('location', ''),
            'date': e['start_time'],
            'days_until': e['days_until']
        })
    
    # Custom events
    for e in custom_events:
        all_items.append({
            'type': '⭐ Custom',
            'name': e['name'],
            'date': e['due_date'],
            'days_until': e['days_until']
        })
    
    if not all_items:
        return "🎉 <b>No upcoming items!</b>\n\nYou're all caught up for the next week. Enjoy your free time!"
    
    # Sort by date
    all_items.sort(key=lambda x: x['date'])
    
    # Group by urgency
    urgent = [i for i in all_items if i['days_until'] <= 2]
    upcoming = [i for i in all_items if 2 < i['days_until'] <= 7]
    
    if urgent:
        message += "🔴 <b>URGENT (Due in 2 days or less)</b>\n\n"
        for item in urgent:
            emoji = "🔥" if item['days_until'] == 0 else "⚠️"
            due_text = "TODAY" if item['days_until'] == 0 else f"in {item['days_until']} day(s)"
            
            message += f"{emoji} <b>{item['name']}</b>\n"
            message += f"   {item['type']}\n"
            if 'course' in item and item['course']:
                message += f"   📖 {item['course']}\n"
            if 'location' in item and item['location']:
                message += f"   📍 {item['location']}\n"
            message += f"   ⏰ Due {due_text} - {item['date'].strftime('%b %d, %I:%M %p')}\n\n"
    
    if upcoming:
        message += "📋 <b>UPCOMING (Next 3-7 days)</b>\n\n"
        for item in upcoming:
            message += f"📌 <b>{item['name']}</b>\n"
            message += f"   {item['type']}\n"
            if 'course' in item and item['course']:
                message += f"   📖 {item['course']}\n"
            if 'location' in item and item['location']:
                message += f"   📍 {item['location']}\n"
            message += f"   ⏰ Due in {item['days_until']} days - {item['date'].strftime('%b %d, %I:%M %p')}\n\n"
    
    message += "─" * 30 + "\n"
    message += f"Total: {len(all_items)} item(s) due this week"
    
    return message


def send_daily_agenda():
    """Main function to fetch and send daily agenda"""
    print(f"\n{'='*50}")
    print(f"Running daily agenda at {datetime.now()}")
    print(f"{'='*50}\n")
    
    # Fetch all data
    assignments = get_upcoming_assignments()
    calendar_events = get_outlook_events()
    custom_events = get_custom_events()
    
    if assignments is None:
        send_telegram_message("⚠️ <b>Error</b>\n\nCouldn't fetch assignments from Canvas.")
        return
    
    # Format and send message
    message = format_full_agenda(assignments, calendar_events, custom_events)
    send_telegram_message(message)


def check_day_before_reminders():
    """Check for assignments due tomorrow and send reminders"""
    print(f"Checking for day-before reminders at {datetime.now()}")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get Canvas assignments
    assignments = get_upcoming_assignments()
    if not assignments:
        conn.close()
        return
    
    # Get custom events
    custom_events = get_custom_events()
    
    # Combine all items due tomorrow
    tomorrow_items = []
    
    for a in assignments:
        if a['days_until'] == 1:  # Due tomorrow
            # Check if already reminded
            c.execute("SELECT id FROM sent_reminders WHERE assignment_id = ?", (a['id'],))
            if not c.fetchone():
                tomorrow_items.append(a)
                # Mark as reminded
                c.execute("INSERT INTO sent_reminders (assignment_id) VALUES (?)", (a['id'],))
    
    for e in custom_events:
        if e['days_until'] == 1:
            event_id = e['id']
            c.execute("SELECT id FROM sent_reminders WHERE assignment_id = ?", (event_id,))
            if not c.fetchone():
                tomorrow_items.append(e)
                c.execute("INSERT INTO sent_reminders (assignment_id) VALUES (?)", (event_id,))
    
    conn.commit()
    conn.close()
    
    # Send reminder if there are items due tomorrow
    if tomorrow_items:
        message = "⏰ <b>DAY-BEFORE REMINDER</b>\n\n"
        message += f"You have {len(tomorrow_items)} item(s) due TOMORROW:\n\n"
        
        for item in tomorrow_items:
            message += f"🔔 <b>{item['name']}</b>\n"
            if 'course' in item:
                message += f"   📖 {item['course']}\n"
            message += f"   ⏰ Due tomorrow - {item['due_date'].strftime('%b %d, %I:%M %p')}\n\n"
        
        message += "Get started today! 💪"
        send_telegram_message(message)
        print(f"✓ Sent day-before reminder for {len(tomorrow_items)} items")


def handle_telegram_commands():
    """Poll for Telegram commands and handle them"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    try:
        # Get last processed update ID
        offset_file = "last_update_id.txt"
        if os.path.exists(offset_file):
            with open(offset_file, 'r') as f:
                offset = int(f.read().strip()) + 1
        else:
            offset = 0
        
        response = requests.get(url, params={"offset": offset, "timeout": 1})
        data = response.json()
        
        if not data.get("ok"):
            return
        
        for update in data.get("result", []):
            update_id = update["update_id"]
            
            # Save last update ID
            with open(offset_file, 'w') as f:
                f.write(str(update_id))
            
            if "message" not in update:
                continue
            
            message = update["message"]
            if "text" not in message:
                continue
            
            text = message["text"].strip()
            
            # Handle /remind command
            if text.startswith("/remind"):
                handle_remind_command(text)
            
            # Handle /add command
            elif text.startswith("/add"):
                handle_add_command(text)
    
    except Exception as e:
        print(f"Error polling commands: {e}")


def handle_remind_command(text):
    """Handle /remind command"""
    parts = text.split(maxsplit=1)
    
    # /remind with no args - send agenda now
    if len(parts) == 1:
        send_daily_agenda()
        return
    
    # Parse time argument
    time_arg = parts[1].strip()
    
    # Parse number and unit (days or hours)
    match = re.match(r'(\d+)\s*(hours?|days?)?', time_arg, re.IGNORECASE)
    
    if not match:
        send_telegram_message("❌ Invalid format. Use: /remind OR /remind 2 OR /remind 3 hours")
        return
    
    number = int(match.group(1))
    unit = match.group(2) or "days"
    
    # Calculate remind time
    if "hour" in unit.lower():
        remind_at = datetime.now() + timedelta(hours=number)
        time_desc = f"{number} hour(s)"
    else:
        remind_at = datetime.now() + timedelta(days=number)
        time_desc = f"{number} day(s)"
    
    # Store reminder in database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO reminders (remind_at, message) VALUES (?, ?)",
              (remind_at.isoformat(), "Scheduled agenda reminder"))
    conn.commit()
    conn.close()
    
    send_telegram_message(f"✅ Reminder set for {time_desc} from now\n({remind_at.strftime('%b %d at %I:%M %p')})")


def handle_add_command(text):
    """Handle /add command
    Format: /add [event_name] [recurring=yes/no] [freq=daily/weekly/etc] [due_date]
    Example: /add "Weekly Quiz" recurring=yes freq=weekly 2026-03-20
    """
    try:
        # Parse command
        pattern = r'/add\s+"([^"]+)"\s+recurring=(yes|no)\s+freq=(\w+)\s+(\S+)'
        match = re.match(pattern, text)
        
        if not match:
            send_telegram_message(
                "❌ Invalid format.\n\n"
                "Use: /add \"Event Name\" recurring=yes/no freq=daily/weekly due_date\n\n"
                "Example: /add \"Weekly Quiz\" recurring=yes freq=weekly 2026-03-20"
            )
            return
        
        name = match.group(1)
        recurring = match.group(2)
        frequency = match.group(3)
        due_date_str = match.group(4)
        
        # Parse due date
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError:
            send_telegram_message("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2026-03-20)")
            return
        
        # Store in database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO custom_events (name, due_date, recurring, frequency) VALUES (?, ?, ?, ?)",
            (name, due_date.isoformat(), recurring, frequency)
        )
        conn.commit()
        conn.close()
        
        send_telegram_message(
            f"✅ Event added successfully!\n\n"
            f"📌 {name}\n"
            f"⏰ Due: {due_date.strftime('%b %d, %Y')}\n"
            f"🔄 Recurring: {recurring}\n"
            f"📆 Frequency: {frequency if recurring == 'yes' else 'N/A'}"
        )
        
    except Exception as e:
        send_telegram_message(f"❌ Error adding event: {str(e)}")


def check_custom_reminders():
    """Check and send any pending custom reminders"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    now = datetime.now()
    
    # Get pending reminders
    c.execute("SELECT id, remind_at, message FROM reminders WHERE remind_at <= ?", (now.isoformat(),))
    reminders = c.fetchall()
    
    for reminder_id, remind_at, message in reminders:
        # Send agenda
        send_daily_agenda()
        
        # Delete reminder
        c.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        print(f"✓ Sent custom reminder (ID: {reminder_id})")
    
    conn.commit()
    conn.close()


def test_connection():
    """Test all connections"""
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
        test_msg = f"🤖 Bot connected!\n\nTesting at {datetime.now().strftime('%I:%M %p on %B %d, %Y')}"
        if send_telegram_message(test_msg):
            print("✓ Telegram connected")
        else:
            return False
    except Exception as e:
        print(f"✗ Telegram connection failed: {e}")
        return False
    
    # Test Outlook (optional)
    if all([MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID]):
        try:
            events = get_outlook_events()
            print(f"✓ Outlook connected ({len(events)} events)")
        except Exception as e:
            print(f"⚠ Outlook connection failed (optional): {e}")
    else:
        print("⚠ Outlook not configured (optional)")
    
    print("\n✓ Core connections successful!\n")
    return True


def main():
    """Main entry point"""
    # Initialize database
    init_db()
    
    # Check environment variables
    required_vars = [CANVAS_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]
    if not all(required_vars):
        print("Error: Missing required environment variables!")
        print("Make sure .env file contains:")
        print("  - CANVAS_API_KEY")
        print("  - TELEGRAM_BOT_TOKEN")
        print("  - TELEGRAM_CHAT_ID")
        sys.exit(1)
    
    # Test connections
    if not test_connection():
        print("\nConnection test failed.")
        sys.exit(1)
    
    # Check if running in test mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("\n🧪 TEST MODE - Sending one agenda now...\n")
        send_daily_agenda()
        print("\n✓ Test complete!")
        return
    
    # Schedule tasks
    schedule.every().day.at("11:00").do(send_daily_agenda)  # Morning agenda
    schedule.every().day.at("20:00").do(check_day_before_reminders)  # Evening reminder check
    schedule.every(5).minutes.do(check_custom_reminders)  # Check custom reminders
    
    print("\n🤖 Bot is running!")
    print("📅 Daily agenda: 8:00 AM")
    print("⏰ Day-before check: 8:00 PM")
    print("🔔 Custom reminders: Every 5 minutes")
    print("\nCommands available:")
    print("  /remind - Send agenda now")
    print("  /remind 2 - Remind in 2 days")
    print("  /remind 3 hours - Remind in 3 hours")
    print("  /add \"Event\" recurring=yes freq=weekly 2026-03-20 - Add custom event")
    print("\nPress Ctrl+C to stop\n")
    
    # Send initial agenda
    send_daily_agenda()
    
    # Main loop
    try:
        while True:
            schedule.run_pending()
            handle_telegram_commands()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped")


if __name__ == "__main__":
    main()

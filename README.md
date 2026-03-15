# Canvas to Telegram Bot 🤖

Get daily reminders of your UofT Quercus assignments sent directly to Telegram!

## What This Does

- Fetches your upcoming assignments from Canvas (Quercus)
- Sends you a formatted agenda every day at 8:00 AM
- Highlights urgent assignments (due in 2 days or less)
- Shows all assignments due in the next week
- Runs 24/7 in the cloud (free!)

---

## Setup Guide (20 minutes)

### Step 1: Create Your Telegram Bot (5 mins)

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g., "My Canvas Bot")
4. Choose a username (e.g., "myuoftcanvasbot")
5. **Save the bot token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Get Your Telegram Chat ID (2 mins)

1. Search for `@userinfobot` on Telegram
2. Send it any message
3. It will reply with your Chat ID
4. **Save this number** - looks like: `123456789`

### Step 3: Get Your Canvas API Token (3 mins)

1. Log into Quercus: https://q.utoronto.ca
2. Click your profile (top left) → **Settings**
3. Scroll to **Approved Integrations**
4. Click **+ New Access Token**
5. Purpose: "Telegram Bot"
6. Leave expiry blank (never expires)
7. Click **Generate Token**
8. **Copy and save the token immediately** (you can't see it again!)

### Step 4: Set Up Locally (5 mins)

1. **Download this project** (all files in this folder)

2. **Install Python 3.10+** if you don't have it:
   - Download from https://python.org

3. **Open Terminal/Command Prompt** and navigate to this folder:
   ```bash
   cd path/to/canvas-telegram-bot
   ```

4. **Create a virtual environment:**
   ```bash
   python -m venv venv
   
   # Activate it:
   # On Mac/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

5. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

6. **Create your .env file:**
   - Copy `.env.example` to `.env`
   - Open `.env` and fill in your tokens:
   
   ```
   CANVAS_API_KEY=paste_your_canvas_token_here
   TELEGRAM_BOT_TOKEN=paste_your_bot_token_here
   TELEGRAM_CHAT_ID=paste_your_chat_id_here
   ```

7. **Test it:**
   ```bash
   python bot.py test
   ```
   
   You should get a test message on Telegram!

---

## Running It 24/7 (Deploy to Railway)

### Option A: Railway.app (Recommended - Easiest)

1. **Create a GitHub account** (if you don't have one)

2. **Push your code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/canvas-telegram-bot.git
   git push -u origin main
   ```

3. **Sign up for Railway:** https://railway.app
   - Use your GitHub account

4. **Create new project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `canvas-telegram-bot` repository

5. **Add environment variables:**
   - Click on your service
   - Go to "Variables" tab
   - Add all three variables from your .env file:
     - `CANVAS_API_KEY`
     - `TELEGRAM_BOT_TOKEN`
     - `TELEGRAM_CHAT_ID`

6. **Deploy!**
   - Railway will automatically deploy
   - Your bot is now running 24/7!
   - Check logs to confirm it's working

**Cost:** $5 free credit/month (this bot uses ~$0.10/month)

### Option B: Run on Your Computer

If you want to test without deploying:

```bash
python bot.py
```

Leave this running. The bot will send messages at 8:00 AM daily.

**Note:** Your computer must stay on for this to work.

---

## Customization

### Change the Schedule

Edit `bot.py`, line 194:

```python
# Change "08:00" to your preferred time (24-hour format)
schedule.every().day.at("08:00").do(send_daily_agenda)
```

Examples:
- `"07:30"` = 7:30 AM
- `"20:00"` = 8:00 PM
- `"12:00"` = Noon

### Change How Far Ahead to Look

Edit `bot.py`, line 19:

```python
DAYS_AHEAD = 7  # Change to 14 for 2 weeks, etc.
```

### Multiple Messages Per Day

Add more schedules:

```python
schedule.every().day.at("08:00").do(send_daily_agenda)  # Morning
schedule.every().day.at("20:00").do(send_daily_agenda)  # Evening
```

---

## Troubleshooting

### "Canvas connection failed"
- Double-check your Canvas API token
- Make sure you're using Quercus (q.utoronto.ca), not regular Canvas

### "Telegram connection failed"
- Verify your bot token from BotFather
- Verify your chat ID from userinfobot
- Make sure you've started a conversation with your bot (send `/start`)

### "No assignments found"
- Check if you have any active courses
- Verify assignments have due dates set

### Bot stops running on Railway
- Check Railway logs for errors
- Verify environment variables are set correctly
- Make sure you haven't exceeded free tier limits

---

## Features

✅ Daily automated reminders
✅ Highlights urgent assignments (due in 2 days)
✅ Shows all upcoming work (next 7 days)
✅ Formatted with emojis for quick scanning
✅ Free to run (using Railway's free tier)
✅ Works on your phone via Telegram

---

## Support

If you run into issues:
1. Check the Troubleshooting section above
2. Review Railway logs (if deployed)
3. Make sure all environment variables are correct

---

## Technical Details

- **Language:** Python 3.10+
- **APIs:** Canvas LMS API, Telegram Bot API
- **Hosting:** Railway (or any Python hosting platform)
- **Schedule:** Python `schedule` library
- **Dependencies:** See `requirements.txt`

---

**Enjoy your automated assignment reminders! 📚**

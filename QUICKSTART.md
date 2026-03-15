# QUICK START (5 Minutes)

## Get Your 3 Keys:

1. **Telegram Bot Token:**
   - Message `@BotFather` on Telegram
   - Send `/newbot`
   - Save the token it gives you

2. **Telegram Chat ID:**
   - Message `@userinfobot` on Telegram
   - Save the number it replies with

3. **Canvas API Token:**
   - Go to q.utoronto.ca → Settings → New Access Token
   - Generate and save immediately

## Run It:

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env with your 3 tokens
# (Use any text editor)

# Install dependencies
pip install -r requirements.txt

# Test it
python bot.py test
```

You should get a Telegram message!

## Deploy (Free 24/7):

1. Push to GitHub
2. Sign up for Railway.app
3. Connect your GitHub repo
4. Add the 3 environment variables
5. Deploy

Done! 🎉

**Full instructions:** See README.md

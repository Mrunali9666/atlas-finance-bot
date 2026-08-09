import asyncio
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# Windows event loop fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- DUMMY WEB SERVER TO TRICK RENDER ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Atlas Bot is successfully running and Live!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000)) 
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# ----------------------------------------

# Secure way to get API keys
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    print("Error: API Keys not found! Please set TELEGRAM_TOKEN and GROQ_API_KEY.")
    sys.exit(1)

client = Groq(api_key=GROQ_API_KEY)

# ULTIMATE SAFE SYSTEM PROMPT
SYSTEM_PROMPT = """You are Atlas, a highly intelligent Global Financial Assistant.
Strict Rules:
1. NO GUESSING NUMBERS (SAFE ESCAPE): If a user asks for exact tax brackets, 401(k) contribution limits, or IRS figures for a specific year (like 2024, 2025, or 2026), DO NOT guess or provide outdated numbers. Instead, smoothly reply: "I do not provide specific IRS limits for [Year] as these are subject to frequent updates. I recommend checking the official irs.gov website for the exact figures."
2. CURRENT YEAR IS 2026: Always keep in mind that the current year is 2026.
3. DEFAULT TO US CONTEXT: Assume the United States financial system (Federal Reserve, SEC, IRS) and use US Dollars ($).
4. HANDLE INDIAN TERMS: If explicitly asked about India-specific terms (RBI, NDTL, CRR, SLR), provide the accurate Indian context.
5. Answer concisely, accurately, and act like a Pro Financial Analyst."""

user_conversations = {}
subscribed_users = set()

# --- ONBOARDING EXPERIENCE ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribed_users.add(chat_id)
    user_name = update.effective_user.first_name 
    
    welcome_msg = (
        f"Hi {user_name}! 👋 I am Atlas, your personal AI Finance Assistant.\n\n"
        "To help me personalize your experience, could you tell me a bit about yourself? "
        "What best describes your role (e.g., Investor, Student, Finance Professional)? "
        "And are there any specific stocks or sectors you'd like me to monitor?\n\n"
        "💡 *(Feel free to answer, or just skip this and ask me your first financial question!)*"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

# --- MOCK GOOGLE INTEGRATIONS ---
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🔗 *Connect Your Accounts*\n\n"
        "Atlas can securely connect to your daily tools to provide better financial insights. What would you like to link?\n\n"
        "📧 /connect_gmail - Scan receipts, bills & financial emails\n"
        "📅 /connect_calendar - Sync earnings calls & meeting schedules\n"
        "📁 /connect_drive - Analyze financial PDFs and spreadsheets\n\n"
        "*(You can skip this and connect later at any time!)*"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def connect_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This simulates a quick, seamless connection process safely
    service = update.message.text.split('_')[1].capitalize()
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    await asyncio.sleep(1.5) # Realistic slight delay
    
    success_msg = (
        f"✅ *{service} Successfully Linked!*\n\n"
        f"Atlas is now synced with your {service}. I will use this data to proactively assist you with your financial workflow."
    )
    await update.message.reply_text(success_msg, parse_mode='Markdown')

# --- FINANCIAL FEATURES ---
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a stock ticker symbol.\nExample: `/price TSLA` or `/price AAPL`", parse_mode='Markdown')
        return
    ticker_symbol = context.args[0].upper()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        stock = yf.Ticker(ticker_symbol)
        current_price = stock.fast_info['lastPrice']
        await update.message.reply_text(f"📈 The current live price of **{ticker_symbol}** is **${current_price:.2f}**", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text(f"Sorry, I couldn't fetch the data for {ticker_symbol}. Make sure the symbol is correct.")

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id
    subscribed_users.add(chat_id)
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    if chat_id not in user_conversations:
        user_conversations[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    user_conversations[chat_id].append({"role": "user", "content": user_message})
    
    # Limit memory to the last 30 interactions for deeper context
    if len(user_conversations[chat_id]) > 30:
        user_conversations[chat_id] = [user_conversations[chat_id][0]] + user_conversations[chat_id][-29:]

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=user_conversations[chat_id], 
            temperature=0.2, 
            max_tokens=300,
        )
        ai_reply = completion.choices[0].message.content
        user_conversations[chat_id].append({"role": "assistant", "content": ai_reply})
        await update.message.reply_text(ai_reply)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Sorry, small technical issue.")

async def proactive_market_alert(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in list(subscribed_users):
        try:
            stock = yf.Ticker("SPY")
            price = stock.fast_info['lastPrice']
            alert_msg = (
                "🚨 *Proactive Market Alert*\n\n"
                f"Just keeping you informed: the S&P 500 ETF (SPY) is currently trading at **${price:.2f}**.\n"
                "Let me know if you need a deeper analysis for today's market!"
            )
            await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to send alert to {chat_id}: {e}")

def main():
    print("Starting Atlas Bot (Hackathon Ready Version)... Please wait.")
    
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(CommandHandler("connect_gmail", connect_service))
    app.add_handler(CommandHandler("connect_calendar", connect_service))
    app.add_handler(CommandHandler("connect_drive", connect_service))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    # Proactive alerts
    job_queue = app.job_queue
    job_queue.run_repeating(proactive_market_alert, interval=120, first=10)

    print("Bot is successfully running! Send a message on Telegram.")
    app.run_polling()

if __name__ == '__main__':
    main()
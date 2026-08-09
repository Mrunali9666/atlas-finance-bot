import asyncio
import sys
import os
import yfinance as yf
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# Windows event loop fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Secure way to get API keys from Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Check if keys are loaded
if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    print("Error: API Keys not found! Please set TELEGRAM_TOKEN and GROQ_API_KEY in Environment Variables.")
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name 
    welcome_msg = (
        f"Hi {user_name}! 👋 I am Atlas, your personal AI Finance Assistant.\n\n"
        "How can I help you with your finances today?"
    )
    await update.message.reply_text(welcome_msg)

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
    print(f"User asking: {user_message}")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2, 
            max_tokens=300,
        )
        ai_reply = completion.choices[0].message.content
        await update.message.reply_text(ai_reply)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Sorry, small technical issue.")

def main():
    print("Starting Atlas Bot (Secure & Live Version)... Please wait.")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    print("Bot is successfully running! Send a message on Telegram.")
    app.run_polling()

if __name__ == '__main__':
    main()
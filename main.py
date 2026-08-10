import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# ==========================================
# 🌐 DUMMY WEB SERVER
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Atlas Bot is running successfully on Render!")

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
chat_histories = {}

# ==========================================
# 📈 BACKGROUND JOB (ALERTS)
# ==========================================
async def send_market_alert(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    try:
        spy = yf.Ticker("SPY")
        price = spy.history(period="1d")['Close'].iloc[-1]
        msg = (f"🚨 *Proactive Market Alert*\n\n"
               f"Just keeping you informed: the S&P 500 ETF (SPY) is currently trading at ${price:.2f}.\n"
               f"Let me know if you need a deeper analysis for today's market!")
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
    except:
        pass

# ==========================================
# 🚀 COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome_msg = (
        "Hi Mrunali! 👋 I am Atlas, your personal AI Finance Assistant.\n\n"
        "To personalize your experience, what best describes your role (e.g., Investor, Student, Finance Professional)? "
        "And are there any stocks or sectors you'd like me to monitor?"
    )
    await update.message.reply_text(welcome_msg)
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
    context.job_queue.run_repeating(send_market_alert, interval=120, first=10, chat_id=chat_id, name=str(chat_id))

# ==========================================
# 💬 TEXT MESSAGE HANDLER (MOCKED FOR DEMO)
# ==========================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()
    
    # Simulate AI thinking time
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    await asyncio.sleep(2) 
    
    if "apple" in user_text:
        bot_reply = (
            "🍏 **Apple Inc. (AAPL) Quick Valuation:**\n\n"
            "Apple is currently showing strong market resilience. Key metrics:\n"
            "- **P/E Ratio:** ~28x (Trading at a premium, justified by Services growth).\n"
            "- **Strengths:** Robust free cash flow and aggressive share buybacks.\n"
            "- **Verdict:** Solid long-term hold, though slightly overvalued in the short term."
        )
    else:
        bot_reply = "Based on my real-time financial analysis, the current market indicators show strong resilience. I recommend diversifying your portfolio to hedge against macroeconomic shifts."
        
    await update.message.reply_text(bot_reply)

# ==========================================
# 📄 PDF DOCUMENT HANDLER (MOCKED FOR DEMO)
# ==========================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📥 Document received! Reading the financial report... please wait ⏳")
    
    # Simulate PDF reading and AI processing time
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    await asyncio.sleep(3)
    
    bot_reply = (
        "📄 **Executive Summary:**\n\n"
        "Based on the uploaded financial document, here is the breakdown:\n\n"
        "1. **Revenue Growth:** The company has shown a 12% Year-over-Year increase in top-line revenue.\n"
        "2. **Operating Margins:** Margins have improved by 150 bps due to cost-cutting measures.\n"
        "3. **EPS:** Earnings Per Share beat street estimates.\n\n"
        "**Conclusion:** The financial health is robust. Let me know if you want a deeper dive into the balance sheet!"
    )
    await update.message.reply_text(bot_reply)

# ==========================================
# ⚙️ MAIN SETUP
# ==========================================
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.run_polling(drop_pending_updates=True)
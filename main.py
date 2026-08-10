import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import PyPDF2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# ==========================================
# 🌐 DUMMY WEB SERVER (RENDER KEEP-ALIVE)
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

# ==========================================
# 🔑 API & CLIENT SETUP
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")

groq_client = Groq(api_key=GROQ_API_KEY)
chat_histories = {}

# ==========================================
# 📈 BACKGROUND JOB (LIVE MARKET ALERTS)
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
    except Exception as e:
        print(f"Alert Error: {e}")

# ==========================================
# 🚀 COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name if update.effective_user else "there"
    
    # Initialize real AI memory
    chat_histories[chat_id] = [
        {"role": "system", "content": "You are Atlas, a highly intelligent and professional AI financial assistant. Provide concise, accurate financial answers with a professional tone. Keep responses short and impactful. Format with bold text and bullet points where necessary."}
    ]
    
    welcome_msg = (
        f"Hi {user_name}! 👋 I am Atlas, your personal AI Finance Assistant.\n\n"
        "To personalize your experience, what best describes your role (e.g., Investor, Student, Finance Professional)? "
        "And are there any stocks or sectors you'd like me to monitor?"
    )
    await update.message.reply_text(welcome_msg)
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
    context.job_queue.run_repeating(send_market_alert, interval=120, first=10, chat_id=chat_id, name=str(chat_id))

# ==========================================
# 💬 REAL AI TEXT HANDLER
# ==========================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": "You are Atlas, a professional AI financial assistant."}]

    chat_histories[chat_id].append({"role": "user", "content": user_text})
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        # UPDATED TO NEW GROQ MODEL
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=chat_histories[chat_id],
            max_tokens=600
        )
        bot_reply = response.choices[0].message.content
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply)
    except Exception as e:
        print(f"Groq API Error: {e}")
        error_msg = f"API Error: {str(e)}. Please check if your Groq API key is valid and has not exceeded its limit."
        await update.message.reply_text(error_msg)

# ==========================================
# 📄 REAL AI PDF HANDLER
# ==========================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if not update.message.document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("⚠️ Please upload a valid PDF file.")
        return

    await update.message.reply_text("📥 Document received! Reading and analyzing the financial report... please wait ⏳")
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = "temp_report.pdf"
        await file.download_to_drive(file_path)
        
        extracted_text = ""
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text
                    
        os.remove(file_path)
        
        if not extracted_text.strip():
            await update.message.reply_text("⚠️ Could not extract text. This might be an image-based PDF.")
            return

        user_caption = update.message.caption or "Provide a structured executive summary of this financial document. Highlight key metrics."
        truncated_text = extracted_text[:4000] # Fit within Groq limits
        prompt = f"{user_caption}\n\nHere is the document text:\n{truncated_text}"
        
        if chat_id not in chat_histories:
            chat_histories[chat_id] = [{"role": "system", "content": "You are Atlas, a professional AI financial assistant."}]
            
        messages = chat_histories[chat_id] + [{"role": "user", "content": prompt}]
        
        # UPDATED TO NEW GROQ MODEL
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=800
        )
        bot_reply = response.choices[0].message.content
        
        chat_histories[chat_id].append({"role": "user", "content": "I uploaded a document and asked you to summarize it."})
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply)

    except Exception as e:
        print(f"PDF Error: {e}")
        await update.message.reply_text(f"❌ Error processing document: {str(e)}")

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
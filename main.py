import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import PyPDF2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# ==========================================
# 🌐 DUMMY WEB SERVER (TO KEEP RENDER HAPPY)
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
# 🔑 API KEYS SETUP
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# Dictionary to store chat context (Memory)
chat_histories = {}

# ==========================================
# 📈 BACKGROUND JOB (PROACTIVE MARKET ALERTS)
# ==========================================
async def send_market_alert(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    try:
        # Fetch live SPY (S&P 500) data
        spy = yf.Ticker("SPY")
        price = spy.history(period="1d")['Close'].iloc[-1]
        
        msg = (f"🚨 *Proactive Market Alert*\n\n"
               f"Just keeping you informed: the S&P 500 ETF (SPY) is currently trading at ${price:.2f}.\n"
               f"Let me know if you need a deeper analysis for today's market!")
        
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Failed to send market alert: {e}")

# ==========================================
# 🚀 COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Initialize chat history for the user
    chat_histories[chat_id] = [
        {"role": "system", "content": "You are Atlas, a highly intelligent and professional AI financial assistant. Provide concise, accurate financial answers. Keep responses short and impactful."}
    ]
    
    welcome_msg = (
        "Hi user_name}! 👋 I am Atlas, your personal AI Finance Assistant.\n\n"
        "To personalize your experience, what best describes your role (e.g., Investor, Student, Finance Professional)? "
        "And are there any stocks or sectors you'd like me to monitor? (You can just chat naturally or skip this!)"
    )
    await update.message.reply_text(welcome_msg)
    
    # Start proactive alerts (Starts after 10 seconds, repeats every 120 seconds)
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
    context.job_queue.run_repeating(
        send_market_alert, interval=120, first=10, chat_id=chat_id, name=str(chat_id)
    )

# ==========================================
# 💬 TEXT MESSAGE HANDLER (WITH MEMORY)
# ==========================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": "You are Atlas, a highly intelligent AI financial assistant."}]

    # Append user message to history
    chat_histories[chat_id].append({"role": "user", "content": user_text})

    try:
        # Call Groq API for response
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192", 
            messages=chat_histories[chat_id],
            max_tokens=500
        )
        bot_reply = response.choices[0].message.content
        
        # Append bot response to history
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})
        
        await update.message.reply_text(bot_reply)
    except Exception as e:
        print(f"Groq API Error: {e}")
        await update.message.reply_text("I am currently analyzing massive amounts of data. Please try your request again in a moment.")

# ==========================================
# 📄 PDF DOCUMENT HANDLER
# ==========================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if not update.message.document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("⚠️ Please upload a valid PDF file.")
        return

    await update.message.reply_text("📥 Document received! Reading the financial report... please wait ⏳")
    
    try:
        # 1. Download PDF
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = "temp_report.pdf"
        await file.download_to_drive(file_path)
        
        # 2. Extract Text
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

        # 3. Prepare AI Prompt
        user_caption = update.message.caption or "Provide a structured executive summary of this financial document."
        truncated_text = extracted_text[:5000] # Limit text length
        prompt = f"{user_caption}\n\nHere is the document text:\n{truncated_text}"
        
        if chat_id not in chat_histories:
            chat_histories[chat_id] = [{"role": "system", "content": "You are Atlas, a highly intelligent AI financial assistant."}]
            
        messages = chat_histories[chat_id] + [{"role": "user", "content": prompt}]
        
        # 4. Get Summary from AI
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages,
            max_tokens=800
        )
        bot_reply = response.choices[0].message.content
        
        # Save context to memory
        chat_histories[chat_id].append({"role": "user", "content": "I uploaded a document and asked you to summarize it."})
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})

        await update.message.reply_text(bot_reply)

    except Exception as e:
        print(f"PDF Processing Error: {e}")
        await update.message.reply_text("❌ There was an error processing your document. It might be too large.")

# ==========================================
# ⚙️ MAIN APPLICATION SETUP
# ==========================================
if __name__ == "__main__":
    print("Starting Atlas Bot...")
    
    # 🔴 START DUMMY WEB SERVER IN BACKGROUND
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # Initialize the Application
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Register Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Run Bot
    print("Bot is live and polling!")
    app.run_polling(drop_pending_updates=True)
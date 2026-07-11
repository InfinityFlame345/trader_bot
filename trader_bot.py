import os
from flask import Flask, request, jsonify
from telegram import Update, Bot, ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf
import openai

app = Flask(__name__)

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get('8868202823:AAGossWmb0df2fPY96ayuFLP5O5cQQYyHJY')
OPENAI_API_KEY = os.environ.get('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')

# --- TELEGRAM BOT FUNCTIONS ---

def get_market_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        history = ticker.history(period="1y")
        
        # Simplified data for AI
        data_str = f"Symbol: {symbol}\nPrice: {info.get('currentPrice', 'N/A')}\nMarket Cap: {info.get('marketCap', 'N/A')}\nPE Ratio: {info.get('trailingPE', 'N/A')}\n52W High: {info.get('fiftyTwoWeekHigh', 'N/A')}\n52W Low: {info.get('fiftyTwoWeekLow', 'N/A')}\nVolume: {info.get('volume', 'N/A')}\nHistory (Last 5 days): {history.tail(5)}"
        return data_str
    except Exception as e:
        return f"Error getting data for {symbol}: {str(e)}"

def ask_ai(data):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a crypto/stock analyst. Give a short, punchy analysis."},
                {"role": "user", "content": data}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

def handle_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get the symbol (e.g., "/check BTC")
    args = update.message.text.split()
    if len(args) < 2:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /check SYMBOL (e.g., /check BTC)")
        return

    symbol = args[1].upper()
    
    # Show typing indicator
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    # Get Data
    data = get_market_data(symbol)
    
    # Ask AI
    analysis = ask_ai(data)
    
    # Send Message
    message = f"📊 **{symbol} Analysis**\n\n{analysis}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode="Markdown")

# --- WEBHOOK FUNCTION ---

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    try:
        # Handle GET request from Pine Script
        if request.method == 'GET':
            symbol = request.args.get('symbol', 'BTC')
            direction = request.args.get('direction', 'WAIT')
            price = request.args.get('price', '0')
            time = request.args.get('time', 'Now')
        else:
            data = request.json
            symbol = data.get('symbol', 'BTC')
            direction = data.get('direction', 'WAIT')
            price = data.get('price', '0')
            time = data.get('time', 'Now')

        # Get Full Market Data
        full_data = get_market_data(symbol)
        
        # Ask AI for Analysis
        analysis = ask_ai(full_data)
        
        # Send to Telegram
        # NOTE: You need to store the Chat ID somewhere or use a specific one
        TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '123456789')
        
        message = f"🚨 **{symbol} Alert: {direction}**\n\n{analysis}"
        
        # Create a simple bot instance to send the message
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
        
        return jsonify({"status": "sent"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- MAIN STARTUP ---

def start_telegram_bot():
    print(f"Starting Telegram Bot with Token: {TELEGRAM_BOT_TOKEN}")
    
    # Build the application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add the command handler
    application.add_handler(CommandHandler("check", handle_check))
    
    # Start polling
    print("Telegram Bot is polling...")
    application.run_polling()

if __name__ == '__main__':
    import threading
    import os
    
    # 1. Start Telegram Bot in a background thread
    print("Starting Telegram Thread...")
    telegram_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    telegram_thread.start()
    
    # 2. Start Flask Web Server
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask Server on port {port}...")
    app.run(host='0.0.0.0', port=port)

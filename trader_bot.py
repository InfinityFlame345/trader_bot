import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import openai
import json
import yfinance as yf
from flask import Flask, request, jsonify
import threading

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8868202823:AAGossWmb0df2fPY96ayuFLP5O5cQQYyHJY"  # Get from @BotFather
OPENAI_API_KEY = "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"  # Paste your OpenAI Key here       

SYSTEM_PROMPT = """
You are an expert trader. Analyze the data and provide a trade setup.

**Strict Output Format:**
- Confidence Score: [0-100]%
- Direction: LONG / SHORT / WAIT
- Entry: [Exact Price]
- Stop Loss: [Exact Price]
- Take Profit: [Exact Price]
- Risk/Reward: [e.g., 1:2]
- Reasoning: [1 concise sentence]

**Calculation Rules:**
1. If Direction is LONG:
   - Stop Loss should be below the Entry (approx 1-2% away).
   - Take Profit must be EXACTLY 2x the distance of the Stop Loss. (TP = Entry + 2*(Entry - SL))
2. If Direction is SHORT:
   - Stop Loss should be above the Entry (approx 1-2% away).
   - Take Profit must be EXACTLY 2x the distance of the Stop Loss. (TP = Entry - 2*(SL - Entry))
3. If Confidence < 70%, Direction is WAIT.
4. All prices must be numbers (e.g., 4500.50).
"""

def get_market_data(symbol_input):
    try:
        TICKER_MAP = {
            "BTC": "BTC-USD", "BITCOIN": "BTC-USD",
            "ETH": "ETH-USD", "ETHEREUM": "ETH-USD",
            "SOL": "SOL-USD", "SOLANA": "SOL-USD",
            "GOLD": "GC=F", "GLD": "GLD",
            "OIL": "CL=F", "USO": "USO"
        }
        ticker_symbol = TICKER_MAP.get(symbol_input.upper(), symbol_input.upper())
        
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        if not info:
            return {"error": f"No data found for {ticker_symbol}", "symbol": symbol_input}
        
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
        high_24h = info.get('dayHigh') or info.get('regularMarketDayHigh')
        low_24h = info.get('dayLow') or info.get('regularMarketDayLow')
        volume = info.get('volume') or info.get('regularMarketVolume')
        
        if not current_price or not previous_close:
            return {"error": f"Missing price data for {ticker_symbol}", "symbol": symbol_input}
            
        change_pct = ((current_price - previous_close) / previous_close) * 100 if previous_close > 0 else 0
        mid_price = (high_24h + low_24h) / 2
        is_mss = current_price > mid_price
        is_sweep = (current_price > high_24h * 0.995) or (current_price < low_24h * 1.005)

        return {
            "price": float(current_price),
            "volume": float(volume) if volume else 0,
            "change_24h": float(change_pct),
            "mss_detected": is_mss,
            "liquidity_sweep": is_sweep,
            "symbol": symbol_input,
            "high_24h": float(high_24h) if high_24h else current_price,
            "low_24h": float(low_24h) if low_24h else current_price,
            "ticker_used": ticker_symbol
        }
        
    except Exception as e:
        return {"error": f"Yahoo Finance Error: {str(e)}", "symbol": symbol_input}

def ask_ai(data):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this trade setup:\n{json.dumps(data)}"}
            ],
            max_tokens=200,
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# --- TELEGRAM BOT SETUP ---
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /check BTC")
        return
    
    raw_symbol = context.args[0].upper()
    SYMBOL_MAP = {"BTC": "BTC", "BITCOIN": "BTC", "ETH": "ETH", "GOLD": "GOLD", "OIL": "OIL"}
    symbol_code = SYMBOL_MAP.get(raw_symbol, raw_symbol)
    
    await update.message.reply_text(f"🔍 Analyzing {symbol_code}...")
    
    try:
        data = get_market_data(symbol_code)
        if "error" in data:
            await update.message.reply_text(f"❌ Data Error: {data['error']}")
            return
        
        analysis = ask_ai(data)
        await update.message.reply_text(f"📊 **{symbol_code} Analysis:**\n\n{analysis}", parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Bot Error: {str(e)}")

# --- WEBHOOK SETUP (FOR TRADINGVIEW) ---
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # 1. Handle GET request (from the new Pine Script)
        if request.method == 'GET':
            symbol = request.args.get('symbol', 'BTC')
            direction = request.args.get('direction', 'WAIT')
            price = request.args.get('price', '0')
            time = request.args.get('time', 'Now')
        
        # 2. Handle POST request (fallback for old JSON format)
        else:
            data = request.json
            symbol = data.get('symbol', 'BTC')
            direction = data.get('direction', 'WAIT')
            price = data.get('price', '0')
            time = data.get('time', 'Now')

        # 3. Get Full Market Data
        full_data = get_market_data(symbol)
        
        if "error" in full_data:
            return jsonify({"status": "error", "message": full_data['error']})
        
        # 4. Ask AI for Analysis
        analysis = ask_ai(full_data)
        
        # 5. Send to Telegram
        # REPLACE THIS WITH YOUR ACTUAL CHAT ID
        TELEGRAM_CHAT_ID = "123456789" 
        
        message = f"🚨 **{symbol} Alert: {direction}**\n\n{analysis}"
        
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        try:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
            return jsonify({"status": "sent"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
       

def run_telegram_bot():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('check', check_command))
    print("Telegram Bot is polling...")
    application.run_polling()

def run_flask_app():
    print("Flask Webhook is listening on port 5000...")
    app.run(port=5000, debug=False)

if __name__ == '__main__':
    # Run Telegram Bot in a Thread
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.daemon = True
    telegram_thread.start()
    
    # Run Flask Webhook in Main Thread
    run_flask_app()

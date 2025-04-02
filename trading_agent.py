# halal_trading_agent.py — Enhanced AI Trading Flow with WhatsApp Feedback Tracking

import yfinance as yf
import pandas as pd
import ta
import json
from datetime import datetime
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from flask import Flask, request
import os

app = Flask(__name__)

# === SETTINGS ===
MARKETS = {
    "1": {  # Saudi Market
        "name": "Saudi Market",
        "tickers": ['2222.SR', '2030.SR', 'TADAWUL:1010']
    },
    "2": {  # US Market
        "name": "US Market",
        "tickers": ['AAPL', 'MSFT', 'NVDA']
    },
    "3": {  # Crypto Market
        "name": "Crypto Market",
        "tickers": ['BTC-USD', 'ETH-USD', 'SOL-USD']
    }
}
START_DATE = '2023-01-01'
END_DATE = '2024-12-31'

# === GATHER SIGNALS FOR EACH TICKER ===
def generate_signals(ticker):
    try:
        data = yf.download(ticker, start=START_DATE, end=END_DATE)
        data['rsi'] = ta.momentum.RSIIndicator(data['Close']).rsi()
        data['ema_20'] = ta.trend.EMAIndicator(data['Close'], window=20).ema_indicator()

        signals = []
        for i in range(1, len(data)):
            today = data.iloc[i]
            yesterday = data.iloc[i - 1]
            if today['rsi'] < 30 and today['Close'] > today['ema_20'] and yesterday['Close'] < yesterday['ema_20']:
                signals.append({
                    'date': today.name.strftime('%Y-%m-%d'),
                    'symbol': ticker,
                    'signal': 'BUY',
                    'price_in': round(today['Close'], 2),
                    'stop_loss': round(today['Close'] * 0.97, 2),
                    'target': round(today['Close'] * 1.05, 2)
                })
        return signals
    except Exception as e:
        print(f"⚠️ Error processing {ticker}: {e}")
        return []

# === PREVENT REPEATED NOTIFICATIONS ===
def already_notified_today():
    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        with open("last_notified.txt", "r") as f:
            return f.read().strip() == today_str
    except FileNotFoundError:
        return False

def mark_notified_today():
    today_str = datetime.now().strftime('%Y-%m-%d')
    with open("last_notified.txt", "w") as f:
        f.write(today_str)

# === SIMULATED USER SELECTION ===
selected_market = os.getenv("USER_SELECTED_MARKET", "1")
market_info = MARKETS.get(selected_market, MARKETS["1"])

# === COLLECT SIGNALS ===
all_signals = []
for ticker in market_info['tickers']:
    all_signals.extend(generate_signals(ticker))

if all_signals:
    print(f"\n📈 {market_info['name']} Signals")
    for s in all_signals:
        print(f"{s['date']} - {s['symbol']} - {s['signal']} | Entry: {s['price_in']} | Target: {s['target']} | SL: {s['stop_loss']}")
else:
    print(f"No signals generated for {market_info['name']}.")

# === SAVE SIGNAL TO LOG ===
log_file = 'signal_log.json'
try:
    with open(log_file, 'r') as f:
        log = json.load(f)
except FileNotFoundError:
        log = []

log.extend(all_signals)
with open(log_file, 'w') as f:
    json.dump(log, f, indent=2)

# === EXPORT TO EXCEL ===
df_export = pd.DataFrame(log)
df_export.to_excel('halal_trading_signals.xlsx', index=False)

# === EMAIL FUNCTION ===
def send_email():
    sender = os.getenv("EMAIL_FROM")
    password = os.getenv("EMAIL_PASS")
    recipient = os.getenv("EMAIL_TO")

    msg = EmailMessage()
    msg['Subject'] = '📈 Halal Trading Signal Report'
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content('Please find attached the latest trading signals. After completing your trades, please reply with "Profit" or "Loss" to track performance.')

    with open('halal_trading_signals.xlsx', 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='halal_trading_signals.xlsx')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("✅ Email sent.")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# === WHATSAPP FUNCTION ===
def send_whatsapp():
    account_sid = os.getenv('TWILIO_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)

    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            to=os.getenv('TWILIO_TO_NUMBER'),
            body=f'📊 {market_info["name"]} report is ready. Check your email. After trades complete, reply "Profit" or "Loss" to track performance.'
        )
        print("✅ WhatsApp message sent.")
    except Exception as e:
        print(f"❌ WhatsApp failed: {e}")

# === FEEDBACK LOGGING ===
def log_feedback(result):
    feedback_file = 'trade_feedback.json'
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        with open(feedback_file, 'r') as f:
            feedback_log = json.load(f)
    except FileNotFoundError:
        feedback_log = {}

    feedback_log[today] = feedback_log.get(today, []) + [result]

    with open(feedback_file, 'w') as f:
        json.dump(feedback_log, f, indent=2)

# === REPORTING FUNCTION ===
def generate_feedback_report():
    feedback_file = 'trade_feedback.json'
    try:
        with open(feedback_file, 'r') as f:
            feedback_log = json.load(f)
    except FileNotFoundError:
        return "No feedback data available."

    summary = {}
    for date, feedbacks in feedback_log.items():
        for fb in feedbacks:
            summary[fb] = summary.get(fb, 0) + 1

    total = sum(summary.values())
    report = "\n📊 Feedback Report:\n"
    for k, v in summary.items():
        percentage = (v / total) * 100 if total > 0 else 0
        report += f"{k}: {v} times ({percentage:.1f}%)\n"
    report += f"Total feedback received: {total}\n"
    return report

# === WHATSAPP FEEDBACK ENDPOINT ===
@app.route("/whatsapp", methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    if incoming_msg in ['profit', 'loss']:
        log_feedback(incoming_msg.capitalize())
        return "Feedback received. Thank you."
    elif incoming_msg == 'report':
        return generate_feedback_report()
    return "Reply with 'Profit', 'Loss', or 'Report' to help us improve."

# === TRIGGER NOTIFICATIONS ===
if all_signals and not already_notified_today():
    send_email()
    send_whatsapp()
    mark_notified_today()
else:
    print("No new signals or already notified today.")

# === Optional: Run report generator manually
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

# halal_trading_agent.py

import yfinance as yf
import pandas as pd
import ta
import json
from datetime import datetime
import smtplib
from email.message import EmailMessage
from twilio.rest import Client

# === SETTINGS ===
HALAL_TICKERS = ['AAPL', 'MSFT', 'TSLA', 'BTC-USD', '2222.SR']
SYMBOL = 'AAPL'
START_DATE = '2023-01-01'
END_DATE = '2024-12-31'

# === HALAL FILTER ===
if SYMBOL not in HALAL_TICKERS:
    print(f"❌ {SYMBOL} is not halal-approved. Exiting.")
    exit()
else:
    print(f"✅ {SYMBOL} is halal-approved.")

# === DOWNLOAD DATA ===
data = yf.download(SYMBOL, start=START_DATE, end=END_DATE)
data['rsi'] = ta.momentum.RSIIndicator(data['Close'].squeeze()).rsi()
data['ema_20'] = ta.trend.EMAIndicator(data['Close'].squeeze(), window=20).ema_indicator()

# === GENERATE SIGNALS ===
def generate_signals(df):
    signals = []
    for i in range(1, len(df)):
        today = df.iloc[i]
        yesterday = df.iloc[i - 1]

        try:
            if (
                float(today['rsi']) < 30 and
                float(today['Close']) > float(today['ema_20']) and
                float(yesterday['Close']) < float(yesterday['ema_20'])
            ):
                signals.append({
                    'date': today.name.strftime('%Y-%m-%d'),
                    'symbol': SYMBOL,
                    'signal': 'BUY',
                    'price_in': round(float(today['Close']), 2),
                    'stop_loss': round(float(today['Close']) * 0.97, 2),
                    'target': round(float(today['Close']) * 1.05, 2)
                })
        except Exception as e:
            print(f"⚠️ Error on row {i}: {e}")
    return signals

signals = generate_signals(data)

if not signals:
    print("No signals generated.")
else:
    last = signals[-1]
    print("\n📈 Signal:")
    print(f"{last['date']} - {last['symbol']} - {last['signal']}")
    print(f"Price-In: {last['price_in']}, Target: {last['target']}, Stop-Loss: {last['stop_loss']}")

# === SAVE SIGNAL TO LOG ===
log_file = 'signal_log.json'
try:
    with open(log_file, 'r') as f:
        log = json.load(f)
except FileNotFoundError:
    log = []

log.extend(signals)
with open(log_file, 'w') as f:
    json.dump(log, f, indent=2)

# === EXPORT TO EXCEL ===
df_export = pd.DataFrame(log)
df_export.to_excel('halal_trading_signals.xlsx', index=False)

# === EMAIL FUNCTION ===
import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content

# === EMAIL FUNCTION WITH SENDGRID ===
def send_email():
    api_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('EMAIL_FROM')
    to_email = os.getenv('EMAIL_TO')

    sg = sendgrid.SendGridAPIClient(api_key=api_key)

    message = Mail(
        from_email=Email(from_email),
        to_emails=To(to_email),
        subject='📈 Halal Trading Signal Report',
        plain_text_content='Please find attached the latest halal trading signals.'
    )

    try:
        # Attach Excel file
        with open('halal_trading_signals.xlsx', 'rb') as f:
            data = f.read()
            import base64
            encoded_file = base64.b64encode(data).decode()

        from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
        attachment = Attachment()
        attachment.file_content = FileContent(encoded_file)
        attachment.file_type = FileType('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        attachment.file_name = FileName('halal_trading_signals.xlsx')
        attachment.disposition = Disposition('attachment')
        message.attachment = attachment

        sg.send(message)
        print("✅ Email sent successfully via SendGrid.")

    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# === WHATSAPP FUNCTION ===
def send_whatsapp():
    account_sid = 'your_twilio_sid'
    auth_token = 'your_twilio_token'
    client = Client(account_sid, auth_token)

    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            to='whatsapp:+your_verified_number',
            body='📊 Halal trading report is ready. Check your email for the Excel file.'
        )
        print("✅ WhatsApp message sent.")
    except Exception as e:
        print(f"❌ WhatsApp failed: {e}")

# === TRIGGER NOTIFICATIONS ===
send_email()
send_whatsapp()

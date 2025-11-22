from flask import Flask, request
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TWELVE_API_KEY = "YOUR_TWELVEDATA_API_KEY"
BASE_TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

symbols = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "XAUUSD": "XAU/USD",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD"
}

def fetch(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&apikey={TWELVE_API_KEY}&outputsize=50"
    r = requests.get(url).json()
    if "values" not in r:
        return None
    df = pd.DataFrame(r["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    df["close"] = df["close"].astype(float)
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def next_candle():
    now = datetime.utcnow()
    mins = 5 - (now.minute % 5)
    entry = now + timedelta(minutes=mins)
    entry = entry.replace(second=0, microsecond=0)
    left = int((entry - now).total_seconds())
    return entry.strftime("%H:%M:%S"), left

def analyze(df):
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])

    last = df.iloc[-1]
    prev = df.iloc[-2]

    up = last["close"] > last["ema200"]
    dn = last["close"] < last["ema200"]

    r = last["rsi"]
    p_r = prev["rsi"]

    entry_time, seconds_left = next_candle()

    if up and 20 < r < 45 and r > p_r:
        return f"📈 CALL Signal\nEntry: {entry_time} UTC\nSeconds left: {seconds_left}"
    if dn and 55 < r < 80 and r < p_r:
        return f"📉 PUT Signal\nEntry: {entry_time} UTC\nSeconds left: {seconds_left}"

    return None

@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if text == "/start":
            requests.post(BASE_TELEGRAM_URL, json={"chat_id": chat_id, "text": "Bot active!"})

        if text == "/signal":
            for k, v in symbols.items():
                df = fetch(v)
                if df is None:
                    continue
                sig = analyze(df)
                if sig:
                    requests.post(BASE_TELEGRAM_URL, json={"chat_id": chat_id, "text": f"{k}\n{sig}"})

    return "OK"

@app.route("/", methods=["GET"])
def home():
    return "Bot Running"

if __name__ == "__main__":
    app.run()

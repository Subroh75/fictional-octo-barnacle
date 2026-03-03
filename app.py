import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
import time

st.set_page_config(page_title="Nifty 500 Alpha Ignition", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("⚡ Momentum Controls")
risk_amt = st.sidebar.number_input("Risk per Trade (INR)", value=1000)
scan_num = st.sidebar.slider("Scan Depth", 10, 500, 100)

@st.cache_data(ttl=3600)
def fetch_complete_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except Exception:
        symbols = ["RELIANCE.NS", "TCS.NS"]
        industries = {}

    all_data = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(symbols[:limit]):
        progress.progress((i + 1) / limit)
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 50: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            
            # Technicals
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi_val = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1]))) if loss.iloc[-1] != 0 else 100
            
            # Momentum/NR7
            df['Range'] = df['High'] - df['Low']
            is_nr7 = df['Range'].iloc[-1] == df['Range'].iloc[-7:].min()
            recent_high_20 = df['High'].iloc[-21:-1].max()
            recent_low_20 = df['Low'].iloc[-21:-1].min()
            avg_vol = df['Volume'].iloc[-21:-1].mean()
            curr_vol = df['Volume'].iloc[-1]
            
            # Signals
            status = "Neutral"
            if cp > recent_high_20 and curr_vol > (avg_vol * 1.5):
                status = "🚀 IGNITION" if is_nr7 else "⚡ BURST"
            elif cp > ma20 > ma50 > ma200:
                status = "📈 TREND UP"
            elif cp < recent_low_20 and curr_vol > (avg_vol * 1.5):
                status = "📉 BREAKDOWN"
            elif cp < ma20 < ma50 < ma200:
                status = "🔻 STRONG SELL"

            # Risk
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            is

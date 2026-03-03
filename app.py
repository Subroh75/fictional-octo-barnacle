import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
import time

st.set_page_config(page_title="Nifty 500 Alpha Ignition", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("⚡ Momentum & Breakdown")
risk_amt = st.sidebar.number_input("Risk per Trade (INR)", value=1000)
scan_num = st.sidebar.slider("Scan Depth", 10, 500, 100)
chase_limit = st.sidebar.slider("Max Day % (Avoid Chasing)", 1.0, 10.0, 5.0)

@st.cache_data(ttl=3600)
def fetch_complete_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS"]
        industries = {}

    all_data = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(symbols[:limit]):
        progress.progress((i + 1) / limit)
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 50: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # --- Basic Metrics ---
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            day_change = ((cp - prev_cp) / prev_cp) * 100
            
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # --- RSI Calculation ---
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            # --- Momentum & NR7 Logic ---
            df['Range'] = df['High'] - df['Low']
            is_nr7 = df['Range'].iloc[-1] == df['Range'].iloc[-7:].min()
            recent_high_20 = df['High'].iloc[-21:-1].max()
            recent_low_20 = df['Low'].iloc[-21:-1].min()
            avg_vol = df['Volume'].iloc[-21:-1].mean()
            curr_vol = df['Volume'].iloc[-1]
            
            # --- Signal Logic ---
            status = "Neutral"
            # Bullish Signals
            if cp > recent_high_20 and curr_vol > (avg_vol * 1.5):
                status = "🚀 IGNITION" if is_nr7 else "⚡ BURST"
            elif cp > ma20 > ma50 > ma200:
                status = "📈 TREND UP"
            # Bearish Signals (Strong Sell)
            elif cp < recent_low_20 and curr_vol > (avg_vol * 1.5):
                status = "📉 BREAKDOWN"
            elif cp < ma20 < ma50 < ma200:
                status = "🔻 STRONG SELL"

            # --- Risk Management ---
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # SL logic: Below CP for Buys, Above CP for Sells
            is_bearish = "SELL" in status or "BREAKDOWN" in status
            sl = cp + (1.5 * atr) if is_bearish else cp - (1.5 * atr)
            qty = int(risk_amt / abs(cp - sl)) if abs(cp - sl) > 0 else 0

            all_data.append({
                "Ticker": ticker,
                "Industry": industries.get(ticker, "N/A"),
                "Price": round(cp, 2),
                "Day %": round(day_change, 2),
                "RSI": round(rsi, 2),
                "Signal": status,
                "Action": "⚠️ OVEREXTENDED" if (day_change > chase_limit and not is_bearish) else "✅ TRADE ZONE",
                "Vol Surge": round(curr_vol/avg_vol, 1),
                "Stop Loss": round(sl, 2),
                "Qty": qty,
                "52W High": round(df['High'].max(), 2)
            })
            time.sleep(0.05)
        except: continue
    return pd.DataFrame(all_data)

# --- APP LAYOUT ---
st.title("🏹 Alpha Ignition Suite (Long & Short)")

if st.button("🔍 Scan Nifty 500"):
    st.session_state['data'] = fetch_complete_data(scan_num)

if 'data' in st.session_state:
    df_res = st.session_state['data']
    
    t1, t2, t3 = st.tabs(["⚡ Momentum (Long)", "📉 Breakdown (Short)", "📊 Sector Pulse"])

    with t1:
        st.subheader("High-Velocity Upside Bursts")
        long_df = df_res[df_res['Signal'].str.contains("IGNITION|BURST|TREND UP", na=False)]
        st.dataframe(long_df.sort_values(by="Vol Surge", ascending=False), use_container_width=True)

    with t2:
        st.subheader("High-Velocity Downside Crashes")
        short_df = df_res[df_res['Signal'].str.contains("BREAKDOWN|SELL", na=False)]
        st.dataframe(short_df.

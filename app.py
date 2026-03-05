import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
from datetime import datetime
import time

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = pd.DataFrame(columns=['Date', 'Ticker', 'Qty', 'Entry', 'SL', 'Target', 'Trader'])

# --- 2. MARKET REGIME ---
@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        cp = nifty['Close'].iloc[-1]
        ma200 = nifty['Close'].rolling(200).mean().iloc[-1]
        adr = (nifty['High'] - nifty['Low']).rolling(20).mean().iloc[-1] / cp * 100
        if cp > ma200:
            return ("🐂 BULLISH", "green", round(adr, 2))
        return ("🐻 BEARISH", "red", round(adr, 2))
    except: return ("UNKNOWN", "grey", 0)

# --- 3. MASTER SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except: symbols, industries = ["RELIANCE.NS", "TCS.NS"], {}

    all_data = []
    prog = st.progress(0)
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            v_surge = float(df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1])
            
            # Breakout Logic
            h21 = float(df['High'].iloc[-22:-1].max())
            l21 = float(df['Low'].iloc[-22:-1].min())
            
            # Quant Scoring
            score = 0
            std10 = df['Close'].pct_change().rolling(10).std().iloc[-1]
            std100 = df['Close'].pct_change().rolling(100).std().iloc[-1]
            if (std10/std100) < 0.8: score += 1
            if cp > h21: score += 1
            if v_surge > 2.0: score += 1
            
            # Signal Assignment
            sig = "Neutral"
            if cp > h21 and v_surge > 1.1: sig = "🚀 BREAKOUT"
            elif cp < l21 and v_surge > 1.1: sig = "📉 BREAKDOWN"

            # MA Status
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            trend = "Bull" if cp > m20 > m50 > m200 else "Bear" if cp < m20 < m50 < m200 else "Flat"

            all_data.append({
                "Ticker": t, "Sector": industries.get(t, "N/A"), "Score": int(score), 
                "Price": round(cp, 2), "Signal": sig, "Surge": round(v_surge, 1),
                "MA_Trend": trend, "H21": round(h21, 2), "L21": round(l21, 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. UI ---
reg, col, vol = get_market_regime()
st.sidebar.markdown(f"### Market: <span style='color:{col}'>{reg}</span>", unsafe_allow_html=True)
active_p = st.sidebar.selectbox("Partner", ["Partner A", "Partner B"])

if st.button("🚀 Execute Global Scan"):
    res = run_master_scan(st.sidebar.slider("Depth", 50, 500, 100))
    if not res.empty:
        st.session_state['scan_results'] = res

if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
    data = st.session_state['scan_results']
    tabs = st.tabs(["🎯 Quant Picks", "💥 Breakouts", "📉 Breakdowns", "📈 MA Trends", "📊 Portfolio"])

    with tabs[0]:
        st.dataframe(data[data['Score'] >= 2].sort_values("Score", ascending=False), use_container_width=True)

    with tabs[1]:
        # Filter safely
        st.success("21-Day High Breakouts")
        st.dataframe(data[data['Signal'] == "🚀 BREAKOUT"][['Ticker', 'Price', 'Surge', 'H21']], use_container_width=True)
        

    with tabs[2]:
        st.error("21-Day Low Breakdowns")
        st.dataframe(data[data['Signal'] == "📉 BREAKDOWN"][['Ticker', 'Price', 'Surge', 'L21']], use_container_width=True)

    with tabs[3]:
        st.info("Moving Average Alignment (20/50/200)")
        st.dataframe(data[['Ticker', 'Price', 'MA_Trend', 'Sector']], use_container_width=True)
        

    with tabs[4]:
        st.write("Current Holdings and P&L Tracking...")
        st.dataframe(st.session_state['portfolio'], use_container_width=True)

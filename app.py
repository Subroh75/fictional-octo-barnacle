import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
from datetime import datetime, timedelta
import time

# --- 1. CONFIG & SESSION INITIALIZATION ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = pd.DataFrame(columns=[
        'Entry_Date', 'Ticker', 'Qty', 'Entry_Price', 'SL', 'Target', 'Trader'
    ])

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. MARKET REGIME ENGINE ---
@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        cp = nifty['Close'].iloc[-1]
        ma200 = nifty['Close'].rolling(200).mean().iloc[-1]
        adr = (nifty['High'] - nifty['Low']).rolling(20).mean().iloc[-1] / cp * 100
        
        if cp > ma200:
            return ("🐂 BULLISH", "green", round(adr, 2)) if adr < 1.5 else ("⚠️ VOLATILE BULL", "orange", round(adr, 2))
        return ("🐻 BEARISH", "red", round(adr, 2))
    except: return ("UNKNOWN", "grey", 0)

# --- 3. QUANT SCANNER ENGINE ---
@st.cache_data(ttl=3600)
def run_quant_scan(limit):
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

            cp, prev_cp = df['Close'].iloc[-1], df['Close'].iloc[-2]
            v_surge = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
            
            # QUANT SCORING
            score = 0
            # A. VCP Squeeze
            std10 = df['Close'].pct_change().rolling(10).std().iloc[-1]
            std100 = df['Close'].pct_change().rolling(100).std().iloc[-1]
            if (std10/std100) < 0.8: score += 1
            # B. RSI-2
            delta = df['Close'].diff()
            g, l = delta.where(delta > 0, 0).rolling(2).mean(), -delta.where(delta < 0, 0).rolling(2).mean()
            rsi2 = 100 - (100 / (1 + (g.iloc[-1] / l.iloc[-1]))) if l.iloc[-1] != 0 else 100
            if rsi2 < 20: score += 1
            # C. Volume & Breakout
            if v_surge > 2.0: score += 1
            if cp > df['High'].iloc[-21:-1].max(): score += 1

            tr = pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]

            all_data.append({
                "Ticker": t, "Sector": industries.get(t, "N/A"), "Score": int(score), 
                "Price": round(cp, 2), "RSI2": round(rsi2, 1), "Surge": round(v_surge, 1), 
                "SL": round(cp - (1.5 * atr), 2), "Target": round(cp * 1.07, 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. UI HEADER ---
reg, col, vol = get_market_regime()
st.title("🏹 Alpha Quant Terminal")
st.sidebar.markdown(f"### Regime: <span style='color:{col}'>{reg}</span>", unsafe_allow_html=True)
st.sidebar.write(f"Market Volatility: {vol}%")

active_partner = st.sidebar.selectbox("Active Partner", ["Partner A", "Partner B"])

menu = st.tabs(["🔍 Quant Scanner", "📊 Portfolio Tracker", "🧪 Strategy Backtest"])

# --- TAB 1: SCANNER ---
with menu[0]:
    c1, c2 = st.columns([1, 4])
    with c1:
        depth = st.number_input("Scan Depth", 50, 500, 100)
        if st.button("🚀 Run Market Scan"):
            st.session_state['scan_results'] = run_quant_scan(depth)
    
    if not st.session_state['scan_results'].empty:
        df_scan = st.session_state['scan_results']
        high_score = df_scan[df_scan['Score'] >= 2].sort_values("Score", ascending=False)
        
        st.subheader("🎯 High Conviction Signals (Score 2+)")
        st.dataframe(high_score, use_container_width=True)
        
        st.download_button("📥 Export CSV", high_score.to_csv(index=False), "quant_scan.csv")
        
        st.divider()
        sel_ticker = st.selectbox("Detailed Chart Analysis:", df_scan['Ticker'].tolist())
        if sel_ticker:
            cdf = yf.download(sel_ticker, period="6mo", progress=False)
            if isinstance(cdf.columns, pd.MultiIndex): cdf.columns = cdf.columns.get_level_values(0)

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
from datetime import datetime

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

# --- 3. THE MASTER SCANNER ENGINE ---
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

            # Core Data
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = df['Volume'].iloc[-1] / vol_avg
            
            # Highs/Lows (21 Days = 1 Trading Month)
            h21 = df['High'].iloc[-22:-1].max()
            l21 = df['Low'].iloc[-22:-1].min()
            
            # MA Calculations
            ma20, ma50, ma200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # Quant Score
            score = 0
            std10, std100 = df['Close'].pct_change().rolling(10).std().iloc[-1], df['Close'].pct_change().rolling(100).std().iloc[-1]
            if (std10/std100) < 0.8: score += 1
            if cp > h21: score += 1
            if v_surge > 2.0: score += 1
            
            # Signal Classification
            move = "Neutral"
            if cp > h21 and v_surge > 1.2: move = "🚀 BREAKOUT"
            elif cp < l21 and v_surge > 1.2: move = "📉 BREAKDOWN"

            all_data.append({
                "Ticker": t, "Sector": industries.get(t, "N/A"), "Score": int(score), 
                "Price": round(cp, 2), "Signal": move, "Surge": round(v_surge, 1),
                "MA_Trend": "Bull" if cp > ma20 > ma50 > ma200 else "Bear" if cp < ma20 < ma50 < ma200 else "Flat",
                "H21": round(h21, 2), "L21": round(l21, 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. UI ---
reg, col, vol = get_market_regime()
st.title("🏹 Alpha Quant Terminal")
st.sidebar.markdown(f"### Regime: <span style='color:{col}'>{reg}</span>", unsafe_allow_html=True)

if st.button("🚀 Execute Global Scan"):
    st.session_state['scan_results'] = run_master_scan(st.sidebar.slider("Scan Depth", 50, 500, 100))

if not st.session_state['scan_results'].empty:
    data = st.session_state['scan_results']
    tabs = st.tabs(["🎯 Quant Picks", "💥 Breakout/Down", "📈 MA Screener", "📊 Portfolio"])

    with tabs[0]:
        st.subheader("Multi-Factor High Score (Score 2+)")
        st.dataframe(data[data['Score'] >= 2].sort_values("Score", ascending=False), use_container_width=True)

    with tabs[1]:
        st.subheader("Price Action Extremes (21-Day)")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            st.success("**🚀 Breakout Candidates**")
            st.dataframe(data[data['Signal'] == "🚀 BREAKOUT"][['Ticker', 'Price', 'Surge', 'H21']], use_container_width=True)
        with b_col2:
            st.error("**📉 Breakdown Candidates**")
            st.dataframe(data[data['Signal'] == "📉 BREAKDOWN"][['Ticker', 'Price', 'Surge', 'L21']], use_container_width=True)

    with tabs[2]:
        st.subheader("Trend Alignment")
        st.dataframe(data[['Ticker', 'Price', 'MA_Trend', 'Sector']], use_container_width=True)

    with tabs[3]:
        st.subheader("Active Trades")
        st.write("Logged Trades appear here for monitoring...")
        st.dataframe(st.session_state['portfolio'], use_container_width=True)

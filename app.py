import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# --- 1. CONFIG & SESSION STATE ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. FUNCTION DEFINITIONS ---

@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        cp = nifty['Close'].iloc[-1]
        ma200 = nifty['Close'].rolling(200).mean().iloc[-1]
        return ("🐂 BULLISH", "green") if cp > ma200 else ("🐻 BEARISH", "red")
    except: return ("UNKNOWN", "grey")

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols, sector_map = ["RELIANCE.NS", "TCS.NS"], {}

    all_data = []
    prog = st.progress(0, text="Analyzing Trends...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20 = float(df['Close'].rolling(20).mean().iloc[-1])
            m50 = float(df['Close'].rolling(50).mean().iloc[-1])
            m200 = float(df['Close'].rolling(200).mean().iloc[-1])
            
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            h21 = float(df['High'].iloc[-22:-1].max())

            # Recommendation Logic
            if cp > m20 > m50 > m200: action = "🟢 STRONG BUY"
            elif cp > m50 > m200: action = "🟡 HOLD"
            elif cp < m200: action = "🔴 AVOID"
            else: action = "⚪ NEUTRAL"

            # Momentum Score
            score = sum([v_surge > 2.0, cp > h21, m20 > m50])

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA20": round(m20, 2), "MA50": round(m50, 2), "MA200": round(m200, 2),
                "Action": action, "Surge": round(v_surge, 1), "Score": score
            })
        except: continue
        
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI RENDER ---
reg_name, reg_color = get_market_regime()
st.sidebar.title("🛠️ Alpha Dashboard")
st.sidebar.markdown(f"### Market: <span style='color:{reg_color}'>{reg_name}</span>", unsafe_allow_html=True)

depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
if st.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(depth)
    if not res.empty:
        st.session_state['scan_results'] = res
        st.rerun()

# --- 4. TABS ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2, t3 = st.tabs(["🎯 Momentum Picks", "📈 Trend Action (MA Details)", "🔥 Volume Shockers"])

    with t1:
        st.subheader("Top Ranked Individual Stocks")
        picks = df[df['Action'] != "🔴 AVOID"].sort_values(by=["Score", "Surge"], ascending=False)
        st.dataframe(picks, use_container_width=True)

    with t2:
        st.subheader("Moving Average Signal Details")
        st.info("Strategy: Only enter when Price is above all 3 MAs for high-probability swings.")
        
        # Displaying the raw MA values and the Action Signal
        st.dataframe(df[['Ticker', 'Price', 'MA20', 'MA50', 'MA200', 'Action']].sort_values("Action"), use_container_width=True)

    with t3:
        st.subheader("⚠️ Institutional Volume Shockers")
        shockers = df[df['Surge'] >= 3.0].sort_values(by="Surge", ascending=False)
        st.dataframe(shockers, use_container_width=True)
else:
    st.info("Scanner Ready. Execute scan to see Moving Average signals.")

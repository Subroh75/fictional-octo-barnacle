import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
from datetime import datetime

# --- 1. CONFIG & SESSION STATE ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = pd.DataFrame(columns=['Date', 'Ticker', 'Qty', 'Entry', 'SL', 'Trader'])

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. MARKET REGIME ENGINE ---
@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        cp = nifty['Close'].iloc[-1]
        ma200 = nifty['Close'].rolling(200).mean().iloc[-1]
        if cp > ma200:
            return ("🐂 BULLISH", "green")
        return ("🐻 BEARISH", "red")
    except:
        return ("UNKNOWN", "grey")

# --- 3. MASTER SCANNER ENGINE ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]

    all_data = []
    prog = st.progress(0)
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Technical Variables
            cp = float(df['Close'].iloc[-1])
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            m50 = df['Close'].rolling(50).mean().iloc[-1]
            m200 = df['Close'].rolling(200).mean().iloc[-1]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            
            h21 = float(df['High'].iloc[-22:-1].max())
            l21 = float(df['Low'].iloc[-22:-1].min())

            # A. MA Action Logic (Buy/Hold/Avoid)
            if cp > m20 > m50 > m200:
                action = "🟢 STRONG BUY"
            elif cp > m50 > m200:
                action = "🟡 HOLD / WATCH"
            elif cp < m200:
                action = "🔴 AVOID / SELL"
            else:
                action = "⚪ NEUTRAL"
            
            # B. Breakout/Down Logic
            signal = "Neutral"
            if cp > h21 and v_surge > 1.2:
                signal = "🚀 BREAKOUT"
            elif cp < l21 and v_surge > 1.2:
                signal = "📉 BREAKDOWN"

            # C. Quant Scoring (Volume + Price Strength)
            score = 0
            if v_surge > 2.0: score += 1
            if cp > h21: score += 1
            if m20 > m50: score += 1

            all_data.append({
                "Ticker": t,
                "Price": round(cp, 2),
                "Action": action,
                "Signal": signal,
                "Surge": round(v_surge, 1),
                "Score": score,
                "H21": round(h21, 2),
                "L21": round(l21, 2)
            })
        except:
            continue
            
    return pd.DataFrame(all_data)

# --- 4. MAIN USER INTERFACE ---
reg_name, reg_color = get_market_regime()

st.sidebar.title("🛠️ Quant Settings")
st.sidebar.markdown(f"### Market Regime: <span style='color:{reg_color}'>{reg_name}</span>", unsafe_allow_html=True)
active_partner = st.sidebar.selectbox("Active Partner", ["Partner A", "Partner B"])
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)

if st.button("🚀 EXECUTE GLOBAL SCAN"):
    results = run_master_scan(scan_depth)
    if not results.empty:
        st.session_state['scan_results'] = results

# Display Tabs if Data Exists
if not st.session_state['scan_results'].empty:
    data = st.session_state['scan_results']
    t1, t2, t3, t4 = st

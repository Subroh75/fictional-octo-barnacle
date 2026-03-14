import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
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
        
        if cp > ma200:
            return ("🐂 BULLISH", "green")
        return ("🐻 BEARISH", "red")
    except:
        return ("UNKNOWN", "grey")

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

            cp = float(df['Close'].iloc[-1])
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            m50 = df['Close'].rolling(50).mean().iloc[-1]
            m200 = df['Close'].rolling(200).mean().iloc[-1]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            
            h21 = float(df['High'].iloc[-22:-1].max())
            l21 = float(df['Low'].iloc[-22:-1].min())

            # Recommendation Logic (Buy/Hold/Avoid)
            if cp > m20 > m50 > m200:
                action = "🟢 STRONG BUY"
            elif cp > m50 > m200:
                action = "🟡 HOLD / WATCH"
            elif cp < m200:
                action = "🔴 AVOID / SELL"
            else:
                action = "⚪ NEUTRAL"
            
            # Breakout Signal
            sig = "Neutral"
            if cp > h21 and v_surge > 1.2:
                sig = "🚀 BREAKOUT"
            elif cp < l21 and v_surge > 1.2:
                sig = "📉 BREAKDOWN"

            # Momentum Scoring (The Top Rank Logic)
            score = 0
            if v_surge > 2.0: score += 1      # Institutional Fuel
            if cp > h21: score += 1           # Relative Strength
            if m20 > m50: score += 1          # Acceleration

            all_data.append({
                "Ticker": t, "Price": round(cp, 2), "Action": action,
                "Signal": sig, "Surge": round(v_surge, 1), "Score": score,
                "H21": round(h21, 2), "L21": round(l21, 2)
            })
        except:
            continue
    return pd.DataFrame(all_data)

# --- 3. MAIN USER INTERFACE ---

reg_name, reg_color = get_market_regime()

st.sidebar.title("🛠️ Quant Settings")
st.sidebar.markdown(f"### Market Regime: <span style='color:{reg_color}'>{reg_name}</span>", unsafe_allow_html=True)
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)

if st.button("🚀 EXECUTE GLOBAL SCAN"):
    results = run_master_scan(scan_depth)
    if not results.empty:
        st.session_state['scan_results'] = results

if not st.session_state['scan_results'].empty:
    data = st.session_state['scan_results']
    t1, t2, t3 = st.tabs(["🎯 Top Momentum Picks", "📈 Trend Action", "💥 Breakouts/Downs"])

    with t1:
        st.subheader("Highest Probability Momentum Setups")
        # Ranking Logic: High Score -> Volume Surge -> Strong Buy
        picks = data[data['Action'].isin(["🟢 STRONG BUY", "🟡 HOLD / WATCH"])]
        picks = picks.sort_values(by=["Score", "Surge"], ascending=[False, False])
        st.dataframe(picks, use_container_width=True)

    with t2:
        st.subheader("Trend Alignment Status")
        
        st.dataframe(data[['Ticker', 'Price', 'Action', 'Score']].sort_values("Action"), use_container_width=True)

    with t3:
        st.subheader("21-Day Price Action Extremes")
        
        st.dataframe(data[data['Signal'] != "Neutral"][['Ticker', 'Price', 'Signal', 'Surge', 'H21', 'L21']], use_container_width=True)

else:
    st.info("Scanner Ready. Adjust depth and click 'Execute Global Scan'.")

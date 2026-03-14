import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# --- 1. CONFIG & SESSION STATE ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

# Pre-initialize columns to avoid "KeyError" or "Non-responsive" tabs
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame(columns=[
        "Ticker", "Sector", "Price", "1W %", "1M %", "Action", "Surge", "Score"
    ])

# --- 2. FUNCTION DEFINITIONS ---

@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        # Fix for yfinance MultiIndex columns
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
        symbols, sector_map = ["RELIANCE.NS", "TCS.NS", "INFY.NS"], {}

    all_data = []
    prog = st.progress(0, text="Scanning Market Momentum...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Shortened period to '6mo' for faster fetching
            df = yf.download(t, period="6mo", progress=False)
            if df.empty or len(df) < 22: continue
            
            # CRITICAL FIX: Flatten multi-index columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            # Use .values[0] or float() to ensure we have numbers, not series
            m20 = float(df['Close'].rolling(20).mean().iloc[-1])
            m50 = float(df['Close'].rolling(50).mean().iloc[-1])
            m200 = float(df['Close'].rolling(200).mean().iloc[-1]) if len(df) >= 200 else m50
            
            perf_1w = ((cp / df['Close'].iloc[-5]) - 1) * 100
            perf_1m = ((cp / df['Close'].iloc[-21]) - 1) * 100
            
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            h21 = float(df['High'].iloc[-22:-1].max())

            # Action Logic
            if cp > m20 > m50: action = "🟢 STRONG BUY"
            elif cp > m50: action = "🟡 HOLD"
            else: action = "🔴 AVOID"
            
            # Momentum Score (0-3)
            score = 0
            if v_surge > 1.5: score += 1
            if cp > h21: score += 1
            if m20 > m50: score += 1

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "1W %": round(float(perf_1w), 2), "1M %": round(float(perf_1m), 2), 
                "Action": action, "Surge": round(v_surge, 1), "Score": score
            })
        except: continue
        
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI RENDER ---
reg_name, reg_color = get_market_regime()
st.sidebar.title("🛠️ Alpha Dashboard")
st.sidebar.markdown(f"### Market: <span style='color:{reg_color}'>{reg_name}</span>", unsafe_allow_html=True)

if not st.session_state['scan_results'].empty:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏆 Top Sectors (1W)")
    lb = st.session_state['scan_results'].groupby('Sector')['1W %'].mean().sort_values(ascending=False).head(5)
    for sec, val in lb.items():
        st.sidebar.write(f"**{sec}**: `{val:.2f}%`")

depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
if st.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(depth)
    if not res.empty:
        st.session_state['scan_results'] = res
        st.rerun()

# --- 4. TABS ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2, t3 = st.tabs(["🌍 Birds-Eye View", "🎯 Momentum Picks", "🔥 Volume Shockers"])

    with t1:
        st.subheader("Market Map")
        
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['1W %']),
                         color='1W %', color_continuous_scale='RdYlGn',
                         range_color=[-7, 7], hover_data=['Price', 'Action'])
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Momentum Leaderboard")
        # Ensure we are not sorting an empty slice
        picks = df[df['Action'] != "🔴 AVOID"]
        if not picks.empty:
            st.dataframe(picks.sort_values(by=["Score", "Surge"], ascending=False), use_container_width=True)
        else:
            st.warning("No Strong Buy/Hold candidates found in this scan.")

    with t3:
        st.subheader("Institutional Activity (>3x Volume)")
        shockers = df[df['Surge'] >= 3.0].sort_values(by="Surge", ascending=False)
        st.dataframe(shockers, use_container_width=True)
else:
    st.info("Scanner Ready. Click 'Execute Global Scan' to populate Momentum Picks.")

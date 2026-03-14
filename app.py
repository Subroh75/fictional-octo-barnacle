import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# --- 1. CONFIG & SESSION STATE ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

# Initialize session state with empty but structured DataFrame to prevent KeyErrors
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame(columns=[
        "Ticker", "Sector", "Price", "1W %", "1M %", "Action", "Surge", "Score"
    ])

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
    prog = st.progress(0)
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="6mo", progress=False)
            if df.empty or len(df) < 60: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            perf_1w = ((cp / df['Close'].iloc[-5]) - 1) * 100
            perf_1m = ((cp / df['Close'].iloc[-21]) - 1) * 100
            
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            h21 = float(df['High'].iloc[-22:-1].max())

            action = "🟢 STRONG BUY" if cp > m20 > m50 > m200 else "🟡 HOLD" if cp > m50 > m200 else "🔴 AVOID"
            score = sum([v_surge > 2.0, cp > h21, m20 > m50])

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "1W %": round(perf_1w, 2), "1M %": round(perf_1m, 2), "Action": action,
                "Surge": round(v_surge, 1), "Score": score
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 3. UI & SIDEBAR ---
reg_name, reg_color = get_market_regime()
st.sidebar.title("🛠️ Alpha Dashboard")
st.sidebar.markdown(f"### Market: <span style='color:{reg_color}'>{reg_name}</span>", unsafe_allow_html=True)

# Safety Fix: Only show leaderboard if Sector column exists and has data
if not st.session_state['scan_results'].empty and 'Sector' in st.session_state['scan_results'].columns:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏆 Top Sectors (1W)")
    try:
        leaderboard = st.session_state['scan_results'].groupby('Sector')['1W %'].mean().sort_values(ascending=False).head(5)
        for sec, val in leaderboard.items():
            st.sidebar.write(f"**{sec}**: `{val:.2f}%`")
    except:
        pass

depth = st.sidebar.slider("Scan Depth", 50, 500, 150)
if st.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(depth)
    if not res.empty:
        st.session_state['scan_results'] = res
        st.rerun() # Refresh to update sidebar leaderboard

# --- 4. TABS ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2, t3, t4 = st.tabs(["🌍 Birds-Eye View", "🎯 Momentum Picks", "💥 Sector Deep-Dive", "🔥 Volume Shockers"])

    with t1:
        st.subheader("Market Map")
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['1W %']),
                         color='1W %', color_continuous_scale='RdYlGn',
                         range_color=[-8, 8], hover_data=['Price', 'Action'])
        st.plotly_chart(fig, use_container_width=True)
        

    with t2:
        st.subheader("Top Ranked Individual Stocks")
        picks = df[df['Action'] != "🔴 AVOID"].sort_values(by=["Score", "1W %"], ascending=False)
        st.dataframe(picks, use_container_width=True)

    with t3:
        st.subheader("Sector-wise Strength")
        sec_df = df.groupby('Sector').agg({'1W %': 'mean', '1M %': 'mean', 'Ticker': 'count', 'Score': 'mean'}).sort_values('1W %', ascending=False)
        st.dataframe(sec_df.style.background_gradient(cmap='RdYlGn', subset=['1W %', '1M %']), use_container_width=True)
        

    with t4:
        st.subheader("⚠️ Volume Shockers (>3x Average)")
        # Showing stocks with unusual institutional activity
        shockers = df[df['Surge'] >= 3.0].sort_values(by="Surge", ascending=False)
        if not shockers.empty:
            st.warning("High volume surges often precede explosive 3-5 day moves.")
            st.dataframe(shockers[['Ticker', 'Sector', 'Surge', 'Price', 'Action']], use_container_width=True)
        else:
            st.write("No major volume surges detected in this scan depth.")

else:
    st.info("Scanner Ready. Run the scan to view market-wide sector performance.")

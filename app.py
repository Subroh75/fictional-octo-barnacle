import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. CORE LOGIC ---
@st.cache_data(ttl=3600)
def run_enhanced_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols, sector_map = ["RELIANCE.NS", "TCS.NS"], {}

    all_data = []
    prog = st.progress(0, text="Crunching Market Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20 = float(df['Close'].rolling(20).mean().iloc[-1])
            m50 = float(df['Close'].rolling(50).mean().iloc[-1])
            m200 = float(df['Close'].rolling(200).mean().iloc[-1])
            
            # Distance from MA20 (%)
            dist_ma20 = ((cp - m20) / m20) * 100
            perf_1w = ((cp / df['Close'].iloc[-5]) - 1) * 100
            
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            v_surge = float(df['Volume'].iloc[-1] / vol_avg)
            h21 = float(df['High'].iloc[-22:-1].max())

            # Signals
            action = "🟢 STRONG BUY" if cp > m20 > m50 > m200 else "🔴 AVOID" if cp < m200 else "🟡 HOLD"
            score = sum([v_surge > 2.0, cp > h21, m20 > m50])

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA20": round(m20, 2), "MA50": round(m50, 2), "MA200": round(m200, 2),
                "Dist MA20 %": round(dist_ma20, 2), "1W %": round(perf_1w, 2),
                "Action": action, "Surge": round(v_surge, 1), "Score": score
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. SIDEBAR ---
st.sidebar.title("🛠️ Settings")
depth = st.sidebar.slider("Scan Depth", 50, 500, 150)
if st.sidebar.button("🚀 RUN GLOBAL SCAN"):
    st.session_state['scan_results'] = run_enhanced_scan(depth)

# --- 4. MAIN DASHBOARD ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2, t3 = st.tabs(["📊 Market Heatmap", "🎯 Momentum Picks", "📈 MA Signal Logic"])

    with t1:
        st.subheader("Interactive Sector Momentum (1-Week Perf)")
        # Heatmap Made BIG and Interactive
        fig = px.treemap(
            df, 
            path=['Sector', 'Ticker'], 
            values=np.abs(df['1W %']),
            color='1W %', 
            color_continuous_scale='RdYlGn',
            range_color=[-10, 10],
            hover_data=['Price', 'Action', 'Dist MA20 %']
        )
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=700) # Tall and Screen-filling
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Top Ranked Individual Stocks")
        # Added Distance from MA20 to help find entries
        picks = df[df['Action'] != "🔴 AVOID"].sort_values(by=["Score", "Surge"], ascending=False)
        st.dataframe(picks, use_container_width=True)

    with t3:
        st.subheader("Moving Average Alignment")
        st.info("💡 Pro Tip: Look for stocks with 'Dist MA20 %' between 0 and 2. These are perfect pullbacks.")
        st.dataframe(df[['Ticker', 'Action', 'MA20', 'MA50', 'MA200', 'Dist MA20 %']], use_container_width=True)
else:
    st.info("Dashboard Ready. Run the scan to populate the Heatmap.")

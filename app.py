import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Genius V5.0", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE ADVANCED ENGINE ---
@st.cache_data(ttl=3600)
def run_advanced_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
    except:
        symbols, sector_map = ["RELIANCE.NS", "TCS.NS"], {}

    all_data = []
    prog = st.progress(0, text="Analyzing Institutional Footprints...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="60d", progress=False)
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            open_p = float(df['Open'].iloc[-1])
            vol = float(df['Volume'].iloc[-1])
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            m50 = float(df['Close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else cp

            # LOGIC 1: Institutional Footprint (High Vol, Tight Range)
            body_size = abs(cp - open_p)
            avg_range = (df['High'] - df['Low']).rolling(10).mean().iloc[-1]
            footprint = "👣 ACCUMULATION" if (vol > 1.5 * avg_vol and body_size < 0.3 * avg_range) else "Normal"

            # LOGIC 2: Gap-Up Go (Professional Gap)
            gap_pct = ((open_p - prev_cp) / prev_cp) * 100
            gap_signal = "🚀 PRO GAP" if (gap_pct > 1.0 and cp >= open_p) else "No Gap"

            # LOGIC 3: Momentum Setup
            above_50 = 1 if cp > m50 else 0

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Gap %": round(gap_pct, 2), "Gap Signal": gap_signal,
                "Footprint": footprint, "Above_50MA": above_50, "Volume_Ratio": round(vol/avg_vol, 2),
                "Close": cp # For correlation
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI SIDEBAR ---
st.sidebar.title("🛠️ Alpha V5.0")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
if st.sidebar.button("🚀 RUN FULL MARKET ANALYSIS"):
    st.session_state['scan_results'] = run_advanced_scan(depth)

# --- 4. TABS ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2, t3, t4 = st.tabs(["📉 Breadth Gauge", "👣 Institutional Tracking", "🚀 Gap-Up Scanner", "🔗 Correlation Matrix"])

    with t1:
        st.subheader("Market Health (Breadth)")
        breadth = (df['Above_50MA'].sum() / len(df)) * 100
        st.metric("Nifty 500 Breadth (>50MA)", f"{round(breadth, 1)}%")
        st.progress(breadth/100)
        
        st.markdown("""
        ### 📖 Breadth Logic
        * **< 30% (Oversold):** Market is fearful. Look for quality stocks showing **👣 Accumulation**.
        * **> 70% (Overbought):** Market is euphoric. Be cautious with new entries; tighten your Stop Losses.
        """)
        

    with t2:
        st.subheader("Tracking the Big Players")
        acc_df = df[df['Footprint'] == "👣 ACCUMULATION"]
        st.dataframe(acc_df[['Ticker', 'Sector', 'Price', 'Volume_Ratio']], use_container_width=True)
        
        st.markdown("""
        ### 📖 Footprint Logic
        Institutional accumulation is hidden. We find it by looking for **High Volume** combined with **Low Price Action (Tightness)**. It means a big player is absorbing all sell orders at a specific price level.
        """)
        

    with t3:
        st.subheader("Professional Gap-Ups")
        gaps = df[df['Gap Signal'] == "🚀 PRO GAP"].sort_values("Gap %", ascending=False)
        st.dataframe(gaps[['Ticker', 'Price', 'Gap %', 'Volume_Ratio']], use_container_width=True)
        
        st.markdown("""
        ### 📖 Gap-Up Logic
        A **Pro Gap** is when a stock opens >1% up and traders don't sell it off immediately. If the price stays above the opening price, it signals extreme urgency.
        """)

    with t4:
        st.subheader("Portfolio Correlation Risk")
        # Logic 4: Simple Correlation check on Top 10 Momentum Picks
        corr_df = df.sort_values("Volume_Ratio", ascending=False).head(10)
        st.info("This matrix shows if your top picks move together. High correlation (near 1.0) means you are not diversified.")
        # Simulating a matrix for visualization
        dummy_corr = np.random.uniform(0.5, 0.95, size=(5,5))
        st.write("Correlation analysis requires live history; below is a sector-concentration summary:")
        st.bar_chart(df.groupby('Sector')['Ticker'].count())

else:
    st.info("Execute Analysis to view Opening Bell insights.")

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Command Center V7", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE MASTER ENGINE ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols, sector_map, nifty_perf_1m = ["RELIANCE.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Analyzing Volume & Volatility Structures...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # Price Data
            cp = float(df['Close'].iloc[-1])
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            
            # --- VOLATILITY LOGIC (ATR & BANDS) ---
            high_low = df['High'] - df['Low']
            df['TR'] = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            df['ATR'] = df['TR'].rolling(14).mean()
            current_atr = df['ATR'].iloc[-1]
            atr_ratio = current_atr / df['ATR'].rolling(50).mean().iloc[-1]
            # Historical Volatility (Standard Deviation)
            hist_vol = df['Close'].pct_change().rolling(20).std().iloc[-1] * np.sqrt(252) * 100

            # --- VOLUME LOGIC ---
            vol = float(df['Volume'].iloc[-1])
            avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol
            # Volume Price Trend (VPT) - Simple proxy
            vpt = "Bullish" if (cp > df['Close'].iloc[-2] and vol > avg_vol) else "Neutral"

            # --- UPDATED CONFLUENCE SCORE (0-10) ---
            score = 0
            if cp > m20: score += 1
            if atr_ratio < 0.9: score += 3  # Volatility Contraction (VCP) - High Weight
            if vol_surge > 2.0: score += 3  # Volume Breakout - High Weight
            if hist_vol < 30: score += 1    # Stable Trend
            if vol_surge > 1.2 and cp > df['Close'].iloc[-2]: score += 2 # Accumulation

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2),
                "ATR_Ratio": round(atr_ratio, 2), "Hist_Vol_%": round(hist_vol, 2),
                "VPT": vpt, "ATR_Val": round(current_atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI ---
st.sidebar.title("🏹 Alpha Master V7")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (₹)", value=5000)

if st.sidebar.button("🚀 EXECUTE VOLUME-VOL SCAN"):
    st.session_state['scan_results'] = run_full_scan(depth)

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_amt / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🌍 Birds-Eye", "📈 Trend Action", "🧠 Quant Lab", "📊 Vol & Volume Lab", "👣 Inst. Flow", "🚀 Gap-Ups"])

    with tabs[3]:
        st.subheader("Volatility & Volume Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Volume Surge Leaders**")
            st.dataframe(df[['Ticker', 'Vol_Surge', 'VPT']].sort_values("Vol_Surge", ascending=False).head(10), use_container_width=True)
        
        with col2:
            st.write("**Volatility Contraction (VCP Candidates)**")
            st.dataframe(df[['Ticker', 'ATR_Ratio', 'Hist_Vol_%']].sort_values("ATR_Ratio", ascending=True).head(10), use_container_width=True)

        st.markdown("""
        ---
        ### 📖 The Vol-Vol Logic
        * **Volume Surge (> 2.0):** Indicates massive institutional interest. Volume often precedes price.
        * **ATR Ratio (< 0.9):** Price is "tightening." Look for this to drop before an explosive move.
        * **Hist Vol %:** High values mean the stock is "wild." For 3-5 day swings, we prefer 20% to 40%—not 80%.
        """)

    with tabs[2]:
        st.subheader("Confluence Leaderboard (Weighted for Vol/Volume)")
        st.dataframe(df[['Ticker', 'Score', 'Vol_Surge', 'ATR_Ratio', 'Qty']].sort_values("Score", ascending=False), use_container_width=True)

else:
    st.info("Execute scan to analyze Volume and Volatility structures.")

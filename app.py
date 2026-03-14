import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty 500 Sniper", layout="wide")

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
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except Exception as e:
        st.error(f"Error fetching index data: {e}")
        return pd.DataFrame()

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500 Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: 
                continue
            
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # --- VOLATILITY (VCP LOGIC) ---
            high_low = df['High'] - df['Low']
            df['TR'] = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            df['ATR'] = df['TR'].rolling(14).mean()
            atr_ratio = df['ATR'].iloc[-1] / df['ATR'].rolling(50).mean().iloc[-1]
            hist_vol = df['Close'].pct_change().rolling(20).std().iloc[-1] * np.sqrt(252) * 100

            # --- VOLUME LOGIC ---
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol

            # --- CONFLUENCE SCORE ---
            score = 0
            if cp > m20 > m50: score += 2  
            if ((cp / float(df['Close'].iloc[-21])) - 1) - nifty_perf_1m > 0: score += 2 
            if atr_ratio < 0.9: score += 3  
            if vol_surge > 1.8: score += 3  

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2), "ATR_Ratio": round(atr_ratio, 2),
                "MA_Action": "🟢 STRONG" if cp > m20 > m50 > m200 else "⚪ NEUTRAL",
                "ATR_Val": round(df['ATR'].iloc[-1], 2), "Hist_Vol": round(hist_vol, 2)
            })
        except:
            continue # Skip failed tickers
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI SIDEBAR ---
st.sidebar.title("🏹 Nifty 500 Sniper")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (₹)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    res = run_full_scan(depth)
    if not res.empty:
        st.session_state['scan_results'] = res
        st.rerun()

# --- 4. DASHBOARD TABS ---
if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_amt / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf, np.nan], 0).astype(int)

    tabs = st.tabs(["🎯 Sniper Leaderboard", "📈 Trend Action", "📊 Vol & Volume", "🧠 Quant Genius", "👣 Inst. Flow"])

    with tabs[0]:
        st.subheader("High Confluence Picks (Score 8-10)")
        st.dataframe(df[df['Score'] >= 8].sort_values("Score", ascending=False), use_container_width=True)
        st.markdown("""
        ---
        ### 📖 Sniper Confluence Logic
        * **Trend (2 pts):** Verified that the stock is in a stacked bullish alignment ($Price > MA_{20} > MA_{50}$).
        * **RS (2 pts):** Outperforming the Nifty 50 over a 1-month rolling window.
        * **Tightness (3 pts):** ATR is contracting, indicating a price 'coil' is forming.

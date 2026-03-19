import numpy as np
# Fix for NumPy 2.0 / Backtesting compatibility
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper AI v2.0", layout="wide")

# Version Marker to ensure the app actually updated
st.sidebar.markdown("### 🛠️ System Version: 2.0 (Deep Scan)")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- 2. THE BRUTE FORCE DATA ENGINE (NO CACHE) ---
# We removed @st.cache_data to force a fresh UI update
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "3MINDIA.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Force-Scanning Market Structure...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Fetch 2 years to ensure MA200 is possible
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 200: continue
            
            # --- THE 2026 HEADER BYPASS ---
            # Extracting RAW numpy arrays to avoid MultiIndex NaN bugs
            c_raw = raw['Close'].values.flatten()
            v_raw = raw['Volume'].values.flatten()
            
            # Manual Math (More stable than rolling() in 2026)
            cp = float(c_raw[-1])
            m20 = float(np.mean(c_raw[-20:]))
            m50 = float(np.mean(c_raw[-50:]))
            m200 = float(np.mean(c_raw[-200:]))
            
            dist_ma20 = ((cp - m20) / m20) * 100
            
            avg_vol = float(np.mean(v_raw[-20:]))
            vol_surge = float(v_raw[-1]) / avg_vol if avg_vol != 0 else 0

            # Trend Determination
            trend = "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL"
            
            # Action Logic
            p_change = (cp - c_raw[-2]) / c_raw[-2]
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.8) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"

            all_data.append({
                "Ticker": t, 
                "Sector": sector_map.get(t, "Misc"), 
                "Price": round(cp, 2),
                "MA 20": round(m20, 2), 
                "MA 50": round(m50, 2), 
                "MA 200": round(m200, 2),
                "MA20 Dist": f"{round(dist_ma20, 2)}%", 
                "Vol_Surge": round(vol_surge, 2), 
                "Action": action,
                "Trend": trend
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper AI")
v_depth = st.sidebar.slider("Scan Depth", 10, 500, 50)

if st.sidebar.button("🚀 RUN DEEP SCAN"):
    # Clear session state to force table refresh
    if 'scan_results' in st.session_state:
        del st.session_state['scan_results']
    
    res = run_full_scan(v_depth)
    if not res.empty:
        st.session_state['scan_results'] = res

if st.session_state.get('scan_results') is not None:
    df = st.session_state['scan_results']
    
    # NEW TABS WITH EXPLICIT COLUMN CALLS
    t1, t2 = st.tabs(["🎯 Main Dashboard", "📈 Trend & MA Lab"])
    
    with t1:
        st.subheader("Leaderboard")
        st.dataframe(df.sort_values("Price", ascending=False), use_container_width=True)
        
    with t2:
        st.subheader("Structural Moving Averages")
        # If this table doesn't show 7 columns, the app hasn't refreshed
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200', 'MA20 Dist', 'Trend']], use_container_width=True)
else:
    st.info("Ready. Use the sidebar and click 'RUN DEEP SCAN'.")

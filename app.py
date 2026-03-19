import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd

# --- 0. THE UPDATE CHECK ---
st.error("⚠️ SYSTEM RESET ACTIVE: Version 2.1 Deployment")
st.sidebar.warning("App Updated: March 20, 2026")

# --- 1. DATA ENGINE (RAW NUMPY MATH) ---
def run_force_scan(limit):
    # Standard Nifty 500 URL
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS"]

    all_data = []
    prog = st.progress(0, text="Bypassing Cache...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Fetching 2 years for 200 SMA
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 200: continue
            
            # --- THE RAW EXTRACTION ---
            c_raw = raw['Close'].values.flatten()
            
            cp = float(c_raw[-1])
            # Direct Numpy Mean (Bypasses all Pandas Column naming bugs)
            m20 = float(np.mean(c_raw[-20:]))
            m50 = float(np.mean(c_raw[-50:]))
            m200 = float(np.mean(c_raw[-200:]))
            
            dist_ma20 = ((cp - m20) / m20) * 100
            
            all_data.append({
                "Ticker": t, 
                "Price": round(cp, 2),
                "MA 20": round(m20, 2), 
                "MA 50": round(m50, 2), 
                "MA 200": round(m200, 2),
                "MA20 Dist %": f"{round(dist_ma20, 2)}%",
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL"
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 2. INTERFACE ---
st.title("🏹 Nifty Sniper Elite")
depth = st.sidebar.slider("Scan Depth", 10, 100, 30)

if st.sidebar.button("🚀 FORCE RE-SCAN"):
    # Clear all state to kill the "Ghost" data
    st.cache_data.clear()
    for key in st.session_state.keys():
        del st.session_state[key]
        
    res = run_force_scan(depth)
    if not res.empty:
        st.session_state['new_results'] = res

if 'new_results' in st.session_state:
    st.subheader("📊 Structural Trend & MA Analysis")
    # This table HAS to show the new columns
    st.dataframe(st.session_state['new_results'], use_container_width=True)
else:
    st.info("Click 'FORCE RE-SCAN' to initialize Version 2.1")
